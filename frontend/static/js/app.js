const API_URL = "/api/v1/simulate";
const CONFIG_API_URL = "/api/config";
let simulationDataCache = null;

// Inicialización global al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    loadInitialConfig();

    const toggleButton = document.getElementById('toggle-sidebar-btn');
    const sidebar = document.getElementById('sidebar');

    if (toggleButton && sidebar) {
        toggleButton.addEventListener('click', () => {
            sidebar.classList.toggle('is-hidden');
            if (sidebar.classList.contains('is-hidden')) {
                toggleButton.textContent = '▶';
            } else {
                toggleButton.textContent = '◀';
            }
        });
    }

    loadExampleTracks();
});

async function loadInitialConfig() {
    try {
        const response = await fetch(CONFIG_API_URL);
        if (!response.ok) return;

        const config = await response.json();

        if (config.cyclist) {
            setInputValue('weight_kg', config.cyclist.weight_kg);
            setInputValue('bike_weight_kg', config.cyclist.bike_weight_kg);
            setInputValue('ftp_watts', config.cyclist.ftp_watts);
            setInputValue('intensity_factor', config.cyclist.intensity_factor);
            setInputValue('w_prime_kj', config.cyclist.w_prime_kj);
            setInputValue('fatigue_rate_per_1000kj', config.cyclist.fatigue_rate_per_1000kj);
            setInputValue('cda_seated', config.cyclist.cda_seated);
            setInputValue('cda_standing', config.cyclist.cda_standing);
            setInputValue('rolling_resistance_cr', config.cyclist.rolling_resistance_cr);
        }

        if (config.power_strategy) {
            setInputValue('climb_gradient_threshold', config.power_strategy.climb_gradient_threshold);
            setInputValue('descent_gradient_threshold', config.power_strategy.descent_gradient_threshold);
            setInputValue('descent_power_watts', config.power_strategy.descent_power_watts);
            setInputValue('false_flat_power_factor', config.power_strategy.false_flat_power_factor);
            setInputValue('exhausted_power_multiplier', config.power_strategy.exhausted_power_multiplier);
        }

        if (config.simulation_limits) {
            setInputValue('max_descent_speed_kmh', config.simulation_limits.max_descent_speed_kmh);
            setInputValue('descent_braking_factor', config.simulation_limits.descent_braking_factor);
            setInputValue('braking_speed_threshold_kmh', config.simulation_limits.braking_speed_threshold_kmh);
            setInputValue('technical_descent_damping', config.simulation_limits.technical_descent_damping);
        }

        if (config.smooth_radius_1 !== undefined) setInputValue('smooth_radius_1', config.smooth_radius_1);
        if (config.smooth_radius_2 !== undefined) setInputValue('smooth_radius_2', config.smooth_radius_2);

    } catch (error) {
        console.warn('No se pudieron cargar los valores predeterminados de la configuración:', error);
    }
}

function setInputValue(id, val) {
    if (val !== undefined && val !== null) {
        const input = document.getElementById(id);
        if (input) input.value = val;
    }
}

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

        // Procesar y categorizar los puertos según el desnivel
        if (simulationDataCache.simulation && simulationDataCache.simulation.detected_climbs) {
            simulationDataCache.simulation.detected_climbs = simulationDataCache.simulation.detected_climbs.map(climb => {
                let cat = climb.type;
                if (climb.type === "Puerto") {
                    const gain = climb.elevation_gain_m || 0;
                    if (gain <= 300) cat = "Puerto 3ª";
                    else if (gain <= 600) cat = "Puerto 2ª";
                    else if (gain <= 1000) cat = "Puerto 1ª";
                    else cat = "Hors Catégorie";
                }
                return { ...climb, display_type: cat };
            });
        }

        renderDashboard(simulationDataCache);
        renderClimbsSummaryTable(simulationDataCache.simulation, simulationDataCache.telemetry_records);
    } catch (err) {
        alert(`Error: ${err.message}`);
    } finally {
        btn.innerText = "Simular Ruta";
        btn.disabled = false;
    }
});

