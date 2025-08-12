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
                logging.debug(
                    "Loaded %d cached entries from %s", len(self.cache), self.cache_file
                )
            except Exception as e:
                logging.warning(f"Cache load error: {e}")
                self.cache = {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            with self._lock:
                with open(self.cache_file, 'w') as f:
                    json.dump(self.cache, f, indent=2)
            logging.debug(
                "Saved %d cached entries to %s", len(self.cache), self.cache_file
            )
        except Exception as e:
            logging.warning(f"Cache save error: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self._lock:
            if key in self.cache:
                self.cache_stats["hits"] += 1
                logging.debug("Cache hit for key %s", key)
                return self.cache[key].get('data')
            self.cache_stats["misses"] += 1
            logging.debug("Cache miss for key %s", key)
            return None
    
    def set(self, key: str, value: Any):
        """Set item in cache."""
        with self._lock:
            self.cache[key] = {
                'data': value,
                'timestamp': datetime.now().isoformat()
            }
            logging.debug("Cache set for key %s", key)
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

    def __init__(
        self,
        api_key: str,
        cache_manager: Optional[CacheManager] = None,
        request_timeout: int = 10,
    ):
        self.api_key = api_key
        self.cache = cache_manager or CacheManager()
        self.rate_limiter = RateLimiter()
        self.quota_used = 0
        self.max_retries = 3
        self.request_timeout = request_timeout
        # Thread-local storage for per-thread API clients
        self._thread_local = threading.local()

    def _get_service(self):
        """Get or create the YouTube service for the current thread."""
        if not hasattr(self._thread_local, "youtube"):
            import httplib2

            http = httplib2.Http(timeout=self.request_timeout)
            self._thread_local.youtube = build(
                "youtube", "v3", developerKey=self.api_key, http=http
            )
        return self._thread_local.youtube

    def _make_request(self, resource: str, method: str = "list", **kwargs):
        cache_key = hashlib.md5(
            f"{resource}.{method}_{kwargs}".encode()
        ).hexdigest()
        # Avoid leaking API keys in logs
        safe_kwargs = kwargs.copy()
        if "key" in safe_kwargs:
            safe_kwargs["key"] = "REDACTED"
        logging.debug(
            "API request %s.%s with kwargs %s", resource, method, safe_kwargs
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            logging.debug("Using cached result for %s.%s", resource, method)
            return cached

        self.rate_limiter.wait_if_needed()

        service = self._get_service()

        for attempt in range(self.max_retries):
            try:
                logging.debug(
                    "Attempt %d for API call %s.%s", attempt + 1, resource, method
                )
                request_method = getattr(getattr(service, resource)(), method)
                request = request_method(**kwargs)
                result = request.execute()
                self.cache.set(cache_key, result)
                self.quota_used += 1
                logging.debug("API call %s.%s succeeded", resource, method)
                return result
            except HttpError as e:
                logging.debug(
                    "API call %s.%s failed with %s on attempt %d",
                    resource,
                    method,
                    e,
                    attempt + 1,
                )
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    raise QuotaExceededException("YouTube API quota exceeded")
                elif e.resp.status == 429:
                    time.sleep(2 ** attempt)
                elif attempt == self.max_retries - 1:
                    raise
                else:
                    time.sleep(1)
            except Exception as e:
                logging.debug(
                    "API call %s.%s raised %s on attempt %d",
                    resource,
                    method,
                    e,
                    attempt + 1,
                )
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(1)
        logging.error(
            "API call %s.%s failed after %d attempts", resource, method, self.max_retries
        )
        return None
    
    def get_video_info(self, video_id: str) -> Optional[VideoInfo]:
        """Get detailed video information."""
        try:
            response = self._make_request(
                "videos",
                part="snippet,contentDetails,statistics",
                id=video_id,
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
                "playlists",
                part="snippet,contentDetails,status",
                id=playlist_id,
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
                    "playlistItems",
                    part="contentDetails",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=page_token,
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
                    "search",
                    part="id",
                    q=query,
                    type="playlist",
                    maxResults=min(50, max_results - len(playlist_ids)),
                    pageToken=page_token,
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
                    "playlists",
                    part="id",
                    channelId=channel_id,
                    maxResults=min(50, max_results - len(playlist_ids)),
                    pageToken=page_token,
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


class SearchCancelled(Exception):
    """Exception raised when a search operation is cancelled."""
    pass


class PlaylistFinder:
    """Advanced playlist finder with multiple search strategies."""
    
    def __init__(self, api_key: str, cache_dir: str = ".cache"):
        self.cache_manager = CacheManager(cache_dir)
        self.api = YouTubeAPI(api_key, self.cache_manager)
        self.found_playlists = []
        self.checked_playlist_ids = set()
        self.progress_callback = None
        self._stop_event = threading.Event()
    
    def set_progress_callback(self, callback):
        """Set callback for progress updates."""
        self.progress_callback = callback

    def cancel_search(self):
        """Signal any running search to stop."""
        self._stop_event.set()
    
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
        logging.debug(
            "Starting search for video %s with strategies %s (max %d, parallel=%s)",
            video_id,
            strategies,
            max_playlists,
            parallel,
        )

        # Reset state for a fresh search
        self.found_playlists = []
        self.checked_playlist_ids = set()
        self._stop_event.clear()

        # Get video info first
        video_info = self.api.get_video_info(video_id)
        if not video_info:
            raise ValueError(f"Video {video_id} not found")
        logging.debug("Retrieved video info: %s", video_info)

        self._update_progress(f"Searching for playlists containing: {video_info.title}", 0)

        # Default strategies
        if not strategies:
            strategies = [
                SearchStrategy.EXACT_TITLE,
                SearchStrategy.CHANNEL_PLAYLISTS,
                SearchStrategy.TITLE_AND_CHANNEL,
                SearchStrategy.KEYWORD_SEARCH
            ]
            logging.debug("Using default strategies: %s", strategies)

        # Collect potential playlist IDs
        all_playlist_ids = set()

        for i, strategy in enumerate(strategies):
            if self._stop_event.is_set():
                raise SearchCancelled()
            self._update_progress(
                f"Strategy: {strategy.value}",
                int((i / len(strategies)) * 50)
            )
            logging.debug("Executing strategy %s", strategy)
            playlist_ids = self._search_by_strategy(strategy, video_info, max_playlists)
            logging.debug(
                "Strategy %s found %d playlists", strategy, len(playlist_ids)
            )
            all_playlist_ids.update(playlist_ids)

            if len(all_playlist_ids) >= max_playlists:
                logging.debug("Reached max playlist limit (%d)", max_playlists)
                break

        # Check playlists for video
        all_playlist_ids = list(all_playlist_ids)[:max_playlists]
        logging.debug("Checking %d unique playlists for video", len(all_playlist_ids))
        self._update_progress(f"Checking {len(all_playlist_ids)} playlists...", 50)

        if parallel:
            found = self._check_playlists_parallel(all_playlist_ids, video_id)
        else:
            found = self._check_playlists_sequential(all_playlist_ids, video_id)

        self._update_progress("Search complete!", 100)
        self.cache_manager._save_cache()
        logging.debug("Search complete: found %d playlists", len(found))

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
            logging.debug("Fetching playlists for channel %s", video_info.channel_id)
            playlist_ids = self.api.get_channel_playlists(video_info.channel_id, max_results)
            
        elif strategy == SearchStrategy.TITLE_AND_CHANNEL:
            query = f"{video_info.title} {video_info.channel_title}"
            logging.debug("Searching playlists with query: %s", query)
            playlist_ids = self.api.search_playlists(query, max_results)
            
        elif strategy == SearchStrategy.KEYWORD_SEARCH:
            # Use video tags and keywords from description
            keywords = video_info.tags[:3] if video_info.tags else []
            if keywords:
                query = " ".join(keywords)
                logging.debug("Keyword search with: %s", query)
                playlist_ids = self.api.search_playlists(query, max_results)
        
        elif strategy == SearchStrategy.POPULAR_PLAYLISTS:
            # Search for popular compilation playlists
            queries = ["best of", "compilation", "mix", "playlist"]
            results_per_query = max(1, max_results // len(queries))  # Guard against zero results
            for query in queries:
                ids = self.api.search_playlists(
                    f"{query} {video_info.channel_title}",
                    results_per_query
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
            if self._stop_event.is_set():
                raise SearchCancelled()
            if playlist_id in self.checked_playlist_ids:
                continue

            self._update_progress(
                f"Checking playlist {i+1}/{len(playlist_ids)}",
                50 + int((i / len(playlist_ids)) * 50)
            )
            logging.debug("Sequential check for playlist %s", playlist_id)

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
            try:
                if self._stop_event.is_set() or playlist_id in self.checked_playlist_ids:
                    return None

                if self.api.check_video_in_playlist(playlist_id, video_id):
                    info = self.api.get_playlist_info(playlist_id)
                    if info:
                        return info
            except Exception as e:
                logging.debug(f"Error processing playlist {playlist_id}: {e}")
            return None

        executor = ThreadPoolExecutor(max_workers=max_workers)
        futures = {executor.submit(check_playlist, pid): pid for pid in playlist_ids}
        try:
            logging.debug(
                "Parallel check for %d playlists with %d workers",
                len(playlist_ids),
                max_workers,
            )
            for future in as_completed(futures):
                if self._stop_event.is_set():
                    for f in futures:
                        f.cancel()
                    raise SearchCancelled()

                checked_count += 1
                self._update_progress(
                    f"Checking playlist {checked_count}/{len(playlist_ids)}",
                    50 + int((checked_count / len(playlist_ids)) * 50)
                )
                logging.debug(
                    "Completed check for playlist %s", futures[future]
                )

                try:
                    result = future.result()
                except Exception as e:
                    logging.debug(
                        "Future for playlist %s raised %s", futures[future], e
                    )
                    result = None

                if result:
                    found.append(result)
                    logging.info(f"Found in: {result.title}")

                playlist_id = futures[future]
                self.checked_playlist_ids.add(playlist_id)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

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
