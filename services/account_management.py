import logging
import datetime
from threading import Lock

account_locks = Lock()
active_connections = {}     # username -> channel_id
recently_released = {}      # username -> datetime when it was released

def find_available_account(accounts):
    with account_locks:
        for account in accounts:
            if account["username"] not in active_connections:
                return account
    return None

def lock_account(account, channel_id):
    with account_locks:
        active_connections[account["username"]] = channel_id
        logging.debug(f"Locked account {account['username']} for channel {channel_id}.")

def release_account(account, channel_id=None):
    del active_connections[account["username"]]
    recently_released[account["username"]] = datetime.datetime.now()
    logging.debug(f"Released account {account['username']} from channel {channel_id}.")

def clean_recently_released():
    with account_locks:
        cooldown = datetime.timedelta(seconds=30)
        for username, release_time in list(recently_released.items()):
            if datetime.datetime.now() - release_time > cooldown:
                del recently_released[username]
                logging.debug(f"Account {username} is now reusable.")
