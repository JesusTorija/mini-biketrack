import gpxpy
import math
import pandas as pd

class GPXRouteAnalyzer:
    """
    Clase para leer y procesar archivos GPX de rutas de ciclismo,
    extrayendo distancias, desniveles y pendientes por segmentos con suavizado robusto.
    """
    def __init__(self, gpx_file_path: str, smooth_distance_m: float = 50.0):
        self.gpx_file_path = gpx_file_path
        self.smooth_distance_m = smooth_distance_m  
        self.points = []
        self.segments = []
        self._parse_gpx()
        self._smooth_elevations_robust()
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

    def _smooth_elevations_robust(self):
        """
        Aplica un suavizado robusto y efectivo a las altitudes utilizando una ventana 
        deslizante basada en la distancia configurada (smooth_distance_m).
        """
        if not self.points or self.smooth_distance_m <= 0:
            return

        n = len(self.points)
        if n < 3:
            return

        # Extraer elevaciones a un DataFrame de pandas para aplicar un suavizado limpio y rápido
        elevations = [p['elevation'] for p in self.points]
        df_temp = pd.DataFrame({'elevation': elevations})

        # Estimar cuántos puntos abarca aproximadamente el radio de suavizado
        # Calculamos la distancia total media entre puntos consecutivos
        total_dist = 0.0
        for i in range(n - 1):
            total_dist += self._haversine_distance(
                self.points[i]['latitude'], self.points[i]['longitude'],
                self.points[i+1]['latitude'], self.points[i+1]['longitude']
            )
        
        avg_spacing = total_dist / max(1, n - 1)
        # Ventana de puntos basada en los metros solicitados (mínimo 3 puntos)
        window_size = max(3, int(self.smooth_distance_m / max(0.5, avg_spacing)))
        # Asegurar que la ventana sea impar para mantener simetría
        if window_size % 2 == 0:
            window_size += 1

        # Aplicar media móvil centrada para eliminar picos de GPS sin retrasar la altitud
        smoothed_series = df_temp['elevation'].rolling(window=window_size, center=True, min_periods=1).mean()
        
        # Asignar de vuelta las altitudes suavizadas
        for i, p in enumerate(self.points):
            p['elevation'] = float(smoothed_series.iloc[i])

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

            # Límite físico de seguridad para descartar cualquier micro-ruido remanente (>30% o <-30%)
            gradient = max(-30.0, min(30.0, gradient))

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