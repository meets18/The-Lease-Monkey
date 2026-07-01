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
let selectedMapPolygon = null;
let currentFilter = 'all';
let colorCodingActive = false; // Default: OFF (Cream plots)
let satelliteActive = false;    // Default: OFF (Dark backdrop map view)

// Constants for color codes
const COLORS = {
  available: '#9CB447', // Available
  reserved: '#8e9aa8',  // Booked (Grey)
  sold: '#C7483F',      // On Hold
  uniform: '#eaddca'    // Uniform beige
};

// Initial document load setup
document.addEventListener("DOMContentLoaded", () => {
  initMap();
});

// Initialize Leaflet Map
function initMap() {
  const centerCoords = [26.788506, 75.836371];
  
  // Create Leaflet map container on div 'map'
  map = L.map('map', {
    center: centerCoords,
    zoom: 17,
    zoomControl: false, // Disable default top-left control to place on right
    attributionControl: false,
    minZoom: 16,
    maxZoom: 19
  });

  // Position zoom controls on the right-hand side
  L.control.zoom({ position: 'topright' }).addTo(map);

  // Draw land boundary rectangle shape in flat dark theme
  const landBoundaryCoords = [
    [26.787651, 75.833059],
    [26.786722, 75.838976],
    [26.789209, 75.839725],
    [26.790382, 75.833765]
  ];

  boundaryPolygon = L.polygon(landBoundaryCoords, {
    color: '#282b30',
    weight: 3,
    opacity: 0.8,
    fillColor: '#151922',
    fillOpacity: 0.95
  }).addTo(map);

  // Add road label in the central corridor between North and South plot rows
  const roadIcon = L.divIcon({
    className: 'road-label-container',
    html: '<div class="map-road-label">12M WIDE ACCESS ROAD</div>',
    iconSize: [250, 20],
    iconAnchor: [125, 10]
  });
  L.marker([26.78851, 75.8363], { icon: roadIcon, interactive: false }).addTo(map);

  // Draw plot polygons on top of the boundary
  plotData.forEach(plot => {
    let statusColorKey = plot.status;
    if (plot.status === 'sold') statusColorKey = 'sold';
    if (plot.status === 'available') statusColorKey = 'available';
    if (plot.status === 'reserved') statusColorKey = 'reserved';

    const polygon = L.polygon(plot.coordinates, {
      color: '#3d4045',
      weight: 1.5,
      opacity: 0.8,
      fillColor: getPlotColor(statusColorKey),
      fillOpacity: colorCodingActive ? 0.8 : 0.9
    }).addTo(map);

    polygon.plotData = plot;
    polygon.statusColorKey = statusColorKey;

    // Bind permanent plot number label centered inside the polygon
    polygon.bindTooltip(plot.number, {
      permanent: true,
      direction: 'center',
      className: 'plot-number-tooltip'
    });

    mapPolygons.push(polygon);

    // Hover Mouseover
    polygon.on('mouseover', function(e) {
      this.setStyle({
        fillOpacity: colorCodingActive ? 0.75 : 0.98,
        weight: 3,
        color: '#00b8ff' // highlight blue on hover
      });
    });

    // Hover Mouseout
    polygon.on('mouseout', function(e) {
      if (selectedMapPolygon !== this) {
        this.setStyle({
          fillOpacity: colorCodingActive ? 0.8 : 0.9,
          weight: 1.5,
          color: '#3d4045'
        });
      } else {
        // Keep selected highlight style
        this.setStyle({
          fillOpacity: colorCodingActive ? 0.75 : 0.98,
          weight: 3.5,
          color: '#00b8ff'
        });
      }
    });

    // Click selection
    polygon.on('click', function(e) {
      selectMapPlot(this);
    });
  });

  // Setup control listeners
  setupToggleControls();
  setupFilters();
  setupSearch();
  setupUtilities();
}

// Select Map Plot polygon
function selectMapPlot(polygon) {
  if (selectedMapPolygon) {
    selectedMapPolygon.setStyle({
      fillColor: getPlotColor(selectedMapPolygon.statusColorKey),
      fillOpacity: colorCodingActive ? 0.8 : 0.9,
      weight: 1.5,
      color: '#3d4045'
    });
  }

  selectedMapPolygon = polygon;

  polygon.setStyle({
    fillColor: '#00b8ff', // fill blue on click
    fillOpacity: 0.8,
    weight: 3.5,
    color: '#00b8ff' // highlight outline blue on click
  });

  populateDetailsPanel(polygon.plotData, polygon.statusColorKey);
  map.panTo([polygon.plotData.center.lat, polygon.plotData.center.lng]);
}

