const API_URL = "/api/v1/simulate";
const CONFIG_API_URL = "/api/config";
let simulationDataCache = null;

const plotlyConfig = { responsive: true, displayModeBar: 'hover', displaylogo: false };

// --- UTILIDADES DE DISPOSICIÓN Y RESIZE ---
function isMobile() { return window.innerWidth <= 768; }

function getCommonLayout(titleText, customMargin = {}) {
    const mobile = isMobile();
    return {
        title: { text: titleText, font: { size: mobile ? 11 : 13, weight: 900 } },
        paper_bgcolor: '#ffffff',
        plot_bgcolor: '#fcfbfa',
        font: { color: '#121212', family: 'Montserrat, sans-serif' },
        margin: { l: mobile ? 40 : 50, r: mobile ? 20 : 40, t: mobile ? 55 : 40, b: mobile ? 40 : 50, ...customMargin },
        height: mobile ? 300 : 360,
        autosize: true,
        hovermode: 'x unified'
    };
}

function renderPlotlyChart(containerId, traces, layout) {
    Plotly.newPlot(containerId, traces, layout, plotlyConfig);
}

function resizeAllCharts() {
    ['chart-map', 'chart-elevation', 'chart-combined', 'chart-fatigue', 'chart-wprime'].forEach(id => {
        const el = document.getElementById(id);
        if (el && el.data && typeof Plotly !== 'undefined') {
            Plotly.Plots.resize(el);
        }
    });
}

// --- INICIALIZACIÓN ---
document.addEventListener('DOMContentLoaded', () => {
    loadInitialConfig();
    const toggleButton = document.getElementById('toggle-sidebar-btn');
    const sidebar = document.getElementById('sidebar');

    if (toggleButton && sidebar) {
        toggleButton.addEventListener('click', () => {
            sidebar.classList.toggle('is-hidden');
            toggleButton.textContent = sidebar.classList.contains('is-hidden') ? '▶' : '◀';
            setTimeout(resizeAllCharts, 350);
        });
    }
    window.addEventListener('resize', resizeAllCharts);
    loadExampleTracks();
});

async function loadInitialConfig() {
    try {
        const res = await fetch(CONFIG_API_URL);
        if (!res.ok) return;
        const cfg = await res.json();
        
        if (cfg.cyclist) {
            ['weight_kg', 'bike_weight_kg', 'ftp_watts', 'intensity_factor', 'w_prime_kj', 
             'fatigue_rate_per_1000kj', 'cda_seated', 'cda_standing', 'rolling_resistance_cr'].forEach(k => setInputValue(k, cfg.cyclist[k]));
        }
        if (cfg.power_strategy) {
            ['climb_gradient_threshold', 'descent_gradient_threshold', 'descent_power_watts', 
             'false_flat_power_factor', 'exhausted_power_multiplier'].forEach(k => setInputValue(k, cfg.power_strategy[k]));
        }
        if (cfg.simulation_limits) {
            ['max_descent_speed_kmh', 'descent_braking_factor', 'braking_speed_threshold_kmh', 
             'technical_descent_damping'].forEach(k => setInputValue(k, cfg.simulation_limits[k]));
        }
        if (cfg.smooth_radius_1 !== undefined) setInputValue('smooth_radius_1', cfg.smooth_radius_1);
        if (cfg.smooth_radius_2 !== undefined) setInputValue('smooth_radius_2', cfg.smooth_radius_2);
    } catch (e) { console.warn('Error cargando config inicial:', e); }
}

function setInputValue(id, val) {
    if (val !== undefined && val !== null) {
        const el = document.getElementById(id);
        if (el) el.value = val;
    }
}

