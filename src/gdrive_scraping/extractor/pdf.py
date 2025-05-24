import fitz
import io
import logging
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

def extract_text_from_pdf(service, file_id):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    try:
        while not done:
            status, done = downloader.next_chunk()
    except HttpError as e:
        if 'fileNotDownloadable' in str(e):
            logger.warning(f"❌ PDF file not downloadable: {file_id}")
            return ""
        else:
            raise

    text = ""
    with fitz.open(stream=fh.getvalue(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text
