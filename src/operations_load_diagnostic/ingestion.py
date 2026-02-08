from __future__ import annotations

import csv
import email
import imaplib
import re
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path
from typing import Iterable

from .models import InboundItem


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    # Handle common "Z" suffix.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ]
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def limit_items(
    items: Iterable[InboundItem],
    lookback_days: int = 14,
    max_items: int = 200,
) -> list[InboundItem]:
    now = datetime.now()
    threshold = now - timedelta(days=lookback_days)
    filtered: list[InboundItem] = []

    for item in items:
        if item.timestamp and item.timestamp < threshold:
            continue
        filtered.append(item)

    filtered.sort(key=lambda x: x.timestamp or now, reverse=True)
    return filtered[:max_items]


def ingest_csv(path: str | Path) -> list[InboundItem]:
    path = Path(path)
    items: list[InboundItem] = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            items.append(
                InboundItem(
                    item_id=f"csv-{idx}",
                    timestamp=parse_timestamp(row.get("timestamp")),
                    sender=(row.get("sender") or "").strip() or None,
                    subject=(row.get("subject") or "").strip(),
                    body=(row.get("body") or "").strip(),
                    source="csv",
                )
            )
    return items


def _extract_prefixed_line(block: str, prefix: str) -> str | None:
    for line in block.splitlines():
        if line.lower().startswith(prefix.lower()):
            return line.split(":", 1)[1].strip() if ":" in line else None
    return None


def ingest_text_batch(path: str | Path) -> list[InboundItem]:
    """
    Batch format:
    - Split messages with a line containing only ---
    - Optional headers in each block:
      timestamp: 2026-02-01 09:30
      sender: someone@company.com
      subject: Status for shipment 123
      body:
      Please share ETA...
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    raw_blocks = [b.strip() for b in re.split(r"(?m)^\s*---\s*$", text) if b.strip()]
    items: list[InboundItem] = []

    for idx, block in enumerate(raw_blocks, start=1):
        timestamp = parse_timestamp(_extract_prefixed_line(block, "timestamp"))
        sender = _extract_prefixed_line(block, "sender")
        subject = _extract_prefixed_line(block, "subject") or ""

        body = ""
        body_marker = re.search(r"(?im)^body\s*:\s*$", block)
        if body_marker:
            body = block[body_marker.end() :].strip()
        else:
            body = block.strip()

        if not subject:
            first_line = body.splitlines()[0] if body else ""
            subject = (first_line[:80] + "...") if len(first_line) > 80 else first_line

        items.append(
            InboundItem(
                item_id=f"text-{idx}",
                timestamp=timestamp,
                sender=sender,
                subject=subject,
                body=body,
                source="text",
            )
        )
    return items


def _decode_mime_header(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    return str(make_header(decode_header(raw_value)))


def _extract_text_body(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", "")).lower()
            if content_type == "text/plain" and "attachment" not in disposition:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                try:
                    return payload.decode(charset, errors="replace")
                except LookupError:
                    return payload.decode("utf-8", errors="replace")
    payload = msg.get_payload(decode=True) or b""
    charset = msg.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def ingest_imap(
    host: str,
    username: str,
    password: str,
    folder: str = "INBOX",
    lookback_days: int = 14,
    max_items: int = 200,
) -> list[InboundItem]:
    """
    Read-only IMAP fetch for recent inbound messages.
    """
    client = imaplib.IMAP4_SSL(host)
    client.login(username, password)
    client.select(folder, readonly=True)

    since_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")
    status, data = client.search(None, f'(SINCE "{since_date}")')
    if status != "OK" or not data or not data[0]:
        client.logout()
        return []

    message_ids = data[0].split()[-max_items:]
    items: list[InboundItem] = []

    for idx, msg_id in enumerate(message_ids, start=1):
        fetch_status, msg_data = client.fetch(msg_id, "(RFC822)")
        if fetch_status != "OK" or not msg_data:
            continue
        raw_email = msg_data[0][1]
        if not raw_email:
            continue
        msg = email.message_from_bytes(raw_email)
        subject = _decode_mime_header(msg.get("Subject"))
        sender = _decode_mime_header(msg.get("From")) or None
        date_raw = msg.get("Date")
        timestamp = None
        if date_raw:
            try:
                timestamp = email.utils.parsedate_to_datetime(date_raw)
            except (TypeError, ValueError):
                timestamp = None
        body = _extract_text_body(msg).strip()
        items.append(
            InboundItem(
                item_id=f"imap-{idx}",
                timestamp=timestamp,
                sender=sender,
                subject=subject,
                body=body,
                source="imap",
            )
        )

    client.logout()
    items.sort(key=lambda x: x.timestamp or datetime.now(), reverse=True)
    return items[:max_items]