function renderDashboard(data) {
    const resultsWrapper = document.getElementById('results-wrapper');
    resultsWrapper.classList.remove('hidden');

    // --- 1. Ocultar el panel lateral automáticamente tras simular ---
    const sidebar = document.getElementById('sidebar');
    const toggleButton = document.getElementById('toggle-sidebar-btn');
    if (sidebar && !sidebar.classList.contains('is-hidden')) {
        sidebar.classList.add('is-hidden');
        if (toggleButton) toggleButton.textContent = '▶';
    }

    // --- 2. Auto-scroll suave hacia la zona de resultados ---
    resultsWrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });

    const sim = data.simulation;
    const summary = data.summary;
    const real = data.real_telemetry_metrics;
    const segments = sim.segments_simulation;

    // Métricas simuladas
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

    // Métricas reales
    if (real) {
        document.getElementById('m-time-real').innerText = `Real: ${real.formatted_time || '--:--:--'}`;
        document.getElementById('m-speed-real').innerText = `Real: ${real.average_speed_kmh} km/h`;
        document.getElementById('m-power-real').innerText = `Real: ${real.average_power_watts} W`;
        document.getElementById('m-energy-real').innerText = `Real: ${real.total_energy_kj} kJ`;
        
        if (real.tss !== undefined) {
            const tssCard = document.getElementById('m-tss');
            tssCard.innerHTML = `${Math.round(sim.tss || 0)} <span class="sub-real">Real: ${Math.round(real.tss)}</span>`;
        }
    } else {
        document.getElementById('m-time-real').innerText = `Real: --`;
        document.getElementById('m-speed-real').innerText = `Real: --`;
        document.getElementById('m-power-real').innerText = `Real: --`;
        document.getElementById('m-energy-real').innerText = `Real: --`;
    }

    const slider = document.getElementById('km-slider');
    slider.max = summary.total_distance_km;
    slider.value = 0;
    
    slider.oninput = (e) => {
        updateAllChartsSync(parseFloat(e.target.value));
    };

    plotMap(data.points, segments, sim.detected_climbs || []);
    plotElevation(segments, summary, sim.detected_climbs || []);
    plotCombined(segments, data.telemetry_records);
    plotFatigue(segments);
    plotWPrime(segments);
    
    updateAllChartsSync(0);
    setupChartClickEvents();
}

function updateAllChartsSync(km) {
    document.getElementById('lbl-km').innerText = km.toFixed(2);
    const slider = document.getElementById('km-slider');
    if (slider && parseFloat(slider.value) !== km) slider.value = km;

    if (!simulationDataCache) return;

    const segments = simulationDataCache.simulation.segments_simulation;
    const points = simulationDataCache.points;
    let distAcc = 0;
    let closestSeg = segments[0];
    let minDiff = Infinity;
    let closestSegmentIndex = 0;

    segments.forEach((s, idx) => {
        distAcc += s.distance_m / 1000;
        const diff = Math.abs(distAcc - km);
        if (diff < minDiff) {
            minDiff = diff;
            closestSeg = s;
            closestSegmentIndex = idx;
        }
    });

    document.getElementById('km-detail-box').innerHTML = `
        <strong>Detalle en el KM ${km.toFixed(2)}</strong> &nbsp;|&nbsp; 
        Tiempo: <strong>${closestSeg.time_formatted || '00:00'}</strong> &nbsp;|&nbsp; 
        Potencia: <strong>${closestSeg.power_watts.toFixed(1)} W</strong> &nbsp;|&nbsp; 
        Velocidad: <strong>${closestSeg.speed_kmh.toFixed(1)} km/h</strong> &nbsp;|&nbsp; 
        Pendiente: <strong>${closestSeg.gradient_percent.toFixed(1)}%</strong> &nbsp;|&nbsp; 
        W': <strong>${closestSeg.w_prime_percent.toFixed(1)}%</strong>
    `;

    const verticalLineShape = {
        type: 'line',
        x0: km,
        x1: km,
        y0: 0,
        y1: 1,
        yref: 'paper',
        line: { color: '#e63946', width: 2, dash: 'dash' }
    };

    ['chart-elevation', 'chart-combined', 'chart-fatigue', 'chart-wprime'].forEach(chartId => {
        const el = document.getElementById(chartId);
        if (el && el.data) {
            Plotly.relayout(chartId, { shapes: [verticalLineShape] });
        }
    });

    const mapEl = document.getElementById('chart-map');
    if (mapEl && mapEl.data && points && points.length > 0) {
        let targetPoint = points[Math.min(closestSegmentIndex, points.length - 1)];
        const markerTraceIndex = mapEl.data.length - 1;
        
        Plotly.restyle('chart-map', {
            x: [[targetPoint.longitude]],
            y: [[targetPoint.latitude]]
        }, [markerTraceIndex]);
    }
}

