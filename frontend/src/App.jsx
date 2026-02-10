import { useState, useEffect } from 'react';
import Map3D from './components/Map3D';
import RouteForm from './components/RouteForm';
import ResultsPanel from './components/ResultsPanel';
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
        <div className="header-status">
          <span className={`status-indicator ${apiConnected ? 'connected' : ''}`}>
            {apiConnected ? '🟢 已連接' : '🔴 未連接'}
          </span>
        </div>
      </header>

      {/* Main Content */}
      <div className="main-content">
        {/* Left Panel - Route Form */}
        <aside className="left-panel">
          <RouteForm
            areas={areas}
            onSubmit={handlePlanRoute}
            loading={loading}
            onClearRoute={handleClearRoute}
            onRouteSelect={setSelectedRoute}
            onWaypointsChange={setSelectedWaypoints}
          />
        </aside>

        {/* Center Panel - Map */}
        <main className="center-panel">
          <Map3D
            route={route}
            isLoop={false}
            selectedRoute={selectedRoute}
            selectedWaypoints={selectedWaypoints}
          />
        </main>

        {/* Right Panel - Results */}
        <aside className="right-panel">
          <ResultsPanel
            route={route}
            onExport={handleExport}
          />
        </aside>
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

      {/* Toast Container */}
      <div id="toast-container"></div>
    </div>
  );
}

export default App;
