import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const POINT_ICON = { trailhead: '🚩', peak: '⛰️', hut: '🏠', campsite: '⛺' };
const POINT_LABEL = { trailhead: '登山口', peak: '山頭', hut: '山屋', campsite: '營地', intersection: '岔路' };

export default function Map3D({
  route,
  availablePoints = [],
  selectedPoints = [],
  onPointClick,
  selectedLegIndex = null,
}) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const [isMapLoaded, setIsMapLoaded] = useState(false);
  const routeMarkersRef = useRef([]);
  const areaMarkersRef = useRef([]);      // [{marker, el, pointId}]
  const areaMarkerMapRef = useRef({});    // pointId → {marker, el}
  const [is3DMode, setIs3DMode] = useState(false);
  const [mapStyle, setMapStyle] = useState('osm');

  const getMapStyle = (styleType) => {
    const base = {
      version: 8,
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
      sources: {
        'terrarium-dem': {
          type: 'raster-dem',
          tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
          encoding: 'terrarium',
          tileSize: 256,
          maxzoom: 15,
        },
      },
      terrain: { source: 'terrarium-dem', exaggeration: 1.5 },
    };

    if (styleType === 'satellite') {
      return {
        ...base,
        sources: {
          ...base.sources,
          'satellite-tiles': {
            type: 'raster',
            tiles: ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'],
            tileSize: 256, maxzoom: 20, attribution: '© Google',
          },
        },
        layers: [{ id: 'satellite', type: 'raster', source: 'satellite-tiles' }],
      };
    }
    if (styleType === 'terrain') {
      return {
        ...base,
        sources: {
          ...base.sources,
          'topo-tiles': {
            type: 'raster',
            tiles: ['https://a.tile.opentopomap.org/{z}/{x}/{y}.png'],
            tileSize: 256, maxzoom: 17,
            attribution: '© OpenStreetMap contributors, SRTM | © OpenTopoMap',
          },
        },
        layers: [{ id: 'topo', type: 'raster', source: 'topo-tiles' }],
      };
    }
    return {
      ...base,
      sources: {
        ...base.sources,
        'osm-tiles': {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256, maxzoom: 19, attribution: '© OpenStreetMap contributors',
        },
      },
      layers: [{ id: 'osm', type: 'raster', source: 'osm-tiles' }],
    };
  };

  // Initialize map
  useEffect(() => {
    if (map.current) return;
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: getMapStyle('osm'),
      center: [120.95, 23.45],
      zoom: 8,
      pitch: 0,
      bearing: 0,
      maxPitch: 85,
      antialias: true,
    });
    map.current.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-left');
    map.current.addControl(new maplibregl.ScaleControl(), 'bottom-left');
    map.current.on('load', () => setIsMapLoaded(true));
    return () => { map.current?.remove(); map.current = null; };
  }, []);

  // ── Create area markers once when area changes; fly to bounds ──
  useEffect(() => {
    if (!map.current || !isMapLoaded) return;

    // Tear down old markers
    areaMarkersRef.current.forEach(({ marker }) => marker.remove());
    areaMarkersRef.current = [];
    areaMarkerMapRef.current = {};

    if (availablePoints.length === 0) return;

    // Fly to fit area
    const bounds = availablePoints.reduce(
      (b, p) => b.extend([p.lon, p.lat]),
      new maplibregl.LngLatBounds([availablePoints[0].lon, availablePoints[0].lat], [availablePoints[0].lon, availablePoints[0].lat])
    );
    map.current.fitBounds(bounds, { padding: 80, duration: 800, maxZoom: 14 });

    availablePoints.forEach(point => {
      const icon = POINT_ICON[point.type] || '📍';
      const label = POINT_LABEL[point.type] || '節點';
      const typeColor = point.type === 'peak' ? '#f97316'
        : point.type === 'hut' ? '#a78bfa'
        : point.type === 'trailhead' ? '#4ade80'
        : '#94a3b8';

      // Outer wrapper — maplibre owns this element's inline style for positioning.
      // Never touch el.style after handing it to Marker.
      const el = document.createElement('div');

      // Inner element — we update this freely without disturbing maplibre's transform.
      const inner = document.createElement('div');
      inner.style.cssText = `
        width: 32px; height: 32px;
        border-radius: 50%;
        background: rgba(10,18,12,0.85);
        border: 2px solid ${typeColor};
        box-shadow: 0 2px 8px rgba(0,0,0,0.5);
        display: flex; align-items: center; justify-content: center;
        font-size: 14px; cursor: pointer;
        transition: transform 0.15s, background 0.15s, width 0.15s, height 0.15s;
      `;
      inner.textContent = icon;
      el.appendChild(inner);

      const popup = new maplibregl.Popup({
        offset: 20, closeButton: false, closeOnClick: false, focusAfterOpen: false,
      });

      inner.addEventListener('mouseenter', () => {
        inner.style.transform = 'scale(1.2)';
        const entry = areaMarkerMapRef.current[point.id];
        const orders = entry?.orders || [];
        popup.setHTML(`
          <div style="font-family:-apple-system,sans-serif;padding:4px 2px">
            <strong style="font-size:0.9rem">${icon} ${point.name}</strong><br/>
            <span style="font-size:0.78rem;color:#64748b">${label} · ${point.elevation}m</span>
            ${orders.length > 0 ? `<br/><span style="font-size:0.75rem;color:#10b981">順序：${orders.join(', ')}</span>` : ''}
          </div>
        `).setLngLat([point.lon, point.lat]).addTo(map.current);
      });
      inner.addEventListener('mouseleave', () => {
        inner.style.transform = '';
        popup.remove();
      });
      inner.addEventListener('click', (e) => {
        e.stopPropagation();
        if (onPointClick) onPointClick(point.id);
      });

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([point.lon, point.lat])
        .addTo(map.current);

      const entry = { marker, el, inner, orders: [] };
      areaMarkersRef.current.push(entry);
      areaMarkerMapRef.current[point.id] = entry;
    });
  }, [availablePoints, isMapLoaded]);

  // ── Update marker appearance when selection changes (no recreate, no camera move) ──
  useEffect(() => {
    if (!map.current || !isMapLoaded || availablePoints.length === 0) return;

    // Build orderMap
    const orderMap = {};
    selectedPoints.forEach((item, index) => {
      if (!orderMap[item.pointId]) orderMap[item.pointId] = [];
      orderMap[item.pointId].push(index + 1);
    });

    availablePoints.forEach(point => {
      const entry = areaMarkerMapRef.current[point.id];
      if (!entry) return;

      const orders = orderMap[point.id] || [];
      entry.orders = orders; // keep fresh for popup
      const isSelected = orders.length > 0;
      const icon = POINT_ICON[point.type] || '📍';
      const typeColor = point.type === 'peak' ? '#f97316'
        : point.type === 'hut' ? '#a78bfa'
        : point.type === 'trailhead' ? '#4ade80'
        : '#94a3b8';

      const inner = entry.inner;
      if (isSelected) {
        inner.style.width = '36px';
        inner.style.height = '36px';
        inner.style.background = '#4ade80';
        inner.style.border = '2.5px solid #fff';
        inner.style.boxShadow = '0 0 0 3px rgba(74,222,128,0.4), 0 3px 10px rgba(0,0,0,0.5)';
        inner.style.fontSize = '13px';
        inner.style.fontWeight = '800';
        inner.style.color = '#0a120c';
        inner.style.zIndex = '20';
        inner.textContent = orders.length === 1 ? String(orders[0]) : `×${orders.length}`;
      } else {
        inner.style.width = '32px';
        inner.style.height = '32px';
        inner.style.background = 'rgba(10,18,12,0.85)';
        inner.style.border = `2px solid ${typeColor}`;
        inner.style.boxShadow = '0 2px 8px rgba(0,0,0,0.5)';
        inner.style.fontSize = '14px';
        inner.style.fontWeight = '';
        inner.style.color = '';
        inner.style.zIndex = '10';
        inner.textContent = icon;
      }
    });
  }, [selectedPoints, isMapLoaded]);

  // ── Route markers (after planning) ──
  useEffect(() => {
    if (!map.current || !isMapLoaded) return;

    // Always clear previous route from map
    ['route', 'route-outline'].forEach(id => {
      if (map.current.getLayer(id)) map.current.removeLayer(id);
    });
    if (map.current.getSource('route')) map.current.removeSource('route');
    routeMarkersRef.current.forEach(m => m.remove());
    routeMarkersRef.current = [];

    if (!route) return;

    const coords = route.segments?.flatMap(seg => {
      if (seg.geometry?.length > 0) return seg.geometry.map(p => [p[1] || p.lon, p[0] || p.lat]);
      return [[seg.start_node.lon, seg.start_node.lat]];
    }) || [];

    if (coords.length > 0) {
      map.current.addSource('route', {
        type: 'geojson',
        data: { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } },
      });
      map.current.addLayer({ id: 'route-outline', type: 'line', source: 'route',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#ffffff', 'line-width': 6, 'line-opacity': 0.7 },
      });
      map.current.addLayer({ id: 'route', type: 'line', source: 'route',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#ef4444', 'line-width': 4, 'line-opacity': 0.95 },
      });

      const bounds = coords.reduce((b, c) => b.extend(c),
        new maplibregl.LngLatBounds(coords[0], coords[0]));
      map.current.fitBounds(bounds, { padding: 60, duration: 1000 });
    }

  }, [route, isMapLoaded]);

  // ── Highlight selected leg ──
  useEffect(() => {
    if (!map.current || !isMapLoaded || !route) return;

    const leg = selectedLegIndex !== null ? route.legs?.[selectedLegIndex] : null;

    if (leg) {
      // Highlight coords from the leg's segment range
      const legSegs = route.segments.slice(leg.segment_start, leg.segment_end + 1);
      const highlightCoords = legSegs.flatMap(seg => {
        if (seg.geometry?.length > 0) return seg.geometry.map(p => [p[1] || p.lon, p[0] || p.lat]);
        return [[seg.start_node.lon, seg.start_node.lat]];
      });

      // Dim full route
      if (map.current.getLayer('route')) map.current.setPaintProperty('route', 'line-opacity', 0.2);
      if (map.current.getLayer('route-outline')) map.current.setPaintProperty('route-outline', 'line-opacity', 0.15);

      // Add or update highlight layer
      const hlGeoJSON = { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: highlightCoords } };
      if (map.current.getSource('route-highlight')) {
        map.current.getSource('route-highlight').setData(hlGeoJSON);
      } else {
        map.current.addSource('route-highlight', { type: 'geojson', data: hlGeoJSON });
        map.current.addLayer({ id: 'route-highlight-outline', type: 'line', source: 'route-highlight',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: { 'line-color': '#ffffff', 'line-width': 8, 'line-opacity': 0.8 },
        });
        map.current.addLayer({ id: 'route-highlight', type: 'line', source: 'route-highlight',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: { 'line-color': '#f59e0b', 'line-width': 5, 'line-opacity': 1 },
        });
      }

      // FlyTo leg bounds
      if (highlightCoords.length > 0) {
        const bounds = highlightCoords.reduce((b, c) => b.extend(c),
          new maplibregl.LngLatBounds(highlightCoords[0], highlightCoords[0]));
        map.current.fitBounds(bounds, { padding: 160, duration: 800, maxZoom: 13 });
      }
    } else {
      // Restore full route opacity
      if (map.current.getLayer('route')) map.current.setPaintProperty('route', 'line-opacity', 0.95);
      if (map.current.getLayer('route-outline')) map.current.setPaintProperty('route-outline', 'line-opacity', 0.7);

      // Remove highlight layers
      ['route-highlight', 'route-highlight-outline'].forEach(id => {
        if (map.current.getLayer(id)) map.current.removeLayer(id);
      });
      if (map.current.getSource('route-highlight')) map.current.removeSource('route-highlight');
    }
  }, [selectedLegIndex, route, isMapLoaded]);

  const toggle3D = () => {
    if (!map.current) return;
    map.current.easeTo({ pitch: is3DMode ? 0 : 60, bearing: 0, duration: 800 });
    setIs3DMode(!is3DMode);
  };

  const switchMapStyle = (styleType) => {
    if (!map.current || mapStyle === styleType) return;
    setMapStyle(styleType);
    setIsMapLoaded(false);
    map.current.setStyle(getMapStyle(styleType));
    map.current.once('styledata', () => setIsMapLoaded(true));
  };

  // Map controls dark style
  const ctrlBase = {
    display: 'block', width: '100%', padding: '8px 14px', border: 'none',
    cursor: 'pointer', fontSize: '0.82rem', textAlign: 'left', transition: 'all 0.15s',
  };

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative' }}>
      <div ref={mapContainer} style={{ height: '100%', width: '100%' }} />

      {/* Map controls */}
      <div className="map-controls">
        <button
          className={`map-ctrl-btn map-ctrl-3d${is3DMode ? ' active' : ''}`}
          onClick={toggle3D}
        >
          {is3DMode ? '🗻 3D' : '🗺 2D'}
        </button>
        <div className="map-ctrl-group">
          {[
            { key: 'osm', label: '🗺 標準地圖' },
            { key: 'terrain', label: '⛰️ 地形圖' },
            { key: 'satellite', label: '🛰 衛星影像' },
          ].map(({ key, label }, i) => (
            <button
              key={key}
              className={`map-ctrl-style${mapStyle === key ? ' active' : ''}${i > 0 ? ' sep' : ''}`}
              onClick={() => switchMapStyle(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
