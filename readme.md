# YouTube Playlist Finder Pro

A powerful Python application to find all YouTube playlists containing a specific video. Features both command-line and graphical interfaces with advanced search strategies and caching.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Version](https://img.shields.io/badge/version-2.0.0-brightgreen.svg)

## 🌟 Features

### Core Features
- **Multiple Search Strategies**: Find playlists using various methods
  - Exact title search
  - Channel playlists search
  - Title + Channel combination
  - Keyword-based search
  - Popular playlists search
  
- **Dual Interface**:
  - Modern GUI with tabs and real-time progress
  - Enhanced CLI with rich terminal output
  
- **Performance Optimizations**:
  - Smart caching system to reduce API calls
  - Parallel search support for faster results
  - Batch processing for multiple videos
  
- **Export Options**:
  - JSON format for data processing
  - HTML format for web viewing
  - CSV format for spreadsheet analysis

### Advanced Features
- Video preview before searching
- Progress tracking with visual feedback
- Quota management and error handling
- Search history and statistics
- Configurable search parameters
- Rate limiting to avoid API throttling

## 📋 Prerequisites

- Python 3.8 or higher
- YouTube Data API v3 key ([Get one here](https://console.cloud.google.com/apis/credentials))

## 🚀 Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/youtube-playlist-finder.git
cd youtube-playlist-finder
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up your API key

Provide your YouTube Data API key using any of these methods:

#### Option A: Configuration file
Copy `config-sample.yaml` to `config.yaml` and edit:
```yaml
api_key: "YOUR_YOUTUBE_API_KEY_HERE"
max_playlists: 100
cache_enabled: true
```
For the GUI, you can alternatively create a `gui_config.json` file:
```json
{
  "api_key": "YOUR_YOUTUBE_API_KEY_HERE"
}
```
YAML is the canonical format; JSON config files (`config.json` or `gui_config.json`) are also accepted.

#### Option B: Environment variable
```bash
export YOUTUBE_API_KEY="YOUR_API_KEY_HERE"
```

## 💻 Usage

### GUI Version (Recommended for beginners)

```bash
python youtube_playlist_gui.py
```

Features:
- User-friendly interface with tabs
- Visual progress indicators
- Click-to-open playlist URLs
- Built-in video preview
- Batch search interface

### CLI Version

#### Interactive Mode
```bash
python youtube_playlist_cli.py --interactive
```

#### Direct Search
```bash
# Search using video URL
python youtube_playlist_cli.py "https://www.youtube.com/watch?v=VIDEO_ID" --api-key YOUR_KEY

# Search using video ID
python youtube_playlist_cli.py "VIDEO_ID" --max-playlists 50

# Specify search strategies
python youtube_playlist_cli.py "VIDEO_ID" --strategies exact_title channel_playlists

# Export results
python youtube_playlist_cli.py "VIDEO_ID" --output results.json --format json
```

#### Batch Search
Create a file `videos.txt` with one video ID/URL per line:
```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
jNQXAC9IVRw
https://youtu.be/9bZkp7q19f0
```

Then run:
```bash
python youtube_playlist_cli.py --batch videos.txt --max-playlists 30
```

### Python API Usage

```python
from youtube_playlist_core import PlaylistFinder, SearchStrategy

# Initialize finder
finder = PlaylistFinder(api_key="YOUR_API_KEY")

# Search for playlists
video_id = "dQw4w9WgXcQ"
playlists = finder.find_playlists(
    video_id=video_id,
    strategies=[
        SearchStrategy.EXACT_TITLE,
        SearchStrategy.CHANNEL_PLAYLISTS
    ],
    max_playlists=100,
    parallel=True
)

# Display results
for playlist in playlists:
    print(f"Found in: {playlist.title} by {playlist.channel_title}")
    print(f"URL: {playlist.url}")
    print(f"Videos in playlist: {playlist.item_count}")
    print()

# Export results
video_info = finder.api.get_video_info(video_id)
finder.export_results(video_info, playlists, format="html", filename="results.html")
```

## 🔧 Configuration Options

### config.yaml
```yaml
# API Configuration
api_key: "YOUR_API_KEY"

# Search Settings
max_playlists: 100          # Maximum playlists to check
parallel_search: true        # Use parallel processing
search_strategies:           # Default strategies to use
  - exact_title
  - channel_playlists
  - title_channel

# Cache Settings
cache_enabled: true
cache_dir: ".cache"
cache_expire_hours: 24

# Output Settings
output_dir: "results"
export_formats:
  - json
  - html
```

## 📊 Search Strategies Explained

1. **Exact Title**: Searches for playlists using the exact video title
2. **Channel Playlists**: Checks all playlists from the video's channel
3. **Title + Channel**: Combines video title and channel name for better results
4. **Keyword Search**: Uses video tags and keywords from description
5. **Popular Playlists**: Searches for popular compilation playlists

## 🎯 Tips for Best Results

1. **Start with fewer strategies**: Begin with exact_title and channel_playlists
2. **Use caching**: Keep cache enabled to avoid redundant API calls
3. **Batch processing**: Process multiple videos together to save time
4. **Monitor quota**: YouTube API has daily quotas, monitor your usage
5. **Parallel search**: Enable for faster results with multiple playlists

## 📈 API Quota Management

YouTube Data API v3 has the following quotas:
- **Daily quota**: 10,000 units
- **Per-request costs**:
  - Search: 100 units
  - Playlist items list: 1 unit
  - Video details: 1 unit

This tool implements smart caching and optimization to minimize API usage:
- Caches all API responses for 24 hours
- Reuses video information across searches
- Batches playlist checks when possible

## 🐛 Troubleshooting

### Common Issues

1. **"API key not valid"**
   - Ensure your API key is correct
   - Check if YouTube Data API v3 is enabled in Google Cloud Console

2. **"Quota exceeded"**
   - Wait until the next day (quotas reset at midnight Pacific Time)
   - Consider using caching more aggressively
   - Reduce max_playlists value

3. **"No playlists found"**
   - Try different search strategies
   - The video might be in private playlists (not searchable)
   - Increase max_playlists value

4. **GUI doesn't start**
   - Ensure tkinter is installed: `python -m tkinter`
   - On Linux: `sudo apt-get install python3-tk`

### Debug Mode
Enable detailed logging:
```bash
python youtube_playlist_cli.py VIDEO_ID --verbose
```

## 📁 Project Structure

```
youtube-playlist-finder/
├── youtube_playlist_core.py    # Core functionality and API
├── youtube_playlist_cli.py     # Command-line interface
├── youtube_playlist_gui.py     # Graphical interface
├── requirements.txt            # Python dependencies
├── config-sample.yaml         # Example configuration
├── config.yaml                # User configuration
├── README.md                  # Documentation
├── .cache/                    # Cache directory (auto-created)
├── results/                   # Output directory (auto-created)
└── logs/                      # Log files (auto-created)
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Google for the YouTube Data API
- The Python community for excellent libraries
- Contributors and users of this tool

## 📮 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Contact: your.email@example.com

## 🚀 Future Enhancements

- [ ] Add support for authentication to find private playlists
- [ ] Implement playlist monitoring for changes
- [ ] Add support for channel-wide playlist analysis
- [ ] Create web interface version
- [ ] Add machine learning for better playlist discovery
- [ ] Support for multiple API keys rotation
- [ ] Export to more formats (Excel, PDF)
- [ ] Integration with playlist management tools

---

**Made with ❤️ by [Your Name]**

*If you find this tool useful, please consider giving it a ⭐ on GitHub!*