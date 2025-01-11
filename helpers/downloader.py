import logging
import os
import requests

def download_file(url, file_path):
    """Download a file if it does not already exist."""
    if os.path.exists(file_path):
        logging.info(f"File already exists: {file_path}")
        return file_path

    logging.info(f"Downloading file from: {url}")
    try:
        response = requests.get(url, stream=True, timeout=20)
        response.raise_for_status()
        with open(file_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        logging.info(f"File saved to: {file_path}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download file from {url}: {e}")
        return None

    return file_path


def download_m3u(account, playlist_file_path):
    """Download the M3U playlist file."""
    playlist_url = (
        f"http://{account['server']}.d4ktv.info:8080/"
        f"get.php?username={account['username']}&password={account['password']}"
        "&type=m3u_plus&output=mpegts"
    )
    return download_file(playlist_url, playlist_file_path)


def download_epg(account, epg_file_path):
    """Download the EPG file."""
    epg_url = (
        f"http://{account['server']}.d4ktv.info:8080/"
        f"xmltv.php?username={account['username']}&password={account['password']}"
    )
    return download_file(epg_url, epg_file_path)
