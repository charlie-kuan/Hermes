#!/usr/bin/env python3
"""
清除圖資緩存並重建

在模型結構改變後使用，確保所有緩存的圖資都有最新的欄位。
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.services.graph_service import GraphService
from app.api.routes.areas import load_areas


def main():
    """清除所有緩存的圖資。"""
    
    logger.info("=" * 60)
    logger.info("清除圖資緩存")
    logger.info("=" * 60)
    
    graph_service = GraphService()
    
    # 清除所有緩存
    logger.info("\n1. 清除所有圖資緩存...")
    graph_service.clear_cache()
    logger.success("   ✓ 緩存已清除")
    
    # 可選：重新建立所有區域的圖資
    logger.info("\n2. 是否要重新建立所有區域的圖資？")
    logger.info("   這會下載 OSM 資料並重建圖資（可能需要幾分鐘）")
    
    areas = load_areas()
    logger.info(f"   找到 {len(areas)} 個區域: {[a['area_id'] for a in areas]}")
    
    rebuild = input("\n   重新建立？ (y/N): ").lower().strip() == 'y'
    
    if rebuild:
        logger.info("\n3. 開始重建圖資...")
        for area in areas:
            area_id = area['area_id']
            
            logger.info(f"\n   處理區域: {area_id}")
            try:
                graph = graph_service.get_or_build_graph(area_id, area_data=area)
                stats = graph_service.get_graph_stats(graph)
                logger.success(f"   ✓ {area_id}: {stats['total_nodes']} 節點, "
                             f"{stats['total_edges']} 邊, "
                             f"{stats['total_distance_km']:.1f} km")
            except Exception as e:
                logger.error(f"   ✗ {area_id}: {e}")
        
        logger.success("\n所有圖資已重建！")
    else:
        logger.info("\n跳過重建。圖資將在首次使用時自動建立。")
    
    logger.info("\n" + "=" * 60)
    logger.info("完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
