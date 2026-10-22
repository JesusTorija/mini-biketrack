import math
import pandas as pd

class CyclingPhysicsSimulator:
    """
    Motor de física avanzado parametrizado al 100% mediante configuración externa.
    """
    def __init__(self, segments: list, config: dict):
        self.config = config  
        
        smoothing_method = config.get('smoothing_method', 'standard')
        self.segments = self._apply_smoothing(segments, smoothing_method)
        
        cyclist = config['cyclist']
        self.total_mass = cyclist['weight_kg'] + cyclist['bike_weight_kg']
        self.ftp = cyclist['ftp_watts']
        self.intensity_factor = cyclist.get('intensity_factor', 0.88)
        self.base_target_power = cyclist.get('target_power_watts', self.ftp * self.intensity_factor)
        
        self.cda_seated = cyclist['cda_seated']
        self.cda_standing = cyclist['cda_standing']
        self.cr = cyclist['rolling_resistance_cr']
        self.drivetrain_loss = cyclist.get('drivetrain_loss_percent', 2.5) / 100.0
        
        w_prime_kj = cyclist.get('w_prime_kj', 20.0)
        self.w_prime_max = w_prime_kj * 1000.0
        self.w_prime_current = self.w_prime_max

        self.fatigue_rate_per_1000kj = cyclist.get('fatigue_rate_per_1000kj', 1.5) / 100.0
        self.severe_depletion_penalty_factor = cyclist.get('severe_depletion_penalty_factor', 0.92)
        self.severe_depletion_threshold_pct = cyclist.get('severe_depletion_threshold_pct', 15.0)

        env = config.get('environment', {})
        self.base_air_density = env.get('air_density', 1.225)
        self.wind_speed = env.get('wind_speed_ms', 0.0)
        
        limits = config.get('simulation_limits', {})
        self.min_speed_ms = limits.get('min_speed_ms', 1.0)
        self.max_descent_speed_ms = limits.get('max_descent_speed_kmh', 75.0) / 3.6
        self.descent_braking_factor = limits.get('descent_braking_factor', 0.85)
        self.braking_speed_threshold_kmh = limits.get('braking_speed_threshold_kmh', 45.0)
        self.technical_descent_gradient = limits.get('technical_descent_gradient', -8.0)
        self.technical_descent_damping = limits.get('technical_descent_damping', 0.75)
        self.standing_threshold_ms = limits.get('standing_speed_threshold_kmh', 15.0) / 3.6
        
        strategy = config.get('power_strategy', {})
        self.climb_gradient_threshold = strategy.get('climb_gradient_threshold', 4.0)
        self.climb_power_multiplier = strategy.get('climb_power_multiplier', 1.15)
        self.climb_excess_gradient_factor = strategy.get('climb_excess_gradient_factor', 0.03)
        self.descent_gradient_threshold = strategy.get('descent_gradient_threshold', -4.5)
        self.descent_power_watts = strategy.get('descent_power_watts', 20.0)
        self.false_flat_gradient_limit = strategy.get('false_flat_gradient_limit', 0.0)
        self.false_flat_power_factor = strategy.get('false_flat_power_factor', 0.75)
        self.exhausted_power_multiplier = strategy.get('exhausted_power_multiplier', 0.90)
        
        # Parámetros del factor oculto de "muros" (pendientes altas)
        self.steep_wall_threshold = strategy.get('steep_wall_threshold', 8.0)
        
        inertia = config.get('inertia', {})
        self.inertia_prev_weight = inertia.get('previous_speed_weight', 0.75)
        self.inertia_curr_weight = inertia.get('current_speed_weight', 0.25)
        self.power_prev_weight = inertia.get('previous_power_weight', 0.8)
        self.power_curr_weight = inertia.get('current_power_weight', 0.2)
        self.w_prime_recovery_multiplier = inertia.get('w_prime_recovery_multiplier', 0.1)
        self.w_prime_accumulation_divisor = inertia.get('w_prime_accumulation_divisor', 3000.0)
        self.w_prime_min_accumulation_factor = inertia.get('w_prime_min_accumulation_factor', 0.4)

        self.g = 9.81

    def _apply_smoothing(self, segments: list, method: str) -> list:
        if method != 'sql_double_ma' or not segments:
            return segments

        radius_1 = self.config.get('smooth_radius_1', 500.0)
        radius_2 = self.config.get('smooth_radius_2', 250.0)
        
        if radius_1 <= 0 and radius_2 <= 0:
            return segments

        n = len(segments)
        dist_acums = []
        current_dist_acum = 0.0
        abs_elevations = []
        curr_ele = 0.0

        for seg in segments:
            current_dist_acum += seg.get('distance_m', 0.0)
            dist_acums.append(current_dist_acum)
            curr_ele += seg.get('elevation_change_m', 0.0)
            abs_elevations.append(curr_ele)

        smoothed_pass1 = []
        for i, d in enumerate(dist_acums):
            window_elevations = [
                abs_elevations[j] for j in range(n) 
                if dist_acums[j] >= d - radius_1 and dist_acums[j] <= d + radius_1
            ]
            avg_ele = sum(window_elevations) / len(window_elevations) if window_elevations else abs_elevations[i]
            smoothed_pass1.append(avg_ele)

        smoothed_pass2 = []
        for i, d in enumerate(dist_acums):
            window_elevations = [
                smoothed_pass1[j] for j in range(n) 
                if dist_acums[j] >= d - radius_2 and dist_acums[j] <= d + radius_2
            ]
            avg_ele = sum(window_elevations) / len(window_elevations) if window_elevations else smoothed_pass1[i]
            smoothed_pass2.append(avg_ele)

        new_segments = []
        prev_smoothed_ele = 0.0
        for i, seg in enumerate(segments):
            new_seg = seg.copy()
            current_smoothed_ele = smoothed_pass2[i]
            new_elevation_change = current_smoothed_ele - prev_smoothed_ele
            prev_smoothed_ele = current_smoothed_ele

            new_seg['elevation_change_m'] = new_elevation_change
            new_seg['absolute_elevation_m'] = current_smoothed_ele
            dist = new_seg.get('distance_m', 0.0)
            if dist > 0:
                new_seg['gradient_percent'] = (new_elevation_change / dist) * 100.0
            
            new_segments.append(new_seg)

        return new_segments

    def detect_climbs(self, df_sim: pd.DataFrame) -> list:
        if df_sim.empty or 'gradient_percent' not in df_sim.columns:
            return []

        climbs = []
        in_climb = False
        start_dist = 0.0
        elevation_gain = 0.0
        distance_climb = 0.0

        for i, row in df_sim.iterrows():
            dist = row['distance_m']
            elev_change = row['elevation_change_m']
            grad = row['gradient_percent']
            dist_cum = row['distance_accumulated_km'] * 1000.0

            if not in_climb:
                if grad >= 2.0:
                    in_climb = True
                    start_dist = dist_cum - dist
                    elevation_gain = max(0.0, elev_change)
                    distance_climb = dist
            else:
                if grad < -1.0 or (grad < 1.0 and elev_change < 0):
                    if distance_climb >= 200 and elevation_gain >= 30:
                        avg_slope = (elevation_gain / distance_climb) * 100.0
                        climb_type = "Puerto" if (avg_slope > 4.5 and distance_climb > 500) else "Repecho"
                        
                        climbs.append({
                            'start_dist_km': start_dist / 1000.0,
                            'end_dist_km': dist_cum / 1000.0,
                            'distance_m': distance_climb,
                            'elevation_gain_m': elevation_gain,
                            'average_slope_percent': avg_slope,
                            'type': climb_type
                        })
                    in_climb = False
                    elevation_gain = 0.0
                    distance_climb = 0.0
                else:
                    distance_climb += dist
                    if elev_change > 0:
                        elevation_gain += elev_change

        if in_climb and distance_climb >= 200 and elevation_gain >= 30:
            avg_slope = (elevation_gain / distance_climb) * 100.0
            climb_type = "Puerto" if (avg_slope > 4.5 and distance_climb > 500) else "Repecho"
            climbs.append({
                'start_dist_km': start_dist / 1000.0,
                'end_dist_km': df_sim['distance_accumulated_km'].iloc[-1],
                'distance_m': distance_climb,
                'elevation_gain_m': elevation_gain,
                'average_slope_percent': avg_slope,
                'type': climb_type
            })

        return climbs

    def _determine_segment_power(self, gradient_percent: float, eff_ftp: float, eff_base_power: float, w_prime_pct: float) -> float:
        if gradient_percent > self.climb_gradient_threshold:
            excess_gradient = max(0.0, gradient_percent - self.climb_gradient_threshold)
            multiplier = min(self.climb_power_multiplier, 1.0 + (excess_gradient * self.climb_excess_gradient_factor))
            raw_power = min(eff_ftp * 1.1, eff_base_power * multiplier)
            
        elif gradient_percent < self.descent_gradient_threshold:
            raw_power = self.descent_power_watts
            
        elif gradient_percent < self.false_flat_gradient_limit:
            raw_power = eff_base_power * self.false_flat_power_factor
            
        else:
            raw_power = eff_base_power

        if w_prime_pct <= 0.0:
            raw_power = min(raw_power, eff_ftp * self.exhausted_power_multiplier)

        return raw_power

    def _solve_speed_for_segment(self, distance_m: float, elevation_change_m: float, power_watts: float, previous_v: float, air_density: float) -> float:
        if distance_m <= 0:
            return previous_v

        dist_3d = math.sqrt(distance_m**2 + elevation_change_m**2)
        if dist_3d == 0:
            return previous_v
        
        sin_theta = elevation_change_m / dist_3d
        gradient_pct = (elevation_change_m / distance_m) * 100.0 if distance_m > 0 else 0.0
        p_wheel = power_watts * (1.0 - self.drivetrain_loss)

        v = max(self.min_speed_ms, previous_v)
        
        for _ in range(15):
            v_rel = v + self.wind_speed
            v_rel_squared = v_rel * abs(v_rel)

            is_climbing = elevation_change_m > 0
            is_slow = v < self.standing_threshold_ms
            cda = self.cda_standing if (is_climbing and is_slow) else self.cda_seated

            p_aero = 0.5 * air_density * cda * v_rel_squared * v
            p_grav = self.total_mass * self.g * sin_theta * v
            p_roll = self.cr * self.total_mass * self.g * max(0.0, math.cos(math.asin(max(-1.0, min(1.0, sin_theta))))) * v

            p_resistances = p_aero + p_grav + p_roll
            diff = p_wheel - p_resistances

            if abs(diff) < 0.1:
                break

            dp_dv = 1.5 * air_density * cda * (v_rel**2) + self.total_mass * self.g * sin_theta + self.cr * self.total_mass * self.g * math.cos(math.asin(max(-1.0, min(1.0, sin_theta))))
            v += diff / max(20.0, dp_dv)
            
            if v < self.min_speed_ms:
                v = self.min_speed_ms

        # FACTOR OCULTO DE MUROS: Penalización no lineal de velocidad en pendientes altas
        if elevation_change_m > 0 and gradient_pct > self.steep_wall_threshold:
            excess_slope = gradient_pct - self.steep_wall_threshold
            # Aplica una fricción/pérdida adicional progresiva por cada % por encima del umbral (ej. > 8%)
            wall_penalty = max(0.75, 1.0 - (excess_slope * 0.015))
            v *= wall_penalty

        if elevation_change_m < 0:
            if gradient_pct < self.technical_descent_gradient:
                v *= self.technical_descent_damping

            v_kmh_temp = v * 3.6
            if v_kmh_temp > self.braking_speed_threshold_kmh:
                braking_span = (self.max_descent_speed_ms * 3.6) - self.braking_speed_threshold_kmh
                excess_speed = v_kmh_temp - self.braking_speed_threshold_kmh
                braking_adjustment = 1.0 - ((1.0 - self.descent_braking_factor) * (excess_speed / max(1.0, braking_span)))
                v = v * max(self.descent_braking_factor, braking_adjustment)

            if v > self.max_descent_speed_ms:
                v = self.max_descent_speed_ms

        smoothed_v = (self.inertia_prev_weight * previous_v) + (self.inertia_curr_weight * v)
        return smoothed_v

    def run_simulation(self) -> dict:
        total_time_seconds = 0.0
        detailed_segments = []
        
        self.w_prime_current = self.w_prime_max
        if self.segments and self.segments[0]['distance_m'] > 0:
            first_grad = self.segments[0]['gradient_percent']
            current_v = 3.0 if first_grad > 3.0 else 5.0
        else:
            current_v = 4.0

        previous_power = self.base_target_power
        background_elevation = 0.0
        total_energy_kj = 0.0

        for i, seg in enumerate(self.segments):
            dist = seg['distance_m']
            elev_change = seg['elevation_change_m']
            gradient = seg['gradient_percent']
            background_elevation += elev_change

            current_air_density = self.base_air_density * math.exp(-max(0.0, background_elevation) / 8400.0)

            altitude_penalty = 1.0
            if background_elevation > 600.0:
                altitude_penalty = 1.0 - ((background_elevation - 600.0) / 300.0) * 0.01
                altitude_penalty = max(0.80, altitude_penalty)

            w_prime_pct_current = (self.w_prime_current / self.w_prime_max) * 100.0
            severe_depletion_penalty = self.severe_depletion_penalty_factor if w_prime_pct_current < self.severe_depletion_threshold_pct else 1.0
            base_fatigue_factor = max(0.70, 1.0 - (total_energy_kj / 1000.0) * self.fatigue_rate_per_1000kj)
            
            fatigue_factor = base_fatigue_factor * severe_depletion_penalty * altitude_penalty

            current_effective_ftp = self.ftp * fatigue_factor
            current_effective_base_power = self.base_target_power * fatigue_factor

            raw_segment_power = self._determine_segment_power(gradient, current_effective_ftp, current_effective_base_power, w_prime_pct_current)
            segment_power = (self.power_prev_weight * previous_power) + (self.power_curr_weight * raw_segment_power)
            previous_power = segment_power

            current_v = self._solve_speed_for_segment(dist, elev_change, segment_power, current_v, current_air_density)
            
            time_s = dist / current_v if current_v > 0 else 0.0
            total_time_seconds += time_s

            segment_kj = (segment_power * time_s) / 1000.0
            total_energy_kj += segment_kj

            power_diff = segment_power - current_effective_ftp
            if power_diff > 0:
                energy_spent = power_diff * time_s
                self.w_prime_current = max(0.0, self.w_prime_current - energy_spent)
            else:
                accumulation_penalty = max(self.w_prime_min_accumulation_factor, 1.0 - (total_energy_kj / self.w_prime_accumulation_divisor))
                recovery_rate = abs(power_diff) * self.w_prime_recovery_multiplier * accumulation_penalty
                self.w_prime_current = min(self.w_prime_max, self.w_prime_current + (recovery_rate * time_s))

            v_kmh = current_v * 3.6
            w_prime_final_pct = (self.w_prime_current / self.w_prime_max) * 100.0

            detailed_segments.append({
                'segment_index': i,
                'distance_m': dist,
                'elevation_change_m': elev_change,
                'gradient_percent': gradient,
                'speed_kmh': v_kmh,
                'power_watts': segment_power,
                'time_seconds': time_s,
                'w_prime_joules': self.w_prime_current,
                'w_prime_percent': w_prime_final_pct,
                'energy_kj_accumulated': total_energy_kj,
                'effective_ftp_watts': current_effective_ftp
            })

        df_sim_temp = pd.DataFrame(detailed_segments)
        df_sim_temp['distance_accumulated_km'] = df_sim_temp['distance_m'].cumsum() / 1000.0
        
        detected_climbs = self.detect_climbs(df_sim_temp)

        hours = int(total_time_seconds // 3600)
        minutes = int((total_time_seconds % 3600) // 60)
        seconds = int(total_time_seconds % 60)
        formatted_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        total_dist_km = sum(s['distance_m'] for s in self.segments) / 1000.0
        avg_speed = (total_dist_km / (total_time_seconds / 3600.0)) if total_time_seconds > 0 else 0.0

        return {
            'total_time_seconds': total_time_seconds,
            'formatted_time': formatted_time_str,
            'average_speed_kmh': avg_speed,
            'segments_simulation': detailed_segments,
            'detected_climbs': detected_climbs
        }