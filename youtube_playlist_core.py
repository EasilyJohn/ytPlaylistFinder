"""
youtube_playlist_core.py - Core module for YouTube Playlist Finder
Shared functionality for both CLI and GUI versions
"""

import os
import json
import time
import logging
import hashlib
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class SearchStrategy(Enum):
    """Different strategies for finding playlists."""
    EXACT_TITLE = "exact_title"
    TITLE_AND_CHANNEL = "title_channel"
    CHANNEL_PLAYLISTS = "channel_playlists"
    RELATED_VIDEOS = "related_videos"
    KEYWORD_SEARCH = "keyword_search"
    POPULAR_PLAYLISTS = "popular_playlists"


@dataclass
class VideoInfo:
    """Video information structure."""
    id: str
    title: str
    channel_id: str
    channel_title: str
    description: str
    duration: str
    view_count: int
    like_count: int
    published_at: str
    thumbnail_url: str
    tags: List[str]
    
    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.id}"


@dataclass
class PlaylistInfo:
    """Playlist information structure."""
    id: str
    title: str
    channel_id: str
    channel_title: str
    description: str
    item_count: int
    published_at: str
    thumbnail_url: str
    privacy_status: str = "public"
    
    @property
    def url(self) -> str:
        return f"https://www.youtube.com/playlist?list={self.id}"


