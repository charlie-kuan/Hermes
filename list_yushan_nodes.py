"""列出玉山圖中的所有節點"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.graph_service import GraphService
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")

def list_yushan_nodes():
    graph_service = GraphService()
    area_name = "yushan"
    
    print(f"載入 {area_name} 地區圖資...")
    graph = graph_service.get_or_build_graph(area_name)
    
    print(f"\n圖資統計:")
    print(f"  節點數: {graph.number_of_nodes()}")
    print(f"  邊數: {graph.number_of_edges()}")
    
    # 列出所有重要節點
    print(f"\n重要節點 (peaks, huts, trailheads):")
    print(f"{'節點ID':<50} {'名稱':<30} {'類型':<15} {'高度(m)':<10}")
    print("-" * 105)
    
    important_nodes = []
    for node_id, node_data in graph.nodes(data=True):
        node = node_data['data']
        if node.node_type.value in ['peak', 'hut', 'trailhead', 'viewpoint']:
            important_nodes.append((node_id, node))
    
    # 按類型排序
    important_nodes.sort(key=lambda x: (x[1].node_type.value, x[1].name or x[0]))
    
    for node_id, node in important_nodes:
        name = node.name or "(無名稱)"
        print(f"{node_id:<50} {name:<30} {node.node_type.value:<15} {node.elevation:>9.0f}")
    
    # 檢查 CSV 中定義的節點
    print(f"\n\n檢查 CSV 定義的節點:")
    csv_nodes = [
        "yushan_tataka_trailhead",
        "yushan_paiyun_hut",
        "yushan_main_peak",
        "yushan_front_peak",
        "yushan_east_peak",
        "yushan_north_peak",
        "yushan_west_peak"
    ]
    
    for node_id in csv_nodes:
        exists = graph.has_node(node_id)
        status = "✓ 存在" if exists else "✗ 不存在"
        print(f"  {node_id:<30} {status}")
        
        if exists:
            node = graph.nodes[node_id]['data']
            print(f"    → 名稱: {node.name}, 高度: {node.elevation}m")

if __name__ == "__main__":
    list_yushan_nodes()
