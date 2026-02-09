import { useState, useEffect } from 'react';

export default function RouteForm({
  areas,
  onSubmit,
  loading,
  startPoint,
  endPoint,
  onClearMarkers,
  onRouteSelect,
  onWaypointsChange
}) {
  const [formData, setFormData] = useState({
    area_id: '',
    route_id: '',
    start_lat: '',
    start_lon: '',
    end_lat: '',
    end_lon: '',
    loop_route: false,
    multi_day: false,
    target_hours_per_day: 7,
    hiker_fitness: 'moderate',
    pack_weight_kg: 12,
    max_distance: '',
    prefer_huts: true,
    avoid_difficult: false,
  });

  const [selectedArea, setSelectedArea] = useState(null);
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [selectedWaypoints, setSelectedWaypoints] = useState([]);

  // Update form when markers are placed
  useEffect(() => {
    if (startPoint) {
      setFormData(prev => ({
        ...prev,
        start_lat: startPoint.lat.toFixed(5),
        start_lon: startPoint.lng.toFixed(5),
      }));
    }
  }, [startPoint]);

  useEffect(() => {
    if (endPoint) {
      setFormData(prev => ({
        ...prev,
        end_lat: endPoint.lat.toFixed(5),
        end_lon: endPoint.lng.toFixed(5),
      }));
    }
  }, [endPoint]);

  // Handle area selection
  useEffect(() => {
    if (formData.area_id) {
      const area = areas.find(a => a.area_id === formData.area_id);
      setSelectedArea(area);
      setSelectedRoute(null);
      setSelectedWaypoints([]);
      setFormData(prev => ({
        ...prev,
        route_id: '',
        start_lat: '',
        start_lon: '',
        end_lat: '',
        end_lon: '',
      }));
    }
  }, [formData.area_id, areas]);

  // Handle route selection
  useEffect(() => {
    if (formData.route_id && selectedArea?.routes) {
      const route = selectedArea.routes.find(r => r.route_id === formData.route_id);
      setSelectedRoute(route);
      
      if (route) {
        // Auto-fill trailhead as start point
        setFormData(prev => ({
          ...prev,
          start_lat: route.trailhead.lat.toFixed(5),
          start_lon: route.trailhead.lon.toFixed(5),
          multi_day: route.days > 1,
          loop_route: false,
        }));
        
        // Pre-select all required waypoints
        const required = route.waypoints.filter(w => w.required).map(w => w.name);
        setSelectedWaypoints(required);
        
        // Notify parent component
        if (onRouteSelect) onRouteSelect(route);
        if (onWaypointsChange) onWaypointsChange(required);
      }
    } else {
      setSelectedRoute(null);
      setSelectedWaypoints([]);
      if (onRouteSelect) onRouteSelect(null);
      if (onWaypointsChange) onWaypointsChange([]);
    }
  }, [formData.route_id, selectedArea, onRouteSelect, onWaypointsChange]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleWaypointToggle = (waypointName, required) => {
    if (required) return; // Required waypoints cannot be deselected
    
    setSelectedWaypoints(prev => {
      const newWaypoints = prev.includes(waypointName)
        ? prev.filter(w => w !== waypointName)
        : [...prev, waypointName];
      
      // Notify parent component
      if (onWaypointsChange) onWaypointsChange(newWaypoints);
      
      return newWaypoints;
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const params = {
      area_id: formData.area_id,
      start_lat: parseFloat(formData.start_lat),
      start_lon: parseFloat(formData.start_lon),
      loop_route: formData.loop_route,
      multi_day: formData.multi_day,
      hiker_fitness: formData.hiker_fitness,
      pack_weight_kg: parseFloat(formData.pack_weight_kg),
      prefer_huts: formData.prefer_huts,
      avoid_difficult: formData.avoid_difficult,
    };

    // Add selected waypoints as via_points
    if (selectedRoute && selectedWaypoints.length > 0) {
      params.via_points = selectedRoute.waypoints
        .filter(w => selectedWaypoints.includes(w.name))
        .map(w => ({
          lat: w.lat,
          lon: w.lon,
          name: w.name,
          type: w.type
        }));
    }

    if (formData.multi_day) {
      params.target_hours_per_day = parseFloat(formData.target_hours_per_day);
    }

    if (!formData.loop_route && formData.end_lat && formData.end_lon) {
      params.end_lat = parseFloat(formData.end_lat);
      params.end_lon = parseFloat(formData.end_lon);
    }

    if (formData.max_distance) {
      params.max_distance = parseFloat(formData.max_distance);
    }

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
                {area.name} ({area.country})
              </option>
            ))}
          </select>
        </div>

        {/* Route Selection */}
        {selectedArea && selectedArea.routes && selectedArea.routes.length > 0 && (
          <div className="form-group">
            <label htmlFor="route_id">選擇路線 *</label>
            <select
              id="route_id"
              name="route_id"
              value={formData.route_id}
              onChange={handleChange}
              required
            >
              <option value="">請選擇路線...</option>
              {selectedArea.routes.map(route => (
                <option key={route.route_id} value={route.route_id}>
                  {route.name} ({route.days}天 - {route.difficulty})
                </option>
              ))}
            </select>
            {selectedRoute && (
              <small style={{ display: 'block', marginTop: '5px', color: '#666' }}>
                📍 {selectedRoute.description}<br/>
                📏 距離: {selectedRoute.total_distance} km | ⏱️ {selectedRoute.estimated_time}
              </small>
            )}
          </div>
        )}

        {/* Waypoints Selection */}
        {selectedRoute && selectedRoute.waypoints && selectedRoute.waypoints.length > 0 && (
          <div className="form-group waypoints-group">
            <label>選擇經過點/山頭/住宿點</label>
            <div className="waypoints-list">
              {/* Trailhead (always shown, not selectable) */}
              <div className="waypoint-item trailhead-item">
                <span className="waypoint-icon">🚩</span>
                <div className="waypoint-info">
                  <strong>{selectedRoute.trailhead.name}</strong>
                  <small>登山口 | {selectedRoute.trailhead.elevation}m</small>
                </div>
                <span className="waypoint-badge required">起點</span>
              </div>
              
              {/* Waypoints */}
              {selectedRoute.waypoints.map((waypoint, idx) => (
                <div key={idx} className="waypoint-item">
                  <input
                    type="checkbox"
                    id={`waypoint-${idx}`}
                    checked={selectedWaypoints.includes(waypoint.name)}
                    onChange={() => handleWaypointToggle(waypoint.name, waypoint.required)}
                    disabled={waypoint.required}
                  />
                  <label htmlFor={`waypoint-${idx}`} className="waypoint-info">
                    <span className="waypoint-icon">
                      {waypoint.type === 'peak' ? '⛰️' : 
                       waypoint.type === 'hut' ? '🏠' : '📍'}
                    </span>
                    <div>
                      <strong>{waypoint.name}</strong>
                      <small>
                        {waypoint.type === 'peak' ? '山頭' : 
                         waypoint.type === 'hut' ? '山屋' : '中繼點'} | {waypoint.elevation}m
                        {waypoint.facilities && ` | ${waypoint.facilities.join(', ')}`}
                      </small>
                    </div>
                  </label>
                  {waypoint.required && (
                    <span className="waypoint-badge required">必經</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Start Point - only show if no route selected */}
        {!selectedRoute && (
          <div className="form-group">
            <label>起點座標 *</label>
            <div className="coordinate-input">
              <input
                type="number"
                name="start_lat"
                value={formData.start_lat}
                onChange={handleChange}
                placeholder="緯度"
                step="0.00001"
                required
              />
              <input
                type="number"
                name="start_lon"
                value={formData.start_lon}
                onChange={handleChange}
                placeholder="經度"
                step="0.00001"
                required
              />
            </div>
            <small>點擊地圖選擇起點</small>
          </div>
        )}
        {/* End Point - only show if no route selected and not loop */}
        {!selectedRoute && !formData.loop_route && (
          <div className="form-group">
            <label>終點座標</label>
            <div className="coordinate-input">
              <input
                type="number"
                name="end_lat"
                value={formData.end_lat}
                onChange={handleChange}
                placeholder="緯度"
                step="0.00001"
              />
              <input
                type="number"
                name="end_lon"
                value={formData.end_lon}
                onChange={handleChange}
                placeholder="經度"
                step="0.00001"
              />
            </div>
            <small>點擊地圖選擇終點</small>
          </div>
        )}

        {/* Multi-day */}
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              name="multi_day"
              checked={formData.multi_day}
              onChange={handleChange}
            />
            多日行程規劃
          </label>
        </div>

        {/* Target Hours */}
        {formData.multi_day && (
          <div className="form-group">
            <label htmlFor="target_hours_per_day">每日目標時數</label>
            <input
              type="number"
              id="target_hours_per_day"
              name="target_hours_per_day"
              value={formData.target_hours_per_day}
              onChange={handleChange}
              min="4"
              max="12"
              step="0.5"
            />
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

        {/* Max Distance */}
        <div className="form-group">
          <label htmlFor="max_distance">最大距離 (km)</label>
          <input
            type="number"
            id="max_distance"
            name="max_distance"
            value={formData.max_distance}
            onChange={handleChange}
            placeholder="選填"
            min="1"
            max="100"
            step="1"
          />
        </div>

        {/* Preferences */}
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              name="prefer_huts"
              checked={formData.prefer_huts}
              onChange={handleChange}
            />
            優先選擇山屋
          </label>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              name="avoid_difficult"
              checked={formData.avoid_difficult}
              onChange={handleChange}
            />
            避開困難路段
          </label>
        </div>

        {/* Buttons */}
        <div className="form-buttons">
          <button
            type="submit"
            className="btn-primary"
            disabled={loading}
          >
            {loading ? '規劃中...' : '🗺️ 規劃路線'}
          </button>

          <button
            type="button"
            className="btn-secondary"
            onClick={onClearMarkers}
          >
            🗑️ 清除標記
          </button>
        </div>
      </form>

      {/* Instructions */}
      <div className="instructions">
        <h3>💡 使用說明</h3>
        <ol>
          <li>選擇登山區域</li>
          <li>選擇預設路線（或自行在地圖上標記）</li>
          <li>勾選想要經過的山頭和住宿點</li>
          <li>設定體能水平和背包重量</li>
          <li>點擊「規劃路線」取得詳細路線和GPX</li>
        </ol>
      </div>
    </div>
  );
}