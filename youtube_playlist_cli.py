#!/usr/bin/env python3
"""
youtube_playlist_cli.py - Enhanced Command Line Interface for YouTube Playlist Finder
"""

import os
import sys
import argparse
import json
import logging
from typing import List, Optional
from datetime import datetime
from pathlib import Path

# Rich terminal output support
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.panel import Panel
    from rich.logging import RichHandler
    from rich.prompt import Prompt, Confirm
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Install 'rich' for better terminal output: pip install rich")

# Import core module
try:
    from youtube_playlist_core import (
        PlaylistFinder, SearchStrategy, VideoInfo, PlaylistInfo,
        QuotaExceededException
    )
except ImportError:
    print("Error: youtube_playlist_core.py not found in the same directory")
    sys.exit(1)


from config import Config


class CLIInterface:
    """Enhanced CLI interface with rich output."""
    
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.config = Config()
        self.setup_logging()
        self.finder = None
    
    def setup_logging(self):
        """Setup logging configuration."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"playlist_finder_{datetime.now():%Y%m%d}.log"
        
        if RICH_AVAILABLE:
            logging.basicConfig(
                level=logging.INFO,
                format="%(message)s",
                handlers=[
                    RichHandler(console=self.console, rich_tracebacks=True),
                    logging.FileHandler(log_file)
                ]
            )
        else:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(log_file)
                ]
            )
    
    def print_banner(self):
        """Print application banner."""
        if self.console:
            banner = """
