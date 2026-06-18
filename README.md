# Project Hermes - Intelligent Hiking Route Planning System

**Version**: 0.2.0

Project Hermes is a production-quality FastAPI backend for intelligent hiking route planning. It processes OpenStreetMap trail data, provides smart routing algorithms optimized for hiking, estimates hiking time using enhanced Naismith's Rule, automatically splits multi-day routes, and offers equipment and food recommendations.

## Features

- **Smart Route Planning**: Plan hiking routes with customizable preferences (distance, elevation, difficulty)
- **GPS Trace-Based Popularity**: 🆕 Use real hiker GPS tracks to identify popular trails (crowdsourced route validation)
- **Multi-Day Planning**: Automatically split long routes into daily segments with overnight stops at huts or campsites
- **Time Estimation**: Enhanced Naismith's Rule with adjustments for fitness level, pack weight, and terrain difficulty
- **Equipment Recommendations**: Context-aware gear suggestions based on route characteristics and conditions
- **Food & Water Planning**: Calculate calorie and water needs for your hike
- **GPX & GeoJSON Export**: Export routes for GPS devices and mapping applications
- **OSM Integration**: Leverage OpenStreetMap's rich trail data
- **Elevation Data**: SRTM elevation integration for accurate climb/descent calculations

## Technology Stack

- **FastAPI** + Uvicorn - High-performance API server
- **NetworkX** - Graph data structures and routing algorithms
- **OSMnx** - OpenStreetMap data processing
- **SRTM** - Elevation data
- **gpxpy** - GPX file generation
- **Pydantic v2** - Data validation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI Layer                          │
│  /areas  /routes/plan  /routes/estimate  /routes/export     │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                      Services Layer                          │
│  RoutingService  PlanningService  EstimationService         │
│  RecommendationService  ExportService  GraphService         │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    Core Algorithms Layer                     │
│  OSMProcessor  ElevationProcessor  CostFunctions            │
│  TimeEstimators  GraphAlgorithms                            │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                        Data Layer                            │
│  NetworkX Graph  OSM Cache  Elevation Cache  Graph Cache    │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.9 or higher
- pip or poetry for dependency management

### Setup

1. **Clone or navigate to project directory**:
   ```bash
   cd /Users/charlie/Desktop/Project/Project_Hermes
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Create data directories** (already done by config.py on first run):
   ```bash
   mkdir -p data/{osm,elevation,graphs,gps_traces}
   ```

6. **Optional: Add GPS traces for popularity data**:
   ```bash
   # Place your GPS trace files (.gpx or .geojson) in:
   mkdir -p data/gps_traces/yushan
   # See docs/GPS_TRACES.md for details
   ```

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for a detailed getting started guide.

### Start the Server

```bash
uvicorn app.main:app --reload
```

### Enrich with GPS Traces (Optional)

To use real hiker GPS tracks for better route popularity scoring:

```bash
# Place GPS trace files in data/gps_traces/{area_id}/
python scripts/enrich_with_gps_traces.py
```

See [GPS_TRACES.md](docs/GPS_TRACES.md) for complete documentation.

The API will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Basic Usage

1. **Check health**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **List available areas**:
   ```bash
   curl http://localhost:8000/api/v1/areas
   ```

3. **Plan a route**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/routes/plan \
     -H "Content-Type: application/json" \
     -d '{
       "area_id": "test_region",
       "start_lat": 23.45,
       "start_lon": 120.95,
       "loop_route": true,
       "max_distance": 15,
       "hiker_fitness": "moderate"
     }'
   ```

4. **Export to GPX**:
   ```bash
   curl http://localhost:8000/api/v1/routes/{route_id}/export?format=gpx \
     --output route.gpx
   ```

## API Endpoints

### Health & Info
- `GET /health` - Health check
- `GET /` - API information

### Areas
- `GET /api/v1/areas` - List available hiking areas
- `GET /api/v1/areas/{area_id}` - Get area details

### Routes
- `POST /api/v1/routes/plan` - Plan a hiking route
- `GET /api/v1/routes/{route_id}` - Get route by ID
- `GET /api/v1/routes/{route_id}/export` - Export route (GPX/GeoJSON)

