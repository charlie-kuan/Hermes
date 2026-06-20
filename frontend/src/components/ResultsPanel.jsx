import { useState } from 'react';
import { apiService } from '../services/api';
import ElevationProfile from './ElevationProfile';

export default function ResultsPanel({ route, onReplan, onClearRoute, wideMode = false }) {
  const [collapsed, setCollapsed] = useState({ stats: false, elevation: false, segments: false, dayplans: false, equipment: true, food: true });
  const toggle = (key) => setCollapsed(prev => ({ ...prev, [key]: !prev[key] }));

  if (!route) {
    return (
      <div className="results-panel">
        <div className="empty-state">
          <div className="empty-icon">🏔️</div>
          <p>規劃路線後，這裡會顯示詳細資訊</p>
        </div>
      </div>
    );
  }

  const getDifficultyClass = (d) => `difficulty-badge difficulty-${d}`;

  const formatTime = (hours) => {
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    return `${h}小時${m > 0 ? ` ${m}分` : ''}`;
  };

  const handleExport = async (format) => {
    try {
      const blob = await apiService.exportRoute(route.route_id, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `route_${route.route_id.substring(0, 8)}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      alert(`匯出失敗: ${error.message}`);
    }
  };

  const categoryLabel = (c) => ({ essential: '必備裝備', overnight: '過夜裝備', clothing: '服裝', technical: '技術裝備' }[c] || '選配裝備');

  const replanButtons = (
    <div className="replan-buttons">
      <button className="btn-primary btn-replan" onClick={onReplan}>✏️ 調整路線</button>
      <button className="btn-secondary" onClick={onClearRoute}>清除重來</button>
    </div>
  );

  const legsBlock = route.legs?.length > 1 && (
    <div className="result-section">
      <div className="result-section-header" onClick={() => toggle('segments')}>
        🗺 逐段行程
        <span>{collapsed.segments ? '▶' : '▼'}</span>
      </div>
      {!collapsed.segments && (
        <div className="result-section-body">
          {route.legs.map((leg, i) => (
            <div key={i} className="segment-row">
              <div className="segment-nodes">
                <span className="segment-node-name">{leg.start_node.name || leg.start_node.type}</span>
                <span className="segment-arrow">→</span>
                <span className="segment-node-name">{leg.end_node.name || leg.end_node.type}</span>
              </div>
              <div className="segment-stats">
                <span>{leg.distance.toFixed(1)} km</span>
                <span>↑ {leg.elevation_gain.toFixed(0)} m</span>
                <span>↓ {leg.elevation_loss.toFixed(0)} m</span>
                <span>⏱ {formatTime(leg.estimated_time)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  if (wideMode) {
    return (
      <div className="results-panel results-wide">
        {replanButtons}
        <div className="results-wide-cols">
          {/* Left col */}
          <div className="results-wide-col">
            <div className="result-section">
              <div className="result-section-header" onClick={() => toggle('stats')}>
                基本資料 <span>{collapsed.stats ? '▶' : '▼'}</span>
              </div>
              {!collapsed.stats && (
                <div className="result-section-body">
                  <div className="stat-grid stat-grid-3">
                    <div className="stat-item"><div className="stat-label">總距離</div><div className="stat-value">{route.total_distance.toFixed(1)} km</div></div>
                    <div className="stat-item"><div className="stat-label">↑ 爬升</div><div className="stat-value">{route.total_elevation_gain.toFixed(0)} m</div></div>
                    <div className="stat-item"><div className="stat-label">↓ 下降</div><div className="stat-value">{route.total_elevation_loss.toFixed(0)} m</div></div>
                  </div>
                  <div className="time-row">
                    <div className="time-row-item"><span className="time-row-label">樂觀</span><span className="time-row-val">{formatTime(route.estimated_time.optimistic)}</span></div>
                    <div className="time-row-sep" />
                    <div className="time-row-item time-row-normal"><span className="time-row-label">正常</span><span className="time-row-val">{formatTime(route.estimated_time.normal)}</span></div>
                    <div className="time-row-sep" />
                    <div className="time-row-item"><span className="time-row-label">保守</span><span className="time-row-val">{formatTime(route.estimated_time.conservative)}</span></div>
                  </div>
                </div>
              )}
            </div>

            <div className="result-section">
              <div className="result-section-header" onClick={() => toggle('elevation')}>
                高度剖面圖 <span>{collapsed.elevation ? '▶' : '▼'}</span>
              </div>
              {!collapsed.elevation && (
                <div className="result-section-body" style={{ padding: '0.5rem' }}>
                  <ElevationProfile route={route} />
                </div>
              )}
            </div>

            {route.day_plans?.length > 0 && (
              <div className="result-section">
                <div className="result-section-header" onClick={() => toggle('dayplans')}>
                  📅 多天行程規劃 <span>{collapsed.dayplans ? '▶' : '▼'}</span>
                </div>
                {!collapsed.dayplans && (
                  <div className="result-section-body">
                    {route.day_plans.map(day => (
                      <div key={day.day} className="day-plan">
                        <div className="day-plan-header">
                          第 {day.day} 天
                          {day.overnight_stop && <span className="day-plan-stop">→ 夜宿 {day.overnight_stop.name}</span>}
                        </div>
                        <div className="day-plan-stats">
                          <span>{day.distance.toFixed(1)} km</span>
                          <span>↑ {day.elevation_gain.toFixed(0)} m</span>
                          <span>↓ {day.elevation_loss.toFixed(0)} m</span>
                          <span>⏱ {formatTime(day.estimated_time.normal)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="result-section">
              <div className="result-section-header" style={{ cursor: 'default' }}>💾 匯出路線</div>
              <div className="result-section-body">
                <div className="export-buttons">
                  <button className="btn-secondary" onClick={() => handleExport('gpx')}>📍 GPX</button>
                  <button className="btn-secondary" onClick={() => handleExport('geojson')}>🗺 GeoJSON</button>
                </div>
              </div>
            </div>
          </div>

          <div className="results-wide-sep" />

          {/* Right col */}
          <div className="results-wide-col">
            {legsBlock}

            {route.equipment?.length > 0 && (
              <div className="result-section">
                <div className="result-section-header" onClick={() => toggle('equipment')}>
                  🎒 裝備建議 <span>{collapsed.equipment ? '▶' : '▼'}</span>
                </div>
                {!collapsed.equipment && (
                  <div className="result-section-body">
                    {route.equipment.map((cat, i) => (
                      <div key={i} className="equipment-category">
                        <h4>{categoryLabel(cat.category)}</h4>
                        <ul className="equipment-list">{cat.items.map((item, j) => <li key={j}>{item}</li>)}</ul>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {route.food && (
              <div className="result-section">
                <div className="result-section-header" onClick={() => toggle('food')}>
                  🍽 食物與水 <span>{collapsed.food ? '▶' : '▼'}</span>
                </div>
                {!collapsed.food && (
                  <div className="result-section-body">
                    <div className="food-info">
                      <div>每日熱量：{route.food.daily_calories} kcal</div>
                      <div>總熱量：{route.food.total_calories} kcal</div>
                      <div>每日水量：{route.food.daily_water_liters} L</div>
                      <div>每日餐數：{route.food.meals_per_day}</div>
                    </div>
                    {route.food.notes?.length > 0 && (
                      <div className="food-notes">
                        <strong style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>注意事項</strong>
                        <ul>{route.food.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="results-panel">

      {/* Replan / Clear buttons */}
      {replanButtons}

      {/* Basic Stats */}
      <div className="result-section">
        <div className="result-section-header" onClick={() => toggle('stats')}>
          基本資料
          <span>{collapsed.stats ? '▶' : '▼'}</span>
        </div>
        {!collapsed.stats && (
          <div className="result-section-body">
            <div className="stat-grid stat-grid-3">
              <div className="stat-item">
                <div className="stat-label">總距離</div>
                <div className="stat-value">{route.total_distance.toFixed(1)} km</div>
              </div>
              <div className="stat-item">
                <div className="stat-label">↑ 爬升</div>
                <div className="stat-value">{route.total_elevation_gain.toFixed(0)} m</div>
              </div>
              <div className="stat-item">
                <div className="stat-label">↓ 下降</div>
                <div className="stat-value">{route.total_elevation_loss.toFixed(0)} m</div>
              </div>
            </div>
            <div className="time-row">
              <div className="time-row-item">
                <span className="time-row-label">樂觀</span>
                <span className="time-row-val">{formatTime(route.estimated_time.optimistic)}</span>
              </div>
              <div className="time-row-sep" />
              <div className="time-row-item time-row-normal">
                <span className="time-row-label">正常</span>
                <span className="time-row-val">{formatTime(route.estimated_time.normal)}</span>
              </div>
              <div className="time-row-sep" />
              <div className="time-row-item">
                <span className="time-row-label">保守</span>
                <span className="time-row-val">{formatTime(route.estimated_time.conservative)}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Elevation Profile */}
      <div className="result-section">
        <div className="result-section-header" onClick={() => toggle('elevation')}>
          高度剖面圖
          <span>{collapsed.elevation ? '▶' : '▼'}</span>
        </div>
        {!collapsed.elevation && (
          <div className="result-section-body" style={{ padding: '0.5rem' }}>
            <ElevationProfile route={route} />
          </div>
        )}
      </div>


      {/* Legs */}
      {legsBlock}

      {/* Multi-day plan */}
      {route.day_plans?.length > 0 && (
        <div className="result-section">
          <div className="result-section-header" onClick={() => toggle('dayplans')}>
            📅 多天行程規劃
            <span>{collapsed.dayplans ? '▶' : '▼'}</span>
          </div>
          {!collapsed.dayplans && (
            <div className="result-section-body">
              {route.day_plans.map(day => (
                <div key={day.day} className="day-plan">
                  <div className="day-plan-header">
                    第 {day.day} 天
                    {day.overnight_stop && (
                      <span className="day-plan-stop">→ 夜宿 {day.overnight_stop.name}</span>
                    )}
                  </div>
                  <div className="day-plan-stats">
                    <span>{day.distance.toFixed(1)} km</span>
                    <span>↑ {day.elevation_gain.toFixed(0)} m</span>
                    <span>↓ {day.elevation_loss.toFixed(0)} m</span>
                    <span>⏱ {formatTime(day.estimated_time.normal)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Equipment */}
      {route.equipment?.length > 0 && (
        <div className="result-section">
          <div className="result-section-header" onClick={() => toggle('equipment')}>
            🎒 裝備建議
            <span>{collapsed.equipment ? '▶' : '▼'}</span>
          </div>
          {!collapsed.equipment && (
            <div className="result-section-body">
              {route.equipment.map((cat, i) => (
                <div key={i} className="equipment-category">
                  <h4>{categoryLabel(cat.category)}</h4>
                  <ul className="equipment-list">
                    {cat.items.map((item, j) => <li key={j}>{item}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Food */}
      {route.food && (
        <div className="result-section">
          <div className="result-section-header" onClick={() => toggle('food')}>
            🍽 食物與水
            <span>{collapsed.food ? '▶' : '▼'}</span>
          </div>
          {!collapsed.food && (
            <div className="result-section-body">
              <div className="food-info">
                <div>每日熱量：{route.food.daily_calories} kcal</div>
                <div>總熱量：{route.food.total_calories} kcal</div>
                <div>每日水量：{route.food.daily_water_liters} L</div>
                <div>每日餐數：{route.food.meals_per_day}</div>
              </div>
              {route.food.notes?.length > 0 && (
                <div className="food-notes">
                  <strong style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>注意事項</strong>
                  <ul>{route.food.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Export */}
      <div className="result-section">
        <div className="result-section-header" style={{ cursor: 'default' }}>💾 匯出路線</div>
        <div className="result-section-body">
          <div className="export-buttons">
            <button className="btn-secondary" onClick={() => handleExport('gpx')}>📍 GPX</button>
            <button className="btn-secondary" onClick={() => handleExport('geojson')}>🗺 GeoJSON</button>
          </div>
        </div>
      </div>

    </div>
  );
}
