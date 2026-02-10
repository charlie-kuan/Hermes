import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

export default function Map3D({
  route,
  isLoop,
  selectedRoute = null,
  selectedWaypoints = []
}) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const [isMapLoaded, setIsMapLoaded] = useState(false);
  const markersRef = useRef([]);
  const [is3DMode, setIs3DMode] = useState(false);
  const [mapStyle, setMapStyle] = useState('osm'); // 'osm', 'satellite', 'terrain'

  // Map style configurations using free open-source tiles
  const getMapStyle = (styleType) => {
    const baseConfig = {
      version: 8,
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
      sources: {
        'terrarium-dem': {
          type: 'raster-dem',
          tiles: [
            'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
          ],
          encoding: 'terrarium',
          tileSize: 256,
          maxzoom: 15
        }
      },
      terrain: {
        source: 'terrarium-dem',
        exaggeration: 1.5
      }
    };

    if (styleType === 'satellite') {
      return {
        ...baseConfig,
        sources: {
          ...baseConfig.sources,
          'satellite-tiles': {
            type: 'raster',
            tiles: [
              'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
              'https://mt2.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
              'https://mt3.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
            ],
            tileSize: 256,
            maxzoom: 20,
            attribution: '© Google'
          }
        },
        layers: [
          {
            id: 'satellite',
            type: 'raster',
            source: 'satellite-tiles'
          }
        ]
      };
    } else if (styleType === 'terrain') {
      return {
        ...baseConfig,
        sources: {
          ...baseConfig.sources,
          'topo-tiles': {
            type: 'raster',
            tiles: [
              'https://a.tile.opentopomap.org/{z}/{x}/{y}.png',
              'https://b.tile.opentopomap.org/{z}/{x}/{y}.png',
              'https://c.tile.opentopomap.org/{z}/{x}/{y}.png'
            ],
            tileSize: 256,
            maxzoom: 17,
            attribution: '© OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap'
          }
        },
        layers: [
          {
            id: 'topo',
            type: 'raster',
            source: 'topo-tiles'
          }
        ]
      };
    } else {
      // OSM
      return {
        ...baseConfig,
        sources: {
          ...baseConfig.sources,
          'osm-tiles': {
            type: 'raster',
            tiles: [
              'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
            ],
            tileSize: 256,
            maxzoom: 19,
            attribution: '© OpenStreetMap contributors'
          }
        },
        layers: [
          {
            id: 'osm',
            type: 'raster',
            source: 'osm-tiles'
          }
        ]
      };
    }
  };

  // Initialize map
  useEffect(() => {
    if (map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: getMapStyle('osm'),
      center: [120.95, 23.45],
      zoom: 13,
      pitch: 0,
      bearing: 0,
      antialias: true
    });

    // Add navigation controls
    map.current.addControl(new maplibregl.NavigationControl({
      visualizePitch: true,
      showCompass: true
    }), 'top-left');

    // Add scale control
    map.current.addControl(new maplibregl.ScaleControl(), 'bottom-left');

    // Add fullscreen control
    map.current.addControl(new maplibregl.FullscreenControl(), 'top-left');

    map.current.on('load', () => {
      setIsMapLoaded(true);
    });

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, []);

  // Clear existing markers
  const clearMarkers = () => {
    markersRef.current.forEach(marker => marker.remove());
    markersRef.current = [];
  };


  // Draw route
  useEffect(() => {
    if (!map.current || !isMapLoaded || !route) return;

    // Remove existing route layer and source
    if (map.current.getLayer('route')) {
      map.current.removeLayer('route');
    }
    if (map.current.getLayer('route-outline')) {
      map.current.removeLayer('route-outline');
    }
    if (map.current.getSource('route')) {
      map.current.removeSource('route');
    }

    // Extract route coordinates
    const routeCoordinates = route.segments?.flatMap(segment => {
      if (segment.geometry && segment.geometry.length > 0) {
        return segment.geometry.map(point => [point[1] || point.lon, point[0] || point.lat]);
      }
      return [[segment.start_node.lon, segment.start_node.lat]];
    }) || [];

    if (routeCoordinates.length > 0) {
      // Add route source
      map.current.addSource('route', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'LineString',
            coordinates: routeCoordinates
          }
        }
      });

      // Add route outline
      map.current.addLayer({
        id: 'route-outline',
        type: 'line',
        source: 'route',
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': '#ffffff',
          'line-width': 6,
          'line-opacity': 0.8
        }
      });

      // Add route layer
      map.current.addLayer({
        id: 'route',
        type: 'line',
        source: 'route',
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': '#2563eb',
          'line-width': 4,
          'line-opacity': 0.9
        }
      });

      // Fit map to route bounds
      const bounds = routeCoordinates.reduce((bounds, coord) => {
        return bounds.extend(coord);
      }, new maplibregl.LngLatBounds(routeCoordinates[0], routeCoordinates[0]));

      map.current.fitBounds(bounds, {
        padding: 50,
        duration: 1000
      });
    }

    // Add waypoint markers
    if (route.waypoints && route.waypoints.length > 0) {
      route.waypoints.forEach((waypoint, index) => {
        const color = waypoint.type === 'peak' ? '#f97316' :
                     waypoint.type === 'hut' ? '#8b5cf6' : '#eab308';
        const icon = waypoint.type === 'peak' ? '⛰️' :
                    waypoint.type === 'hut' ? '🏠' : '📍';

        const el = document.createElement('div');
        el.style.cssText = `
          background-color: ${color};
          width: 28px;
          height: 28px;
          border-radius: 50%;
          border: 2px solid white;
          box-shadow: 0 2px 6px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 14px;
          cursor: pointer;
        `;
        el.textContent = icon;

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([waypoint.lon, waypoint.lat])
          .setPopup(new maplibregl.Popup({ offset: 25 })
            .setHTML(`
              <strong>${waypoint.name || waypoint.type}</strong><br/>
              類型: ${waypoint.type}<br/>
              海拔: ${waypoint.elevation?.toFixed(0)}m
              ${waypoint.amenities?.length > 0 ? `<br/>設施: ${waypoint.amenities.join(', ')}` : ''}
            `))
          .addTo(map.current);

        markersRef.current.push(marker);
      });
    }
  }, [route, isMapLoaded]);

  // Handle preview waypoints
  useEffect(() => {
    if (!map.current || !isMapLoaded || !selectedRoute || route) return;

    clearMarkers();

    // Add trailhead
    if (selectedRoute.trailhead) {
      const el = document.createElement('div');
      el.style.cssText = `
        background-color: #10b981;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        border: 3px solid white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        cursor: pointer;
      `;
      el.textContent = '🚩';

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([selectedRoute.trailhead.lon, selectedRoute.trailhead.lat])
        .setPopup(new maplibregl.Popup({ offset: 25 })
          .setHTML(`
            <strong>🚩 ${selectedRoute.trailhead.name}</strong><br/>
            登山口<br/>
            海拔: ${selectedRoute.trailhead.elevation}m
            ${selectedRoute.trailhead.facilities ? `<br/>設施: ${selectedRoute.trailhead.facilities.join(', ')}` : ''}
          `))
        .addTo(map.current);

      markersRef.current.push(marker);

      // Center on trailhead
      map.current.flyTo({
        center: [selectedRoute.trailhead.lon, selectedRoute.trailhead.lat],
        zoom: 14
      });
    }

    // Add selected waypoints
    selectedRoute.waypoints
      ?.filter(wp => selectedWaypoints.includes(wp.name))
      .forEach(waypoint => {
        const color = waypoint.type === 'peak' ? '#f97316' :
                     waypoint.type === 'hut' ? '#8b5cf6' : '#eab308';
        const icon = waypoint.type === 'peak' ? '⛰️' :
                    waypoint.type === 'hut' ? '🏠' : '📍';

        const el = document.createElement('div');
        el.style.cssText = `
          background-color: ${color};
          width: 28px;
          height: 28px;
          border-radius: 50%;
          border: 2px solid white;
          box-shadow: 0 2px 6px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 14px;
          cursor: pointer;
        `;
        el.textContent = icon;

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([waypoint.lon, waypoint.lat])
          .setPopup(new maplibregl.Popup({ offset: 25 })
            .setHTML(`
              <strong>${icon} ${waypoint.name}</strong><br/>
              ${waypoint.type === 'peak' ? '山頭' : waypoint.type === 'hut' ? '山屋' : '中繼點'}<br/>
              海拔: ${waypoint.elevation}m
              ${waypoint.facilities ? `<br/>設施: ${waypoint.facilities.join(', ')}` : ''}
              ${waypoint.required ? '<br/>⚠️ 必經點' : ''}
            `))
          .addTo(map.current);

        markersRef.current.push(marker);
      });
  }, [selectedRoute, selectedWaypoints, isMapLoaded, route]);

  // Toggle 3D mode
  const toggle3D = () => {
    if (!map.current) return;

    if (is3DMode) {
      // Switch to 2D
      map.current.easeTo({
        pitch: 0,
        bearing: 0,
        duration: 1000
      });
      setIs3DMode(false);
    } else {
      // Switch to 3D
      map.current.easeTo({
        pitch: 60,
        bearing: 0,
        duration: 1000
      });
      setIs3DMode(true);
    }
  };

  // Switch map style
  const switchMapStyle = (styleType) => {
    if (!map.current || mapStyle === styleType) return;

    setMapStyle(styleType);
    map.current.setStyle(getMapStyle(styleType));

    // Wait for style to load before marking as loaded
    map.current.once('styledata', () => {
      setIsMapLoaded(true);
    });
  };

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative' }}>
      <div ref={mapContainer} style={{ height: '100%', width: '100%' }} />

      {/* Control Panel */}
      <div style={{
        position: 'absolute',
        top: '10px',
        right: '10px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        zIndex: 1000
      }}>
        {/* 3D Toggle Button */}
        <button
          onClick={toggle3D}
          style={{
            background: is3DMode ? '#2563eb' : 'white',
            color: is3DMode ? 'white' : '#1e293b',
            border: 'none',
            padding: '10px 16px',
            borderRadius: '8px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: '600',
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
          onMouseEnter={(e) => {
            if (!is3DMode) {
              e.target.style.background = '#f8fafc';
            }
          }}
          onMouseLeave={(e) => {
            if (!is3DMode) {
              e.target.style.background = 'white';
            }
          }}
        >
          {is3DMode ? '🗻 3D 視角' : '🗺️ 2D 視角'}
        </button>

        {/* Map Style Switcher */}
        <div style={{
          background: 'white',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          overflow: 'hidden'
        }}>
          <button
            onClick={() => switchMapStyle('osm')}
            style={{
              display: 'block',
              width: '100%',
              padding: '8px 12px',
              border: 'none',
              background: mapStyle === 'osm' ? '#2563eb' : 'white',
              color: mapStyle === 'osm' ? 'white' : '#1e293b',
              cursor: 'pointer',
              fontSize: '0.875rem',
              fontWeight: mapStyle === 'osm' ? '600' : '400',
              textAlign: 'left',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              if (mapStyle !== 'osm') e.target.style.background = '#f8fafc';
            }}
            onMouseLeave={(e) => {
              if (mapStyle !== 'osm') e.target.style.background = 'white';
            }}
          >
            🗺️ 標準地圖
          </button>
          <button
            onClick={() => switchMapStyle('terrain')}
            style={{
              display: 'block',
              width: '100%',
              padding: '8px 12px',
              border: 'none',
              borderTop: '1px solid #e2e8f0',
              background: mapStyle === 'terrain' ? '#2563eb' : 'white',
              color: mapStyle === 'terrain' ? 'white' : '#1e293b',
              cursor: 'pointer',
              fontSize: '0.875rem',
              fontWeight: mapStyle === 'terrain' ? '600' : '400',
              textAlign: 'left',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              if (mapStyle !== 'terrain') e.target.style.background = '#f8fafc';
            }}
            onMouseLeave={(e) => {
              if (mapStyle !== 'terrain') e.target.style.background = 'white';
            }}
          >
            ⛰️ 地形圖
          </button>
          <button
            onClick={() => switchMapStyle('satellite')}
            style={{
              display: 'block',
              width: '100%',
              padding: '8px 12px',
              border: 'none',
              borderTop: '1px solid #e2e8f0',
              background: mapStyle === 'satellite' ? '#2563eb' : 'white',
              color: mapStyle === 'satellite' ? 'white' : '#1e293b',
              cursor: 'pointer',
              fontSize: '0.875rem',
              fontWeight: mapStyle === 'satellite' ? '600' : '400',
              textAlign: 'left',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              if (mapStyle !== 'satellite') e.target.style.background = '#f8fafc';
            }}
            onMouseLeave={(e) => {
              if (mapStyle !== 'satellite') e.target.style.background = 'white';
            }}
          >
            🛰️ 衛星影像
          </button>
        </div>
      </div>
    </div>
  );
}
