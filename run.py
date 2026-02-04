#!/usr/bin/env python3
"""
Run script for Instagram Story Downloader.
This is the main entry point for running the application.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, Config

if __name__ == '__main__':
    # Print startup info
    print("\n" + "=" * 60)
    print("📸 Instagram Story Downloader - VPS Edition")
    print("=" * 60)
    
    # Validate configuration
    if not Config.validate():
        print("\n⚠️  WARNING: Instagram credentials not configured!")
        print("Set the following environment variables:")
        print("  - IG_SESSION_ID")
        print("  - IG_DS_USER_ID")
        print("  - IG_CSRF_TOKEN")
        print("\nSee .env.example for instructions on getting these values.")
        print("=" * 60 + "\n")
    else:
        print("✅ Instagram credentials configured")
    
    print(f"\n🚀 Starting server on http://{Config.HOST}:{Config.PORT}")
    print(f"📝 Debug mode: {Config.DEBUG}")
    print("Press Ctrl+C to stop\n")
    
    # Run the Flask app
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
