import io
from googleapiclient.http import MediaIoBaseDownload
import docx
import logging
import zipfile

logger = logging.getLogger(__name__)

def extract_text_from_docx(service, file_id):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    fh.seek(0)

    try:
        document = docx.Document(fh)
        text = "\n".join([p.text for p in document.paragraphs])
        return text
    except zipfile.BadZipFile:
        logger.warning(f"❌ Failed to parse DOCX file (not a real zip): {file_id}")
        return ""
