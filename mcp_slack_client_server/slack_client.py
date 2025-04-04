# slack_mcp_server/slack_client.py

import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackClient:
    def __init__(self):
        self.client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

    def post_message(self, channel_id: str, text: str) -> dict:
        """Post a new message to a Slack channel"""
        try:
            response = self.client.chat_postMessage(channel=channel_id, text=text)
            return response.data
        except SlackApiError as e:
            return {"error": str(e)}

    def list_channels(self, limit: int = 100, cursor: str = None) -> dict:
        """List public channels"""
        try:
            params = {"limit": limit}
            if cursor:
                params["cursor"] = cursor
            response = self.client.conversations_list(**params)
            return response.data
        except SlackApiError as e:
            return {"error": str(e)}

    def post_reply(self, channel_id: str, thread_ts: str, text: str) -> dict:
        """Reply to a thread (post message with thread_ts)"""
        try:
            response = self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts,
            )
            return response.data
        except SlackApiError as e:
            return {"error": str(e)}

    def add_reaction(self, channel_id: str, timestamp: str, reaction: str) -> dict:
        """Add a reaction emoji to a message"""
        try:
            response = self.client.reactions_add(
                channel=channel_id,
                timestamp=timestamp,
                name=reaction
            )
            return response.data
        except SlackApiError as e:
            return {"error": str(e)}

    def get_channel_history(self, channel_id: str, limit: int = 10) -> dict:
        """Get recent messages from a channel"""
        try:
            params = {
                "channel": channel_id,
                "limit": limit
            }
            response = self.client.conversations_history(**params)
            return response.data
        except SlackApiError as e:
            return {"error": str(e)}

    def get_thread_replies(self, channel_id: str, thread_ts: str) -> dict:
        """Get all replies in a message thread"""
        try:
            params = {
                "channel": channel_id,
                "ts": thread_ts
            }
            response = self.client.conversations_replies(**params)
            return response.data
        except SlackApiError as e:
            return {"error": str(e)}

    def get_users(self, limit: int = 100, cursor: str = None) -> dict:
        """Get a list of all users in the workspace"""
        try:
            params = {"limit": limit}
            if cursor:
                params["cursor"] = cursor
            response = self.client.users_list(**params)
            return response.data
        except SlackApiError as e:
            return {"error": str(e)}

    def get_user_profile(self, user_id: str) -> dict:
        """Get detailed profile information for a specific user"""
        try:
            response = self.client.users_profile_get(user=user_id)
            return response.data
        except SlackApiError as e:
            return {"error": str(e)}
