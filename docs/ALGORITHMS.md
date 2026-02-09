# Algorithms Documentation

## Overview

Project Hermes uses several key algorithms for route planning and time estimation. This document explains the mathematical models and implementation details.

---

## 1. Time Estimation - Enhanced Naismith's Rule

### Original Naismith's Rule (1892)

Basic formula: **5 km/h + 1 hour per 600m elevation gain**

### Our Enhancements

We extend Naismith's Rule with modern adjustments:

```
base_time = distance_km / base_speed
ascent_time = elevation_gain_m / 600
descent_bonus = min(elevation_loss_m / 300 / 6, base_time * 0.25)

total_time = (base_time + ascent_time - descent_bonus)
           × difficulty_factor
           × pack_penalty

if total_time > 4:
    total_time *= 1.1  # Add 10% rest time
```

### Components

#### 1. Base Speed (by fitness level)

- **Beginner**: 4.0 km/h
- **Moderate**: 5.0 km/h
- **Expert**: 6.0 km/h

#### 2. Ascent Time

Standard Naismith: 1 hour per 600m gain

#### 3. Descent Adjustment

- Subtract time for descent: 10 min per 300m
- Capped at 25% of horizontal time
- Accounts for faster descent but prevents unrealistic speeds

#### 4. Difficulty Multiplier

- **Easy (T1)**: 1.0× (no penalty)
- **Moderate (T2)**: 1.15× (+15%)
- **Difficult (T3)**: 1.35× (+35%)
- **Expert (T4+)**: 1.6× (+60%)

Based on SAC (Swiss Alpine Club) scale.

#### 5. Pack Weight Penalty

```
penalty = 1.0 + max(0, pack_weight_kg - 10) × 0.02
```

- Base weight: 10 kg (no penalty)
- 2% penalty per kg over 10 kg
- Example: 20 kg pack = 1.2× multiplier (+20%)

#### 6. Rest Breaks

For hikes longer than 4 hours, add 10% time for breaks.

### Example Calculation

**Route**: 10 km, 800m gain, 200m loss, moderate difficulty, moderate fitness, 12 kg pack

```
base_time = 10 / 5.0 = 2.0 hours
ascent_time = 800 / 600 = 1.33 hours
descent_bonus = min(200/300/6, 2.0 × 0.25) = min(0.11, 0.5) = 0.11 hours

difficulty_factor = 1.15
pack_penalty = 1.0 + (12 - 10) × 0.02 = 1.04

total_time = (2.0 + 1.33 - 0.11) × 1.15 × 1.04 = 3.85 hours
```

Since < 4 hours, no rest break multiplier.

**Result**: ~3.85 hours (~3h 51min)

### Scenario Estimates

- **Optimistic**: normal × 0.8 (-20%)
- **Normal**: as calculated
- **Conservative**: normal × 1.2 (+20%)

---

## 2. Routing Cost Function

### Overview

Uses weighted sum of distance, elevation, difficulty, and popularity to find optimal paths.

### Formula

```
cost = w_dist × (distance_km)
     + w_elev × (elevation_gain / 100)
     + w_diff × (difficulty_multiplier - 1.0)
     - w_pop × (popularity_bonus)
```

### Default Weights

- `w_dist = 1.0`: Distance component
- `w_elev = 0.5`: Elevation component (per 100m)
- `w_diff = 0.3`: Difficulty component
- `w_pop = 0.0`: Popularity component (0 = ignore, higher = prefer popular trails)

### Difficulty Costs

- **Easy**: 1.0 (base)
- **Moderate**: 1.3
- **Difficult**: 1.7
- **Expert**: 2.5

### Trail Popularity Score

Calculated from OpenStreetMap attributes (range: 0.5-2.0):

**Positive Indicators:**
- Has trail name: +0.3
- Has route reference (ref tag): +0.4
- Excellent/good visibility: +0.3
- Better surface quality: +0.2
- Well-maintained tracktype: +0.1
- Easy SAC scale: +0.1

**Negative Indicators:**
- Poor visibility (bad/horrible/no): -0.2
- Technical alpine routes: -0.1

**Popular trails** typically have:
- Named routes (e.g., "玉山主峰線", "GR20")
- Official route references
- Better visibility and surface quality
- More likely to have trail markers and maintenance

### Optimization Profiles

#### Speed (Fastest Route)
```
w_dist = 1.0
w_elev = 0.3
w_diff = 0.2
w_pop = 0.0
```
Minimizes distance, tolerates elevation and difficulty.

#### Scenic (Beautiful Route)
```
w_dist = 0.7
w_elev = 1.0
w_diff = 0.1
w_pop = 0.0
```
Prefers elevation gain (peaks, ridges), less concerned with difficulty.

#### Easy (Beginner-Friendly)
```
w_dist = 0.8
w_elev = 0.5
w_diff = 1.5
w_pop = 0.0
```
Heavily penalizes difficult terrain.

#### Popular (Well-Traveled Routes)
```
w_dist = 0.8
w_elev = 0.4
w_diff = 0.8
w_pop = 1.5
```
Strongly prefers popular, well-maintained trails that are commonly used by hikers.
Ideal for first-time visitors or those who prefer established routes with better infrastructure.

### Pathfinding Algorithm

Uses **A\* search** with:
- **Weight function**: cost function above
- **Heuristic**: Straight-line distance × distance weight
- **Graph**: NetworkX MultiDiGraph

