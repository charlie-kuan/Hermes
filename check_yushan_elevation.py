"""檢查玉山路線的爬升和下降數據"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.graph_service import GraphService
from app.services.routing_service import RoutingService
from app.core.elevation_processor import ElevationProcessor
from loguru import logger

# 配置日誌
logger.remove()
logger.add(sys.stderr, level="INFO")

def check_yushan_route():
    """檢查玉山主峰路線的爬升和下降"""
    
    print("=" * 80)
    print("檢查玉山路線高度數據")
    print("=" * 80)
    
    # 初始化服務
    graph_service = GraphService()
    routing_service = RoutingService(graph_service)
    
    # 載入玉山地區的圖
    area_name = "yushan"
    print(f"\n正在載入 {area_name} 地區圖資...")
    graph = graph_service.get_or_build_graph(area_name)
    
    print(f"圖資節點數: {graph.number_of_nodes()}")
    print(f"圖資邊數: {graph.number_of_edges()}")
    
    # 檢查路線
    routes_to_check = [
        {
            "name": "玉山主峰二日",
            "start": "yushan_tataka_trailhead",
            "end": "yushan_tataka_trailhead",
            "via": ["yushan_paiyun_hut", "yushan_main_peak", "yushan_paiyun_hut"],
            "expected_ascent": 1400,  # 根據公開資料
            "expected_descent": 1400,
        }
    ]
    
    for route_info in routes_to_check:
        print(f"\n{'='*80}")
        print(f"路線: {route_info['name']}")
        print(f"{'='*80}")
        
        try:
            route = routing_service.plan_route(
                graph=graph,
                start_node_id=route_info["start"],
                end_node_id=route_info["end"],
                via_nodes=route_info["via"]
            )
            
            print(f"\n路線資訊:")
            print(f"  總距離: {route.total_distance/1000:.2f} km")
            print(f"  計算的總爬升: {route.total_elevation_gain:.0f} m")
            print(f"  計算的總下降: {route.total_elevation_loss:.0f} m")
            print(f"  預計時間: {route.estimated_time:.2f} 小時")
            
            print(f"\n預期數據 (根據公開資料):")
            print(f"  預期總爬升: {route_info['expected_ascent']} m")
            print(f"  預期總下降: {route_info['expected_descent']} m")
            
            print(f"\n差異分析:")
            ascent_diff = route.total_elevation_gain - route_info['expected_ascent']
            descent_diff = route.total_elevation_loss - route_info['expected_descent']
            ascent_percent = (ascent_diff / route_info['expected_ascent']) * 100
            descent_percent = (descent_diff / route_info['expected_descent']) * 100
            
            print(f"  爬升差異: {ascent_diff:+.0f} m ({ascent_percent:+.1f}%)")
            print(f"  下降差異: {descent_diff:+.0f} m ({descent_percent:+.1f}%)")
            
            if abs(ascent_percent) > 20 or abs(descent_percent) > 20:
                print(f"  ⚠️  警告: 差異超過20%，需要檢查!")
            
            # 顯示詳細的段落資訊
            print(f"\n詳細段落資訊:")
            print(f"{'段落':<30} {'距離(km)':<10} {'爬升(m)':<10} {'下降(m)':<10}")
            print("-" * 60)
            
            for i, segment in enumerate(route.segments):
                start = segment.start_node.name or segment.start_node.node_id
                end = segment.end_node.name or segment.end_node.node_id
                seg_name = f"{start[:12]} → {end[:12]}"
                print(f"{seg_name:<30} {segment.distance/1000:>9.2f} {segment.elevation_gain:>9.0f} {segment.elevation_loss:>9.0f}")
            
            print("-" * 60)
            print(f"{'總計':<30} {route.total_distance/1000:>9.2f} {route.total_elevation_gain:>9.0f} {route.total_elevation_loss:>9.0f}")
            
            # 檢查關鍵點位的高度
            print(f"\n關鍵點位高度:")
            key_points = [
                "yushan_tataka_trailhead",
                "yushan_paiyun_hut", 
                "yushan_main_peak"
            ]
            
            for point_id in key_points:
                if graph.has_node(point_id):
                    node = graph.nodes[point_id]['data']
                    print(f"  {node.name}: {node.elevation:.0f} m")
            
        except Exception as e:
            print(f"錯誤: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    check_yushan_route()
