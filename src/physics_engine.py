import math

class CyclingPhysicsSimulator:
    """
    Motor de física con inercia y fatiga aeróbica basada en kilojulios (KJ) consumidos.
    """
    def __init__(self, segments: list, config: dict):
        self.segments = segments
        self.config = config
        
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

        env = config.get('environment', {})
        self.air_density = env.get('air_density', 1.225)
        self.wind_speed = env.get('wind_speed_ms', 0.0)
        
        limits = config.get('simulation_limits', {})
        self.max_descent_speed_ms = limits.get('max_descent_speed_kmh', 75.0) / 3.6
        self.descent_braking_factor = limits.get('descent_braking_factor', 0.85)
        self.standing_threshold_ms = limits.get('standing_speed_threshold_kmh', 15.0) / 3.6
        
        strategy = config.get('power_strategy', {})
        self.climb_gradient_threshold = strategy.get('climb_gradient_threshold', 4.0)
        self.climb_power_multiplier = strategy.get('climb_power_multiplier', 1.15)
        self.descent_gradient_threshold = strategy.get('descent_gradient_threshold', -2.0)
        self.descent_power_watts = strategy.get('descent_power_watts', 20.0)
        self.false_flat_power_factor = strategy.get('false_flat_power_factor', 0.4)
        
        inertia = config.get('inertia', {})
        self.inertia_prev_weight = inertia.get('previous_speed_weight', 0.6)
        self.inertia_curr_weight = inertia.get('current_speed_weight', 0.4)
        self.power_prev_weight = inertia.get('previous_power_weight', 0.7)
        self.power_curr_weight = inertia.get('current_power_weight', 0.3)

        self.g = 9.81

    def _determine_segment_power(self, gradient_percent: float, eff_ftp: float, eff_base_power: float) -> float:
        if gradient_percent > self.climb_gradient_threshold:
            return min(eff_ftp * 1.25, eff_base_power * self.climb_power_multiplier)
        elif gradient_percent < self.descent_gradient_threshold:
            return self.descent_power_watts
        elif gradient_percent < 0.0:
            return eff_base_power * self.false_flat_power_factor
        else:
            return eff_base_power

    def _solve_speed_for_segment(self, distance_m: float, elevation_change_m: float, power_watts: float, previous_v: float) -> float:
        if distance_m <= 0:
            return previous_v

        dist_3d = math.sqrt(distance_m**2 + elevation_change_m**2)
        if dist_3d == 0:
            return previous_v
        
        sin_theta = elevation_change_m / dist_3d
        p_wheel = power_watts * (1.0 - self.drivetrain_loss)

        v = max(1.0, previous_v)
        
        for _ in range(12):
            v_rel = v + self.wind_speed
            v_rel_squared = v_rel * abs(v_rel)

            is_climbing = elevation_change_m > 0
            is_slow = v < self.standing_threshold_ms
            cda = self.cda_standing if (is_climbing and is_slow) else self.cda_seated

            p_aero = 0.5 * self.air_density * cda * v_rel_squared * v
            p_grav = self.total_mass * self.g * sin_theta * v
            p_roll = self.cr * self.total_mass * self.g * max(0.0, math.cos(math.asin(sin_theta))) * v

            p_resistances = p_aero + p_grav + p_roll
            diff = p_wheel - p_resistances

            if abs(diff) < 0.1:
                break

            v += diff / (max(200.0, 3.0 * p_aero / max(v, 0.1) + self.total_mass * self.g * abs(sin_theta) + 20.0))
            if v < 0.1:
                v = 0.1

        if elevation_change_m < 0:
            v = v * self.descent_braking_factor
            if v > self.max_descent_speed_ms:
                v = self.max_descent_speed_ms

        smoothed_v = (self.inertia_prev_weight * previous_v) + (self.inertia_curr_weight * v)
        return smoothed_v

    def run_simulation(self) -> dict:
        total_time_seconds = 0.0
        detailed_segments = []
        
        self.w_prime_current = self.w_prime_max
        current_v = 6.0
        previous_power = self.base_target_power
        total_energy_kj = 0.0

        for i, seg in enumerate(self.segments):
            dist = seg['distance_m']
            elev_change = seg['elevation_change_m']
            gradient = seg['gradient_percent']

            # Cálculo de fatiga basado en KJ consumidos (Suelo de rendimiento en 75%)
            fatigue_factor = max(0.75, 1.0 - (total_energy_kj / 1000.0) * self.fatigue_rate_per_1000kj)
            
            current_effective_ftp = self.ftp * fatigue_factor
            current_effective_base_power = self.base_target_power * fatigue_factor

            raw_segment_power = self._determine_segment_power(gradient, current_effective_ftp, current_effective_base_power)
            segment_power = (self.power_prev_weight * previous_power) + (self.power_curr_weight * raw_segment_power)
            previous_power = segment_power

            current_v = self._solve_speed_for_segment(dist, elev_change, segment_power, current_v)
            
            time_s = dist / current_v if current_v > 0 else 0.0
            total_time_seconds += time_s

            segment_kj = (segment_power * time_s) / 1000.0
            total_energy_kj += segment_kj

            power_diff = segment_power - current_effective_ftp
            if power_diff > 0:
                energy_spent = power_diff * time_s
                self.w_prime_current = max(0.0, self.w_prime_current - energy_spent)
            else:
                recovery_rate = abs(power_diff) * 0.1
                self.w_prime_current = min(self.w_prime_max, self.w_prime_current + (recovery_rate * time_s))

            v_kmh = current_v * 3.6

            detailed_segments.append({
                'segment_index': i,
                'distance_m': dist,
                'elevation_change_m': elev_change,
                'gradient_percent': gradient,
                'speed_kmh': v_kmh,
                'power_watts': segment_power,
                'time_seconds': time_s,
                'w_prime_joules': self.w_prime_current,
                'w_prime_percent': (self.w_prime_current / self.w_prime_max) * 100.0,
                'energy_kj_accumulated': total_energy_kj,       # <-- Añadido
                'effective_ftp_watts': current_effective_ftp    # <-- Añadido
            })

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
            'segments_simulation': detailed_segments
        }