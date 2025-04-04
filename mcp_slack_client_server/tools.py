# slack_mcp_server/tools.py

#from services.mcp.claude import MCPTool, MCPToolParameter
from claude import MCPTool, MCPToolParameter

# Post a message
SLACK_POST_MESSAGE_TOOL = MCPTool(
    name="slack_post_message",
    description="Post a new message to a Slack channel",
    parameters=[
        MCPToolParameter(name="channel_id", description="The ID of the channel", type="string", required=True),
        MCPToolParameter(name="text", description="The message text to post", type="string", required=True),
    ],
)

# List public channels
SLACK_LIST_CHANNELS_TOOL = MCPTool(
    name="slack_list_channels",
    description="List public channels in the workspace",
    parameters=[
        MCPToolParameter(name="limit", description="Max number of channels to return", type="integer", required=False),
        MCPToolParameter(name="cursor", description="Pagination cursor for next page", type="string", required=False),
    ],
)

# Reply to a message thread
SLACK_REPLY_TO_THREAD_TOOL = MCPTool(
    name="slack_reply_to_thread",
    description="Reply to a specific thread in Slack",
    parameters=[
        MCPToolParameter(name="channel_id", description="Channel ID", type="string", required=True),
        MCPToolParameter(name="thread_ts", description="Timestamp of parent message (format: 1234567890.123456)", type="string", required=True),
        MCPToolParameter(name="text", description="Text of the reply", type="string", required=True),
    ],
)

# Add a reaction
SLACK_ADD_REACTION_TOOL = MCPTool(
    name="slack_add_reaction",
    description="Add a reaction emoji to a message",
    parameters=[
        MCPToolParameter(name="channel_id", description="Channel ID", type="string", required=True),
        MCPToolParameter(name="timestamp", description="Timestamp of the message", type="string", required=True),
        MCPToolParameter(name="reaction", description="Name of the emoji (without colons)", type="string", required=True),
    ],
)

# Get channel history
SLACK_GET_CHANNEL_HISTORY_TOOL = MCPTool(
    name="slack_get_channel_history",
    description="Get recent messages from a Slack channel",
    parameters=[
        MCPToolParameter(name="channel_id", description="Channel ID", type="string", required=True),
        MCPToolParameter(name="limit", description="Number of messages to retrieve", type="integer", required=False),
    ],
)

# Get replies to a thread
SLACK_GET_THREAD_REPLIES_TOOL = MCPTool(
    name="slack_get_thread_replies",
    description="Get all replies from a thread",
    parameters=[
        MCPToolParameter(name="channel_id", description="Channel ID", type="string", required=True),
        MCPToolParameter(name="thread_ts", description="Timestamp of the parent message", type="string", required=True),
    ],
)

# Get users list
SLACK_GET_USERS_TOOL = MCPTool(
    name="slack_get_users",
    description="Get list of users in workspace",
    parameters=[
        MCPToolParameter(name="limit", description="Number of users to return", type="integer", required=False),
        MCPToolParameter(name="cursor", description="Pagination cursor", type="string", required=False),
    ],
)

# Get user profile
SLACK_GET_USER_PROFILE_TOOL = MCPTool(
    name="slack_get_user_profile",
    description="Get detailed profile info for a user",
    parameters=[
        MCPToolParameter(name="user_id", description="ID of the user", type="string", required=True),
    ],
)

# Group all tools
SLACK_TOOLS = [
    SLACK_POST_MESSAGE_TOOL,
    SLACK_LIST_CHANNELS_TOOL,
    SLACK_REPLY_TO_THREAD_TOOL,
    SLACK_ADD_REACTION_TOOL,
    SLACK_GET_CHANNEL_HISTORY_TOOL,
    SLACK_GET_THREAD_REPLIES_TOOL,
    SLACK_GET_USERS_TOOL,
    SLACK_GET_USER_PROFILE_TOOL,
]
