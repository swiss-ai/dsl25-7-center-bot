from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
import asyncio
import logging

from slack_sdk import WebClient
from services.slack.verification import verify_slack_request
from services.slack.events import handle_slack_event, handle_message_with_context

# Initialize Slack client
from dotenv import load_dotenv
import os
load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=SLACK_BOT_TOKEN)
logger = logging.getLogger(__name__)

router = APIRouter()

class SlackChallenge(BaseModel):
    challenge: str
    token: str
    type: str

@router.post("/events")
async def slack_events(request: Request):
    """
    Handle Slack events, including URL verification and message events.
    """
    # Verify request is from Slack
    if not await verify_slack_request(request):
        raise HTTPException(status_code=403, detail="Invalid request signature")
    
    body = await request.json()
    
    # Handle URL verification challenge
    if "challenge" in body:
        return {"challenge": body["challenge"]}
    
    # Process Slack event
    await handle_slack_event(body)
    
    # Slack expects a 200 OK response quickly
    return JSONResponse(content={"ok": True})

@router.post("/interactions")
async def slack_interactions(request: Request):
    """
    Handle Slack interactive components like buttons and modals.
    """
    # Verify request is from Slack
    if not await verify_slack_request(request):
        raise HTTPException(status_code=403, detail="Invalid request signature")
    
    # Parse form data
    form_data = await request.form()
    payload_str = form_data.get("payload", "{}")
    
    try:
        # Parse the JSON payload
        payload = json.loads(payload_str)
        
        # Get the type of interaction
        action_type = payload.get("type")
        
        # Import needed dependencies
        from main import gdrive_mcp, document_processor
        
        if action_type == "block_actions":
            # Handle block actions (buttons, etc.)
            actions = payload.get("actions", [])
            if not actions:
                return JSONResponse(content={"ok": True})
            
            # Get the first action
            action = actions[0]
            action_id = action.get("action_id")
            value = action.get("value")
            
            # Extract user info
            user_id = payload.get("user", {}).get("id")
            channel_id = payload.get("channel", {}).get("id")
            response_url = payload.get("response_url")
            
            if action_id == "drive_view_file":
                # Handle viewing a file
                if not gdrive_mcp:
                    return JSONResponse(content={
                        "response_type": "ephemeral",
                        "text": "Google Drive integration is not available."
                    })
                
                # File ID is in the value
                file_id = value
                
                # Show that we're fetching the file
                client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text=f"Fetching file content from Google Drive..."
                )
                
                # Fetch the file content
                content, metadata = await gdrive_mcp.get_file_content(file_id)
                
                # Format metadata
                file_name = metadata.get("name", "Untitled")
                mime_type = metadata.get("mimeType", "Unknown type")
                created_time = metadata.get("createdTime", "Unknown").replace('T', ' ').replace('Z', ' UTC')
                modified_time = metadata.get("modifiedTime", "Unknown").replace('T', ' ').replace('Z', ' UTC')
                
                # Format the response
                blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": file_name
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Type:* {mime_type}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Created:* {created_time}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Modified:* {modified_time}"
                            }
                        ]
                    }
                ]
                
                # Add file content as a section
                # Truncate if too long
                if content:
                    if len(content) > 2900:
                        content = content[:2900] + "...\n[Content truncated]"
                    
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"```\n{content}\n```"
                        }
                    })
                else:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "No content available for this file."
                        }
                    })
                
                # Add buttons for actions
                blocks.append({
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Add to Knowledge Base"
                            },
                            "value": file_id,
                            "action_id": "drive_add_to_kb"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Ask Question About File"
                            },
                            "value": file_id,
                            "action_id": "drive_ask_question"
                        }
                    ]
                })
                
                # Send the response using the response_url
                # This updates the message in place
                if response_url:
                    import requests
                    response = requests.post(
                        response_url,
                        json={
                            "response_type": "ephemeral",
                            "replace_original": True,
                            "blocks": blocks
                        }
                    )
                else:
                    # Fallback to ephemeral message
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        blocks=blocks
                    )
                
            elif action_id == "drive_more_results":
                # Handle loading more search results
                if not gdrive_mcp:
                    return JSONResponse(content={
                        "response_type": "ephemeral",
                        "text": "Google Drive integration is not available."
                    })
                
                # Query is in the value
                query = value
                
                # Find previous results to determine offset
                original_blocks = payload.get("message", {}).get("blocks", [])
                file_count = sum(1 for block in original_blocks if block.get("accessory", {}).get("action_id") == "drive_view_file")
                
                # Fetch more results
                files = await gdrive_mcp.search_files(query, max_results=5)
                
                if not files:
                    # No more results
                    blocks = original_blocks[:-1]  # Remove the "Load More" button
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "No more results found."
                        }
                    })
                else:
                    # Keep the header
                    blocks = [original_blocks[0]]
                    
                    # Add both old and new files
                    old_files = []
                    for block in original_blocks:
                        if block.get("accessory", {}).get("action_id") == "drive_view_file":
                            old_files.append(block)
                    
                    # Add old files first
                    blocks.extend(old_files)
                    
                    # Then add new files
                    for file in files:
                        file_type = file.get('mimeType', 'Unknown').split('.')[-1]
                        file_name = file.get('name', 'Untitled')
                        file_id = file.get('id')
                        modified = file.get('modifiedTime', 'Unknown date').replace('T', ' ').replace('Z', ' UTC')
                        
                        blocks.append({
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*{file_name}*\nType: {file_type}\nModified: {modified}"
                            },
                            "accessory": {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "View"
                                },
                                "value": file_id,
                                "action_id": "drive_view_file"
                            }
                        })
                    
                    # Add a "load more" button if there might be more results
                    if len(files) == 5:
                        blocks.append({
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Load More Results"
                                    },
                                    "value": query,
                                    "action_id": "drive_more_results"
                                }
                            ]
                        })
                
                # Send the response using the response_url
                if response_url:
                    import requests
                    response = requests.post(
                        response_url,
                        json={
                            "response_type": "ephemeral",
                            "replace_original": True,
                            "blocks": blocks
                        }
                    )
                
            elif action_id == "drive_add_to_kb":
                # Handle adding a file to the knowledge base
                if not gdrive_mcp or not document_processor:
                    return JSONResponse(content={
                        "response_type": "ephemeral",
                        "text": "Google Drive or Knowledge Base integration is not available."
                    })
                
                # File ID is in the value
                file_id = value
                
                # Show that we're processing the file
                client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text=f"Adding file to knowledge base..."
                )
                
                # Process the file in the background
                asyncio.create_task(
                    add_file_to_kb_and_notify(
                        file_id=file_id,
                        channel_id=channel_id,
                        user_id=user_id,
                        gdrive_mcp=gdrive_mcp
                    )
                )
                
            elif action_id == "drive_ask_question":
                # Handle asking a question about a file
                # This opens a modal for the user to enter a question
                if not gdrive_mcp:
                    return JSONResponse(content={
                        "response_type": "ephemeral",
                        "text": "Google Drive integration is not available."
                    })
                
                # File ID is in the value
                file_id = value
                
                # Get file metadata
                metadata = None
                try:
                    _, metadata = await gdrive_mcp.get_file_content(file_id)
                except Exception as e:
                    logger.error(f"Error getting file metadata: {e}")
                    return JSONResponse(content={
                        "response_type": "ephemeral",
                        "text": f"Error getting file information: {str(e)}"
                    })
                
                file_name = metadata.get("name", "this file")
                
                # Open a modal for the user to enter a question
                client.views_open(
                    trigger_id=payload.get("trigger_id"),
                    view={
                        "type": "modal",
                        "callback_id": "drive_question_modal",
                        "title": {
                            "type": "plain_text",
                            "text": f"Ask about {file_name}"
                        },
                        "submit": {
                            "type": "plain_text",
                            "text": "Ask"
                        },
                        "close": {
                            "type": "plain_text",
                            "text": "Cancel"
                        },
                        "private_metadata": file_id,  # Store the file ID for later
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"What would you like to know about *{file_name}*?"
                                }
                            },
                            {
                                "type": "input",
                                "block_id": "question_block",
                                "element": {
                                    "type": "plain_text_input",
                                    "action_id": "question_input",
                                    "placeholder": {
                                        "type": "plain_text",
                                        "text": "Type your question here..."
                                    },
                                    "multiline": True
                                },
                                "label": {
                                    "type": "plain_text",
                                    "text": "Question"
                                }
                            }
                        ]
                    }
                )
        
        elif action_type == "view_submission":
            # Handle modal submissions
            callback_id = payload.get("view", {}).get("callback_id")
            
            if callback_id == "drive_question_modal":
                # Get the question from the modal
                values = payload.get("view", {}).get("state", {}).get("values", {})
                question = values.get("question_block", {}).get("question_input", {}).get("value", "")
                
                # Get the file ID from the private metadata
                file_id = payload.get("view", {}).get("private_metadata")
                
                # Get user info
                user_id = payload.get("user", {}).get("id")
                
                # Get a DM channel with the user
                user_info = client.users_info(user=user_id)
                im_info = client.conversations_open(users=user_id)
                dm_channel_id = im_info.get("channel", {}).get("id")
                
                if not question or not file_id or not dm_channel_id:
                    return JSONResponse(content={"ok": True})
                
                # Let the user know we're processing their question
                client.chat_postMessage(
                    channel=dm_channel_id,
                    text=f"Processing your question about the file. This may take a moment..."
                )
                
                # Process the question in the background
                asyncio.create_task(
                    process_file_question(
                        question=question,
                        file_id=file_id,
                        channel_id=dm_channel_id,
                        user_id=user_id,
                        gdrive_mcp=gdrive_mcp,
                        document_processor=document_processor
                    )
                )
    
    except Exception as e:
        logger.error(f"Error processing interaction: {e}")
        return JSONResponse(content={
            "response_type": "ephemeral",
            "text": f"Error: {str(e)}"
        })
    
    return JSONResponse(content={"ok": True})

