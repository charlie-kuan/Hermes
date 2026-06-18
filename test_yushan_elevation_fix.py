"""測試玉山高度計算修復"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.graph_service import GraphService
from app.services.routing_service import RoutingService
from app.utils.area_loader import load_area_full
from app.utils.cache import graph_cache
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")

def test_yushan_with_custom_nodes():
    """測試整合CSV節點後的玉山路線計算"""
    
    print("=" * 80)
    print("測試玉山高度計算修復")
    print("=" * 80)
    
    # 清除舊緩存
    print("\n1. 清除舊的圖緩存...")
    graph_cache.clear_cache("yushan")
    
    # 載入區域數據（包含CSV定義的點位）
    print("\n2. 載入玉山區域數據...")
    area_data = load_area_full("yushan")
    
    if not area_data:
        print("❌ 無法載入玉山區域數據")
        return
    
    print(f"   載入了 {len(area_data.get('points', []))} 個自定義點位")
    for point in area_data.get('points', []):
        print(f"   - {point['name']} ({point['type']}): {point['elevation']}m")
    
    # 初始化服務並構建圖（會自動整合自定義節點）
    print("\n3. 構建圖並整合自定義節點...")
    graph_service = GraphService()
    routing_service = RoutingService(graph_service)
    
    graph = graph_service.get_or_build_graph("yushan", area_data=area_data)
    
    print(f"   圖資統計:")
    print(f"   - 總節點數: {graph.number_of_nodes()}")
    print(f"   - 總邊數: {graph.number_of_edges()}")
    
    # 檢查自定義節點是否存在
    print("\n4. 驗證自定義節點...")
    custom_nodes = [
        "yushan_tataka_trailhead",
        "yushan_paiyun_hut",
        "yushan_main_peak"
    ]
    
    all_exist = True
    for node_id in custom_nodes:
        exists = graph.has_node(node_id)
        status = "✓" if exists else "✗"
        print(f"   {status} {node_id}")
        if exists:
            node = graph.nodes[node_id]['data']
            print(f"      名稱: {node.name}, 高度: {node.elevation}m")
        else:
            all_exist = False
    
    if not all_exist:
        print("\n❌ 部分自定義節點不存在，無法進行路線規劃")
        print("   提示: 可能需要重新預處理圖資")
        return
    
    # 規劃路線
    print("\n5. 規劃玉山主峰路線...")
    try:
        route = routing_service.plan_route(
            graph=graph,
            start_node_id="yushan_tataka_trailhead",
            end_node_id="yushan_tataka_trailhead",
            via_nodes=["yushan_paiyun_hut", "yushan_main_peak", "yushan_paiyun_hut"]
        )
        
        print(f"\n   路線規劃成功！")
        print(f"   - 總距離: {route.total_distance:.2f} km")
        print(f"   - 計算的總爬升: {route.total_elevation_gain:.0f} m")
        print(f"   - 計算的總下降: {route.total_elevation_loss:.0f} m")
        print(f"   - 預計時間: {route.estimated_time:.2f} 小時")
        print(f"   - 段落數: {len(route.segments)}")
        
        # 檢查geometry
        print(f"\n   段落詳情:")
        total_geometry_points = 0
        for i, segment in enumerate(route.segments, 1):
            geom_points = len(segment.geometry)
            total_geometry_points += geom_points
            has_elevation = any(len(p) >= 3 for p in segment.geometry) if segment.geometry else False
            print(f"   段落 {i}: {segment.start_node.name} → {segment.end_node.name}")
            print(f"           距離: {segment.distance:.2f}km, 爬升: {segment.elevation_gain:.0f}m, 下降: {segment.elevation_loss:.0f}m")
            print(f"           幾何點數: {geom_points}, 包含高度: {'✓' if has_elevation else '✗'}")
        
        print(f"\n   總幾何點數: {total_geometry_points}")
        
        # 與預期比較
        print(f"\n6. 與公開資料比較:")
        print("=" * 80)
        expected_ascent = 1400
        expected_descent = 1400
        csv_ascent = 1342  # 從CSV直接計算的結果
        
        ascent_diff = route.total_elevation_gain - expected_ascent
        descent_diff = route.total_elevation_loss - expected_descent
        ascent_percent = (ascent_diff / expected_ascent) * 100
        descent_percent = (descent_diff / expected_descent) * 100
        
        print(f"   {'系統計算結果:':<30} 爬升 {route.total_elevation_gain:.0f}m, 下降 {route.total_elevation_loss:.0f}m")
        print(f"   {'CSV節點計算:':<30} 爬升 {csv_ascent:.0f}m, 下降 {csv_ascent:.0f}m")
        print(f"   {'公開資料 (目標):':<30} 爬升 {expected_ascent:.0f}m, 下降 {expected_descent:.0f}m")
        print(f"   {'與目標差異:':<30} 爬升 {ascent_diff:+.0f}m ({ascent_percent:+.1f}%), 下降 {descent_diff:+.0f}m ({descent_percent:+.1f}%)")
        
        if abs(ascent_percent) <= 15 and abs(descent_percent) <= 15:
            print(f"\n   ✓ 結果在合理範圍內（±15%）")
        elif abs(ascent_percent) <= 25 and abs(descent_percent) <= 25:
            print(f"\n   ⚠️  結果偏差較大但可接受（15-25%）")
        else:
            print(f"\n   ❌ 結果偏差過大（>25%），需要進一步優化")
        
        print("\n" + "=" * 80)
        print("測試完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 路線規劃失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_yushan_with_custom_nodes()
