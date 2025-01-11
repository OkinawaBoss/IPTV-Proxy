import threading
import uuid
import queue
from flask import Blueprint, request, Response

from config import ACCOUNTS
from services.account_management import find_available_account, lock_account, release_account
from services.channel_manager import (
    channel_to_process,
    channel_to_account,
    channel_viewers_queues,
    last_buffer_update,
    release_account_if_inactive,
    generate_viewer
)
from helpers.streaming import start_ffmpeg_stream, fetch_from_ffmpeg

stream_bp = Blueprint('stream', __name__)

@stream_bp.route('/stream/<channel_id>', methods=['GET'])
def stream_channel(channel_id):
    if channel_id in channel_to_process:
        pass  # Already streaming, do nothing special
    else:
        account = find_available_account(ACCOUNTS)
        if not account:
            return "No available accounts", 503

        lock_account(account, channel_id)
        try:
            input_url = f"http://{account['server']}.d4ktv.info:8080/{account['username']}/{account['password']}/{channel_id}"
            process = start_ffmpeg_stream(channel_id, input_url)
            channel_to_process[channel_id] = process
            channel_to_account[channel_id] = account
            channel_viewers_queues[channel_id] = {}

            threading.Thread(
                target=fetch_from_ffmpeg,
                args=(channel_id, process, channel_viewers_queues, last_buffer_update, release_account_if_inactive),
                daemon=True
            ).start()

        except Exception as e:
            release_account(account, channel_id)
            return "Failed to start stream", 503

    viewer_id = str(uuid.uuid4())
    q = channel_viewers_queues[channel_id].setdefault(viewer_id, queue.Queue(maxsize=100))

    return Response(
        generate_viewer(channel_id, viewer_id),
        content_type="video/mp2t"
    )
