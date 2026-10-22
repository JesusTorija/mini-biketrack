import streamlit as st
import tempfile
import os
import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from gpx_parser import GPXRouteAnalyzer
from fit_parser import FITRouteAnalyzer
from physics_engine import CyclingPhysicsSimulator

# --- CARGAR CONFIGURACIÓN DESDE JSON ---
config_path = "config.json"
if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            default_config = json.load(f)
    except Exception:
        default_config = {}
else:
    default_config = {}

APP_TITLE = default_config.get("app_name", "Mini BikeTrack App")

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=None,
    layout="wide"
)

# --- GESTIÓN DE COOKIES Y CONSENTIMIENTO RGPD (SESSION STATE) ---
if "cookies_accepted" not in st.session_state:
    st.session_state["cookies_accepted"] = False

if not st.session_state["cookies_accepted"]:
    st.warning("Aviso de Privacidad y Cookies: Este sitio web utiliza cookies técnicas y de análisis para mejorar la experiencia de usuario y mostrar publicidad personalizada. Al continuar navegando, aceptas nuestra política de uso de cookies.")
    col_c1, col_c2, _ = st.columns([1, 1, 4])
    if col_c1.button("Aceptar todas"):
        st.session_state["cookies_accepted"] = True
        st.rerun()
    if col_c2.button("Configurar / Rechazar"):
        st.info("Puedes cerrar la aplicación si no estás de acuerdo con el uso de cookies básicas.")

c_def = default_config.get("cyclist", {})
e_def = default_config.get("environment", {})
l_def = default_config.get("simulation_limits", {})
p_def = default_config.get("power_strategy", {})
i_def = default_config.get("inertia", {})

st.title(f"{APP_TITLE} - Simulador de Ruta")
st.markdown("Sube tu archivo de ruta (**GPX** o **FIT**), ajusta tus parámetros en la barra lateral y haz clic en **Simular Ruta**. Si el archivo es un FIT, podrás comparar la simulación directamente con tus datos reales.")

# --- SUBIR ARCHIVO GPX / FIT ---
uploaded_file = st.file_uploader("Sube tu archivo de ruta (.gpx o .fit)", type=["gpx", "fit"])

