import json
import os
from pydantic import BaseModel, Field
from typing import Optional

# Cargar la configuración desde config.json si existe
config_path = "config.json"
default_config = {}
if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            default_config = json.load(f)
    except Exception:
        default_config = {}

# Extraer bloques de configuración con fallbacks seguros
c_def = default_config.get("cyclist", {})
e_def = default_config.get("environment", {})
l_def = default_config.get("simulation_limits", {})
p_def = default_config.get("power_strategy", {})
i_def = default_config.get("inertia", {})

class CyclistConfig(BaseModel):
    weight_kg: float = Field(default=float(c_def.get("weight_kg", 59.0)), description="Peso del ciclista en kg")
    bike_weight_kg: float = Field(default=float(c_def.get("bike_weight_kg", 8.0)), description="Peso de la bicicleta en kg")
    ftp_watts: int = Field(default=int(c_def.get("ftp_watts", 185)), description="FTP en vatios")
    intensity_factor: float = Field(default=float(c_def.get("intensity_factor", 0.88)), description="Factor de Intensidad (IF)")
    target_power_watts: Optional[float] = None
    cda_seated: float = Field(default=float(c_def.get("cda_seated", 0.25)), description="CdA posición sentado")
    cda_standing: float = Field(default=float(c_def.get("cda_standing", c_def.get("cda_standing", 0.40))), description="CdA posición de pie")
    rolling_resistance_cr: float = Field(default=float(c_def.get("rolling_resistance_cr", 0.004)), description="Coeficiente de rodadura Cr")
    drivetrain_loss_percent: float = Field(default=float(c_def.get("drivetrain_loss_percent", 2.5)), description="Pérdida de transmisión en %")
    w_prime_kj: float = Field(default=float(c_def.get("w_prime_kj", 20.0)), description="Capacidad W' en kJ")
    fatigue_rate_per_1000kj: float = Field(default=float(c_def.get("fatigue_rate_per_1000kj", 1.5)), description="Tasa de fatiga % por cada 1.000 kJ")

class EnvironmentConfig(BaseModel):
    air_density: float = Field(default=float(e_def.get("air_density", 1.225)), description="Densidad del aire kg/m³")
    wind_speed_ms: float = Field(default=float(e_def.get("wind_speed_ms", 0.0)), description="Velocidad del viento en m/s")

class LimitsConfig(BaseModel):
    min_speed_ms: float = Field(default=float(l_def.get("min_speed_ms", 1.0)))
    max_descent_speed_kmh: float = Field(default=float(l_def.get("max_descent_speed_kmh", 75.0)))
    descent_braking_factor: float = Field(default=float(l_def.get("descent_braking_factor", 0.85)))
    braking_speed_threshold_kmh: float = Field(default=float(l_def.get("braking_speed_threshold_kmh", 45.0)))
    technical_descent_gradient: float = Field(default=float(l_def.get("technical_descent_gradient", -8.0)))
    technical_descent_damping: float = Field(default=float(l_def.get("technical_descent_damping", 0.75)))
    standing_speed_threshold_kmh: float = Field(default=float(l_def.get("standing_speed_threshold_kmh", 15.0)))
    gravity_assist_cap_kmh: float = Field(default=float(l_def.get("gravity_assist_cap_kmh", 85.0)))

class PowerStrategyConfig(BaseModel):
    climb_gradient_threshold: float = Field(default=float(p_def.get("climb_gradient_threshold", 4.0)))
    climb_power_multiplier: float = Field(default=float(p_def.get("climb_power_multiplier", 1.15)))
    climb_excess_gradient_factor: float = Field(default=float(p_def.get("climb_excess_gradient_factor", 0.03)))
    descent_gradient_threshold: float = Field(default=float(p_def.get("descent_gradient_threshold", -4.5)))
    descent_power_watts: float = Field(default=float(p_def.get("descent_power_watts", 20.0)))
    false_flat_gradient_limit: float = Field(default=float(p_def.get("false_flat_gradient_limit", 0.0)))
    false_flat_power_factor: float = Field(default=float(p_def.get("false_flat_power_factor", 0.75)))
    exhausted_power_multiplier: float = Field(default=float(p_def.get("exhausted_power_multiplier", 0.90)))
    
class InertiaConfig(BaseModel):
    previous_speed_weight: float = Field(default=float(i_def.get("previous_speed_weight", 0.75)))
    current_speed_weight: float = Field(default=float(i_def.get("current_speed_weight", 0.25)))
    previous_power_weight: float = Field(default=float(i_def.get("previous_power_weight", 0.8)))
    current_power_weight: float = Field(default=float(i_def.get("current_power_weight", 0.2)))

class SimulationConfig(BaseModel):
    cyclist: CyclistConfig = Field(default_factory=CyclistConfig)
    smoothing_method: str = Field(default="sql_double_ma")
    smooth_radius_1: float = Field(default=500.0)
    smooth_radius_2: float = Field(default=250.0)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    simulation_limits: LimitsConfig = Field(default_factory=LimitsConfig)
    power_strategy: PowerStrategyConfig = Field(default_factory=PowerStrategyConfig)
    inertia: InertiaConfig = Field(default_factory=InertiaConfig)