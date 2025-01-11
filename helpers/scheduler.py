import os
import logging
import time
import schedule
from helpers.downloader import download_epg
from helpers.epg_filter import filter_epg
from config import ACCOUNTS, EPG_FILE_PATH, FILTERED_EPG_FILE_PATH

def schedule_epg_update():
    schedule.every(24).hours.do(lambda: update_epg_once())
    while True:
        schedule.run_pending()
        time.sleep(1)

def update_epg_once():
    """Perform a single EPG update."""
    try:
        logging.info("Starting EPG update...")

        # Delete old files to ensure fresh data
        if os.path.exists(EPG_FILE_PATH):
            os.remove(EPG_FILE_PATH)
            logging.info(f"Deleted old EPG file: {EPG_FILE_PATH}")

        if os.path.exists(FILTERED_EPG_FILE_PATH):
            os.remove(FILTERED_EPG_FILE_PATH)
            logging.info(f"Deleted old filtered EPG file: {FILTERED_EPG_FILE_PATH}")

        download_epg(ACCOUNTS[0], EPG_FILE_PATH)
        filter_epg(EPG_FILE_PATH, FILTERED_EPG_FILE_PATH)

        logging.info("EPG update completed successfully.")
    except Exception as e:
        logging.error(f"Failed to update EPG: {e}")