# --- BARRA LATERAL: FORMULARIO DE CONFIGURACIÓN ---
with st.sidebar.form("simulation_form"):
    st.header("Parámetros de Simulación")
    
    st.subheader("1. Ciclista y Fisiología")
    weight_kg = st.slider("Peso del ciclista (kg)", 30.0, 150.0, float(c_def.get("weight_kg", 70.0)), 0.5)
    bike_weight_kg = st.slider("Peso de la bicicleta (kg)", 3.0, 25.0, float(c_def.get("bike_weight_kg", 8.0)), 0.5)
    ftp_watts = st.slider("FTP (vatios)", 50, 600, int(c_def.get("ftp_watts", 250)), 5)
    intensity_factor = st.slider("Factor de Intensidad (IF)", 0.4, 1.5, float(c_def.get("intensity_factor", 0.88)), 0.01)
    w_prime_kj = st.slider("Capacidad W' (kJ)", 5.0, 40.0, float(c_def.get("w_prime_kj", 20.0)), 1.0)
    fatigue_per_1000kj = st.slider("Pérdida de rendimiento por 1.000 KJ (%)", 0.0, 20.0, float(c_def.get("fatigue_rate_per_1000kj", 1.5)), 0.1)

    st.subheader("2. Aerodinámica y Resistencia")
    cda_seated = st.slider("CdA Sentado", 0.10, 0.70, float(c_def.get("cda_seated", 0.25)), 0.01)
    cda_standing = st.slider("CdA De pie", 0.20, 0.80, float(c_def.get("cda_standing", 0.40)), 0.01)
    rolling_resistance = st.slider("Coef. Rodadura (Cr)", 0.0010, 0.0150, float(c_def.get("rolling_resistance_cr", 0.004)), 0.0005, format="%.4f")

    st.subheader("3. Estrategia de Potencia por Pendiente")
    climb_thresh = st.slider("Pendiente mín. para apretar subiendo (%)", 0.5, 15.0, float(p_def.get("climb_gradient_threshold", 4.0)), 0.5)
    descent_thresh = st.slider("Pendiente mín. para soltar bajando (%)", -15.0, 0.0, float(p_def.get("descent_gradient_threshold", -2.0)), 0.5)
    descent_watts = st.slider("Vatios en bajada pronunciada (W)", 0.0, 200.0, float(p_def.get("descent_power_watts", 20.0)), 5.0)

    st.subheader("4. Límites, Inercia y Suavizado")
    max_descent_speed = st.slider("Velocidad máx. descenso (km/h)", 30.0, 130.0, float(l_def.get("max_descent_speed_kmh", 75.0)), 5.0)
    descent_braking = st.slider("Factor frenado en curvas rápidas", 0.90, 1.00, float(l_def.get("descent_braking_factor", 0.95)), 0.01)
    standing_threshold = st.slider("Umbral de pie en subida (km/h)", 3.0, 40.0, float(l_def.get("standing_speed_threshold_kmh", 15.0)), 1.0)
    wind_speed = st.slider("Viento (m/s) [+ contra, - favor]", -20.0, 20.0, float(e_def.get("wind_speed_ms", 0.0)), 0.5)
    
    smooth_radius_1 = st.slider("Radio suavizado principal (Pasada 1 - m)", 0.0, 2000.0, 500.0, 10.0)
    smooth_radius_2 = st.slider("Radio suavizado refino (Pasada 2 - m)", 0.0, 1000.0, 250.0, 10.0)

    smoothing_option = st.selectbox(
        "Método de suavizado de altitud",
        options=["standard", "sql_double_ma"],
        format_func=lambda x: "Estándar (Sin suavizado extra)" if x == "standard" else "Doble Media Móvil (Estilo SQL ajustable)",
        index=1
    )

    submitted = st.form_submit_button("Simular Ruta")