See [API.md](docs/API.md) for detailed API documentation.

## Key Algorithms

### Enhanced Naismith's Rule

Time estimation formula:
```
base_time = distance_km / base_speed
ascent_time = elevation_gain_m / 600
descent_bonus = min(elevation_loss_m / 300 / 6, base_time * 0.25)

total_time = (base_time + ascent_time - descent_bonus)
           * difficulty_factor
           * pack_penalty

if total_time > 4 hours:
    total_time *= 1.1  # Add rest breaks
```

### Routing Cost Function

```
cost = w_dist * (distance_km)
     + w_elev * (elevation_gain / 100)
     + w_diff * (difficulty_multiplier - 1.0)
```

### Multi-Day Splitting

1. Calculate total route time
2. Divide by target hours per day → number of days
3. Find optimal split points near huts/campsites (±1 hour of ideal)
4. Validate each day is 4–10 hours

See [ALGORITHMS.md](docs/ALGORITHMS.md) for detailed algorithm documentation.

## Project Structure

```
Project_Hermes/
├── app/
│   ├── main.py                   # FastAPI application
│   ├── config.py                 # Configuration
│   ├── exceptions.py             # Custom exceptions
│   ├── api/                      # API layer
│   │   ├── routes/               # Route handlers
│   │   └── dependencies.py       # Dependency injection
│   ├── models/                   # Data models
│   │   ├── domain.py            # Core domain models
│   │   ├── requests.py          # API request models
│   │   └── responses.py         # API response models
│   ├── services/                 # Business logic
│   │   ├── graph_service.py
│   │   ├── routing_service.py
│   │   ├── planning_service.py
│   │   ├── estimation_service.py
│   │   ├── recommendation_service.py
│   │   └── export_service.py
│   ├── core/                     # Core algorithms
│   │   ├── osm_processor.py
│   │   ├── elevation_processor.py
│   │   ├── cost_functions.py
│   │   └── time_estimators.py
│   └── utils/                    # Utilities
├── data/                         # Data storage
│   ├── osm/                     # OSM cache
│   ├── elevation/               # Elevation cache
│   ├── graphs/                  # Serialized graphs
│   └── areas.json               # Area metadata
├── tests/                        # Test suite
├── scripts/                      # Utility scripts
├── docs/                         # Documentation
└── requirements.txt              # Dependencies
```

## Development

### Running Tests

```bash
pytest tests/ -v --cov=app
```

### Adding New Hiking Areas

1. Edit `data/areas.json` with new area metadata
2. Add area points/routes data (or GPS traces in `data/gps_traces/{area_id}/`)
3. The graph will be built automatically on first route request (`bbox` is optional)

Example:
```json
{
  "area_id": "alps_chamonix",
  "name": "Chamonix - Mont Blanc",
  "description": "Classic alpine trails around Mont Blanc",
  "country": "France",
  "elevation_range": [1000, 4800]
}
```

### Pre-processing Graphs

For production, pre-build graphs using:
```bash
python scripts/download_osm_data.py --area test_region
python scripts/preprocess_graphs.py --area test_region
```

## Configuration

Key configuration options in `.env`:

```env
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Routing
DEFAULT_FITNESS_LEVEL=moderate
DEFAULT_HOURS_PER_DAY=7
MAX_ROUTE_DISTANCE_KM=100

# Cache
ENABLE_GRAPH_CACHE=true
CACHE_EXPIRY_HOURS=24
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- OpenStreetMap contributors for trail data
- SRTM for elevation data
- FastAPI for the excellent web framework
- NetworkX for graph algorithms

## Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/yourusername/project-hermes/issues)
- Documentation: See `docs/` directory

## Roadmap

- [ ] Weather integration
- [ ] ML-based time estimation
- [ ] Social features (share routes)
- [ ] Mobile app integration
- [ ] Real-time tracking
- [ ] Scenic route optimization
- [ ] Multi-country support
- [ ] Offline mode

---

**Project Hermes** - Making mountain adventures safer and more enjoyable through intelligent planning.
