import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const api = (path) => `${API_BASE}/api/v1${path}`;

const DIFFICULTY_OPTIONS = ['簡易', '中等', '困難', '非常困難', '極度困難'];
const POINT_TYPES = ['trailhead', 'shelter', 'peak', 'waypoint', 'water'];
const TYPE_LABELS = { trailhead: '登山口', shelter: '住宿/營地', peak: '山峰', waypoint: '中繼點', water: '水源' };

const emptyPoint = () => ({ id: '', name: '', type: 'peak', lat: '', lon: '', elevation: '', description: '', facilities: [], capacity: '' });
const emptyRoute = () => ({ route_id: '', name: '', description: '', days: 1, difficulty: '中等', estimated_distance: '', estimated_time: '', point_sequence: [], highlight: '' });
const emptyArea = () => ({ area_id: '', name: '', description: '' });

function typeBadgeColor(type) {
  return { trailhead: '#7c3aed', shelter: '#d97706', peak: '#dc2626', waypoint: '#0891b2', water: '#1d4ed8' }[type] || '#6b7280';
}
function diffBadgeColor(d) {
  return { '簡易': '#15803d', '中等': '#0891b2', '困難': '#d97706', '非常困難': '#dc2626', '極度困難': '#7c3aed' }[d] || '#6b7280';
}

// ─── Main Admin Panel ─────────────────────────────────────────────────────────

