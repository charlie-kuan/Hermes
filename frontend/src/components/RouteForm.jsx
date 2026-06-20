import { useState } from 'react';

export default function RouteForm({
  areas,
  selectedArea,
  selectedPoints,
  onAreaChange,
  onPointAdd,
  onPointRemove,
  onPointReorder,
  onQuickRoute,
  onSubmit,
  onClearRoute,
  loading,
  wideMode = false,
}) {
  const [formData, setFormData] = useState({
    hiker_fitness: 'moderate',
    pack_weight_kg: 12,
  });
  const [quickSelectRoute, setQuickSelectRoute] = useState('');
  const [dragIndex, setDragIndex] = useState(null);
  // nightNumbers: { [item.id]: '1' | '2' | '' }
  const [nightNumbers, setNightNumbers] = useState({});

  const isShelter = (type) => type === 'shelter' || type === 'hut';

  const handleAreaChange = (e) => {
    const area = areas.find(a => a.area_id === e.target.value) || null;
    setQuickSelectRoute('');
    onAreaChange(area);
  };

  const handleQuickSelect = (e) => {
    const routeId = e.target.value;
    setQuickSelectRoute(routeId);
    if (!routeId) return;
    const route = selectedArea?.recommended_routes?.find(r => r.route_id === routeId);
    if (route) onQuickRoute(route.point_sequence);
  };

  const handleChange = (e) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const getPointById = (pointId) => selectedArea?.points.find(p => p.id === pointId);
  const getPointCount = (pointId) => selectedPoints.filter(item => item.pointId === pointId).length;

  const getPointIcon = (type) => ({ trailhead: '🚩', peak: '⛰️', hut: '🏠' }[type] || '📍');
  const getPointTypeLabel = (type) => ({ trailhead: '登山口', peak: '山頭', hut: '山屋' }[type] || '經過點');

  // Drag-and-drop handlers
  const handleDragStart = (e, index) => {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };
  const handleDragOver = (e, index) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };
  const handleDrop = (e, index) => {
    e.preventDefault();
    if (dragIndex !== null) onPointReorder(dragIndex, index);
    setDragIndex(null);
  };
  const handleDragEnd = () => setDragIndex(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (selectedPoints.length < 2) {
      alert('請至少選擇兩個點（起點和終點）');
      return;
    }
    const via_points = selectedPoints.map(item => {
      const point = getPointById(item.pointId);
      return { lat: point.lat, lon: point.lon, name: point.name, type: point.type };
    });
    const overnight_stops = selectedPoints
      .slice(1, -1)
      .filter(item => {
        const p = getPointById(item.pointId);
        return p && isShelter(p.type) && nightNumbers[item.id];
      })
      .map(item => {
        const p = getPointById(item.pointId);
        return { lat: p.lat, lon: p.lon, name: p.name, night: parseInt(nightNumbers[item.id]) };
      })
      .sort((a, b) => a.night - b.night);
    onSubmit({
      area_id: selectedArea.area_id,
      start_lat: via_points[0].lat,
      start_lon: via_points[0].lon,
      start_name: via_points[0].name,
      end_lat: via_points[via_points.length - 1].lat,
      end_lon: via_points[via_points.length - 1].lon,
      end_name: via_points[via_points.length - 1].name,
      loop_route: false,
      hiker_fitness: formData.hiker_fitness,
      pack_weight_kg: parseFloat(formData.pack_weight_kg),
      via_points: via_points.slice(1, -1),
      overnight_stops: overnight_stops.length > 0 ? overnight_stops : undefined,
    });
  };

  // ── Shared blocks ──────────────────────────────────────────────
  const areaBlock = (
    <div className="form-group">
      <label htmlFor="area_id">登山區域</label>
      <select id="area_id" value={selectedArea?.area_id || ''} onChange={handleAreaChange} required>
        <option value="">請選擇區域...</option>
        {areas.map(area => (
          <option key={area.area_id} value={area.area_id}>{area.name}</option>
        ))}
      </select>
    </div>
  );

  const quickRouteBlock = selectedArea?.recommended_routes?.length > 0 && (
    <div className="form-group">
      <label htmlFor="quick_select">推薦路線快選</label>
      <select id="quick_select" value={quickSelectRoute} onChange={handleQuickSelect}>
        <option value="">自訂路線...</option>
        {selectedArea.recommended_routes.map(r => (
          <option key={r.route_id} value={r.route_id}>
            {r.name}（{r.days}天 · {r.difficulty}）
          </option>
        ))}
      </select>
      {quickSelectRoute && (() => {
        const r = selectedArea.recommended_routes.find(x => x.route_id === quickSelectRoute);
        return r ? <small>{r.description}</small> : null;
      })()}
    </div>
  );

  const availablePointsBlock = selectedArea && (
    <>
      <div className="section-label">
        可選點位
        <span style={{ fontSize: '0.65rem', opacity: 0.6, marginLeft: '0.4rem', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>點擊列表或地圖上的標記加入</span>
      </div>
      <div className="points-grid">
        {selectedArea.points.map(point => {
          const count = getPointCount(point.id);
          return (
            <div key={point.id} className={`point-card ${count > 0 ? 'has-selection' : ''}`} onClick={() => onPointAdd(point.id)}>
              <span className="point-icon">{getPointIcon(point.type)}</span>
              <div className="point-details">
                <strong>{point.name}</strong>
                <small>{getPointTypeLabel(point.type)} · {point.elevation}m</small>
              </div>
              {count > 0 && <span className="selection-count">{count}</span>}
            </div>
          );
        })}
      </div>
    </>
  );

  const instructionsBlock = (
    <div className="instructions">
      <h3>💡 使用說明</h3>
      <ol>
        <li>選擇登山區域，地圖上會出現可選點位</li>
        <li>點擊地圖標記或下方列表加入路線點</li>
        <li>點位可重複添加（如往返登山口）</li>
        <li>拖曳已選點位調整順序</li>
        <li>設定體能與背包重量後規劃</li>
      </ol>
    </div>
  );

  const selectedPointsBlock = selectedArea && selectedPoints.length > 0 && (
    <>
      <div className="section-label">
        已選路線（{selectedPoints.length} 個點）
        <span style={{ fontSize: '0.65rem', opacity: 0.6, marginLeft: '0.4rem', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>拖曳可調整順序</span>
      </div>
      <div className="selected-route-list">
        {selectedPoints.map((item, index) => {
          const point = getPointById(item.pointId);
          if (!point) return null;
          return (
            <div
              key={item.id}
              className={`selected-point-item${dragIndex === index ? ' dragging' : ''}`}
              draggable
              onDragStart={(e) => handleDragStart(e, index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDrop={(e) => handleDrop(e, index)}
              onDragEnd={handleDragEnd}
            >
              <span className="drag-handle">⠿</span>
              <span className="point-order">{index + 1}</span>
              <span>{getPointIcon(point.type)}</span>
              <div className="point-info">
                <strong>{point.name}</strong>
                <small>{getPointTypeLabel(point.type)} · {point.elevation}m</small>
              </div>
              {isShelter(point.type) && index > 0 && index < selectedPoints.length - 1 && (
                <label className="night-input-label" onClick={e => e.stopPropagation()}>
                  <span className="night-input-prefix">夜</span>
                  <input
                    type="number"
                    className="night-input"
                    min="1" max="9" placeholder="—"
                    value={nightNumbers[item.id] || ''}
                    onChange={e => setNightNumbers(prev => ({ ...prev, [item.id]: e.target.value }))}
                    onDragStart={e => e.stopPropagation()}
                  />
                </label>
              )}
              <button type="button" onClick={() => onPointRemove(item.id)} className="btn-icon btn-remove" title="移除">✕</button>
            </div>
          );
        })}
      </div>
    </>
  );

  const fitnessBlock = (
    <div className="form-row">
      <div className="form-group">
        <label htmlFor="hiker_fitness">體能水平</label>
        <select id="hiker_fitness" name="hiker_fitness" value={formData.hiker_fitness} onChange={handleChange}>
          <option value="beginner">初學者</option>
          <option value="moderate">中等</option>
          <option value="expert">專家</option>
        </select>
      </div>
      <div className="form-group">
        <label htmlFor="pack_weight_kg">背包重量 (kg)</label>
        <input type="number" id="pack_weight_kg" name="pack_weight_kg" value={formData.pack_weight_kg} onChange={handleChange} min="5" max="50" step="0.5" />
      </div>
    </div>
  );

  const buttonsBlock = (
    <form onSubmit={handleSubmit}>
      <div className="form-buttons">
        <button type="submit" className="btn-primary" disabled={loading || selectedPoints.length < 2}>
          {loading ? '規劃中...' : '🗺️ 開始規劃路線'}
        </button>
        <button type="button" className="btn-secondary" onClick={onClearRoute}>清除路線</button>
      </div>
    </form>
  );

  // ── Wide (two-column) layout ────────────────────────────────────
  if (wideMode) {
    return (
      <div className="route-form-wide">
        <div className="route-form-col">
          {areaBlock}
          {quickRouteBlock}
          <div className="points-section route-form-col-scroll">{availablePointsBlock}</div>
        </div>
        <div className="route-form-col-sep" />
        <div className="route-form-col">
          <div className="points-section">{selectedPointsBlock}</div>
          {fitnessBlock}
          {buttonsBlock}
          {instructionsBlock}
        </div>
      </div>
    );
  }

  // ── Single-column layout ────────────────────────────────────────
  return (
    <div className="route-form">
      {areaBlock}
      {quickRouteBlock}
      {selectedArea && (
        <div className="points-section">
          {selectedPointsBlock}
          {availablePointsBlock}
        </div>
      )}
      {fitnessBlock}
      {buttonsBlock}
      {instructionsBlock}
    </div>
  );
}
