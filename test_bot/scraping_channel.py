import os
import logging
import json
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from slack_sdk import WebClient

# Load environment variables
load_dotenv()

# Slack API tokens
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# Check if environment variables are set
if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("Missing required Slack environment variables!")

# Initialize Slack app and client
app = App(token=SLACK_BOT_TOKEN)
client = WebClient(token=SLACK_BOT_TOKEN)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Folder to store scraped messages
SCRAPED_FOLDER = "scraped_data"
os.makedirs(SCRAPED_FOLDER, exist_ok=True)


# Function to load existing JSON data for a channel
def load_channel_data(channel_name):
    """Loads existing channel data from JSON, ensuring required keys exist"""
    file_path = os.path.join(SCRAPED_FOLDER, f"{channel_name}_channel.json")
    
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    else:
        data = {}  # Ensure an empty dictionary if file does not exist

    # Ensure the required keys exist
    if "messages" not in data:
        data["messages"] = []
    if "threads" not in data:
        data["threads"] = {}

    return data
# Function to save data in JSON format
def save_channel_data(channel_name, data):
    """Saves channel messages and threads in JSON format"""
    file_path = os.path.join(SCRAPED_FOLDER, f"{channel_name}_channel.json")
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

# Function to handle storing messages correctly
def save_message(channel_name, user, message, timestamp, thread_ts=None):
    """Saves messages properly in the correct thread or as a standalone message"""
    data = load_channel_data(channel_name)

    if thread_ts:
        # Ensure the thread exists, else create it
        if thread_ts not in data["threads"]:
            data["threads"][thread_ts] = {"parent": None, "replies": []}

        # Add the reply to the correct thread
        data["threads"][thread_ts]["replies"].append({
            "timestamp": timestamp,
            "user": user,
            "message": message
        })
    else:
        # Store standalone messages separately
        data["messages"].append({
            "timestamp": timestamp,
            "user": user,
            "message": message
        })
        # Track thread parent message
        data["threads"][timestamp] = {"parent": message, "replies": []}

    # Save updated data
    save_channel_data(channel_name, data)

# Slack event listener for all messages
@app.message()
def handle_message(message, say):
    channel_id = message.get("channel")  # Channel ID
    user_message = message.get("text", "").strip()
    user_id = message.get("user")
    timestamp = message.get("ts")
    thread_ts = message.get("thread_ts", None)  # If this exists, it's a thread reply


    # Save the message (either a new message or a reply)
    save_message(channel_id, user_id, user_message, timestamp, thread_ts)

    # Optional: Send a response for confirmation (can be removed)
    # say(f"✅ Message recorded in {channel_name}_channel.json!", thread_ts=timestamp)

# Start Slack bot with Socket Mode
if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
