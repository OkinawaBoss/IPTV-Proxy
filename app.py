#!/usr/bin/env python3

import threading
import logging
import os
from flask import Flask
from config import (
    ACCOUNTS,
    PLAYLIST_FILE_PATH, EPG_FILE_PATH,
    FILTERED_EPG_FILE_PATH, FILTERED_PLAYLIST_FILE_PATH,
    ALLOWED_GROUPS
)
from helpers.downloader import download_m3u, download_epg
from helpers.epg_filter import (
    filter_m3u, filter_to_allowed_groups,
    load_epg_display_names
)
from helpers.scheduler import schedule_epg_update
# Blueprints
from routes.main import main_bp
from routes.stream import stream_bp

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)
app.register_blueprint(main_bp)
app.register_blueprint(stream_bp)

if __name__ == "__main__":
    # 1) Start the scheduled EPG updates in a separate thread
    epg_thread = threading.Thread(target=schedule_epg_update, daemon=True)
    epg_thread.start()

    # 2) Check if EPG exists; if not, download & filter it  # <-- NEW
    if not os.path.exists(EPG_FILE_PATH):
        logging.info("No unfiltered.xml found. Downloading EPG now...")
        try:
            download_epg(ACCOUNTS[0], EPG_FILE_PATH)
        except Exception as e:
            logging.error(f"Failed to download EPG: {e}")
        # You may also want to filter it here if needed, e.g.:
        # filter_epg(EPG_FILE_PATH, FILTERED_EPG_FILE_PATH)
        # but if you want to create it fresh, uncomment the line above if your logic requires it.

    # 3) If unfiltered.m3u or filtered.m3u are missing, attempt to create them
    try:
        # unfiltered.m3u check
        if not os.path.exists(PLAYLIST_FILE_PATH):
            logging.info("No unfiltered.m3u found. Downloading now...")
            download_m3u(ACCOUNTS[0], PLAYLIST_FILE_PATH)

            # Immediately remove junk by only keeping ALLOWED_GROUPS in-place
            filter_to_allowed_groups(
                PLAYLIST_FILE_PATH,
                PLAYLIST_FILE_PATH,
                ALLOWED_GROUPS
            )

        # filtered.m3u check
        if not os.path.exists(FILTERED_PLAYLIST_FILE_PATH):
            logging.info("No filtered.m3u found. Creating now...")
            epg_display_name_to_id = {}
            if os.path.exists(FILTERED_EPG_FILE_PATH):
                epg_display_name_to_id = load_epg_display_names(FILTERED_EPG_FILE_PATH)

            # Now produce filtered.m3u with advanced matching (tvg-ID)
            filter_m3u(
                PLAYLIST_FILE_PATH,
                FILTERED_PLAYLIST_FILE_PATH,
                epg_display_name_to_id,
                ALLOWED_GROUPS
            )
            logging.info("M3U playlist created successfully.")

    except Exception as e:
        logging.error(f"An error occurred during the startup preloading process: {e}")

    # 4) Start the Flask app
    logging.info("Starting the Flask server...")
    app.run(host="0.0.0.0", port=9191, threaded=True)