function setupChartClickEvents() {
    ['chart-elevation', 'chart-map', 'chart-combined', 'chart-fatigue', 'chart-wprime'].forEach(chartId => {
        const el = document.getElementById(chartId);
        if (el) {
            el.removeAllListeners('plotly_click');
            el.on('plotly_click', function(data) {
                if (data.points && data.points.length > 0) {
                    const pt = data.points[0];
                    let clickedKm = null;
                    
                    if (chartId === 'chart-map' && pt.customdata) {
                        clickedKm = pt.customdata[0];
                    } else if (pt.x !== undefined) {
                        clickedKm = pt.x;
                    }

                    if (typeof clickedKm === 'number' && !isNaN(clickedKm)) {
                        updateAllChartsSync(clickedKm);
                    }
                }
            });
        }
    });
}

function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371000;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

function plotMap(points, segments, climbs) {
    if (!points || points.length === 0) return;

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
        
        let grad = 0;
        if (segments[idx] && segments[idx].gradient_percent !== undefined) {
            grad = segments[idx].gradient_percent;
        }
        gradients.push(grad);
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
                    climbGrads.push(segments[i] ? segments[i].gradient_percent : 0);
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
        title: { text: 'MAPA DE LA RUTA', font: { size: 13, weight: 900 } },
        paper_bgcolor: '#ffffff',
        plot_bgcolor: '#fcfbfa',
        font: { color: '#121212', family: 'Montserrat, sans-serif' },
        xaxis: { title: 'Longitud', gridcolor: '#e5e1dc', zerolinecolor: '#cccccc', automargin: true },
        yaxis: { title: 'Latitud', gridcolor: '#e5e1dc', zerolinecolor: '#cccccc', scaleanchor: 'x', automargin: true },
        margin: { l: 50, r: 40, t: 40, b: 50 },
        height: 380,
        hovermode: 'closest',
        showlegend: false
    };

    Plotly.newPlot('chart-map', traces, layout);
}

