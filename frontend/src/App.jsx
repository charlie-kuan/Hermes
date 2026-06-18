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
  const [error, setError] = useState(null);

  // For route preview
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [selectedWaypoints, setSelectedWaypoints] = useState([]);

  // Sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('plan'); // 'plan' or 'results'
  const [adminOpen, setAdminOpen] = useState(false);

  // Check API health and load areas on mount
  useEffect(() => {
    checkApiHealth();
    loadAreas();
  }, []);

  const checkApiHealth = async () => {
    try {
      await apiService.checkHealth();
      setApiConnected(true);
    } catch (err) {
      setApiConnected(false);
      console.error('API health check failed:', err);
    }
  };

  const loadAreas = async () => {
    try {
      const data = await apiService.getAreas();
      setAreas(data.areas || []);
    } catch (err) {
      console.error('Failed to load areas:', err);
      showToast('無法載入區域列表', 'error');
    }
  };


  const handleClearRoute = () => {
    setRoute(null);
  };

  const handlePlanRoute = async (params) => {
    setLoading(true);
    setError(null);
    setRoute(null);

    try {
      const result = await apiService.planRoute(params);
      setRoute(result);
      showToast('路線規劃完成！', 'success');
      // Auto-switch to results tab
      setActiveTab('results');
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || '路線規劃失敗';
      setError(errorMsg);
      showToast(errorMsg, 'error');
      console.error('Route planning failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = (format) => {
    showToast(`已匯出為 ${format.toUpperCase()}`, 'success');
  };

  const showToast = (message, type = 'info') => {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    const container = document.getElementById('toast-container');
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'slideOut 0.3s ease-out';
      setTimeout(() => container.removeChild(toast), 300);
    }, 3000);
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <h1>🏔️ Project Hermes</h1>
          <p>一站式登山行程規劃系統</p>
        </div>
        <div className="header-status" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span className={`status-indicator ${apiConnected ? 'connected' : ''}`}>
            {apiConnected ? '🟢 已連接' : '🔴 未連接'}
          </span>
          <button
            onClick={() => setAdminOpen(true)}
            style={{ background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.3)', color: 'white', padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}
          >
            ⚙️ 管理
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="main-content">
        {/* Left Sidebar */}
        <aside className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
          {/* Sidebar Header with Tabs */}
          <div className="sidebar-header">
            <div className="sidebar-tabs">
              <button
                className={`tab-button ${activeTab === 'plan' ? 'active' : ''}`}
                onClick={() => setActiveTab('plan')}
              >
                📍 路線規劃
              </button>
              <button
                className={`tab-button ${activeTab === 'results' ? 'active' : ''}`}
                onClick={() => setActiveTab('results')}
              >
                📊 路線資訊
              </button>
            </div>
            <button
              className="sidebar-toggle"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              title={sidebarOpen ? '收起側邊欄' : '展開側邊欄'}
            >
              {sidebarOpen ? '◀' : '▶'}
            </button>
          </div>

          {/* Sidebar Content */}
          <div className="sidebar-content">
            {activeTab === 'plan' && (
              <RouteForm
                areas={areas}
                onSubmit={handlePlanRoute}
                loading={loading}
                onClearRoute={handleClearRoute}
                onRouteSelect={setSelectedRoute}
                onWaypointsChange={setSelectedWaypoints}
              />
            )}

            {activeTab === 'results' && (
              <ResultsPanel
                route={route}
                onExport={handleExport}
              />
            )}
          </div>
        </aside>

        {/* Map Section */}
        <main className="map-section">
          <Map3D
            route={route}
            isLoop={false}
            selectedRoute={selectedRoute}
            selectedWaypoints={selectedWaypoints}
          />

          {/* Floating Toggle Button (when sidebar is closed) */}
          {!sidebarOpen && (
            <button
              className="floating-toggle"
              onClick={() => setSidebarOpen(true)}
              title="展開側邊欄"
            >
              ▶
            </button>
          )}
        </main>
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="loading-overlay">
          <div className="loading-spinner">
            <div className="spinner"></div>
            <p>正在規劃路線...</p>
            <small style={{ marginTop: '10px', color: '#aaa', fontSize: '0.9em' }}>
              首次規劃需要下載地圖數據，可能需要30-60秒
            </small>
          </div>
        </div>
      )}

      {/* Admin Panel */}
      {adminOpen && <AdminPanel onClose={() => setAdminOpen(false)} />}

      {/* Toast Container */}
      <div id="toast-container"></div>
    </div>
  );
}

export default App;
