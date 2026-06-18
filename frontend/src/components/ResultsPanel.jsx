import { useState } from 'react';
import { apiService } from '../services/api';
import ElevationProfile from './ElevationProfile';

export default function ResultsPanel({ route, onExport }) {
  const [collapsed, setCollapsed] = useState({ time: true, equipment: true, food: true });
  const toggle = (key) => setCollapsed(prev => ({ ...prev, [key]: !prev[key] }));
  if (!route) {
    return (
      <div className="results-panel">
        <h2>📊 路線資訊</h2>
        <div className="empty-state">
          <p className="empty-icon">🏔️</p>
          <p>規劃路線後，這裡會顯示詳細資訊</p>
        </div>
      </div>
    );
  }

  const getDifficultyClass = (difficulty) => {
    return `difficulty-badge difficulty-${difficulty}`;
  };

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

      if (onExport) onExport(format);
    } catch (error) {
      console.error('Export failed:', error);
      alert(`匯出失敗: ${error.message}`);
    }
  };

  return (
    <div className="results-panel">
      <h2>📊 路線資訊</h2>

      {/* Basic Stats */}
      <div className="result-section">
        <h3>基本資料</h3>
        <div className="stat-grid">
          <div className="stat-item">
            <div className="stat-label">總距離</div>
            <div className="stat-value">{route.total_distance.toFixed(1)} km</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">爬升</div>
            <div className="stat-value">{route.total_elevation_gain.toFixed(0)} m</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">下降</div>
            <div className="stat-value">{route.total_elevation_loss.toFixed(0)} m</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">難度</div>
            <div className="stat-value">
              <span className={getDifficultyClass(route.difficulty)}>
                {route.difficulty}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Elevation Profile */}
      <div className="result-section">
        <ElevationProfile route={route} />
      </div>

      {/* Time Estimates */}
      <div className="result-section">
        <h3 className="collapsible-header" onClick={() => toggle('time')}>
          ⏱️ 時間估算 <span className="collapse-icon">{collapsed.time ? '▶' : '▼'}</span>
        </h3>
        {!collapsed.time && (
          <div className="time-estimates">
            <div className="time-item">
              <span className="time-label">樂觀:</span>
              <span className="time-value">{formatTime(route.estimated_time.optimistic)}</span>
            </div>
            <div className="time-item time-normal">
              <span className="time-label">正常:</span>
              <span className="time-value">{formatTime(route.estimated_time.normal)}</span>
            </div>
            <div className="time-item">
              <span className="time-label">保守:</span>
              <span className="time-value">{formatTime(route.estimated_time.conservative)}</span>
            </div>
          </div>
        )}
      </div>

      {/* Equipment */}
      {route.equipment && route.equipment.length > 0 && (
        <div className="result-section">
          <h3 className="collapsible-header" onClick={() => toggle('equipment')}>
            🎒 裝備建議 <span className="collapse-icon">{collapsed.equipment ? '▶' : '▼'}</span>
          </h3>
          {!collapsed.equipment && route.equipment.map((category, index) => (
            <div key={index} className="equipment-category">
              <h4>{category.category === 'essential' ? '必備裝備' :
                   category.category === 'overnight' ? '過夜裝備' :
                   category.category === 'clothing' ? '服裝' :
                   category.category === 'technical' ? '技術裝備' : '選配裝備'}</h4>
              <ul className="equipment-list">
                {category.items.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {/* Food */}
      {route.food && (
        <div className="result-section">
          <h3 className="collapsible-header" onClick={() => toggle('food')}>
            🍽️ 食物與水 <span className="collapse-icon">{collapsed.food ? '▶' : '▼'}</span>
          </h3>
          {!collapsed.food && (
            <>
              <div className="food-info">
                <div>每日熱量: {route.food.daily_calories} kcal</div>
                <div>總熱量: {route.food.total_calories} kcal</div>
                <div>每日水量: {route.food.daily_water_liters} L</div>
                <div>每日餐數: {route.food.meals_per_day}</div>
              </div>
              {route.food.notes && route.food.notes.length > 0 && (
                <div className="food-notes">
                  <strong>注意事項:</strong>
                  <ul>
                    {route.food.notes.map((note, i) => (
                      <li key={i}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Export Buttons */}
      <div className="result-section">
        <h3>💾 匯出路線</h3>
        <div className="export-buttons">
          <button
            className="btn-secondary"
            onClick={() => handleExport('gpx')}
          >
            📍 匯出 GPX
          </button>
          <button
            className="btn-secondary"
            onClick={() => handleExport('geojson')}
          >
            🗺️ 匯出 GeoJSON
          </button>
        </div>
      </div>
    </div>
  );
}