function plotElevation(segments, summary, climbs) {
    let distAcc = 0;
    const distances = [0], gradients = [segments.length > 0 ? segments[0].gradient_percent : 0];

    // Construir el perfil general usando la altitud absoluta real desde origen
    const elevations = segments.map(s => s.absolute_elevation_m !== undefined ? s.absolute_elevation_m : 0);
    if (segments.length > 0 && segments[0].absolute_elevation_m !== undefined) {
        elevations.unshift(segments[0].absolute_elevation_m - segments[0].elevation_change_m);
    } else {
        elevations.unshift(0);
    }

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
                
                // Usar la altitud absoluta real del segmento en lugar de acumular desde 0
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
        title: { text: 'PERFIL DE ELEVACIÓN Y PUERTOS', font: { size: 13, weight: 900 } },
        paper_bgcolor: '#ffffff',
        plot_bgcolor: '#fcfbfa',
        font: { color: '#121212', family: 'Montserrat, sans-serif' },
        xaxis: { title: 'Distancia Acumulada (km)', gridcolor: '#e5e1dc', zerolinecolor: '#cccccc', automargin: true },
        yaxis: { title: 'Altitud (m)', gridcolor: '#e5e1dc', zerolinecolor: '#cccccc', automargin: true },
        margin: { l: 50, r: 40, t: 40, b: 60 },
        height: 380,
        hovermode: 'x unified',
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

    Plotly.newPlot('chart-elevation', traces, layout);
}
function plotCombined(segments, telemetry) {
    let distAcc = 0;
    const distances = [0];
    
    const elevations = segments.map(s => s.absolute_elevation_m !== undefined ? s.absolute_elevation_m : 0);
    elevations.unshift(segments.length > 0 && segments[0].absolute_elevation_m !== undefined ? segments[0].absolute_elevation_m - segments[0].elevation_change_m : 0);

    segments.forEach(s => {
        distAcc += s.distance_m / 1000;
        distances.push(distAcc);
    });

    let simPower = segments.map(s => s.power_watts);
    let simSpeed = segments.map(s => s.speed_kmh);
    let simTimes = segments.map(s => s.time_seconds || 0);

    let simTimeAcc = [];
    let cumulativeT = 0;
    simTimes.forEach(t => {
        cumulativeT += t;
        simTimeAcc.push(cumulativeT);
    });

    const smoothWindow = (arr, win) => {
        const res = [];
        for (let i = 0; i < arr.length; i++) {
            let sum = 0, count = 0;
            for (let j = Math.max(0, i - Math.floor(win/2)); j <= Math.min(arr.length - 1, i + Math.floor(win/2)); j++) {
                sum += arr[j];
                count++;
            }
            res.push(sum / count);
        }
        return res;
    };

    if (simPower.length > 50) {
        const windowSize = Math.max(5, Math.floor(simPower.length / 100));
        simPower = smoothWindow(simPower, windowSize);
        simSpeed = smoothWindow(simSpeed, windowSize);
    }

    const traceElevBg = {
        x: distances,
        y: elevations,
        name: 'Perfil de Ruta',
        fill: 'tozeroy',
        fillcolor: 'rgba(200, 200, 200, 0.1)',
        line: { color: 'rgba(150, 150, 150, 0.2)', width: 1 },
        yaxis: 'y3',
        hoverinfo: 'skip'
    };

    const tracePower = {
        x: distances.slice(1),
        y: simPower,
        name: 'Potencia Simulada (W)',
        line: { color: '#b5830d', width: 2.5 },
        hovertemplate: 'Potencia Sim.: %{y:.1f} W<extra></extra>'
    };

    const traceSpeed = {
        x: distances.slice(1),
        y: simSpeed,
        name: 'Velocidad Sim. (km/h)',
        line: { color: '#1d3557', width: 2.5 },
        yaxis: 'y2',
        hovertemplate: 'Velocidad Sim.: %{y:.1f} km/h<extra></extra>'
    };

    const traces = [traceElevBg, tracePower, traceSpeed];

    if (telemetry && telemetry.length > 0) {
        let telDist = telemetry.map(t => t.distance_accumulated_km);
        let telPower = telemetry.map(t => t.real_power_watts);
        let telSpeed = telemetry.map(t => t.real_speed_kmh);

        let maxSimDist = distances[distances.length - 1];
        let maxTelDist = telDist[telDist.length - 1];
        if (maxTelDist > 0 && maxSimDist > 0) {
            telDist = telDist.map(d => (d / maxTelDist) * maxSimDist);
        }

        let telTimesAcc = [];
        if (telemetry[0].time) {
            let t0 = new Date(telemetry[0].time).getTime();
            telemetry.forEach(t => {
                let tCurr = new Date(t.time).getTime();
                telTimesAcc.push((tCurr - t0) / 1000.0);
            });
        } else {
            let tSum = 0;
            telemetry.forEach((t, idx) => {
                if (idx > 0) {
                    let dStep = telDist[idx] - telDist[idx-1];
                    let vMs = (t.real_speed_kmh || 20) / 3.6;
                    tSum += vMs > 0 ? (dStep * 1000) / vMs : 0;
                }
                telTimesAcc.push(tSum);
            });
        }

        if (telPower.length > 50) {
            const windowSize = Math.max(5, Math.floor(telPower.length / 100));
            telPower = smoothWindow(telPower, windowSize);
            telSpeed = smoothWindow(telSpeed, windowSize);
        }

        let timeDiffCustom = [];
        for (let i = 0; i < telDist.length; i++) {
            let dCurrent = telDist[i];
            let simIdx = 0;
            let minDDiff = Infinity;
            for (let j = 0; j < distances.length; j++) {
                let dDiff = Math.abs(distances[j] - dCurrent);
                if (dDiff < minDDiff) {
                    minDDiff = dDiff;
                    simIdx = j;
                }
            }
            let simT = simTimeAcc[Math.max(0, simIdx - 1)] || 0;
            let realT = telTimesAcc[i] || 0;
            let diffSec = realT - simT;
            
            let sign = diffSec >= 0 ? "+" : "-";
            let absSec = Math.abs(diffSec);
            let m = Math.floor(absSec / 60);
            let s = Math.floor(absSec % 60);
            let diffStr = `${sign}${m}m ${s}s`;

            timeDiffCustom.push(diffStr);
        }

        traces.push({
            x: telDist,
            y: telPower,
            name: 'Potencia Real',
            line: { color: '#e63946', dash: 'dot', width: 2 },
            customdata: timeDiffCustom,
            hovertemplate: 'Potencia Real: %{y:.1f} W<br>Desfase T: %{customdata}<extra></extra>'
        });

        traces.push({
            x: telDist,
            y: telSpeed,
            name: 'Velocidad Real',
            line: { color: '#457b9d', dash: 'dot', width: 2 },
            yaxis: 'y2',
            customdata: timeDiffCustom,
            hovertemplate: 'Velocidad Real: %{y:.1f} km/h<br>Desfase T: %{customdata}<extra></extra>'
        });
    }

    const maxElev = elevations.length > 0 ? Math.max(...elevations) : 500;

    const layout = {
        title: {
            text: 'DINÁMICA DE RUTA: POTENCIA, VELOCIDAD Y PERFIL',
            font: { size: 13, weight: 900 }
        },
        paper_bgcolor: '#ffffff', 
        plot_bgcolor: '#fcfbfa', 
        font: { color: '#121212', family: 'Montserrat, sans-serif' },
        xaxis: { title: 'Distancia Acumulada (km)', gridcolor: '#e5e1dc', zerolinecolor: '#cccccc', automargin: true },
        yaxis: { title: 'Potencia (W)', side: 'left', gridcolor: '#e5e1dc', zerolinecolor: '#cccccc', automargin: true, zorder: 2 },
        yaxis2: { title: 'Velocidad (km/h)', overlaying: 'y', side: 'right', showgrid: false, automargin: true, zorder: 2 },
        yaxis3: {
            title: '',
            overlaying: 'y',
            side: 'right',
            showgrid: false,
            zeroline: false,
            showticklabels: false,
            range: [0, maxElev * 3.5],
            zorder: 1
        },
        margin: { l: 60, r: 85, t: 85, b: 60 },
        height: 360, 
        hovermode: 'x unified',
        legend: { 
            orientation: 'h', 
            yanchor: 'bottom', 
            y: 1.05, 
            xanchor: 'center', 
            x: 0.5,
            font: { size: 10 }
        }
    };
    
    Plotly.newPlot('chart-combined', traces, layout);
}

