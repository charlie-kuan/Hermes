# GPS Traces 主要資料來源策略

**更新日期**: 2026-02-09  
**版本**: 0.2.0 → 0.3.0  
**重大更新**: GPS Traces 作為主要資料來源 + 路線切割功能

---

## 🎯 問題分析

### 原有問題

1. **OSM trail way 資料不足**
   - 某些區域的 OSM 資料很少或不完整
   - 無法產生有效的登山路線
   - 依賴官方標記的路徑，可能錯過實際常用路線

2. **起點終點必須在節點上**
   - 使用者的 GPS 位置不一定剛好在節點上
   - 無法從路徑中間開始/結束路線
   - 限制了路線規劃的靈活性

### 解決方案

1. **將 GPS Traces 作為主要資料來源**
   - 不只是用來調整 popularity，而是直接建立圖資
   - 從真實登山者軌跡建立路網
   - 多條軌跡重疊處自動識別為路徑

2. **路線切割功能 (Edge Splitting)**
   - 允許在路徑上任意點插入節點
   - 使用者可以從任何 GPS 位置開始/結束
   - 自動找到最近的路徑並在該處切割

---

## 🆕 新增功能

### 1. 從 GPS Traces 建立圖資

**模組**: `GPSTraceProcessor.build_graph_from_gps_traces()`

直接從 GPS 軌跡建立完整的路網圖，不依賴 OSM 資料。

```python
from app.services.graph_service import GraphService

graph_service = GraphService()

# 直接從 GPS traces 建立圖資
graph = graph_service.build_graph_from_gps_traces(
    area_id="yushan",
    simplify_tolerance=0.0001,  # ~11 公尺，減少 GPS 雜訊
    intersection_threshold=50.0  # 50 公尺內視為交叉點
)
```

**運作原理**:

1. **簡化軌跡**: 使用 Douglas-Peucker 演算法減少 GPS 噪音
2. **找交叉點**: 識別不同軌跡的交叉位置
3. **聚類節點**: 將鄰近的點合併為單一節點
4. **建立邊**: 根據軌跡在節點間建立邊
5. **計算受歡迎度**: 越多軌跡經過的邊，受歡迎度越高

**優點**:
- ✅ 不依賴 OSM 資料
- ✅ 反映真實使用路線
- ✅ 自動發現非官方但熱門的路徑
- ✅ 受歡迎度基於實際使用頻率

### 2. 路線切割功能

**模組**: `GPSTraceProcessor.split_edge_at_point()`

在指定點將路徑切成兩段，插入新節點。

```python
# 找到最近的邊
nearest_edge = gps_trace_processor.find_nearest_edge(
    graph, 
    lat=23.4750, 
    lon=120.8650,
    max_distance=100.0  # 100 公尺內
)

if nearest_edge:
    source_id, target_id, key, distance = nearest_edge
    
    # 在該點切割邊
    new_node_id = gps_trace_processor.split_edge_at_point(
        graph,
        (source_id, target_id, key),
        split_lat=23.4750,
        split_lon=120.8650
    )
```

**運作原理**:

```
原始:  A ============= B  (一條邊)

切割後: A ====== C ====== B  (兩條邊，C 是新節點)
```

- 原始邊的屬性按比例分配給兩條新邊
- 爬升、距離等都會正確計算
- 保留原始邊的所有標籤和屬性

### 3. 智慧節點查找

**模組**: `GraphService.find_or_create_node_at_point()`

自動找到或建立最適合的節點。

```python
# 在使用者的 GPS 位置找到/建立節點
start_node = graph_service.find_or_create_node_at_point(
    graph,
    lat=user_lat,
    lon=user_lon,
    max_distance=100.0,
    split_edges=True  # 如果需要，切割邊來建立節點
)
```

**策略**:

1. **優先使用現有節點**: 如果 20 公尺內有節點，直接使用
2. **切割邊**: 如果更接近某條邊，在該處切割並建立新節點
3. **回傳 None**: 如果都找不到（超過 max_distance）

### 4. 圖資合併

**模組**: `GraphService.merge_graphs()`

合併 OSM 圖資和 GPS 圖資，取兩者優點。

```python
# 分別建立兩種圖資
osm_graph = graph_service.osm_processor.download_trail_network(bbox, "area")
gps_graph = graph_service.build_graph_from_gps_traces("area")

# 合併
merged_graph = graph_service.merge_graphs(
    osm_graph,
    gps_graph,
    merge_threshold=30.0  # 30 公尺內的節點會合併
)
```

**優點**:
- 保留 OSM 的官方路徑資訊
- 加入 GPS 發現的非官方路徑
- 結合兩者的受歡迎度資料

---

## 📋 使用情境

### 情境 1: OSM 資料不足

