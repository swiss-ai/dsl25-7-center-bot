import io
import pandas as pd
from googleapiclient.http import MediaIoBaseDownload


def extract_text_from_xlsx(service, file_id):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    fh.seek(0)
    text = ""
    try:
        xls = pd.read_excel(fh, sheet_name=None)
        for sheet_name, df in xls.items():
            text += f"\nSheet: {sheet_name}\n"
            text += df.to_string(index=False)
            text += "\n"
    except Exception as e:
        print(f"Failed to parse XLSX: {e}")
    return text