// --- PETICIÓN Y SIMULACIÓN ---
document.getElementById('sim-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('route-file');
    if (!fileInput.files[0]) return alert("Selecciona un archivo .fit o .gpx");

    const btn = document.getElementById('btn-simulate');
    btn.innerText = "Simulando física...";
    btn.disabled = true;

    const configData = {
        cyclist: {
            weight_kg: parseFloat(document.getElementById('weight_kg').value),
            bike_weight_kg: parseFloat(document.getElementById('bike_weight_kg').value),
            ftp_watts: parseInt(document.getElementById('ftp_watts').value),
            intensity_factor: parseFloat(document.getElementById('intensity_factor').value),
            w_prime_kj: parseFloat(document.getElementById('w_prime_kj').value),
            cda_seated: parseFloat(document.getElementById('cda_seated').value),
            cda_standing: parseFloat(document.getElementById('cda_standing').value),
            rolling_resistance_cr: parseFloat(document.getElementById('rolling_resistance_cr').value),
            fatigue_rate_per_1000kj: parseFloat(document.getElementById('fatigue_rate_per_1000kj').value)
        },
        power_strategy: {
            climb_gradient_threshold: parseFloat(document.getElementById('climb_gradient_threshold').value),
            descent_gradient_threshold: parseFloat(document.getElementById('descent_gradient_threshold').value),
            descent_power_watts: parseFloat(document.getElementById('descent_power_watts').value),
            false_flat_power_factor: parseFloat(document.getElementById('false_flat_power_factor').value),
            exhausted_power_multiplier: parseFloat(document.getElementById('exhausted_power_multiplier').value)
        },
        simulation_limits: {
            max_descent_speed_kmh: parseFloat(document.getElementById('max_descent_speed_kmh').value),
            descent_braking_factor: parseFloat(document.getElementById('descent_braking_factor').value),
            braking_speed_threshold_kmh: parseFloat(document.getElementById('braking_speed_threshold_kmh').value),
            technical_descent_damping: parseFloat(document.getElementById('technical_descent_damping').value)
        },
        smoothing_method: "sql_double_ma",
        smooth_radius_1: parseFloat(document.getElementById('smooth_radius_1').value) || 500.0,
        smooth_radius_2: parseFloat(document.getElementById('smooth_radius_2').value) || 250.0
    };

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('config_json', JSON.stringify(configData));

    try {
        const response = await fetch(API_URL, { method: 'POST', body: formData });
        if (!response.ok) throw new Error(await response.text());
        
        simulationDataCache = await response.json();

        if (simulationDataCache.simulation?.detected_climbs) {
            simulationDataCache.simulation.detected_climbs = simulationDataCache.simulation.detected_climbs.map(c => {
                let cat = c.type;
                if (c.type === "Puerto") {
                    const gain = c.elevation_gain_m || 0;
                    cat = gain <= 300 ? "Puerto 3ª" : gain <= 600 ? "Puerto 2ª" : gain <= 1000 ? "Puerto 1ª" : "Hors Catégorie";
                }
                return { ...c, display_type: cat };
            });
        }

        renderDashboard(simulationDataCache);
        renderClimbsSummaryTable(simulationDataCache.simulation, simulationDataCache.telemetry_records);
    } catch (err) { alert(`Error: ${err.message}`); } 
    finally { btn.innerText = "Simular Ruta"; btn.disabled = false; }
});

function renderDashboard(data) {
    const resultsWrapper = document.getElementById('results-wrapper');
    resultsWrapper.classList.remove('hidden');

    const sidebar = document.getElementById('sidebar');
    const toggleButton = document.getElementById('toggle-sidebar-btn');
    if (sidebar && !sidebar.classList.contains('is-hidden')) {
        sidebar.classList.add('is-hidden');
        if (toggleButton) toggleButton.textContent = '▶';
    }

    resultsWrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });

    const sim = data.simulation, summary = data.summary, real = data.real_telemetry_metrics, segments = sim.segments_simulation;

    document.getElementById('m-time').innerText = sim.formatted_time || "--:--:--";
    document.getElementById('m-dist').innerText = `${summary.total_distance_km.toFixed(2)} km`;
    document.getElementById('m-speed').innerText = `${sim.average_speed_kmh.toFixed(1)} km/h`;
    document.getElementById('m-elev').innerText = `${summary.elevation_gain_m.toFixed(1)} m`;

    const avgPower = segments.reduce((acc, s) => acc + s.power_watts, 0) / segments.length;
    const totalKj = segments[segments.length - 1].energy_kj_accumulated;
    document.getElementById('m-power').innerText = `${Math.round(avgPower)} W`;
    document.getElementById('m-np').innerText = `${Math.round(sim.normalized_power_watts || avgPower)} W`;
    document.getElementById('m-energy').innerText = `${Math.round(totalKj)} kJ`;
    document.getElementById('m-tss').innerText = `${Math.round(sim.tss || 0)}`;

    if (real) {
        document.getElementById('m-time-real').innerText = `Real: ${real.formatted_time || '--:--:--'}`;
        document.getElementById('m-speed-real').innerText = `Real: ${real.average_speed_kmh} km/h`;
        document.getElementById('m-power-real').innerText = `Real: ${real.average_power_watts} W`;
        document.getElementById('m-energy-real').innerText = `Real: ${real.total_energy_kj} kJ`;
        if (real.tss !== undefined) {
            document.getElementById('m-tss').innerHTML = `${Math.round(sim.tss || 0)} <span class="sub-real">Real: ${Math.round(real.tss)}</span>`;
        }
    } else {
        ['m-time-real', 'm-speed-real', 'm-power-real', 'm-energy-real'].forEach(id => document.getElementById(id).innerText = 'Real: --');
    }

    const slider = document.getElementById('km-slider');
    slider.max = summary.total_distance_km;
    slider.value = 0;
    slider.oninput = (e) => updateAllChartsSync(parseFloat(e.target.value));

    plotMap(data.points, segments, sim.detected_climbs || []);
    plotElevation(segments, summary, sim.detected_climbs || []);
    plotCombined(segments, data.telemetry_records);
    plotFatigue(segments);
    plotWPrime(segments);
    
    updateAllChartsSync(0);
    setupChartClickEvents();

    // Refresco doble asegurado para recalcular tras la transición CSS del sidebar
    setTimeout(resizeAllCharts, 100);
    setTimeout(resizeAllCharts, 400);
}