async def add_file_to_kb_and_notify(file_id: str, channel_id: str, user_id: str, gdrive_mcp=None):
    """
    Add a file to the knowledge base and notify the user when done.
    
    Args:
        file_id: The Google Drive file ID
        channel_id: The Slack channel ID
        user_id: The Slack user ID
        gdrive_mcp: The Google Drive MCP instance
    """
    try:
        success = await gdrive_mcp.process_file_to_vector_db(file_id)
        
        if success:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="File successfully added to the knowledge base!"
            )
        else:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="Failed to add file to the knowledge base. Please check the logs for details."
            )
    except Exception as e:
        logger.error(f"Error adding file to KB: {e}")
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"Error adding file to knowledge base: {str(e)}"
        )

async def process_file_question(
    question: str, 
    file_id: str, 
    channel_id: str, 
    user_id: str, 
    gdrive_mcp=None,
    document_processor=None
):
    """
    Process a question about a file and send the response to the user.
    
    Args:
        question: The user's question
        file_id: The Google Drive file ID
        channel_id: The Slack channel ID
        user_id: The Slack user ID
        gdrive_mcp: The Google Drive MCP instance
        document_processor: The document processor instance
    """
    try:
        # Get the file content
        content, metadata = await gdrive_mcp.get_file_content(file_id)
        
        if not content:
            client.chat_postMessage(
                channel=channel_id,
                text=f"Sorry, I couldn't retrieve the content of the file."
            )
            return
        
        file_name = metadata.get("name", "the file")
        
        # Prepare the context for Claude
        context = f"Information about \"{file_name}\":\n\n{content}"
        
        # Formulate a prompt that includes both the context and the question
        prompt = f"I have a question about the following document. First, here is the document:\n\n{context}\n\nHere is my question: {question}\n\nPlease answer my question based on the document provided."
        
        # Use Claude to answer the question
        claude_response = await claude_mcp_request(
            user_message=prompt,
            enable_tool_use=False  # No need for tools here
        )
        
        # Extract the response text
        response_text = await get_claude_response_text(claude_response)
        
        # Send the response to the user
        client.chat_postMessage(
            channel=channel_id,
            text=f"Question about {file_name}:\n>{question}\n\n{response_text}",
            mrkdwn=True
        )
        
    except Exception as e:
        logger.error(f"Error processing file question: {e}")
        client.chat_postMessage(
            channel=channel_id,
            text=f"Sorry, I encountered an error while processing your question: {str(e)}"
        )

