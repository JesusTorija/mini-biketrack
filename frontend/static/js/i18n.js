let currentLang = localStorage.getItem('app_lang') || 'es';

const translations = {
    es: {
        title: "Hors Catégorie - Simulador de rutas de Ciclismo",
        headerSubtitle: "Simulador de Física Ciclista & Análisis Telemétrico Avanzado",
        sidebarTitle: "Parámetros de Simulación",
        fileLabel: "Archivo de Ruta (.fit / .gpx):",
        noFileYet: "¿Sin archivo? Prueba un ejemplo:",
        loadExampleBtn: "Cargar",
        selectExample: "-- Selecciona ruta de ejemplo --",
        simulateBtn: "Simular Ruta",
        simulatingBtn: "Simulando física...",
        // Fieldsets
        fs1: "1. Ciclista y Fisiología",
        fs2: "2. Aerodinámica y Resistencia",
        fs3: "3. Estrategia de Potencia",
        fs4: "4. Control de Descensos y Límites",
        fs5: "5. Parámetros de Suavizado de Ruta",
        lblWeightKg: "Peso ciclista (kg):",
        lblBikeWeightKg: "Peso bici (kg):",
        lblFtpWatts: "FTP (W):",
        lblIntensityFactor: "Factor Intensidad (IF):",
        lblWPrimeKj: "Capacidad W' (kJ):",
        lblFatigueRate: "Fatiga por 1.000 kJ (%):",
        lblCdaSeated: "CdA Sentado:",
        lblCdaStanding: "CdA De pie:",
        lblRollingResistance: "Coef. Rodadura (Cr):",
        lblClimbThreshold: "Pendiente mín. subida (%):",
        lblDescentThreshold: "Pendiente mín. bajada (%):",
        lblDescentPower: "Vatios bajada pronunciada (W):",
        lblFalseFlatPower: "Factor potencia falso llano:",
        lblExhaustedPower: "Multiplicador W' agotada:",
        lblMaxDescentSpeed: "Velocidad máx. descenso (km/h):",
        lblBrakingFactor: "Factor de frenado (Curvas):",
        lblBrakingThreshold: "Umbral inicio frenado (km/h):",
        lblTechDescentDamping: "Amortiguación bajada técnica:",
        lblSmoothRadius1: "Radio Suavizado 1 (m):",
        lblSmoothRadius2: "Radio Suavizado 2 (m):",

        // Métricas
        metricTime: "Tiempo Total",
        metricDist: "Distancia",
        metricSpeed: "Velocidad Media",
        metricElev: "Desnivel Positivo",
        metricPower: "Potencia Media",
        metricNP: "Potencia Normalizada (NP)",
        metricEnergy: "Energía Total",
        metricTSS: "Carga (TSS)",

        // Sincronizador
        syncLabel: "Selector de Kilómetro (Sincronizador maestro):",
        syncDefault: "Sube una ruta y simula para ver el detalle por kilómetro.",

        // Tabla
        tableTitle: "Resumen Comparativo: Puertos y Tramos (Simulado vs Real)",
        thRoute: "Puerto / Tramo",
        thStart: "Inicio (km)",
        thDist: "Distancia",
        thElev: "Desnivel",
        thSlope: "Pendiente",
        thSimTime: "Tiempo Sim.",
        thRealTime: "Tiempo Real",
        thSimSpeed: "Vel. Sim.",
        thRealSpeed: "Vel. Real",
        thSimPower: "Pot. Sim.",
        thRealPower: "Pot. Real",
        tableEmpty: "Cargue una ruta para ver el resumen de puertos.",
        repecho: "Repecho",
        puerto3: "Puerto 3ª",
        puerto2: "Puerto 2ª",
        puerto1: "Puerto 1ª",
        horsCat: "Hors Catégorie",

        // Textos de JS / Gráficos / Alertas
        alertNoFile: "Selecciona un archivo .fit o .gpx",
        btnSimulating: "Simulando física...",
        btnSimulate: "Simular Ruta",
        alertSelectExample: "Por favor, selecciona una ruta de ejemplo.",
        alertExampleSuccess: "¡Ruta '{filename}' cargada con éxito! Pulsa en 'Simular Ruta' para ver los resultados.",
        
        // Títulos de gráficos y ejes
        mapTitle: "MAPA DE LA RUTA",
        mapAxisLon: "Longitud",
        mapAxisLat: "Latitud",
        
        elevationTitle: "PERFIL DE ELEVACIÓN Y PUERTOS",
        elevationXAxis: "Distancia Acumulada (km)",
        elevationYAxis: "Altitud (m)",
        
        combinedTitle: "DINÁMICA DE RUTA: POTENCIA, VELOCIDAD Y PERFIL",
        combinedPowerAxis: "Potencia (W)",
        combinedSpeedAxis: "Velocidad (km/h)",
        
        fatigueTitle: "EVOLUCIÓN DE LA FATIGA: FTP EFECTIVO Y ENERGÍA",
        fatigueYAxis: "FTP Efectivo (W)",
        fatigueEnergyAxis: "Energía (kJ)",
        
        wprimeTitle: "CAPACIDAD ANAERÓBICA: W' DISPONIBLE (%)",
        
        noClimbsFound: "No se han detectado puertos o tramos significativos en esta ruta.",
        loadClimbsPrompt: "Cargue una ruta para ver el resumen de puertos."
    },
    en: {
        title: "Hors Catégorie - Cycling Route Simulator",
        headerSubtitle: "Cycling Physics Simulator & Advanced Telemetric Analysis",
        sidebarTitle: "Simulation Parameters",
        fileLabel: "Route File (.fit / .gpx):",
        noFileYet: "No file? Try an example:",
        loadExampleBtn: "Load",
        selectExample: "-- Select example route --",
        simulateBtn: "Run Simulation",
        simulatingBtn: "Simulating physics...",
        fs1: "1. Cyclist & Physiology",
        fs2: "2. Aerodynamics & Drag",
        fs3: "3. Power Strategy",
        fs4: "4. Descent Control & Limits",
        fs5: "5. Route Smoothing Parameters",
        lblWeightKg: "Rider Weight (kg):",
        lblBikeWeightKg: "Bike Weight (kg):",
        lblFtpWatts: "FTP (W):",
        lblIntensityFactor: "Intensity Factor (IF):",
        lblWPrimeKj: "W' Capacity (kJ):",
        lblFatigueRate: "Fatigue per 1,000 kJ (%):",
        lblCdaSeated: "CdA Seated:",
        lblCdaStanding: "CdA Standing:",
        lblRollingResistance: "Rolling Resistance (Cr):",
        lblClimbThreshold: "Min. Climb Gradient (%):",
        lblDescentThreshold: "Min. Descent Gradient (%):",
        lblDescentPower: "Steep Descent Power (W):",
        lblFalseFlatPower: "False Flat Power Factor:",
        lblExhaustedPower: "Depleted W' Multiplier:",
        lblMaxDescentSpeed: "Max Descent Speed (km/h):",
        lblBrakingFactor: "Cornering Braking Factor:",
        lblBrakingThreshold: "Braking Start Threshold (km/h):",
        lblTechDescentDamping: "Technical Descent Damping:",
        lblSmoothRadius1: "Smoothing Radius 1 (m):",
        lblSmoothRadius2: "Smoothing Radius 2 (m):",
        metricTime: "Total Time",
        metricDist: "Distance",
        metricSpeed: "Average Speed",
        metricElev: "Elevation Gain",
        metricPower: "Average Power",
        metricNP: "Normalized Power (NP)",
        metricEnergy: "Total Energy",
        metricTSS: "Training Stress (TSS)",
        syncLabel: "Kilometer Selector (Master Sync):",
        syncDefault: "Upload a route and run simulation to see details per kilometer.",
        tableTitle: "Comparative Summary: Climbs & Segments (Simulated vs Real)",
        thRoute: "Climb / Segment",
        thStart: "Start (km)",
        thDist: "Distance",
        thElev: "Elevation",
        thSlope: "Gradient",
        thSimTime: "Sim Time",
        thRealTime: "Real Time",
        thSimSpeed: "Sim Speed",
        thRealSpeed: "Real Speed",
        thSimPower: "Sim Power",
        thRealPower: "Real Power",
        tableEmpty: "Load a route to view the climbs summary.",
        repecho: "Short Climb",
        puerto3: "Cat. 3 Climb",
        puerto2: "Cat. 2 Climb",
        puerto1: "Cat. 1 Climb",
        horsCat: "Hors Catégorie",

        alertNoFile: "Please select a .fit or .gpx file",
        btnSimulating: "Simulating physics...",
        btnSimulate: "Run Simulation",
        alertSelectExample: "Please select an example route.",
        alertExampleSuccess: "Route '{filename}' loaded successfully! Click 'Run Simulation' to view results.",
        
        mapTitle: "ROUTE MAP",
        mapAxisLon: "Longitude",
        mapAxisLat: "Latitude",
        
        elevationTitle: "ELEVATION PROFILE & CLIMBS",
        elevationXAxis: "Cumulative Distance (km)",
        elevationYAxis: "Altitude (m)",
        
        combinedTitle: "ROUTE DYNAMICS: POWER, SPEED & PROFILE",
        combinedPowerAxis: "Power (W)",
        combinedSpeedAxis: "Speed (km/h)",
        
        fatigueTitle: "FATIGUE EVOLUTION: EFFECTIVE FTP & ENERGY",
        fatigueYAxis: "Effective FTP (W)",
        fatigueEnergyAxis: "Energy (kJ)",
        
        wprimeTitle: "ANAEROBIC CAPACITY: AVAILABLE W' (%)",
        
        noClimbsFound: "No significant climbs or segments detected in this route.",
        loadClimbsPrompt: "Load a route to view the climbs summary."
    },
    fr: {
        title: "Hors Catégorie - Simulateur de Parcours Cyclistes",
        headerSubtitle: "Simulateur de Physique Cycliste & Analyse Télémétrique Avancée",
        sidebarTitle: "Paramètres de Simulation",
        fileLabel: "Fichier d'itinéraire (.fit / .gpx):",
        noFileYet: "Pas de fichier ? Essayez un exemple :",
        loadExampleBtn: "Charger",
        selectExample: "-- Sélectionnez un exemple --",
        simulateBtn: "Simuler l'itinéraire",
        simulatingBtn: "Simulation en cours...",
        fs1: "1. Cycliste & Physiologie",
        fs2: "2. Aérodynamisme & Résistance",
        fs3: "3. Stratégie de Puissance",
        fs4: "4. Contrôle des Descentes & Limites",
        fs5: "5. Paramètres de Lissage d'Itinéraire",
        lblWeightKg: "Poids Cycliste (kg) :",
        lblBikeWeightKg: "Poids Vélo (kg) :",
        lblFtpWatts: "FTP (W) :",
        lblIntensityFactor: "Facteur d'Intensité (IF) :",
        lblWPrimeKj: "Capacité W' (kJ) :",
        lblFatigueRate: "Fatigue par 1 000 kJ (%) :",
        lblCdaSeated: "CdA Assis :",
        lblCdaStanding: "CdA Debout :",
        lblRollingResistance: "Résistance au Roulement (Cr) :",
        lblClimbThreshold: "Pente Min. Montée (%) :",
        lblDescentThreshold: "Pente Min. Descente (%) :",
        lblDescentPower: "Puissance Descente Raide (W) :",
        lblFalseFlatPower: "Facteur Puissance Faux Plat :",
        lblExhaustedPower: "Multiplicateur W' Épuisé :",
        lblMaxDescentSpeed: "Vitesse Max Descente (km/h) :",
        lblBrakingFactor: "Facteur Freinage Virage :",
        lblBrakingThreshold: "Seuil Début Freinage (km/h) :",
        lblTechDescentDamping: "Amortissement Descente Technique :",
        lblSmoothRadius1: "Rayon de Lissage 1 (m) :",
        lblSmoothRadius2: "Rayon de Lissage 2 (m) :",
        metricTime: "Temps Total",
        metricDist: "Distance",
        metricSpeed: "Vitesse Moyenne",
        metricElev: "Dénivelé Positif",
        metricPower: "Puissance Moyenne",
        metricNP: "Puissance Normalisée (NP)",
        metricEnergy: "Énergie Totale",
        metricTSS: "Charge (TSS)",
        syncLabel: "Sélecteur de Kilomètre (Synchro maître) :",
        syncDefault: "Téléchargez un parcours et simulez pour voir les détails par kilomètre.",
        tableTitle: "Résumé Comparatif : Cols & Sections (Simulé vs Réel)",
        thRoute: "Col / Section",
        thStart: "Début (km)",
        thDist: "Distance",
        thElev: "Dénivelé",
        thSlope: "Pente",
        thSimTime: "Temps Sim.",
        thRealTime: "Temps Réel",
        thSimSpeed: "Vit. Sim.",
        thRealSpeed: "Vit. Réelle",
        thSimPower: "Puis. Sim.",
        thRealPower: "Puis. Réelle",
        tableEmpty: "Chargez un parcours pour afficher le résumé des cols.",
        repecho: "Côte",
        puerto3: "Col de 3e cat.",
        puerto2: "Col de 2e cat.",
        puerto1: "Col de 1re cat.",
        horsCat: "Hors Catégorie",

        alertNoFile: "Veuillez sélectionner un fichier .fit ou .gpx",
        btnSimulating: "Simulation en cours...",
        btnSimulate: "Simuler l'itinéraire",
        alertSelectExample: "Veuillez sélectionner un exemple de parcours.",
        alertExampleSuccess: "Parcours '{filename}' chargé avec succès ! Cliquez sur 'Simuler l'itinéraire' pour voir les résultats.",
        
        mapTitle: "CARTE DU PARCOURS",
        mapAxisLon: "Longitude",
        mapAxisLat: "Latitude",
        
        elevationTitle: "PROFIL D'ELEVATION & COLS",
        elevationXAxis: "Distance Cumulée (km)",
        elevationYAxis: "Altitude (m)",
        
        combinedTitle: "DYNAMIQUE DU PARCOURS : PUISSANCE, VITESSE & PROFIL",
        combinedPowerAxis: "Puissance (W)",
        combinedSpeedAxis: "Vitesse (km/h)",
        
        fatigueTitle: "ÉVOLUTION DE LA FATIGUE : FTP EFFECTIVE & ÉNERGIE",
        fatigueYAxis: "FTP Effective (W)",
        fatigueEnergyAxis: "Énergie (kJ)",
        
        wprimeTitle: "CAPACITÉ ANAÉROBIE : W' DISPONIBLE (%)",
        
        noClimbsFound: "Aucun col ou section significative détecté sur ce parcours.",
        loadClimbsPrompt: "Chargez un parcours pour afficher le résumé des cols."
    }

};

function t(key, params = {}) {
    let text = translations[currentLang]?.[key] || translations['es']?.[key] || key;
    Object.keys(params).forEach(param => {
        text = text.replace(new RegExp(`{${param}}`, 'g'), params[param]);
    });
    return text;
}

function setLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('app_lang', lang);
    const dictionary = translations[lang];

    if (!dictionary) return;

    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (dictionary[key]) {
            el.innerText = dictionary[key];
        }
    });

    const langSelector = document.getElementById('language-selector');
    if (langSelector && langSelector.value !== lang) {
        langSelector.value = lang;
    }

    if (window.simulationDataCache) {
        renderDashboard(window.simulationDataCache);
        renderClimbsSummaryTable(window.simulationDataCache.simulation, window.simulationDataCache.telemetry_records);
    }
}