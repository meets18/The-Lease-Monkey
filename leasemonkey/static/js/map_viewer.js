// Centralized dummy plot dataset with geolocated corner coordinates
const plotData = [
  {
    "number": "101",
    "status": "sold",
    "price": "INR 4,712,000",
    "area": "1,705 sqft",
    "facing": "South",
    "coordinates": [
      [26.787732, 75.833265],
      [26.787610, 75.834034],
      [26.788687, 75.834319],
      [26.788822, 75.833548]
    ],
    "center": { "lat": 26.788213, "lng": 75.833792 }
  },
  {
    "number": "102",
    "status": "available",
    "price": "INR 4,724,000",
    "area": "1,710 sqft",
    "facing": "South",
    "coordinates": [
      [26.787582, 75.834212],
      [26.787460, 75.834981],
      [26.788521, 75.835269],
      [26.788656, 75.834497]
    ],
    "center": { "lat": 26.788055, "lng": 75.83474 }
  },
  {
    "number": "103",
    "status": "reserved",
    "price": "INR 4,736,000",
    "area": "1,715 sqft",
    "facing": "South",
    "coordinates": [
      [26.787432, 75.835159],
      [26.787310, 75.835928],
      [26.788355, 75.836219],
      [26.788490, 75.835447]
    ],
    "center": { "lat": 26.787897, "lng": 75.835688 }
  },
  {
    "number": "104",
    "status": "sold",
    "price": "INR 4,748,000",
    "area": "1,720 sqft",
    "facing": "South",
    "coordinates": [
      [26.787281, 75.836106],
      [26.787159, 75.836875],
      [26.788189, 75.837169],
      [26.788324, 75.836397]
    ],
    "center": { "lat": 26.787739, "lng": 75.836637 }
  },
  {
    "number": "105",
    "status": "available",
    "price": "INR 4,760,000",
    "area": "1,725 sqft",
    "facing": "South",
    "coordinates": [
      [26.787131, 75.837053],
      [26.787009, 75.837822],
      [26.788024, 75.838118],
      [26.788158, 75.837347]
    ],
    "center": { "lat": 26.787581, "lng": 75.837585 }
  },
  {
    "number": "106",
    "status": "reserved",
    "price": "INR 4,772,000",
    "area": "1,730 sqft",
    "facing": "South",
    "coordinates": [
      [26.786981, 75.838000],
      [26.786859, 75.838769],
      [26.787858, 75.839068],
      [26.787992, 75.838296]
    ],
    "center": { "lat": 26.787423, "lng": 75.838533 }
  },
  {
    "number": "107",
    "status": "available",
    "price": "INR 5,912,000",
    "area": "2,205 sqft",
    "facing": "North",
    "coordinates": [
      [26.789148, 75.833633],
      [26.789010, 75.834405],
      [26.790087, 75.834690],
      [26.790238, 75.833916]
    ],
    "center": { "lat": 26.789621, "lng": 75.834161 }
  },
  {
    "number": "108",
    "status": "reserved",
    "price": "INR 5,924,000",
    "area": "2,210 sqft",
    "facing": "North",
    "coordinates": [
      [26.788978, 75.834583],
      [26.788839, 75.835356],
      [26.789901, 75.835643],
      [26.790052, 75.834869]
    ],
    "center": { "lat": 26.789442, "lng": 75.835113 }
  },
  {
    "number": "109",
    "status": "sold",
    "price": "INR 5,936,000",
    "area": "2,215 sqft",
    "facing": "North",
    "coordinates": [
      [26.788807, 75.835534],
      [26.788669, 75.836306],
      [26.789714, 75.836597],
      [26.789866, 75.835822]
    ],
    "center": { "lat": 26.789264, "lng": 75.836065 }
  },
  {
    "number": "110",
    "status": "available",
    "price": "INR 5,948,000",
    "area": "2,220 sqft",
    "facing": "North",
    "coordinates": [
      [26.788637, 75.836484],
      [26.788498, 75.837257],
      [26.789528, 75.837550],
      [26.789680, 75.836775]
    ],
    "center": { "lat": 26.789086, "lng": 75.837017 }
  },
  {
    "number": "111",
    "status": "reserved",
    "price": "INR 5,960,000",
    "area": "2,225 sqft",
    "facing": "North",
    "coordinates": [
      [26.788466, 75.837435],
      [26.788328, 75.838207],
      [26.789342, 75.838503],
      [26.789493, 75.837729]
    ],
    "center": { "lat": 26.788907, "lng": 75.837969 }
  },
  {
    "number": "112",
    "status": "sold",
    "price": "INR 5,972,000",
    "area": "2,230 sqft",
    "facing": "North",
    "coordinates": [
      [26.788296, 75.838385],
      [26.788157, 75.839158],
      [26.789156, 75.839457],
      [26.789307, 75.838682]
    ],
    "center": { "lat": 26.788729, "lng": 75.838921 }
  }
];

