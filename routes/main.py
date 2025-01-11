import os
from flask import Blueprint, send_from_directory, Response, request, jsonify
from config import STATIC_DIR, FILTERED_PLAYLIST_FILE_PATH, EPG_FILE_PATH
from services.channel_manager import channel_to_process
import logging

# <-- ADDED: we will use these to force refresh
from helpers.scheduler import update_epg_once
from helpers.downloader import download_m3u
from helpers.epg_filter import filter_to_allowed_groups, filter_m3u, load_epg_display_names
from config import ACCOUNTS, PLAYLIST_FILE_PATH, FILTERED_EPG_FILE_PATH, ALLOWED_GROUPS
from helpers.logo_cache import download_and_process_logo

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def serve_index():
    return send_from_directory(STATIC_DIR, 'index.html')

@main_bp.route('/filtered.m3u', methods=['GET'])
def serve_filtered_playlist():
    if not os.path.exists(FILTERED_PLAYLIST_FILE_PATH):
        logging.error("Filtered playlist file not found.")
        return "Filtered playlist file not found", 404

    try:
        with open(FILTERED_PLAYLIST_FILE_PATH, "r") as playlist_file:
            lines = playlist_file.readlines()

        modified_lines = []
        skip_next_url = False

        for line in lines:
            if line.startswith("#EXTINF"):
                modified_lines.append(line)
                skip_next_url = False
            elif line.startswith("http"):
                if not skip_next_url:
                    channel_id = line.split("/")[-1].strip()
                    if channel_id.isdigit():
                        local_url = f"http://{request.host}/stream/{channel_id}"
                        modified_lines.append(local_url + "\n")
                        skip_next_url = True
            else:
                modified_lines.append(line)

        return Response("".join(modified_lines), content_type="application/vnd.apple.mpegurl")
    except Exception as e:
        logging.error(f"Error serving filtered playlist: {e}")
        return "Internal Server Error", 500

@main_bp.route('/m3u/save_filtered', methods=['POST'])
def save_filtered_playlist():
    try:
        content = request.data.decode("utf-8")
        with open(FILTERED_PLAYLIST_FILE_PATH, "w") as playlist_file:
            playlist_file.write(content)
        logging.info("Filtered playlist saved successfully.")
        return "Filtered playlist saved", 200
    except Exception as e:
        logging.error(f"Error saving filtered playlist: {e}")
        return "Failed to save filtered playlist", 500

@main_bp.route('/epg.xml', methods=['GET'])
def serve_epg():
    if not os.path.exists(EPG_FILE_PATH):
        logging.error("EPG file not found.")
        return "EPG file not found", 404

    try:
        with open(EPG_FILE_PATH, "r") as epg_file:
            return Response(epg_file.read(), content_type="application/xml")
    except Exception as e:
        logging.error(f"Error serving EPG: {e}")
        return "Internal Server Error", 500

@main_bp.route('/<path:filename>')
def serve_static_files(filename):
    return send_from_directory(STATIC_DIR, filename)

# -------------------------------------------------------------------------
# NEW: Manually refresh EPG
# -------------------------------------------------------------------------
@main_bp.route('/epg/refresh', methods=['POST'])
def refresh_epg():
    try:
        logging.info("[MANUAL REFRESH] Starting EPG refresh by user request...")
        update_epg_once()  # use the same function from scheduler.py
        return jsonify({"status": "EPG refreshed successfully"}), 200
    except Exception as e:
        logging.error(f"[MANUAL REFRESH] EPG refresh failed: {e}")
        return jsonify({"error": "Failed to refresh EPG"}), 500


