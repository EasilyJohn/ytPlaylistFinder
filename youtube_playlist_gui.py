#!/usr/bin/env python3
"""
youtube_playlist_gui.py - Modern GUI for YouTube Playlist Finder
A beautiful and functional graphical interface using tkinter
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import json
import webbrowser
import os
from datetime import datetime
from typing import List, Dict, Optional
import logging
import argparse
from pathlib import Path
from config import Config


logger = logging.getLogger(__name__)

def setup_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(Path("playlist_finder.log")),
            logging.StreamHandler(),
        ],
    )

# Import core module
try:
    from youtube_playlist_core import (
        PlaylistFinder, SearchStrategy, VideoInfo, PlaylistInfo,
        QuotaExceededException, SearchCancelled
    )
except ImportError:
    messagebox.showerror("Error", "youtube_playlist_core.py not found!")
    logger.error("youtube_playlist_core.py not found")
    exit(1)


class ModernButton(tk.Button):
    """Modern styled button."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(
            relief=tk.FLAT,
            bg="#4285f4",
            fg="white",
            font=("Segoe UI", 10),
            cursor="hand2",
            activebackground="#357ae8",
            activeforeground="white",
            padx=20,
            pady=10
        )
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
    
    def on_enter(self, e):
        self['bg'] = "#357ae8"
    
    def on_leave(self, e):
        self['bg'] = "#4285f4"


class SearchThread(threading.Thread):
    """Background thread for searching."""

    def __init__(self, finder, video_id, strategies, max_playlists, result_queue):
        super().__init__(daemon=True)
        self.finder = finder
        self.video_id = video_id
        self.strategies = strategies
        self.max_playlists = max_playlists
        self.result_queue = result_queue
        self.progress_queue = queue.Queue()

    def run(self):
        try:
            def progress_callback(msg, percent):
                self.progress_queue.put(("progress", msg, percent))

            self.finder.set_progress_callback(progress_callback)

            playlists = self.finder.find_playlists(
                self.video_id,
                self.strategies,
                self.max_playlists,
                parallel=True
            )

            video_info = self.finder.api.get_video_info(self.video_id)

            self.result_queue.put(("success", video_info, playlists))

        except SearchCancelled:
            self.result_queue.put(("cancelled", None))
        except QuotaExceededException as e:
            self.result_queue.put(("quota_error", str(e)))
        except Exception as e:
            self.result_queue.put(("error", str(e)))

    def stop(self):
        """Request the search to stop."""
        self.finder.cancel_search()


