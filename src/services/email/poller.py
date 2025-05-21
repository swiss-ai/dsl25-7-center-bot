#!/usr/bin/env python3
import os
import time
import pathlib
import logging
import base64
import re
from email.message import EmailMessage

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

import asyncio
import logging

import sys, importlib
sys.path.append(os.path.join(os.path.dirname(__file__), "../../.."))
project_root = os.path.abspath(os.path.join(__file__, "../../../.."))
if project_root not in sys.path:
    sys.path.append(project_root)
# ---------------------------------------------------------------

# now a plain absolute import works no matter where poller lives
main_app = importlib.import_module("main")     # == import main

from services.mcp.claude import ask_claude_with_tools
import asyncio

# ─── CONFIG ───────────────────────────────────────────────────────────────────
SCOPES           = ["https://www.googleapis.com/auth/gmail.modify"]
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH       = os.getenv("GMAIL_TOKEN_PATH",       "token.json")
STATE_PATH       = os.getenv("GMAIL_STATE_PATH",       "last_history_id.txt")
POLL_INTERVAL_S  = int(os.getenv("GMAIL_POLL_INTERVAL", "10"))

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

# ─── SIMPLE FORWARD SPLITTER ───────────────────────────────────────────────────
FWD_SEP = re.compile(
    r"(?m)^(?:[-]{2,}\s*Forwarded\smessage\s*[-]{2,}"
    r"|Begin\sforwarded\smessage:"
    r"|[-]{2,}\s*Original\sMessage\s*[-]{2,}"
    r"|On\s.+?wrote:)"
)


def split_user_and_forward(body):
    """
    Returns (user_text, forwarded_text).
    forwarded_text has separator, headers, and '>' stripped out.
    """
    m = FWD_SEP.search(body)
    if not m:
        return body.strip(), ""
    user = body[:m.start()].strip()
    fwd_lines = body[m.start():].splitlines()

    cleaned = []
    for line in fwd_lines:
        # skip separator or blank lines
        if FWD_SEP.match(line) or not line.strip():
            continue
        # strip leading '>' and whitespace
        line = line.lstrip(">").lstrip()
        # skip email headers
        if re.match(r"^(From:|Date:|Subject:|To:)", line):
            continue
        cleaned.append(line)
    return user, "\n".join(cleaned).strip()

# ─── OAUTH2 / GMAIL CLIENT ─────────────────────────────────────────────────────
def get_gmail_service():
    """Load or refresh credentials, then build the Gmail client."""
    creds = None
    # 1) load saved token
    if pathlib.Path(TOKEN_PATH).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    # 2) refresh or run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not pathlib.Path(CREDENTIALS_PATH).exists():
                raise FileNotFoundError(f"Missing client secret: {CREDENTIALS_PATH}")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        # 3) save for next time
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    # 4) build service
    return build("gmail", "v1", credentials=creds, cache_discovery=False)

# Initialize Gmail service once
gmail = get_gmail_service()

# ─── HISTORY CHECKPOINT ────────────────────────────────────────────────────────
def load_start_history():
    p = pathlib.Path(STATE_PATH)
    if p.exists():
        return p.read_text().strip()
    profile = gmail.users().getProfile(userId="me").execute()
    hid = profile["historyId"]
    p.write_text(hid)
    return hid

def save_history_id(hid):
    pathlib.Path(STATE_PATH).write_text(hid)

# ─── GMAIL HELPERS ─────────────────────────────────────────────────────────────
def get_new_message_ids(start_hid):
    resp = gmail.users().history().list(
        userId="me",
        startHistoryId=start_hid,
        historyTypes=["messageAdded"]
    ).execute()
    ids = []
    for h in resp.get("history", []):
        start_hid = h["id"]
        for m in h.get("messagesAdded", []):
            ids.append(m["message"]["id"])
    return ids, start_hid

def fetch_message(msg_id):
    return gmail.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()

def _walk_parts(payload):
    """Yield every sub-part in depth-first order."""
    stack = [payload]
    while stack:
        part = stack.pop()
        yield part
        stack.extend(part.get("parts", []))          # push children

_TAG_RE = re.compile(r"<[^>]+>")                     # crude html stripper

def get_plain_body(msg) -> str:
    """
    Return best-effort plain text from a Gmail message.
    1. Prefer text/plain (first one encountered)
    2. else fall back to stripped text/html
    """
    txt = None
    html = None

    for part in _walk_parts(msg["payload"]):
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        if not body.get("data"):
            continue
        data = base64.urlsafe_b64decode(body["data"]).decode(errors="replace")

        if mime == "text/plain" and txt is None:
            txt = data.strip()
            break                                    # good enough
        elif mime == "text/html" and html is None:
            html = data

    if txt:
        return txt
    if html:
        return _TAG_RE.sub("", html).strip()         # strip tags → text
    return ""

# ─── YOUR LLM STUB (swap in real model) ────────────────────────────────────────
def generate_reply(user_text: str, forwarded_text: str) -> str:
    """
    Build a prompt then synchronously call the async
    Claude-with-tools helper.  We pull the already-initialised
    document_processor / managers directly from main.py so we
    don’t duplicate anything.
    """

    # Grab the shared, already-initialised objects (None if
    # startup hasn’t finished yet)
    dp   = getattr(main_app, "document_processor", None)
    gdrv = getattr(main_app, "gdrive_manager", None)
    wcm  = getattr(main_app, "web_content_manager", None)

    if dp is None:            # still spinning-up – be polite
        return "Sorry, I'm still starting up—please try again in a minute."

    prompt = (
        "The query is the following:\n"
        f"{user_text}\n\n"
        "And you can use this exchange of messages as additional content"
        f"{forwarded_text}\n\n"
    )

    # run the async helper in this background-thread context
    return asyncio.run(
        ask_claude_with_tools(
            prompt,
            document_processor=dp,
            gdrive_manager=gdrv,
            web_content_manager=wcm
        )
    )


def send_reply(original, reply_text):
    hdrs = {h["name"].lower(): h["value"] for h in original["payload"]["headers"]}
    msg = EmailMessage()
    msg["To"]          = hdrs.get("from")
    msg["Subject"]     = "Re: " + hdrs.get("subject", "")
    msg["In-Reply-To"] = original["id"]
    msg["References"]  = original["id"]
    msg.set_content(reply_text)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": original["threadId"]}
    ).execute()

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────
def run_email_poller():
    last_hid = load_start_history()
    logger.info("Starting poll loop from historyId %s", last_hid)

    while True:
        try:
            msg_ids, last_hid = get_new_message_ids(last_hid)
            if msg_ids:
                logger.info("Found %d new message(s)", len(msg_ids))

            for mid in msg_ids:
                # skip your own replies
                meta = gmail.users().messages().get(
                    userId="me", id=mid, format="metadata"
                ).execute()
                if "SENT" in meta.get("labelIds", []):
                    continue

                msg = fetch_message(mid)
                body = get_plain_body(msg)
                user_text, forwarded_text = split_user_and_forward(body)

                logger.info("User text      : %r", user_text)
                logger.info("Forwarded text : %r", forwarded_text)

                answer = generate_reply(user_text, forwarded_text)
                send_reply(msg, answer)
                logger.info("Replied to message %s", mid)

            save_history_id(last_hid)
        except Exception as e:
            logger.exception("Error during poll loop: %s", e)

        time.sleep(POLL_INTERVAL_S)