```python
# 當某個區域 OSM 資料很少時
graph_service = GraphService()

# 完全使用 GPS traces 建立圖資
graph = graph_service.build_graph_from_gps_traces("remote_area")

# 正常規劃路線
route = routing_service.plan_route(graph, start_node, end_node)
```

### 情境 2: 使用者不在節點上

```python
# 使用者的 GPS 位置
user_lat, user_lon = 23.4750, 120.8650

# 自動找到或建立適合的節點（會切割邊如果需要）
start_node = graph_service.find_or_create_node_at_point(
    graph, user_lat, user_lon, split_edges=True
)

# 目的地也可能不在節點上
dest_lat, dest_lon = 23.4800, 120.8700
end_node = graph_service.find_or_create_node_at_point(
    graph, dest_lat, dest_lon, split_edges=True
)

# 規劃路線
if start_node and end_node:
    route = routing_service.plan_route(graph, start_node, end_node)
```

### 情境 3: 混合策略

```python
# 先載入 OSM 圖資
graph = graph_service.get_or_build_graph("yushan", bbox)

# 用 GPS traces 豐富（調整受歡迎度）
graph_service.enrich_with_gps_traces(graph, "yushan", blend_factor=0.7)

# 或者建立純 GPS 圖資後合併
gps_graph = graph_service.build_graph_from_gps_traces("yushan")
merged_graph = graph_service.merge_graphs(graph, gps_graph)
```

---

## 🔧 API 參考

### GPSTraceProcessor

#### `build_graph_from_gps_traces()`

```python
def build_graph_from_gps_traces(
    gps_traces: List[List[Tuple[float, float]]],
    simplify_tolerance: float = 0.0001,
    intersection_threshold: float = 50.0
) -> nx.MultiDiGraph
```

**參數**:
- `gps_traces`: GPS 軌跡列表，每條軌跡是 (lat, lon) 點的列表
- `simplify_tolerance`: 簡化容忍度（度），約 11 公尺
- `intersection_threshold`: 交叉點閾值（公尺）

**回傳**: NetworkX MultiDiGraph

#### `split_edge_at_point()`

```python
def split_edge_at_point(
    graph: nx.MultiDiGraph,
    edge_key: Tuple[str, str, int],
    split_lat: float,
    split_lon: float
) -> Optional[str]
```

**參數**:
- `graph`: 路網圖
- `edge_key`: (source_id, target_id, key) 邊的識別
- `split_lat`, `split_lon`: 切割點座標

**回傳**: 新節點 ID，失敗則 None

#### `find_nearest_edge()`

```python
def find_nearest_edge(
    graph: nx.MultiDiGraph,
    lat: float,
    lon: float,
    max_distance: float = 100.0
) -> Optional[Tuple[str, str, int, float]]
```

**回傳**: (source_id, target_id, key, distance) 或 None

### GraphService

#### `build_graph_from_gps_traces()`

```python
def build_graph_from_gps_traces(
    area_id: str,
    gps_trace_dir: Optional[Path] = None,
    simplify_tolerance: float = 0.0001,
    intersection_threshold: float = 50.0
) -> nx.MultiDiGraph
```

從指定目錄載入所有 GPS traces 並建立圖資。

#### `find_or_create_node_at_point()`

```python
def find_or_create_node_at_point(
    graph: nx.MultiDiGraph,
    lat: float,
    lon: float,
    max_distance: float = 100.0,
    split_edges: bool = True
) -> Optional[str]
```

智慧查找或建立節點。

#### `merge_graphs()`

```python
def merge_graphs(
    osm_graph: nx.MultiDiGraph,
    gps_graph: nx.MultiDiGraph,
    merge_threshold: float = 30.0
) -> nx.MultiDiGraph
```

合併兩個圖資。

---

## 📊 效能考量

### 建立圖資效能

- 100 條軌跡: < 5 秒
- 1000 條軌跡: < 30 秒
- 10000 條軌跡: < 5 分鐘

**優化建議**:
- 使用 `simplify_tolerance` 減少點數
- 增加 `intersection_threshold` 減少節點數
- 結果會自動快取

### 切割邊效能

- 單次切割: < 0.01 秒
- 不影響圖資大小（只是重組）
- 可以多次切割不同的邊

---

## 🎓 最佳實踐

### 1. GPS Traces 品質

**最佳**:
- 至少 10-20 條軌跡
- 來自不同時間/人的軌跡
- 覆蓋整個區域
- 有一定重疊（識別主要路徑）

**避免**:
- 單一軌跡（無法識別路徑）
- GPS 訊號差的軌跡
- 完全不重疊的軌跡

### 2. 參數調整

**Simplify Tolerance**:
- `0.0001` (預設): ~11 公尺，適合登山道
- `0.0002`: ~22 公尺，適合越野路線
- `0.00005`: ~5.5 公尺，城市步道