// --- DIBUJO DE GRÁFICOS ---
function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371000, dLat = (lat2 - lat1) * Math.PI / 180, dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLon/2)**2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function plotMap(points, segments, climbs) {
    if (!points?.length) return;
    let distAcc = 0;
    const lons = [], lats = [], elevs = [], dists = [], gradients = [];

    points.forEach((p, idx) => {
        lats.push(p.latitude);
        lons.push(p.longitude);
        elevs.push(p.elevation);
        if (idx > 0) {
            distAcc += haversine(points[idx-1].latitude, points[idx-1].longitude, points[idx].latitude, points[idx].longitude) / 1000;
        }
        dists.push(distAcc);
        gradients.push(segments[idx]?.gradient_percent || 0);
    });

    const traceRoute = {
        x: lons,
        y: lats,
        customdata: dists.map((d, i) => [d, elevs[i], gradients[i]]),
        mode: 'lines',
        line: { width: 3.5, color: '#1d3557' },
        name: 'Ruta General',
        hovertemplate: '<b>KM:</b> %{customdata[0]:.2f} km<br><b>Altitud:</b> %{customdata[1]:.1f} m<br><b>Pendiente:</b> %{customdata[2]:.1f}%<extra></extra>'
    };

    const traces = [traceRoute];

    // Recuperar el dibujado de los puertos/repechos sobre el mapa
    if (climbs && climbs.length > 0) {
        climbs.forEach(climb => {
            const isPuerto = climb.type === "Puerto";
            const color = isPuerto ? "#e63946" : "#ffb703";
            const displayType = climb.display_type || climb.type;
            
            const climbLons = [], climbLats = [], climbElevs = [], climbDists = [], climbGrads = [];
            let runningDist = 0;

            for (let i = 0; i < points.length; i++) {
                if (i > 0) {
                    runningDist += haversine(points[i-1].latitude, points[i-1].longitude, points[i].latitude, points[i].longitude) / 1000;
                }
                if (runningDist >= climb.start_dist_km && runningDist <= climb.end_dist_km) {
                    climbLons.push(points[i].longitude);
                    climbLats.push(points[i].latitude);
                    climbElevs.push(points[i].elevation);
                    climbDists.push(runningDist);
                    climbGrads.push(segments[i]?.gradient_percent || 0);
                }
            }

            if (climbLons.length > 1) {
                traces.push({
                    x: climbLons,
                    y: climbLats,
                    customdata: climbDists.map((d, i) => [d, climbElevs[i], climbGrads[i]]),
                    mode: 'lines',
                    line: { width: 5, color: color },
                    name: displayType,
                    hovertemplate: `<b>${displayType}</b><br><b>KM:</b> %{customdata[0]:.2f} km<br><b>Altitud:</b> %{customdata[1]:.1f} m<br><b>Pendiente:</b> %{customdata[2]:.1f}%<extra></extra>`
                });
            }
        });
    }

    const traceMarker = {
        x: [points[0].longitude],
        y: [points[0].latitude],
        mode: 'markers',
        marker: { size: 12, color: '#e63946', symbol: 'circle', line: { width: 2, color: '#121212' } },
        name: 'Posición',
        hoverinfo: 'skip'
    };
    traces.push(traceMarker);

    const layout = {
        ...getCommonLayout('MAPA DE LA RUTA'),
        xaxis: { title: 'Longitud', gridcolor: '#e5e1dc', automargin: true },
        yaxis: { title: 'Latitud', gridcolor: '#e5e1dc', scaleanchor: 'x', automargin: true },
        hovermode: 'closest',
        showlegend: false
    };

    renderPlotlyChart('chart-map', traces, layout);
}