// Populate Left Slide-In Panel
function populateDetailsPanel(data, statusColorKey) {
  document.getElementById('detailNum').innerText = data.number;
  document.getElementById('detailArea').innerText = data.area;
  document.getElementById('detailPrice').innerText = data.price;
  document.getElementById('detailFacing').innerText = data.facing;

  const statusLabel = document.getElementById('detailStatus');
  statusLabel.innerText = data.status.toUpperCase();
  statusLabel.className = 'badge fw-bold py-1.5 px-3 text-uppercase text-dark';
  statusLabel.style.backgroundColor = COLORS[statusColorKey];

  document.getElementById('detailsPanel').style.display = 'block';
}

// Get plot color helper
function getPlotColor(statusColorKey) {
  if (!colorCodingActive) {
    return COLORS.uniform;
  }
  return COLORS[statusColorKey];
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
          fillOpacity: 0.8,
          color: '#00b8ff',
          weight: 3.5
        });
      } else {
        polygon.setStyle({
          fillColor: getPlotColor(polygon.statusColorKey),
          fillOpacity: colorCodingActive ? 0.8 : 0.9
        });
      }
    });
  });

  // Circular Satellite Map Toggler button (OFF/ON)
  const satelliteBtn = document.getElementById('btnSatelliteToggle');
  satelliteBtn.addEventListener('click', () => {
    satelliteActive = !satelliteActive;
    const mapEl = document.getElementById('map');
    
    if (satelliteActive) {
      satelliteBtn.classList.add('active-cyan-btn');
      if (mapEl) mapEl.classList.add('satellite-active');
      
      // Allow unrestricted zoom out when satellite is active
      map.setMinZoom(1);
      
      // Load and add Satellite tiles dynamically underneath polygons
      if (!satelliteLayer) {
        satelliteLayer = L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
          maxZoom: 19,
          subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
        });
      }
      satelliteLayer.addTo(map);
      
      // Send satellite tiles to the back so vector plots sit on top
      satelliteLayer.bringToBack();
    } else {
      satelliteBtn.classList.remove('active-cyan-btn');
      if (mapEl) mapEl.classList.remove('satellite-active');
      
      // Reset zoom limits and re-center if user zoomed out past 16
      if (map.getZoom() < 16) {
        map.setView([26.788506, 75.836371], 17);
      }
      map.setMinZoom(16);
      
      // Unload/remove Satellite tiles from Leaflet map view
      if (satelliteLayer) {
        map.removeLayer(satelliteLayer);
      }
    }
  });
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
      }
    } else {
      if (map.hasLayer(polygon)) {
        map.removeLayer(polygon);
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
    if (!map.hasLayer(matched)) {
      currentFilter = 'all';
      applyFilters();
    }
    map.setView([matched.plotData.center.lat, matched.plotData.center.lng], 19);
    selectMapPlot(matched);
    
    // Outline pulse animation in Leaflet
    let isPulse = true;
    let count = 0;
    const pulseInterval = setInterval(() => {
      matched.setStyle({
        fillOpacity: isPulse ? 0.8 : 0.2,
        weight: isPulse ? 6 : 1.5,
        color: '#00b8ff'
      });
      isPulse = !isPulse;
      count++;
      if (count >= 6) {
        clearInterval(pulseInterval);
        matched.setStyle({
          fillOpacity: colorCodingActive ? 0.75 : 0.98,
          weight: 3.5,
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
      fillOpacity: colorCodingActive ? 0.8 : 0.9,
      weight: 1.5,
      color: '#3d4045'
    });
    selectedMapPolygon = null;
  }
  document.getElementById('detailsPanel').style.display = 'none';
  map.setView([26.788506, 75.836371], 17);
}

// Setup menu utilities
function setupUtilities() {
  // Reset locate home view
  document.getElementById('btnHomeLocate').addEventListener('click', () => {
    map.setView([26.788506, 75.836371], 17);
  });
}

// Close details specs sidebar panel
function closeDetailsPanel() {
  document.getElementById('detailsPanel').style.display = 'none';
  if (selectedMapPolygon) {
    selectedMapPolygon.setStyle({
      fillColor: getPlotColor(selectedMapPolygon.statusColorKey),
      fillOpacity: colorCodingActive ? 0.8 : 0.9,
      weight: 1.5,
      color: '#3d4045'
    });
    selectedMapPolygon = null;
  }
}
