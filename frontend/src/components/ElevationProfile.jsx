import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function ElevationProfile({ route }) {
  if (!route || !route.segments) {
    return null;
  }

  // Extract elevation data from route segments
  const elevationData = [];
  const distanceData = [];
  let cumulativeDistance = 0;

  // Get elevation from a geometry point (returns null if not a 3D point)
  const geomElev = (point) =>
    point && point.length >= 3 && point[2] != null ? point[2] : null;

  // Find first valid geometry elevation in a segment's geometry array
  const firstGeomElev = (geom) => {
    if (!geom) return null;
    for (const p of geom) { const e = geomElev(p); if (e !== null) return e; }
    return null;
  };
  const lastGeomElev = (geom) => {
    if (!geom) return null;
    for (let i = geom.length - 1; i >= 0; i--) { const e = geomElev(geom[i]); if (e !== null) return e; }
    return null;
  };

  // Add starting point — prefer geometry[0] DEM elevation over node tag, null if unknown
  if (route.segments.length > 0) {
    const firstSeg = route.segments[0];
    const startElev = firstGeomElev(firstSeg.geometry) ?? firstSeg.start_node.elevation ?? null;
    elevationData.push(startElev);
    distanceData.push(0);
  }

  // Process each segment
  route.segments.forEach((segment) => {
    if (segment.geometry && segment.geometry.length > 1) {
      const geom = segment.geometry;
      const numPoints = geom.length;

      // Use geometry-derived endpoints for interpolation; null if truly unknown
      const interpStart = firstGeomElev(geom) ?? segment.start_node.elevation ?? null;
      const interpEnd   = lastGeomElev(geom)  ?? segment.end_node.elevation   ?? null;

      geom.forEach((point, idx) => {
        if (idx === 0) return;
        let elevation = geomElev(point);
        if (elevation === null && interpStart !== null && interpEnd !== null) {
          elevation = interpStart + (interpEnd - interpStart) * (idx / (numPoints - 1));
        }
        cumulativeDistance += segment.distance / (numPoints - 1);
        elevationData.push(elevation); // may be null — filled in below
        distanceData.push(cumulativeDistance);
      });
    } else {
      cumulativeDistance += segment.distance;
      elevationData.push(segment.end_node.elevation ?? null);
      distanceData.push(cumulativeDistance);
    }
  });

  // Fill null gaps with linear interpolation between known neighbours
  const interpolateNulls = (data) => {
    const out = [...data];
    let i = 0;
    while (i < out.length) {
      if (out[i] === null) {
        const lo = i - 1;
        let hi = i + 1;
        while (hi < out.length && out[hi] === null) hi++;
        if (lo >= 0 && hi < out.length) {
          for (let j = i; j < hi; j++)
            out[j] = out[lo] + (out[hi] - out[lo]) * ((j - lo) / (hi - lo));
        } else if (lo >= 0) {
          for (let j = i; j < out.length; j++) out[j] = out[lo];
        } else if (hi < out.length) {
          for (let j = 0; j < hi; j++) out[j] = out[hi];
        }
        i = hi;
      } else {
        i++;
      }
    }
    return out;
  };
  const filled = interpolateNulls(elevationData);
  for (let i = 0; i < elevationData.length; i++) elevationData[i] = filled[i] ?? 0;

  // Remove outliers using a large window median filter, run 3 passes so clusters
  // of bad SRTM points don't corrupt each other's median.
  const filterOutliers = (data, window = 25, threshold = 200) => {
    const out = [...data];
    for (let i = 0; i < out.length; i++) {
      const lo = Math.max(0, i - window);
      const hi = Math.min(out.length, i + window + 1);
      const sorted = out.slice(lo, hi).slice().sort((a, b) => a - b);
      const median = sorted[Math.floor(sorted.length / 2)];
      if (Math.abs(out[i] - median) > threshold) {
        out[i] = median;
      }
    }
    return out;
  };
  // 1. Remove gross outliers (bad DEM pixels) with 3-pass median filter
  let filtered = filterOutliers(elevationData);
  filtered = filterOutliers(filtered);
  filtered = filterOutliers(filtered);

  // 2. Smooth remaining DEM noise with a Gaussian-weighted moving average.
  //    Window ≈ 200 m worth of points; clip to at least 3 so short segments still smooth.
  const smoothProfile = (data, halfWin = 5) => {
    if (data.length <= 2) return data;
    // Gaussian weights (σ = halfWin/2)
    const sigma = halfWin / 2;
    const weights = Array.from({ length: 2 * halfWin + 1 }, (_, k) => {
      const d = k - halfWin;
      return Math.exp(-(d * d) / (2 * sigma * sigma));
    });
    return data.map((_, i) => {
      let wSum = 0, vSum = 0;
      for (let k = -halfWin; k <= halfWin; k++) {
        const j = i + k;
        if (j < 0 || j >= data.length) continue;
        const w = weights[k + halfWin];
        vSum += data[j] * w;
        wSum += w;
      }
      return vSum / wSum;
    });
  };
  filtered = smoothProfile(filtered, 5);

  for (let i = 0; i < elevationData.length; i++) elevationData[i] = filtered[i];

  // Calculate stats
  const maxElevation = Math.max(...elevationData);
  const minElevation = Math.min(...elevationData);
  const elevationRange = maxElevation - minElevation;

  const chartData = {
    labels: distanceData.map(d => d.toFixed(1)),
    datasets: [
      {
        label: '海拔高度',
        data: elevationData,
        fill: true,
        backgroundColor: 'rgba(37, 99, 235, 0.1)',
        borderColor: 'rgba(37, 99, 235, 0.8)',
        borderWidth: 2,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: 'rgba(37, 99, 235, 1)',
      }
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: {
        display: false
      },
      title: {
        display: true,
        text: '高度變化圖',
        font: {
          size: 16,
          weight: 'bold'
        },
        color: '#1e293b',
        padding: {
          top: 10,
          bottom: 20
        }
      },
      tooltip: {
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        titleColor: '#1e293b',
        bodyColor: '#64748b',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        padding: 12,
        displayColors: false,
        callbacks: {
          title: function(context) {
            return `距離: ${context[0].label} km`;
          },
          label: function(context) {
            return `海拔: ${context.parsed.y.toFixed(0)} m`;
          }
        }
      }
    },
    scales: {
      x: {
        display: true,
        title: {
          display: true,
          text: '距離 (km)',
          color: '#64748b',
          font: {
            size: 12,
            weight: '600'
          }
        },
        ticks: {
          color: '#64748b',
          maxTicksLimit: 10
        },
        grid: {
          color: 'rgba(226, 232, 240, 0.5)'
        }
      },
      y: {
        display: true,
        title: {
          display: true,
          text: '海拔 (m)',
          color: '#64748b',
          font: {
            size: 12,
            weight: '600'
          }
        },
        ticks: {
          color: '#64748b',
          callback: function(value) {
            return value.toFixed(0) + 'm';
          }
        },
        grid: {
          color: 'rgba(226, 232, 240, 0.5)'
        },
        // Add some padding to the scale
        suggestedMin: Math.max(0, minElevation - elevationRange * 0.1),
        suggestedMax: maxElevation + elevationRange * 0.1
      }
    }
  };

  return (
    <div style={{
      background: '#ffffff',
      padding: '1.5rem',
      borderRadius: '8px',
      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
      marginBottom: '1rem'
    }}>
      <div style={{ height: '250px' }}>
        <Line data={chartData} options={options} />
      </div>

      {/* Elevation Stats */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '0.75rem',
        marginTop: '1rem',
        paddingTop: '1rem',
        borderTop: '1px solid #e2e8f0'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem' }}>
            最高點
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: '600', color: '#1e293b' }}>
            {maxElevation.toFixed(0)}m
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem' }}>
            最低點
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: '600', color: '#1e293b' }}>
            {minElevation.toFixed(0)}m
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem' }}>
            高度差
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: '600', color: '#1e293b' }}>
            {elevationRange.toFixed(0)}m
          </div>
        </div>
      </div>
    </div>
  );
}
