"""
GPS Trace Data Integration Guide
=================================

This document explains how to integrate GPS trace data to improve route popularity scoring.

## Overview

The system now supports using **Public GPS Traces** to determine trail popularity. The more
people who have walked a trail (based on their GPS tracks), the higher its popularity score.

## Why Use GPS Traces?

### Current System (OSM Attributes)
- Based on trail names, official routes, surface quality
- Static data that doesn't reflect actual usage
- May miss informal but popular trails

### With GPS Traces
- ✅ Real-world usage data from actual hikers
- ✅ Discovers popular unmarked trails
- ✅ Reflects seasonal trends and current preferences
- ✅ Crowdsourced validation of route quality

## Data Sources

### 1. OpenStreetMap GPS Traces
- **URL**: https://www.openstreetmap.org/traces
- **Format**: GPX
- **License**: Open Database License (ODbL)
- **How to get**:
  1. Go to OSM GPS traces page
  2. Filter by area (use bbox)
  3. Download public GPS traces
  4. Save to `data/gps_traces/{area_id}/`

### 2. Your Own GPX Files
- Export from hiking apps (AllTrails, Komoot, Gaia GPS, etc.)
- Export from GPS devices (Garmin, Suunto, etc.)
- Convert from other formats using `gpxpy`

### 3. Strava Global Heatmap (Future)
- Requires Strava API access
- High-density data in popular areas
- Implementation placeholder in `gps_trace_processor.py`

### 4. Wikiloc (Future)
- Popular hiking route platform
- Requires API access or web scraping
- Implementation placeholder in `gps_trace_processor.py`

## File Structure

```
data/
  gps_traces/
    yushan/              # Area ID
      trace001.gpx       # Individual GPS tracks
      trace002.gpx
      strava_export.geojson
      osm_traces.geojson
    hehuan/
      ...
    xueshan/
      ...
```

## Usage

### Method 1: Automatic Enrichment (Recommended)

```python
from app.services.graph_service import GraphService

graph_service = GraphService()

# Load/build graph
graph = graph_service.get_or_build_graph("yushan", bbox=[23.4, 120.8, 23.6, 121.0])

# Enrich with GPS traces from data/gps_traces/yushan/
graph_service.enrich_with_gps_traces(
    graph=graph,
    area_id="yushan",
    blend_factor=0.7  # 70% GPS traces, 30% OSM attributes
)
```

### Method 2: Manual Processing

```python
from app.core.gps_trace_processor import GPSTraceProcessor
from pathlib import Path

processor = GPSTraceProcessor()

# Load traces from GPX files
traces = processor.load_gps_traces_from_gpx_files(Path("data/gps_traces/yushan"))

# Or from GeoJSON
traces = processor.load_gps_traces_from_geojson(Path("data/gps_traces/yushan/all_traces.geojson"))

# Calculate popularity and update graph
processor.enrich_graph_with_trace_popularity(
    graph=graph,
    gps_traces=traces,
    blend_factor=0.7
)
```

### Method 3: Using in Route Planning

```python
from app.services.routing_service import RoutingService

routing_service = RoutingService(graph_service)

# Plan route with popularity preference
route = routing_service.plan_route(
    graph=graph,
    start_node_id="node_123",
    end_node_id="node_456",
    preferences={
        'distance': 1.0,
        'elevation': 0.5,
        'difficulty': 0.3,
        'popularity': 0.5  # ← Prefer popular trails (GPS trace-based)
    }
)
```

## Configuration

### Blend Factor
Controls the weight between OSM attributes and GPS trace data:

- `0.0` = 100% OSM attributes (names, surface, etc.)
- `0.5` = Equal weight (50/50)
- `0.7` = **Recommended** - 70% GPS traces, 30% OSM
- `1.0` = 100% GPS traces only

**Recommendation**: Start with 0.7 for areas with good GPS trace coverage.

### Buffer Distance
When matching GPS traces to trail edges:

- `buffer_distance=30.0` meters (default)
- Increase for sparse/noisy GPS data
- Decrease for dense urban trails

```python
processor.calculate_trace_based_popularity(
    graph=graph,
    gps_traces=traces,
    buffer_distance=50.0  # More forgiving matching
)
```

## Popularity Score Scale

After GPS trace processing, edges receive scores:

- **0.5** - No GPS traces (unpopular/unmapped)
- **1.0** - Median usage (average popularity)
- **2.0** - Top 10% most used trails
- **2.5** - Extremely popular trails (top 1%)

## Implementation Details

### How It Works

1. **Load GPS Traces**: Read GPX/GeoJSON files
2. **Match to Edges**: Find which trail edges each GPS trace crosses
3. **Count Crossings**: Count how many traces pass near each edge
4. **Normalize**: Convert counts to 0.5-2.5 scale
5. **Blend**: Combine with existing OSM-based scores
6. **Update**: Apply new popularity scores to graph edges

### Spatial Matching

Uses Shapely for efficient geometric operations:
- Converts GPS traces to LineString geometries
- Calculates distance to trail edges
- Traces within buffer_distance are counted as matches

### Performance

- ~100 traces: < 1 second
- ~1000 traces: < 10 seconds
- ~10000 traces: < 2 minutes

For large datasets, results are cached.

## API Integration

### New Endpoint (Future)

```
POST /api/v1/admin/areas/{area_id}/enrich-gps-traces

Request:
{
  "blend_factor": 0.7,
  "gps_trace_source": "directory"  // or "osm", "strava"
}

Response:
{
  "area_id": "yushan",
  "traces_processed": 1247,
  "edges_updated": 3892,
  "avg_popularity_before": 1.18,
  "avg_popularity_after": 1.34
}
```

## Example: Convert Strava Export to GeoJSON

If you have Strava bulk export:

```python
import gpxpy
import json

def convert_gpx_to_geojson(gpx_dir, output_file):
    features = []
    
    for gpx_file in Path(gpx_dir).glob("*.gpx"):
        with open(gpx_file, 'r') as f:
            gpx = gpxpy.parse(f)
            
            for track in gpx.tracks:
                for segment in track.segments:
                    coords = [[p.longitude, p.latitude] for p in segment.points]
                    
                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coords
                        },
                        "properties": {
                            "name": track.name or "Unknown"
                        }
                    })
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open(output_file, 'w') as f:
        json.dump(geojson, f)
    
    print(f"Converted {len(features)} tracks to {output_file}")

# Usage
convert_gpx_to_geojson("strava_export", "data/gps_traces/yushan/strava.geojson")
```

## Benefits by Trail Type

### Popular Trails
- High GPS trace count → high popularity score
- Routes naturally favor these well-trodden paths
- Better time estimates (more data points)

### Remote/Expert Trails
- Few GPS traces → lower popularity score
- System can still plan routes using OSM attributes
- Blend factor helps balance popularity vs. other factors

### Unmarked Trails
- GPS traces reveal "social trails" not in OSM
- Can be added to graph if enough trace density
- Helps discover local favorites

## Maintenance

### Updating GPS Traces

Run periodically to keep popularity data current:

```bash
python scripts/enrich_with_gps_traces.py
```

### Monitoring

Check graph statistics:

```python
stats = graph_service.get_graph_stats(graph)
print(f"Edges with high popularity (>2.0): {count_high_popularity}")
```

## Future Enhancements

- [ ] Real-time OSM GPS trace API integration
- [ ] Strava Metro API integration
- [ ] Wikiloc data integration
- [ ] Seasonal popularity tracking
- [ ] Time-of-day usage patterns
- [ ] Difficulty validation from GPS speeds
- [ ] Automatic trail discovery from dense GPS traces

## Troubleshooting

### No GPS traces found
- Check directory path: `data/gps_traces/{area_id}/`
- Verify file formats: `.gpx` or `.geojson`
- Check file permissions

### Low popularity scores after enrichment
- May need more GPS traces
- Lower blend_factor to rely more on OSM
- Check buffer_distance setting

### Routing ignores popularity
- Set `preferences['popularity'] > 0` in route planning
- Higher values = stronger preference for popular trails
- Combine with reasonable distance/elevation weights

## License

GPS trace data sources have different licenses:
- **OSM GPS Traces**: ODbL - must credit and share-alike
- **Strava**: Check Strava Metro licensing
- **Personal GPX**: Your own license

Always comply with data source licenses.

## Contact

For questions or contributions regarding GPS trace integration, please open an issue.