// Global States
let map = null;
let satelliteLayer = null;
let boundaryPolygon = null;
let mapPolygons = [];
let renderedRoadLayers = [];
let activeLabelMarkers = [];
let selectedMapPolygon = null;
let currentFilter = 'all';
let colorCodingActive = false; // Default: OFF (Cream plots)
let satelliteActive = false;    // Default: OFF (Dark backdrop map view)

// Dynamic road weight scaling based on zoom levels and thickness multiplier
let roadThicknessMultiplier = 1.0;

function calculateRoadWeight(width, zoom) {
  const baseWeight = width * 2.8 * roadThicknessMultiplier;
  const zoomFactor = Math.pow(2, zoom - 18);
  return Math.max(1.5, baseWeight * zoomFactor);
}

function calculateRoadOutlineWeight(width, zoom) {
  const baseWeight = (width * 2.8 + 3.0) * roadThicknessMultiplier;
  const zoomFactor = Math.pow(2, zoom - 18);
  return Math.max(2.5, baseWeight * zoomFactor);
}

function calculateRoadStripeWeight(zoom) {
  const zoomFactor = Math.pow(2, zoom - 18);
  return Math.max(0.5, 1.5 * zoomFactor * roadThicknessMultiplier);
}

function updateRoadWeights() {
  const currentZoom = map.getZoom();
  renderedRoadLayers.forEach(layer => {
    if (layer.outline) layer.outline.setStyle({ weight: calculateRoadOutlineWeight(layer.width, currentZoom) });
    if (layer.polyline) layer.polyline.setStyle({ weight: calculateRoadWeight(layer.width, currentZoom) });
    if (layer.stripe) layer.stripe.setStyle({ weight: calculateRoadStripeWeight(currentZoom) });
  });
}

function updatePlotLabelVisibility() {
  const currentZoom = map.getZoom();
  const showLabels = currentZoom >= 17.5;
  mapPolygons.forEach(polygon => {
    if (polygon.labelMarker) {
      if (showLabels && !satelliteActive) {
        if (!map.hasLayer(polygon.labelMarker)) {
          polygon.labelMarker.addTo(map);
        }
      } else {
        if (map.hasLayer(polygon.labelMarker)) {
          map.removeLayer(polygon.labelMarker);
        }
      }
    }
  });
}

let is3DActive = false;
let building3DLayers = [];

