"""直接從CSV數據計算玉山路線的爬升和下降"""

import csv
from pathlib import Path

def calculate_route_elevation():
    """從CSV計算玉山路線的實際爬升和下降"""
    
    # 讀取points.csv
    points_file = Path("/Users/charlie/Desktop/Project/Project_Hermes/data/areas/yushan/points.csv")
    
    points = {}
    with open(points_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            points[row['id']] = {
                'name': row['name'],
                'elevation': float(row['elevation']),
                'type': row['type']
            }
    
    print("=" * 80)
    print("玉山路線高度數據驗證")
    print("=" * 80)
    
    # 顯示關鍵點位高度
    print("\n關鍵點位高度:")
    key_points = [
        "yushan_tataka_trailhead",
        "yushan_paiyun_hut",
        "yushan_main_peak"
    ]
    
    for point_id in key_points:
        if point_id in points:
            p = points[point_id]
            print(f"  {p['name']}: {p['elevation']:.0f} m")
    
    # 讀取routes.csv
    routes_file = Path("/Users/charlie/Desktop/Project/Project_Hermes/data/areas/yushan/routes.csv")
    
    print("\n\n玉山主峰路線分析:")
    print("=" * 80)
    
    with open(routes_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['route_id'] == 'yushan_main_2day':
                route_name = row['name']
                point_sequence = row['point_sequence'].split('>')
                
                print(f"\n路線: {route_name}")
                print(f"點位序列: {' → '.join(point_sequence)}")
                print(f"\n詳細高度變化:")
                print(f"{'段落':<50} {'海拔(m)':<12} {'高度差(m)':<12}")
                print("-" * 74)
                
                total_ascent = 0
                total_descent = 0
                prev_elevation = None
                prev_name = None
                
                for point_id in point_sequence:
                    if point_id in points:
                        p = points[point_id]
                        elevation = p['elevation']
                        
                        if prev_elevation is not None:
                            diff = elevation - prev_elevation
                            diff_str = f"{diff:+.0f}"
                            
                            if diff > 0:
                                total_ascent += diff
                            else:
                                total_descent += abs(diff)
                            
                            segment = f"{prev_name} → {p['name']}"
                            print(f"{segment:<50} {elevation:>11.0f} {diff_str:>11}")
                        else:
                            print(f"{p['name']:<50} {elevation:>11.0f} {'起點':>11}")
                        
                        prev_elevation = elevation
                        prev_name = p['name']
                
                print("-" * 74)
                print(f"\n{'總爬升:':<50} {total_ascent:>11.0f} m")
                print(f"{'總下降:':<50} {total_descent:>11.0f} m")
                
                # 與公開資料比較
                print(f"\n\n與公開資料比較:")
                print("-" * 74)
                expected_ascent = 1400
                expected_descent = 1400
                
                ascent_diff = total_ascent - expected_ascent
                descent_diff = total_descent - expected_descent
                ascent_percent = (ascent_diff / expected_ascent) * 100
                descent_percent = (descent_diff / expected_descent) * 100
                
                print(f"{'CSV計算結果:':<30} 爬升 {total_ascent:.0f}m, 下降 {total_descent:.0f}m")
                print(f"{'公開資料 (預期):':<30} 爬升 {expected_ascent:.0f}m, 下降 {expected_descent:.0f}m")
                print(f"{'差異:':<30} 爬升 {ascent_diff:+.0f}m ({ascent_percent:+.1f}%), 下降 {descent_diff:+.0f}m ({descent_percent:+.1f}%)")
                
                if abs(ascent_percent) > 20 or abs(descent_percent) > 20:
                    print(f"\n⚠️  警告: 差異超過20%!")
                    print(f"\n可能的原因:")
                    print(f"  1. CSV中的高度數據不準確")
                    print(f"  2. 公開資料包含了路線中的起伏（上上下下），而單純計算節點差異會低估")
                    print(f"  3. 實際路線可能經過更多未記錄的高度變化點")
                else:
                    print(f"\n✓ 數據在合理範圍內")
                
                break

if __name__ == "__main__":
    calculate_route_elevation()
