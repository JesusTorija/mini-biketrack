import streamlit as st
import tempfile
import os
import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from gpx_parser import GPXRouteAnalyzer
from physics_engine import CyclingPhysicsSimulator

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Mini BikeTrack App",
    page_icon="🚴‍♂️",
    layout="wide"
)

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

c_def = default_config.get("cyclist", {})
e_def = default_config.get("environment", {})
l_def = default_config.get("simulation_limits", {})
p_def = default_config.get("power_strategy", {})
i_def = default_config.get("inertia", {})

st.title("🚴‍♂️ Mini BikeTrack App - Simulador de Ruta")
st.markdown("Sube tu archivo GPX, ajusta tus parámetros en la barra lateral y haz clic en **Simular Ruta**. *Usa el selector deslizante o haz clic en las gráficas para sincronizar la posición en el mapa y perfiles.*")

# --- SUBIR ARCHIVO GPX ---
uploaded_file = st.file_uploader("Sube tu archivo de ruta (.gpx)", type=["gpx"])

# --- BARRA LATERAL: FORMULARIO DE CONFIGURACIÓN ---
with st.sidebar.form("simulation_form"):
    st.header("⚙️ Parámetros de Simulación")
    
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

    st.subheader("4. Límites, Inercia y Calidad GPS")
    max_descent_speed = st.slider("Velocidad máx. descenso (km/h)", 30.0, 130.0, float(l_def.get("max_descent_speed_kmh", 75.0)), 5.0)
    descent_braking = st.slider("Factor frenado en curvas rápidas", 0.90, 1.00, float(l_def.get("descent_braking_factor", 0.95)), 0.01)
    standing_threshold = st.slider("Umbral de pie en subida (km/h)", 3.0, 40.0, float(l_def.get("standing_speed_threshold_kmh", 15.0)), 1.0)
    wind_speed = st.slider("Viento (m/s) [+ contra, - favor]", -20.0, 20.0, float(e_def.get("wind_speed_ms", 0.0)), 0.5)
    smooth_distance = st.slider("Radio suavizado altitud (m)", 0.0, 300.0, 50.0, 10.0)

    submitted = st.form_submit_button("🚀 Simular Ruta")

