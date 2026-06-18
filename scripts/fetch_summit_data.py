#!/usr/bin/env python3
"""
Script to fetch mountain summit data from OpenStreetMap.
Queries both man_made=summit_board and natural=peak tags.
Saves the data to CSV format for future use.
"""

import requests
import csv
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Taiwan bounding box (approximately)
# Format: [south, west, north, east]
TAIWAN_BBOX = [21.5, 119.5, 25.5, 122.5]


def build_overpass_query(bbox: List[float], query_type: str = "both") -> str:
    """
    Build Overpass QL query to fetch summit data.
    
    Args:
        bbox: Bounding box [south, west, north, east]
        query_type: Type of query - "summit_board", "peak", or "both"
    
    Returns:
        Overpass QL query string
    """
    south, west, north, east = bbox
    
    queries = []
    
    if query_type in ["summit_board", "both"]:
        # Query for summit boards
        queries.append(f"""
    node["man_made"="summit_board"]({south},{west},{north},{east});
        """)
    
    
    if query_type in ["peak", "both"]:
        # Query for peaks
        queries.append(f"""
    node["natural"="peak"]({south},{west},{north},{east});
        """)
    
    query = f"""
[out:json][timeout:180];
(
    {"".join(queries)}
);
out body;
>;
out skel qt;
"""
    
    return query


def fetch_osm_data(bbox: List[float], query_type: str = "both") -> Dict[str, Any]:
    """
    Fetch summit data from OpenStreetMap using Overpass API.
    
    Args:
        bbox: Bounding box coordinates
        query_type: Type of query to execute
    
    Returns:
        JSON response from Overpass API
    """
    query = build_overpass_query(bbox, query_type)
    
    print(f"Querying Overpass API...")
    print(f"Query type: {query_type}")
    print(f"Bounding box: {bbox}")
    
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=200
        )
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Retrieved {len(data.get('elements', []))} elements")
        
        return data
        
    except requests.exceptions.Timeout:
        print("✗ Request timed out. Try reducing the bounding box size.")
        raise
    except requests.exceptions.RequestException as e:
        print(f"✗ Error fetching data: {e}")
        raise


def parse_summit_data(osm_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse OSM data and extract summit information.
    
    Args:
        osm_data: Raw OSM data from Overpass API
    
    Returns:
        List of summit dictionaries
    """
    summits = []
    
    for element in osm_data.get('elements', []):
        if element.get('type') != 'node':
            continue
        
        tags = element.get('tags', {})
        
        # Determine summit type
        summit_type = None
        if tags.get('man_made') == 'summit_board':
            summit_type = 'summit_board'
        elif tags.get('natural') == 'peak':
            summit_type = 'peak'
        else:
            continue
        
        summit = {
            'id': element.get('id'),
            'type': summit_type,
            'name': tags.get('name', ''),
            'name_zh': tags.get('name:zh', ''),
            'name_en': tags.get('name:en', ''),
            'latitude': element.get('lat'),
            'longitude': element.get('lon'),
            'elevation': tags.get('ele', ''),
            'prominence': tags.get('prominence', ''),
            'wikipedia': tags.get('wikipedia', ''),
            'wikidata': tags.get('wikidata', ''),
            'description': tags.get('description', ''),
        }
        
        summits.append(summit)
    
    return summits


def save_to_csv(summits: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Save summit data to CSV file.
    
    Args:
        summits: List of summit data dictionaries
        output_path: Output CSV file path
    """
    if not summits:
        print("No summits to save.")
        return
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Define CSV columns
    fieldnames = [
        'id', 'type', 'name', 'name_zh', 'name_en',
        'latitude', 'longitude', 'elevation', 'prominence',
        'wikipedia', 'wikidata', 'description'
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summits)
    
    print(f"✓ Saved {len(summits)} summits to {output_path}")


def save_to_json(summits: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Save summit data to JSON file (backup format).
    
    Args:
        summits: List of summit data dictionaries
        output_path: Output JSON file path
    """
    if not summits:
        return
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(summits, jsonfile, ensure_ascii=False, indent=2)
    
    print(f"✓ Saved JSON backup to {output_path}")


def print_summary(summits: List[Dict[str, Any]]) -> None:
    """Print summary statistics of fetched summits."""
    if not summits:
        print("\nNo summits found.")
        return
    
    summit_boards = [s for s in summits if s['type'] == 'summit_board']
    peaks = [s for s in summits if s['type'] == 'peak']
    
    named_summits = [s for s in summits if s['name']]
    with_elevation = [s for s in summits if s['elevation']]
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total summits: {len(summits)}")
    print(f"  - Summit boards (登頂牌): {len(summit_boards)}")
    print(f"  - Peaks (山峰): {len(peaks)}")
    print(f"Summits with names: {len(named_summits)}")
    print(f"Summits with elevation data: {len(with_elevation)}")
    
    # Show some examples
    if summits:
        print("\nFirst 5 summits:")
        for i, summit in enumerate(summits[:5], 1):
            name = summit['name'] or summit['name_zh'] or '(unnamed)'
            ele = summit['elevation'] or 'N/A'
            print(f"  {i}. {name} - {summit['latitude']:.4f}, {summit['longitude']:.4f} (ele: {ele}m)")
    print("="*60)


def main():
    """Main execution function."""
    print("="*60)
    print("Mountain Summit Data Fetcher")
    print("="*60)
    print()
    
    # Configuration
    bbox = TAIWAN_BBOX
    query_type = "summit_board"  # Options: "summit_board", "peak", "both"
    
    # Output paths
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_dir = Path(__file__).parent.parent / "data"
    csv_path = data_dir / f"summits_{timestamp}.csv"
    json_path = data_dir / f"summits_{timestamp}.json"
    
    # Also save a "latest" version without timestamp
    csv_latest = data_dir / "summits_latest.csv"
    json_latest = data_dir / "summits_latest.json"
    
    try:
        # Fetch data
        osm_data = fetch_osm_data(bbox, query_type)
        
        # Parse summits
        print("\nParsing summit data...")
        summits = parse_summit_data(osm_data)
        
        # Sort by name
        summits.sort(key=lambda x: (x['name'] or x['name_zh'] or ''))
        
        # Save to files
        print("\nSaving data...")
        save_to_csv(summits, csv_path)
        save_to_csv(summits, csv_latest)
        save_to_json(summits, json_path)
        save_to_json(summits, json_latest)
        
        # Print summary
        print_summary(summits)
        
        print("\n✓ Done!")
        print(f"\nFiles saved:")
        print(f"  - {csv_path}")
        print(f"  - {csv_latest}")
        print(f"  - {json_path}")
        print(f"  - {json_latest}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    main()