class YouTubePlaylistFinderGUI:
    """Main GUI Application."""

    def __init__(self, config: Optional[Config] = None):
        self.root = tk.Tk()
        self.root.title("YouTube Playlist Finder Pro")
        self.root.geometry("1200x700")
        
        # Set icon if available
        try:
            self.root.iconbitmap("youtube_icon.ico")
        except:
            pass
        
        # Variables
        self.api_key = tk.StringVar()
        self.video_input = tk.StringVar()
        self.max_playlists = tk.IntVar(value=100)
        self.search_thread = None
        self.result_queue = queue.Queue()
        self.finder = None
        self.current_results = []
        self.current_video_info = None
        self.config = config or Config()
        
        # Search strategies
        self.strategy_vars = {
            "Exact Title": tk.BooleanVar(value=True),
            "Channel Playlists": tk.BooleanVar(value=True),
            "Title + Channel": tk.BooleanVar(value=True),
            "Keyword Search": tk.BooleanVar(value=False),
            "Popular Playlists": tk.BooleanVar(value=False)
        }
        
        # Style configuration
        self.setup_styles()
        
        # Create UI
        self.create_widgets()
        
        # Load config
        self.load_config()
        
        # Start update loop
        self.update_progress()
        
        # Center window
        self.center_window()
    
    def setup_styles(self):
        """Configure ttk styles for modern look."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        bg_color = "#f5f5f5"
        self.root.configure(bg=bg_color)
        
        # Configure notebook style
        style.configure("TNotebook", background=bg_color)
        style.configure("TNotebook.Tab", padding=[20, 10])
        
        # Configure frame style
        style.configure("Card.TFrame", background="white", relief="flat", borderwidth=1)
        
        # Configure treeview style
        style.configure("Treeview", background="white", foreground="black", 
                       fieldbackground="white", font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        
        # Progress bar style
        style.configure("TProgressbar", thickness=20)
    
    def create_widgets(self):
        """Create all GUI widgets."""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Search tab
        search_tab = ttk.Frame(notebook)
        notebook.add(search_tab, text="  Search  ")
        self.create_search_tab(search_tab)
        
        # Results tab
        results_tab = ttk.Frame(notebook)
        notebook.add(results_tab, text="  Results  ")
        self.create_results_tab(results_tab)
        
        # Batch tab
        batch_tab = ttk.Frame(notebook)
        notebook.add(batch_tab, text="  Batch Search  ")
        self.create_batch_tab(batch_tab)
        
        # Settings tab
        settings_tab = ttk.Frame(notebook)
        notebook.add(settings_tab, text="  Settings  ")
        self.create_settings_tab(settings_tab)
        
        # About tab
        about_tab = ttk.Frame(notebook)
        notebook.add(about_tab, text="  About  ")
        self.create_about_tab(about_tab)
    
    def create_search_tab(self, parent):
        """Create the search tab."""
        # Main container
        container = ttk.Frame(parent, style="Card.TFrame", padding=20)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title = tk.Label(container, text="Find Playlists Containing a Video",
                        font=("Segoe UI", 18, "bold"), bg="white")
        title.pack(pady=(0, 20))
        
        # Video input section
        input_frame = ttk.Frame(container)
        input_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(input_frame, text="Video URL or ID:", 
                font=("Segoe UI", 11), bg="white").pack(side=tk.LEFT, padx=(0, 10))
        
        entry = tk.Entry(input_frame, textvariable=self.video_input,
                        font=("Segoe UI", 11), width=50)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Preview button
        preview_btn = tk.Button(input_frame, text="Preview", 
                               command=self.preview_video,
                               bg="#f8f9fa", relief=tk.FLAT,
                               cursor="hand2", padx=15)
        preview_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # Video info display
        self.video_info_frame = ttk.Frame(container)
        self.video_info_frame.pack(fill=tk.X, pady=10)
        
        # Search options
        options_frame = ttk.LabelFrame(container, text="Search Options", padding=15)
        options_frame.pack(fill=tk.X, pady=10)
        
        # Max playlists
        max_frame = ttk.Frame(options_frame)
        max_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(max_frame, text="Maximum playlists to check:",
                font=("Segoe UI", 10)).pack(side=tk.LEFT)
        
        tk.Spinbox(max_frame, from_=10, to=500, textvariable=self.max_playlists,
                  width=10, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(10, 0))
        
        # Strategies
        strat_label = tk.Label(options_frame, text="Search Strategies:",
                              font=("Segoe UI", 10, "bold"))
        strat_label.pack(anchor=tk.W, pady=(10, 5))
        
        strat_frame = ttk.Frame(options_frame)
        strat_frame.pack(fill=tk.X)
        
        for i, (name, var) in enumerate(self.strategy_vars.items()):
            cb = tk.Checkbutton(strat_frame, text=name, variable=var,
                               font=("Segoe UI", 9), bg="white")
            cb.grid(row=i//3, column=i%3, sticky=tk.W, padx=5, pady=2)
        
        # Progress section
        self.progress_frame = ttk.Frame(container)
        self.progress_frame.pack(fill=tk.X, pady=20)
        
        self.progress_label = tk.Label(self.progress_frame, text="",
                                      font=("Segoe UI", 10), bg="white")
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate',
                                           length=400)

        # Search button
        self.search_btn = ModernButton(container, text="🔍 Start Search",
                                      command=self.start_search,
                                      font=("Segoe UI", 12, "bold"))
        self.search_btn.pack(pady=10)

        # Stop button
        self.stop_btn = ModernButton(container, text="⏹ Stop Search",
                                     command=self.stop_search,
                                     font=("Segoe UI", 12, "bold"),
                                     state=tk.DISABLED)
        self.stop_btn.pack(pady=(0, 20))
        
        # Status bar
        self.status_label = tk.Label(container, text="Ready", 
                                    font=("Segoe UI", 9), bg="white", fg="gray")
        self.status_label.pack(side=tk.BOTTOM, pady=(10, 0))
    
    def create_results_tab(self, parent):
        """Create the results tab."""
        container = ttk.Frame(parent, padding=10)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Results header
        header_frame = ttk.Frame(container)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.results_label = tk.Label(header_frame, 
                                     text="No search performed yet",
                                     font=("Segoe UI", 14, "bold"))
        self.results_label.pack(side=tk.LEFT)
        
        # Export buttons
        export_frame = ttk.Frame(header_frame)
        export_frame.pack(side=tk.RIGHT)
        
        tk.Button(export_frame, text="Export JSON", command=lambda: self.export_results("json"),
                 bg="#28a745", fg="white", relief=tk.FLAT, cursor="hand2",
                 padx=10).pack(side=tk.LEFT, padx=2)
        
        tk.Button(export_frame, text="Export HTML", command=lambda: self.export_results("html"),
                 bg="#17a2b8", fg="white", relief=tk.FLAT, cursor="hand2",
                 padx=10).pack(side=tk.LEFT, padx=2)
        
        tk.Button(export_frame, text="Export CSV", command=lambda: self.export_results("csv"),
                 bg="#ffc107", fg="black", relief=tk.FLAT, cursor="hand2",
                 padx=10).pack(side=tk.LEFT, padx=2)
        
        # Results tree
        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview with scrollbars
        tree_scroll_y = ttk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.results_tree = ttk.Treeview(tree_frame, 
                                        yscrollcommand=tree_scroll_y.set,
                                        xscrollcommand=tree_scroll_x.set,
                                        columns=("Channel", "Videos", "Published"),
                                        height=20)
        self.results_tree.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll_y.config(command=self.results_tree.yview)
        tree_scroll_x.config(command=self.results_tree.xview)
        
        # Configure columns
        self.results_tree.heading("#0", text="Playlist Title")
        self.results_tree.heading("Channel", text="Channel")
        self.results_tree.heading("Videos", text="Videos")
        self.results_tree.heading("Published", text="Published")
        
        self.results_tree.column("#0", width=400)
        self.results_tree.column("Channel", width=200)
        self.results_tree.column("Videos", width=80)
        self.results_tree.column("Published", width=100)
        
        # Bind double-click to open URL
        self.results_tree.bind("<Double-1>", self.open_playlist_url)
        
        # Context menu
        self.create_context_menu()
    
    def create_batch_tab(self, parent):
        """Create batch search tab."""
        container = ttk.Frame(parent, padding=20)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Title
        tk.Label(container, text="Batch Search Multiple Videos",
                font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))
        
        # Input method
        method_frame = ttk.LabelFrame(container, text="Input Method", padding=10)
        method_frame.pack(fill=tk.X, pady=10)
        
        self.batch_method = tk.StringVar(value="manual")
        
        tk.Radiobutton(method_frame, text="Manual Input", variable=self.batch_method,
                      value="manual", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=10)
        
        tk.Radiobutton(method_frame, text="Load from File", variable=self.batch_method,
                      value="file", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=10)
        
        tk.Button(method_frame, text="Browse...", command=self.browse_batch_file,
                 bg="#6c757d", fg="white", relief=tk.FLAT,
                 cursor="hand2").pack(side=tk.RIGHT, padx=10)
        
        # Input area
        input_frame = ttk.LabelFrame(container, text="Video IDs/URLs (one per line)", 
                                    padding=10)
        input_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.batch_text = scrolledtext.ScrolledText(input_frame, height=10,
                                                    font=("Consolas", 10))
        self.batch_text.pack(fill=tk.BOTH, expand=True)
        
        # Batch options
        options_frame = ttk.Frame(container)
        options_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(options_frame, text="Max playlists per video:",
                font=("Segoe UI", 10)).pack(side=tk.LEFT)
        
        self.batch_max = tk.IntVar(value=50)
        tk.Spinbox(options_frame, from_=10, to=200, textvariable=self.batch_max,
                  width=10).pack(side=tk.LEFT, padx=(10, 0))
        
        # Start button
        self.batch_btn = ModernButton(container, text="Start Batch Search",
                                     command=self.start_batch_search,
                                     font=("Segoe UI", 12, "bold"))
        self.batch_btn.pack(pady=20)
        
        # Results area
        results_frame = ttk.LabelFrame(container, text="Batch Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        self.batch_results = scrolledtext.ScrolledText(results_frame, height=8,
                                                       font=("Consolas", 9))
        self.batch_results.pack(fill=tk.BOTH, expand=True)
    
    def create_settings_tab(self, parent):
        """Create settings tab."""
        container = ttk.Frame(parent, padding=20)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Title
        tk.Label(container, text="Settings",
                font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))
        
        # API Key section
        api_frame = ttk.LabelFrame(container, text="YouTube API Configuration", padding=15)
        api_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(api_frame, text="API Key:",
                font=("Segoe UI", 10)).pack(anchor=tk.W)
        
        key_frame = ttk.Frame(api_frame)
        key_frame.pack(fill=tk.X, pady=5)
        
        self.api_key_entry = tk.Entry(key_frame, textvariable=self.api_key,
                                     show="*", font=("Segoe UI", 10))
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.show_key_var = tk.BooleanVar()
        tk.Checkbutton(key_frame, text="Show", variable=self.show_key_var,
                      command=self.toggle_api_key_visibility).pack(side=tk.LEFT, padx=5)
        
        tk.Button(api_frame, text="Save API Key", command=self.save_api_key,
                 bg="#28a745", fg="white", relief=tk.FLAT,
                 cursor="hand2").pack(anchor=tk.W, pady=5)
        
        # Cache settings
        cache_frame = ttk.LabelFrame(container, text="Cache Settings", padding=15)
        cache_frame.pack(fill=tk.X, pady=10)
        
        self.cache_enabled = tk.BooleanVar(value=True)
        tk.Checkbutton(cache_frame, text="Enable caching",
                      variable=self.cache_enabled,
                      font=("Segoe UI", 10)).pack(anchor=tk.W)
        
        tk.Button(cache_frame, text="Clear Cache", command=self.clear_cache,
                 bg="#dc3545", fg="white", relief=tk.FLAT,
                 cursor="hand2").pack(anchor=tk.W, pady=10)
        
        # Performance settings
        perf_frame = ttk.LabelFrame(container, text="Performance", padding=15)
        perf_frame.pack(fill=tk.X, pady=10)
        
        self.parallel_search = tk.BooleanVar(value=True)
        tk.Checkbutton(perf_frame, text="Use parallel search (faster)",
                      variable=self.parallel_search,
                      font=("Segoe UI", 10)).pack(anchor=tk.W)
        
        # Statistics
        stats_frame = ttk.LabelFrame(container, text="Statistics", padding=15)
        stats_frame.pack(fill=tk.X, pady=10)
        
        self.stats_text = tk.Text(stats_frame, height=5, font=("Consolas", 9))
        self.stats_text.pack(fill=tk.X)
        
        tk.Button(stats_frame, text="Refresh Statistics", command=self.update_statistics,
                 bg="#6c757d", fg="white", relief=tk.FLAT,
                 cursor="hand2").pack(pady=5)
    
    def create_about_tab(self, parent):
        """Create about tab."""
        container = ttk.Frame(parent, padding=20)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Logo/Title
        title_frame = ttk.Frame(container)
        title_frame.pack(pady=20)
        
        tk.Label(title_frame, text="YouTube Playlist Finder Pro",
                font=("Segoe UI", 24, "bold")).pack()
        
        tk.Label(title_frame, text="Version 2.0",
                font=("Segoe UI", 12), fg="gray").pack()
        
        # Description
        desc_text = """
