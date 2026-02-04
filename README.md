# 📸 Instagram Story Downloader - VPS Edition

A self-hosted web application to download Instagram stories and highlights anonymously.

## Features

- 📸 Download Instagram stories (photos & videos)
- 🎬 Download Instagram highlights
- 🔒 Anonymous viewing - users won't know you viewed their stories
- 🎨 Beautiful, responsive UI
- ⚡ Fast Flask-based backend
- 🐳 Docker support for easy deployment
- 🔄 Rate limiting and security features
- 📱 Works on mobile and desktop

## Quick Start

### Option 1: Local Development

```bash
# Clone and navigate to vps folder
cd vps

# Run installer (Linux/macOS)
chmod +x scripts/install.sh
./scripts/install.sh

# Or on Windows PowerShell
.\scripts\install.ps1

# Edit .env with your Instagram credentials
nano .env  # or notepad .env on Windows

# Start the server
python run.py
```

### Option 2: Docker

```bash
# Copy and edit environment file
cp .env.example .env
nano .env

# Build and run
docker-compose up -d

# View logs
docker-compose logs -f
```

### Option 3: Docker with Nginx

```bash
docker-compose --profile with-nginx up -d
```

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `IG_SESSION_ID` | Instagram session cookie | `12345%3Axyz...` |
| `IG_DS_USER_ID` | Your Instagram user ID | `12345678` |
| `IG_CSRF_TOKEN` | CSRF token from cookies | `AbCdEf123...` |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `5000` |
| `DEBUG` | Enable debug mode | `false` |
| `SECRET_KEY` | Flask secret key | Random |
| `WORKERS` | Gunicorn workers | CPU * 2 + 1 |

## How to Get Instagram Cookies

1. Open **Instagram** in Chrome/Firefox
2. Login to your account
3. Open **Developer Tools** (F12)
4. Go to **Application** → **Cookies** → **instagram.com**
5. Copy these cookie values:
   - `sessionid` → `IG_SESSION_ID`
   - `ds_user_id` → `IG_DS_USER_ID`
   - `csrftoken` → `IG_CSRF_TOKEN`

> ⚠️ **Note:** Session cookies expire periodically. You may need to update them if you get authentication errors.

## API Endpoints

### GET /api/stories

Fetch stories for a username or highlight.

**Parameters:**
- `username` (required): Instagram username, profile URL, or highlight URL

**Examples:**
```
/api/stories?username=instagram
/api/stories?username=https://instagram.com/stories/username/
/api/stories?username=https://instagram.com/stories/highlights/12345/
```

**Response:**
```json
{
  "success": true,
  "username": "example",
  "user": {
    "pk": "123456789",
    "username": "example",
    "full_name": "Example User",
    "profile_pic_url": "https://...",
    "is_private": false
  },
  "stories": [...],
  "count": 5
}
```

### GET /api/download

Proxy download for media files.

**Parameters:**
- `url` (required): Media URL (must be from Instagram CDN)
- `filename` (optional): Download filename
- `type` (optional): `image` or `video`

### GET /api/health

Health check endpoint.

## Production Deployment

### Using Gunicorn (Recommended)

```bash
# Activate virtual environment
source venv/bin/activate

# Start with gunicorn
gunicorn -c gunicorn.conf.py app:app
```

### Using systemd

Create `/etc/systemd/system/instagram-downloader.service`:

```ini
[Unit]
Description=Instagram Story Downloader
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/instagram-downloader
Environment="PATH=/opt/instagram-downloader/venv/bin"
EnvironmentFile=/opt/instagram-downloader/.env
ExecStart=/opt/instagram-downloader/venv/bin/gunicorn -c gunicorn.conf.py app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable instagram-downloader
sudo systemctl start instagram-downloader
```

### Using Docker in Production

```bash
# Build production image
docker build -t instagram-downloader:latest .

# Run with Docker
docker run -d \
  --name instagram-downloader \
  --restart unless-stopped \
  -p 5000:5000 \
  --env-file .env \
  instagram-downloader:latest
```

## Security Considerations

1. **Never commit `.env` files** - They contain sensitive credentials
2. **Use HTTPS** in production - Configure SSL with Nginx
3. **Rate limiting** is enabled by default - 100 requests/hour per IP
4. **Download proxy validates domains** - Only Instagram CDN URLs allowed
5. **Run as non-root user** in Docker

## Troubleshooting

### "Session expired" error
- Your Instagram cookies have expired
- Get new cookies from your browser and update `.env`

### "Rate limited" error
- Instagram is temporarily blocking requests
- Wait a few minutes and try again
- Consider using multiple accounts (rotate credentials)

### "User not found" error
- Check the username spelling
- The account may have been deleted or banned

### Container won't start
- Check logs: `docker-compose logs`
- Verify `.env` file exists and has correct values

## Project Structure

```
vps/
├── app.py              # Main Flask application
├── config.py           # Configuration management
├── run.py              # Development server entry point
├── requirements.txt    # Python dependencies
├── gunicorn.conf.py    # Gunicorn configuration
├── Dockerfile          # Docker image definition
├── docker-compose.yml  # Docker Compose configuration
├── nginx.conf          # Nginx configuration
├── .env.example        # Environment template
├── static/
│   └── index.html      # Frontend UI
└── scripts/
    ├── install.sh      # Linux/macOS installer
    ├── install.ps1     # Windows installer
    ├── start.sh        # Linux/macOS start script
    └── start.ps1       # Windows start script
```

## License

MIT License - Use at your own risk.

## Disclaimer

This tool is for educational purposes only. Use responsibly and respect Instagram's Terms of Service. The developers are not responsible for any misuse of this tool.