export default function AdminPanel({ onClose }) {
  const [areas, setAreas] = useState([]);
  const [selectedAreaId, setSelectedAreaId] = useState(null);
  const [points, setPoints] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [tab, setTab] = useState('points');
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  // Inline editing state (shown in side panel, not modal)
  const [editingPoint, setEditingPoint] = useState(null);  // null = not editing
  const [editingRoute, setEditingRoute] = useState(null);
  const [areaModal, setAreaModal] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  // Map: which point is "pending placement" (newly added, waiting for click)
  const [placingPoint, setPlacingPoint] = useState(false);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const loadAreas = useCallback(async () => {
    try {
      const res = await axios.get(api('/admin/areas'));
      setAreas(res.data.areas || []);
    } catch { showToast('無法載入區域', 'error'); }
  }, []);

  const loadPoints = useCallback(async (areaId) => {
    if (!areaId) return;
    try {
      const res = await axios.get(api(`/admin/areas/${areaId}/points`));
      setPoints(res.data.points || []);
    } catch { showToast('無法載入點位', 'error'); }
  }, []);

  const loadRoutes = useCallback(async (areaId) => {
    if (!areaId) return;
    try {
      const res = await axios.get(api(`/admin/areas/${areaId}/routes`));
      setRoutes(res.data.routes || []);
    } catch { showToast('無法載入路線', 'error'); }
  }, []);

  useEffect(() => { loadAreas(); }, [loadAreas]);
  useEffect(() => {
    setEditingPoint(null);
    setEditingRoute(null);
    if (selectedAreaId) { loadPoints(selectedAreaId); loadRoutes(selectedAreaId); }
  }, [selectedAreaId, loadPoints, loadRoutes]);

  // ── Area CRUD ──
  const handleSaveArea = async (form) => {
    setLoading(true);
    try {
      const exists = areas.find(a => a.area_id === form.area_id);
      if (exists) await axios.put(api(`/admin/areas/${form.area_id}`), { name: form.name, description: form.description });
      else await axios.post(api('/admin/areas'), form);
      showToast(exists ? '區域已更新' : '區域已新增');
      setAreaModal(null);
      await loadAreas();
    } catch (e) { showToast(e.response?.data?.detail || '儲存失敗', 'error'); }
    finally { setLoading(false); }
  };

  const handleDeleteArea = async (area_id) => {
    setLoading(true);
    try {
      await axios.delete(api(`/admin/areas/${area_id}`));
      showToast('區域已刪除');
      if (selectedAreaId === area_id) setSelectedAreaId(null);
      await loadAreas();
    } catch (e) { showToast(e.response?.data?.detail || '刪除失敗', 'error'); }
    finally { setLoading(false); setDeleteConfirm(null); }
  };

  // ── Point CRUD ──
  const handleSavePoint = async (form) => {
    setLoading(true);
    try {
      const { _idManual, _existing, ...rest } = form;
      const lat = parseFloat(rest.lat);
      const lon = parseFloat(rest.lon);
      const elevation = parseFloat(rest.elevation);
      if (!rest.id) { showToast('請填寫點位名稱', 'error'); return; }
      if (isNaN(lat) || isNaN(lon)) { showToast('請在地圖上點選座標', 'error'); return; }
      if (isNaN(elevation)) { showToast('請填寫海拔', 'error'); return; }
      const payload = {
        ...rest,
        lat,
        lon,
        elevation,
        capacity: rest.capacity ? parseInt(rest.capacity) : null,
        facilities: typeof rest.facilities === 'string' ? rest.facilities.split(';').filter(Boolean) : (rest.facilities || []),
      };
      await axios.post(api(`/admin/areas/${selectedAreaId}/points`), payload);
      showToast('點位已儲存');
      setEditingPoint(null);
      setPlacingPoint(false);
      await loadPoints(selectedAreaId);
    } catch (e) { showToast(e.response?.data?.detail || '儲存失敗', 'error'); }
    finally { setLoading(false); }
  };

  const handleDeletePoint = async (point_id) => {
    setLoading(true);
    try {
      await axios.delete(api(`/admin/areas/${selectedAreaId}/points/${point_id}`));
      showToast('點位已刪除');
      if (editingPoint?.id === point_id) setEditingPoint(null);
      await loadPoints(selectedAreaId);
    } catch (e) { showToast(e.response?.data?.detail || '刪除失敗', 'error'); }
    finally { setLoading(false); setDeleteConfirm(null); }
  };

  // ── Route CRUD ──
  const handleSaveRoute = async (form) => {
    setLoading(true);
    try {
      const { _idManual, ...rest } = form;
      if (!rest.route_id) { showToast('請填寫路線名稱', 'error'); return; }
      const payload = {
        ...rest,
        days: parseInt(rest.days) || 1,
        estimated_distance: rest.estimated_distance ? parseFloat(rest.estimated_distance) : null,
        point_sequence: Array.isArray(rest.point_sequence) ? rest.point_sequence : (rest.point_sequence || '').split('>').filter(Boolean),
      };
      await axios.post(api(`/admin/areas/${selectedAreaId}/routes`), payload);
      showToast('路線已儲存');
      setEditingRoute(null);
      await loadRoutes(selectedAreaId);
    } catch (e) { showToast(e.response?.data?.detail || '儲存失敗', 'error'); }
    finally { setLoading(false); }
  };

  const handleDeleteRoute = async (route_id) => {
    setLoading(true);
    try {
      await axios.delete(api(`/admin/areas/${selectedAreaId}/routes/${route_id}`));
      showToast('路線已刪除');
      if (editingRoute?.route_id === route_id) setEditingRoute(null);
      await loadRoutes(selectedAreaId);
    } catch (e) { showToast(e.response?.data?.detail || '刪除失敗', 'error'); }
    finally { setLoading(false); setDeleteConfirm(null); }
  };

  // Map click handler: set lat/lon on editing point
  const handleMapClick = useCallback((lat, lon) => {
    setEditingPoint(p => p ? { ...p, lat: lat.toFixed(6), lon: lon.toFixed(6) } : p);
  }, []);

  // Route map: clicking a point marker adds it to sequence
  const handleRoutePointClick = useCallback((pid) => {
    setEditingRoute(r => r ? {
      ...r,
      point_sequence: r.point_sequence.includes(pid)
        ? r.point_sequence
        : [...r.point_sequence, pid],
    } : r);
  }, []);

  const selectedArea = areas.find(a => a.area_id === selectedAreaId);
  const isEditingPoint = editingPoint !== null;
  const isEditingRoute = editingRoute !== null;
  const sidePanel = isEditingPoint || isEditingRoute;

  return (
    <div style={S.root}>
      {/* ── Header ── */}
      <div style={S.header}>
        <div>
          <span style={{ fontWeight: 700, fontSize: '1.1rem' }}>⚙️ 管理後台</span>
          <span style={{ marginLeft: 12, opacity: 0.7, fontSize: '0.85rem' }}>點位 · 路線 · 區域維護</span>
        </div>
        <button style={S.closeBtn} onClick={onClose}>✕ 關閉</button>
      </div>

      {/* ── Body ── */}
      <div style={S.body}>
        {/* Left: area list */}
        <div style={S.areaCol}>
          <div style={S.areaColHeader}>
            <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>區域</span>
            <button style={S.btnSm} onClick={() => setAreaModal(emptyArea())}>+ 新增</button>
          </div>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {areas.map(a => (
              <div key={a.area_id}
                style={{ ...S.areaItem, ...(selectedAreaId === a.area_id ? S.areaItemActive : {}) }}
                onClick={() => setSelectedAreaId(a.area_id)}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.82rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.name}</div>
                  <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>{a.point_count}點 · {a.route_count}路線</div>
                </div>
                <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                  <button style={S.iconBtn} onClick={e => { e.stopPropagation(); setAreaModal({ ...a }); }}>✏️</button>
                  <button style={S.iconBtn} onClick={e => {
                    e.stopPropagation();
                    setDeleteConfirm({ label: a.name, onConfirm: () => handleDeleteArea(a.area_id) });
                  }}>🗑️</button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Center: map + table */}
        {!selectedAreaId ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: '0.95rem' }}>
            ← 選擇左側區域開始編輯
          </div>
        ) : (
          <div style={S.centerCol}>
            {/* Tabs */}
            <div style={S.tabBar}>
              <div style={{ display: 'flex', gap: 4 }}>
                <button style={{ ...S.tab, ...(tab === 'points' ? S.tabActive : {}) }} onClick={() => { setTab('points'); setEditingRoute(null); }}>
                  📍 點位 ({points.length})
                </button>
                <button style={{ ...S.tab, ...(tab === 'routes' ? S.tabActive : {}) }} onClick={() => { setTab('routes'); setEditingPoint(null); }}>
                  🗺️ 路線 ({routes.length})
                </button>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>{selectedArea?.name}</span>
                {tab === 'points' && !isEditingPoint && (
                  <button style={S.btnPrimary} onClick={() => setEditingPoint(emptyPoint())}>+ 新增點位</button>
                )}
                {tab === 'routes' && !isEditingRoute && (
                  <button style={S.btnPrimary} onClick={() => setEditingRoute(emptyRoute())}>+ 新增路線</button>
                )}
                {(isEditingPoint || isEditingRoute) && (
                  <button style={S.btnGhost} onClick={() => { setEditingPoint(null); setEditingRoute(null); }}>取消編輯</button>
                )}
              </div>
            </div>

            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
              {/* Map */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                <AdminMap
                  points={points}
                  editingPoint={editingPoint}
                  editingRoute={editingRoute}
                  tab={tab}
                  onMapClick={handleMapClick}
                  onPointMarkerClick={tab === 'routes' ? handleRoutePointClick : (p) => setEditingPoint({
                    ...p,
                    facilities: Array.isArray(p.facilities) ? p.facilities.join(';') : (p.facilities || ''),
                  })}
                />

                {/* Table below map */}
                <div style={S.tableWrap}>
                  {tab === 'points' && (
                    <PointsTable
                      points={points}
                      editingId={editingPoint?.id}
                      onEdit={p => setEditingPoint({ ...p, facilities: Array.isArray(p.facilities) ? p.facilities.join(';') : (p.facilities || '') })}
                      onDelete={p => setDeleteConfirm({ label: p.name, onConfirm: () => handleDeletePoint(p.id) })}
                    />
                  )}
                  {tab === 'routes' && (
                    <RoutesTable
                      routes={routes}
                      points={points}
                      editingId={editingRoute?.route_id}
                      onEdit={r => setEditingRoute({
                        ...r,
                        point_sequence: typeof r.point_sequence === 'string' ? r.point_sequence.split('>').filter(Boolean) : (r.point_sequence || []),
                      })}
                      onDelete={r => setDeleteConfirm({ label: r.name, onConfirm: () => handleDeleteRoute(r.route_id) })}
                    />
                  )}
                </div>
              </div>

              {/* Side edit panel */}
              {sidePanel && (
                <div style={S.sidePanel}>
                  {isEditingPoint && (
                    <PointForm
                      data={editingPoint}
                      onChange={setEditingPoint}
                      onSave={handleSavePoint}
                      onCancel={() => { setEditingPoint(null); setPlacingPoint(false); }}
                      loading={loading}
                    />
                  )}
                  {isEditingRoute && (
                    <RouteForm
                      data={editingRoute}
                      points={points}
                      onChange={setEditingRoute}
                      onSave={handleSaveRoute}
                      onCancel={() => setEditingRoute(null)}
                      loading={loading}
                    />
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Toast */}
      {toast && <div style={{ ...S.toast, background: toast.type === 'error' ? '#ef4444' : '#10b981' }}>{toast.msg}</div>}

      {/* Area Modal */}
      {areaModal && (
        <SimpleModal title={areas.some(a => a.area_id === areaModal.area_id) ? '編輯區域' : '新增區域'} onClose={() => setAreaModal(null)}>
          <AreaForm data={areaModal} isEdit={areas.some(a => a.area_id === areaModal.area_id)} onSave={handleSaveArea} onClose={() => setAreaModal(null)} loading={loading} />
        </SimpleModal>
      )}

      {deleteConfirm && (
        <SimpleModal title="確認刪除" onClose={() => setDeleteConfirm(null)}>
          <p style={{ marginBottom: 16 }}>確定要刪除「<strong>{deleteConfirm.label}</strong>」嗎？此操作無法復原。</p>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button style={S.btnGhost} onClick={() => setDeleteConfirm(null)}>取消</button>
            <button style={{ ...S.btnPrimary, background: '#ef4444' }} onClick={deleteConfirm.onConfirm} disabled={loading}>
              {loading ? '刪除中...' : '確認刪除'}
            </button>
          </div>
        </SimpleModal>
      )}
    </div>
  );
}

// ─── Map Component ────────────────────────────────────────────────────────────

function AdminMap({ points, editingPoint, editingRoute, tab, onMapClick, onPointMarkerClick }) {
  const mapRef = useRef(null);
  const leafletRef = useRef(null);
  const markersRef = useRef([]);
  const lineRef = useRef(null);
  const editMarkerRef = useRef(null);

  useEffect(() => {
    if (leafletRef.current) return;
    const map = L.map(mapRef.current, { zoomControl: true }).setView([23.8, 121.0], 9);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors', maxZoom: 19,
    }).addTo(map);
    map.on('click', e => onMapClick(e.latlng.lat, e.latlng.lng));
    leafletRef.current = map;
    return () => { map.remove(); leafletRef.current = null; };
  }, []);

  // Update click handler ref (avoid stale closure)
  useEffect(() => {
    const map = leafletRef.current;
    if (!map) return;
    map.off('click');
    map.on('click', e => onMapClick(e.latlng.lat, e.latlng.lng));
  }, [onMapClick]);

  // Render point markers
  useEffect(() => {
    const map = leafletRef.current;
    if (!map) return;
    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];

    const seqIds = editingRoute
      ? (typeof editingRoute.point_sequence === 'string'
        ? editingRoute.point_sequence.split('>').filter(Boolean)
        : editingRoute.point_sequence || [])
      : [];

    const validPoints = points.filter(p => p.lat && p.lon && !isNaN(parseFloat(p.lat)));

    validPoints.forEach(p => {
      const seqIdx = seqIds.indexOf(p.id);
      const isEditing = editingPoint?.id === p.id;
      const color = isEditing ? '#f59e0b' : (seqIdx >= 0 ? '#2563eb' : typeBadgeColor(p.type));
      const label = seqIdx >= 0 ? `${seqIdx + 1}` : '';
      const size = isEditing ? 26 : 20;

      const icon = L.divIcon({
        html: `<div style="width:${size}px;height:${size}px;background:${color};border:2.5px solid white;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:white;cursor:pointer">${label}</div>`,
        iconSize: [size, size], iconAnchor: [size / 2, size / 2], className: '',
      });
      const m = L.marker([parseFloat(p.lat), parseFloat(p.lon)], { icon })
        .bindTooltip(`${p.name}${tab === 'routes' ? ' (點擊加入路線)' : ' (點擊編輯)'}`, { direction: 'top', offset: [0, -size / 2] })
        .on('click', e => { e.originalEvent.stopPropagation(); onPointMarkerClick(tab === 'routes' ? p.id : p); })
        .addTo(map);
      markersRef.current.push(m);
    });

    // Fit bounds on first load
    if (validPoints.length > 0 && !leafletRef.current._hermesFitted) {
      const bounds = L.latLngBounds(validPoints.map(p => [parseFloat(p.lat), parseFloat(p.lon)]));
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
      leafletRef.current._hermesFitted = true;
    }
  }, [points, editingPoint?.id, editingRoute?.point_sequence, tab]);

  // Draw route polyline
  useEffect(() => {
    const map = leafletRef.current;
    if (!map) return;
    if (lineRef.current) { lineRef.current.remove(); lineRef.current = null; }
    if (!editingRoute) return;
    const seqIds = typeof editingRoute.point_sequence === 'string'
      ? editingRoute.point_sequence.split('>').filter(Boolean)
      : (editingRoute.point_sequence || []);
    const pointMap = Object.fromEntries(points.map(p => [p.id, p]));
    const coords = seqIds.map(pid => pointMap[pid]).filter(p => p?.lat && !isNaN(parseFloat(p.lat))).map(p => [parseFloat(p.lat), parseFloat(p.lon)]);
    if (coords.length > 1) {
      lineRef.current = L.polyline(coords, { color: '#2563eb', weight: 4, opacity: 0.8, dashArray: '8,5' }).addTo(map);
    }
  }, [editingRoute?.point_sequence, points]);

  // Move editing point marker
  useEffect(() => {
    const map = leafletRef.current;
    if (!map) return;
    if (editMarkerRef.current) { editMarkerRef.current.remove(); editMarkerRef.current = null; }
    if (!editingPoint || !editingPoint.lat || !editingPoint.lon || isNaN(parseFloat(editingPoint.lat))) return;
    const icon = L.divIcon({
      html: `<div style="width:28px;height:28px;background:#f59e0b;border:3px solid white;border-radius:50%;box-shadow:0 3px 10px rgba(0,0,0,0.5);animation:pulse 1s infinite alternate"></div>`,
      iconSize: [28, 28], iconAnchor: [14, 14], className: '',
    });
    editMarkerRef.current = L.marker([parseFloat(editingPoint.lat), parseFloat(editingPoint.lon)], { icon })
      .bindTooltip(editingPoint.name || '新點位', { permanent: true, direction: 'top', offset: [0, -16] })
      .addTo(map);
  }, [editingPoint?.lat, editingPoint?.lon, editingPoint?.name]);

  const hint = editingPoint
    ? '點擊地圖設定座標（橘色標記會移動）'
    : editingRoute
    ? '點擊標記將點位加入路線序列'
    : '點擊標記來編輯點位';

  return (
    <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
      <div ref={mapRef} style={{ width: '100%', height: '100%' }} />
      <div style={S.mapHint}>{hint}</div>
    </div>
  );
}

// ─── Point Form (side panel) ──────────────────────────────────────────────────

function slugify(name) {
  return name
    .trim()
    .toLowerCase()
    .replace(/[\s　]+/g, '_')
    .replace(/[^\w一-鿿]/g, '')
    .slice(0, 40);
}

function PointForm({ data, onChange, onSave, onCancel, loading }) {
  const set = (k, v) => onChange(p => ({ ...p, [k]: v }));

  const handleNameChange = (name) => {
    onChange(p => ({
      ...p,
      name,
      // Only auto-fill ID if user hasn't manually edited it yet
      id: p._idManual ? p.id : slugify(name),
    }));
  };
  const isNew = !data._existing;
  return (
    <div style={S.editForm}>
      <div style={S.editFormTitle}>{data.id && data._existing ? '編輯點位' : '新增點位'}</div>
      <F label="名稱"><input style={S.inp} value={data.name} onChange={e => handleNameChange(e.target.value)} autoFocus /></F>
      <F label="ID（自動產生，可手動修改）">
        <input style={{ ...S.inp, color: '#6b7280', fontSize: '0.78rem' }}
          value={data.id}
          onChange={e => onChange(p => ({ ...p, id: e.target.value, _idManual: true }))}
          placeholder="自動從名稱產生"
        />
      </F>
      <F label="類型">
        <select style={S.inp} value={data.type} onChange={e => set('type', e.target.value)}>
          {POINT_TYPES.map(t => <option key={t} value={t}>{TYPE_LABELS[t] || t}</option>)}
        </select>
      </F>
      <F label="海拔(m)"><input style={S.inp} type="number" value={data.elevation} onChange={e => set('elevation', e.target.value)} /></F>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <F label="緯度"><input style={S.inp} type="number" step="0.0001" value={data.lat} onChange={e => set('lat', e.target.value)} /></F>
        <F label="經度"><input style={S.inp} type="number" step="0.0001" value={data.lon} onChange={e => set('lon', e.target.value)} /></F>
      </div>
      <div style={{ fontSize: '0.72rem', color: '#0891b2', background: '#e0f2fe', padding: '5px 8px', borderRadius: 5, marginBottom: 8 }}>
        ← 直接點地圖設定座標
      </div>
      <F label="設施 (分號分隔)"><input style={S.inp} value={data.facilities} onChange={e => set('facilities', e.target.value)} placeholder="住宿;廁所;用水" /></F>
      <F label="容量"><input style={S.inp} type="number" value={data.capacity} onChange={e => set('capacity', e.target.value)} /></F>
      <F label="描述"><textarea style={{ ...S.inp, height: 60, resize: 'vertical' }} value={data.description} onChange={e => set('description', e.target.value)} /></F>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button style={S.btnGhost} onClick={onCancel}>取消</button>
        <button style={{ ...S.btnPrimary, flex: 1 }} onClick={() => onSave(data)} disabled={loading}>
          {loading ? '儲存中...' : '儲存點位'}
        </button>
      </div>
    </div>
  );
}

// ─── Route Form (side panel) ──────────────────────────────────────────────────

function RouteForm({ data, points, onChange, onSave, onCancel, loading }) {
  const set = (k, v) => onChange(r => ({ ...r, [k]: v }));
  const seq = typeof data.point_sequence === 'string'
    ? data.point_sequence.split('>').filter(Boolean)
    : (data.point_sequence || []);
  const pointMap = Object.fromEntries(points.map(p => [p.id, p]));

  const removeFromSeq = (idx) => set('point_sequence', seq.filter((_, i) => i !== idx));
  const moveSeq = (idx, dir) => {
    const arr = [...seq];
    const t = idx + dir;
    if (t < 0 || t >= arr.length) return;
    [arr[idx], arr[t]] = [arr[t], arr[idx]];
    set('point_sequence', arr);
  };

  return (
    <div style={S.editForm}>
      <div style={S.editFormTitle}>{data.route_id ? '編輯路線' : '新增路線'}</div>
      <F label="名稱">
        <input style={S.inp} value={data.name} autoFocus onChange={e => {
          const name = e.target.value;
          onChange(r => ({ ...r, name, route_id: r._idManual ? r.route_id : slugify(name) }));
        }} />
      </F>
      <F label="ID（自動產生，可手動修改）">
        <input style={{ ...S.inp, color: '#6b7280', fontSize: '0.78rem' }}
          value={data.route_id}
          onChange={e => onChange(r => ({ ...r, route_id: e.target.value, _idManual: true }))}
          placeholder="自動從名稱產生"
        />
      </F>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <F label="天數"><input style={S.inp} type="number" min="1" value={data.days} onChange={e => set('days', e.target.value)} /></F>
        <F label="難度">
          <select style={S.inp} value={data.difficulty} onChange={e => set('difficulty', e.target.value)}>
            {DIFFICULTY_OPTIONS.map(d => <option key={d}>{d}</option>)}
          </select>
        </F>
        <F label="距離(km)"><input style={S.inp} type="number" step="0.1" value={data.estimated_distance} onChange={e => set('estimated_distance', e.target.value)} /></F>
        <F label="估計時間"><input style={S.inp} value={data.estimated_time} onChange={e => set('estimated_time', e.target.value)} placeholder="10-12小時" /></F>
      </div>
      <F label="亮點"><input style={S.inp} value={data.highlight} onChange={e => set('highlight', e.target.value)} /></F>

      <div style={{ fontWeight: 600, fontSize: '0.78rem', color: '#374151', marginBottom: 4, marginTop: 4 }}>路線序列</div>
      <div style={{ fontSize: '0.72rem', color: '#0891b2', background: '#e0f2fe', padding: '5px 8px', borderRadius: 5, marginBottom: 6 }}>
        ← 點地圖上的標記依序加入
      </div>
      <div style={S.seqList}>
        {seq.map((pid, i) => {
          const p = pointMap[pid];
          return (
            <div key={i} style={S.seqItem}>
              <span style={{ fontSize: '0.72rem', color: '#2563eb', fontWeight: 700, minWidth: 18 }}>{i + 1}.</span>
              <span style={{ flex: 1, fontSize: '0.8rem' }}>{p?.name || pid}</span>
              <div style={{ display: 'flex', gap: 2 }}>
                <button style={S.seqBtn} onClick={() => moveSeq(i, -1)} disabled={i === 0}>↑</button>
                <button style={S.seqBtn} onClick={() => moveSeq(i, 1)} disabled={i === seq.length - 1}>↓</button>
                <button style={{ ...S.seqBtn, color: '#ef4444' }} onClick={() => removeFromSeq(i)}>✕</button>
              </div>
            </div>
          );
        })}
        {seq.length === 0 && <div style={{ color: '#94a3b8', fontSize: '0.8rem', padding: '8px 0' }}>尚未選擇點位</div>}
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <button style={S.btnGhost} onClick={onCancel}>取消</button>
        <button style={{ ...S.btnPrimary, flex: 1 }} onClick={() => onSave(data)} disabled={loading}>
          {loading ? '儲存中...' : '儲存路線'}
        </button>
      </div>
    </div>
  );
}

// ─── Tables ───────────────────────────────────────────────────────────────────

function PointsTable({ points, editingId, onEdit, onDelete }) {
  return (
    <table style={S.table}>
      <thead>
        <tr>{['名稱', '類型', '海拔(m)', '座標', '設施', '操作'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr>
      </thead>
      <tbody>
        {points.map(p => (
          <tr key={p.id} style={{ ...S.tr, background: p.id === editingId ? '#fef9c3' : undefined }}>
            <td style={S.td}><div style={{ fontWeight: 600, fontSize: '0.83rem' }}>{p.name}</div><div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>{p.id}</div></td>
            <td style={S.td}><span style={{ ...S.badge, background: typeBadgeColor(p.type) }}>{TYPE_LABELS[p.type] || p.type}</span></td>
            <td style={S.td}>{p.elevation}</td>
            <td style={S.td} title={`${p.lat}, ${p.lon}`}><span style={{ fontSize: '0.75rem', color: '#475569' }}>{parseFloat(p.lat).toFixed(4)}, {parseFloat(p.lon).toFixed(4)}</span></td>
            <td style={S.td}><span style={{ fontSize: '0.75rem' }}>{p.facilities || '-'}</span></td>
            <td style={S.td}>
              <button style={S.iconBtn} onClick={() => onEdit(p)}>✏️</button>
              <button style={S.iconBtn} onClick={() => onDelete(p)}>🗑️</button>
            </td>
          </tr>
        ))}
        {points.length === 0 && <tr><td colSpan={6} style={{ ...S.td, textAlign: 'center', color: '#94a3b8', padding: 20 }}>尚無點位，點擊「+ 新增點位」或直接在地圖上點擊標記來選取</td></tr>}
      </tbody>
    </table>
  );
}

function RoutesTable({ routes, points, editingId, onEdit, onDelete }) {
  const pointNameMap = Object.fromEntries(points.map(p => [p.id, p.name]));
  return (
    <table style={S.table}>
      <thead>
        <tr>{['路線名稱', '天數', '難度', '距離', '點位序列', '操作'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr>
      </thead>
      <tbody>
        {routes.map(r => {
          const seq = typeof r.point_sequence === 'string' ? r.point_sequence.split('>').filter(Boolean) : (r.point_sequence || []);
          return (
            <tr key={r.route_id} style={{ ...S.tr, background: r.route_id === editingId ? '#fef9c3' : undefined }}>
              <td style={S.td}><div style={{ fontWeight: 600, fontSize: '0.83rem' }}>{r.name}</div><div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>{r.route_id}</div></td>
              <td style={S.td}>{r.days} 天</td>
              <td style={S.td}><span style={{ ...S.badge, background: diffBadgeColor(r.difficulty) }}>{r.difficulty}</span></td>
              <td style={S.td}>{r.estimated_distance ? `${r.estimated_distance}km` : '-'}</td>
              <td style={{ ...S.td, maxWidth: 200 }}>
                <div style={{ fontSize: '0.73rem', color: '#475569', lineHeight: 1.5 }}>
                  {seq.map((pid, i) => <span key={i}>{i > 0 && <span style={{ color: '#94a3b8', margin: '0 2px' }}>›</span>}<span title={pid}>{pointNameMap[pid] || pid}</span></span>)}
                </div>
              </td>
              <td style={S.td}>
                <button style={S.iconBtn} onClick={() => onEdit(r)}>✏️</button>
                <button style={S.iconBtn} onClick={() => onDelete(r)}>🗑️</button>
              </td>
            </tr>
          );
        })}
        {routes.length === 0 && <tr><td colSpan={6} style={{ ...S.td, textAlign: 'center', color: '#94a3b8', padding: 20 }}>尚無路線，點擊「+ 新增路線」開始設計</td></tr>}
      </tbody>
    </table>
  );
}

// ─── Area Form (modal) ────────────────────────────────────────────────────────

function AreaForm({ data, isEdit, onSave, onClose, loading }) {
  const [form, setForm] = useState({ ...data });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  return (
    <>
      <F label="區域ID (英文)"><input style={S.inp} value={form.area_id} disabled={isEdit} onChange={e => set('area_id', e.target.value)} placeholder="e.g. yushan" /></F>
      <F label="名稱"><input style={S.inp} value={form.name} onChange={e => set('name', e.target.value)} /></F>
      <F label="描述"><textarea style={{ ...S.inp, height: 70 }} value={form.description} onChange={e => set('description', e.target.value)} /></F>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
        <button style={S.btnGhost} onClick={onClose}>取消</button>
        <button style={S.btnPrimary} onClick={() => onSave(form)} disabled={loading}>{loading ? '儲存中...' : '儲存'}</button>
      </div>
    </>
  );
}

function SimpleModal({ title, children, onClose }) {
  return (
    <div style={S.modalOverlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={S.modal}>
        <div style={S.modalHeader}>
          <span style={{ fontWeight: 700 }}>{title}</span>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem' }} onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: '16px 20px' }}>{children}</div>
      </div>
    </div>
  );
}

function F({ label, children }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#374151', marginBottom: 3 }}>{label}</label>
      {children}
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const S = {
  root: { position: 'fixed', inset: 0, background: '#f1f5f9', zIndex: 1000, display: 'flex', flexDirection: 'column', fontFamily: "-apple-system, 'Microsoft JhengHei', sans-serif" },
  header: { background: 'linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%)', color: 'white', padding: '10px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 },
  closeBtn: { background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.3)', color: 'white', padding: '5px 14px', borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' },
  body: { display: 'flex', flex: 1, overflow: 'hidden' },
  // Area column
  areaCol: { width: 200, background: 'white', borderRight: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', flexShrink: 0 },
  areaColHeader: { padding: '10px 12px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 },
  areaItem: { padding: '9px 12px', display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', borderBottom: '1px solid #f1f5f9' },
  areaItemActive: { background: '#eff6ff', borderLeft: '3px solid #2563eb' },
  // Center
  centerCol: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  tabBar: { background: 'white', borderBottom: '1px solid #e2e8f0', padding: '8px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 },
  tab: { padding: '5px 14px', border: '1px solid #e2e8f0', background: 'white', borderRadius: 6, cursor: 'pointer', fontSize: '0.83rem', color: '#475569' },
  tabActive: { background: '#2563eb', color: 'white', borderColor: '#2563eb' },
  // Table
  tableWrap: { background: 'white', borderTop: '1px solid #e2e8f0', maxHeight: 220, overflowY: 'auto', flexShrink: 0 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' },
  th: { background: '#f8fafc', padding: '7px 10px', textAlign: 'left', borderBottom: '2px solid #e2e8f0', fontWeight: 600, color: '#475569', whiteSpace: 'nowrap', position: 'sticky', top: 0, zIndex: 1 },
  td: { padding: '7px 10px', borderBottom: '1px solid #f1f5f9', verticalAlign: 'middle' },
  tr: {},
  badge: { display: 'inline-block', color: 'white', padding: '2px 7px', borderRadius: 9999, fontSize: '0.7rem', fontWeight: 600, whiteSpace: 'nowrap' },
  // Side panel
  sidePanel: { width: 260, background: 'white', borderLeft: '1px solid #e2e8f0', overflowY: 'auto', flexShrink: 0 },
  editForm: { padding: '14px 14px' },
  editFormTitle: { fontWeight: 700, fontSize: '0.9rem', marginBottom: 12, color: '#1e293b', borderBottom: '1px solid #e2e8f0', paddingBottom: 8 },
  inp: { width: '100%', padding: '6px 9px', border: '1px solid #d1d5db', borderRadius: 5, fontSize: '0.82rem', outline: 'none', fontFamily: 'inherit', background: 'white', boxSizing: 'border-box' },
  seqList: { display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 160, overflowY: 'auto' },
  seqItem: { display: 'flex', alignItems: 'center', gap: 4, padding: '4px 6px', background: '#eff6ff', borderRadius: 5, border: '1px solid #bfdbfe' },
  seqBtn: { background: 'none', border: '1px solid #e2e8f0', borderRadius: 3, cursor: 'pointer', padding: '1px 5px', fontSize: '0.72rem' },
  // Map hint
  mapHint: { position: 'absolute', top: 8, left: 8, background: 'rgba(255,255,255,0.92)', padding: '4px 10px', borderRadius: 5, fontSize: '0.75rem', color: '#374151', zIndex: 1000, pointerEvents: 'none', boxShadow: '0 1px 4px rgba(0,0,0,0.1)' },
  // Buttons
  btnSm: { background: '#2563eb', color: 'white', border: 'none', padding: '4px 10px', borderRadius: 5, cursor: 'pointer', fontSize: '0.78rem', fontWeight: 600 },
  btnPrimary: { background: '#2563eb', color: 'white', border: 'none', padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontSize: '0.83rem', fontWeight: 600 },
  btnGhost: { background: 'white', color: '#475569', border: '1px solid #d1d5db', padding: '6px 12px', borderRadius: 6, cursor: 'pointer', fontSize: '0.83rem' },
  iconBtn: { background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px', fontSize: '0.95rem', borderRadius: 4 },
  // Toast
  toast: { position: 'fixed', bottom: 24, right: 24, color: 'white', padding: '10px 20px', borderRadius: 8, fontWeight: 600, fontSize: '0.9rem', zIndex: 9999, boxShadow: '0 4px 12px rgba(0,0,0,0.2)' },
  // Modal
  modalOverlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center' },
  modal: { background: 'white', borderRadius: 10, width: 420, boxShadow: '0 20px 60px rgba(0,0,0,0.3)', overflow: 'hidden' },
  modalHeader: { padding: '12px 20px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8fafc' },
};