function update3DBuildingsView() {
  // Clear any existing 3D layers
  building3DLayers.forEach(layer => map.removeLayer(layer));
  building3DLayers = [];

  const mapEl = document.getElementById('map');
  const btn3D = document.getElementById('btn3DToggle');

  if (is3DActive) {
    if (mapEl) mapEl.classList.add('map-3d-tilted');
    if (btn3D) {
      btn3D.innerHTML = '2D';
      btn3D.classList.add('active-cyan-btn');
    }

    // Offset in geographic degrees to simulate building height when tilted
    // We scale it dynamically based on the building height (floors/multiplier)
    // A default base of 0.000025 dLat and 0.000007 dLng per floor gives a nice scaling look.

    // Find all dedicated building records
    let activePlotData = plotData;
    if (typeof landConfig !== 'undefined' && landConfig.slug !== 'demo-land') {
      activePlotData = landConfig.buildings || [];
    }

    activePlotData.forEach(plot => {
      const rawStatus = (plot.status || '').toLowerCase();
      if (rawStatus === 'building') {
        const baseCoords = plot.coordinates;
        // Make sure coordinates are normalized as array of numbers
        const baseNorm = baseCoords.map(p => Array.isArray(p) ? p : [p.lat, p.lng]);
        
        const floors = parseInt(plot.height || 1, 10);
        const dLat = 0.000025 * floors;
        const dLng = 0.000007 * floors;
        const roofCoords = baseNorm.map(pt => [pt[0] + dLat, pt[1] + dLng]);

        // Hide the original flat building polygon
        const flatPoly = mapPolygons.find(p => p.plotData && p.plotData.number === plot.number);
        if (flatPoly) {
          flatPoly.setStyle({ fillOpacity: 0, opacity: 0 });
          if (flatPoly.labelMarker) flatPoly.labelMarker.setOpacity(0);
        }

        // 1. Render side walls (connect base edges to roof edges)
        const numPts = baseNorm.length;
        for (let i = 0; i < numPts; i++) {
          const nextIdx = (i + 1) % numPts;
          const wallCoords = [
            baseNorm[i],
            baseNorm[nextIdx],
            roofCoords[nextIdx],
            roofCoords[i]
          ];

          // Alternating wall shading for depth
          const wallColor = i % 2 === 0 ? '#718096' : '#4a5568';
          const wall = L.polygon(wallCoords, {
            color: '#2d3748',
            weight: 1,
            opacity: 0.7,
            fillColor: wallColor,
            fillOpacity: 0.9,
            interactive: false
          }).addTo(map);
          building3DLayers.push(wall);
        }

        // 2. Render roof polygon (semi-translucent white/light grey glass look)
        const roof = L.polygon(roofCoords, {
          color: '#cbd5e0',
          weight: 1.5,
          opacity: 0.9,
          fillColor: '#edf2f7',
          fillOpacity: 0.85,
          interactive: false
        }).addTo(map);
        building3DLayers.push(roof);

        // 3. Render floating label marker at the roof centroid
        const roofCentroid = getPolygonCentroid(roofCoords);
        const labelIcon = L.divIcon({
          className: 'plot-number-tooltip-3d',
          html: `<div style="color: #ffffff; text-shadow: 0 1px 3px rgba(0,0,0,0.9); font-weight: 800;">${plot.number}</div>`,
          iconSize: [30, 16],
          iconAnchor: [15, 8]
        });
        const labelMarker = L.marker(roofCentroid, { icon: labelIcon, interactive: false }).addTo(map);
        building3DLayers.push(labelMarker);
      }
    });

  } else {
    // 2D View
    if (mapEl) mapEl.classList.remove('map-3d-tilted');
    if (btn3D) {
      btn3D.innerHTML = '3D';
      btn3D.classList.remove('active-cyan-btn');
    }

    // Show the original flat polygons
    mapPolygons.forEach(flatPoly => {
      if (flatPoly.statusColorKey === 'building') {
        flatPoly.setStyle({ fillOpacity: 0.95, opacity: 0.8 });
        if (flatPoly.labelMarker) flatPoly.labelMarker.setOpacity(1);
      }
    });
  }

  if (map) {
    requestAnimationFrame(() => {
      map.invalidateSize(true);
    });
  }
}
let centerCoords = [26.788506, 75.836371];
let initialZoom = 17;
let minZoomLimit = 16;



// Constants for color codes — theme-aware
function getThemeColors() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  return {
    available: isLight ? '#43A047' : '#9CB447',
    reserved: isLight ? '#F59E0B' : '#8e9aa8',
    sold: isLight ? '#DC2626' : '#C7483F',
    building: isLight ? '#cbd5e1' : '#ffffff',
    uniform: '#f0e6d6'
  };
}
const COLORS = getThemeColors();

// Rebuild colors when theme toggles
const themeObserver = new MutationObserver(function() {
  const c = getThemeColors();
  Object.assign(COLORS, c);
});
const htmlEl = document.documentElement;
themeObserver.observe(htmlEl, { attributes: true, attributeFilter: ['data-theme'] });

// Initial document load setup
document.addEventListener("DOMContentLoaded", () => {
  initMap();
});

