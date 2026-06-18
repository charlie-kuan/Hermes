"""測試新的高度計算改進 - 使用CSV節點直接計算"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.elevation_processor import ElevationProcessor
from app.utils.area_loader import load_area_points

def test_elevation_improvement():
    """測試高度計算改進"""
    
    print("=" * 80)
    print("測試玉山路線高度計算改進")
    print("=" * 80)
    
    # 載入玉山的自定義節點
    points = load_area_points("yushan")
    print(f"\n載入了 {len(points)} 個自定義節點")
    
    # 創建elevation processor
    elev_proc = ElevationProcessor()
    
    # 測試路線：塔塔加 -> 排雲 -> 主峰 -> 排雲 -> 塔塔加
    route_sequence = [
        "yushan_tataka_trailhead",
        "yushan_paiyun_hut", 
        "yushan_main_peak",
        "yushan_paiyun_hut",
        "yushan_tataka_trailhead"
    ]
    
    # 將ID映射到點資料
    points_dict = {p['id']: p for p in points}
    
    print("\n路線節點:")
    for point_id in route_sequence:
        if point_id in points_dict:
            p = points_dict[point_id]
            print(f"  {p['name']}: {p['elevation']:.0f}m at ({p['lat']:.5f}, {p['lon']:.5f})")
    
    # 模擬沿路徑插值並查詢DEM高度
    print("\n\n測試場景1: 簡單節點高度差異 (當前方法)")
    print("-" * 80)
    
    elevations_simple = []
    for point_id in route_sequence:
        if point_id in points_dict:
            p = points_dict[point_id]
            elevations_simple.append(p['elevation'])
    
    gain_simple, loss_simple = elev_proc.calculate_elevation_gain_loss(elevations_simple)
    print(f"總爬升: {gain_simple:.0f}m")
    print(f"總下降: {loss_simple:.0f}m")
    print(f"(這是CSV數據的理論值，未考慮路徑起伏)")
    
    # 測試帶插值的版本
    print("\n\n測試場景2: 沿路徑採樣DEM高度 (改進方法)")
    print("-" * 80)
    print("模擬每個段落插值10個採樣點...")
    
    from app.utils.geo_utils import haversine_distance
    
    elevations_detailed = []
    total_samples = 0
    
    for i in range(len(route_sequence) - 1):
        start_id = route_sequence[i]
        end_id = route_sequence[i + 1]
        
        if start_id in points_dict and end_id in points_dict:
            p1 = points_dict[start_id]
            p2 = points_dict[end_id]
            
            # 計算段落距離
            distance = haversine_distance(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
            
            # 插值10個點
            num_samples = 10
            for j in range(num_samples + 1):
                ratio = j / num_samples
                lat = p1['lat'] + ratio * (p2['lat'] - p1['lat'])
                lon = p1['lon'] + ratio * (p2['lon'] - p1['lon'])
                
                # 從DEM查詢實際高度
                elev = elev_proc.get_elevation(lat, lon)
                if elev is not None:
                    elevations_detailed.append(elev)
                    total_samples += 1
                else:
                    # 線性插值作為備用
                    elev = p1['elevation'] + ratio * (p2['elevation'] - p1['elevation'])
                    elevations_detailed.append(elev)
                    total_samples += 1
            
            print(f"  {p1['name'][:20]:20} → {p2['name'][:20]:20}: {distance/1000:.2f}km, {num_samples+1} 採樣點")
    
    if len(elevations_detailed) > 0:
        gain_detailed, loss_detailed = elev_proc.calculate_elevation_gain_loss(elevations_detailed)
        print(f"\n總共採樣了 {total_samples} 個高度點")
        print(f"總爬升: {gain_detailed:.0f}m")
        print(f"總下降: {loss_detailed:.0f}m")
        
        # 比較
        print("\n\n比較結果:")
        print("-" * 80)
        print(f"{'方法':<30} {'總爬升':<15} {'總下降':<15}")
        print(f"{'CSV節點(簡單)':<30} {gain_simple:>14.0f}m {loss_simple:>14.0f}m")
        print(f"{'沿路採樣(詳細)':<30} {gain_detailed:>14.0f}m {loss_detailed:>14.0f}m")
        print(f"{'公開資料(預期)':<30} {'1400m':>14} {'1400m':>14}")
        
        diff_gain = gain_detailed - gain_simple
        diff_loss = loss_detailed - loss_simple
        print(f"\n詳細方法vs簡單方法:")
        print(f"  爬升差異: {diff_gain:+.0f}m ({diff_gain/gain_simple*100:+.1f}%)")
        print(f"  下降差異: {diff_loss:+.0f}m ({diff_loss/loss_simple*100:+.1f}%)")
    else:
        print("無法獲取高度數據")
    
    print("\n\n結論:")
    print("-" * 80)
    print("1. CSV節點的簡單計算：1342m (只考慮關鍵點位)")
    print("2. 沿路採樣會捕捉更多起伏，應該更接近實際的1400m")
    print("3. 實際偏差取決於DEM數據品質和路徑的實際起伏")

if __name__ == "__main__":
    test_elevation_improvement()