function plotElevation(segments, summary, climbs) {
    let distAcc = 0;
    const distances = [0], gradients = [segments[0]?.gradient_percent || 0];
    const elevations = segments.map(s => s.absolute_elevation_m ?? 0);
    elevations.unshift(segments[0]?.absolute_elevation_m ? segments[0].absolute_elevation_m - segments[0].elevation_change_m : 0);

    segments.forEach(s => {
        distAcc += s.distance_m / 1000;
        distances.push(distAcc);
        gradients.push(s.gradient_percent || 0);
    });

    const traceElev = {
        x: distances,
        y: elevations,
        customdata: gradients,
        fill: 'tozeroy',
        fillcolor: 'rgba(29, 53, 87, 0.08)',
        line: { color: '#1d3557', width: 2.5 },
        name: 'Perfil General',
        hovertemplate: '<b>KM:</b> %{x:.2f} km<br><b>Altitud:</b> %{y:.1f} m<br><b>Pendiente:</b> %{customdata:.1f}%<extra></extra>'
    };

    const traces = [traceElev];
    const annotations = [];
    let pCount = 1, rCount = 1;

    const repechoX = [], repechoY = [], repechoCustom = [];
    const puertoX = [], puertoY = [], puertoCustom = [];

    // Recuperar el dibujado de las líneas superpuestas en el perfil de elevación
    if (climbs && climbs.length > 0) {
        climbs.forEach(climb => {
            const isPuerto = climb.type === "Puerto";
            const color = isPuerto ? "#e63946" : "#b5830d";
            const labelId = isPuerto ? `P${pCount++}` : `R${rCount++}`;
            const lengthKm = (climb.distance_m / 1000).toFixed(1);
            const displayType = climb.display_type || climb.type;

            const subDistances = [], subElevs = [], climbCustomData = [];
            let runningDist = 0;

            segments.forEach((s) => {
                const segDist = s.distance_m / 1000;
                const prevDist = runningDist;
                runningDist += segDist;
                const segElev = s.absolute_elevation_m !== undefined ? s.absolute_elevation_m : 0;

                if (runningDist >= climb.start_dist_km && prevDist <= climb.end_dist_km) {
                    subDistances.push(runningDist);
                    subElevs.push(segElev);
                    climbCustomData.push([
                        labelId,
                        displayType,
                        lengthKm,
                        climb.elevation_gain_m.toFixed(0),
                        climb.average_slope_percent.toFixed(1)
                    ]);
                }
            });

            if (subDistances.length > 1) {
                const targetX = isPuerto ? puertoX : repechoX;
                const targetY = isPuerto ? puertoY : repechoY;
                const targetCustom = isPuerto ? puertoCustom : repechoCustom;

                targetX.push(...subDistances, null);
                targetY.push(...subElevs, null);
                climbCustomData.forEach(cd => targetCustom.push(cd));
                targetCustom.push(null);

                let maxElev = Math.max(...subElevs);
                let maxIdx = subElevs.indexOf(maxElev);
                let maxDist = subDistances[maxIdx];

                annotations.push({
                    x: maxDist,
                    y: maxElev,
                    text: `<b>${labelId}</b>`,
                    showarrow: true,
                    arrowhead: 0,
                    arrowwidth: 2,
                    arrowcolor: color,
                    ax: 0,
                    ay: -22,
                    font: { size: 10, color: "#ffffff", family: 'Space Mono, monospace', weight: 'bold' },
                    bgcolor: color,
                    borderpad: 3
                });
            }
        });

        if (repechoX.length > 0) {
            traces.push({
                x: repechoX,
                y: repechoY,
                customdata: repechoCustom,
                mode: 'lines',
                line: { color: '#b5830d', width: 5 },
                showlegend: false,
                hovertemplate: '<b>[%{customdata[0]}] %{customdata[1]}</b><br>Distancia: %{customdata[2]} km<br>Desnivel: %{customdata[3]} m<br>Pendiente Media: %{customdata[4]}%<extra></extra>'
            });
        }

        if (puertoX.length > 0) {
            traces.push({
                x: puertoX,
                y: puertoY,
                customdata: puertoCustom,
                mode: 'lines',
                line: { color: '#e63946', width: 5 },
                showlegend: false,
                hovertemplate: '<b>[%{customdata[0]}] %{customdata[1]}</b><br>Distancia: %{customdata[2]} km<br>Desnivel: %{customdata[3]} m<br>Pendiente Media: %{customdata[4]}%<extra></extra>'
            });
        }
    }

    const layout = {
        ...getCommonLayout('PERFIL DE ELEVACIÓN Y PUERTOS'),
        xaxis: { title: 'Distancia Acumulada (km)', gridcolor: '#e5e1dc', automargin: true },
        yaxis: { title: 'Altitud (m)', gridcolor: '#e5e1dc', automargin: true },
        annotations: annotations,
        legend: {
            orientation: 'h',
            yanchor: 'top',
            y: -0.32,
            xanchor: 'center',
            x: 0.5,
            font: { size: 10 }
        }
    };

    renderPlotlyChart('chart-elevation', traces, layout);
}

