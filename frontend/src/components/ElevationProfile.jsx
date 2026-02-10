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

  // Add starting point
  if (route.segments.length > 0) {
    const firstSegment = route.segments[0];
    elevationData.push(firstSegment.start_node.elevation || 0);
    distanceData.push(0);
  }

  // Process each segment
  route.segments.forEach((segment) => {
    const startElevation = segment.start_node.elevation || 0;
    const endElevation = segment.end_node.elevation || 0;

    // If segment has detailed geometry with elevation data
    if (segment.geometry && segment.geometry.length > 1) {
      const numPoints = segment.geometry.length;
      segment.geometry.forEach((point, idx) => {
        if (idx > 0) { // Skip first point as it's the same as previous segment's end
          // Check if point has elevation data (3D point: [lat, lon, elevation])
          let elevation;
          if (point.length >= 3 && point[2] != null) {
            // Use DEM elevation data from backend
            elevation = point[2];
          } else {
            // Fallback to linear interpolation
            const elevationRatio = idx / (numPoints - 1);
            elevation = startElevation + (endElevation - startElevation) * elevationRatio;
          }

          cumulativeDistance += segment.distance / (numPoints - 1);
          elevationData.push(elevation);
          distanceData.push(cumulativeDistance);
        }
      });
    } else {
      // Use end point elevation if no detailed geometry
      cumulativeDistance += segment.distance;
      elevationData.push(endElevation);
      distanceData.push(cumulativeDistance);
    }
  });

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
