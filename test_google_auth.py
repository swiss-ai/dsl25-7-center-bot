#!/usr/bin/env python3

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Path to your credentials.json file
CREDENTIALS_FILE = '/home/dsl25-7-center-bot/config/credentials/credentials.json'
# Path where the token will be saved
TOKEN_FILE = '/home/dsl25-7-center-bot/config/credentials/token.pickle'

# Define the scopes needed (read-only access to files)
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def authenticate_google_drive():
    """Authenticate with Google Drive API and return the service."""
    credentials = None

    # Check if token file exists
    if os.path.exists(TOKEN_FILE):
        print(f"Found existing token file at {TOKEN_FILE}")
        with open(TOKEN_FILE, 'rb') as token:
            credentials = pickle.load(token)

    # If credentials don't exist or are invalid, get new ones
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("Refreshing expired credentials...")
            credentials.refresh(Request())
        else:
            print(f"Starting new OAuth flow with credentials from {CREDENTIALS_FILE}")
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)
        
        # Save the credentials for future use
        print(f"Saving new credentials to {TOKEN_FILE}")
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)

    # Build and return the Drive service
    return build('drive', 'v3', credentials=credentials)

def list_files(service, page_size=10):
    """List files from Google Drive."""
    print(f"\nListing up to {page_size} files from your Google Drive:")
    
    results = service.files().list(
        pageSize=page_size,
        fields="nextPageToken, files(id, name, mimeType, modifiedTime)"
    ).execute()
    
    items = results.get('files', [])
    
    if not items:
        print('No files found.')
    else:
        print('Files:')
        for i, item in enumerate(items, 1):
            print(f"{i}. {item['name']} ({item['mimeType']})")
            print(f"   ID: {item['id']}")
            print(f"   Modified: {item['modifiedTime']}")
            print()

if __name__ == '__main__':
    print("Google Drive API Authentication Test")
    print("===================================")
    
    try:
        # Authenticate and get the service
        print("Authenticating with Google Drive API...")
        service = authenticate_google_drive()
        print("Authentication successful!")
        
        # List some files to verify it's working
        list_files(service)
        
        print("\nTest completed successfully.")
        print(f"Token file saved at: {TOKEN_FILE}")
        print("You can now use this token file for your application.")
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        print("\nPlease check your credentials.json file and try again.")