function plotCombined(segments, telemetry) {
    let distAcc = 0;
    const distances = [0];
    const elevations = segments.map(s => s.absolute_elevation_m ?? 0);
    elevations.unshift(segments[0]?.absolute_elevation_m ? segments[0].absolute_elevation_m - segments[0].elevation_change_m : 0);

    segments.forEach(s => { distAcc += s.distance_m / 1000; distances.push(distAcc); });

    const traces = [
        { x: distances, y: elevations, fill: 'tozeroy', fillcolor: 'rgba(200, 200, 200, 0.1)', line: { color: 'rgba(150, 150, 150, 0.2)' }, yaxis: 'y3', hoverinfo: 'skip' },
        { x: distances.slice(1), y: segments.map(s => s.power_watts), name: 'Potencia Sim. (W)', line: { color: '#b5830d', width: 2.5 } },
        { x: distances.slice(1), y: segments.map(s => s.speed_kmh), name: 'Velocidad Sim. (km/h)', line: { color: '#1d3557', width: 2.5 }, yaxis: 'y2' }
    ];

    const maxElev = Math.max(...elevations, 500);
    const layout = {
        ...getCommonLayout('DINÁMICA DE RUTA: POTENCIA, VELOCIDAD Y PERFIL'),
        xaxis: { title: 'Distancia (km)', gridcolor: '#e5e1dc', automargin: true },
        yaxis: { title: 'Potencia (W)', gridcolor: '#e5e1dc', automargin: true },
        yaxis2: { title: 'Velocidad (km/h)', overlaying: 'y', side: 'right', showgrid: false, automargin: true },
        yaxis3: { overlaying: 'y', side: 'right', showgrid: false, showticklabels: false, range: [0, maxElev * 3.5] },
        legend: { orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center' }
    };

    renderPlotlyChart('chart-combined', traces, layout);
}

function plotFatigue(segments) {
    let distAcc = 0;
    const dists = segments.map(s => { distAcc += s.distance_m / 1000; return distAcc; });

    const traces = [
        { x: dists, y: segments.map(s => s.effective_ftp_watts), name: 'FTP Efectivo (W)', line: { color: '#1d3557', width: 2.5 } },
        { x: dists, y: segments.map(s => s.energy_kj_accumulated), name: 'Energía (kJ)', line: { color: '#e63946', dash: 'dot', width: 2 }, yaxis: 'y2' }
    ];

    const layout = {
        ...getCommonLayout('EVOLUCIÓN DE LA FATIGA: FTP EFECTIVO Y ENERGÍA'),
        xaxis: { title: 'Distancia (km)', gridcolor: '#e5e1dc', automargin: true },
        yaxis: { title: 'FTP Efectivo (W)', gridcolor: '#e5e1dc', automargin: true },
        yaxis2: { title: 'Energía (kJ)', overlaying: 'y', side: 'right', showgrid: false, automargin: true }
    };

    renderPlotlyChart('chart-fatigue', traces, layout);
}

function plotWPrime(segments) {
    let distAcc = 0;
    const dists = segments.map(s => { distAcc += s.distance_m / 1000; return distAcc; });

    const trace = { x: dists, y: segments.map(s => s.w_prime_percent), fill: 'tozeroy', fillcolor: 'rgba(230, 57, 70, 0.1)', line: { color: '#e63946', width: 2.5 } };
    const layout = {
        ...getCommonLayout("CAPACIDAD ANAERÓBICA: W' DISPONIBLE (%)"),
        xaxis: { title: 'Distancia (km)', gridcolor: '#e5e1dc', automargin: true },
        yaxis: { title: "W' (%)", range: [0, 105], gridcolor: '#e5e1dc', automargin: true }
    };

    renderPlotlyChart('chart-wprime', [trace], layout);
}

// --- EVENTOS INTERACTIVOS Y TABLA ---
function updateAllChartsSync(km) {
    document.getElementById('lbl-km').innerText = km.toFixed(2);
    if (!simulationDataCache) return;

    const segments = simulationDataCache.simulation.segments_simulation;
    let distAcc = 0, minDiff = Infinity, closestSeg = segments[0], idx = 0;

    segments.forEach((s, i) => {
        distAcc += s.distance_m / 1000;
        if (Math.abs(distAcc - km) < minDiff) {
            minDiff = Math.abs(distAcc - km);
            closestSeg = s; idx = i;
        }
    });

    document.getElementById('km-detail-box').innerHTML = `
        <strong>KM ${km.toFixed(2)}</strong> | Tiempo: <strong>${closestSeg.time_formatted || '00:00'}</strong> | Potencia: <strong>${closestSeg.power_watts.toFixed(1)} W</strong> | Velocidad: <strong>${closestSeg.speed_kmh.toFixed(1)} km/h</strong> | Pendiente: <strong>${closestSeg.gradient_percent.toFixed(1)}%</strong> | W': <strong>${closestSeg.w_prime_percent.toFixed(1)}%</strong>
    `;

    const vLine = { type: 'line', x0: km, x1: km, y0: 0, y1: 1, yref: 'paper', line: { color: '#e63946', width: 2, dash: 'dash' } };
    ['chart-elevation', 'chart-combined', 'chart-fatigue', 'chart-wprime'].forEach(id => {
        if (document.getElementById(id)?.data) Plotly.relayout(id, { shapes: [vLine] });
    });
}

function setupChartClickEvents() {
    ['chart-elevation', 'chart-map', 'chart-combined', 'chart-fatigue', 'chart-wprime'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.removeAllListeners('plotly_click');
            el.on('plotly_click', (d) => {
                const pt = d.points?.[0];
                if (pt) {
                    const km = id === 'chart-map' ? pt.customdata?.[0] : pt.x;
                    if (typeof km === 'number') updateAllChartsSync(km);
                }
            });
        }
    });
}

