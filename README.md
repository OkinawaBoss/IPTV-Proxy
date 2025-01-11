# IPTV Proxy

This project is an **IPTV Proxy** designed to simplify the process of organizing and streaming IPTV channels. It can help you:

- Maintain multiple IPTV accounts for multiple viewers (DVR, live viewing, etc.) without consuming additional login sessions.  
- Filter out unwanted channels by group or custom rules.  
- Automatically refresh EPG (Electronic Program Guide) data every 24 hours.  
- Cache channel logos to reduce load time and avoid rate limits.  
- Provide a user-friendly web interface (via Flask) to manage your channels, playlists, and EPG.

Although it is pre-configured for **cloudstream.us** (see usage of `serverNumber.d4ktv.info` in the code), you can adapt it for other IPTV services with minimal modifications (primarily in the `config.py` and `downloader.py`).

## Key Features

1. **Single Account, Multiple Streams**  
   This proxy uses **FFmpeg** to buffer your IPTV feed. Multiple users can watch or record the same channel simultaneously, all while using **only one** account on the backend.  

2. **Automatic EPG Updates**  
   Uses the `schedule` library to refresh the EPG every 24 hours. The schedule runs in a background thread.  

3. **Logo Caching**  
   Channels’ logos are downloaded, processed, and cached locally to improve performance and avoid rate-limits.  

4. **Filtering by Groups and Fuzzy Matching**  
   - Allows filtering channels (in `unfiltered.m3u`) to only keep certain groups, generating a smaller `filtered.m3u`.  
   - Uses fuzzy matching to map channel names to the EPG.  

5. **Simple Web Interface**  
   - View channels, filter them, and save new playlists.  
   - Refresh the EPG or M3U manually from the interface if needed.  
   - Access it on a local (or remote) server at `http://your-server:9191/`.  

## How It Works (High-Level)

1. **Startup** (`app.py`):
   - Downloads the main (unfiltered) playlist (`unfiltered.m3u`) if not found.  
   - Downloads the main EPG (`unfiltered.xml`) if not found.  
   - Filters the playlist to only the groups you want (in-place) and saves it back as `unfiltered.m3u`.  
   - Generates a new `filtered.m3u` with more advanced EPG matching.  
   - Launches the Flask server on port `9191`.  

2. **Streaming**:
   - When a user clicks a channel link from the filtered playlist, a request hits `/stream/<channel_id>`.  
   - If FFmpeg is not already running for that channel, the system finds an available IPTV account, locks it, and spawns an FFmpeg process.  
   - Data is piped from FFmpeg to all connected viewers. The account remains locked until all viewers disconnect.  

3. **EPG Scheduling**:
   - The code in `scheduler.py` uses `schedule.every(24).hours.do(...)` to periodically download a fresh EPG and filter it.  
   - Old EPG data is removed to prevent confusion.  

4. **Logo Caching**:
   - The `logo_cache` blueprint (in `helpers/logo_cache.py`) can download and preprocess channel logos.  
   - It fills in transparent areas with a background color and serves the processed images locally.  

## Configuration

All user-customizable settings, including server credentials, file paths, and default groups, live in **`config.py`**:

```python
ACCOUNTS = [
    {
        "server": "ServerNumber", 
        "username": "username", 
        "password": "password"
    }
]

ALLOWED_GROUPS = [
    "US NBC NETWORK", "USA Ultra 60FPS", "US ABC NETWORK", 
    "US CBS NETWORK", "US CW NETWORK", "US ENTERTAINMENT NETWORK",
    "US FOX NETWORK", "US LOCAL", "US NEWS NETWORK", 
    "US PBS NETWORK", "US SPORTS NETWORK", "USA METV NETWORK"
]
```

- **`server`**: The server prefix used by your IPTV provider.  
- **`username`** and **`password`**: Your IPTV credentials.  
- **`ALLOWED_GROUPS`**: Channel groups that you want to retain in `unfiltered.m3u`.  

You can add more accounts if needed; the system will pick the first available account for each channel.

## Project Structure

A brief overview of the important directories and files:

```
.
├── app.py                 # Main Flask entry point
├── config.py              # Configuration file (credentials, file paths, etc.)
├── requirements.txt       # Python dependencies (see below)
├── helpers/
│   ├── downloader.py      # Downloads M3U & EPG from the IPTV provider
│   ├── epg_filter.py      # Filters M3U, maps EPG, fuzzy matching
│   ├── logo_cache.py      # Caches logos
│   ├── scheduler.py       # Periodic tasks (EPG refresh)
│   └── streaming.py       # FFmpeg logic
├── routes/                # Flask routes
│   ├── main.py            # Main endpoints (index, EPG, refresh actions)
│   └── stream.py          # Streaming endpoints
├── services/              # Business logic
│   ├── account_management.py  # Locks/releases IPTV accounts
│   └── channel_manager.py     # Manages channel processes, viewers
├── static/
│   ├── Fresh/             # Directory for actual M3U and XML files
│   ├── css/               # Frontend styles
│   ├── js/                # Frontend JavaScript (mainly `app.js`)
│   └── index.html         # Main UI for editing and filtering channels
└── ...
```

## Getting Started

1. **Clone the repository**:
   ```bash
   git clone https://github.com/OkinawaBoss/IPTV-Proxy.git
   cd iptv-proxy
   ```

2. **Install Python dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Edit `config.py`** to add your IPTV **server**, **username**, and **password**.

4. **Run the application**:
   ```bash
   python app.py
   ```
   The server should start on **`http://0.0.0.0:9191/`**.

5. **Access the web interface**:  
   Visit `http://localhost:9191/` (or replace `localhost` with your server's IP if running remotely).

## Frequently Asked Questions

- **Q**: *Can I use another IPTV service?*  
  **A**: Yes. Update the playlist/EPG download URLs in `downloader.py` to match your provider’s API.  

- **Q**: *What if I need more advanced filtering?*  
  **A**: You can modify `epg_filter.py` or the JavaScript in `app.js`.  

- **Q**: *Does this support HTTPS?*  
  **A**: Not out of the box. You’ll need to run behind a reverse proxy like Nginx or Caddy to enable HTTPS.  

- **Q**: *How often is the EPG updated?*  
  **A**: By default, every 24 hours (see `scheduler.schedule_epg_update`).  

- **Q**: *Where are the M3U and EPG files located?*  
  **A**: In `static/Fresh/` by default.  

- **Q**: *My logos are missing or not showing?*  
  **A**: Check `logo_cache.py` and ensure the cache folder is writable. Also verify your M3U's `tvg-logo` references are valid URLs.  

## Requirements

- **Python 3.7+**  
- The following Python packages (see `requirements.txt` below)

## requirements.txt

```
Flask==2.2.5
requests==2.31.0
Pillow==10.0.0
schedule==1.2.0
```