// Initialize Leaflet Map
function initMap() {
  // Use dynamic configuration if provided by Django context
  if (typeof landConfig !== 'undefined') {
    if (landConfig.center) centerCoords = landConfig.center;
    if (landConfig.zoom) initialZoom = landConfig.zoom;
    // For newly plotted custom lands, allow standard zoom ranges
    if (landConfig.slug !== 'demo-land') {
      minZoomLimit = 1;
    }
  }
  
  // Create Leaflet map container on div 'map'
  map = L.map('map', {
    center: centerCoords,
    zoom: initialZoom,
    zoomControl: false, // Disable default top-left control to place on right
    attributionControl: false,
    minZoom: minZoomLimit,
    maxZoom: 22
  });

  // Position zoom controls on the right-hand side
  L.control.zoom({ position: 'topright' }).addTo(map);

  // Listen to map zoom changes to dynamically scale road weights
  map.on('zoomend', updateRoadWeights);
  map.on('zoomend', updatePlotLabelVisibility);

  // If satellite mode is active on load, add satellite layer and toggle class
  if (satelliteActive) {
    const mapEl = document.getElementById('map');
    const satelliteBtn = document.getElementById('btnSatelliteToggle');
    if (satelliteBtn) satelliteBtn.classList.add('active-cyan-btn');
    if (mapEl) mapEl.classList.add('satellite-active');

    satelliteLayer = L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
      maxZoom: 22,
      maxNativeZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
    });
    satelliteLayer.addTo(map);
  }

  // Draw land boundary rectangle shape in flat dark theme or glowing translucent
  let landBoundaryCoords = [
    [26.787651, 75.833059],
    [26.786722, 75.838976],
    [26.789209, 75.839725],
    [26.790382, 75.833765]
  ];

  if (typeof landConfig !== 'undefined' && landConfig.boundary && landConfig.boundary.length > 0) {
    landBoundaryCoords = landConfig.boundary;
  }

  let boundaryStyle = {
    color: '#3a3d44',
    weight: 1.5,
    opacity: 0.6,
    fillColor: '#151922',
    fillOpacity: 0.95
  };

  if (typeof landConfig !== 'undefined' && landConfig.slug !== 'demo-land') {
    boundaryStyle = {
      color: '#00ffd2',
      weight: 2,
      opacity: 0.65,
      fillColor: '#151922',
      fillOpacity: 0.92
    };
  }

  boundaryPolygon = L.polygon(landBoundaryCoords, boundaryStyle).addTo(map);

  // Fit entire project boundary within viewport, accounting for navbar and controls
  if (typeof landConfig !== 'undefined' && landConfig.slug !== 'demo-land') {
    map.fitBounds(boundaryPolygon.getBounds(), {
      paddingTopLeft: [20, 70],
      paddingBottomRight: [370, 240]
    });
  }

  if (typeof landConfig !== 'undefined' && landConfig.slug !== 'demo-land') {
    // Render database roads and gates for custom properties
    if (landConfig.roads) {
      // 1. Draw all outlines
      const outlines = landConfig.roads.map(road => renderRoadOutline(road));
      // 2. Draw all solid surfaces
      const polylines = landConfig.roads.map(road => renderRoadSurface(road));
      // 3. Draw all stripes
      const stripes = landConfig.roads.map(road => renderRoadStripe(road));
      
      // Populate layer tracking for scaling zoom adjustments
      landConfig.roads.forEach((road, idx) => {
        const roadWidth = road.width || road.width_meters || 9.0;
        renderedRoadLayers.push({
          outline: outlines[idx],
          polyline: polylines[idx],
          stripe: stripes[idx],
          width: roadWidth
        });
      });
    }
    if (landConfig.gates) {
      landConfig.gates.forEach(gate => renderGateOnMap(gate));
    }
  }

  // Draw plot polygons on top of the boundary
  let activePlotData = plotData;
  if (typeof landConfig !== 'undefined' && landConfig.slug !== 'demo-land') {
    const plots = landConfig.plots || [];
    const buildings = landConfig.buildings || [];
    activePlotData = [...plots, ...buildings];
  }

  activePlotData.forEach(plot => {
    const rawStatus = (plot.status || '').toLowerCase();
    const statusColorKey = ['available', 'reserved', 'sold', 'building'].includes(rawStatus)
      ? rawStatus
      : 'available';
    const isBuildingPlot = statusColorKey === 'building';

    const polygon = L.polygon(plot.coordinates, {
      color: isBuildingPlot ? '#718096' : '#55585e',
      weight: isBuildingPlot ? 1.0 : 1.0,
      opacity: 0.7,
      fillColor: isBuildingPlot ? '#e2e8f0' : getPlotColor(statusColorKey),
      fillOpacity: isBuildingPlot ? 0.95 : (colorCodingActive ? 0.75 : 0.85),
      interactive: !isBuildingPlot
    }).addTo(map);

    polygon.plotData = plot;
    polygon.statusColorKey = statusColorKey;

    // Bind permanent plot number label centered inside the polygon using custom centroid marker
    const centroid = getPolygonCentroid(plot.coordinates);
    const labelIcon = L.divIcon({
      className: 'plot-number-tooltip',
      html: `<div>${plot.number}</div>`,
      iconSize: [30, 16],
      iconAnchor: [15, 8]
    });
    const labelMarker = L.marker(centroid, { icon: labelIcon, interactive: false }).addTo(map);
    polygon.labelMarker = labelMarker;

    mapPolygons.push(polygon);

    if (!isBuildingPlot) {
      // Hover Mouseover
      polygon.on('mouseover', function(e) {
        this.setStyle({
          fillOpacity: colorCodingActive ? 0.7 : 0.95,
          weight: 2,
          color: '#00b8ff'
        });
      });

      // Hover Mouseout
      polygon.on('mouseout', function(e) {
        if (selectedMapPolygon !== this) {
          this.setStyle({
            fillOpacity: colorCodingActive ? 0.75 : 0.85,
            weight: 1.0,
            color: '#55585e'
          });
        } else {
          this.setStyle({
            fillOpacity: colorCodingActive ? 0.7 : 0.95,
            weight: 2.5,
            color: '#00b8ff'
          });
        }
      });

      // Click selection
      polygon.on('click', function(e) {
        selectMapPlot(this);
      });
    }
  });

  // Setup control listeners
  setupToggleControls();
  setupFilters();
  setupSearch();
  setupUtilities();

  // Apply initial plot label visibility
  updatePlotLabelVisibility();
}

