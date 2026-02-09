# API Documentation

## Base URL

```
http://localhost:8000
```

## Authentication

Currently no authentication is required (for MVP). Production deployment should add API key or OAuth2.

## Endpoints

### Health & Info

#### GET /health

Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-20T10:30:00"
}
```

#### GET /

Root endpoint with API information.

**Response**:
```json
{
  "name": "Project Hermes",
  "version": "0.1.0",
  "description": "Intelligent hiking route planning system",
  "docs": "/docs",
  "health": "/health"
}
```

---

### Areas

#### GET /api/v1/areas

List all available hiking areas.

**Response**:
```json
{
  "areas": [
    {
      "area_id": "test_region",
      "name": "Test Region",
      "description": "Small test region for development",
      "country": "Taiwan",
      "bbox": [23.4, 120.9, 23.5, 121.0],
      "elevation_range": [1000, 3000],
      "trail_count": 50,
      "peak_count": 5,
      "hut_count": 3
    }
  ],
  "total": 1
}
```

#### GET /api/v1/areas/{area_id}

Get details for a specific hiking area.

**Parameters**:
- `area_id` (path): Area identifier

**Response**: Same as single area object above

**Errors**:
- `404`: Area not found

---

### Routes

#### POST /api/v1/routes/plan

Plan a hiking route with full details.

**Request Body**:
```json
{
  "area_id": "test_region",
  "start_lat": 23.45,
  "start_lon": 120.95,
  "end_lat": 23.48,
  "end_lon": 120.98,
  "loop_route": false,
  "via_points": [
    {"lat": 23.46, "lon": 120.96}
  ],
  "max_distance": 20,
  "required_waypoints": ["peak", "hut"],
  "multi_day": true,
  "target_hours_per_day": 7,
  "hiker_fitness": "moderate",
  "pack_weight_kg": 12,
  "prefer_huts": true,
  "avoid_difficult": false
}
```

**Parameters**:

Required:
- `area_id`: Area identifier
- `start_lat`: Starting latitude
- `start_lon`: Starting longitude

Optional:
- `end_lat`, `end_lon`: Ending coordinates (omit for loop)
- `loop_route` (default: false): Create loop route
- `via_points`: Array of waypoints to visit
- `max_distance`: Maximum distance in km
- `required_waypoints`: Required waypoint types
- `multi_day` (default: false): Plan as multi-day route
- `target_hours_per_day` (default: 7): Target hiking hours per day
- `hiker_fitness` (default: "moderate"): "beginner", "moderate", or "expert"
- `pack_weight_kg` (default: 12): Pack weight in kg
- `prefer_huts` (default: true): Prefer huts over campsites
- `avoid_difficult` (default: false): Avoid difficult trails

**Response**:
```json
{
  "route_id": "abc123...",
  "area_id": "test_region",
  "segments": [
    {
      "start_node": {
        "id": "node_123",
        "type": "trailhead",
        "lat": 23.45,
        "lon": 120.95,
        "elevation": 1500,
        "name": "Trailhead Parking",
        "amenities": ["parking"]
      },
      "end_node": { ... },
      "distance": 5.2,
      "elevation_gain": 450,
      "elevation_loss": 50,
      "estimated_time": 2.1,
      "difficulty": "moderate",
      "trail_name": "Mountain Trail"
    }
  ],
  "total_distance": 15.5,
  "total_elevation_gain": 1200,
  "total_elevation_loss": 800,
  "estimated_time": {
    "optimistic": 5.2,
    "normal": 6.5,
    "conservative": 7.8
  },
  "difficulty": "moderate",
  "is_loop": false,
  "waypoints": [ ... ],
  "multi_day": true,
  "days": [
    {
      "day_number": 1,
      "segments": [ ... ],
      "start_node": { ... },
      "end_node": { ... },
      "total_distance": 8.0,
      "total_elevation_gain": 650,
      "total_elevation_loss": 100,
      "estimated_time": 3.5,
      "difficulty": "moderate",
      "overnight_stop": {
        "id": "hut_456",
        "type": "hut",
        "name": "Mountain Hut",
        "amenities": ["shelter", "water"]
      }
    }
  ],
  "total_days": 2,
  "overnight_stops": [ ... ],
  "equipment": [
    {
      "category": "essential",
      "items": ["Backpack", "Water bottles", "First aid kit", ...]
    },
    {
      "category": "overnight",
      "items": ["Sleeping bag", "Tent", ...]
    }
  ],
  "food": {
    "daily_calories": 2800,
    "total_calories": 5600,
    "meals_per_day": 3,
    "daily_water_liters": 3.0,
    "notes": [
      "Plan for 2 day(s) of hiking",
      "Water sources available at overnight stops"
    ]
  }
}
```

**Errors**:
- `400`: Invalid parameters or no valid path found
- `404`: Area not found

#### GET /api/v1/routes/{route_id}

Get a previously planned route by ID.

**Parameters**:
- `route_id` (path): Route identifier

**Response**: Same as POST /routes/plan response

**Errors**:
- `404`: Route not found

#### GET /api/v1/routes/{route_id}/export

Export route to GPX or GeoJSON format.

**Parameters**:
- `route_id` (path): Route identifier
- `format` (query): Export format ("gpx" or "geojson")

**Response**: File download with appropriate Content-Type

**Errors**:
- `404`: Route not found
- `400`: Invalid format

---

## Data Models

### Node Types

- `trailhead`: Trail starting point
- `intersection`: Trail junction
- `peak`: Mountain peak
- `hut`: Alpine hut or refuge
- `campsite`: Camping location
- `water_source`: Water source
- `viewpoint`: Scenic viewpoint

### Trail Difficulty

- `easy`: Well-marked trails, gentle terrain (SAC T1)
- `moderate`: Mountain trails, some steep sections (SAC T2)
- `difficult`: Demanding mountain trails (SAC T3)
- `expert`: Alpine terrain, requires experience (SAC T4+)

### Fitness Levels

- `beginner`: 4 km/h base speed
- `moderate`: 5 km/h base speed
- `expert`: 6 km/h base speed

---

## Error Responses

All errors return JSON with the following structure:

```json
{
  "error": "Error type",
  "detail": "Detailed error message"
}
```

### HTTP Status Codes

- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Not found
- `422`: Validation error
- `500`: Internal server error

---

## Rate Limiting

Currently no rate limiting (MVP). Production should implement:
- 100 requests per minute per IP
- 1000 requests per day per API key

---

## Interactive Documentation

Visit http://localhost:8000/docs for interactive Swagger UI documentation.
