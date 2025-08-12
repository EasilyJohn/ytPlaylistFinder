#!/usr/bin/env python3
"""
setup.py - Setup and Quick Start Script for YouTube Playlist Finder
This script helps with initial setup, dependency installation, and configuration.
"""

import os
import sys
import subprocess
import platform
import json
import yaml
from pathlib import Path


class Setup:
    """Setup helper for YouTube Playlist Finder."""
    
    def __init__(self):
        self.platform = platform.system()
        self.python_version = sys.version_info
        self.project_root = Path(__file__).parent
        
    def check_python_version(self):
        """Check if Python version is 3.8+."""
        print("🐍 Checking Python version...")
        if self.python_version < (3, 8):
            print(f"❌ Python 3.8+ required. You have {sys.version}")
            return False
        print(f"✅ Python {sys.version} detected")
        return True
    
    def install_dependencies(self):
        """Install required packages."""
        print("\n📦 Installing dependencies...")
        
        # Check if pip is available
        try:
            subprocess.run([sys.executable, "-m", "pip", "--version"], 
                         check=True, capture_output=True)
        except:
            print("❌ pip not found. Please install pip first.")
            return False
        
        # Upgrade pip
        print("Upgrading pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        
        # Install requirements
        requirements_file = self.project_root / "requirements.txt"
        if requirements_file.exists():
            print("Installing packages from requirements.txt...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✅ All dependencies installed successfully")
                return True
            else:
                print(f"❌ Error installing dependencies:\n{result.stderr}")
                return False
        else:
            print("❌ requirements.txt not found")
            return False
    
    def check_tkinter(self):
        """Check if tkinter is available for GUI."""
        print("\n🖼️ Checking tkinter for GUI support...")
        try:
            import tkinter
            print("✅ tkinter is available")
            return True
        except ImportError:
            print("⚠️ tkinter not found. GUI will not work.")
            print("To install tkinter:")
            if self.platform == "Linux":
                print("  Ubuntu/Debian: sudo apt-get install python3-tk")
                print("  Fedora: sudo dnf install python3-tkinter")
            elif self.platform == "Darwin":
                print("  macOS: tkinter should be included with Python")
            elif self.platform == "Windows":
                print("  Windows: tkinter should be included with Python")
            return False
    
    def setup_api_key(self):
        """Help user set up YouTube API key."""
        print("\n🔑 Setting up YouTube API key...")
        print("\nTo use this tool, you need a YouTube Data API v3 key.")
        print("Get one here: https://console.cloud.google.com/apis/credentials")
        print("\nSteps:")
        print("1. Create a project in Google Cloud Console")
        print("2. Enable YouTube Data API v3")
        print("3. Create credentials (API Key)")
        print("4. Copy the API key")
        
        api_key = input("\nEnter your YouTube API key (or press Enter to skip): ").strip()
        
        if api_key:
            # Save to config.yaml
            config_file = self.project_root / "config.yaml"
            config = {
                "api_key": api_key,
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
                    "keyword_search"
                ]
            }
            
            with open(config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            print(f"✅ API key saved to {config_file}")
            
            # Also save for GUI
            gui_config = self.project_root / "gui_config.json"
            gui_config_data = {
                "api_key": api_key,
                "max_playlists": 100,
                "cache_enabled": True,
                "parallel_search": True
            }
            
            with open(gui_config, 'w') as f:
                json.dump(gui_config_data, f, indent=2)
            
            print(f"✅ GUI config saved to {gui_config}")
            return True
        else:
            print("⚠️ No API key provided. You'll need to set it later.")
            return False
    
    def create_directories(self):
        """Create necessary directories."""
        print("\n📁 Creating project directories...")
        
        dirs = [
            self.project_root / ".cache",
            self.project_root / "results",
            self.project_root / "logs"
        ]
        
        for dir_path in dirs:
            dir_path.mkdir(exist_ok=True)
            print(f"✅ Created {dir_path}")
    
    def test_installation(self):
        """Test if everything is working."""
        print("\n🧪 Testing installation...")
        
        # Test core module
        try:
            from youtube_playlist_core import PlaylistFinder, SearchStrategy
            print("✅ Core module loaded successfully")
        except ImportError as e:
            print(f"❌ Error loading core module: {e}")
            return False
        
        # Test CLI
        try:
            result = subprocess.run(
                [sys.executable, str(self.project_root / "youtube_playlist_cli.py"), "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print("✅ CLI interface working")
            else:
                print("⚠️ CLI interface has issues")
        except Exception as e:
            print(f"⚠️ CLI test failed: {e}")
        
        # Test GUI availability
        try:
            import tkinter
            print("✅ GUI interface available")
        except ImportError:
            print("⚠️ GUI interface not available (tkinter missing)")
        
        return True
    
    def create_shortcuts(self):
        """Create convenient shortcuts/scripts."""
        print("\n🚀 Creating shortcuts...")
        
        if self.platform == "Windows":
            # Create batch files for Windows
            cli_bat = self.project_root / "start_cli.bat"
            with open(cli_bat, 'w') as f:
                f.write(f'@echo off\npython "{self.project_root / "youtube_playlist_cli.py"}" --interactive\npause')
            print(f"✅ Created {cli_bat}")
            
            gui_bat = self.project_root / "start_gui.bat"
            with open(gui_bat, 'w') as f:
                f.write(f'@echo off\npython "{self.project_root / "youtube_playlist_gui.py"}"\npause')
            print(f"✅ Created {gui_bat}")
            
        else:
            # Create shell scripts for Unix-like systems
            cli_sh = self.project_root / "start_cli.sh"
            with open(cli_sh, 'w') as f:
                f.write(f'#!/bin/bash\npython3 "{self.project_root / "youtube_playlist_cli.py"}" --interactive\n')
            cli_sh.chmod(0o755)
            print(f"✅ Created {cli_sh}")
            
            gui_sh = self.project_root / "start_gui.sh"
            with open(gui_sh, 'w') as f:
                f.write(f'#!/bin/bash\npython3 "{self.project_root / "youtube_playlist_gui.py"}"\n')
            gui_sh.chmod(0o755)
            print(f"✅ Created {gui_sh}")
    
    def print_next_steps(self):
        """Print next steps for the user."""
        print("\n" + "="*50)
        print("🎉 Setup Complete!")
        print("="*50)
        
        print("\n📚 Quick Start Guide:")
        print("\n1. GUI Interface (Recommended):")
        if self.platform == "Windows":
            print("   Double-click 'start_gui.bat' or run:")
            print(f"   python youtube_playlist_gui.py")
        else:
            print("   Run: ./start_gui.sh")
            print(f"   Or: python3 youtube_playlist_gui.py")
        
        print("\n2. CLI Interface:")
        if self.platform == "Windows":
            print("   Double-click 'start_cli.bat' or run:")
            print(f"   python youtube_playlist_cli.py --interactive")
        else:
            print("   Run: ./start_cli.sh")
            print(f"   Or: python3 youtube_playlist_cli.py --interactive")
        
        print("\n3. Direct Search (CLI):")
        print('   python youtube_playlist_cli.py "VIDEO_ID_OR_URL"')
        
        print("\n📖 Documentation:")
        print("   See README.md for detailed usage instructions")
        
        print("\n⚠️ Important:")
        print("   - Make sure you have set your YouTube API key")
        print("   - API has daily quotas (10,000 units)")
        print("   - Use caching to minimize API calls")
        
        print("\n💡 Tips:")
        print("   - Start with the GUI for easier use")
        print("   - Enable caching to save API quota")
        print("   - Try different search strategies for better results")
    
    def run(self):
        """Run the complete setup process."""
        print("="*50)
        print("YouTube Playlist Finder - Setup Script")
        print("="*50)
        
        # Check Python version
        if not self.check_python_version():
            return False
        
        # Install dependencies
        if not self.install_dependencies():
            response = input("\n⚠️ Continue without all dependencies? (y/n): ")
            if response.lower() != 'y':
                return False
        
        # Check tkinter
        self.check_tkinter()
        
        # Create directories
        self.create_directories()
        
        # Setup API key
        self.setup_api_key()
        
        # Test installation
        self.test_installation()
        
        # Create shortcuts
        self.create_shortcuts()
        
        # Print next steps
        self.print_next_steps()
        
        return True


def main():
    """Main entry point."""
    setup = Setup()
    
    try:
        success = setup.run()
        if success:
            print("\n✅ Setup completed successfully!")
        else:
            print("\n❌ Setup encountered issues. Please check the errors above.")
    except KeyboardInterrupt:
        print("\n\n⚠️ Setup interrupted by user")
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
