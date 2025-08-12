#!/usr/bin/env python3
"""
example_usage.py - Example scripts showing how to use YouTube Playlist Finder programmatically
"""

import os
import sys
from datetime import datetime
from typing import List

# Import the core module
from youtube_playlist_core import (
    PlaylistFinder,
    SearchStrategy,
    VideoInfo,
    PlaylistInfo,
    QuotaExceededException
)


def example_basic_search():
    """Basic example: Find playlists containing a single video."""
    print("=" * 50)
    print("Example 1: Basic Search")
    print("=" * 50)
    
    # Initialize the finder with your API key
    api_key = "YOUR_API_KEY_HERE"  # Replace with your actual API key
    finder = PlaylistFinder(api_key)
    
    # Video to search for (can be ID or URL)
    video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    
    try:
        # Search for playlists
        print(f"Searching for playlists containing video: {video_id}")
        playlists = finder.find_playlists(
            video_id=video_id,
            strategies=[SearchStrategy.EXACT_TITLE, SearchStrategy.CHANNEL_PLAYLISTS],
            max_playlists=50
        )
        
        # Display results
        print(f"\nFound {len(playlists)} playlists:")
        for i, playlist in enumerate(playlists[:10], 1):  # Show first 10
            print(f"\n{i}. {playlist.title}")
            print(f"   Channel: {playlist.channel_title}")
            print(f"   Videos: {playlist.item_count}")
            print(f"   URL: {playlist.url}")
        
        if len(playlists) > 10:
            print(f"\n... and {len(playlists) - 10} more playlists")
        
        # Export results
        video_info = finder.api.get_video_info(video_id)
        filename = finder.export_results(video_info, playlists, format="json")
        print(f"\nResults saved to: {filename}")
        
    except QuotaExceededException:
        print("ERROR: YouTube API quota exceeded. Try again tomorrow.")
    except Exception as e:
        print(f"ERROR: {e}")


def example_advanced_search():
    """Advanced example: Search with multiple strategies and progress tracking."""
    print("\n" + "=" * 50)
    print("Example 2: Advanced Search with Progress")
    print("=" * 50)
    
    api_key = "YOUR_API_KEY_HERE"
    finder = PlaylistFinder(api_key)
    
    # Define progress callback
    def progress_callback(message: str, percent: int = None):
        if percent is not None:
            print(f"[{percent:3d}%] {message}")
        else:
            print(f"      {message}")
    
    finder.set_progress_callback(progress_callback)
    
    # Video URL (automatically extracts ID)
    video_url = "https://www.youtube.com/watch?v=9bZkp7q19f0"
    video_id = video_url.split("v=")[1] if "v=" in video_url else video_url
    
    # Use all search strategies
    all_strategies = [
        SearchStrategy.EXACT_TITLE,
        SearchStrategy.CHANNEL_PLAYLISTS,
        SearchStrategy.TITLE_AND_CHANNEL,
        SearchStrategy.KEYWORD_SEARCH,
        SearchStrategy.POPULAR_PLAYLISTS
    ]
    
    try:
        playlists = finder.find_playlists(
            video_id=video_id,
            strategies=all_strategies,
            max_playlists=100,
            parallel=True  # Use parallel processing
        )
        
        print(f"\n✅ Search complete! Found {len(playlists)} playlists")
        
        # Get statistics
        stats = finder.get_statistics()
        print("\nSearch Statistics:")
        print(f"  API calls made: {stats['api_quota_used']}")
        print(f"  Playlists checked: {stats['playlists_checked']}")
        print(f"  Cache hit rate: {stats['cache_stats']['hit_rate']}")
        
    except Exception as e:
        print(f"ERROR: {e}")


def example_batch_search():
    """Batch example: Search for multiple videos."""
    print("\n" + "=" * 50)
    print("Example 3: Batch Search for Multiple Videos")
    print("=" * 50)
    
    api_key = "YOUR_API_KEY_HERE"
    finder = PlaylistFinder(api_key)
    
    # List of videos to search
    videos = [
        "dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
        "9bZkp7q19f0",  # PSY - Gangnam Style
        "kJQP7kiw5Fk",  # Luis Fonsi - Despacito
    ]
    
    all_results = {}
    
    for video_id in videos:
        print(f"\nSearching for video: {video_id}")
        try:
            # Get video info
            video_info = finder.api.get_video_info(video_id)
            if video_info:
                print(f"  Title: {video_info.title}")
                
                # Search with limited strategies for batch processing
                playlists = finder.find_playlists(
                    video_id=video_id,
                    strategies=[SearchStrategy.EXACT_TITLE],
                    max_playlists=30  # Limit for batch processing
                )
                
                all_results[video_id] = {
                    "video_info": video_info,
                    "playlists": playlists
                }
                
                print(f"  Found: {len(playlists)} playlists")
            else:
                print(f"  ERROR: Video not found")
                
        except Exception as e:
            print(f"  ERROR: {e}")
            all_results[video_id] = {"error": str(e)}
    
    # Summary
    print("\n" + "-" * 30)
    print("Batch Search Summary:")
    total_playlists = sum(
        len(r.get("playlists", [])) 
        for r in all_results.values() 
        if "playlists" in r
    )
    print(f"  Videos processed: {len(videos)}")
    print(f"  Total playlists found: {total_playlists}")
    
    # Export batch results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"batch_results_{timestamp}.json"
    
    import json
    export_data = {}
    for video_id, data in all_results.items():
        if "error" in data:
            export_data[video_id] = {"error": data["error"]}
        else:
            export_data[video_id] = {
                "video_title": data["video_info"].title,
                "playlists_found": len(data["playlists"]),
                "playlists": [
                    {
                        "title": p.title,
                        "channel": p.channel_title,
                        "url": p.url
                    }
                    for p in data["playlists"][:5]  # Export first 5 only
                ]
            }
    
    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"\nBatch results saved to: {filename}")