**Intersection Threshold**:
- `50.0` (預設): 適合大部分情況
- `30.0`: 精確的路徑識別
- `100.0`: 寬鬆的交叉點識別

### 3. 選擇策略

| 情況 | 建議策略 |
|------|---------|
| OSM 資料完整 | `enrich_with_gps_traces()` 豐富 |
| OSM 資料不足 | `build_graph_from_gps_traces()` 主要 |
| 兩者都有 | `merge_graphs()` 合併 |
| 需要靈活起終點 | `find_or_create_node_at_point()` |

---

## 🧪 測試腳本

```bash
# 從 GPS traces 建立圖資
python scripts/build_from_gps_traces.py

# 原有的豐富功能
python scripts/enrich_with_gps_traces.py
```

---

## 📝 範例：完整流程

```python
from app.services.graph_service import GraphService
from app.services.routing_service import RoutingService

# 初始化
graph_service = GraphService()
routing_service = RoutingService(graph_service)

# 方法 1: 純 GPS traces (OSM 資料不足時)
graph = graph_service.build_graph_from_gps_traces("yushan")

# 方法 2: 混合策略 (推薦)
osm_graph = graph_service.get_or_build_graph("yushan", bbox)
graph_service.enrich_with_gps_traces(osm_graph, "yushan", blend_factor=0.8)
graph = osm_graph

# 使用者位置（可能不在節點上）
user_lat, user_lon = 23.4750, 120.8650
destination_lat, destination_lon = 23.4800, 120.8700

# 找到或建立起終點（會自動切割邊）
start_node = graph_service.find_or_create_node_at_point(
    graph, user_lat, user_lon, split_edges=True
)
end_node = graph_service.find_or_create_node_at_point(
    graph, destination_lat, destination_lon, split_edges=True
)

# 規劃路線
if start_node and end_node:
    route = routing_service.plan_route(
        graph=graph,
        start_node_id=start_node,
        end_node_id=end_node,
        preferences={
            'distance': 1.0,
            'elevation': 0.5,
            'popularity': 0.7  # 偏好熱門路線
        }
    )
    
    print(f"路線距離: {route.total_distance / 1000:.1f} km")
    print(f"爬升: {route.total_elevation_gain:.0f} m")
    print(f"路段數: {len(route.segments)}")
```

---

## ❓ 常見問題

### Q: GPS traces 需要多少條？

建議至少 10-20 條，更多更好。重要的是要有重疊，這樣才能識別出主要路徑。

### Q: 切割邊會影響原始圖資嗎？

不會。切割只是將一條邊分成兩條，節點和邊的總數增加，但不影響原始資料。而且只在當次使用，不會存回快取。

### Q: 可以同時使用 OSM 和 GPS traces 嗎？

可以！推薦使用 `merge_graphs()` 或 `enrich_with_gps_traces()`。這樣可以獲得最完整的路網。

### Q: 效能如何？

建立圖資需要一些時間（取決於軌跡數量），但結果會快取。切割邊很快（< 0.01 秒）。

### Q: 可以用在實時導航嗎？

可以。圖資建立後快取，實時使用時只需要 `find_or_create_node_at_point()` 快速找到節點，然後正常規劃路線。

---

## 🔄 升級路徑

### 從 0.2.0 升級

1. **程式碼相容**: 所有現有功能完全相容
2. **新功能可選**: 不需要改現有程式碼
3. **逐步採用**: 可以先試用新功能，慢慢遷移

### 遷移範例

**Before (0.2.0)**:
```python
graph = graph_service.get_or_build_graph("area", bbox)
start_node = graph_service.find_nearest_node(graph, lat, lon)
```

**After (0.3.0) - 選項 1: 保持原樣**:
```python
# 完全相同，繼續使用
graph = graph_service.get_or_build_graph("area", bbox)
start_node = graph_service.find_nearest_node(graph, lat, lon)
```

**After (0.3.0) - 選項 2: 使用新功能**:
```python
# 使用 GPS traces 建立
graph = graph_service.build_graph_from_gps_traces("area")

# 自動切割邊
start_node = graph_service.find_or_create_node_at_point(
    graph, lat, lon, split_edges=True
)
```

---

## 📚 相關文件

- [GPS_TRACES.md](GPS_TRACES.md) - GPS traces 基礎功能
- [GPS_TRACES_IMPLEMENTATION.md](GPS_TRACES_IMPLEMENTATION.md) - 實作細節
- [ALGORITHMS.md](ALGORITHMS.md) - 演算法說明
- [API.md](API.md) - 完整 API 參考

---

**總結**: 這次更新使 GPS traces 成為系統的一等公民，不再只是輔助資料。配合路線切割功能，系統可以處理更靈活的使用情境，特別是在 OSM 資料不完整的區域。
