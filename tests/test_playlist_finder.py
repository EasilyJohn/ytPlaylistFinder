import pytest

import threading

from youtube_playlist_core import (
    PlaylistFinder,
    SearchStrategy,
    VideoInfo,
    PlaylistInfo,
    CacheManager,
)


class FakeAPI:
    def get_video_info(self, video_id):
        return VideoInfo(
            id=video_id,
            title="title",
            channel_id="cid",
            channel_title="channel",
            description="",
            duration="",
            view_count=0,
            like_count=0,
            published_at="",
            thumbnail_url="",
            tags=[],
        )

    def search_playlists(self, query, max_results):
        if query == "title" or query == "title channel":
            return ["p1"]
        return []

    def get_channel_playlists(self, channel_id, max_results):
        return ["p1", "p2"]

    def check_video_in_playlist(self, playlist_id, video_id):
        return playlist_id == "p1"

    def get_playlist_info(self, playlist_id):
        return PlaylistInfo(
            id=playlist_id,
            title=f"Playlist {playlist_id}",
            channel_id="cid",
            channel_title="channel",
            description="",
            item_count=1,
            published_at="",
            thumbnail_url="",
        )

class DummyFinder(PlaylistFinder):
    def __init__(self, cache_dir):
        self.cache_manager = CacheManager(cache_dir)
        self.api = FakeAPI()
        self.found_playlists = []
        self.checked_playlist_ids = set()
        self.progress_callback = None
        self._stop_event = threading.Event()


def test_search_resets_checked_playlists(tmp_path):
    finder = DummyFinder(cache_dir=str(tmp_path))

    res1 = finder.find_playlists("v1", [SearchStrategy.EXACT_TITLE], parallel=False)
    assert len(res1) == 1

    res2 = finder.find_playlists(
        "v1",
        [SearchStrategy.EXACT_TITLE, SearchStrategy.CHANNEL_PLAYLISTS],
        parallel=False,
    )
    assert len(res2) == 1


def test_parallel_search_matches_sequential(tmp_path):
    finder = DummyFinder(cache_dir=str(tmp_path))
    strategies = [SearchStrategy.EXACT_TITLE, SearchStrategy.CHANNEL_PLAYLISTS]

    sequential = finder.find_playlists("v1", strategies, parallel=False)
    parallel = finder.find_playlists("v1", strategies, parallel=True)

    seq_ids = [p.id for p in sequential]
    par_ids = [p.id for p in parallel]

    assert seq_ids == par_ids
    assert len(sequential) == len(parallel)