# -------------------------------------------------------------------------
# NEW: Manually refresh channels (M3U)
# -------------------------------------------------------------------------
@main_bp.route('/m3u/refresh', methods=['POST'])
def refresh_m3u():
    try:
        logging.info("[MANUAL REFRESH] Starting M3U refresh by user request...")

        # 1) Download the raw file if it doesn't exist or if we want to force re-download
        download_m3u(ACCOUNTS[0], PLAYLIST_FILE_PATH)  

        # 2) Filter to allowed groups (this modifies unfiltered.m3u "in-place" with only allowed channels)
        filter_to_allowed_groups(PLAYLIST_FILE_PATH, PLAYLIST_FILE_PATH, ALLOWED_GROUPS)

        # 3) If the filtered file doesn't exist, create it by fully filtering (EPG-based).
        #    We first load the EPG channel IDs to do tvg-ID mapping
        if not os.path.exists(FILTERED_EPG_FILE_PATH):
            logging.warning("[MANUAL REFRESH] Filtered EPG file not found. EPG IDs might be missing.")
            epg_display_name_to_id = {}
        else:
            epg_display_name_to_id = load_epg_display_names(FILTERED_EPG_FILE_PATH)

        if not os.path.exists(FILTERED_PLAYLIST_FILE_PATH):
            logging.info("[MANUAL REFRESH] Creating fresh filtered.m3u because none was found.")
            filter_m3u(PLAYLIST_FILE_PATH, FILTERED_PLAYLIST_FILE_PATH, epg_display_name_to_id, ALLOWED_GROUPS)

        return jsonify({"status": "M3U refreshed successfully"}), 200

    except Exception as e:
        logging.error(f"[MANUAL REFRESH] M3U refresh failed: {e}")
        return jsonify({"error": "Failed to refresh M3U"}), 500

@main_bp.route('/m3u/save_filtered_advanced', methods=['POST'])
def save_filtered_advanced():
    """
    Receives a user-edited M3U,
    runs the fuzzy matching logic to assign tvg-ID,
    and then writes final output to filtered.m3u.
    """
    from helpers.epg_filter import filter_m3u, load_epg_display_names
    from helpers.logo_cache import download_and_process_logo
    from config import FILTERED_PLAYLIST_FILE_PATH, FILTERED_EPG_FILE_PATH
    import tempfile, re

    try:
        # 1) Write user’s posted M3U to a temp file
        raw_content = request.data.decode("utf-8")
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp.write(raw_content)
            tmp.flush()
            temp_path = tmp.name

        # 2) Load EPG
        epg_display_name_to_id = load_epg_display_names(FILTERED_EPG_FILE_PATH)

        # 3) We'll do two passes:
        #    (a) We'll read the lines from temp_path,
        #    (b) For each #EXTINF line, we’ll replace the original tvg-logo with our cached version,
        #    (c) Then write them to the same temp file or a second temp file,
        #    (d) Pass that final to `filter_m3u`.
        final_lines = []
        with open(temp_path, "r", encoding="utf-8") as f:
            for line in f:
                # check #EXTINF lines for tvg-logo
                if line.startswith("#EXTINF"):
                    tvg_logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                    if tvg_logo_match:
                        original_logo_url = tvg_logo_match.group(1)
                        if original_logo_url.startswith("http"):
                            new_filename = download_and_process_logo(original_logo_url)
                            if new_filename:
                                new_logo_url = f"http://{request.host}/cache/{new_filename}"
                                line = line.replace(original_logo_url, new_logo_url)
                final_lines.append(line)

        # Write that updated M3U back to temp_path 
        # (or use a second NamedTemporaryFile if you prefer)
        with open(temp_path, "w", encoding="utf-8") as f:
            f.writelines(final_lines)

        # 4) Fuzzy match & inject tvg-ID into the final filtered.m3u
        filter_m3u(
            input_path=temp_path,
            output_path=FILTERED_PLAYLIST_FILE_PATH,
            epg_display_name_to_id=epg_display_name_to_id,
            allowed_groups=None  # or some list
        )

        logging.info("Filtered playlist saved & tvg-ID assigned.")
        return jsonify({"message": "Filtered playlist saved with fuzzy matching"}), 200

    except Exception as e:
        logging.error(f"Error in save_filtered_advanced: {e}")
        return jsonify({"error": str(e)}), 500


