from auth.google_auth import get_drive_service
from extractor.pdf import extract_text_from_pdf
from extractor.markdown import extract_text_from_md
from extractor.docs import extract_text_from_docs
from extractor.sheets import extract_text_from_sheets
from extractor.slides import extract_text_from_slides
from extractor.text import extract_text_from_txt
from extractor.docx import extract_text_from_docx
from extractor.pptx import extract_text_from_pptx
from chunking.splitter import chunk_text
from vectorstore.chroma import store_chunks
from sync import get_files_to_update, mark_file_synced
import os

EXTENSIONS = {
    '.pdf': extract_text_from_pdf,
    '.md': extract_text_from_md,
    '.gdoc': extract_text_from_docs,
    '.gsheet': extract_text_from_sheets,
    '.gslides': extract_text_from_slides,
    '.txt': extract_text_from_txt,
    '.docx': extract_text_from_docx,
    '.pptx': extract_text_from_pptx,
}

import logging
logging.basicConfig(level=logging.INFO)

def main():
    service = get_drive_service()
    logging.info("Authenticated to Google Drive ✅")

    files = get_files_to_update(service)
    logging.info(f"Found {len(files)} files to process.")

    for file in files:
        name = file['name']
        file_id = file['id']
        ext = os.path.splitext(name)[-1].lower()
        mime_type = file.get("mimeType", "")

        logging.info(f"Processing file: {name} (ID: {file_id}, MIME: {mime_type})")

        if ext in EXTENSIONS:
            try:
                extractor = EXTENSIONS[ext]
                text = extractor(service, file_id)
                chunks = chunk_text(text)
                if not chunks:
                    logging.info(f"❗️ No chunks extracted from {name}")
                store_chunks(file_id, name, chunks)
                mark_file_synced(file)
            except Exception as e:
                logging.warning(f"❌ Failed to extract {name} (ID: {file_id}): {e}")
        else:
            logging.info(f"Skipped unsupported file type: {name}")



if __name__ == '__main__':
    main()