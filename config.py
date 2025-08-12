import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_key": "",
    "max_playlists": 100,
    "cache_enabled": True,
    "cache_dir": ".cache",
    "output_dir": "results",
    "parallel_search": True,
    "export_formats": ["json", "html"],
    "search_strategies": [
        "exact_title",
        "channel_playlists",
        "title_channel",
        "keyword_search",
    ],
}

def save_config(file_path: str, config: Dict[str, Any]) -> None:
    """Save configuration to a YAML or JSON file."""
    path = Path(file_path)
    try:
        with path.open("w") as f:
            if path.suffix.lower() in {".yaml", ".yml"}:
                yaml.dump(config, f, default_flow_style=False)
            elif path.suffix.lower() == ".json":
                json.dump(config, f, indent=2)
            else:
                raise ValueError("Unsupported config format: %s" % path.suffix)
    except Exception as e:
        logging.error(f"Error saving config: {e}")

def load_config(file_path: str, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load configuration from a YAML or JSON file and merge with defaults."""
    path = Path(file_path)
    data: Dict[str, Any] = {}
    if path.exists():
        try:
            with path.open("r") as f:
                if path.suffix.lower() in {".yaml", ".yml"}:
                    data = yaml.safe_load(f) or {}
                elif path.suffix.lower() == ".json":
                    data = json.load(f)
                else:
                    raise ValueError("Unsupported config format: %s" % path.suffix)
        except Exception as e:
            logging.warning(f"Error loading config: {e}")
            data = {}
    if defaults:
        merged = defaults.copy()
        merged.update(data)
        return merged
    return data

class Config:
    """Simple configuration manager."""

    def __init__(self, file_path: str = "config.yaml", defaults: Optional[Dict[str, Any]] = None):
        self.file_path = file_path
        self.defaults = defaults or DEFAULT_CONFIG
        if not Path(self.file_path).exists():
            save_config(self.file_path, self.defaults)
        self.config = load_config(self.file_path, self.defaults)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any, autosave: bool = True) -> None:
        self.config[key] = value
        if autosave:
            self.save()

    def save(self) -> None:
        save_config(self.file_path, self.config)
