# GPS Traces Sample Data

This directory contains sample GPS trace data for the Yushan (玉山) area.

## Files

- `sample_traces.geojson` - Sample hiking GPS traces in GeoJSON format

## Using Your Own Data

1. **From Hiking Apps:**
   - Export GPX files from AllTrails, Komoot, Gaia GPS, etc.
   - Place them in this directory

2. **From GPS Devices:**
   - Download tracks from Garmin, Suunto, etc.
   - Save as .gpx files here

3. **From OpenStreetMap:**
   - Visit: https://www.openstreetmap.org/traces
   - Search for area: Yushan / 玉山
   - Download public GPS traces
   - Place in this directory

4. **From Strava:**
   - Request Strava bulk export
   - Convert to GeoJSON (see GPS_TRACES.md)
   - Place result here

## Format Requirements

### GPX Format
```xml
<?xml version="1.0"?>
<gpx version="1.1">
  <trk>
    <name>Trail Name</name>
    <trkseg>
      <trkpt lat="23.4652" lon="120.8567"><ele>3000</ele></trkpt>
      <trkpt lat="23.4658" lon="120.8571"><ele>3010</ele></trkpt>
      ...
    </trkseg>
  </trk>
</gpx>
```

### GeoJSON Format
```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "geometry": {
      "type": "LineString",
      "coordinates": [[120.8567, 23.4652], [120.8571, 23.4658], ...]
    },
    "properties": {
      "name": "Trail Name"
    }
  }]
}
```

## Usage

Run the enrichment script:
```bash
python scripts/enrich_with_gps_traces.py
```

The system will:
1. Load all .gpx and .geojson files from this directory
2. Match GPS traces to trail edges in the graph
3. Calculate popularity scores based on trace density
4. Update the cached graph with new popularity data

## Tips

- More traces = better popularity data
- Minimum 10-20 traces for meaningful results
- Mix of different routes gives best coverage
- Regular updates keep data current
