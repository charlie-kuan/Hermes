import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons in React Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Custom marker icons
const startIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const endIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const peakIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const hutIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-violet.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const waypointIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-yellow.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

function MapClickHandler({ onMapClick, isSelectingStart }) {
  useMapEvents({
    click: (e) => {
      onMapClick(e.latlng, isSelectingStart);
    },
  });
  return null;
}

export default function MapComponent({
  startPoint,
  endPoint,
  route,
  onMapClick,
  isLoop,
  selectedRoute = null,
  selectedWaypoints = []
}) {
  const [center] = useState([23.45, 120.95]); // Default center (Taiwan)
  const [isSelectingStart, setIsSelectingStart] = useState(true);
  const [mapLayer, setMapLayer] = useState('standard'); // 'standard', 'terrain', 'satellite'

  // Extract route coordinates for polyline
  const routeCoordinates = route?.segments?.flatMap(segment =>
    segment.geometry || [[segment.start_node.lat, segment.start_node.lon]]
  ) || [];

  // Extract waypoints from completed route
  const routeWaypoints = route?.waypoints || [];

  // Get icon for waypoint type
  const getWaypointIcon = (type) => {
    switch(type) {
      case 'peak': return peakIcon;
      case 'hut': return hutIcon;
      case 'trailhead': return startIcon;
      default: return waypointIcon;
    }
  };

  const handleMapClick = (latlng, forStart) => {
    onMapClick(latlng, forStart);
    // Toggle between selecting start and end
    if (!isLoop) {
      setIsSelectingStart(!forStart);
    }
  };

  // Define tile layer configurations
  const tileLayerConfigs = {
    standard: {
      url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    },
    terrain: {
      url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
      attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a>'
    },
    satellite: {
      url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    }
  };

  const currentLayer = tileLayerConfigs[mapLayer];

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative' }}>
      <MapContainer
        center={center}
        zoom={13}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          key={mapLayer}
          attribution={currentLayer.attribution}
          url={currentLayer.url}
          maxZoom={mapLayer === 'terrain' ? 17 : 19}
        />

        <MapClickHandler
          onMapClick={handleMapClick}
          isSelectingStart={isSelectingStart}
        />

        {/* Start marker */}
        {startPoint && (
          <Marker position={[startPoint.lat, startPoint.lng]} icon={startIcon}>
            <Popup>
              <strong>起點</strong><br />
              緯度: {startPoint.lat.toFixed(5)}<br />
              經度: {startPoint.lng.toFixed(5)}
            </Popup>
          </Marker>
        )}

        {/* End marker */}
        {endPoint && !isLoop && (
          <Marker position={[endPoint.lat, endPoint.lng]} icon={endIcon}>
            <Popup>
              <strong>終點</strong><br />
              緯度: {endPoint.lat.toFixed(5)}<br />
              經度: {endPoint.lng.toFixed(5)}
            </Popup>
          </Marker>
        )}

        {/* Route polyline */}
        {routeCoordinates.length > 0 && (
          <Polyline
            positions={routeCoordinates}
            color="#2563eb"
            weight={4}
            opacity={0.7}
          />
        )}

        {/* Waypoint markers from completed route */}
        {routeWaypoints.map((waypoint, index) => (
          <Marker
            key={`route-wp-${index}`}
            position={[waypoint.lat, waypoint.lon]}
            icon={getWaypointIcon(waypoint.type)}
          >
            <Popup>
              <strong>{waypoint.name || waypoint.type}</strong><br />
              類型: {waypoint.type}<br />
              海拔: {waypoint.elevation?.toFixed(0)}m
              {waypoint.amenities?.length > 0 && (
                <>
                  <br />設施: {waypoint.amenities.join(', ')}
                </>
              )}
            </Popup>
          </Marker>
        ))}

        {/* Preview waypoints from selected route (before planning) */}
        {selectedRoute && !route && (
          <>
            {/* Trailhead */}
            <Marker
              position={[selectedRoute.trailhead.lat, selectedRoute.trailhead.lon]}
              icon={startIcon}
            >
              <Popup>
                <strong>🚩 {selectedRoute.trailhead.name}</strong><br />
                登山口<br />
                海拔: {selectedRoute.trailhead.elevation}m
                {selectedRoute.trailhead.facilities && (
                  <>
                    <br />設施: {selectedRoute.trailhead.facilities.join(', ')}
                  </>
                )}
              </Popup>
            </Marker>

            {/* Selected waypoints */}
            {selectedRoute.waypoints
              .filter(wp => selectedWaypoints.includes(wp.name))
              .map((waypoint, index) => (
                <Marker
                  key={`preview-wp-${index}`}
                  position={[waypoint.lat, waypoint.lon]}
                  icon={getWaypointIcon(waypoint.type)}
                >
                  <Popup>
                    <strong>
                      {waypoint.type === 'peak' ? '⛰️' : 
                       waypoint.type === 'hut' ? '🏠' : '📍'} {waypoint.name}
                    </strong><br />
                    {waypoint.type === 'peak' ? '山頭' : 
                     waypoint.type === 'hut' ? '山屋' : '中繼點'}<br />
                    海拔: {waypoint.elevation}m
                    {waypoint.facilities && (
                      <>
                        <br />設施: {waypoint.facilities.join(', ')}
                      </>
                    )}
                    {waypoint.required && <><br />⚠️ 必經點</>}
                  </Popup>
                </Marker>
              ))}
          </>
        )}
      </MapContainer>

      {/* Selection indicator */}
      <div style={{
        position: 'absolute',
        top: '10px',
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'white',
        padding: '8px 16px',
        borderRadius: '20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        zIndex: 1000,
        fontWeight: 500,
      }}>
        {!startPoint && '點擊地圖選擇起點 📍'}
        {startPoint && !endPoint && !isLoop && '點擊地圖選擇終點 🏁'}
        {startPoint && isLoop && '環形路線模式 🔄'}
      </div>

      {/* Layer Switcher */}
      <div style={{
        position: 'absolute',
        top: '10px',
        right: '10px',
        background: 'white',
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        zIndex: 1000,
        overflow: 'hidden'
      }}>
        <button
          onClick={() => setMapLayer('standard')}
          style={{
            display: 'block',
            width: '100%',
            padding: '8px 12px',
            border: 'none',
            background: mapLayer === 'standard' ? '#2563eb' : 'white',
            color: mapLayer === 'standard' ? 'white' : '#1e293b',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: mapLayer === 'standard' ? '600' : '400',
            textAlign: 'left',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            if (mapLayer !== 'standard') e.target.style.background = '#f8fafc';
          }}
          onMouseLeave={(e) => {
            if (mapLayer !== 'standard') e.target.style.background = 'white';
          }}
        >
          🗺️ 標準地圖
        </button>
        <button
          onClick={() => setMapLayer('terrain')}
          style={{
            display: 'block',
            width: '100%',
            padding: '8px 12px',
            border: 'none',
            borderTop: '1px solid #e2e8f0',
            background: mapLayer === 'terrain' ? '#2563eb' : 'white',
            color: mapLayer === 'terrain' ? 'white' : '#1e293b',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: mapLayer === 'terrain' ? '600' : '400',
            textAlign: 'left',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            if (mapLayer !== 'terrain') e.target.style.background = '#f8fafc';
          }}
          onMouseLeave={(e) => {
            if (mapLayer !== 'terrain') e.target.style.background = 'white';
          }}
        >
          ⛰️ 地形地圖
        </button>
        <button
          onClick={() => setMapLayer('satellite')}
          style={{
            display: 'block',
            width: '100%',
            padding: '8px 12px',
            border: 'none',
            borderTop: '1px solid #e2e8f0',
            background: mapLayer === 'satellite' ? '#2563eb' : 'white',
            color: mapLayer === 'satellite' ? 'white' : '#1e293b',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: mapLayer === 'satellite' ? '600' : '400',
            textAlign: 'left',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            if (mapLayer !== 'satellite') e.target.style.background = '#f8fafc';
          }}
          onMouseLeave={(e) => {
            if (mapLayer !== 'satellite') e.target.style.background = 'white';
          }}
        >
          🛰️ 衛星影像
        </button>
      </div>
    </div>
  );
}
