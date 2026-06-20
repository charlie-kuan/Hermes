import { useState, useEffect } from 'react';
import Map3D from './components/Map3D';
import RouteForm from './components/RouteForm';
import ResultsPanel from './components/ResultsPanel';
import AdminPanel from './components/AdminPanel';
import { apiService } from './services/api';
import './App.css';

function App() {
  const [areas, setAreas] = useState([]);
  const [apiConnected, setApiConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [route, setRoute] = useState(null);

  // Lifted selection state (shared between RouteForm and Map3D)
  const [selectedArea, setSelectedArea] = useState(null);
  const [selectedPoints, setSelectedPoints] = useState([]);
  const [nextUniqueId, setNextUniqueId] = useState(1);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [wideMode, setWideMode] = useState(false);
  const isAdminRoute = window.location.pathname === '/admin';
  const [adminOpen, setAdminOpen] = useState(isAdminRoute);
  const [theme, setTheme] = useState('light');

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.setAttribute('data-theme', next === 'light' ? 'light' : '');
  };

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme === 'light' ? 'light' : '');
  }, [theme]);

  useEffect(() => {
    checkApiHealth();
    loadAreas();
  }, []);

  const checkApiHealth = async () => {
    try {
      await apiService.checkHealth();
      setApiConnected(true);
    } catch {
      setApiConnected(false);
    }
  };

  const loadAreas = async () => {
    try {
      const data = await apiService.getAreas();
      setAreas(data.areas || []);
    } catch {
      showToast('無法載入區域列表', 'error');
    }
  };

  // Area change: reset point selection
  const handleAreaChange = (area) => {
    setSelectedArea(area);
    setSelectedPoints([]);
    setNextUniqueId(1);
    setRoute(null);
  };

  // Add point (from sidebar list or map click)
  const handlePointAdd = (pointId) => {
    setSelectedPoints(prev => [...prev, { id: nextUniqueId, pointId }]);
    setNextUniqueId(prev => prev + 1);
  };

  const handlePointRemove = (uid) => {
    setSelectedPoints(prev => prev.filter(item => item.id !== uid));
  };

  // Reorder via drag-and-drop
  const handlePointReorder = (fromIndex, toIndex) => {
    if (fromIndex === toIndex) return;
    setSelectedPoints(prev => {
      const arr = [...prev];
      const [moved] = arr.splice(fromIndex, 1);
      arr.splice(toIndex, 0, moved);
      return arr;
    });
  };

  // Quick route pre-fill
  const handleQuickRoute = (pointIds) => {
    let uid = nextUniqueId;
    setSelectedPoints(pointIds.map(pointId => ({ id: uid++, pointId })));
    setNextUniqueId(uid);
  };

  const handleClearRoute = () => {
    setRoute(null);
    setSelectedPoints([]);
  };

  // Goes back to form but keeps area + points so user can tweak and re-plan
  const handleReplan = () => {
    setRoute(null);
  };

  const handlePlanRoute = async (params) => {
    setLoading(true);
    setRoute(null);
    try {
      const result = await apiService.planRoute(params);
      setRoute(result);
      showToast('路線規劃完成', 'success');
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || '路線規劃失敗';
      showToast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  const showToast = (message, type = 'info') => {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    const container = document.getElementById('toast-container');
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.animation = 'slideOut 0.25s ease-out';
      setTimeout(() => container.removeChild(toast), 250);
    }, 3000);
  };

  return (
    <div className="app">
      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-brand">
          <span className="brand-icon">⛰️</span>
          <span className="brand-name">Project Hermes</span>
          <span className="brand-sub">百岳行程規劃</span>
        </div>
        <div className="topbar-actions">
          <span className={`status-dot ${apiConnected ? 'online' : ''}`}>
            {apiConnected ? 'API 已連線' : 'API 未連線'}
          </span>
          <button className="btn-theme" onClick={toggleTheme} title={theme === 'dark' ? '切換亮色模式' : '切換暗色模式'}>
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
      </header>

      {/* Full-screen map */}
      <div className="map-canvas">
        <Map3D
          route={route}
          availablePoints={selectedArea?.points || []}
          selectedPoints={selectedPoints}
          onPointClick={handlePointAdd}
        />
      </div>

      {/* Glass Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? '' : 'hidden'} ${wideMode ? 'wide' : ''}`}>
        <div className="sidebar-header">
          <span className="sidebar-header-title">
            {route ? '📊 路線資訊' : '📍 路線規劃'}
          </span>
          <button
            className={`btn-wide-toggle ${wideMode ? 'active' : ''}`}
            onClick={() => setWideMode(w => !w)}
            title={wideMode ? '收合成單欄' : '展開成雙欄'}
          >
            {wideMode ? '⊟' : '⊞'}
          </button>
        </div>
        <div className="sidebar-content">
          {!route ? (
            <RouteForm
              areas={areas}
              selectedArea={selectedArea}
              selectedPoints={selectedPoints}
              onAreaChange={handleAreaChange}
              onPointAdd={handlePointAdd}
              onPointRemove={handlePointRemove}
              onPointReorder={handlePointReorder}
              onQuickRoute={handleQuickRoute}
              onSubmit={handlePlanRoute}
              onClearRoute={handleClearRoute}
              loading={loading}
              wideMode={wideMode}
            />
          ) : (
            <ResultsPanel
              route={route}
              onReplan={handleReplan}
              onClearRoute={handleClearRoute}
              wideMode={wideMode}
            />
          )}
        </div>
      </aside>

      {/* Sidebar Toggle */}
      <button
        className={`sidebar-toggle ${sidebarOpen ? 'sidebar-open' : ''} ${!route && wideMode ? 'wide' : ''}`}
        onClick={() => setSidebarOpen(!sidebarOpen)}
        title={sidebarOpen ? '收起側欄' : '展開側欄'}
      >
        {sidebarOpen ? '◀' : '▶'}
      </button>


      {loading && (
        <div className="loading-overlay">
          <div className="loading-card">
            <div className="spinner" />
            <p>正在規劃路線...</p>
            <small>首次規劃需下載地圖資料，約需 30–60 秒</small>
          </div>
        </div>
      )}

      {adminOpen && <AdminPanel onClose={() => setAdminOpen(false)} />}
      <div id="toast-container" />
    </div>
  );
}

export default App;
