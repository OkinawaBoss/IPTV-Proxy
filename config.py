import os
import datetime
import logging

logging.basicConfig(level=logging.DEBUG)

ACCOUNTS = [
    {"server": "servernumber", "username": "username",  "password": "password"},
]

# Only channels in these groups will appear in unfiltered.m3u
# before further filtering or cleanup for filtered.m3u
ALLOWED_GROUPS = [
    "US NBC NETWORK", "USA Ultra 60FPS", "US ABC NETWORK", "US CBS NETWORK",
    "US CW NETWORK", "US ENTERTAINMENT NETWORK", "US FOX NETWORK",
    "US LOCAL", "US NEWS NETWORK", "US PBS NETWORK",
    "US SPORTS NETWORK", "USA METV NETWORK"
]

BASE_DIR = os.getcwd()
STATIC_DIR = os.path.join(BASE_DIR, "static")

PLAYLIST_FILE_PATH = os.path.join(STATIC_DIR, "Fresh", "unfiltered.m3u")
EPG_FILE_PATH = os.path.join(STATIC_DIR, "Fresh", "unfiltered.xml")
FILTERED_EPG_FILE_PATH = os.path.join(STATIC_DIR, "Fresh", "filtered.xml")
FILTERED_PLAYLIST_FILE_PATH = os.path.join(STATIC_DIR, "Fresh", "filtered.m3u")