# --- LÓGICA DE EJECUCIÓN Y VISUALIZACIÓN ---
if uploaded_file is not None:
    file_extension = uploaded_file.name.split('.')[-1].lower()

    if submitted or "last_simulation" not in st.session_state:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        try:
            if file_extension == "fit":
                analyzer = FITRouteAnalyzer(tmp_path, smooth_distance_m=smooth_radius_1)
            else:
                analyzer = GPXRouteAnalyzer(tmp_path, smooth_distance_m=smooth_radius_1)

            summary = analyzer.get_summary()
            segments = analyzer.get_segments()

            target_power = int(ftp_watts * intensity_factor)
            
            config = {
                "cyclist": {
                    "weight_kg": weight_kg,
                    "bike_weight_kg": bike_weight_kg,
                    "ftp_watts": ftp_watts,
                    "target_power_watts": target_power,
                    "intensity_factor": intensity_factor,
                    "cda_seated": cda_seated,
                    "cda_standing": cda_standing,
                    "rolling_resistance_cr": rolling_resistance,
                    "drivetrain_loss_percent": 2.5,
                    "w_prime_kj": w_prime_kj,
                    "fatigue_rate_per_1000kj": fatigue_per_1000kj
                },
                "smoothing_method": smoothing_option,
                "smooth_radius_1": smooth_radius_1,
                "smooth_radius_2": smooth_radius_2,
                "environment": {
                    "air_density": 1.225,
                    "wind_speed_ms": wind_speed
                },
                "simulation_limits": {
                    "max_descent_speed_kmh": max_descent_speed,
                    "descent_braking_factor": descent_braking,
                    "standing_speed_threshold_kmh": standing_threshold
                },
                "power_strategy": {
                    "climb_gradient_threshold": climb_thresh,
                    "climb_power_multiplier": 1.15,
                    "descent_gradient_threshold": descent_thresh,
                    "descent_power_watts": descent_watts,
                    "false_flat_power_factor": 0.4
                },
                "inertia": {
                    "previous_speed_weight": i_def.get("previous_speed_weight", 0.75),
                    "current_speed_weight": i_def.get("current_speed_weight", 0.25),
                    "previous_power_weight": i_def.get("previous_power_weight", 0.8),
                    "current_power_weight": i_def.get("current_power_weight", 0.2)
                }
            }

            simulator = CyclingPhysicsSimulator(segments, config)
            result = simulator.run_simulation()

            telemetry_df = None
            if hasattr(analyzer, 'telemetry_records') and analyzer.telemetry_records:
                telemetry_df = pd.DataFrame(analyzer.telemetry_records)
                if len(telemetry_df) > 1:
                    dists = [0.0]
                    for i in range(1, len(telemetry_df)):
                        lat1, lon1 = telemetry_df.loc[i-1, 'latitude'], telemetry_df.loc[i-1, 'longitude']
                        lat2, lon2 = telemetry_df.loc[i, 'latitude'], telemetry_df.loc[i, 'longitude']
                        dists.append(dists[-1] + analyzer._haversine_distance(lat1, lon1, lat2, lon2) / 1000.0)
                    telemetry_df['distance_accumulated_km'] = dists

            st.session_state["last_simulation"] = {
                "summary": summary,
                "segments": segments,
                "result": result,
                "target_power": target_power,
                "points": analyzer.points,
                "telemetry_df": telemetry_df
            }
            st.session_state["selected_km"] = 0.0

        except Exception as e:
            st.error(f"Ocurrió un error procesando el archivo: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    if "last_simulation" in st.session_state:
        sim_data_store = st.session_state["last_simulation"]
        summary = sim_data_store["summary"]
        segments = sim_data_store["segments"]
        result = sim_data_store["result"]
        target_power = sim_data_store["target_power"]
        points = sim_data_store["points"]
        telemetry_df = sim_data_store.get("telemetry_df", None)

        st.sidebar.info(f"Potencia base objetivo: {target_power} W")

        st.divider()
        st.subheader("Resultados y Métricas de la Simulación")
        
        sim_data = result['segments_simulation']
        df_sim = pd.DataFrame(sim_data)

        df_sim['distance_accumulated_km'] = df_sim['distance_m'].cumsum() / 1000.0
        df_sim['time_accumulated_sec'] = df_sim['time_seconds'].cumsum()
        
        def sec_to_str(sec_val):
            h = int(sec_val // 3600)
            m = int((sec_val % 3600) // 60)
            s = int(sec_val % 60)
            return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

        df_sim['time_formatted'] = df_sim['time_accumulated_sec'].apply(sec_to_str)

        avg_power = df_sim['power_watts'].mean()
        total_kj = df_sim['energy_kj_accumulated'].iloc[-1] if 'energy_kj_accumulated' in df_sim else 0.0

        total_seconds = result['total_time_seconds']
        if len(df_sim) > 0 and total_seconds > 0:
            window_np = max(1, len(df_sim) // 30)
            rolling_power = df_sim['power_watts'].rolling(window=window_np, min_periods=1).mean()
            np_watts = (rolling_power ** 4).mean() ** 0.25
        else:
            np_watts = avg_power

        if ftp_watts > 0 and total_seconds > 0:
            intensity_factor_science = np_watts / ftp_watts
            tss_science = (total_seconds * np_watts * intensity_factor_science) / (ftp_watts * 3600.0) * 100.0
        else:
            intensity_factor_science = 0.0
            tss_science = 0.0

        real_time_str = "N/A"
        real_avg_speed = 0.0
        real_avg_power = 0.0
        real_total_kj = 0.0

        if telemetry_df is not None and not telemetry_df.empty:
            if 'real_speed_kmh' in telemetry_df.columns:
                real_avg_speed = telemetry_df['real_speed_kmh'].mean()
            if 'real_power_watts' in telemetry_df.columns:
                real_avg_power = telemetry_df['real_power_watts'].mean()
            if 'real_power_watts' in telemetry_df.columns and 'time' in telemetry_df.columns:
                real_total_kj = (telemetry_df['real_power_watts'].sum() * 1.0) / 1000.0
            if 'time' in telemetry_df.columns and telemetry_df['time'].iloc[0] is not None and telemetry_df['time'].iloc[-1] is not None:
                try:
                    t_start = pd.to_datetime(telemetry_df['time'].iloc[0])
                    t_end = pd.to_datetime(telemetry_df['time'].iloc[-1])
                    diff_sec = (t_end - t_start).total_seconds()
                    if diff_sec > 0:
                        real_time_str = sec_to_str(diff_sec)
                except Exception:
                    pass

        st.divider()
        st.subheader("Resultados y Métricas de la Simulación vs. Realidad")

        if telemetry_df is not None and not telemetry_df.empty:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Tiempo Total", result['formatted_time'], delta=f"Real: {real_time_str}", delta_color="off")
            col2.metric("Distancia", f"{summary['total_distance_km']:.2f} km")
            col3.metric("Velocidad Media", f"{result['average_speed_kmh']:.2f} km/h", delta=f"Real: {real_avg_speed:.1f} km/h", delta_color="off")
            col4.metric("Desnivel", f"{summary['elevation_gain_m']:.1f} m")

            col5, col6, col7, col8 = st.columns(4)
            col5.metric("Potencia Media", f"{avg_power:.0f} W", delta=f"Real: {real_avg_power:.0f} W", delta_color="off")
            col6.metric("Potencia Normalizada (NP)", f"{np_watts:.0f} W")
            col7.metric("Energía Total", f"{total_kj:.0f} kJ", delta=f"Real: {real_total_kj:.0f} kJ", delta_color="off")
            col8.metric("Carga (TSS)", f"{tss_science:.0f}")
        else:
            row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
            row1_col1.metric("Tiempo", result['formatted_time'])
            row1_col2.metric("Distancia", f"{summary['total_distance_km']:.2f} km")
            row1_col3.metric("Vel. Media", f"{result['average_speed_kmh']:.2f} km/h")
            row1_col4.metric("Desnivel", f"{summary['elevation_gain_m']:.1f} m")

            row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)
            row2_col1.metric("Potencia Media", f"{avg_power:.0f} W")
            row2_col2.metric("Potencia Normalizada (NP)", f"{np_watts:.0f} W")
            row2_col3.metric("Energía Total", f"{total_kj:.0f} kJ")
            row2_col4.metric("Carga (TSS)", f"{tss_science:.0f}")

        max_dist_km = float(summary['total_distance_km'])
        
        if "selected_km" not in st.session_state or st.session_state["selected_km"] is None:
            st.session_state["selected_km"] = 0.0

        selected_km = st.slider(
            "Selector de Kilómetro (Sincronizador maestro)", 
            0.0, max_dist_km, 
            float(min(st.session_state["selected_km"], max_dist_km)), 
            0.1
        )
        st.session_state["selected_km"] = selected_km

        idx_closest = (df_sim['distance_accumulated_km'] - selected_km).abs().idxmin()
        row_sel = df_sim.loc[idx_closest]

        elevations = [seg['elevation_start'] for seg in segments] + [segments[-1]['elevation_end']]
        distances_alt = [0] + list(df_sim['distance_accumulated_km'])
        current_elevation = np.interp(selected_km, distances_alt, elevations)

        st.markdown(f"""
        **Detalle en el KM {selected_km:.2f}**: 
        &nbsp;&nbsp;|&nbsp;&nbsp; Altitud: **{current_elevation:.1f} m**
        &nbsp;&nbsp;|&nbsp;&nbsp; Tiempo: **{row_sel['time_formatted']}** 
        &nbsp;&nbsp;|&nbsp;&nbsp; Potencia: **{row_sel['power_watts']:.1f} W** 
        &nbsp;&nbsp;|&nbsp;&nbsp; Velocidad: **{row_sel['speed_kmh']:.1f} km/h** 
        &nbsp;&nbsp;|&nbsp;&nbsp; Energía: **{row_sel['energy_kj_accumulated']:.1f} kJ** 
        &nbsp;&nbsp;|&nbsp;&nbsp; W': **{row_sel['w_prime_percent']:.1f}%**
        &nbsp;&nbsp;|&nbsp;&nbsp; Pendiente: **{row_sel['gradient_percent']:.1f}%**
        &nbsp;&nbsp;|&nbsp;&nbsp; FTP Efectivo: **{row_sel['effective_ftp_watts']:.1f} W**
        """)

        d_cum = 0.0
        best_idx = 0
        min_diff = float('inf')
        for idx, p in enumerate(points):
            if idx > 0:
                import math
                lat1, lon1 = points[idx-1]['latitude'], points[idx-1]['longitude']
                lat2, lon2 = p['latitude'], p['longitude']
                dist_seg = math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2) * 111000
                d_cum += dist_seg / 1000.0
            
            diff = abs(d_cum - selected_km)
            if diff < min_diff:
                min_diff = diff
                best_idx = idx
        
        sel_lat = points[best_idx]['latitude']
        sel_lon = points[best_idx]['longitude']

        top_col1, top_col2 = st.columns(2)

        with top_col1:
            st.subheader("Trazado Geométrico")
            lats = [p['latitude'] for p in points]
            lons = [p['longitude'] for p in points]

            fig_map = go.Figure()
            fig_map.add_trace(go.Scatter(
                x=lons, y=lats,
                mode='lines',
                line=dict(width=3, color='orange'),
                name="Ruta",
                hoverinfo='skip'
            ))
            fig_map.add_trace(go.Scatter(
                x=[sel_lon], y=[sel_lat],
                mode='markers',
                marker=dict(size=14, color='cyan', symbol='circle', line=dict(width=2, color='white')),
                name="Posición",
                hovertemplate=f"<b>KM:</b> {selected_km:.2f}<br>Lat: {sel_lat:.4f}<br>Lon: {sel_lon:.4f}<extra></extra>"
            ))
            fig_map.update_layout(
                xaxis_title="Longitud",
                yaxis_title="Latitud",
                yaxis=dict(scaleanchor="x", scaleratio=1),
                margin=dict(l=10, r=10, t=20, b=10),
                height=340,
                hovermode="closest",
                showlegend=False
            )
            st.plotly_chart(fig_map, width='stretch', key="map_chart")

        with top_col2:
            st.subheader("Perfil de Elevación")
            
            df_plot_ele = df_sim.copy()
            detected_climbs = result.get('detected_climbs', [])
            step_sample_ele = max(1, len(df_plot_ele) // 150)
            df_plot_click_ele = df_plot_ele.iloc[::step_sample_ele].copy()
            
            elevations_sampled = [np.interp(d, distances_alt, elevations) for d in df_plot_click_ele['distance_accumulated_km']]

            fig_elev = go.Figure()
            
            fig_elev.add_trace(
                go.Scatter(
                    x=distances_alt, y=elevations,
                    fill='tozeroy', fillcolor='rgba(46, 134, 193, 0.15)',
                    line=dict(color='rgb(31, 119, 180)', width=2),
                    name="Llano / Descenso", hoverinfo='skip'
                )
            )

            p_count = 1
            r_count = 1

            for climb in detected_climbs:
                is_puerto = climb['type'] == "Puerto"
                
                if is_puerto:
                    label_id = f"P{p_count}"
                    color = "rgb(211, 47, 47)"
                    p_count += 1
                else:
                    label_id = f"R{r_count}"
                    color = "rgb(251, 192, 45)"
                    r_count += 1

                sub_df = df_plot_ele[
                    (df_plot_ele['distance_accumulated_km'] >= climb['start_dist_km']) & 
                    (df_plot_ele['distance_accumulated_km'] <= climb['end_dist_km'])
                ]
                
                if not sub_df.empty:
                    sub_distances = list(sub_df['distance_accumulated_km'])
                    sub_elevs = [np.interp(d, distances_alt, elevations) for d in sub_distances]
                    
                    legend_name = f"[{label_id}] {climb['type']} ({climb['average_slope_percent']:.1f}%)"

                    fig_elev.add_trace(
                        go.Scatter(
                            x=sub_distances, y=sub_elevs,
                            mode='lines',
                            line=dict(color=color, width=4.5),
                            name=legend_name,
                            hovertemplate=(
                                f"<b>[{label_id}] {climb['type']}</b><br>"
                                f"Tramo: {climb['start_dist_km']:.2f} km - {climb['end_dist_km']:.2f} km<br>"
                                f"Pendiente media: {climb['average_slope_percent']:.1f}%<br>"
                                f"Desnivel: {climb['elevation_gain_m']:.1f} m<extra></extra>"
                            )
                        )
                    )

                    max_idx = np.argmax(sub_elevs)
                    fig_elev.add_annotation(
                        x=sub_distances[max_idx],
                        y=sub_elevs[max_idx],
                        text=f"<b>{label_id}</b>",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=1,
                        arrowcolor=color,
                        ax=0,
                        ay=-25,
                        font=dict(size=10, color="white"),
                        bgcolor=color,
                        borderpad=2
                    )

            fig_elev.add_trace(
                go.Scatter(
                    x=df_plot_click_ele['distance_accumulated_km'], 
                    y=elevations_sampled,
                    mode='markers', marker=dict(size=8, color='rgba(0,0,0,0)'),
                    showlegend=False,
                    hovertemplate=(
                        "<b>Distancia:</b> %{x:.2f} km<br>"
                        "<b>Altitud:</b> %{customdata[0]:.1f} m<br>"
                        "<b>Pendiente:</b> %{customdata[1]:.1f}%<extra></extra>"
                    ),
                    customdata=list(zip(elevations_sampled, df_plot_click_ele['gradient_percent']))
                )
            )
            fig_elev.add_vline(x=selected_km, line_width=2.5, line_dash="dash", line_color="#00FFFF")

            fig_elev.update_layout(
                xaxis_title="Distancia Acumulada (km)",
                yaxis_title="Altitud (m)",
                margin=dict(l=10, r=10, t=30, b=30),
                height=380,
                hovermode="x unified",
                clickmode="event+select",
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.28,
                    xanchor="center",
                    x=0.5
                )
            )
            event_elev = st.plotly_chart(fig_elev, width='stretch', on_select="rerun", key="chart_elev")

        st.divider()
        st.subheader("Panorámica de Rendimiento y Comparativa Real")

        df_plot = df_sim.copy()
        if len(df_plot) > 300:
            window_size = max(5, len(df_plot) // 100)
            df_plot['power_watts'] = df_plot['power_watts'].rolling(window=window_size, min_periods=1).mean()
            df_plot['speed_kmh'] = df_plot['speed_kmh'].rolling(window=window_size, min_periods=1).mean()
            df_plot['w_prime_percent'] = df_plot['w_prime_percent'].rolling(window=window_size, min_periods=1).mean()
            df_plot['effective_ftp_watts'] = df_plot['effective_ftp_watts'].rolling(window=window_size, min_periods=1).mean()
            df_plot['energy_kj_accumulated'] = df_plot['energy_kj_accumulated'].rolling(window=window_size, min_periods=1).mean()

        if telemetry_df is not None and not telemetry_df.empty:
            if len(telemetry_df) > 300:
                telemetry_window = max(5, len(telemetry_df) // 100)
                if 'real_power_watts' in telemetry_df.columns:
                    telemetry_df['real_power_watts'] = telemetry_df['real_power_watts'].rolling(window=telemetry_window, min_periods=1).mean()
                if 'real_speed_kmh' in telemetry_df.columns:
                    telemetry_df['real_speed_kmh'] = telemetry_df['real_speed_kmh'].rolling(window=telemetry_window, min_periods=1).mean()

        step_sample = max(1, len(df_plot) // 150)
        df_plot_click = df_plot.iloc[::step_sample].copy()

        fig_combined = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig_combined.add_trace(go.Scatter(x=df_plot['distance_accumulated_km'], y=df_plot['power_watts'], name="Potencia Simulada (W)", line=dict(color='orange', width=2), hoverinfo='skip'), secondary_y=False)
        fig_combined.add_trace(go.Scatter(x=df_plot['distance_accumulated_km'], y=df_plot['speed_kmh'], name="Velocidad Simulada (km/h)", line=dict(color='deepskyblue', width=2), hoverinfo='skip'), secondary_y=True)
        
        if telemetry_df is not None and not telemetry_df.empty:
            if 'real_power_watts' in telemetry_df.columns:
                fig_combined.add_trace(go.Scatter(x=telemetry_df['distance_accumulated_km'], y=telemetry_df['real_power_watts'], name="Potencia Real (Suavizada)", line=dict(color='darkorange', width=1.8, dash='dot'), hoverinfo='skip'), secondary_y=False)
            if 'real_speed_kmh' in telemetry_df.columns:
                fig_combined.add_trace(go.Scatter(x=telemetry_df['distance_accumulated_km'], y=telemetry_df['real_speed_kmh'], name="Velocidad Real (Suavizada)", line=dict(color='blue', width=1.8, dash='dot'), hoverinfo='skip'), secondary_y=True)

        fig_combined.add_trace(
            go.Scatter(
                x=df_plot_click['distance_accumulated_km'], y=df_plot_click['power_watts'],
                mode='markers', marker=dict(size=8, color='rgba(0,0,0,0)'),
                name="Puntos clic", showlegend=False,
                hovertemplate=(
                    "Distancia: %{x:.2f} km<br>"
                    "Potencia Sim.: %{y:.1f} W<br>"
                    "Velocidad Sim.: %{customdata[0]:.1f} km/h<br>"
                    "Tiempo: %{customdata[1]}<extra></extra>"
                ),
                customdata=list(zip(df_plot_click['speed_kmh'], df_plot_click['time_formatted']))
            ),
            secondary_y=False
        )
        fig_combined.add_vline(x=selected_km, line_width=2.5, line_dash="dash", line_color="#00FFFF")

        fig_combined.update_layout(
            title="Dinámica de Ruta: Potencia y Velocidad (Simulación vs Realidad Suavizada)",
            hovermode="x unified",
            xaxis_title="Distancia Acumulada (km)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=40, b=20),
            clickmode="event+select",
            height=320
        )
        fig_combined.update_yaxes(title_text="<b>Potencia (W)</b>", secondary_y=False)
        fig_combined.update_yaxes(title_text="<b>Velocidad (km/h)</b>", secondary_y=True)
        
        event_combined = st.plotly_chart(fig_combined, width='stretch', on_select="rerun", key="chart_combined")

        fig_fatigue = make_subplots(specs=[[{"secondary_y": True}]])
        fig_fatigue.add_trace(go.Scatter(x=df_plot['distance_accumulated_km'], y=df_plot['effective_ftp_watts'], name="FTP Efectivo (W)", line=dict(color='purple', width=2), hoverinfo='skip'), secondary_y=False)
        fig_fatigue.add_trace(go.Scatter(x=df_plot['distance_accumulated_km'], y=df_plot['energy_kj_accumulated'], name="Energía / Trabajo (kJ)", line=dict(color='gold', width=2, dash='dot'), hoverinfo='skip'), secondary_y=True)
        
        fig_fatigue.add_trace(
            go.Scatter(
                x=df_plot_click['distance_accumulated_km'], y=df_plot_click['effective_ftp_watts'],
                mode='markers', marker=dict(size=8, color='rgba(0,0,0,0)'),
                showlegend=False, 
                hovertemplate=(
                    "Distancia: %{x:.2f} km<br>"
                    "FTP Efectivo: %{y:.1f} W<br>"
                    "Energía Consumida: %{customdata[0]:.1f} kJ<extra></extra>"
                ),
                customdata=df_plot_click['energy_kj_accumulated']
            ),
            secondary_y=False
        )
        fig_fatigue.add_vline(x=selected_km, line_width=2.5, line_dash="dash", line_color="#00FFFF")

        fig_fatigue.update_layout(
            title="Evolución de la Fatiga: FTP Efectivo y Energía Consumida",
            hovermode="x unified",
            xaxis_title="Distancia Acumulada (km)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=40, b=20),
            clickmode="event+select",
            height=320
        )
        fig_fatigue.update_yaxes(title_text="<b>FTP Efectivo (W)</b>", secondary_y=False)
        fig_fatigue.update_yaxes(title_text="<b>Energía (kJ)</b>", secondary_y=True)
        
        event_fatigue = st.plotly_chart(fig_fatigue, width='stretch', on_select="rerun", key="chart_fatigue")

        fig_wprime = go.Figure()
        fig_wprime.add_trace(go.Scatter(
            x=df_plot['distance_accumulated_km'], y=df_plot['w_prime_percent'],
            name="W' Disponible (%)", line=dict(color='limegreen', width=2),
            fill='tozeroy', fillcolor='rgba(50, 205, 50, 0.15)',
            hoverinfo='skip'
        ))
        
        fig_wprime.add_trace(go.Scatter(
            x=df_plot_click['distance_accumulated_km'], y=df_plot_click['w_prime_percent'],
            mode='markers', marker=dict(size=8, color='rgba(0,0,0,0)'),
            showlegend=False,
            hovertemplate=(
                "Distancia: %{x:.2f} km<br>"
                "W' Restante: %{y:.1f}%<extra></extra>"
            )
        ))
        fig_wprime.add_vline(x=selected_km, line_width=2.5, line_dash="dash", line_color="#00FFFF")

        fig_wprime.update_layout(
            title="Capacidad Anaeróbica: W' Disponible (%)",
            hovermode="x unified",
            xaxis_title="Distancia Acumulada (km)",
            yaxis_title="W' (%)",
            yaxis=dict(range=[0, 105]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=40, b=20),
            clickmode="event+select",
            height=300
        )
        
        event_wprime = st.plotly_chart(fig_wprime, width='stretch', on_select="rerun", key="chart_wprime")

        clicked_km = None
        for ev in [event_combined, event_fatigue, event_wprime, event_elev]:
            if ev and hasattr(ev, "selection") and ev.selection and "points" in ev.selection and ev.selection["points"]:
                pt = ev.selection["points"][0]
                if "x" in pt:
                    clicked_km = float(pt["x"])
                    break

        if clicked_km is not None and abs(clicked_km - selected_km) > 0.001:
            st.session_state["selected_km"] = clicked_km
            st.rerun()

else:
    st.info("Sube un archivo de ruta (GPX o FIT) y pulsa Simular Ruta en la barra lateral para empezar.")

st.markdown("---")
with st.expander(f"Política de Privacidad, Aviso Legal y Cookies - {APP_TITLE}"):
    st.markdown(f"""
    * **Uso de Datos**: {APP_TITLE} procesa los archivos localmente en la sesión de usuario para la simulación física. Ningún archivo personal o ruta es almacenado de forma permanente en servidores externos sin el consentimiento del usuario autenticado.
    * **Cookies y Publicidad**: Utilizamos cookies técnicas necesarias para el funcionamiento de la aplicación, así como cookies de terceros para la medición de tráfico y la personalización de anuncios. Puede gestionar sus preferencias desde la configuración de su navegador.
    * **Contacto**: Para cualquier duda sobre el servicio o los datos, puede contactar a través del repositorio del proyecto.
    """)