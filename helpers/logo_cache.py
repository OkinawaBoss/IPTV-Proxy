import os
import logging
import requests
import hashlib
from PIL import Image

from flask import Blueprint, send_file, request, abort
from io import BytesIO

logo_cache_bp = Blueprint("logo_cache", __name__)
CACHE_FOLDER = os.path.join("static", "cache")
BACKGROUND_COLOR = (106, 133, 176)  # (R, G, B) for #6a85b0

# Make sure the folder exists
if not os.path.exists(CACHE_FOLDER):
    os.makedirs(CACHE_FOLDER, exist_ok=True)

@logo_cache_bp.route("/cache/<path:filename>")
def serve_cached_logo(filename):
    """
    If `filename` already exists in static/cache, serve it.
    If not, we need a mapping from filename -> original URL, or 
    we fail with 404 (or some fallback).
    """
    # 1) Construct full local path
    local_path = os.path.join(CACHE_FOLDER, filename)

    # 2) If file exists locally, serve it
    if os.path.exists(local_path):
        return send_file(local_path, mimetype="image/png")

    # Otherwise, we do NOT know the original URL. We must have stored that somewhere.
    # If you want to store a map filename -> original_url in a DB or a dictionary, do that. 
    # Or embed the original URL into "filename" using a safe base64 or hashing approach.

    logging.error(f"No cached file found for {filename} and no known original URL. 404.")
    abort(404)


def get_hashed_filename(original_url: str) -> str:
    """Generate a stable hashed filename from the original URL."""
    # For instance, use MD5 or sha256
    md5hash = hashlib.md5(original_url.encode("utf-8")).hexdigest()
    return f"{md5hash}.png"


def download_and_process_logo(original_url: str) -> str:
    """
    Download from original_url, fill background, save to static/cache, and return the new filename.
    """
    hashed_name = get_hashed_filename(original_url)
    local_path = os.path.join(CACHE_FOLDER, hashed_name)

    # If it already exists, skip re-downloading
    if os.path.exists(local_path):
        return hashed_name

    # Download
    try:
        resp = requests.get(original_url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to download {original_url}: {e}")
        return None

    # Process with Pillow
    try:
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        # If there's any transparency, fill it with #6a85b0
        background = Image.new("RGBA", img.size, BACKGROUND_COLOR)
        background.paste(img, (0, 0), img)
        # Convert back to RGB (no alpha)
        final = background.convert("RGB")

        # Save final
        final.save(local_path, format="PNG")
        logging.info(f"Logo cached at: {local_path}")

    except Exception as e:
        logging.error(f"Failed to process image {original_url}: {e}")
        return None

    return hashed_name