@router.post("/commands")
async def slack_commands(request: Request):
    """
    Handle Slack slash commands.
    """
    # Verify request is from Slack
    if not await verify_slack_request(request):
        raise HTTPException(status_code=403, detail="Invalid request signature")
    
    # Parse form data
    form_data = await request.form()
    
    # Extract command and text
    command = form_data.get("command", "")
    text = form_data.get("text", "")
    user_id = form_data.get("user_id", "")
    channel_id = form_data.get("channel_id", "")
    
    # Import needed dependencies
    from main import gdrive_mcp, document_processor
    
    if command == "/drive":
        # Handle Google Drive commands
        return await handle_drive_command(text, user_id, channel_id, gdrive_mcp)
    elif command == "/aicenter":
        # Handle general AI Center commands
        return await handle_aicenter_command(text, user_id, channel_id, document_processor, gdrive_mcp)
    
    # Default response for unknown commands
    return JSONResponse(content={
        "response_type": "ephemeral",
        "text": f"Unknown command {command}. Try /drive search <query> or /aicenter help."
    })

async def handle_drive_command(text: str, user_id: str, channel_id: str, gdrive_mcp=None):
    """
    Handle the /drive slash command for Google Drive operations.
    
    Args:
        text: The command text
        user_id: The Slack user ID
        channel_id: The Slack channel ID
        gdrive_mcp: The Google Drive MCP instance
    """
    if not gdrive_mcp or not gdrive_mcp.service:
        return JSONResponse(content={
            "response_type": "ephemeral",
            "text": "Google Drive integration is not available. Please contact your administrator."
        })
    
    # Parse the command
    parts = text.strip().split(" ", 1)
    if not parts:
        return show_drive_help()
    
    subcommand = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    try:
        if subcommand == "search":
            # Search Google Drive for files
            if not args:
                return JSONResponse(content={
                    "response_type": "ephemeral",
                    "text": "Please provide a search query. Usage: /drive search <query>"
                })
            
            files = await gdrive_mcp.search_files(args, max_results=5)
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Google Drive Search Results: {args}"
                    }
                }
            ]
            
            if not files:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"No files found matching '{args}'"
                    }
                })
            else:
                for file in files:
                    file_type = file.get('mimeType', 'Unknown').split('.')[-1]
                    file_name = file.get('name', 'Untitled')
                    file_id = file.get('id')
                    modified = file.get('modifiedTime', 'Unknown date').replace('T', ' ').replace('Z', ' UTC')
                    
                    # Format each file as a section with buttons
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{file_name}*\nType: {file_type}\nModified: {modified}"
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "View"
                            },
                            "value": file_id,
                            "action_id": "drive_view_file"
                        }
                    })
            
            # Add a "load more" button if there might be more results
            if len(files) == 5:
                blocks.append({
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Load More Results"
                            },
                            "value": args,
                            "action_id": "drive_more_results"
                        }
                    ]
                })
            
            return JSONResponse(content={
                "response_type": "ephemeral",
                "blocks": blocks
            })
            
        elif subcommand == "sync":
            # Sync files from Google Drive to the knowledge base
            max_files = 10
            query = None
            
            if args:
                # Parse the args for max files and query
                if args.isdigit():
                    max_files = int(args)
                else:
                    query = args
            
            # Execute the sync operation in the background
            # We'll respond immediately and update when done
            asyncio.create_task(sync_drive_files_and_notify(channel_id, user_id, gdrive_mcp, query, max_files))
            
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"Syncing files from Google Drive to the knowledge base. This may take a while. I'll notify you when it's complete."
            })
            
        elif subcommand == "help" or subcommand == "":
            return show_drive_help()
            
        else:
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"Unknown subcommand: {subcommand}. Try /drive help for available commands."
            })
            
    except Exception as e:
        logger.error(f"Error handling drive command: {e}")
        return JSONResponse(content={
            "response_type": "ephemeral",
            "text": f"Error: {str(e)}"
        })

