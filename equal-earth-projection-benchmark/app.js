(() => {
  "use strict";

  const WIDTH = 960;
  const HEIGHT = 520;
  const MARGIN = 12;
  const MODAL_PANEL = 300; // matches the modal SVG viewBox

  // ---------------------------------------------------------------------
  // Raw projections (radians in, planar units out). No d3-geo-projection
  // dependency: both formulas are implemented directly so the blend below
  // is a plain linear interpolation between two known-good raw functions.
  // ---------------------------------------------------------------------

  // Web Mercator, latitude clamped to avoid the pole singularity.
  const MERCATOR_MAX_PHI = (89 * Math.PI) / 180;
  function mercatorRaw(lambda, phi) {
    const p = Math.max(-MERCATOR_MAX_PHI, Math.min(MERCATOR_MAX_PHI, phi));
    return [lambda, Math.log(Math.tan(Math.PI / 4 + p / 2))];
  }

  // Equal Earth (Savric, Jenny & Jenny, 2018).
  const EE_A1 = 1.340264, EE_A2 = -0.081106, EE_A3 = 0.000893, EE_A4 = 0.003796;
  const EE_M = Math.sqrt(3) / 2;
  function equalEarthRaw(lambda, phi) {
    const theta = Math.asin(EE_M * Math.sin(phi));
    const theta2 = theta * theta;
    const theta6 = theta2 * theta2 * theta2;
    const x = (lambda * Math.cos(theta)) / (EE_M * (EE_A1 + 3 * EE_A2 * theta2 + theta6 * (7 * EE_A3 + 9 * EE_A4 * theta2)));
    const y = theta * (EE_A1 + EE_A2 * theta2 + theta6 * (EE_A3 + EE_A4 * theta2));
    return [x, y];
  }

  function blendedRaw(t) {
    return (lambda, phi) => {
      const [mx, my] = mercatorRaw(lambda, phi);
      const [ex, ey] = equalEarthRaw(lambda, phi);
      return [mx + (ex - mx) * t, my + (ey - my) * t];
    };
  }

  // ---------------------------------------------------------------------
  // Map layers. Each is a single-hue sequential ramp (dataviz skill), with
  // separate light/dark steps validated with validate_palette.js --ordinal
  // (both clear the adjacent-ΔL gate and the light-end contrast floor).
  // ---------------------------------------------------------------------
  const PREFERS_DARK = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;

  const LAYERS = [
    {
      id: "population",
      label: "Population density",
      unit: "people / km²",
      bounds: [10, 25, 50, 100, 300, 1000],
      colorsLight: ["#6cb4ff", "#559cf1", "#3d85d7", "#246ebe", "#0257a6", "#00418e", "#002a76"],
      colorsDark: ["#a7cefe", "#91b8e7", "#7ca2d0", "#688dba", "#5478a4", "#41648e", "#2e5079"],
      binLabels: ["< 10", "10–25", "25–50", "50–100", "100–300", "300–1,000", "≥ 1,000"],
      seriesKey: "population_series",
      globalSeriesKey: "global_population_series",
      currentKey: "pop_density",
      rankKey: "rank_density",
      rankCountKey: "countries_with_density_data",
      needsAreaDivision: true,
      format: (v) => `${v.toFixed(1)} / km²`,
      chartFormat: (v) => formatCompact(v),
    },
    {
      id: "forest",
      label: "Forest cover",
      unit: "% of land area",
      bounds: [10, 25, 40, 55, 70, 85],
      colorsLight: ["#57bd72", "#3fa75e", "#249249", "#007d35", "#006821", "#00540a", "#004000"],
      colorsDark: ["#8cf2a4", "#75da8d", "#5dc377", "#44ac62", "#29954d", "#007f38", "#006a23"],
      binLabels: ["< 10%", "10–25%", "25–40%", "40–55%", "55–70%", "70–85%", "≥ 85%"],
      seriesKey: "forest_series",
      globalSeriesKey: "global_forest_series",
      currentKey: "forest_current",
      rankKey: "rank_forest",
      rankCountKey: "countries_with_forest_data",
      needsAreaDivision: false,
      format: (v) => `${v.toFixed(1)}%`,
      chartFormat: (v) => `${v.toFixed(1)}%`,
    },
    {
      id: "co2",
      label: "CO₂ emissions",
      unit: "t CO₂e / person",
      bounds: [1, 2, 4, 8, 12, 20],
      colorsLight: ["#ff8982", "#e6726b", "#cc5b55", "#b24340", "#992b2b", "#800f16", "#670001"],
      colorsDark: ["#fbb7b0", "#e3a19b", "#cc8c86", "#b67771", "#9f635e", "#8a4f4a", "#743c38"],
      binLabels: ["< 1", "1–2", "2–4", "4–8", "8–12", "12–20", "≥ 20"],
      seriesKey: "co2_series",
      globalSeriesKey: "global_co2_series",
      currentKey: "co2_current",
      rankKey: "rank_co2",
      rankCountKey: "countries_with_co2_data",
      needsAreaDivision: false,
      format: (v) => `${v.toFixed(2)} t/person`,
      chartFormat: (v) => `${v.toFixed(2)} t`,
    },
    {
      id: "urban",
      label: "Urbanization",
      unit: "% urban population",
      bounds: [20, 40, 55, 70, 85, 95],
      colorsLight: ["#b0a0ff", "#9a88ec", "#8371d3", "#6e5aba", "#5944a2", "#462e8a", "#341672"],
      colorsDark: ["#d6c6ff", "#bfafff", "#a998fe", "#9482e6", "#7e6ccd", "#6a57b6", "#57419e"],
      binLabels: ["< 20%", "20–40%", "40–55%", "55–70%", "70–85%", "85–95%", "≥ 95%"],
      seriesKey: "urban_series",
      globalSeriesKey: "global_urban_series",
      currentKey: "urban_current",
      rankKey: "rank_urban",
      rankCountKey: "countries_with_urban_data",
      needsAreaDivision: false,
      format: (v) => `${v.toFixed(1)}%`,
      chartFormat: (v) => `${v.toFixed(1)}%`,
    },
  ];
  const LAYERS_BY_ID = new Map(LAYERS.map((l) => [l.id, l]));

  function colorScaleFor(layer) {
    return d3.scaleThreshold().domain(layer.bounds).range(PREFERS_DARK ? layer.colorsDark : layer.colorsLight);
  }

  // ---------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------
  let worldData = null;
  let endpoints = null; // {scale0, translate0, scale1, translate1}
  let projMercFixed = null, projEqualFixed = null; // world-fit endpoint projections (fixed)
  let pathMercFixed = null, pathEqualFixed = null;
  let currentPath = null;
  let selectedFeature = null;
  let zoomBehavior = null;
  let seriesByFeature = null; // Map<feature, Map<layerId, Map<year, value>>>
  let activeLayer = LAYERS[0];
  let yearMin = 1960, yearMax = 1960;
  let currentYear = 1960;
  let playTimer = null;
  let globalChartX = null, globalChartY = null; // for the year marker on the global chart

  const svg = d3.select("#map");
  const zoomLayer = svg.append("g").attr("class", "zoom-layer");
  const sphere = zoomLayer.append("path").attr("class", "sphere");
  const graticule = zoomLayer.append("path").attr("class", "graticule");
  const countriesLayer = zoomLayer.append("g").attr("class", "countries-layer");
  const graticuleLines = d3.geoGraticule()();
  const tooltip = d3.select("#tooltip");
  const mapWrap = document.querySelector(".map-wrap");

  const blendInput = document.getElementById("blend");
  const blendReadout = document.getElementById("blend-readout");
  const searchInput = document.getElementById("search");
  const countryList = document.getElementById("country-list");
  const clearSelectionBtn = document.getElementById("clear-selection");
  const modalBackdrop = document.getElementById("modal-backdrop");
  const yearInput = document.getElementById("year");
  const yearReadout = document.getElementById("year-readout");
  const playBtn = document.getElementById("play-btn");
  const legendTitle = document.getElementById("legend-title");
  const modalClose = document.getElementById("modal-close");
  const layerTabs = document.getElementById("layer-tabs");

  function fitProjection(rawFn, data) {
    const proj = d3.geoProjection(rawFn).precision(0.2);
    proj.fitExtent([[MARGIN, MARGIN], [WIDTH - MARGIN, HEIGHT - MARGIN]], data);
    return proj;
  }

  function computeEndpoints(data) {
    projMercFixed = fitProjection(mercatorRaw, data);
    projEqualFixed = fitProjection(equalEarthRaw, data);
    pathMercFixed = d3.geoPath(projMercFixed);
    pathEqualFixed = d3.geoPath(projEqualFixed);
    endpoints = {
      scale0: projMercFixed.scale(),
      translate0: projMercFixed.translate(),
      scale1: projEqualFixed.scale(),
      translate1: projEqualFixed.translate(),
    };
  }

  function buildProjection(t) {
    const scale = endpoints.scale0 + (endpoints.scale1 - endpoints.scale0) * t;
    const translate = [
      endpoints.translate0[0] + (endpoints.translate1[0] - endpoints.translate0[0]) * t,
      endpoints.translate0[1] + (endpoints.translate1[1] - endpoints.translate0[1]) * t,
    ];
    return d3.geoProjection(blendedRaw(t)).scale(scale).translate(translate).precision(0.2);
  }

  function formatInt(n) {
    return n === null || n === undefined || Number.isNaN(n) ? null : Math.round(n).toLocaleString("en-US");
  }

  function formatCompact(v) {
    if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
    if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
    return String(Math.round(v));
  }

  function render(t) {
    const projection = buildProjection(t);
    currentPath = d3.geoPath(projection);
    sphere.attr("d", currentPath({ type: "Sphere" }));
    graticule.attr("d", currentPath(graticuleLines));
    countriesLayer.selectAll("path.country").attr("d", currentPath);
    blendReadout.textContent = `${Math.round(t * 100)}% Equal Earth`;
  }

  // ---------------------------------------------------------------------
  // Time-series choropleth: the map itself animates, not just a side chart.
  // ---------------------------------------------------------------------
  function rawSeriesValue(feature, layer, year) {
    const perLayer = seriesByFeature.get(feature);
    const yearMap = perLayer ? perLayer.get(layer.id) : null;
    const v = yearMap ? yearMap.get(year) : undefined;
    return v === undefined ? null : v;
  }

  function mapValueForYear(feature, layer, year) {
    const raw = rawSeriesValue(feature, layer, year);
    if (raw === null) return null;
    if (layer.needsAreaDivision) {
      const area = feature.properties.area_km2;
      return area ? raw / area : null;
    }
    return raw;
  }

  function setActiveLayer(layerId) {
    activeLayer = LAYERS_BY_ID.get(layerId);
    layerTabs.querySelectorAll(".layer-tab").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.layer === layerId);
    });

    const globalSeries = worldData.meta[activeLayer.globalSeriesKey] || [];
    yearMin = globalSeries.length ? globalSeries[0][0] : 1960;
    yearMax = globalSeries.length ? globalSeries[globalSeries.length - 1][0] : 1960;
    currentYear = Math.max(yearMin, Math.min(yearMax, currentYear));
    yearInput.min = yearMin;
    yearInput.max = yearMax;

    buildLegend();
    document.getElementById("global-trend-title").textContent = `Global ${activeLayer.label.toLowerCase()}, ${yearMin}–present`;
    renderTrendChart({
      svgId: "global-trend-chart",
      tooltipId: "global-trend-tooltip",
      readoutId: "global-trend-readout",
      series: globalSeries,
      layer: activeLayer,
    });

    if (selectedFeature) openModal(selectedFeature);
    updateChoropleth(currentYear);
  }

  function updateChoropleth(year) {
    currentYear = year;
    const colorScale = colorScaleFor(activeLayer);
    countriesLayer
      .selectAll("path.country")
      .style("fill", (d) => {
        const value = mapValueForYear(d, activeLayer, year);
        return value !== null ? colorScale(value) : "var(--country-fill)";
      });
    yearInput.value = year;
    yearReadout.textContent = String(year);
    legendTitle.textContent = `${activeLayer.label} in ${year} (${activeLayer.unit})`;
    updateGlobalChartMarker(year);
  }

  function updateGlobalChartMarker(year) {
    if (!globalChartX) return;
    const svgSel = d3.select("#global-trend-chart");
    const px = globalChartX(year);
    let marker = svgSel.select(".year-marker");
    if (marker.empty()) {
      marker = svgSel.append("line").attr("class", "year-marker chart-hover-line").style("stroke-dasharray", "none").style("opacity", 1);
    }
    marker.attr("x1", px).attr("x2", px).attr("y1", globalChartY.range()[1]).attr("y2", globalChartY.range()[0]);
  }

  function stopPlayback() {
    if (playTimer) {
      clearInterval(playTimer);
      playTimer = null;
    }
    playBtn.textContent = "▶";
    playBtn.classList.remove("playing");
    playBtn.setAttribute("aria-label", "Play");
  }

  function togglePlayback() {
    if (playTimer) {
      stopPlayback();
      return;
    }
    playBtn.textContent = "⏸";
    playBtn.classList.add("playing");
    playBtn.setAttribute("aria-label", "Pause");
    playTimer = setInterval(() => {
      let next = currentYear + 1;
      if (next > yearMax) next = yearMin;
      updateChoropleth(next);
    }, 180);
  }

  function buildLegend() {
    const legend = d3.select("#legend");
    legend.selectAll(".legend-row").remove();
    activeLayer.colorsLight.forEach((_, i) => {
      const color = (PREFERS_DARK ? activeLayer.colorsDark : activeLayer.colorsLight)[i];
      const row = legend.append("div").attr("class", "legend-row");
      row.append("div").attr("class", "legend-swatch").style("background", color);
      row.append("span").text(activeLayer.binLabels[i]);
    });
  }

  // ---------------------------------------------------------------------
  // Reusable time-series line chart (global banner + modal)
  // ---------------------------------------------------------------------
  function renderTrendChart({ svgId, tooltipId, readoutId, series, layer }) {
    const svgSel = d3.select(`#${svgId}`);
    svgSel.selectAll("*").remove();
    if (!series || series.length < 2) {
      svgSel.append("text").attr("x", 12).attr("y", 20).attr("fill", "var(--text-muted)").style("font-size", "11px").text("No time series available.");
      const readoutSel = readoutId ? d3.select(`#${readoutId}`) : null;
      if (readoutSel) readoutSel.text("");
      return;
    }
    const fmt = layer.chartFormat;

    const viewBox = svgSel.attr("viewBox").split(" ").map(Number);
    const width = viewBox[2], height = viewBox[3];
    const margin = { top: 10, right: 10, bottom: 20, left: 46 };

    const x = d3.scaleLinear().domain(d3.extent(series, (d) => d[0])).range([margin.left, width - margin.right]);
    const yExtent = d3.extent(series, (d) => d[1]);
    const yDomain = layer.needsAreaDivision || yExtent[0] >= 0 ? [0, yExtent[1] * 1.08] : yExtent;
    const y = d3.scaleLinear().domain(yDomain).nice().range([height - margin.bottom, margin.top]);

    if (svgId === "global-trend-chart") {
      globalChartX = x;
      globalChartY = y;
    }

    const yTicks = y.ticks(4);
    svgSel.append("g").selectAll("line").data(yTicks).join("line")
      .attr("class", "chart-gridline")
      .attr("x1", margin.left).attr("x2", width - margin.right)
      .attr("y1", (d) => y(d)).attr("y2", (d) => y(d));

    svgSel.append("g")
      .attr("class", "chart-axis")
      .attr("transform", `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(4).tickFormat(fmt).tickSize(0))
      .call((g) => g.select(".domain").remove());

    svgSel.append("g")
      .attr("class", "chart-axis")
      .attr("transform", `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x).ticks(Math.min(series.length, 8)).tickFormat(d3.format("d")).tickSize(0));

    const line = d3.line().x((d) => x(d[0])).y((d) => y(d[1]));
    svgSel.append("path").datum(series).attr("class", "chart-line").attr("d", line);

    const hoverLine = svgSel.append("line").attr("class", "chart-hover-line").attr("y1", margin.top).attr("y2", height - margin.bottom).style("opacity", 0);
    const hoverDot = svgSel.append("circle").attr("class", "chart-hover-dot").attr("r", 3.5).style("opacity", 0);
    const tooltipSel = d3.select(`#${tooltipId}`);
    const readoutSel = readoutId ? d3.select(`#${readoutId}`) : null;
    const bisect = d3.bisector((d) => d[0]).left;

    if (readoutSel) {
      const first = series[0], last = series[series.length - 1];
      const pctChange = first[1] > 0 ? ((last[1] - first[1]) / first[1]) * 100 : null;
      readoutSel.text(pctChange !== null ? `${fmt(last[1])} in ${last[0]} (${pctChange >= 0 ? "+" : ""}${pctChange.toFixed(0)}% since ${first[0]})` : `${fmt(last[1])} in ${last[0]}`);
    }

    svgSel.append("rect")
      .attr("x", margin.left).attr("y", margin.top)
      .attr("width", Math.max(width - margin.left - margin.right, 0))
      .attr("height", Math.max(height - margin.top - margin.bottom, 0))
      .attr("fill", "transparent")
      .on("mousemove", function (evt) {
        const [mx] = d3.pointer(evt, this);
        const year = Math.round(x.invert(mx));
        let i = bisect(series, year);
        i = Math.max(0, Math.min(series.length - 1, i));
        const point = series[i];
        const px = x(point[0]), py = y(point[1]);
        hoverLine.attr("x1", px).attr("x2", px).style("opacity", 1);
        hoverDot.attr("cx", px).attr("cy", py).style("opacity", 1);
        const rect = svgSel.node().getBoundingClientRect();
        const scaleX = rect.width / width, scaleY = rect.height / height;
        tooltipSel
          .classed("visible", true)
          .style("left", `${px * scaleX}px`)
          .style("top", `${py * scaleY}px`)
          .text(`${point[0]}: ${fmt(point[1])}`);
      })
      .on("mouseleave", () => {
        hoverLine.style("opacity", 0);
        hoverDot.style("opacity", 0);
        tooltipSel.classed("visible", false);
      });
  }

  // ---------------------------------------------------------------------
  // Per-country side-by-side comparison modal
  // ---------------------------------------------------------------------

  // Renders `feature` into a small modal SVG, using projection/path `proj`,
  // scaled by the shared `zoom` factor so the two panels are comparable.
  function renderModalPanel(svgId, feature, path, zoom) {
    const svgSel = d3.select(`#${svgId}`);
    svgSel.selectAll("*").remove();
    const [[x0, y0], [x1, y1]] = path.bounds(feature);
    const cx = (x0 + x1) / 2;
    const cy = (y0 + y1) / 2;
    const g = svgSel.append("g").attr(
      "transform",
      `translate(${MODAL_PANEL / 2}, ${MODAL_PANEL / 2}) scale(${zoom}) translate(${-cx}, ${-cy})`
    );
    g.append("path")
      .attr("d", path(feature))
      .attr("stroke-width", 0.5 / zoom)
      .style("fill", "var(--accent)")
      .style("stroke", "var(--surface-1)");
  }

  // Rendered on-screen area share vs. this feature's true geometric share of
  // the whole rendered world -- always ~1x for the Equal Earth panel by
  // construction (it's an equal-area projection), so it's an honest baseline
  // for how much Mercator inflates/shrinks a given country by comparison.
  function distortionFor(feature, path) {
    const trueShare = feature.properties.geom_area_km2 / worldData.meta.total_rendered_land_area_km2;
    const worldArea = Math.abs(path.area(worldData));
    const screenShare = worldArea > 0 ? Math.abs(path.area(feature)) / worldArea : 0;
    return trueShare > 0 ? screenShare / trueShare : null;
  }

  function distortionLabel(distortion) {
    if (distortion === null || !isFinite(distortion) || distortion <= 0) return "—";
    if (distortion > 1.05) return `<strong>${distortion.toFixed(1)}×</strong> larger than true size`;
    if (distortion < 0.95) return `<strong>${(1 / distortion).toFixed(1)}×</strong> smaller than true size`;
    return "true relative size";
  }

  function openModal(feature) {
    const p = feature.properties;
    document.getElementById("modal-title").textContent = p.name;

    const boundsM = pathMercFixed.bounds(feature);
    const boundsE = pathEqualFixed.bounds(feature);
    const maxDim = Math.max(
      boundsM[1][0] - boundsM[0][0], boundsM[1][1] - boundsM[0][1],
      boundsE[1][0] - boundsE[0][0], boundsE[1][1] - boundsE[0][1],
      1e-6
    );
    const zoom = (MODAL_PANEL * 0.75) / maxDim;

    renderModalPanel("modal-svg-mercator", feature, pathMercFixed, zoom);
    renderModalPanel("modal-svg-equalearth", feature, pathEqualFixed, zoom);

    document.getElementById("modal-stat-mercator").innerHTML = distortionLabel(distortionFor(feature, pathMercFixed));
    document.getElementById("modal-stat-equalearth").innerHTML = distortionLabel(distortionFor(feature, pathEqualFixed));

    const totalArea = worldData.meta.countries_with_area_data;
    const totalPop = worldData.meta.countries_with_population_data;
    const totalDensity = worldData.meta.countries_with_density_data;

    document.getElementById("stat-population").textContent = formatInt(p.population) || "Data unavailable";
    document.getElementById("stat-population-rank").textContent = p.rank_pop ? `#${p.rank_pop} of ${totalPop} by population` : "";
    document.getElementById("stat-area").textContent = p.area_km2 !== null ? `${formatInt(p.area_km2)} km²` : "Data unavailable";
    document.getElementById("stat-area-rank").textContent = p.rank_area ? `#${p.rank_area} of ${totalArea} by area` : "";
    document.getElementById("stat-density").textContent = p.pop_density !== null ? `${p.pop_density.toFixed(1)} / km²` : "Data unavailable";
    document.getElementById("stat-density-rank").textContent = p.rank_density ? `#${p.rank_density} of ${totalDensity} by density` : "";

    const layerStatTile = document.getElementById("stat-layer-tile");
    if (activeLayer.id === "population") {
      layerStatTile.hidden = true;
    } else {
      layerStatTile.hidden = false;
      const val = p[activeLayer.currentKey];
      const rank = p[activeLayer.rankKey];
      const rankTotal = worldData.meta[activeLayer.rankCountKey];
      document.getElementById("stat-layer-label").textContent = activeLayer.label;
      document.getElementById("stat-layer-value").textContent = val !== null && val !== undefined ? activeLayer.format(val) : "Data unavailable";
      document.getElementById("stat-layer-rank").textContent = rank ? `#${rank} of ${rankTotal} by ${activeLayer.label.toLowerCase()}` : "";
    }

    document.getElementById("modal-trend-title").textContent = `${p.name}: ${activeLayer.label.toLowerCase()}, ${yearMin}–present`;
    renderTrendChart({
      svgId: "modal-trend-chart",
      tooltipId: "modal-trend-tooltip",
      readoutId: "modal-trend-readout",
      series: p[activeLayer.seriesKey],
      layer: activeLayer,
    });

    modalBackdrop.hidden = false;
  }

  function closeModal() {
    modalBackdrop.hidden = true;
  }

  function selectCountry(feature) {
    selectedFeature = feature;
    countriesLayer.selectAll("path.country").classed("selected", (d) => d === feature);
    countriesLayer.selectAll("path.country.selected").raise();
    clearSelectionBtn.hidden = false;
    openModal(feature);
  }

  function clearSelection() {
    selectedFeature = null;
    countriesLayer.selectAll("path.country").classed("selected", false);
    clearSelectionBtn.hidden = true;
    searchInput.value = "";
    closeModal();
  }

  function findCountryByName(query) {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    const exact = worldData.features.find((f) => f.properties.name.toLowerCase() === q);
    if (exact) return exact;
    return worldData.features.find((f) => f.properties.name.toLowerCase().startsWith(q)) || null;
  }

  function wireControls() {
    blendInput.addEventListener("input", () => render(parseFloat(blendInput.value)));

    modalClose.addEventListener("click", closeModal);
    modalBackdrop.addEventListener("click", (evt) => {
      if (evt.target === modalBackdrop) closeModal();
    });
    document.addEventListener("keydown", (evt) => {
      if (evt.key === "Escape" && !modalBackdrop.hidden) closeModal();
    });

    clearSelectionBtn.addEventListener("click", clearSelection);

    searchInput.addEventListener("change", () => {
      const feature = findCountryByName(searchInput.value);
      if (feature) selectCountry(feature);
    });
    searchInput.addEventListener("keydown", (evt) => {
      if (evt.key === "Enter") {
        const feature = findCountryByName(searchInput.value);
        if (feature) selectCountry(feature);
      }
    });

    zoomBehavior = d3.zoom().scaleExtent([1, 12]).on("zoom", (evt) => {
      zoomLayer.attr("transform", evt.transform);
    });
    svg.call(zoomBehavior);

    yearInput.addEventListener("input", () => {
      stopPlayback();
      updateChoropleth(parseInt(yearInput.value, 10));
    });
    playBtn.addEventListener("click", togglePlayback);

    layerTabs.querySelectorAll(".layer-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        stopPlayback();
        setActiveLayer(btn.dataset.layer);
      });
    });
  }

  function populateSearchList() {
    const names = worldData.features.map((f) => f.properties.name).sort((a, b) => a.localeCompare(b));
    countryList.innerHTML = names.map((n) => `<option value="${n}"></option>`).join("");
  }

  async function init() {
    if (window.__WORLD_DATA__) {
      worldData = window.__WORLD_DATA__;
    } else {
      const res = await fetch("data/world.json");
      worldData = await res.json();
    }

    computeEndpoints(worldData);
    populateSearchList();

    seriesByFeature = new Map();
    worldData.features.forEach((f) => {
      const perLayer = new Map();
      LAYERS.forEach((layer) => {
        perLayer.set(layer.id, new Map(f.properties[layer.seriesKey] || []));
      });
      seriesByFeature.set(f, perLayer);
    });

    countriesLayer
      .selectAll("path.country")
      .data(worldData.features, (d) => d.properties.name)
      .join("path")
      .attr("class", "country")
      .on("mousemove", (evt, d) => {
        const rect = mapWrap.getBoundingClientRect();
        const value = mapValueForYear(d, activeLayer, currentYear);
        tooltip
          .classed("visible", true)
          .style("left", `${evt.clientX - rect.left}px`)
          .style("top", `${evt.clientY - rect.top}px`)
          .html(`<strong>${d.properties.name}</strong>${value !== null ? ` — ${activeLayer.format(value)} (${currentYear})` : ""}`);
      })
      .on("mouseleave", () => tooltip.classed("visible", false))
      .on("click", (evt, d) => selectCountry(d));

    const generatedEl = document.getElementById("data-generated");
    if (generatedEl && worldData.meta.generated) {
      generatedEl.textContent = worldData.meta.generated.slice(0, 10);
    }

    wireControls();
    render(parseFloat(blendInput.value));
    setActiveLayer(activeLayer.id);
  }

  init();
})();
