import json
import os
from datetime import datetime

SYNC_FILE = "last_sync.json"

SUPPORTED_EXTENSIONS = {
    '.pdf', '.md', '.gdoc', '.gsheet', '.gslides', '.txt', '.docx', '.pptx', '.xlsx',
}

def load_synced():
    if os.path.exists(SYNC_FILE):
        with open(SYNC_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_synced(data):
    with open(SYNC_FILE, 'w') as f:
        json.dump(data, f)

def get_files_to_update(service):
    synced = load_synced()
    new_files = []

    page_token = None
    while True:
        results = service.files().list(
            q="trashed = false",
            fields="nextPageToken, files(id, name, modifiedTime, mimeType)",
            pageSize=1000,
            pageToken=page_token
        ).execute()

        for file in results.get('files', []):
            ext = os.path.splitext(file['name'])[-1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                if file['id'] not in synced or file['modifiedTime'] > synced[file['id']]:
                    new_files.append(file)

        page_token = results.get('nextPageToken')
        if not page_token:
            break

    return new_files

def mark_file_synced(file):
    synced = load_synced()
    synced[file['id']] = file['modifiedTime']
    save_synced(synced)