def show_drive_help():
    """Show help for the drive command."""
    return JSONResponse(content={
        "response_type": "ephemeral",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Google Drive Commands"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Available commands:*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "• `/drive search <query>` - Search for files in Google Drive"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "• `/drive sync [max_files]` - Sync recent files to the knowledge base"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "• `/drive help` - Show this help message"
                }
            }
        ]
    })

async def sync_drive_files_and_notify(channel_id: str, user_id: str, gdrive_mcp, query=None, max_files=10):
    """
    Sync files from Google Drive and notify the user when done.
    
    Args:
        channel_id: The Slack channel ID
        user_id: The Slack user ID
        gdrive_mcp: The Google Drive MCP instance
        query: Optional query to filter files
        max_files: Maximum number of files to sync
    """
    try:
        synced_count = await gdrive_mcp.sync_recent_files(query, max_files)
        
        # Notify the user when done
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> I've synced {synced_count} files from Google Drive to the knowledge base.",
            mrkdwn=True
        )
    except Exception as e:
        logger.error(f"Error syncing files: {e}")
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> Error syncing files from Google Drive: {str(e)}",
            mrkdwn=True
        )

async def handle_aicenter_command(text: str, user_id: str, channel_id: str, document_processor=None, gdrive_mcp=None):
    """
    Handle the /aicenter slash command for general AI Center operations.
    
    Args:
        text: The command text
        user_id: The Slack user ID
        channel_id: The Slack channel ID
        document_processor: The document processor instance
        gdrive_mcp: The Google Drive MCP instance
    """
    parts = text.strip().split(" ", 1)
    if not parts:
        return show_aicenter_help()
    
    subcommand = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    try:
        if subcommand == "search":
            # Search the knowledge base
            if not args:
                return JSONResponse(content={
                    "response_type": "ephemeral",
                    "text": "Please provide a search query. Usage: /aicenter search <query>"
                })
            
            if not document_processor:
                return JSONResponse(content={
                    "response_type": "ephemeral",
                    "text": "Document processor is not available. Please contact your administrator."
                })
            
            # Perform the search
            results = await document_processor.search_documents(
                query=args,
                n_results=5
            )
            
            # Format the results
            formatted_results = document_processor.format_search_results(results)
            
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"Search results for '{args}':\n\n{formatted_results}"
            })
            
        elif subcommand == "status":
            # Show the status of various components
            status_info = {
                "document_count": document_processor.vector_db.count() if document_processor else 0,
                "google_drive": "operational" if gdrive_mcp and gdrive_mcp.service else "not_initialized"
            }
            
            return JSONResponse(content={
                "response_type": "ephemeral",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "AI Center Status"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Document Count:* {status_info['document_count']}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Google Drive:* {status_info['google_drive']}"
                        }
                    }
                ]
            })
            
        elif subcommand == "help" or subcommand == "":
            return show_aicenter_help()
            
        else:
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"Unknown subcommand: {subcommand}. Try /aicenter help for available commands."
            })
            
    except Exception as e:
        logger.error(f"Error handling aicenter command: {e}")
        return JSONResponse(content={
            "response_type": "ephemeral",
            "text": f"Error: {str(e)}"
        })

def show_aicenter_help():
    """Show help for the aicenter command."""
    return JSONResponse(content={
        "response_type": "ephemeral",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "AI Center Commands"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Available commands:*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "• `/aicenter search <query>` - Search the knowledge base"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "• `/aicenter status` - Show the status of the AI Center"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "• `/aicenter help` - Show this help message"
                }
            }
        ]
    })

@router.post("/context-aware")
async def context_aware_message(
    request: Request,
):
    """
    Enhanced endpoint that uses document_processor and Google Drive MCP for knowledge retrieval.
    """
    # Verify request is from Slack
    if not await verify_slack_request(request):
        raise HTTPException(status_code=403, detail="Invalid request signature")
    
    body = await request.json()
    event = body.get("event", {})
    
    # Handle the message with context
    # We'll pass the document_processor and gdrive_mcp explicitly
    from main import document_processor, gdrive_mcp
    
    await handle_message_with_context(
        event=event,
        document_processor=document_processor,
        gdrive_mcp=gdrive_mcp
    )
    
    # Slack expects a 200 OK response quickly
    return JSONResponse(content={"ok": True})