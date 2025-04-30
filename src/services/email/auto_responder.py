# services/email/auto_responder.py
import asyncio, base64, email, logging, pathlib, time
from typing import Tuple, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from talon import quotations
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# ---------- tiny helpers ---------- #
def _load_creds(creds_path: str, token_path: str) -> Credentials:
    from google_auth_oauthlib.flow import InstalledAppFlow

    if pathlib.Path(token_path).exists():
        return Credentials.from_authorized_user_file(token_path, SCOPES)

    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=0)
    pathlib.Path(token_path).write_text(creds.to_json())
    return creds

def _get_plain_body(msg: dict) -> str:
    for part in msg["payload"].get("parts", []):
        if part["mimeType"] == "text/plain":
            return base64.urlsafe_b64decode(part["body"]["data"]).decode()
        if part["mimeType"] == "text/html":
            html = base64.urlsafe_b64decode(part["body"]["data"]).decode()
            return BeautifulSoup(html, "html.parser").get_text("\n")
    return ""

def _split(body: str) -> Tuple[str, str]:
    fresh = quotations.extract_from(body, lines_till_signature=1000).strip()
    quoted = body.replace(fresh, "", 1).strip()
    return fresh, quoted


############### TO DO ###############
async def dummy_llm(user_text: str, fwd_text: str) -> str:
    # TODO: replace with your real model call
    # NEED TO CONNECT IT TO ACTUAL LLM, user and fwd are the user message and the forwarded message respectively
    # the user message is the query and the forwarded message is the context
    return user_text


# ---------- the poll loop ---------- #
async def start_gmail_poll(
    creds_path: str,
    token_path: str,
    llm_callback,               # async def gen_reply(user, fwd) -> str
    poll_interval: int = 30
):
    """Run forever as an asyncio Task."""
    creds  = _load_creds(creds_path, token_path)
    gmail  = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile = gmail.users().getProfile(userId="me").execute()
    last_hid = profile["historyId"]
    logger.info("Gmail poller started at historyId %s", last_hid)

    while True:
        try:
            resp = gmail.users().history().list(
                userId="me",
                startHistoryId=last_hid,
                historyTypes=["messageAdded"]
            ).execute()
            for h in resp.get("history", []):
                last_hid = h["id"]
                for m in h.get("messagesAdded", []):
                    mid = m["message"]["id"]
                    meta = gmail.users().messages().get(
                        userId="me", id=mid, format="metadata"
                    ).execute()
                    if "SENT" in meta.get("labelIds", []):
                        continue

                    msg   = gmail.users().messages().get(
                        userId="me", id=mid, format="full"
                    ).execute()
                    body  = _get_plain_body(msg)
                    user_txt, fwd_txt = _split(body)

                    answer = await llm_callback(user_txt, fwd_txt)

                    reply = email.message.EmailMessage()
                    hdrs  = {h["name"].lower(): h["value"]
                             for h in msg["payload"]["headers"]}
                    reply["To"]      = hdrs.get("from")
                    reply["Subject"] = "Re: " + hdrs.get("subject", "")
                    reply["In-Reply-To"] = msg["id"]
                    reply["References"]  = msg["id"]
                    reply.set_content(answer or "hello world")

                    raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
                    gmail.users().messages().send(
                        userId="me",
                        body={"raw": raw, "threadId": msg["threadId"]}
                    ).execute()
                    logger.info("Replied to %s", mid)

            await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.exception("Gmail poller error: %s", e)
            await asyncio.sleep(poll_interval)