function plotFatigue(segments) {
    let distAcc = 0;
    const distances = segments.map(s => { distAcc += s.distance_m / 1000; return distAcc; });
    const ftpEff = segments.map(s => s.effective_ftp_watts);
    const energy = segments.map(s => s.energy_kj_accumulated);

    const traceFtp = { x: distances, y: ftpEff, name: 'FTP Efectivo (W)', line: { color: '#1d3557', width: 2.5 } };
    const traceEnergy = { x: distances, y: energy, name: 'Energía (kJ)', line: { color: '#e63946', width: 2, dash: 'dot' }, yaxis: 'y2' };

    const layout = {
        title: { text: 'EVOLUCIÓN DE LA FATIGA: FTP EFECTIVO Y ENERGÍA', font: { size: 13, weight: 900 } },
        paper_bgcolor: '#ffffff', 
        plot_bgcolor: '#fcfbfa', 
        font: { color: '#121212', family: 'Montserrat, sans-serif' },
        xaxis: { title: 'Distancia (km)', gridcolor: '#e5e1dc', zerolinecolor: '#cccccc', automargin: true },
        yaxis: { title: 'FTP Efectivo (W)', gridcolor: '#e5e1dc', zerolinecolor: '#cccccc', automargin: true },
        yaxis2: { title: 'Energía (kJ)', overlaying: 'y', side: 'right', showgrid: false, automargin: true },
        margin: { l: 50, r: 75, t: 40, b: 50 },
        height: 300, 
        hovermode: 'x unified',
        legend: { orientation: 'h', y: 1.15, x: 1, xanchor: 'right', font: { size: 10 } }
    };
    Plotly.newPlot('chart-fatigue', [traceFtp, traceEnergy], layout);
}

