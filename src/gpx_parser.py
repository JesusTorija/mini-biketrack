import gpxpy
import math

class GPXRouteAnalyzer:
    """
    Clase para leer y procesar archivos GPX de rutas de ciclismo,
    extrayendo distancias, desniveles y pendientes por segmentos.
    """
    def __init__(self, gpx_file_path: str, smooth_distance_m: float = 50.0):
        self.gpx_file_path = gpx_file_path
        self.smooth_distance_m = smooth_distance_m  # Distancia en metros para la ventana de suavizado
        self.points = []
        self.segments = []
        self._parse_gpx()
        self._smooth_elevations_spatial()
        self._calculate_segments()

    def _parse_gpx(self):
        """Lee el archivo GPX y extrae los puntos de la primera ruta/track encontrada."""
        with open(self.gpx_file_path, 'r', encoding='utf-8') as f:
            gpx = gpxpy.parse(f)

        raw_points = []
        for track in gpx.tracks:
            for segment in track.segments:
                raw_points.extend(segment.points)
        
        if not raw_points:
            for route in gpx.routes:
                raw_points.extend(route.points)

        if not raw_points:
            raise ValueError("No se encontraron puntos válidos (tracks o routes) en el archivo GPX.")

        for p in raw_points:
            self.points.append({
                'latitude': p.latitude,
                'longitude': p.longitude,
                'elevation': p.elevation if p.elevation is not None else 0.0,
                'time': p.time
            })

    def _haversine_distance(self, lat1, lon1, lat2, lon2) -> float:
        """Calcula la distancia en metros entre dos puntos geográficos usando Haversine."""
        R = 6371000  
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0)**2 + \
            math.cos(phi1) * math.cos(phi2) * \
            math.sin(delta_lambda / 2.0)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _smooth_elevations_spatial(self):
        """Aplica un suavizado espacial promediando las elevaciones dentro de un radio de distancia."""
        if not self.points or self.smooth_distance_m <= 0:
            return

        n = len(self.points)
        elevations = [p['elevation'] for p in self.points]
        smoothed = elevations.copy()

        if n < 3:
            return

        for i in range(n):
            nearby_elevations = []
            
            # Hacia atrás
            dist_back = 0.0
            j = i
            while j >= 0 and dist_back <= self.smooth_distance_m:
                nearby_elevations.append(elevations[j])
                if j > 0:
                    dist_back += self._haversine_distance(
                        self.points[j]['latitude'], self.points[j]['longitude'],
                        self.points[j-1]['latitude'], self.points[j-1]['longitude']
                    )
                j -= 1

            # Hacia adelante
            dist_fwd = 0.0
            j = i + 1
            while j < n and dist_fwd <= self.smooth_distance_m:
                nearby_elevations.append(elevations[j])
                if j < n - 1:
                    dist_fwd += self._haversine_distance(
                        self.points[j]['latitude'], self.points[j]['longitude'],
                        self.points[j+1]['latitude'], self.points[j+1]['longitude']
                    )
                j += 1

            if nearby_elevations:
                smoothed[i] = sum(nearby_elevations) / len(nearby_elevations)

        for i, p in enumerate(self.points):
            p['elevation'] = smoothed[i]

    def _calculate_segments(self):
        """Genera los segmentos de la ruta calculando distancias, desniveles y pendientes."""
        self.segments = []
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i+1]

            dist_horizontal = self._haversine_distance(p1['latitude'], p1['longitude'], p2['latitude'], p2['longitude'])
            elev_change = p2['elevation'] - p1['elevation']
            dist_3d = math.sqrt(dist_horizontal**2 + elev_change**2)

            if dist_horizontal > 0.1:
                gradient = (elev_change / dist_horizontal) * 100.0
            else:
                gradient = 0.0

            self.segments.append({
                'start_point': p1,
                'end_point': p2,
                'distance_m': dist_horizontal,
                'distance_3d_m': dist_3d,
                'elevation_start': p1['elevation'],
                'elevation_end': p2['elevation'],
                'elevation_change_m': elev_change,
                'gradient_percent': gradient
            })

    def get_summary(self) -> dict:
        """Devuelve un resumen general de la ruta aplicando histéresis estricta."""
        total_distance = sum(seg['distance_m'] for seg in self.segments) / 1000.0  

        elevation_gain = 0.0
        elevation_loss = 0.0
        threshold = 3.0  # Umbral de histéresis en metros

        if self.points:
            min_alt = self.points[0]['elevation']
            max_alt = self.points[0]['elevation']
            trend = 0  

            for p in self.points:
                alt = p['elevation']
                if trend == 0:
                    if alt > max_alt: max_alt = alt
                    if alt < min_alt: min_alt = alt
                    if max_alt - min_alt >= threshold:
                        if alt == max_alt:
                            trend = 1
                            elevation_gain += (max_alt - min_alt)
                            min_alt = max_alt
                        else:
                            trend = -1
                            elevation_loss += (max_alt - min_alt)
                            max_alt = min_alt
                elif trend == 1:
                    if alt > max_alt: max_alt = alt
                    elif max_alt - alt >= threshold:
                        elevation_gain += (max_alt - min_alt)
                        min_alt = alt
                        max_alt = alt
                        trend = -1
                elif trend == -1:
                    if alt < min_alt: min_alt = alt
                    elif alt - min_alt >= threshold:
                        elevation_loss += (max_alt - min_alt)
                        max_alt = alt
                        min_alt = alt
                        trend = 1

            if trend == 1 and max_alt - min_alt >= threshold:
                elevation_gain += (max_alt - min_alt)
            elif trend == -1 and max_alt - min_alt >= threshold:
                elevation_loss += (max_alt - min_alt)

        return {
            'total_distance_km': total_distance,
            'elevation_gain_m': elevation_gain,
            'elevation_loss_m': elevation_loss,
            'num_points': len(self.points),       
            'total_points': len(self.points)    
        }

    def get_segments(self) -> list:
        return self.segments