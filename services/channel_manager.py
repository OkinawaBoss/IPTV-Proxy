import logging
import datetime
import queue
from services.account_management import release_account, account_locks

channel_to_process = {}        # channel_id -> FFmpeg Popen
channel_to_account = {}        # channel_id -> account dict
channel_viewers_queues = {}    # channel_id -> {viewer_id -> Queue}
last_buffer_update = {}        # channel_id -> datetime of last buffer

def release_account_if_inactive(channel_id):
    """
    Release FFmpeg process and associated resources for an inactive channel.
    """
    logging.debug(f"Releasing channel {channel_id} if inactive.")
    # Stop the FFmpeg process

    # Release the associated account
    acct = channel_to_account.pop(channel_id, None)
    if acct:
        release_account(acct, channel_id)

    # Cleanup
    if channel_id in channel_viewers_queues:
        del channel_viewers_queues[channel_id]
    if channel_id in last_buffer_update:
        del last_buffer_update[channel_id]

def generate_viewer(channel_id, viewer_id):
    """
    This generator yields data for a specific viewer.
    When the client disconnects, clean up the viewer and, if no viewers remain, tear down the channel.
    """
    try:
        # Get the viewer's queue
        q = channel_viewers_queues.get(channel_id, {}).get(viewer_id)
        if not q:
            logging.error(f"No queue found for channel {channel_id}, viewer {viewer_id}.")
            return

        while True:
            try:
                data = q.get(timeout=10)  # Wait for data
                yield data
            except queue.Empty:
                logging.warning(f"Buffer empty for channel {channel_id}, viewer {viewer_id}.")
                break
    finally:
        # Clean up when the viewer disconnects
        logging.debug(f"Viewer {viewer_id} disconnected from channel {channel_id}. Cleaning up.")
        with account_locks:
            if channel_id in channel_viewers_queues:
                if viewer_id in channel_viewers_queues[channel_id]:
                    del channel_viewers_queues[channel_id][viewer_id]
                # If no viewers remain, clean up the channel
                if not channel_viewers_queues[channel_id]:
                    logging.debug(f"No more viewers left for channel {channel_id}. Stopping FFmpeg.")
                    proc = channel_to_process.pop(channel_id, None)
                    if proc and proc.poll() is None:
                        proc.kill()
                    acct = channel_to_account.pop(channel_id, None)
                    if acct:
                        release_account(acct, channel_id)
                    # Clean up channel data
                    channel_viewers_queues.pop(channel_id, None)
                    last_buffer_update.pop(channel_id, None)
