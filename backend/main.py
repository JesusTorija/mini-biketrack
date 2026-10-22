from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
import tempfile
import os
import json
import pandas as pd

from fit_parser import FITRouteAnalyzer
from gpx_parser import GPXRouteAnalyzer
from physics_engine import CyclingPhysicsSimulator
from schemas import SimulationConfig

app = FastAPI(
    title="Hors Catégorie - Cycling Physics Engine API",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Definir la ruta absoluta de la carpeta frontend
base_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(base_dir, "..", "frontend")
static_files_dir = os.path.join(frontend_dir, "static")  # <- Apuntamos a frontend/static
index_path = os.path.join(frontend_dir, "index.html")

# Montar los archivos estáticos correctamente
if os.path.exists(static_files_dir):
    app.mount("/static", StaticFiles(directory=static_files_dir), name="static")

@app.get("/health")
def health_check():
    return {"status": "ok", "engine": "Hors Catégorie Physics Core v2.0"}

@app.get("/api/config")
async def get_configuration():
    """
    Lee y devuelve la configuración desde el config.json ubicado en la raíz del proyecto (C:\bbs\config.json).
    """
    # Subimos un nivel desde backend/ a la raíz del proyecto
    root_dir = os.path.join(base_dir, "..")
    config_path = os.path.join(root_dir, "config.json")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Error al leer config.json: {str(e)}"})
            
    return SimulationConfig().dict()

@app.post("/api/v1/simulate")
async def simulate_route(
    file: UploadFile = File(...),
    config_json: str = Form(...)
):
    filename = file.filename
    ext = filename.split('.')[-1].lower() if '.' in filename else ""

    if ext not in ["gpx", "fit"]:
        raise HTTPException(status_code=400, detail="Formato no soportado. Solo se admiten archivos .fit o .gpx")

    try:
        config_dict = json.loads(config_json)
        sim_config = SimulationConfig(**config_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error validando la configuración: {str(e)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if ext == "fit":
            analyzer = FITRouteAnalyzer(tmp_path, smooth_distance_m=sim_config.smooth_radius_1)
        else:
            analyzer = GPXRouteAnalyzer(tmp_path, smooth_distance_m=sim_config.smooth_radius_1)

        summary = analyzer.get_summary()
        segments = analyzer.get_segments()

        config_data = sim_config.model_dump()
        ftp = config_data['cyclist']['ftp_watts']
        
        if not config_data['cyclist'].get('target_power_watts'):
            if_factor = config_data['cyclist']['intensity_factor']
            config_data['cyclist']['target_power_watts'] = ftp * if_factor

        simulator = CyclingPhysicsSimulator(segments, config_data)
        simulation_result = simulator.run_simulation()

        # Enriquecer los segmentos con tiempo acumulado/formateado y calcular NP / TSS simulados
        df_sim = pd.DataFrame(simulation_result['segments_simulation'])
        if not df_sim.empty:
            df_sim['time_accumulated_sec'] = df_sim['time_seconds'].cumsum()
            
            def sec_to_str(sec_val):
                h = int(sec_val // 3600)
                m = int((sec_val % 3600) // 60)
                s = int(sec_val % 60)
                return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

            df_sim['time_formatted'] = df_sim['time_accumulated_sec'].apply(sec_to_str)
            
            total_seconds = simulation_result['total_time_seconds']
            avg_power = df_sim['power_watts'].mean() if 'power_watts' in df_sim else 0.0
            
            if len(df_sim) > 0 and total_seconds > 0:
                window_np = max(1, len(df_sim) // 30)
                rolling_power = df_sim['power_watts'].rolling(window=window_np, min_periods=1).mean()
                np_watts = float((rolling_power ** 4).mean() ** 0.25)
            else:
                np_watts = avg_power

            if ftp > 0 and total_seconds > 0:
                if_science = np_watts / ftp
                tss_science = (total_seconds * np_watts * if_science) / (ftp * 3600.0) * 100.0
            else:
                tss_science = 0.0

            simulation_result['normalized_power_watts'] = round(np_watts, 1)
            simulation_result['tss'] = round(tss_science, 1)
            simulation_result['segments_simulation'] = df_sim.to_dict(orient="records")

        telemetry_data = []
        real_metrics = None

        if hasattr(analyzer, 'telemetry_records') and analyzer.telemetry_records:
            df_tel = pd.DataFrame(analyzer.telemetry_records)
            
            if not df_tel.empty:
                dists = [0.0]
                for i in range(1, len(df_tel)):
                    lat1, lon1 = df_tel.loc[i-1, 'latitude'], df_tel.loc[i-1, 'longitude']
                    lat2, lon2 = df_tel.loc[i, 'latitude'], df_tel.loc[i, 'longitude']
                    dists.append(dists[-1] + analyzer._haversine_distance(lat1, lon1, lat2, lon2) / 1000.0)
                df_tel['distance_accumulated_km'] = dists

                if 'time' in df_tel.columns:
                    df_tel['time'] = df_tel['time'].astype(str)

                real_avg_speed = float(df_tel['real_speed_kmh'].mean()) if 'real_speed_kmh' in df_tel else 0.0
                real_avg_power = float(df_tel['real_power_watts'].mean()) if 'real_power_watts' in df_tel else 0.0
                
                real_total_kj = 0.0
                total_seconds_real = 0.0
                real_formatted_time = "--:--:--"
                tss_real = 0.0

                if 'real_power_watts' in df_tel and 'time' in df_tel:
                    try:
                        times = pd.to_datetime(df_tel['time'])
                        time_diffs = times.diff().dt.total_seconds().fillna(1.0)
                        time_diffs = time_diffs.apply(lambda x: x if 0 < x < 10 else 1.0)
                        real_total_kj = float((df_tel['real_power_watts'] * time_diffs).sum() / 1000.0)
                        
                        t_start = times.iloc[0]
                        t_end = times.iloc[-1]
                        total_seconds_real = (t_end - t_start).total_seconds()
                        if total_seconds_real > 0:
                            h = int(total_seconds_real // 3600)
                            m = int((total_seconds_real % 3600) // 60)
                            s = int(total_seconds_real % 60)
                            real_formatted_time = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
                        
                        rolling_np_real = df_tel['real_power_watts'].rolling(window=30, min_periods=1).mean()
                        np_real = float((rolling_np_real ** 4).mean() ** 0.25)
                        if ftp > 0 and total_seconds_real > 0:
                            if_real = np_real / ftp
                            tss_real = (total_seconds_real * np_real * if_real) / (ftp * 3600.0) * 100.0
                    except Exception:
                        real_total_kj = float(df_tel['real_power_watts'].sum() / 1000.0)

                real_metrics = {
                    "average_speed_kmh": round(real_avg_speed, 2),
                    "average_power_watts": round(real_avg_power, 1),
                    "total_energy_kj": round(real_total_kj, 1),
                    "formatted_time": real_formatted_time,
                    "tss": round(tss_real, 1)
                }

                telemetry_data = df_tel.to_dict(orient="records")

        response_content = {
            "success": True,
            "filename": filename,
            "summary": summary,
            "simulation": simulation_result,
            "real_telemetry_metrics": real_metrics,
            "points": analyzer.points,
            "telemetry_records": telemetry_data
        }

        return JSONResponse(content=jsonable_encoder(response_content))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante el procesamiento: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """
    Sirve la interfaz principal en HTML usando rutas absolutas.
    """
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content=f"<h1>Error: No se encontró el archivo en {index_path}</h1>", status_code=404)