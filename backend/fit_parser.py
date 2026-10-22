import fitparse
import math
import pandas as pd

class FITRouteAnalyzer:
    """
    Clase para leer y procesar archivos .fit de actividades de ciclismo de forma optimizada,
    extrayendo geometría, perfiles de altitud, y registros reales de potencia y velocidad.
    """
    def __init__(self, fit_file_path: str, smooth_distance_m: float = 50.0):
        self.fit_file_path = fit_file_path
        self.smooth_distance_m = smooth_distance_m
        self.points = []
        self.segments = []
        self.telemetry_records = []
        self._parse_fit()
        self._smooth_elevations_robust()
        self._calculate_segments()

    def _parse_fit(self):
        """Lee el archivo FIT extrayendo la telemetría completa para métricas exactas y optimizando solo la visualización."""
        try:
            fitfile = fitparse.FitFile(self.fit_file_path)
            all_records = []

            for record in fitfile.get_messages('record'):
                data = {}
                for field in record:
                    if field.name and field.value is not None:
                        data[field.name] = field.value

                lat = data.get('position_lat')
                lon = data.get('position_long')

                if lat is not None and lon is not None:
                    lat_deg = lat * (180.0 / 2**31)
                    lon_deg = lon * (180.0 / 2**31)
                    alt = data.get('altitude', data.get('enhanced_altitude', 0.0))
                    timestamp = data.get('timestamp')

                    speed_ms = data.get('speed', data.get('enhanced_speed', 0.0))
                    power_w = data.get('power', 0.0)
                    speed_kmh = float(speed_ms * 3.6) if speed_ms else 0.0

                    # Filtrar parones (velocidad < 2.5 km/h)
                    if speed_kmh < 2.5:
                        continue

                    all_records.append({
                        'latitude': lat_deg,
                        'longitude': lon_deg,
                        'elevation': float(alt) if alt is not None else 0.0,
                        'time': timestamp,
                        'real_speed_kmh': speed_kmh,
                        'real_power_watts': float(power_w) if power_w else 0.0
                    })

            if not all_records:
                raise ValueError("No se encontraron registros de movimiento válidos en el archivo FIT.")

            # Guardamos la telemetría completa antes de recortar, para que los cálculos de energía y totales sean exactos
            self.telemetry_records = all_records

            # Recorte exclusivo para los puntos de renderizado y análisis si son excesivos
            if len(all_records) > 5000:
                step = len(all_records) // 3000
                self.points = all_records[::step]
            else:
                self.points = all_records

        except Exception as e:
            raise RuntimeError(f"Error al parsear el archivo FIT: {e}")

    def _haversine_distance(self, lat1, lon1, lat2, lon2) -> float:
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
        if not self.points or self.smooth_distance_m <= 0:
            return

        n = len(self.points)
        if n < 3:
            return

        elevations = [p['elevation'] for p in self.points]
        df_temp = pd.DataFrame({'elevation': elevations})

        total_dist = 0.0
        for i in range(n - 1):
            total_dist += self._haversine_distance(
                self.points[i]['latitude'], self.points[i]['longitude'],
                self.points[i+1]['latitude'], self.points[i+1]['longitude']
            )
        
        avg_spacing = total_dist / max(1, n - 1)
        window_size = max(3, int(self.smooth_distance_m / max(0.5, avg_spacing)))
        if window_size % 2 == 0:
            window_size += 1

        smoothed_series = df_temp['elevation'].rolling(window=window_size, center=True, min_periods=1).mean()
        
        for i, p in enumerate(self.points):
            p['elevation'] = float(smoothed_series.iloc[i])

    def _calculate_segments(self):
        self.segments = []
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i+1]

            dist_horizontal = self._haversine_distance(p1['latitude'], p1['longitude'], p2['latitude'], p2['longitude'])
            elev_change = p2['elevation'] - p1['elevation']
            dist_3d = math.sqrt(dist_horizontal**2 + elev_change**2)

            gradient = (elev_change / dist_horizontal * 100.0) if dist_horizontal > 0.1 else 0.0
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
        total_distance = sum(seg['distance_m'] for seg in self.segments) / 1000.0  
        elevation_gain = 0.0
        elevation_loss = 0.0
        threshold = 3.0

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