// Select Map Plot polygon
function selectMapPlot(polygon) {
  if (selectedMapPolygon) {
    selectedMapPolygon.setStyle({
      fillColor: getPlotColor(selectedMapPolygon.statusColorKey),
      fillOpacity: colorCodingActive ? 0.75 : 0.85,
      weight: 1.0,
      color: '#55585e'
    });
  }

  selectedMapPolygon = polygon;

  polygon.setStyle({
    fillColor: '#00b8ff',
    fillOpacity: 0.75,
    weight: 2.5,
    color: '#00b8ff'
  });

  populateDetailsPanel(polygon.plotData, polygon.statusColorKey);
  map.panTo(polygon.getBounds().getCenter());
}

// Populate Left Slide-In Panel
function populateDetailsPanel(data, statusColorKey) {
  document.getElementById('detailNum').innerText = data.number;
  document.getElementById('detailArea').innerText = data.area;
  document.getElementById('detailPrice').innerText = data.price;

  const statusLabel = document.getElementById('detailStatus');
  statusLabel.innerText = data.status.toUpperCase();
  statusLabel.className = 'badge fw-bold py-1.5 px-3 text-uppercase text-dark';
  statusLabel.style.backgroundColor = COLORS[statusColorKey];

  // Toggle Raise a Request CTA display based on plot status
  const btnHoldPlot = document.getElementById('btnHoldPlot');
  if (btnHoldPlot) {
    if (data.status === 'available') {
      btnHoldPlot.style.display = 'block';
    } else {
      btnHoldPlot.style.display = 'none';
    }
  }

  document.getElementById('detailsPanel').style.display = 'block';
}

// Get plot color helper
function getPlotColor(statusColorKey) {
  if (statusColorKey === 'building') {
    return COLORS.building;
  }
  if (!colorCodingActive) {
    return COLORS.uniform;
  }
  return COLORS[statusColorKey] || COLORS.uniform;
}