function plotWPrime(segments) {
    let distAcc = 0;
    const distances = segments.map(s => { distAcc += s.distance_m / 1000; return distAcc; });
    const wPrime = segments.map(s => s.w_prime_percent);

    const traceW = {
        x: distances, y: wPrime, name: "W' Disponible (%)",
        fill: 'tozeroy', fillcolor: 'rgba(230, 57, 70, 0.1)', line: { color: '#e63946', width: 2.5 }
    };

    const layout = {
        title: { text: "CAPACIDAD ANAERÓBICA: W' DISPONIBLE (%)", font: { size: 13, weight: 900 } },
        paper_bgcolor: '#ffffff', 
        plot_bgcolor: '#fcfbfa', 
        font: { color: '#121212', family: 'Montserrat, sans-serif' },
        xaxis: { title: 'Distancia (km)', gridcolor: '#e5e1dc', zerolinecolor: '#cccccc', automargin: true }, 
        yaxis: { title: "W' (%)", range: [0, 105], gridcolor: '#e5e1dc', zerolinecolor: '#cccccc', automargin: true },
        margin: { l: 50, r: 40, t: 40, b: 50 },
        height: 280, 
        hovermode: 'x unified'
    };
    Plotly.newPlot('chart-wprime', [traceW], layout);
}

