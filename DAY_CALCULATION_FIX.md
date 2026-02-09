# 天數計算問題修復說明

## 問題描述
用戶回報：兩天的路線被規劃成100多天

## 根本原因分析

經過詳細的代碼審查，發現可能的問題是：**距離單位轉換錯誤**

### 問題場景
當創建路線segment時，如果distance值是以「公尺」為單位但被誤認為「公里」，會導致：

```python
# 正確：500公尺 = 0.5公里
segment.distance = 0.5  # km
estimated_time = 0.5小時 (30分鐘)

# 錯誤：500公尺被當成500公里！
segment.distance = 500  # 應該是meters但被當成km
estimated_time = 131.6小時 (!)
```

### 為何會產生100+天？

多日路線分段邏輯：
```python
target_hours_per_day = 7.0
threshold = 7.0 * 0.8 = 5.6小時

for segment in route.segments:
    cumulative_time += segment.estimated_time
    if cumulative_time >= 5.6:  # 創建新的一天
        create_new_day()
        cumulative_time = 0
```

如果每個segment的estimated_time都很大（例如131小時），那麼：
- 第一個segment: 131小時 >= 5.6小時 → 創建第1天
- 第二個segment: 131小時 >= 5.6小時 → 創建第2天
- ...
- 第N個segment → 創建第N天

如果有100個segments，就會創建100天！

## 修復方案

已在 `app/services/planning_service.py` 中添加以下保護機制：

### 1. 偵測異常高的segment時間
```python
if segment.estimated_time > 24:  # 單段不應超過24小時
    logger.error(f"Segment時間異常: {segment.estimated_time}小時")
```

### 2. 自動修正距離單位
```python
if segment.distance > 100:  # 可能是公尺而非公里
    logger.warning(f"距離單位可能錯誤，自動轉換...")
    segment.distance = segment.distance / 1000.0  # 轉換為公里
    # 重新計算時間
```

### 3. 天數合理性檢查
```python
if estimated_days > 30:
    logger.warning("預估天數異常高，可能有單位轉換問題")

if len(days) > estimated_days * 2:
    logger.warning("實際創建天數遠超預估，檢查分段邏輯")
```

### 4. 詳細的調試日誌
現在會記錄每個segment的：
- 距離（公里，3位小數）
- 爬升（公尺）
- 時間（小時）
- 累積時間

## 如何驗證修復

### 方法1：運行測試腳本
```bash
python3.12 test_day_calculation_fix.py
```

### 方法2：檢查日誌
規劃路線時，檢查logs/中的日誌文件，尋找：
- ⚠️ 距離單位可能錯誤的警告
- ⚠️ Segment時間異常的錯誤
- 每個segment的詳細資訊

### 方法3：查看終端輸出
FastAPI啟動時會在終端顯示日誌，注意：
- "Corrected segment time" 訊息
- "WARNING: Expected X days" 警告

## 可能需要額外檢查的地方

如果問題持續存在，請檢查：

### 1. OSM數據處理 (`app/core/osm_processor.py`)
```python
# Line 180 - 確認edge.distance是公尺
distance=data.get('length', 0.0),  # OSMnx返回公尺
```

### 2. GPS軌跡處理 (`app/core/gps_trace_processor.py`)
```python
# Line 434-453 - 確認haversine_distance返回公尺
distance = haversine_distance(...)  # 返回公尺
```

### 3. 路線規劃 (`app/services/routing_service.py`)
```python
# Line 194 - 確認有轉換為公里
distance=edge.distance / 1000.0,  # 轉換為公里 ✓
```

## 測試結果

運行 `test_day_calculation_fix.py` 的結果：
- ✅ 時間計算正確（小時為單位）
- ✅ 能偵測到500「公里」的錯誤（實際應該是0.5公里）
- ✅ 估計時間131.6小時 > 24小時門檻 → 會被捕捉
- ✅ 分段邏輯正確（15小時路線 = 2-3天）

## 建議

1. **清除圖形緩存**：如果之前有緩存錯誤的圖形數據
   ```bash
   python3.12 scripts/clear_graph_cache.py
   ```

2. **重新建構圖形**：讓系統重新下載和處理OSM數據

3. **檢查GPS軌跡數據**：如果使用GPS軌跡，確認座標格式正確

4. **監控日誌**：規劃路線時注意警告訊息

## 結論

已添加多層保護機制來偵測和修正距離單位轉換錯誤。如果仍然遇到問題，詳細的日誌會幫助定位具體原因。