// Setup switches and button events
function setupToggleControls() {
  const statusColorToggle = document.getElementById('statusColorToggle');
  const legendPanel = document.getElementById('legendPanel');



  // Status Switch (OFF/ON)
  statusColorToggle.addEventListener('change', (e) => {
    colorCodingActive = e.target.checked;
    
    // Toggle color legend visibility
    legendPanel.style.display = colorCodingActive ? 'flex' : 'none';

    // Refresh polygon colors
    mapPolygons.forEach(polygon => {
      if (polygon === selectedMapPolygon) {
        polygon.setStyle({
          fillColor: '#00b8ff',
          fillOpacity: 0.75,
          color: '#00b8ff',
          weight: 2.5
        });
      } else {
        polygon.setStyle({
          fillColor: getPlotColor(polygon.statusColorKey),
          fillOpacity: colorCodingActive ? 0.75 : 0.85,
          weight: 1.0,
          color: '#55585e'
        });
      }
    });
  });

  // Circular Satellite Map Toggler button (OFF/ON)
  const satelliteBtn = document.getElementById('btnSatelliteToggle');
  const routeBtn = document.getElementById('btnRoute');
  const locateBtn = document.getElementById('btnLocate');
  satelliteBtn.addEventListener('click', () => {
    satelliteActive = !satelliteActive;
    const mapEl = document.getElementById('map');
    
    if (satelliteActive) {
      satelliteBtn.classList.add('active-cyan-btn');
      if (mapEl) mapEl.classList.add('satellite-active');
      if (locateBtn) locateBtn.style.display = 'none';
      if (routeBtn) routeBtn.style.display = 'inline-flex';
      
      // Allow unrestricted zoom out when satellite is active
      map.setMinZoom(1);
      
      // Load and add Satellite tiles dynamically underneath polygons
      if (!satelliteLayer) {
        satelliteLayer = L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
          maxZoom: 22,
          maxNativeZoom: 20,
          subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
        });
      }
      satelliteLayer.addTo(map);
      
      // Send satellite tiles to the back so vector plots sit on top
      satelliteLayer.bringToBack();

      // Hide road and gate text labels on satellite layer
      activeLabelMarkers.forEach(m => map.removeLayer(m));
      updatePlotLabelVisibility();
    } else {
      satelliteBtn.classList.remove('active-cyan-btn');
      if (mapEl) mapEl.classList.remove('satellite-active');
      if (locateBtn) locateBtn.style.display = 'inline-flex';
      if (routeBtn) routeBtn.style.display = 'none';
      
      // Clean up routing layer when toggling satellite off
      if (typeof window.clearGpsRouting === 'function') {
        window.clearGpsRouting();
      }
      
      // Reset zoom limits and re-center if user zoomed out past minZoomLimit
      if (map.getZoom() < minZoomLimit) {
        map.setView(centerCoords, initialZoom);
      }
      map.setMinZoom(minZoomLimit);
      
      // Unload/remove Satellite tiles from Leaflet map view
      if (satelliteLayer) {
        map.removeLayer(satelliteLayer);
      }

      // Show road and gate text labels back on vector layout
      activeLabelMarkers.forEach(m => m.addTo(map));
      updatePlotLabelVisibility();
    }

    requestAnimationFrame(() => {
      map.invalidateSize(true);
    });
  });

  // 3D View Toggler button (OFF/ON) with cinematic loading transition
  const btn3D = document.getElementById('btn3DToggle');
  if (btn3D) {
    btn3D.addEventListener('click', () => {
      is3DActive = !is3DActive;

      const overlay = document.getElementById('loadingOverlay3d');
      const msgEl = document.getElementById('loadingMessage3d');
      const subEl = document.getElementById('loadingSub3d');

      if (!overlay) { update3DBuildingsView(); return; }

      // Show overlay, disable map interaction
      overlay.style.display = 'flex';
      requestAnimationFrame(() => { overlay.classList.add('loading-visible'); });

      map.dragging.disable();
      map.touchZoom.disable();
      map.doubleClickZoom.disable();
      map.scrollWheelZoom.disable();
      map.boxZoom.disable();
      map.keyboard.disable();

      if (map.tap) map.tap.disable();

      if (is3DActive) {
        msgEl.textContent = 'Loading 3D View...';
        subEl.textContent = 'Preparing terrain';
      } else {
        msgEl.textContent = 'Returning to 2D View...';
        subEl.textContent = 'Rendering layout';
      }

      // Run transition behind overlay
      update3DBuildingsView();

      // Reveal when rendering is committed — use double rAF to catch paint
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          overlay.classList.remove('loading-visible');
          setTimeout(() => { overlay.style.display = 'none'; }, 350);

          map.dragging.enable();
          map.touchZoom.enable();
          map.doubleClickZoom.enable();
          map.scrollWheelZoom.enable();
          map.boxZoom.enable();
          map.keyboard.enable();
          if (map.tap) map.tap.enable();
        });
      });
    });
  }
}

