import os
import signal
import subprocess
import logging
import datetime
import queue
from .utils import normalize_name
from services.channel_manager import release_account_if_inactive

def start_ffmpeg_stream(channel_id, input_url):
    logging.debug(f"Starting FFmpeg for channel {channel_id} with URL {input_url}.")
    return subprocess.Popen(
        [
            "ffmpeg", "-re", "-fflags", "+nobuffer", "-flags", "low_delay",
            "-i", input_url,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-f", "mpegts", "-"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )


def fetch_from_ffmpeg(channel_id, process, channel_viewers_queues, last_buffer_update, release_account_if_inactive):
    while True:
        try:
            data = process.stdout.read(4096)
            if not data:
                # Possibly handle error here. But since stderr=DEVNULL, skip reading it.
                logging.error(f"FFmpeg: No more data for channel {channel_id}. Maybe stream ended.")
                break

            last_buffer_update[channel_id] = datetime.datetime.now()
            if channel_id in channel_viewers_queues:
                for q in channel_viewers_queues[channel_id].values():
                    try:
                        q.put(data, timeout=1)
                    except queue.Full:
                        pass

        except Exception as e:
            logging.error(f"Error fetching data for channel {channel_id}: {e}")
            break

    # Once we exit the loop, the stream is effectively done:
    logging.debug(f"Stream fetching stopped for channel {channel_id}.")
    release_account_if_inactive(channel_id)
