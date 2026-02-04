"""
Instagram Story Downloader - VPS Version
A Flask-based web application for downloading Instagram stories and highlights.
"""

import json
import os
import time
import random
import hashlib
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import requests

# Optional rate limiting
try:
    from flask_limiter import Limiter  # type: ignore
    from flask_limiter.util import get_remote_address  # type: ignore
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False
    Limiter = None  # type: ignore
    get_remote_address = None
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse, unquote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== Flask App Setup ==============
app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Rate limiting (optional)
if LIMITER_AVAILABLE and Limiter is not None:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["100 per hour", "20 per minute"]
    )
else:
    limiter = None
    logger.warning("flask-limiter not installed. Rate limiting disabled.")

# ============== Configuration ==============
# Import config from config.py (which has the actual credentials)
from config import Config as AppConfig

class Config:
    """Application configuration - wrapper around config.py settings."""
    
    # Instagram API
    API_DOMAIN = AppConfig.IG_API_DOMAIN
    
    # Session credentials
    SESSION_ID = AppConfig.IG_SESSION_ID
    DS_USER_ID = AppConfig.IG_DS_USER_ID
    CSRF_TOKEN = AppConfig.IG_CSRF_TOKEN
    MID = AppConfig.IG_MID
    
    # Optional cookies
    DATR = AppConfig.IG_DATR
    DID = AppConfig.IG_DID
    RUR = AppConfig.IG_RUR
    
    # Server settings
    HOST = AppConfig.HOST
    PORT = AppConfig.PORT
    DEBUG = AppConfig.DEBUG
    
    # Security
    SECRET_KEY = AppConfig.SECRET_KEY
    
    # Allowed domains for download proxy (security)
    ALLOWED_DOWNLOAD_DOMAINS = AppConfig.ALLOWED_DOWNLOAD_DOMAINS
    
    @classmethod
    def validate(cls) -> bool:
        """Check if required credentials are set."""
        if not cls.SESSION_ID or not cls.DS_USER_ID:
            logger.warning("Instagram credentials not set! Set IG_SESSION_ID and IG_DS_USER_ID environment variables.")
            return False
        return True


# Instagram capabilities for API requests
SUPPORTED_CAPABILITIES = [
    {"name": "SUPPORTED_SDK_VERSIONS", "value": "119.0,120.0,121.0,122.0,123.0,124.0,125.0,126.0,127.0,128.0,129.0,130.0,131.0,132.0,133.0,134.0,135.0,136.0,137.0,138.0,139.0,140.0,141.0,142.0"},
    {"name": "FACE_TRACKER_VERSION", "value": "14"},
    {"name": "COMPRESSION", "value": "ETC2_COMPRESSION"},
    {"name": "gyroscope", "value": "gyroscope_enabled"},
]