[bold blue]╔══════════════════════════════════════════╗
║     YouTube Playlist Finder Pro v2.0     ║
║         Enhanced Edition with GUI         ║
╚══════════════════════════════════════════╝[/bold blue]
            """
            self.console.print(banner)
        else:
            print("\n" + "="*50)
            print("  YouTube Playlist Finder Pro v2.0")
            print("="*50 + "\n")
    
    def interactive_mode(self):
        """Run in interactive mode with prompts."""
        self.print_banner()
        
        # Check API key
        api_key = self.config.get("api_key")
        if not api_key:
            if RICH_AVAILABLE:
                api_key = Prompt.ask("[yellow]Enter your YouTube API key[/yellow]")
            else:
                api_key = input("Enter your YouTube API key: ")
            
            if api_key:
                self.config.set("api_key", api_key)
        
        if not api_key:
            self.error("No API key provided. Exiting.")
            return
        
        # Initialize finder
        self.finder = PlaylistFinder(api_key, self.config.get("cache_dir"))
        
        while True:
            self.show_menu()
            choice = self.get_choice()
            
            if choice == "1":
                self.search_single_video()
            elif choice == "2":
                self.batch_search()
            elif choice == "3":
                self.show_statistics()
            elif choice == "4":
                self.configure_settings()
            elif choice == "5":
                self.clear_cache()
            elif choice == "6":
                self.export_history()
            elif choice == "0":
                if RICH_AVAILABLE:
                    if Confirm.ask("Exit the application?"):
                        break
                else:
                    if input("Exit? (y/n): ").lower() == 'y':
                        break
            else:
                self.error("Invalid choice")
    
    def show_menu(self):
        """Display main menu."""
        if self.console:
            menu = Table(title="Main Menu", show_header=False)
            menu.add_column("Option", style="cyan", width=50)
            menu.add_row("[1] Search for playlists containing a video")
            menu.add_row("[2] Batch search multiple videos")
            menu.add_row("[3] View statistics")
            menu.add_row("[4] Configure settings")
            menu.add_row("[5] Clear cache")
            menu.add_row("[6] Export search history")
            menu.add_row("[0] Exit")
            self.console.print(menu)
        else:
            print("\n--- Main Menu ---")
            print("1. Search for playlists containing a video")
            print("2. Batch search multiple videos")
            print("3. View statistics")
            print("4. Configure settings")
            print("5. Clear cache")
            print("6. Export search history")
            print("0. Exit")
    
    def get_choice(self) -> str:
        """Get user menu choice."""
        if RICH_AVAILABLE:
            return Prompt.ask("\n[bold]Choose an option[/bold]")
        else:
            return input("\nChoose an option: ")
    
    def search_single_video(self):
        """Search for playlists containing a single video."""
        # Get video ID or URL
        if RICH_AVAILABLE:
            video_input = Prompt.ask("\n[cyan]Enter video ID or URL[/cyan]")
        else:
            video_input = input("\nEnter video ID or URL: ")
        
        # Extract video ID from URL if needed
        video_id = self.extract_video_id(video_input)
        if not video_id:
            self.error("Invalid video ID or URL")
            return
        
        # Get search options
        max_playlists = self.config.get("max_playlists", 100)
        if RICH_AVAILABLE:
            custom_max = Prompt.ask(
                f"Maximum playlists to check",
                default=str(max_playlists)
            )
            max_playlists = int(custom_max)
        
        # Select strategies
        strategies = self.select_strategies()
        
        # Perform search with progress
        try:
            if self.console and RICH_AVAILABLE:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    console=self.console
                ) as progress:
                    task = progress.add_task("Searching...", total=100)
                    
                    def update_progress(msg, percent):
                        progress.update(task, description=msg, completed=percent or 0)
                    
                    self.finder.set_progress_callback(update_progress)
                    playlists = self.finder.find_playlists(
                        video_id,
                        strategies,
                        max_playlists,
                        self.config.get("parallel_search", True)
                    )
            else:
                print("\nSearching... (this may take a while)")
                playlists = self.finder.find_playlists(
                    video_id,
                    strategies,
                    max_playlists,
                    self.config.get("parallel_search", True)
                )
            
            # Display results
            self.display_results(playlists, video_id)
            
            # Export results
            if playlists and self.ask_yes_no("Export results?"):
                self.export_results(video_id, playlists)
                
        except QuotaExceededException:
            self.error("YouTube API quota exceeded. Try again tomorrow.")
        except Exception as e:
            self.error(f"Search failed: {e}")
    
    def batch_search(self):
        """Search for multiple videos."""
        if RICH_AVAILABLE:
            input_method = Prompt.ask(
                "Input method",
                choices=["manual", "file"],
                default="manual"
            )
        else:
            print("Input method (manual/file): ")
            input_method = input().lower()
        
        video_ids = []
        
        if input_method == "file":
            filename = input("Enter filename with video IDs (one per line): ")
            try:
                with open(filename, 'r') as f:
                    video_ids = [self.extract_video_id(line.strip()) 
                                for line in f if line.strip()]
            except Exception as e:
                self.error(f"Error reading file: {e}")
                return
        else:
            print("Enter video IDs/URLs (empty line to finish):")
            while True:
                vid = input("> ").strip()
                if not vid:
                    break
                video_id = self.extract_video_id(vid)
                if video_id:
                    video_ids.append(video_id)
        
        if not video_ids:
            self.error("No valid video IDs provided")
            return
        
        # Process each video
        all_results = {}
        for i, video_id in enumerate(video_ids, 1):
            print(f"\n[{i}/{len(video_ids)}] Processing video: {video_id}")
            try:
                playlists = self.finder.find_playlists(
                    video_id,
                    max_playlists=50  # Limit per video in batch mode
                )
                all_results[video_id] = playlists
                self.success(f"Found {len(playlists)} playlists")
            except Exception as e:
                self.error(f"Failed: {e}")
                all_results[video_id] = []
        
        # Export batch results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                vid: [p.__dict__ for p in playlists]
                for vid, playlists in all_results.items()
            }, f, indent=2, default=str)
        
        self.success(f"Batch results saved to {filename}")
    
    def select_strategies(self) -> List[SearchStrategy]:
        """Let user select search strategies."""
        available = [
            ("Exact Title Search", SearchStrategy.EXACT_TITLE),
            ("Channel Playlists", SearchStrategy.CHANNEL_PLAYLISTS),
            ("Title + Channel", SearchStrategy.TITLE_AND_CHANNEL),
            ("Keyword Search", SearchStrategy.KEYWORD_SEARCH),
            ("Popular Playlists", SearchStrategy.POPULAR_PLAYLISTS)
        ]
        
        if RICH_AVAILABLE:
            self.console.print("\n[bold]Select search strategies:[/bold]")
            for i, (name, _) in enumerate(available, 1):
                self.console.print(f"  [{i}] {name}")
            
            selected = Prompt.ask(
                "Enter numbers separated by comma (or 'all')",
                default="1,2,3"
            )
        else:
            print("\nSelect search strategies:")
            for i, (name, _) in enumerate(available, 1):
                print(f"  {i}. {name}")
            selected = input("Enter numbers (comma-separated) or 'all': ")
        
        if selected.lower() == 'all':
            return [s for _, s in available]
        
        try:
            indices = [int(x.strip()) - 1 for x in selected.split(',')]
            return [available[i][1] for i in indices if 0 <= i < len(available)]
        except:
            return [SearchStrategy.EXACT_TITLE, SearchStrategy.CHANNEL_PLAYLISTS]
    
    def display_results(self, playlists: List[PlaylistInfo], video_id: str):
        """Display search results."""
        if not playlists:
            self.warning(f"No playlists found containing video {video_id}")
            return
        
        if self.console and RICH_AVAILABLE:
            # Create results table
            table = Table(title=f"Found {len(playlists)} Playlists")
            table.add_column("#", style="cyan", width=4)
            table.add_column("Title", style="green")
            table.add_column("Channel", style="yellow")
            table.add_column("Videos", style="magenta", width=8)
            table.add_column("URL", style="blue")
            
            for i, p in enumerate(playlists[:20], 1):  # Limit display
                table.add_row(
                    str(i),
                    p.title[:40] + "..." if len(p.title) > 40 else p.title,
                    p.channel_title[:20],
                    str(p.item_count),
                    p.url
                )
            
            self.console.print(table)
            
            if len(playlists) > 20:
                self.console.print(f"\n[dim]... and {len(playlists) - 20} more[/dim]")
        else:
            print(f"\nFound {len(playlists)} playlists:")
            for i, p in enumerate(playlists, 1):
                print(f"\n{i}. {p.title}")
                print(f"   Channel: {p.channel_title}")
                print(f"   Videos: {p.item_count}")
                print(f"   URL: {p.url}")
    
    def export_results(self, video_id: str, playlists: List[PlaylistInfo]):
        """Export results in various formats."""
        video_info = self.finder.api.get_video_info(video_id)
        
        formats = self.config.get("export_formats", ["json", "html"])
        output_dir = Path(self.config.get("output_dir", "results"))
        output_dir.mkdir(exist_ok=True)
        
        for fmt in formats:
            filename = output_dir / f"playlists_{video_id}_{datetime.now():%Y%m%d_%H%M%S}.{fmt}"
            self.finder.export_results(video_info, playlists, fmt, str(filename))
            self.success(f"Exported to {filename}")
    
    def show_statistics(self):
        """Display statistics."""
        if not self.finder:
            self.warning("No search performed yet")
            return
        
        stats = self.finder.get_statistics()
        
        if self.console and RICH_AVAILABLE:
            table = Table(title="Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("API Quota Used", str(stats['api_quota_used']))
            table.add_row("Playlists Checked", str(stats['playlists_checked']))
            table.add_row("Playlists Found", str(stats['playlists_found']))
            table.add_row("Cache Hit Rate", stats['cache_stats']['hit_rate'])
            table.add_row("Cache Entries", str(stats['cache_stats']['total_entries']))
            
            self.console.print(table)
        else:
            print("\n--- Statistics ---")
            for key, value in stats.items():
                if isinstance(value, dict):
                    print(f"\n{key}:")
                    for k, v in value.items():
                        print(f"  {k}: {v}")
                else:
                    print(f"{key}: {value}")
    
    def configure_settings(self):
        """Configure application settings."""
        settings = [
            ("max_playlists", "Maximum playlists to check", int),
            ("parallel_search", "Use parallel search", bool),
            ("cache_enabled", "Enable caching", bool)
        ]
        
        for key, desc, type_func in settings:
            current = self.config.get(key)
            
            if RICH_AVAILABLE:
                if type_func == bool:
                    new_value = Confirm.ask(f"{desc}", default=current)
                else:
                    new_value = Prompt.ask(f"{desc}", default=str(current))
                    if type_func == int:
                        new_value = int(new_value)
            else:
                print(f"\n{desc} (current: {current})")
                new_value = input("New value (or Enter to keep): ").strip()
                if new_value:
                    if type_func == bool:
                        new_value = new_value.lower() in ('yes', 'y', 'true', '1')
                    elif type_func == int:
                        new_value = int(new_value)
                else:
                    new_value = current
            
            if new_value != current:
                self.config.set(key, new_value)
        
        self.success("Settings updated")
    
    def clear_cache(self):
        """Clear the cache."""
        cache_dir = Path(self.config.get("cache_dir", ".cache"))
        
        if cache_dir.exists():
            if self.ask_yes_no("Clear all cache files?"):
                import shutil
                shutil.rmtree(cache_dir)
                cache_dir.mkdir()
                self.success("Cache cleared")
        else:
            self.warning("No cache found")
    
    def export_history(self):
        """Export search history."""
        # This would require implementing a history tracking feature
        self.warning("History export not yet implemented")
    
    def extract_video_id(self, input_str: str) -> Optional[str]:
        """Extract video ID from URL or return as-is if already an ID."""
        import re
        
        # YouTube URL patterns
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$'  # Direct video ID
        ]
        
        for pattern in patterns:
            match = re.search(pattern, input_str)
            if match:
                return match.group(1)
        
        return None
    
    def ask_yes_no(self, question: str) -> bool:
        """Ask a yes/no question."""
        if RICH_AVAILABLE:
            return Confirm.ask(question)
        else:
            response = input(f"{question} (y/n): ").lower()
            return response in ('y', 'yes')
    
    def success(self, message: str):
        """Display success message."""
        if self.console:
            self.console.print(f"[green]✓[/green] {message}")
        else:
            print(f"✓ {message}")
    
    def error(self, message: str):
        """Display error message."""
        if self.console:
            self.console.print(f"[red]✗[/red] {message}")
        else:
            print(f"✗ ERROR: {message}")
    
    def warning(self, message: str):
        """Display warning message."""
        if self.console:
            self.console.print(f"[yellow]![/yellow] {message}")
        else:
            print(f"! WARNING: {message}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="YouTube Playlist Finder - Find playlists containing specific videos",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "video_id",
        nargs="?",
        help="Video ID or URL to search for"
    )
    parser.add_argument(
        "--api-key",
        help="YouTube API key"
    )
    parser.add_argument(
        "--max-playlists",
        type=int,
        default=100,
        help="Maximum number of playlists to check"
    )
    parser.add_argument(
        "--output",
        help="Output file path"
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "html"],
        default="json",
        help="Output format"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching"
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=["exact_title", "channel_playlists", "title_channel", "keyword_search", "popular"],
        help="Search strategies to use"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    
    args = parser.parse_args()
    
    # Create CLI interface
    cli = CLIInterface()
    
    # Interactive mode
    if args.interactive or not args.video_id:
        cli.interactive_mode()
        return
    
    # Command-line mode
    config = cli.config
    
    # Override config with command-line arguments
    if args.api_key:
        api_key = args.api_key
    else:
        api_key = config.get("api_key")
    
    if not api_key:
        cli.error("No API key provided. Use --api-key or set in config.yaml")
        sys.exit(1)
    
    # Extract video ID
    video_id = cli.extract_video_id(args.video_id)
    if not video_id:
        cli.error("Invalid video ID or URL")
        sys.exit(1)
    
    # Create finder
    cache_dir = None if args.no_cache else config.get("cache_dir", ".cache")
    finder = PlaylistFinder(api_key, cache_dir)
    
    # Map strategy strings to enums
    strategy_map = {
        "exact_title": SearchStrategy.EXACT_TITLE,
        "channel_playlists": SearchStrategy.CHANNEL_PLAYLISTS,
        "title_channel": SearchStrategy.TITLE_AND_CHANNEL,
        "keyword_search": SearchStrategy.KEYWORD_SEARCH,
        "popular": SearchStrategy.POPULAR_PLAYLISTS
    }
    
    strategies = None
    if args.strategies:
        strategies = [strategy_map[s] for s in args.strategies]
    
    try:
        # Perform search
        print(f"Searching for playlists containing video: {video_id}")
        playlists = finder.find_playlists(
            video_id,
            strategies,
            args.max_playlists
        )
        
        # Display results
        cli.display_results(playlists, video_id)
        
        # Export if requested
        if args.output and playlists:
            video_info = finder.api.get_video_info(video_id)
            output_file = finder.export_results(
                video_info,
                playlists,
                args.format,
                args.output
            )
            cli.success(f"Results exported to {output_file}")
            
    except Exception as e:
        cli.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
