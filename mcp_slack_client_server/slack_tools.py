# slack_mcp_server/slack_tools.py

from slack_client import SlackClient

class SlackMCPTools:
    def __init__(self):
        self.slack = SlackClient()

    async def execute_tool(self, tool_name: str, parameters: dict) -> str:
        if tool_name == "slack_post_message":
            channel_id = parameters["channel_id"]
            text = parameters["text"]
            result = self.slack.post_message(channel_id, text)
            return str(result)

        if tool_name == "slack_list_channels":
            limit = parameters.get("limit", 100)
            cursor = parameters.get("cursor")
            result = self.slack.list_channels(limit, cursor)
            return str(result)

        if tool_name == "slack_reply_to_thread":
            channel_id = parameters["channel_id"]
            thread_ts = parameters["thread_ts"]
            text = parameters["text"]
            result = self.slack.post_reply(channel_id, thread_ts, text)
            return str(result)

        if tool_name == "slack_add_reaction":
            channel_id = parameters["channel_id"]
            timestamp = parameters["timestamp"]
            reaction = parameters["reaction"]
            result = self.slack.add_reaction(channel_id, timestamp, reaction)
            return str(result)

        if tool_name == "slack_get_channel_history":
            channel_id = parameters["channel_id"]
            limit = parameters.get("limit", 10)
            result = self.slack.get_channel_history(channel_id, limit)
            return str(result)

        if tool_name == "slack_get_thread_replies":
            channel_id = parameters["channel_id"]
            thread_ts = parameters["thread_ts"]
            result = self.slack.get_thread_replies(channel_id, thread_ts)
            return str(result)

        if tool_name == "slack_get_users":
            limit = parameters.get("limit", 100)
            cursor = parameters.get("cursor")
            result = self.slack.get_users(limit, cursor)
            return str(result)

        if tool_name == "slack_get_user_profile":
            user_id = parameters["user_id"]
            result = self.slack.get_user_profile(user_id)
            return str(result)

        return f"Unknown tool: {tool_name}"