# --- LÓGICA DE EJECUCIÓN Y VISUALIZACIÓN ---
if uploaded_file is not None:
    if submitted or "last_simulation" not in st.session_state:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gpx") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        try:
            analyzer = GPXRouteAnalyzer(tmp_path, smooth_distance_m=smooth_distance)
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

            st.session_state["last_simulation"] = {
                "summary": summary,
                "segments": segments,
                "result": result,
                "target_power": target_power,
                "points": analyzer.points
            }
            st.session_state["selected_km"] = 0.0

        except Exception as e:
            st.error(f"Ocurrió un error procesando el archivo GPX: {e}")
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

        st.sidebar.info(f"⚡ Potencia base objetivo: **{target_power} W**")

        st.divider()
        st.subheader("📊 Resultados y Métricas de la Simulación")
        
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

        # --- PANEL DE MÉTRICAS RESUMEN GENERAL (7 KPIs) ---
        m_col1, m_col2, m_col3, m_col4, m_col5, m_col6, m_col7 = st.columns(7)
        m_col1.metric("⏱️ Tiempo", result['formatted_time'])
        m_col2.metric("📏 Distancia", f"{summary['total_distance_km']:.2f} km")
        m_col3.metric("🚀 Vel. Media", f"{result['average_speed_kmh']:.2f} km/h")
        m_col4.metric("⚡ Potencia Media", f"{avg_power:.0f} W")
        m_col5.metric("🔋 Energía", f"{total_kj:.0f} kJ")
        
        total_seconds = result['total_time_seconds']
        if ftp_watts > 0 and total_seconds > 0:
            intensity_factor_actual = avg_power / ftp_watts
            tss_est = (total_seconds * avg_power * intensity_factor_actual) / (ftp_watts * 3600.0) * 100.0
        else:
            tss_est = 0.0

        m_col6.metric("🔥 Carga (TSS)", f"{tss_est:.0f}")
        m_col7.metric("📈 Desnivel", f"{summary['elevation_gain_m']:.1f} m")

        max_dist_km = float(summary['total_distance_km'])
        
        if "selected_km" not in st.session_state or st.session_state["selected_km"] is None:
            st.session_state["selected_km"] = 0.0

        # Selector deslizante maestro
        selected_km = st.slider(
            "📍 Selector de Kilómetro (Sincronizador maestro)", 
            0.0, max_dist_km, 
            float(min(st.session_state["selected_km"], max_dist_km)), 
            0.1
        )
        st.session_state["selected_km"] = selected_km

        # --- MINIRESUMEN DEL KM SELECCIONADO ---
        idx_closest = (df_sim['distance_accumulated_km'] - selected_km).abs().idxmin()
        row_sel = df_sim.loc[idx_closest]

        elevations = [seg['elevation_start'] for seg in segments] + [segments[-1]['elevation_end']]
        distances_alt = [0] + list(df_sim['distance_accumulated_km'])
        current_elevation = np.interp(selected_km, distances_alt, elevations)

        st.markdown(f"""
        📌 **Detalle en el KM {selected_km:.2f}**: 
        &nbsp;&nbsp;|&nbsp;&nbsp; 🏔️ Altitud: **{current_elevation:.1f} m**
        &nbsp;&nbsp;|&nbsp;&nbsp; ⏱️ Tiempo: **{row_sel['time_formatted']}** 
        &nbsp;&nbsp;|&nbsp;&nbsp; ⚡ Potencia: **{row_sel['power_watts']:.1f} W** 
        &nbsp;&nbsp;|&nbsp;&nbsp; 🚀 Velocidad: **{row_sel['speed_kmh']:.1f} km/h** 
        &nbsp;&nbsp;|&nbsp;&nbsp; 🔋 Energía: **{row_sel['energy_kj_accumulated']:.1f} kJ** 
        &nbsp;&nbsp;|&nbsp;&nbsp; ⚡ W': **{row_sel['w_prime_percent']:.1f}%**
        &nbsp;&nbsp;|&nbsp;&nbsp; 📈 Pendiente: **{row_sel['gradient_percent']:.1f}%**
        &nbsp;&nbsp;|&nbsp;&nbsp; 🎯 FTP Efectivo: **{row_sel['effective_ftp_watts']:.1f} W**
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

        # ==========================================================
        # PARTE SUPERIOR: MAPA Y PERFIL DE ELEVACIÓN LADO A LADO
        # ==========================================================
        top_col1, top_col2 = st.columns(2)

        with top_col1:
            st.subheader("🗺️ Trazado Geométrico")
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
            st.subheader("📈 Perfil de Elevación")
            
            df_plot_ele = df_sim.copy()
            step_sample_ele = max(1, len(df_plot_ele) // 150)
            df_plot_click_ele = df_plot_ele.iloc[::step_sample_ele].copy()
            
            elevations_sampled = [np.interp(d, distances_alt, elevations) for d in df_plot_click_ele['distance_accumulated_km']]

            fig_elev = go.Figure()
            fig_elev.add_trace(
                go.Scatter(
                    x=distances_alt, y=elevations,
                    fill='tozeroy', fillcolor='rgba(46, 134, 193, 0.25)',
                    line=dict(color='rgb(31, 119, 180)', width=2),
                    name="Altitud", hoverinfo='skip'
                )
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
                margin=dict(l=10, r=10, t=20, b=10),
                height=340,
                hovermode="x unified",
                clickmode="event+select"
            )
            event_elev = st.plotly_chart(fig_elev, width='stretch', on_select="rerun", key="chart_elev")

        # ==========================================================
        # PARTE INFERIOR: 3 GRÁFICAS DE RENDIMIENTO INDEPENDIENTES
        # ==========================================================
        st.divider()
        st.subheader("📉 Panorámica de Rendimiento y Fisiología")

        df_plot = df_sim.copy()
        if len(df_plot) > 300:
            window_size = max(5, len(df_plot) // 100)
            df_plot['power_watts'] = df_plot['power_watts'].rolling(window=window_size, min_periods=1).mean()
            df_plot['speed_kmh'] = df_plot['speed_kmh'].rolling(window=window_size, min_periods=1).mean()
            df_plot['w_prime_percent'] = df_plot['w_prime_percent'].rolling(window=window_size, min_periods=1).mean()
            df_plot['effective_ftp_watts'] = df_plot['effective_ftp_watts'].rolling(window=window_size, min_periods=1).mean()
            df_plot['energy_kj_accumulated'] = df_plot['energy_kj_accumulated'].rolling(window=window_size, min_periods=1).mean()

        step_sample = max(1, len(df_plot) // 150)
        df_plot_click = df_plot.iloc[::step_sample].copy()

        # --- GRÁFICA 1: Potencia y Velocidad ---
        fig_combined = make_subplots(specs=[[{"secondary_y": True}]])
        fig_combined.add_trace(go.Scatter(x=df_plot['distance_accumulated_km'], y=df_plot['power_watts'], name="Potencia (W)", line=dict(color='orange', width=2), hoverinfo='skip'), secondary_y=False)
        fig_combined.add_trace(go.Scatter(x=df_plot['distance_accumulated_km'], y=df_plot['speed_kmh'], name="Velocidad (km/h)", line=dict(color='deepskyblue', width=2), hoverinfo='skip'), secondary_y=True)
        
        fig_combined.add_trace(
            go.Scatter(
                x=df_plot_click['distance_accumulated_km'], y=df_plot_click['power_watts'],
                mode='markers', marker=dict(size=8, color='rgba(0,0,0,0)'),
                name="Puntos clic", showlegend=False,
                hovertemplate=(
                    "Distancia: %{x:.2f} km<br>"
                    "Potencia: %{y:.1f} W<br>"
                    "Velocidad: %{customdata[0]:.1f} km/h<br>"
                    "Tiempo: %{customdata[1]}<extra></extra>"
                ),
                customdata=list(zip(df_plot_click['speed_kmh'], df_plot_click['time_formatted']))
            ),
            secondary_y=False
        )
        fig_combined.add_vline(x=selected_km, line_width=2.5, line_dash="dash", line_color="#00FFFF")

        fig_combined.update_layout(
            title="Dinámica de Ruta: Potencia y Velocidad",
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

        # --- GRÁFICA 2: Fatiga y Energía ---
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
                    "Energía Consumida: %{customdata:.1f} kJ<extra></extra>"
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

        # --- GRÁFICA 3: Capacidad Anaeróbica (W') ---
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

        # --- GESTOR DE EVENTOS UNIFICADO (4 GRÁFICAS) ---
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
    st.info("👈 Sube un archivo GPX y pulsa **Simular Ruta** en la barra lateral para empezar.")