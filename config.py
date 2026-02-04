"""
Configuration management for Instagram Story Downloader.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:
    def load_dotenv(path=None):  # type: ignore
        pass  # dotenv not installed, skip

# Load .env file if it exists
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)


class Config:
    """Base configuration."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Server settings
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    # Instagram API
    IG_API_DOMAIN = os.environ.get('IG_API_DOMAIN', 'i.instagram.com')
    
    # Instagram credentials (REQUIRED)
    IG_SESSION_ID = os.environ.get(
        'IG_SESSION_ID',
        '80410807926%3AJqTbrkubzZAGXq%3A27%3AAYjgTmevDqV0b62fRe8BcRzeDHb_D31x_nlzNvX1RA'
    )
    IG_DS_USER_ID = os.environ.get('IG_DS_USER_ID', '80410807926')
    IG_CSRF_TOKEN = os.environ.get('IG_CSRF_TOKEN', 'hCMHXBafi44eyeWhQ2H6YFQBU2QOwE7w')
    
    # Instagram credentials (OPTIONAL)
    IG_MID = os.environ.get('IG_MID', 'aWFBJAALAAHRt-UXxVOknqgoxntT')
    IG_DATR = os.environ.get('IG_DATR', 'est5aZkSWaly1AZy49xETXA0')
    IG_DID = os.environ.get('IG_DID', '6A87B787-6286-49C1-92F9-B33A43F43A19')
    IG_RUR = os.environ.get('IG_RUR', '"LDC\\05480410807926\\0541801772719:01fe598b5ab7ea32d63c24dce75bc38a9fe52719df511b1b8bc59befa02a1af616d3308a"')
    
    # Rate limiting
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '100 per hour')
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    
    # Security - allowed domains for download proxy
    ALLOWED_DOWNLOAD_DOMAINS = [
        'instagram.com',
        'cdninstagram.com', 
        'fbcdn.net',
        'instagram.fcdn.net'
    ]
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if required Instagram credentials are set."""
        return bool(cls.IG_SESSION_ID and cls.IG_DS_USER_ID)
    
    @classmethod
    def print_config(cls):
        """Print current configuration (for debugging)."""
        print("=" * 50)
        print("Current Configuration:")
        print("=" * 50)
        print(f"  HOST: {cls.HOST}")
        print(f"  PORT: {cls.PORT}")
        print(f"  DEBUG: {cls.DEBUG}")
        print(f"  IG_SESSION_ID: {'***' + cls.IG_SESSION_ID[-10:] if cls.IG_SESSION_ID else 'NOT SET'}")
        print(f"  IG_DS_USER_ID: {cls.IG_DS_USER_ID or 'NOT SET'}")
        print(f"  IG_CSRF_TOKEN: {'SET' if cls.IG_CSRF_TOKEN else 'NOT SET'}")
        print(f"  Credentials configured: {cls.is_configured()}")
        print("=" * 50)


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True


# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env: Optional[str] = None) -> Config:
    """Get configuration based on environment."""
    if env is None:
        env = os.environ.get('FLASK_ENV', 'default')
    return config_map.get(env, DevelopmentConfig)