---

## 3. Multi-Day Splitting

### Algorithm

```python
1. Estimate total route time
2. Calculate estimated_days = total_time / target_hours_per_day
3. For each segment:
   - Add to current day
   - If cumulative_time >= target_hours × 0.8:
     - Find overnight stop within ±1 hour
     - Create day plan
     - Reset for next day
4. Return list of day plans
```

### Overnight Stop Selection

**Scoring system**:

```
Base score:
- Hut: 100 (if prefer_huts), else 50
- Campsite: 50 (if prefer_huts), else 100

Distance score: 50 - (distance_m / 40)
  (closer is better, within 2km search radius)

Amenities bonus:
- Water available: +20

Final score = base_score + distance_score + amenities_bonus
```

Select highest scoring option.

### Validation

Each day must be:
- **Minimum**: 3 hours
- **Maximum**: 12 hours
- **Target**: 7 hours (configurable)

---

## 4. Elevation Processing

### SRTM Integration

- **Resolution**: 30m (1 arc-second)
- **Coverage**: Global (60°N to 56°S)
- **Source**: NASA Shuttle Radar Topography Mission

### Elevation Gain/Loss Calculation

```python
elevations = [e1, e2, e3, ..., en]

gain = sum(e[i+1] - e[i] for all i where e[i+1] > e[i])
loss = sum(e[i] - e[i+1] for all i where e[i+1] < e[i])
```

### Smoothing

Apply moving average to reduce GPS/SRTM noise:

```python
window_size = 3  # Must be odd
for i in range(len(elevations)):
    window = elevations[i-1:i+2]
    smoothed[i] = mean(window)
```

---

## 5. Equipment Recommendations

### Rule-Based System

```
Essential (always):
- Backpack, water, first aid, map, headlamp, sun protection

If multi_day:
  + Sleeping bag, tent, cooking system, water purification

If elevation > 3000m OR season == winter:
  + Warm layers, rain gear, insulated jacket

If difficulty >= DIFFICULT:
  + Trekking poles, gaiters, technical gear

If no huts available:
  + Full camping setup
```

### Category Priority

1. **Essential**: Cannot hike safely without
2. **Overnight**: Required for multi-day
3. **Clothing**: Weather-appropriate
4. **Technical**: For difficult terrain
5. **Optional**: Comfort and convenience

---

## 6. Calorie Calculation

### Formula

```
base_calories = body_weight_kg × distance_km × 5 kcal/kg/km

elevation_calories = (elevation_gain_m / 100) × 10 kcal per 100m

pack_multiplier = 1.0 + (pack_weight_kg / 5) × 0.05

total = (base_calories + elevation_calories) × pack_multiplier
```

### Daily Requirements

- **Base**: 2200-2500 kcal/day
- **Light hiking**: 2500-3000 kcal/day
- **Moderate hiking**: 3000-3500 kcal/day
- **Strenuous hiking**: 3500-4500 kcal/day

Adjusted for difficulty and effort.

### Water Calculation

```
base_water = 2.5 L/day

if estimated_time > 6h: base_water = 3.0 L
if estimated_time > 8h: base_water = 3.5 L
if elevation_gain > 1000m: base_water += 0.5 L
```

---

## 7. Graph Construction

### OSM Data Extraction

**Node filters**:
- `natural=peak`: Mountain peaks
- `tourism=alpine_hut`: Alpine huts
- `amenity=shelter`: Shelters
- `highway=trailhead`: Trailheads

**Way filters**:
- `highway=path|track|footway`: Hiking trails
- `sac_scale=*`: SAC difficulty rating
- `access!=private`: Public trails

### Graph Structure

- **Nodes**: Node objects with lat/lon/elevation/amenities
- **Edges**: Edge objects with distance/gain/loss/difficulty
- **Type**: NetworkX MultiDiGraph (allows multiple edges between nodes)

### Elevation Enrichment

1. Check OSM `ele` tag
2. If missing, query SRTM for (lat, lon)
3. Calculate edge gain/loss from node elevations
4. Smooth profiles to reduce noise

---

## Performance Characteristics

### Time Complexity

- **Graph building**: O(n + m) where n=nodes, m=edges
- **A\* routing**: O(E × log V) where E=edges, V=nodes
- **Multi-day split**: O(k) where k=number of segments
- **Elevation lookup**: O(1) per point (with caching)

### Space Complexity

- **Graph storage**: ~1KB per node, ~500B per edge
- **Typical region** (100 km²): ~10k nodes, ~20k edges = ~20MB
- **Cache**: Pickle serialization, ~15-30MB per area

### Optimizations

- Graph caching (disk + memory)
- Batch elevation queries
- A\* heuristic for faster pathfinding
- NetworkX optimized data structures

---

## References

1. Naismith, W. W. (1892). "Excursions. Cruach Ardran, Stobinian, and Ben More"
2. SAC Scale: Swiss Alpine Club hiking scale
3. SRTM: NASA Shuttle Radar Topography Mission
4. Tobler's Hiking Function for speed adjustments
5. OpenStreetMap Hiking Tags: wiki.openstreetmap.org/wiki/Hiking

---

## Future Improvements

- Machine learning for personalized time estimates
- Weather integration (wind, precipitation effects)
- Trail condition updates (seasonal, maintenance)
- Social data (crowd-sourced times)
- Scenic route optimization (views, points of interest)
- Energy expenditure models (beyond calories)