def example_custom_strategy():
    """Custom example: Search with specific channel focus."""
    print("\n" + "=" * 50)
    print("Example 4: Custom Strategy - Channel Focus")
    print("=" * 50)
    
    api_key = "YOUR_API_KEY_HERE"
    finder = PlaylistFinder(api_key)
    
    video_id = "your_video_id_here"
    
    try:
        # First, get video info to find the channel
        video_info = finder.api.get_video_info(video_id)
        if not video_info:
            print("Video not found")
            return
        
        print(f"Video: {video_info.title}")
        print(f"Channel: {video_info.channel_title}")
        
        # Search only in the video's channel playlists
        print(f"\nSearching playlists from {video_info.channel_title}...")
        
        channel_playlists = finder.api.get_channel_playlists(
            video_info.channel_id,
            max_results=100
        )
        
        print(f"Found {len(channel_playlists)} playlists in channel")
        
        # Check each playlist for the video
        found_in = []
        for i, playlist_id in enumerate(channel_playlists, 1):
            print(f"Checking playlist {i}/{len(channel_playlists)}...", end="\r")
            
            if finder.api.check_video_in_playlist(playlist_id, video_id):
                playlist_info = finder.api.get_playlist_info(playlist_id)
                if playlist_info:
                    found_in.append(playlist_info)
        
        print(f"\n\nVideo found in {len(found_in)} channel playlists:")
        for playlist in found_in:
            print(f"  - {playlist.title}")
        
    except Exception as e:
        print(f"ERROR: {e}")


def example_export_formats():
    """Export example: Different export formats."""
    print("\n" + "=" * 50)
    print("Example 5: Export in Different Formats")
    print("=" * 50)
    
    api_key = "YOUR_API_KEY_HERE"
    finder = PlaylistFinder(api_key)
    
    video_id = "dQw4w9WgXcQ"
    
    try:
        # Quick search
        print("Performing quick search...")
        playlists = finder.find_playlists(
            video_id=video_id,
            strategies=[SearchStrategy.EXACT_TITLE],
            max_playlists=20
        )
        
        if not playlists:
            print("No playlists found")
            return
        
        print(f"Found {len(playlists)} playlists")
        
        # Get video info for export
        video_info = finder.api.get_video_info(video_id)
        
        # Export in different formats
        formats = ["json", "html", "csv"]
        
        for format_type in formats:
            filename = finder.export_results(
                video_info,
                playlists,
                format=format_type
            )
            print(f"  Exported to {format_type.upper()}: {filename}")
        
        print("\n✅ All formats exported successfully")
        
    except Exception as e:
        print(f"ERROR: {e}")


def example_with_caching():
    """Caching example: Demonstrate cache benefits."""
    print("\n" + "=" * 50)
    print("Example 6: Cache Demonstration")
    print("=" * 50)
    
    api_key = "YOUR_API_KEY_HERE"
    finder = PlaylistFinder(api_key)
    
    video_id = "dQw4w9WgXcQ"
    
    import time
    
    # First search (will populate cache)
    print("First search (populating cache)...")
    start_time = time.time()
    
    playlists1 = finder.find_playlists(
        video_id=video_id,
        strategies=[SearchStrategy.EXACT_TITLE],
        max_playlists=30
    )
    
    first_time = time.time() - start_time
    print(f"  Time taken: {first_time:.2f} seconds")
    print(f"  Found: {len(playlists1)} playlists")
    
    # Second search (should use cache)
    print("\nSecond search (using cache)...")
    start_time = time.time()
    
    playlists2 = finder.find_playlists(
        video_id=video_id,
        strategies=[SearchStrategy.EXACT_TITLE],
        max_playlists=30
    )
    
    second_time = time.time() - start_time
    print(f"  Time taken: {second_time:.2f} seconds")
    print(f"  Found: {len(playlists2)} playlists")
    
    # Show cache statistics
    stats = finder.get_statistics()
    print("\nCache Statistics:")
    print(f"  Hit rate: {stats['cache_stats']['hit_rate']}")
    print(f"  Cache entries: {stats['cache_stats']['total_entries']}")
    print(f"  Speed improvement: {first_time/second_time:.1f}x faster")


def main():
    """Run all examples."""
    print("YouTube Playlist Finder - Usage Examples")
    print("=" * 50)
    
    # Check for API key
    if "YOUR_API_KEY_HERE" in open(__file__).read():
        print("\n⚠️  WARNING: Please update the API key in this file first!")
        print("   Edit this file and replace 'YOUR_API_KEY_HERE' with your actual API key")
        print("   Get one at: https://console.cloud.google.com/apis/credentials")
        return
    
    examples = [
        ("Basic Search", example_basic_search),
        ("Advanced Search", example_advanced_search),
        ("Batch Search", example_batch_search),
        ("Custom Strategy", example_custom_strategy),
        ("Export Formats", example_export_formats),
        ("Caching Demo", example_with_caching)
    ]
    
    print("\nAvailable Examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print("  0. Run all examples")
    
    choice = input("\nSelect an example to run (0-6): ").strip()
    
    if choice == "0":
        for name, func in examples:
            input(f"\nPress Enter to run: {name}")
            func()
    elif choice.isdigit() and 1 <= int(choice) <= len(examples):
        examples[int(choice) - 1][1]()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