function renderClimbsSummaryTable(simulationData, telemetryRecords) {
    const tbody = document.getElementById('comparison-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    const climbs = simulationData.detected_climbs || [];

    if (!climbs.length) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; padding: 15px;">No se han detectado puertos significativos.</td></tr>`;
        return;
    }

    let pCount = 1, rCount = 1;
    climbs.forEach(climb => {
        const isP = climb.type === "Puerto";
        const labelId = isP ? `P${pCount++}` : `R${rCount++}`;
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><span class="${isP ? 'badge-puerto' : 'badge-repecho'}">[${labelId}]</span></td>
            <td>${climb.start_dist_km.toFixed(2)} km</td>
            <td>${(climb.distance_m/1000).toFixed(2)} km</td>
            <td>${climb.elevation_gain_m.toFixed(0)} m</td>
            <td>${climb.average_slope_percent.toFixed(1)}%</td>
            <td colspan="6" style="text-align:center; color:#888;">Procesado</td>
        `;
        tbody.appendChild(row);
    });
}

async function loadExampleTracks() {
    try {
        const res = await fetch('/api/v1/examples');
        if (!res.ok) return;
        const data = await res.json();
        const select = document.getElementById('example-select');
        data.examples?.forEach(fn => {
            const opt = document.createElement('option');
            opt.value = fn; opt.textContent = fn.replace(/\.[^/.]+$/, "").toUpperCase();
            select.appendChild(opt);
        });
    } catch (e) { console.warn("Error rutas ejemplo", e); }
}

document.getElementById('btn-load-example').addEventListener('click', async () => {
    const select = document.getElementById('example-select');
    if (!select.value) return alert("Selecciona una ruta de ejemplo.");
    try {
        const res = await fetch(`/tracks/${select.value}`);
        const blob = await res.blob();
        const file = new File([blob], select.value);
        const dt = new DataTransfer();
        dt.items.add(file);
        document.getElementById('route-file').files = dt.files;
        alert(`¡Ruta '${select.value}' lista para simular!`);
    } catch (err) { alert(`Error: ${err.message}`); }
});