// Sidebar status tags filters
function setupFilters() {
  const filterButtons = document.querySelectorAll('.btn-filter-tag');
  
  filterButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      filterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      currentFilter = btn.getAttribute('data-filter');
      applyFilters();
    });
  });
}

function applyFilters() {
  mapPolygons.forEach(polygon => {
    const status = polygon.plotData.status;
    if (currentFilter === 'all' || status === currentFilter) {
      if (!map.hasLayer(polygon)) {
        polygon.addTo(map);
        if (polygon.labelMarker) polygon.labelMarker.addTo(map);
      }
    } else {
      if (map.hasLayer(polygon)) {
        map.removeLayer(polygon);
        if (polygon.labelMarker) map.removeLayer(polygon.labelMarker);
      }
    }
  });
}

// Hook Plot search bar
function setupSearch() {
  const searchInput = document.getElementById('plotSearchInput');
  
  searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      triggerSearch(searchInput.value.trim());
    }
  });
}

function triggerSearch(query) {
  if (!query) return;
  
  const matched = mapPolygons.find(p => p.plotData.number === query);
  if (matched) {
    if (matched.statusColorKey === 'building') {
      map.setView(matched.getBounds().getCenter(), 19);
      alert(`Plot "${query}" is marked as Building and is not clickable.`);
      return;
    }
    if (!map.hasLayer(matched)) {
      currentFilter = 'all';
      applyFilters();
    }
    map.setView(matched.getBounds().getCenter(), 19);
    selectMapPlot(matched);
    
    // Outline pulse animation
    let isPulse = true;
    let count = 0;
    const pulseInterval = setInterval(() => {
      matched.setStyle({
        fillOpacity: isPulse ? 0.75 : 0.2,
        weight: isPulse ? 4 : 1.0,
        color: '#00b8ff'
      });
      isPulse = !isPulse;
      count++;
      if (count >= 6) {
        clearInterval(pulseInterval);
        matched.setStyle({
          fillOpacity: colorCodingActive ? 0.7 : 0.95,
          weight: 2.5,
          color: '#00b8ff'
        });
      }
    }, 250);
  } else {
    alert(`Plot "${query}" not found. Try searching 101 to 112.`);
  }
}

// Reset filters CTA
function resetFilters() {
  document.getElementById('plotSearchInput').value = '';
  currentFilter = 'all';
  applyFilters();
  
  if (selectedMapPolygon) {
    selectedMapPolygon.setStyle({
      fillColor: getPlotColor(selectedMapPolygon.statusColorKey),
      fillOpacity: colorCodingActive ? 0.75 : 0.85,
      weight: 1.0,
      color: '#55585e'
    });
    selectedMapPolygon = null;
  }
  document.getElementById('detailsPanel').style.display = 'none';
  map.setView(centerCoords, initialZoom);
}

// Setup menu utilities
function setupUtilities() {
  // Reset locate home view
  document.getElementById('btnHomeLocate').addEventListener('click', () => {
    map.setView(centerCoords, initialZoom);
  });
}

// Close details specs sidebar panel
function closeDetailsPanel() {
  document.getElementById('detailsPanel').style.display = 'none';
  if (selectedMapPolygon) {
    selectedMapPolygon.setStyle({
      fillColor: getPlotColor(selectedMapPolygon.statusColorKey),
      fillOpacity: colorCodingActive ? 0.75 : 0.85,
      weight: 1.0,
      color: '#55585e'
    });
    selectedMapPolygon = null;
  }
}

