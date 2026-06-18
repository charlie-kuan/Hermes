import { useState, useEffect } from 'react';

export default function RouteForm({
  areas,
  onSubmit,
  loading,
  onClearRoute,
  onRouteSelect,
  onWaypointsChange
}) {
  const [formData, setFormData] = useState({
    area_id: '',
    hiker_fitness: 'moderate',
    pack_weight_kg: 12,
  });

  const [selectedArea, setSelectedArea] = useState(null);
  const [selectedPoints, setSelectedPoints] = useState([]); // Array of {id: unique_id, pointId: point_id}
  const [quickSelectRoute, setQuickSelectRoute] = useState('');
  const [nextUniqueId, setNextUniqueId] = useState(1);

  // Handle area selection
  useEffect(() => {
    if (formData.area_id) {
      const area = areas.find(a => a.area_id === formData.area_id);
      setSelectedArea(area);
      setSelectedPoints([]);
      setQuickSelectRoute('');
    }
  }, [formData.area_id, areas]);

  // Handle quick route selection
  useEffect(() => {
    if (quickSelectRoute && selectedArea) {
      const route = selectedArea.recommended_routes?.find(r => r.route_id === quickSelectRoute);
      if (route) {
        // Convert point sequence to array of {id, pointId} objects
        let uniqueId = 1;
        const points = route.point_sequence.map(pointId => ({
          id: uniqueId++,
          pointId: pointId
        }));
        setSelectedPoints(points);
        setNextUniqueId(uniqueId);
        setFormData(prev => ({ ...prev }));
      }
    }
  }, [quickSelectRoute, selectedArea]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handlePointAdd = (pointId) => {
    setSelectedPoints(prev => [...prev, { id: nextUniqueId, pointId }]);
    setNextUniqueId(prev => prev + 1);
    setQuickSelectRoute(''); // Clear quick select when manually changing
  };

  const handlePointRemove = (uniqueId) => {
    setSelectedPoints(prev => prev.filter(item => item.id !== uniqueId));
    setQuickSelectRoute(''); // Clear quick select when manually changing
  };

  const handlePointMoveUp = (index) => {
    if (index === 0) return;
    setSelectedPoints(prev => {
      const newPoints = [...prev];
      [newPoints[index - 1], newPoints[index]] = [newPoints[index], newPoints[index - 1]];
      return newPoints;
    });
  };

  const handlePointMoveDown = (index) => {
    if (index === selectedPoints.length - 1) return;
    setSelectedPoints(prev => {
      const newPoints = [...prev];
      [newPoints[index], newPoints[index + 1]] = [newPoints[index + 1], newPoints[index]];
      return newPoints;
    });
  };

  const getPointById = (pointId) => {
    return selectedArea?.points.find(p => p.id === pointId);
  };

  const getPointCount = (pointId) => {
    return selectedPoints.filter(item => item.pointId === pointId).length;
  };

  const getPointIcon = (type) => {
    switch(type) {
      case 'trailhead': return '🚩';
      case 'peak': return '⛰️';
      case 'hut': return '🏠';
      default: return '📍';
    }
  };

  const getPointTypeLabel = (type) => {
    switch(type) {
      case 'trailhead': return '登山口';
      case 'peak': return '山頭';
      case 'hut': return '山屋';
      default: return '經過點';
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    if (selectedPoints.length < 2) {
      alert('請至少選擇兩個點（起點和終點）');
      return;
    }

    // Convert selected points to via_points with full details
    const via_points = selectedPoints.map(item => {
      const point = getPointById(item.pointId);
      return {
        lat: point.lat,
        lon: point.lon,
        name: point.name,
        type: point.type
      };
    });

    const params = {
      area_id: formData.area_id,
      start_lat: via_points[0].lat,
      start_lon: via_points[0].lon,
      end_lat: via_points[via_points.length - 1].lat,
      end_lon: via_points[via_points.length - 1].lon,
      loop_route: false,
      hiker_fitness: formData.hiker_fitness,
      pack_weight_kg: parseFloat(formData.pack_weight_kg),
      via_points: via_points.slice(1, -1) // Exclude first and last (they're start/end)
    };

    onSubmit(params);
  };

  return (
    <div className="route-form">
      <h2>📍 路線規劃</h2>

      <form onSubmit={handleSubmit}>
        {/* Area Selection */}
        <div className="form-group">
          <label htmlFor="area_id">選擇區域 *</label>
          <select
            id="area_id"
            name="area_id"
            value={formData.area_id}
            onChange={handleChange}
            required
          >
            <option value="">請選擇...</option>
            {areas.map(area => (
              <option key={area.area_id} value={area.area_id}>
                {area.name}
              </option>
            ))}
          </select>
        </div>

        {/* Quick Route Selection */}
        {selectedArea && selectedArea.recommended_routes && selectedArea.recommended_routes.length > 0 && (
          <div className="form-group">
            <label htmlFor="quick_select">快速選擇推薦路線</label>
            <select
              id="quick_select"
              value={quickSelectRoute}
              onChange={(e) => setQuickSelectRoute(e.target.value)}
            >
              <option value="">自訂路線...</option>
              {selectedArea.recommended_routes.map(route => (
                <option key={route.route_id} value={route.route_id}>
                  {route.name} ({route.days}天 - {route.difficulty})
                </option>
              ))}
            </select>
            {quickSelectRoute && selectedArea.recommended_routes.find(r => r.route_id === quickSelectRoute) && (
              <small style={{ display: 'block', marginTop: '5px', color: '#666' }}>
                {selectedArea.recommended_routes.find(r => r.route_id === quickSelectRoute).description}
              </small>
            )}
          </div>
        )}

        {/* Point Selection */}
        {selectedArea && (
          <div className="form-group waypoints-group">
            <label>選擇路線點位（可拖曳排序）</label>

            {/* Selected Points (in order) */}
            {selectedPoints.length > 0 && (
              <div className="selected-points-list">
                <h4>已選路線（共 {selectedPoints.length} 個點）</h4>
                {selectedPoints.map((item, index) => {
                  const point = getPointById(item.pointId);
                  if (!point) return null;
                  return (
                    <div key={item.id} className="selected-point-item">
                      <span className="point-order">{index + 1}</span>
                      <span className="waypoint-icon">{getPointIcon(point.type)}</span>
                      <div className="point-info">
                        <strong>{point.name}</strong>
                        <small>{getPointTypeLabel(point.type)} | {point.elevation}m</small>
                      </div>
                      <div className="point-actions">
                        <button
                          type="button"
                          onClick={() => handlePointMoveUp(index)}
                          disabled={index === 0}
                          className="btn-icon"
                          title="往上移"
                        >
                          ▲
                        </button>
                        <button
                          type="button"
                          onClick={() => handlePointMoveDown(index)}
                          disabled={index === selectedPoints.length - 1}
                          className="btn-icon"
                          title="往下移"
                        >
                          ▼
                        </button>
                        <button
                          type="button"
                          onClick={() => handlePointRemove(item.id)}
                          className="btn-icon btn-remove"
                          title="移除"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Available Points */}
            <div className="available-points">
              <h4>可選點位（點擊添加到路線）</h4>
              <div className="points-grid">
                {selectedArea.points.map((point) => {
                  const count = getPointCount(point.id);
                  return (
                    <div
                      key={point.id}
                      className={`point-card ${count > 0 ? 'has-selection' : ''}`}
                      onClick={() => handlePointAdd(point.id)}
                      title={`點擊添加「${point.name}」到路線`}
                    >
                      <span className="point-icon">{getPointIcon(point.type)}</span>
                      <div className="point-details">
                        <strong>{point.name}</strong>
                        <small>{getPointTypeLabel(point.type)} · {point.elevation}m</small>
                      </div>
                      {count > 0 && (
                        <span className="selection-count">{count}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Fitness Level */}
        <div className="form-group">
          <label htmlFor="hiker_fitness">體能水平</label>
          <select
            id="hiker_fitness"
            name="hiker_fitness"
            value={formData.hiker_fitness}
            onChange={handleChange}
          >
            <option value="beginner">初學者 (4 km/h)</option>
            <option value="moderate">中等 (5 km/h)</option>
            <option value="expert">專家 (6 km/h)</option>
          </select>
        </div>

        {/* Pack Weight */}
        <div className="form-group">
          <label htmlFor="pack_weight_kg">背包重量 (kg)</label>
          <input
            type="number"
            id="pack_weight_kg"
            name="pack_weight_kg"
            value={formData.pack_weight_kg}
            onChange={handleChange}
            min="5"
            max="50"
            step="0.5"
          />
        </div>

        {/* Buttons */}
        <div className="form-buttons">
          <button
            type="submit"
            className="btn-primary"
            disabled={loading || selectedPoints.length < 2}
          >
            {loading ? '規劃中...' : '🗺️ 規劃路線'}
          </button>

          <button
            type="button"
            className="btn-secondary"
            onClick={onClearRoute}
          >
            🗑️ 清除路線
          </button>
        </div>
      </form>

      {/* Instructions */}
      <div className="instructions">
        <h3>💡 使用說明</h3>
        <ol>
          <li>選擇登山區域</li>
          <li>快速選擇推薦路線，或點擊卡片自由添加點位</li>
          <li>點位可重複添加（如往返經過登山口）</li>
          <li>使用 ▲ ▼ 按鈕調整點位順序</li>
          <li>設定體能水平和背包重量</li>
          <li>點擊「規劃路線」取得詳細路線和GPX</li>
        </ol>
      </div>
    </div>
  );
}
