import logging
import os
import sys

# Ensure the project root is on sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import Config

def test_empty_config_load(tmp_path, caplog):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("")
    with caplog.at_level(logging.WARNING):
        config = Config(str(cfg_file))
        # No warning should be logged
        assert "Error loading config" not in caplog.text
        # Config should fall back to defaults
        assert config.get("api_key") == ""
        assert config.get("max_playlists") == 100