// Centroid calculator helper
function getPolygonCentroid(latlngs) {
  let pts = latlngs;
  if (pts.length === 1 && Array.isArray(pts[0])) {
    pts = pts[0];
  }
  let points = pts.map(p => {
    if (Array.isArray(p)) {
      return { lat: p[0], lng: p[1] };
    }
    return { lat: p.lat, lng: p.lng };
  });

  if (points.length === 0) return { lat: 0, lng: 0 };
  
  // Filter unique vertices
  let uniquePoints = [];
  let seen = new Set();
  points.forEach(p => {
    let key = `${p.lat.toFixed(8)}_${p.lng.toFixed(8)}`;
    if (!seen.has(key)) {
      seen.add(key);
      uniquePoints.push(p);
    }
  });

  if (uniquePoints.length === 0) return points[0];

  let sumLat = 0;
  let sumLng = 0;
  uniquePoints.forEach(p => {
    sumLat += p.lat;
    sumLng += p.lng;
  });

  return { lat: sumLat / uniquePoints.length, lng: sumLng / uniquePoints.length };
}

function renderRoadOutline(road) {
  const currentZoom = map.getZoom();
  const roadWidth = road.width || road.width_meters || 9.0;
  return L.polyline(road.coordinates, {
    color: '#2a2d33',
    weight: calculateRoadOutlineWeight(roadWidth, currentZoom),
    opacity: 0.9,
    interactive: false,
    lineCap: 'butt',
    lineJoin: 'miter'
  }).addTo(map);
}

function renderRoadSurface(road) {
  const currentZoom = map.getZoom();
  const roadWidth = road.width || road.width_meters || 9.0;
  return L.polyline(road.coordinates, {
    color: '#484b50',
    weight: calculateRoadWeight(roadWidth, currentZoom),
    opacity: 0.85,
    interactive: false,
    lineCap: 'butt',
    lineJoin: 'miter'
  }).addTo(map);
}

function renderRoadStripe(road) {
  const currentZoom = map.getZoom();
  return L.polyline(road.coordinates, {
    color: '#7a8088',
    weight: calculateRoadStripeWeight(currentZoom),
    dashArray: '6, 12',
    opacity: 0.45,
    interactive: false
  }).addTo(map);
}

function renderRoadOnMap(road) {
  const outline = renderRoadOutline(road);
  const polyline = renderRoadSurface(road);
  const stripe = renderRoadStripe(road);
  const roadWidth = road.width || road.width_meters || 9.0;

  renderedRoadLayers.push({
    outline: outline,
    polyline: polyline,
    stripe: stripe,
    width: roadWidth
  });
}

function renderGateOnMap(gate) {
  let gateColor = '#00ffd2'; // Entry: cyan
  let gateLabel = 'ENTRY';
  if (gate.point_type === 'exit') {
    gateColor = '#ff6c00'; // Exit: orange
    gateLabel = 'EXIT';
  } else if (gate.point_type === 'both') {
    gateColor = '#00b2ff'; // Both: blue
    gateLabel = 'ENTRY/EXIT';
  }

  // 1. Neon glowing pulser ring at the gate coordinates
  L.marker([gate.latitude, gate.longitude], {
    icon: L.divIcon({
      className: 'gate-highlight-wrap',
      html: `<div class="gate-pulse-ring" style="color: ${gateColor};"></div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    }),
    interactive: false
  }).addTo(map);

  // 2. High-contrast text label placed cleanly outside the point (above the gate coordinate)
  const labelMarker = L.marker([gate.latitude, gate.longitude], {
    icon: L.divIcon({
      className: 'gate-label-outside',
      html: `<div class="gate-outside-text text-uppercase" style="color: ${gateColor}; font-family: 'Ranade', sans-serif; font-size: 11px; font-weight: 800; letter-spacing: 0.1em;">${gateLabel}</div>`,
      iconSize: [120, 24],
      iconAnchor: [60, 30] // Positioned 30px above the highlight so it sits outside
    }),
    interactive: false
  });

  // Push to dynamic toggle list
  activeLabelMarkers.push(labelMarker);

  // Render on initial load only if satellite view is disabled
  if (!satelliteActive) {
    labelMarker.addTo(map);
  }
}
