# --- PANEL DE MÉTRICAS RESUMEN GENERAL (7 KPIs) ---
        m_col1, m_col2, m_col3, m_col4, m_col5, m_col6, m_col7 = st.columns(7)
        m_col1.metric("⏱️ Tiempo", result['formatted_time'])
        m_col2.metric("📏 Distancia", f"{summary['total_distance_km']:.2f} km")
        m_col3.metric("🚀 Vel. Media", f"{result['average_speed_kmh']:.2f} km/h")
        m_col4.metric("⚡ Potencia Media", f"{avg_power:.0f} W")
        m_col5.metric("🔋 Energía", f"{total_kj:.0f} kJ")
        
        # Cálculo estimado de TSS (Training Stress Score)
        total_seconds = result['total_time_seconds']
        if ftp_watts > 0 and total_seconds > 0:
            intensity_factor_actual = avg_power / ftp_watts
            tss_est = (total_seconds * avg_power * intensity_factor_actual) / (ftp_watts * 3600.0) * 100.0
        else:
            tss_est = 0.0

        m_col6.metric("🔥 Carga (TSS)", f"{tss_est:.0f}")
        m_col7.metric("📈 Desnivel", f"{summary['elevation_gain_m']:.1f} m")