class CacheManager:
    """Advanced caching system with expiration and compression."""
    
    def __init__(self, cache_dir: str = ".cache", expire_hours: int = 24):
        self.cache_dir = cache_dir
        self.expire_hours = expire_hours
        self.cache_file = os.path.join(cache_dir, "playlist_cache.json")
        self.cache = {}
        self.cache_stats = {"hits": 0, "misses": 0}
        self._lock = threading.Lock()
        
        os.makedirs(cache_dir, exist_ok=True)
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from disk with expiration check."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    # Clean expired entries
                    now = datetime.now()
                    self.cache = {
                        k: v for k, v in data.items()
                        if datetime.fromisoformat(v.get('timestamp', '2000-01-01')) 
                        > now - timedelta(hours=self.expire_hours)
                    }
            except Exception as e:
                logging.warning(f"Cache load error: {e}")
                self.cache = {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            with self._lock:
                with open(self.cache_file, 'w') as f:
                    json.dump(self.cache, f, indent=2)
        except Exception as e:
            logging.warning(f"Cache save error: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self._lock:
            if key in self.cache:
                self.cache_stats["hits"] += 1
                return self.cache[key].get('data')
            self.cache_stats["misses"] += 1
            return None
    
    def set(self, key: str, value: Any):
        """Set item in cache."""
        with self._lock:
            self.cache[key] = {
                'data': value,
                'timestamp': datetime.now().isoformat()
            }
            # Save periodically
            if len(self.cache) % 10 == 0:
                self._save_cache()
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total * 100) if total > 0 else 0
        return {
            **self.cache_stats,
            "total_entries": len(self.cache),
            "hit_rate": f"{hit_rate:.1f}%"
        }


class YouTubeAPI:
    """Enhanced YouTube API wrapper with retry logic and rate limiting."""
    
    def __init__(self, api_key: str, cache_manager: Optional[CacheManager] = None):
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.cache = cache_manager or CacheManager()
        self.rate_limiter = RateLimiter()
        self.quota_used = 0
        self.max_retries = 3
    
    def _make_request(self, func, *args, **kwargs):
        cache_key = hashlib.md5(f"{func.__name__}_{args}_{kwargs}".encode()).hexdigest()
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        self.rate_limiter.wait_if_needed()

        for attempt in range(self.max_retries):
            try:
                request = func(*args, **kwargs)   # build request
                result = request.execute()        # <-- execute it
                self.cache.set(cache_key, result)
                self.quota_used += 1
                return result
            except HttpError as e:
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    raise QuotaExceededException("YouTube API quota exceeded")
                elif e.resp.status == 429:
                    time.sleep(2 ** attempt)
                elif attempt == self.max_retries - 1:
                    raise
                else:
                    time.sleep(1)
        return None
    
    def get_video_info(self, video_id: str) -> Optional[VideoInfo]:
        """Get detailed video information."""
        try:
            response = self._make_request(
                self.youtube.videos().list,
                part="snippet,contentDetails,statistics",
                id=video_id
            )
            
            if not response or not response.get('items'):
                return None
            
            item = response['items'][0]
            snippet = item['snippet']
            stats = item.get('statistics', {})
            
            return VideoInfo(
                id=video_id,
                title=snippet.get('title', ''),
                channel_id=snippet.get('channelId', ''),
                channel_title=snippet.get('channelTitle', ''),
                description=snippet.get('description', ''),
                duration=item.get('contentDetails', {}).get('duration', ''),
                view_count=int(stats.get('viewCount', 0)),
                like_count=int(stats.get('likeCount', 0)),
                published_at=snippet.get('publishedAt', ''),
                thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                tags=snippet.get('tags', [])
            )
        except Exception as e:
            logging.error(f"Error getting video info: {e}")
            return None
    
    def get_playlist_info(self, playlist_id: str) -> Optional[PlaylistInfo]:
        """Get detailed playlist information."""
        try:
            response = self._make_request(
                self.youtube.playlists().list,
                part="snippet,contentDetails,status",
                id=playlist_id
            )
            
            if not response or not response.get('items'):
                return None
            
            item = response['items'][0]
            snippet = item['snippet']
            
            return PlaylistInfo(
                id=playlist_id,
                title=snippet.get('title', ''),
                channel_id=snippet.get('channelId', ''),
                channel_title=snippet.get('channelTitle', ''),
                description=snippet.get('description', ''),
                item_count=item.get('contentDetails', {}).get('itemCount', 0),
                published_at=snippet.get('publishedAt', ''),
                thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                privacy_status=item.get('status', {}).get('privacyStatus', 'public')
            )
        except Exception as e:
            logging.error(f"Error getting playlist info: {e}")
            return None
    
    def check_video_in_playlist(self, playlist_id: str, video_id: str) -> bool:
        """Check if a video exists in a playlist."""
        page_token = None
        
        while True:
            try:
                response = self._make_request(
                    self.youtube.playlistItems().list,
                    part="contentDetails",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=page_token
                )
                
                if not response:
                    break
                
                for item in response.get('items', []):
                    if item.get('contentDetails', {}).get('videoId') == video_id:
                        return True
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as e:
                logging.debug(f"Error checking playlist {playlist_id}: {e}")
                break
        
        return False
    
    def search_playlists(self, query: str, max_results: int = 50) -> List[str]:
        """Search for playlist IDs based on query."""
        playlist_ids = []
        page_token = None
        
        while len(playlist_ids) < max_results:
            try:
                response = self._make_request(
                    self.youtube.search().list,
                    part="id",
                    q=query,
                    type="playlist",
                    maxResults=min(50, max_results - len(playlist_ids)),
                    pageToken=page_token
                )
                
                if not response:
                    break
                
                for item in response.get('items', []):
                    if 'playlistId' in item.get('id', {}):
                        playlist_ids.append(item['id']['playlistId'])
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as e:
                logging.error(f"Search error: {e}")
                break
        
        return playlist_ids[:max_results]
    
    def get_channel_playlists(self, channel_id: str, max_results: int = 50) -> List[str]:
        """Get all playlists from a channel."""
        playlist_ids = []
        page_token = None
        
        while len(playlist_ids) < max_results:
            try:
                response = self._make_request(
                    self.youtube.playlists().list,
                    part="id",
                    channelId=channel_id,
                    maxResults=min(50, max_results - len(playlist_ids)),
                    pageToken=page_token
                )
                
                if not response:
                    break
                
                for item in response.get('items', []):
                    playlist_ids.append(item['id'])
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as e:
                logging.debug(f"Channel playlists error: {e}")
                break
        
        return playlist_ids[:max_results]


class RateLimiter:
    """Rate limiting to avoid API throttling."""
    
    def __init__(self, calls_per_second: float = 2.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
        self._lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if necessary to maintain rate limit."""
        with self._lock:
            now = time.time()
            time_since_last = now - self.last_call
            if time_since_last < self.min_interval:
                time.sleep(self.min_interval - time_since_last)
            self.last_call = time.time()


class QuotaExceededException(Exception):
    """Exception raised when API quota is exceeded."""
    pass


class PlaylistFinder:
    """Advanced playlist finder with multiple search strategies."""
    
    def __init__(self, api_key: str, cache_dir: str = ".cache"):
        self.cache_manager = CacheManager(cache_dir)
        self.api = YouTubeAPI(api_key, self.cache_manager)
        self.found_playlists = []
        self.checked_playlist_ids = set()
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """Set callback for progress updates."""
        self.progress_callback = callback
    
    def _update_progress(self, message: str, percent: int = None):
        """Update progress through callback."""
        if self.progress_callback:
            self.progress_callback(message, percent)
    
    def find_playlists(
        self,
        video_id: str,
        strategies: List[SearchStrategy] = None,
        max_playlists: int = 100,
        parallel: bool = True
    ) -> List[PlaylistInfo]:
        """
        Find playlists containing a video using multiple strategies.
        """
        # Get video info first
        video_info = self.api.get_video_info(video_id)
        if not video_info:
            raise ValueError(f"Video {video_id} not found")
        
        self._update_progress(f"Searching for playlists containing: {video_info.title}", 0)
        
        # Default strategies
        if not strategies:
            strategies = [
                SearchStrategy.EXACT_TITLE,
                SearchStrategy.CHANNEL_PLAYLISTS,
                SearchStrategy.TITLE_AND_CHANNEL,
                SearchStrategy.KEYWORD_SEARCH
            ]
        
        # Collect potential playlist IDs
        all_playlist_ids = set()
        
        for i, strategy in enumerate(strategies):
            self._update_progress(
                f"Strategy: {strategy.value}",
                int((i / len(strategies)) * 50)
            )
            playlist_ids = self._search_by_strategy(strategy, video_info, max_playlists)
            all_playlist_ids.update(playlist_ids)
            
            if len(all_playlist_ids) >= max_playlists:
                break
        
        # Check playlists for video
        all_playlist_ids = list(all_playlist_ids)[:max_playlists]
        self._update_progress(f"Checking {len(all_playlist_ids)} playlists...", 50)
        
        if parallel:
            found = self._check_playlists_parallel(all_playlist_ids, video_id)
        else:
            found = self._check_playlists_sequential(all_playlist_ids, video_id)
        
        self._update_progress("Search complete!", 100)
        self.cache_manager._save_cache()
        
        return found
    
    def _search_by_strategy(
        self,
        strategy: SearchStrategy,
        video_info: VideoInfo,
        max_results: int
    ) -> List[str]:
        """Execute a specific search strategy."""
        playlist_ids = []
        
        if strategy == SearchStrategy.EXACT_TITLE:
            playlist_ids = self.api.search_playlists(video_info.title, max_results)
            
        elif strategy == SearchStrategy.CHANNEL_PLAYLISTS:
            playlist_ids = self.api.get_channel_playlists(video_info.channel_id, max_results)
            
        elif strategy == SearchStrategy.TITLE_AND_CHANNEL:
            query = f"{video_info.title} {video_info.channel_title}"
            playlist_ids = self.api.search_playlists(query, max_results)
            
        elif strategy == SearchStrategy.KEYWORD_SEARCH:
            # Use video tags and keywords from description
            keywords = video_info.tags[:3] if video_info.tags else []
            if keywords:
                query = " ".join(keywords)
                playlist_ids = self.api.search_playlists(query, max_results)
        
        elif strategy == SearchStrategy.POPULAR_PLAYLISTS:
            # Search for popular compilation playlists
            queries = ["best of", "compilation", "mix", "playlist"]
            for query in queries:
                ids = self.api.search_playlists(
                    f"{query} {video_info.channel_title}",
                    max_results // len(queries)
                )
                playlist_ids.extend(ids)
        
        return playlist_ids
    
    def _check_playlists_sequential(
        self,
        playlist_ids: List[str],
        video_id: str
    ) -> List[PlaylistInfo]:
        """Check playlists sequentially."""
        found = []
        
        for i, playlist_id in enumerate(playlist_ids):
            if playlist_id in self.checked_playlist_ids:
                continue
                
            self._update_progress(
                f"Checking playlist {i+1}/{len(playlist_ids)}",
                50 + int((i / len(playlist_ids)) * 50)
            )
            
            if self.api.check_video_in_playlist(playlist_id, video_id):
                info = self.api.get_playlist_info(playlist_id)
                if info:
                    found.append(info)
                    logging.info(f"Found in: {info.title}")
            
            self.checked_playlist_ids.add(playlist_id)
        
        return found
    
    def _check_playlists_parallel(
        self,
        playlist_ids: List[str],
        video_id: str,
        max_workers: int = 10
    ) -> List[PlaylistInfo]:
        """Check playlists in parallel using thread pool."""
        found = []
        checked_count = 0
        
        def check_playlist(playlist_id):
            if playlist_id in self.checked_playlist_ids:
                return None
            
            if self.api.check_video_in_playlist(playlist_id, video_id):
                info = self.api.get_playlist_info(playlist_id)
                if info:
                    return info
            return None
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(check_playlist, pid): pid 
                for pid in playlist_ids
            }
            
            for future in as_completed(futures):
                checked_count += 1
                self._update_progress(
                    f"Checking playlist {checked_count}/{len(playlist_ids)}",
                    50 + int((checked_count / len(playlist_ids)) * 50)
                )
                
                result = future.result()
                if result:
                    found.append(result)
                    logging.info(f"Found in: {result.title}")
                
                playlist_id = futures[future]
                self.checked_playlist_ids.add(playlist_id)
        
        return found
    
    def export_results(
        self,
        video_info: VideoInfo,
        playlists: List[PlaylistInfo],
        format: str = "json",
        filename: str = None
    ) -> str:
        """Export results in various formats."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"playlists_{video_info.id}_{timestamp}.{format}"
        
        if format == "json":
            data = {
                "video": asdict(video_info),
                "found_playlists": [asdict(p) for p in playlists],
                "search_time": datetime.now().isoformat(),
                "total_found": len(playlists)
            }
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
                
        elif format == "csv":
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Playlist Title", "Channel", "URL", "Item Count", 
                    "Description", "Published"
                ])
                for p in playlists:
                    writer.writerow([
                        p.title, p.channel_title, p.url, p.item_count,
                        p.description[:100], p.published_at
                    ])
                    
        elif format == "html":
            html_content = self._generate_html_report(video_info, playlists)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        return filename
    
    def _generate_html_report(
        self,
        video_info: VideoInfo,
        playlists: List[PlaylistInfo]
    ) -> str:
        """Generate HTML report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Playlist Search Results</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .video-info {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
                .playlist {{ background: white; margin: 10px 0; padding: 15px; 
                           border: 1px solid #ddd; border-radius: 5px; }}
                .playlist:hover {{ background: #f9f9f9; }}
                h1 {{ color: #333; }}
                a {{ color: #1a73e8; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                .stats {{ color: #666; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <h1>Playlist Search Results</h1>
            
            <div class="video-info">
                <h2>Video Information</h2>
                <p><strong>Title:</strong> {video_info.title}</p>
                <p><strong>Channel:</strong> {video_info.channel_title}</p>
                <p><strong>URL:</strong> <a href="{video_info.url}" target="_blank">{video_info.url}</a></p>
                <p class="stats">Views: {video_info.view_count:,} | Likes: {video_info.like_count:,}</p>
            </div>
            
            <h2>Found in {len(playlists)} Playlists</h2>
        """
        
        for p in playlists:
            html += f"""
            <div class="playlist">
                <h3><a href="{p.url}" target="_blank">{p.title}</a></h3>
                <p><strong>Channel:</strong> {p.channel_title}</p>
                <p><strong>Videos:</strong> {p.item_count}</p>
                <p><strong>Description:</strong> {p.description[:200]}...</p>
                <p class="stats">Published: {p.published_at[:10]}</p>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        return html
    
    def get_statistics(self) -> Dict:
        """Get search statistics."""
        return {
            "api_quota_used": self.api.quota_used,
            "playlists_checked": len(self.checked_playlist_ids),
            "playlists_found": len(self.found_playlists),
            "cache_stats": self.cache_manager.get_stats()
        }