# ============== Instagram Client ==============
class InstagramClient:
    """Client for interacting with Instagram's private API."""
    
    def __init__(self):
        self.session = requests.Session()
        self._setup_session()
        
        # Device identifiers
        self.uuid = str(uuid.uuid4())
        self.phone_id = str(uuid.uuid4())
        self.android_device_id = "android-" + hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
    
    def _setup_session(self):
        """Configure the requests session with retry logic and cookies."""
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Log cookie status for debugging
        logger.info("=" * 50)
        logger.info("Setting up Instagram session cookies:")
        logger.info(f"  SESSION_ID: {'SET (' + Config.SESSION_ID[:20] + '...)' if Config.SESSION_ID else 'NOT SET'}")
        logger.info(f"  DS_USER_ID: {Config.DS_USER_ID if Config.DS_USER_ID else 'NOT SET'}")
        logger.info(f"  CSRF_TOKEN: {'SET' if Config.CSRF_TOKEN else 'NOT SET'}")
        logger.info(f"  MID: {'SET' if Config.MID else 'NOT SET'}")
        logger.info("=" * 50)
        
        # Set cookies
        if Config.SESSION_ID:
            self.session.cookies.set("sessionid", Config.SESSION_ID, domain=".instagram.com")
        if Config.DS_USER_ID:
            self.session.cookies.set("ds_user_id", Config.DS_USER_ID, domain=".instagram.com")
        if Config.CSRF_TOKEN:
            self.session.cookies.set("csrftoken", Config.CSRF_TOKEN, domain=".instagram.com")
        if Config.MID:
            self.session.cookies.set("mid", Config.MID, domain=".instagram.com")
        if Config.DATR:
            self.session.cookies.set("datr", Config.DATR, domain=".instagram.com")
        if Config.DID:
            self.session.cookies.set("ig_did", Config.DID, domain=".instagram.com")
        if Config.RUR:
            self.session.cookies.set("rur", Config.RUR, domain=".instagram.com")
    
    def _get_headers(self) -> dict:
        """Get headers for Instagram API requests."""
        return {
            # Use Instagram Android app User-Agent (more permissive)
            "User-Agent": "Mozilla/5.0 (Linux; Android 9; GM1903 Build/PKQ1.190110.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/75.0.3770.143 Mobile Safari/537.36 Instagram 103.1.0.15.119 Android (28/9; 420dpi; 1080x2260; OnePlus; GM1903; OnePlus7; qcom; sv_SE; 164094539)",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "X-CSRFToken": Config.CSRF_TOKEN,
            "X-IG-App-ID": "936619743392459",
            "X-IG-WWW-Claim": "0",
            "X-Requested-With": "XMLHttpRequest",
            "X-ASBD-ID": "129477",
            "Origin": "https://www.instagram.com",
            "Referer": "https://www.instagram.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Connection": "keep-alive",
        }
    
    def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a request to Instagram's API."""
        url = f"https://{Config.API_DOMAIN}/api/v1/{endpoint}"
        headers = self._get_headers()
        
        # Random delay to avoid rate limiting
        time.sleep(random.uniform(0.5, 1.5))
        
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=30)
            
            logger.debug(f"API request to {endpoint}: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                try:
                    data = response.json()
                    logger.error(f"API 400 error: {data}")
                    raise InstagramError(data.get("message", "Bad request"), 400)
                except json.JSONDecodeError:
                    logger.error(f"API 400 error (non-JSON): {response.text[:200]}")
                    raise InstagramError(f"Bad request: {response.text[:200]}", 400)
            elif response.status_code == 401:
                logger.error("API 401 - Session expired")
                raise InstagramError("Session expired - please update session credentials", 401)
            elif response.status_code == 404:
                logger.warning(f"API 404 for {endpoint}")
                raise InstagramError("Not found", 404)
            elif response.status_code == 429:
                logger.warning("API 429 - Rate limited")
                raise InstagramError("Rate limited - please wait before trying again", 429)
            else:
                logger.error(f"API error {response.status_code}: {response.text[:200]}")
                raise InstagramError(f"Request failed with status {response.status_code}", response.status_code)
                
        except requests.exceptions.Timeout:
            raise InstagramError("Request timed out", 504)
        except requests.exceptions.ConnectionError:
            raise InstagramError("Connection error", 503)
        except requests.exceptions.RequestException as e:
            raise InstagramError(f"Request failed: {str(e)}", 500)
    
    def get_user_id(self, username: str) -> str:
        """Get user ID from username using multiple methods."""
        username = username.lower().strip().lstrip("@")
        
        # Method 1: Try scraping the profile page first (most reliable per Next.js app)
        try:
            user_id = self._get_user_id_from_page(username)
            if user_id:
                logger.info(f"Found user {username} via page scraping")
                return user_id
        except Exception as e:
            logger.warning(f"Page scraping failed for {username}: {e}")
        
        # Method 2: Try GraphQL search API (from Next.js app - very reliable)
        try:
            user_id = self._get_user_id_graphql(username)
            if user_id:
                logger.info(f"Found user {username} via GraphQL API")
                return user_id
        except Exception as e:
            logger.warning(f"GraphQL API failed for {username}: {e}")
        
        # Method 3: Try web_profile_info API
        try:
            user_id = self._get_user_id_web_profile(username)
            if user_id:
                logger.info(f"Found user {username} via web_profile_info API")
                return user_id
        except Exception as e:
            logger.warning(f"web_profile_info API failed for {username}: {e}")
        
        # Method 4: Try the search API
        try:
            user_id = self._get_user_id_search(username)
            if user_id:
                logger.info(f"Found user {username} via search API")
                return user_id
        except Exception as e:
            logger.warning(f"Search API failed for {username}: {e}")
        
        # Method 5: Try the mobile API (often blocked)
        try:
            result = self._request(f"users/{username}/usernameinfo/")
            if result.get("user"):
                logger.info(f"Found user {username} via mobile API")
                return str(result["user"]["pk"])
        except InstagramError as e:
            logger.warning(f"Mobile API failed for {username}: {e.message}")
        
        raise InstagramError(f"User '{username}' not found. Please check the username.", 404)
    
    def _get_user_id_graphql(self, username: str) -> Optional[str]:
        """Get user ID using Instagram's GraphQL search API (from Next.js app)."""
        import urllib.parse
        
        url = "https://www.instagram.com/graphql/query"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-IG-App-ID": "936619743392459",
            "X-CSRFToken": Config.CSRF_TOKEN,
            "X-FB-Friendly-Name": "PolarisSearchBoxRefetchableQuery",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.instagram.com",
            "Referer": "https://www.instagram.com/",
        }
        
        data = {
            "av": "17841461911219001",
            "__d": "www",
            "variables": json.dumps({
                "data": {
                    "context": "blended",
                    "include_reel": "true",
                    "query": username.strip(),
                    "rank_token": "",
                    "search_surface": "web_top_search",
                },
                "hasQuery": True,
            }),
            "doc_id": "9153895011291216",
        }
        
        response = self.session.post(url, headers=headers, data=data, timeout=30)
        logger.debug(f"GraphQL API response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            users = result.get("data", {}).get("xdt_api__v1__fbsearch__topsearch_connection", {}).get("users", [])
            for user_data in users:
                user = user_data.get("user", {})
                if user.get("username", "").lower() == username.lower():
                    return str(user["id"])
        
        return None
    
    def _get_user_id_web_profile(self, username: str) -> Optional[str]:
        """Get user ID using Instagram's web_profile_info API."""
        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 9; GM1903 Build/PKQ1.190110.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/75.0.3770.143 Mobile Safari/537.36 Instagram 103.1.0.15.119 Android (28/9; 420dpi; 1080x2260; OnePlus; GM1903; OnePlus7; qcom; sv_SE; 164094539)",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "X-CSRFToken": Config.CSRF_TOKEN,
            "X-IG-App-ID": "936619743392459",
            "X-ASBD-ID": "129477",
            "X-IG-WWW-Claim": "0",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.instagram.com/{username}/",
            "Origin": "https://www.instagram.com",
        }
        
        response = self.session.get(url, headers=headers, timeout=30)
        logger.debug(f"web_profile_info response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            user = data.get("data", {}).get("user")
            if user:
                return str(user["id"])
        return None
    
    def _get_user_id_from_page(self, username: str) -> Optional[str]:
        """Get user ID by scraping the profile page for embedded data."""
        import re
        
        url = f"https://www.instagram.com/{username}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        response = self.session.get(url, headers=headers, timeout=30)
        logger.debug(f"Profile page response: {response.status_code}")
        
        if response.status_code == 200:
            # Try to find user ID in the page content
            # Pattern 1: "profilePage_<user_id>"
            match = re.search(r'"profilePage_(\d+)"', response.text)
            if match:
                return match.group(1)
            
            # Pattern 2: "user_id":"<user_id>"
            match = re.search(r'"user_id"\s*:\s*"(\d+)"', response.text)
            if match:
                return match.group(1)
            
            # Pattern 3: {"id":"<user_id>"
            match = re.search(r'\{"id"\s*:\s*"(\d+)"[^}]*"username"\s*:\s*"' + re.escape(username) + '"', response.text)
            if match:
                return match.group(1)
                
            # Pattern 4: data-id or similar attributes
            match = re.search(r'data-(?:user-)?id="(\d+)"', response.text)
            if match:
                return match.group(1)
        
        return None
    
    def _get_user_id_search(self, username: str) -> Optional[str]:
        """Get user ID using Instagram's search API."""
        url = f"https://www.instagram.com/web/search/topsearch/?query={username}&context=blended&rank_token=0.3953592318270893&count=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 9; GM1903 Build/PKQ1.190110.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/75.0.3770.143 Mobile Safari/537.36 Instagram 103.1.0.15.119 Android (28/9; 420dpi; 1080x2260; OnePlus; GM1903; OnePlus7; qcom; sv_SE; 164094539)",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "X-CSRFToken": Config.CSRF_TOKEN,
            "X-IG-App-ID": "936619743392459",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/",
        }
        
        response = self.session.get(url, headers=headers, timeout=30)
        logger.debug(f"Search API response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            users = data.get("users", [])
            for user_data in users:
                user = user_data.get("user", {})
                if user.get("username", "").lower() == username.lower():
                    return str(user["pk"])
        
        return None
    
    def get_user_info(self, user_id: str) -> dict:
        """Get user information."""
        try:
            result = self._request(f"users/{user_id}/info/")
            return result.get("user", {})
        except InstagramError as e:
            logger.warning(f"Failed to get user info for {user_id}: {e.message}")
            return {}
    
    def get_user_stories(self, user_id: str) -> List[dict]:
        """Get stories for a user."""
        params = {
            "supported_capabilities_new": json.dumps(SUPPORTED_CAPABILITIES)
        }
        
        result = self._request(f"feed/user/{user_id}/story/", params=params)
        reel = result.get("reel") or {}
        items = reel.get("items", [])
        
        stories = []
        for item in items:
            story = self._extract_story(item)
            if story:
                stories.append(story)
        
        return stories
    
    def get_highlight_stories(self, highlight_id: str) -> tuple:
        """Get stories from a highlight."""
        params = {
            "supported_capabilities_new": json.dumps(SUPPORTED_CAPABILITIES)
        }
        
        result = self._request("feed/reels_media/", params={"user_ids": f"highlight:{highlight_id}"})
        
        reels = result.get("reels", {})
        highlight_key = f"highlight:{highlight_id}"
        
        if highlight_key not in reels:
            raise InstagramError("Highlight not found", 404)
        
        reel = reels[highlight_key]
        items = reel.get("items", [])
        
        # Extract highlight info
        highlight_info = {
            "id": highlight_id,
            "title": reel.get("title", "Highlight"),
            "cover_url": reel.get("cover_media", {}).get("cropped_image_version", {}).get("url", ""),
            "user": {
                "pk": str(reel.get("user", {}).get("pk", "")),
                "username": reel.get("user", {}).get("username", ""),
                "full_name": reel.get("user", {}).get("full_name", ""),
                "profile_pic_url": reel.get("user", {}).get("profile_pic_url", ""),
            }
        }
        
        stories = []
        for item in items:
            story = self._extract_story(item)
            if story:
                stories.append(story)
        
        return highlight_info, stories
    
    def _extract_story(self, data: dict) -> Optional[dict]:
        """Extract story data from API response."""
        try:
            story = {
                "pk": str(data.get("pk", "")),
                "id": data.get("id", ""),
                "code": data.get("code", ""),
                "taken_at": data.get("taken_at", 0),
                "media_type": data.get("media_type", 1),
                "user": {
                    "pk": str(data.get("user", {}).get("pk", "")),
                    "username": data.get("user", {}).get("username", ""),
                    "full_name": data.get("user", {}).get("full_name", ""),
                    "profile_pic_url": data.get("user", {}).get("profile_pic_url", ""),
                },
                "thumbnail_url": None,
                "video_url": None,
                "video_duration": data.get("video_duration", 0),
            }
            
            # Get best quality thumbnail
            if "image_versions2" in data:
                candidates = data["image_versions2"].get("candidates", [])
                if candidates:
                    best = max(candidates, key=lambda x: x.get("width", 0) * x.get("height", 0))
                    story["thumbnail_url"] = best.get("url")
            
            # Get best quality video
            if data.get("media_type") == 2 and "video_versions" in data:
                versions = data["video_versions"]
                if versions:
                    best = max(versions, key=lambda x: x.get("width", 0) * x.get("height", 0))
                    story["video_url"] = best.get("url")
            
            return story
        except Exception as e:
            logger.error(f"Error extracting story: {e}")
            return None


class InstagramError(Exception):
    """Custom exception for Instagram API errors."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ============== Global Client ==============
_client: Optional[InstagramClient] = None


def get_client() -> InstagramClient:
    """Get or create Instagram client instance."""
    global _client
    if _client is None:
        _client = InstagramClient()
    return _client


def reset_client():
    """Reset the client (useful when credentials change)."""
    global _client
    _client = None


# ============== Helper Functions ==============
def parse_instagram_input(user_input: str) -> tuple:
    """
    Parse user input to extract username or highlight ID.
    Returns: (type, value) where type is 'username' or 'highlight'
    """
    user_input = user_input.strip()
    
    # Check if it's a URL
    if "instagram.com" in user_input:
        parsed = urlparse(user_input)
        path_parts = [p for p in parsed.path.split("/") if p]
        
        # Highlight URL
        if "highlights" in path_parts:
            idx = path_parts.index("highlights")
            if len(path_parts) > idx + 1:
                return ("highlight", path_parts[idx + 1])
            raise ValueError("Invalid highlight URL")
        
        # Stories URL
        if "stories" in path_parts:
            idx = path_parts.index("stories")
            if len(path_parts) > idx + 1:
                return ("username", path_parts[idx + 1])
            raise ValueError("Invalid stories URL")
        
        # Profile URL
        if path_parts:
            return ("username", path_parts[0])
        
        raise ValueError("Could not parse Instagram URL")
    
    # Plain username
    return ("username", user_input.lstrip("@").lower())


def is_allowed_download_url(url: str) -> bool:
    """Check if URL is from an allowed domain (security measure)."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return any(allowed in domain for allowed in Config.ALLOWED_DOWNLOAD_DOMAINS)
    except:
        return False


# ============== API Routes ==============
@app.route('/')
def index():
    """Serve the main page."""
    return send_from_directory('static', 'index.html')


@app.route('/api/stories', methods=['GET', 'POST'])
def get_stories():
    """Fetch stories for a username or highlight."""
    try:
        # Get username from query params or JSON body
        if request.method == 'POST':
            data = request.get_json() or {}
            username = data.get('username', '')
        else:
            username = request.args.get('username', '')
        
        if not username:
            return jsonify({"success": False, "error": "Username parameter is required"}), 400
        
        # Parse input
        try:
            input_type, value = parse_instagram_input(username)
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        
        client = get_client()
        
        # Handle highlight request
        if input_type == "highlight":
            highlight_info, stories = client.get_highlight_stories(value)
            return jsonify({
                "success": True,
                "type": "highlight",
                "highlight": {
                    "id": value,
                    "title": highlight_info.get("title", "Highlight"),
                    "cover_url": highlight_info.get("cover_url", ""),
                },
                "user": highlight_info.get("user", {}),
                "stories": stories,
                "count": len(stories)
            })
        
        # Handle username request
        username = value
        
        # Get user ID
        try:
            user_id = client.get_user_id(username)
        except InstagramError as e:
            if e.status_code == 404:
                return jsonify({"success": False, "error": f"User '{username}' not found"}), 404
            raise
        
        # Get user info
        try:
            user_info = client.get_user_info(user_id)
        except:
            user_info = {}
        
        # Check if private
        if user_info.get("is_private"):
            return jsonify({
                "success": True,
                "username": username,
                "user": {
                    "pk": str(user_id),
                    "username": user_info.get("username", username),
                    "full_name": user_info.get("full_name", ""),
                    "profile_pic_url": user_info.get("profile_pic_url", ""),
                    "is_private": True,
                },
                "stories": [],
                "message": "This account is private"
            })
        
        # Get stories
        stories = client.get_user_stories(user_id)
        
        return jsonify({
            "success": True,
            "username": username,
            "user": {
                "pk": str(user_id),
                "username": user_info.get("username", username),
                "full_name": user_info.get("full_name", ""),
                "profile_pic_url": user_info.get("profile_pic_url", ""),
                "is_private": user_info.get("is_private", False),
            },
            "stories": stories,
            "count": len(stories)
        })
        
    except InstagramError as e:
        logger.error(f"Instagram error: {e.message}")
        return jsonify({"success": False, "error": e.message}), e.status_code
    except Exception as e:
        logger.exception("Unexpected error in get_stories")
        return jsonify({"success": False, "error": "An unexpected error occurred"}), 500


@app.route('/api/download', methods=['GET'])
def download_media():
    """Proxy download for media files to avoid CORS issues."""
    url = request.args.get('url', '')
    filename = request.args.get('filename', 'instagram_story')
    media_type = request.args.get('type', 'image')
    
    if not url:
        return jsonify({"success": False, "error": "URL parameter is required"}), 400
    
    # Security: validate URL domain
    if not is_allowed_download_url(url):
        return jsonify({"success": False, "error": "Invalid download URL"}), 400
    
    try:
        # Stream download from Instagram
        response = requests.get(
            url,
            stream=True,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        response.raise_for_status()
        
        # Determine content type and extension
        if media_type == "video":
            content_type = "video/mp4"
            ext = "mp4"
        else:
            content_type = "image/jpeg"
            ext = "jpg"
        
        # Create streaming response
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                yield chunk
        
        headers = {
            "Content-Type": content_type,
            "Content-Disposition": f'attachment; filename="{filename}.{ext}"',
            "Content-Length": response.headers.get("Content-Length", ""),
        }
        
        return Response(
            stream_with_context(generate()),
            headers=headers,
            content_type=content_type
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Download error: {e}")
        return jsonify({"success": False, "error": "Failed to download media"}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "credentials_configured": Config.validate()
    })


@app.route('/api/debug', methods=['GET'])
def debug_session():
    """Debug endpoint to test Instagram session."""
    client = get_client()
    
    debug_info = {
        "credentials": {
            "session_id_set": bool(Config.SESSION_ID),
            "session_id_preview": Config.SESSION_ID[:20] + "..." if Config.SESSION_ID else None,
            "ds_user_id": Config.DS_USER_ID,
            "csrf_token_set": bool(Config.CSRF_TOKEN),
            "mid_set": bool(Config.MID),
        },
        "api_domain": Config.API_DOMAIN,
        "cookies_in_session": list(client.session.cookies.keys()),
    }
    
    # Test API by checking own user info
    try:
        if Config.DS_USER_ID:
            result = client._request(f"users/{Config.DS_USER_ID}/info/")
            debug_info["session_test"] = {
                "status": "SUCCESS",
                "logged_in_as": result.get("user", {}).get("username", "unknown"),
                "full_name": result.get("user", {}).get("full_name", ""),
            }
        else:
            debug_info["session_test"] = {"status": "NO_USER_ID", "message": "DS_USER_ID not set"}
    except InstagramError as e:
        debug_info["session_test"] = {
            "status": "FAILED",
            "error": e.message,
            "status_code": e.status_code
        }
    except Exception as e:
        debug_info["session_test"] = {
            "status": "ERROR",
            "error": str(e)
        }
    
    # Test username lookup
    test_username = request.args.get('test_user', 'instagram')
    try:
        user_id = client.get_user_id(test_username)
        debug_info["username_lookup_test"] = {
            "status": "SUCCESS",
            "username": test_username,
            "user_id": user_id
        }
    except InstagramError as e:
        debug_info["username_lookup_test"] = {
            "status": "FAILED",
            "username": test_username,
            "error": e.message,
            "status_code": e.status_code
        }
    
    return jsonify(debug_info)


@app.route('/api/reset', methods=['POST'])
def reset_session():
    """Reset the Instagram client (admin endpoint)."""
    # In production, add authentication here
    reset_client()
    return jsonify({"success": True, "message": "Client reset successfully"})


# ============== Error Handlers ==============
@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Not found"}), 404


@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({"success": False, "error": "Rate limit exceeded. Please wait before trying again."}), 429


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"success": False, "error": "Internal server error"}), 500


# ============== Main ==============
if __name__ == '__main__':
    # Validate configuration
    if not Config.validate():
        logger.warning("=" * 60)
        logger.warning("WARNING: Instagram credentials not configured!")
        logger.warning("Set environment variables: IG_SESSION_ID, IG_DS_USER_ID")
        logger.warning("=" * 60)
    
    logger.info(f"Starting server on {Config.HOST}:{Config.PORT}")
    logger.info(f"Debug mode: {Config.DEBUG}")
    
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