A powerful tool for finding YouTube playlists that contain specific videos.

Features:
✓ Multiple search strategies for comprehensive results
✓ Batch search for multiple videos
✓ Export results in JSON, HTML, and CSV formats
✓ Smart caching to reduce API usage
✓ Parallel search for faster results
✓ Modern and intuitive user interface

How to use:
1. Enter your YouTube API key in Settings
2. Paste a video URL or ID in the Search tab
3. Select search strategies and options
4. Click "Start Search" to find playlists
5. Export or browse results as needed
        """
        
        tk.Label(container, text=desc_text, justify=tk.LEFT,
                font=("Segoe UI", 10)).pack(pady=20)
        
        # Links
        links_frame = ttk.Frame(container)
        links_frame.pack()
        
        tk.Button(links_frame, text="Get API Key", 
                 command=lambda: webbrowser.open("https://console.cloud.google.com/apis/credentials"),
                 bg="#4285f4", fg="white", relief=tk.FLAT,
                 cursor="hand2", padx=20).pack(side=tk.LEFT, padx=5)
        
        tk.Button(links_frame, text="Documentation",
                 command=lambda: webbrowser.open("https://github.com/yourusername/youtube-playlist-finder"),
                 bg="#333", fg="white", relief=tk.FLAT,
                 cursor="hand2", padx=20).pack(side=tk.LEFT, padx=5)
        
        # Credits
        tk.Label(container, text="Developed with ❤️ using Python and tkinter",
                font=("Segoe UI", 9), fg="gray").pack(side=tk.BOTTOM)
    
    def create_context_menu(self):
        """Create right-click context menu for results."""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Open in Browser", command=self.open_selected_url)
        self.context_menu.add_command(label="Copy URL", command=self.copy_selected_url)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="View Details", command=self.view_playlist_details)
        
        self.results_tree.bind("<Button-3>", self.show_context_menu)
    
    def show_context_menu(self, event):
        """Show context menu on right-click."""
        try:
            self.results_tree.selection_set(self.results_tree.identify_row(event.y))
            self.context_menu.post(event.x_root, event.y_root)
        except:
            pass
    
    def preview_video(self):
        """Preview video information."""
        video_input = self.video_input.get().strip()
        if not video_input:
            logger.warning("Preview requested without video input")
            return

        video_id = self.extract_video_id(video_input)
        if not video_id:
            messagebox.showwarning("Invalid Input", "Please enter a valid YouTube video URL or ID")
            logger.warning("Invalid video input for preview: %s", video_input)
            return

        if not self.api_key.get():
            messagebox.showwarning("No API Key", "Please set your API key in Settings first")
            logger.warning("Preview attempted without API key")
            return

        try:
            if not self.finder:
                self.finder = PlaylistFinder(self.api_key.get())

            video_info = self.finder.api.get_video_info(video_id)
            if video_info:
                self.display_video_preview(video_info)
                logger.info("Preview loaded for video %s", video_id)
            else:
                messagebox.showerror("Error", "Could not fetch video information")
                logger.error("Could not fetch video information for %s", video_id)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to preview video: {e}")
            logger.error("Failed to preview video %s: %s", video_input, e)
    
    def display_video_preview(self, video_info: VideoInfo):
        """Display video preview in the search tab."""
        # Clear previous preview
        for widget in self.video_info_frame.winfo_children():
            widget.destroy()
        
        # Create preview card
        preview = ttk.Frame(self.video_info_frame, relief=tk.RIDGE, borderwidth=1)
        preview.pack(fill=tk.X, pady=5)
        
        # Video details
        info_text = f"Title: {video_info.title[:50]}...\n"
        info_text += f"Channel: {video_info.channel_title}\n"
        info_text += f"Views: {video_info.view_count:,} | Likes: {video_info.like_count:,}"
        
        tk.Label(preview, text=info_text, justify=tk.LEFT,
                font=("Segoe UI", 9)).pack(padx=10, pady=5)
    
    def start_search(self):
        """Start the playlist search."""
        video_input = self.video_input.get().strip()
        if not video_input:
            messagebox.showwarning("Input Required", "Please enter a video URL or ID")
            logger.warning("Search attempted without video input")
            return

        video_id = self.extract_video_id(video_input)
        if not video_id:
            messagebox.showwarning("Invalid Input", "Please enter a valid YouTube video URL or ID")
            logger.warning("Invalid video input for search: %s", video_input)
            return

        if not self.api_key.get():
            messagebox.showwarning("API Key Required", "Please set your API key in Settings")
            logger.warning("Search attempted without API key")
            return
        
        # Get selected strategies
        strategy_map = {
            "Exact Title": SearchStrategy.EXACT_TITLE,
            "Channel Playlists": SearchStrategy.CHANNEL_PLAYLISTS,
            "Title + Channel": SearchStrategy.TITLE_AND_CHANNEL,
            "Keyword Search": SearchStrategy.KEYWORD_SEARCH,
            "Popular Playlists": SearchStrategy.POPULAR_PLAYLISTS
        }
        
        strategies = [strategy_map[name] for name, var in self.strategy_vars.items() if var.get()]

        if not strategies:
            messagebox.showwarning("No Strategies", "Please select at least one search strategy")
            logger.warning("Search attempted without selecting strategies")
            return
        
        # Initialize finder if needed
        if not self.finder:
            self.finder = PlaylistFinder(self.api_key.get())

        logger.info(
            "Starting search for video %s with strategies %s",
            video_id,
            [s.name for s in strategies],
        )

        # Disable search button and enable stop
        self.search_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Searching...")
        
        # Show progress bar
        self.progress_bar.pack(pady=5)
        self.progress_bar['value'] = 0
        
        # Start search thread
        self.search_thread = SearchThread(
            self.finder,
            video_id,
            strategies,
            self.max_playlists.get(),
            self.result_queue
        )
        self.search_thread.start()

    def stop_search(self):
        """Stop the current search."""
        if self.search_thread and self.search_thread.is_alive():
            self.search_thread.stop()
            self.stop_btn.config(state=tk.DISABLED)
            self.status_label.config(text="Stopping search...")
    
    def update_progress(self):
        """Update progress from search thread."""
        # Check for results
        try:
            while True:
                result = self.result_queue.get_nowait()

                if result[0] == "success":
                    self.on_search_complete(result[1], result[2])
                elif result[0] == "error":
                    self.on_search_error(result[1])
                elif result[0] == "quota_error":
                    self.on_quota_error()
                elif result[0] == "cancelled":
                    self.on_search_cancelled()
        except queue.Empty:
            pass
        
        # Check for progress updates
        if self.search_thread and self.search_thread.is_alive():
            try:
                while True:
                    progress = self.search_thread.progress_queue.get_nowait()
                    if progress[0] == "progress":
                        self.progress_label.config(text=progress[1])
                        logger.info(progress[1])
                        if progress[2] is not None:
                            self.progress_bar['value'] = progress[2]
            except queue.Empty:
                pass
        
        # Schedule next update
        self.root.after(100, self.update_progress)
    
    def on_search_complete(self, video_info: VideoInfo, playlists: List[PlaylistInfo]):
        """Handle search completion."""
        self.current_video_info = video_info
        self.current_results = playlists
        
        # Update UI
        self.search_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_bar.pack_forget()
        self.progress_label.config(text="")
        
        # Update status
        self.status_label.config(text=f"Found {len(playlists)} playlists")
        
        # Update results tab
        self.display_results(video_info, playlists)
        
        # Show completion message
        if playlists:
            messagebox.showinfo("Search Complete",
                              f"Found {len(playlists)} playlists containing the video!")
        else:
            messagebox.showinfo("Search Complete",
                              "No playlists found containing this video.")
        logger.info(
            "Search complete for video %s: %d playlists found",
            video_info.id,
            len(playlists),
        )

    def on_search_error(self, error_msg: str):
        """Handle search error."""
        self.search_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_bar.pack_forget()
        self.progress_label.config(text="")
        self.status_label.config(text="Search failed")

        messagebox.showerror("Search Error", f"Search failed: {error_msg}")
        logger.error("Search failed: %s", error_msg)

    def on_quota_error(self):
        """Handle quota exceeded error."""
        self.search_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_bar.pack_forget()
        self.progress_label.config(text="")
        self.status_label.config(text="Quota exceeded")

        messagebox.showerror("Quota Exceeded",
                           "YouTube API quota exceeded. Please try again tomorrow.")
        logger.error("YouTube API quota exceeded")

    def on_search_cancelled(self):
        """Handle user-cancelled search."""
        self.search_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_bar.pack_forget()
        self.progress_label.config(text="")
        self.status_label.config(text="Search cancelled")
    
    def display_results(self, video_info: VideoInfo, playlists: List[PlaylistInfo]):
        """Display search results in the results tab."""
        # Update header
        self.results_label.config(
            text=f"Results for: {video_info.title[:50]}... ({len(playlists)} playlists found)"
        )
        
        # Clear tree
        self.results_tree.delete(*self.results_tree.get_children())
        
        # Add results
        for playlist in playlists:
            self.results_tree.insert("", tk.END, 
                                    text=playlist.title,
                                    values=(playlist.channel_title,
                                           playlist.item_count,
                                           playlist.published_at[:10]),
                                    tags=(playlist.url,))
    
    def open_playlist_url(self, event):
        """Open playlist URL on double-click."""
        selection = self.results_tree.selection()
        if selection:
            item = self.results_tree.item(selection[0])
            if item['tags']:
                webbrowser.open(item['tags'][0])
    
    def open_selected_url(self):
        """Open selected playlist URL."""
        selection = self.results_tree.selection()
        if selection:
            item = self.results_tree.item(selection[0])
            if item['tags']:
                webbrowser.open(item['tags'][0])
    
    def copy_selected_url(self):
        """Copy selected playlist URL to clipboard."""
        selection = self.results_tree.selection()
        if selection:
            item = self.results_tree.item(selection[0])
            if item['tags']:
                self.root.clipboard_clear()
                self.root.clipboard_append(item['tags'][0])
                self.status_label.config(text="URL copied to clipboard")
    
    def view_playlist_details(self):
        """View detailed information about selected playlist."""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item = self.results_tree.item(selection[0])
        
        # Find the playlist in results
        playlist = None
        for p in self.current_results:
            if p.title == item['text']:
                playlist = p
                break
        
        if playlist:
            details = f"Title: {playlist.title}\n"
            details += f"Channel: {playlist.channel_title}\n"
            details += f"Videos: {playlist.item_count}\n"
            details += f"Published: {playlist.published_at}\n"
            details += f"URL: {playlist.url}\n\n"
            details += f"Description:\n{playlist.description}"
            
            messagebox.showinfo("Playlist Details", details)
    
    def export_results(self, format: str):
        """Export results in specified format."""
        if not self.current_results:
            messagebox.showwarning("No Results", "No results to export")
            logger.warning("Export attempted with no results")
            return
        
        # Ask for filename
        if format == "json":
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
        elif format == "html":
            filename = filedialog.asksaveasfilename(
                defaultextension=".html",
                filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
            )
        elif format == "csv":
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
        else:
            return
        
        if filename:
            try:
                self.finder.export_results(
                    self.current_video_info,
                    self.current_results,
                    format,
                    filename
                )
                messagebox.showinfo("Export Successful", f"Results exported to {filename}")
                logger.info("Results exported to %s", filename)
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")
                logger.error("Failed to export results: %s", e)
    
    def start_batch_search(self):
        """Start batch search."""
        # Get video IDs
        text = self.batch_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("No Input", "Please enter video IDs or URLs")
            logger.warning("Batch search attempted without input")
            return
        
        video_ids = []
        for line in text.split('\n'):
            line = line.strip()
            if line:
                video_id = self.extract_video_id(line)
                if video_id:
                    video_ids.append(video_id)
        
        if not video_ids:
            messagebox.showwarning("No Valid IDs", "No valid video IDs found")
            logger.warning("Batch search found no valid video IDs")
            return
        
        if not self.api_key.get():
            messagebox.showwarning("API Key Required", "Please set your API key in Settings")
            logger.warning("Batch search attempted without API key")
            return
        
        # Initialize finder if needed
        if not self.finder:
            self.finder = PlaylistFinder(self.api_key.get())
        
        # Clear results
        self.batch_results.delete("1.0", tk.END)
        self.batch_btn.config(state=tk.DISABLED)

        logger.info("Starting batch search for %d videos", len(video_ids))

        # Start batch search in thread
        def batch_search():
            for i, video_id in enumerate(video_ids, 1):
                self.batch_results.insert(tk.END, f"[{i}/{len(video_ids)}] Searching {video_id}...\n")
                self.batch_results.see(tk.END)
                self.root.update()
                logger.info("Batch search %d/%d for video %s", i, len(video_ids), video_id)

                try:
                    playlists = self.finder.find_playlists(
                        video_id,
                        max_playlists=self.batch_max.get()
                    )
                    self.batch_results.insert(tk.END, f"  Found {len(playlists)} playlists\n")
                    logger.info("Found %d playlists for %s", len(playlists), video_id)
                except Exception as e:
                    self.batch_results.insert(tk.END, f"  Error: {e}\n")
                    logger.error("Batch search error for %s: %s", video_id, e)

                self.batch_results.see(tk.END)
                self.root.update()

            self.batch_results.insert(tk.END, "\nBatch search complete!\n")
            self.batch_btn.config(state=tk.NORMAL)
            logger.info("Batch search complete")

        thread = threading.Thread(target=batch_search, daemon=True)
        thread.start()
    
    def browse_batch_file(self):
        """Browse for batch input file."""
        filename = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    content = f.read()
                self.batch_text.delete("1.0", tk.END)
                self.batch_text.insert("1.0", content)
                logger.info("Loaded batch input file %s", filename)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {e}")
                logger.error("Failed to load batch file %s: %s", filename, e)
    
    def toggle_api_key_visibility(self):
        """Toggle API key visibility."""
        if self.show_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")
    
    def save_api_key(self):
        """Save API key to config."""
        if self.api_key.get():
            self.save_config()
            messagebox.showinfo("Saved", "API key saved successfully")
            logger.info("API key saved")
        else:
            messagebox.showwarning("No Key", "Please enter an API key")
            logger.warning("Attempted to save empty API key")
    
    def clear_cache(self):
        """Clear the cache."""
        if messagebox.askyesno("Clear Cache", "Are you sure you want to clear the cache?"):
            try:
                import shutil
                cache_dir = ".cache"
                if os.path.exists(cache_dir):
                    shutil.rmtree(cache_dir)
                    os.makedirs(cache_dir)
                messagebox.showinfo("Success", "Cache cleared successfully")
                logger.info("Cache cleared at %s", cache_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache: {e}")
                logger.error("Failed to clear cache: %s", e)
    
    def update_statistics(self):
        """Update statistics display."""
        if self.finder:
            stats = self.finder.get_statistics()
            
            text = f"API Quota Used: {stats['api_quota_used']}\n"
            text += f"Playlists Checked: {stats['playlists_checked']}\n"
            text += f"Playlists Found: {stats['playlists_found']}\n"
            text += f"Cache Hit Rate: {stats['cache_stats']['hit_rate']}\n"
            text += f"Cache Entries: {stats['cache_stats']['total_entries']}"
            
            self.stats_text.delete("1.0", tk.END)
            self.stats_text.insert("1.0", text)
        else:
            self.stats_text.delete("1.0", tk.END)
            self.stats_text.insert("1.0", "No statistics available yet")
    
    def extract_video_id(self, input_str: str) -> Optional[str]:
        """Extract video ID from URL or return as-is if already an ID."""
        import re
        
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, input_str)
            if match:
                return match.group(1)
        
        return None
    
    def load_config(self):
        """Load configuration from shared config file."""
        self.api_key.set(self.config.get('api_key', ''))
        self.max_playlists.set(self.config.get('max_playlists', 100))
        self.cache_enabled.set(self.config.get('cache_enabled', True))
        self.parallel_search.set(self.config.get('parallel_search', True))

    def save_config(self):
        """Persist configuration to shared config file."""
        self.config.set('api_key', self.api_key.get(), autosave=False)
        self.config.set('max_playlists', self.max_playlists.get(), autosave=False)
        self.config.set('cache_enabled', self.cache_enabled.get(), autosave=False)
        self.config.set('parallel_search', self.parallel_search.get(), autosave=False)
        self.config.save()
        logger.info("GUI configuration saved")
    
    def center_window(self):
        """Center the window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def run(self):
        """Run the GUI application."""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window closing."""
        self.save_config()
        self.root.destroy()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="YouTube Playlist Finder GUI")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    args = parser.parse_args()

    config = Config()
    log_level = args.log_level or config.get("log_level", "INFO")
    if args.log_level and args.log_level != config.get("log_level"):
        config.set("log_level", args.log_level)

    setup_logging(log_level)

    app = YouTubePlaylistFinderGUI(config)
    app.run()


if __name__ == "__main__":
    main()
