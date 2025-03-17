import os
import anthropic
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Slack API tokens
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Initialize Slack app
app = App(token=SLACK_BOT_TOKEN)

# Function to call Anthropic Claude API
def get_claude_response(user_message):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",  # Try "claude-3-sonnet" or "claude-3-haiku" if needed
            max_tokens=256,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text  # Extract response text

    except anthropic.APIStatusError as e:
        print(f"API Error ({e.status_code}): {e.message}")
        return "Oops! I had trouble contacting Claude. Please try again later."
    except Exception as e:
        print(f"⚠️ Unexpected Error: {e}")
        return "What the hell ? "

# Slack event listener for messages
@app.message()
def handle_message(message, say):
    user_message = message['text']
    slack_user = message['user']

    print(f"Received message from {slack_user}: {user_message}")  # Debugging line

    # Let the user know the bot is thinking
    say(f"Hey <@{slack_user}>, let me think... 🤖")

    # Get response from Anthropic Claude
    claude_response = get_claude_response(user_message)
    say(claude_response)

# Start Slack bot with Socket Mode
if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
