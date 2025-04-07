# Google Drive Integration for AI Center Bot

This guide explains how to set up and use the Google Drive integration for the AI Center Bot. The integration allows the chatbot to access and search content from Google Drive files, making them available for knowledge retrieval.

## Features

- Connect to Google Drive using OAuth authentication
- Extract text from multiple file formats:
  - PDF files
  - Google Docs, Sheets, and Slides
  - Microsoft Office files (DOCX, XLSX, PPTX)
  - Plain text and Markdown files
- Track file modifications and only update changed files
- Search files by content and metadata
- Integrate with the vector database for semantic search

## Setup Instructions

### 1. Create Google API Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Drive API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Drive API" and enable it
4. Create OAuth credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Application type: "Desktop application"
   - Name: "AI Center Bot"
   - Download the credentials JSON file

### 2. Configure Environment Variables

Add the following variables to your `.env` file:

```
# Google Drive Integration
GOOGLE_DRIVE_ENABLED=true
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
GOOGLE_TOKEN_PATH=/path/to/token.pickle
GOOGLE_DRIVE_SYNC_FILE=gdrive_last_sync.json
GOOGLE_DRIVE_MAX_FILES=100
```

- `GOOGLE_DRIVE_ENABLED`: Set to "true" to enable the integration
- `GOOGLE_CREDENTIALS_PATH`: Path to the credentials.json file downloaded from Google Cloud Console
- `GOOGLE_TOKEN_PATH`: Path where the OAuth token will be stored after authentication
- `GOOGLE_DRIVE_SYNC_FILE`: Path to store synchronization state (defaults to "gdrive_last_sync.json")
- `GOOGLE_DRIVE_MAX_FILES`: Maximum number of files to sync per operation (defaults to 100)

### 3. First-time Authentication

The first time you run the application with Google Drive integration enabled, it will open a browser window to authenticate with Google. Follow these steps:

1. Start the application
2. A browser window will open asking you to sign in to Google
3. Sign in and grant the requested permissions
4. The token will be saved to the location specified in `GOOGLE_TOKEN_PATH`

## Usage

### API Endpoints

The following API endpoints are available for the Google Drive integration:

#### Sync All Files

```http
POST /api/knowledge/gdrive/sync
```

Starts synchronizing files from Google Drive to the vector database. This runs in the background and may take some time depending on the number and size of files.

Optional query parameters:
- `max_files`: Override the maximum number of files to sync (default is the value from GOOGLE_DRIVE_MAX_FILES)

#### Sync Specific File

```http
POST /api/knowledge/gdrive/file/{file_id}
```

Synchronizes a specific file from Google Drive by its ID.

#### Search Files in Google Drive

```http
GET /api/knowledge/gdrive/search?query={query}&max_results={max_results}
```

Searches for files in Google Drive by name and content.

Parameters:
- `query`: Text to search for
- `max_results` (optional): Maximum number of results to return (default: 10)

#### Get Google Drive Status

```http
GET /api/knowledge/gdrive/status
```

Returns the status of the Google Drive integration:
- Whether it's enabled
- Whether credentials are configured correctly
- Whether the integration is initialized

## Troubleshooting

### Authentication Issues

If you encounter authentication issues:

1. Verify that you've downloaded the correct credentials file
2. Check that the paths in environment variables are correct
3. Delete the token file (specified in `GOOGLE_TOKEN_PATH`) to force re-authentication
4. Check the logs for specific error messages

### Missing Dependencies

If you encounter errors about missing libraries, make sure you've installed all the required dependencies:

```bash
pip install -r requirements.txt
```

### Files Not Syncing

If files aren't syncing correctly:

1. Check that the file types are supported
2. Verify the file is not trashed in Google Drive
3. Try manually syncing a specific file using the `/api/knowledge/gdrive/file/{file_id}` endpoint
4. Check the logs for any error messages during synchronization

## Implementation Details

The Google Drive integration is implemented in the following files:

- `src/services/knowledge/datasources/gdrive.py`: Main implementation of the GoogleDriveManager class
- `src/api/knowledge_routes.py`: API endpoints for Google Drive operations
- `src/config/settings.py`: Configuration settings for Google Drive integration
- `src/main.py`: Initialization of the Google Drive manager

The integration leverages several libraries to support different file types:
- PyMuPDF for PDF extraction
- python-docx for Word documents
- python-pptx for PowerPoint presentations
- pandas and openpyxl for Excel spreadsheets
- Google Drive API for Google Workspace files (Docs, Sheets, Slides)