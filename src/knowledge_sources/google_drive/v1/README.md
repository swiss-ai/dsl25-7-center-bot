# Google Drive Scraper to Chroma Vector Database

This project scrapes files from your personal **Google Drive**, extracts and chunks the content, and stores it in a **Chroma** vector database (without embeddings, for now). You can later use this database for retrieval-augmented generation (RAG), document search, etc.

---

## Features

- Supports multiple file types: PDF, Markdown, Google Docs, Sheets, Slides, TXT, DOCX, PPTX
- Converts documents to plain text
- Splits content into overlapping chunks
- Stores chunks in a persistent local Chroma DB with metadata
- Option to run on-demand (`main.py`) or on a schedule (`watcher.py`)

---

## Setup Instructions

### 1. Clone the Repo

```bash
git clone https://github.com/your-username/drive-scraper.git
cd drive-scraper
```

---

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Create OAuth Credentials (to access your personal Drive)

> Don't skip this — it's how your scraper accesses your Google Drive files.

#### Step-by-Step:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create a project
3. Enable the **Google Drive API**
4. Go to **APIs & Services > Credentials**
5. Click **“+ Create Credentials” → OAuth client ID**
6. Choose:
   - Application Type: **Desktop App**
   - Name: `Drive Scraper`
7. Download the `credentials.json` file
8. Place it in the root of this repo

> On first run, you’ll be asked to log into your Google account and grant access.

---

### 4. Create a `.env` file

```env
CHROMA_PERSIST_DIRECTORY=./chroma_db
```

---

### 5. Run the Scraper (on-demand)

```bash
python main.py
```

This will:
- Authenticate to Drive
- Download new/updated files
- Extract and chunk their content
- Store everything in `./chroma_db`

---

## Continuous Sync (Like a Cron Job)

Use `watcher.py` to sync automatically every 24h (or configure your own interval).

```bash
python watcher.py
```

To test quickly (e.g., every 1 minute), edit `watcher.py`:

```python
SYNC_INTERVAL_HOURS = 0.016  # ~1 minute
```

---

## Supported File Types

| Format       | Extension | Notes                         |
|--------------|-----------|-------------------------------|
| PDF          | `.pdf`    | Parsed with PyMuPDF           |
| Markdown     | `.md`     | Exported as plain text        |
| Google Docs  | `.gdoc`   | Exported using Drive API      |
| Google Sheets| `.gsheet` | Exported as CSV               |
| Google Slides| `.gslides`| Extracted using Slides API    |
| Text         | `.txt`    | Read as plain text            |
| Word         | `.docx`   | Parsed with `python-docx`     |
| PowerPoint   | `.pptx`   | Parsed with `python-pptx`     |