function renderClimbsSummaryTable(simulationData, telemetryRecords) {
    const tbody = document.getElementById('comparison-table-body');
    if (!tbody) return;

    tbody.innerHTML = '';
    const climbs = simulationData.detected_climbs || [];

    if (climbs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; padding: 15px; color: #6c757d;">No se han detectado puertos o tramos significativos en esta ruta.</td></tr>`;
        return;
    }

    let runningSimDist = 0;
    const simSegmentsWithDist = (simulationData.segments_simulation || []).map(s => {
        runningSimDist += (s.distance_m || 0) / 1000.0;
        return { ...s, accumulated_km: runningSimDist };
    });

    let telSegmentsWithDist = [];
    if (telemetryRecords && telemetryRecords.length > 0) {
        let runningTelDist = 0;
        telSegmentsWithDist = telemetryRecords.map((t, idx) => {
            if (idx > 0) {
                const prev = telemetryRecords[idx - 1];
                runningTelDist += haversine(prev.latitude, prev.longitude, t.latitude, t.longitude) / 1000.0;
            }
            return { ...t, accumulated_km: t.distance_accumulated_km !== undefined ? t.distance_accumulated_km : runningTelDist };
        });
    }

    function formatSecToTime(sec) {
        if (!sec || isNaN(sec)) return '--:--';
        const h = Math.floor(sec / 3600);
        const m = Math.floor((sec % 3600) / 60);
        const s = Math.floor(sec % 60);
        if (h > 0) {
            return `${h}:${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
        }
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    }

    let pCount = 1;
    let rCount = 1;

    climbs.forEach((climb) => {
        const isPuerto = climb.type === "Puerto";
        const labelId = isPuerto ? `P${pCount++}` : `R${rCount++}`;
        const badgeClass = isPuerto ? "badge-puerto" : "badge-repecho";
        const climbDistKm = climb.distance_m / 1000.0;
        const displayType = climb.display_type || climb.type;

        // --- SIMULACIÓN ---
        const segmentsSim = simSegmentsWithDist.filter(s => {
            const distKm = s.accumulated_km || 0;
            return distKm >= climb.start_dist_km && distKm <= climb.end_dist_km;
        });

        let simPower = 0;
        let simTimeSec = 0;
        if (segmentsSim.length > 0) {
            simPower = segmentsSim.reduce((acc, curr) => acc + curr.power_watts, 0) / segmentsSim.length;
            simTimeSec = segmentsSim.reduce((acc, curr) => acc + (curr.time_seconds || 0), 0);
        }

        let simSpeed = (simTimeSec > 0 && climbDistKm > 0) ? climbDistKm / (simTimeSec / 3600.0) : 0;

        // --- REALIDAD ---
        let realSpeed = '--';
        let realPower = '--';
        let realTimeStr = '--:--';

        if (telSegmentsWithDist.length > 0) {
            const telInRange = telSegmentsWithDist.filter(t => {
                const distKm = t.accumulated_km || 0;
                return distKm >= climb.start_dist_km && distKm <= climb.end_dist_km;
            });

            if (telInRange.length > 0) {
                const rPowers = telInRange.map(t => t.real_power_watts || t.power_watts).filter(v => v !== undefined);
                if (rPowers.length > 0) {
                    realPower = (rPowers.reduce((a, b) => a + b, 0) / rPowers.length).toFixed(1) + ' W';
                }

                if (telInRange[0].time && telInRange[telInRange.length - 1].time) {
                    const tStart = new Date(telInRange[0].time).getTime();
                    const tEnd = new Date(telInRange[telInRange.length - 1].time).getTime();
                    const diffSec = (tEnd - tStart) / 1000.0;
                    if (diffSec > 0) {
                        realTimeStr = formatSecToTime(diffSec);
                        const realSpeedVal = climbDistKm / (diffSec / 3600.0);
                        realSpeed = realSpeedVal.toFixed(1) + ' km/h';
                    }
                }
            }
        }

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <div style="display: flex; flex-direction: column; gap: 2px;">
                    <span class="${badgeClass}">[${labelId}]</span>
                    <span class="badge-subtipo">${displayType}</span>
                </div>
            </td>
            <td>${climb.start_dist_km.toFixed(2)} km</td>
            <td>${climbDistKm.toFixed(2)} km</td>
            <td>${climb.elevation_gain_m.toFixed(0)} m</td>
            <td>${climb.average_slope_percent.toFixed(1)}%</td>
            <td>${formatSecToTime(simTimeSec)}</td>
            <td class="col-real">${realTimeStr}</td>
            <td>${simSpeed.toFixed(1)} km/h</td>
            <td class="col-real">${realSpeed}</td>
            <td>${simPower.toFixed(0)} W</td>
            <td class="col-real">${realPower}</td>
        `;
        tbody.appendChild(row);
    });
}

async function loadExampleTracks() {
    try {
        const response = await fetch('/api/v1/examples');
        if (!response.ok) return;
        const data = await response.json();
        
        const select = document.getElementById('example-select');
        if (data.examples && data.examples.length > 0) {
            data.examples.forEach(filename => {
                const option = document.createElement('option');
                option.value = filename;
                option.textContent = filename.replace(/\.[^/.]+$/, "").toUpperCase();
                select.appendChild(option);
            });
        }
    } catch (e) {
        console.warn("No se pudieron cargar las rutas de ejemplo", e);
    }
}

document.getElementById('btn-load-example').addEventListener('click', async () => {
    const select = document.getElementById('example-select');
    const filename = select.value;
    if (!filename) return alert("Por favor, selecciona una ruta de ejemplo.");

    try {
        const response = await fetch(`/tracks/${filename}`);
        if (!response.ok) throw new Error("No se pudo descargar el archivo de ejemplo.");
        
        const blob = await response.blob();
        const file = new File([blob], filename, { type: filename.endsWith('.fit') ? application/octet-stream : "application/gpx+xml" });

        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        document.getElementById('route-file').files = dataTransfer.files;

        alert(`¡Ruta '${filename}' cargada con éxito! Pulsa en 'Simular Ruta' para ver los resultados.`);
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
});