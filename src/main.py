import json
from gpx_parser import GPXRouteAnalyzer
from physics_engine import CyclingPhysicsSimulator

def main():
    # 1. Cargar la configuración
    config_path = "config/config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("Configuración cargada correctamente.")
    except FileNotFoundError:
        print(f"No se encontró el archivo '{config_path}'. Usando valores por defecto.")
        config = {
            "cyclist": {"weight_kg": 70, "bike_weight_kg": 8, "ftp_watts": 250, "target_power_watts": 200, "cda_seated": 0.25, "cda_standing": 0.40, "rolling_resistance_cr": 0.004},
            "environment": {"air_density": 1.225, "wind_speed_ms": 0},
            "simulation_limits": {"max_descent_speed_kmh": 75, "descent_braking_factor": 0.85, "standing_speed_threshold_kmh": 15}
        }

    # 2. Analizar el archivo GPX
    archivo_gpx = "tracks/VLP1.gpx"  # Reemplaza con tu archivo real
    try:
        print(f"Analizando ruta: {archivo_gpx}...")
        analyzer = GPXRouteAnalyzer(archivo_gpx)
        summary = analyzer.get_summary()
        segments = analyzer.get_segments()
        
        print(f"Distancia: {summary['total_distance_km']:.2f} km | Desnivel +: {summary['elevation_gain_m']:.1f} m")

        # 3. Ejecutar simulación de física
        print("Calculando tiempos y velocidades con el motor de física...")
        simulator = CyclingPhysicsSimulator(segments, config)
        result = simulator.run_simulation()

        # 4. Mostrar resultados finales
        print("\n=== RESULTADOS DE LA SIMULACIÓN ===")
        print(f"Tiempo estimado:    {result['formatted_time']}")
        print(f"Velocidad media:    {result['average_speed_kmh']:.2f} km/h")
        
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo GPX '{archivo_gpx}'.")
    except Exception as e:
        print(f"Ocurrió un error durante la ejecución: {e}")

if __name__ == "__main__":
    main()