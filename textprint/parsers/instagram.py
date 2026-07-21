"""Parser for an Instagram data export (your_instagram_activity/messages).

IG DMs aren't mostly words — they're content passed back and forth. This maps
each thread's message_1.json into the normalized schema, tagging every message
with a `kind` (text / reel / post / photo / …) and folding IG reactions into
the same `tapbacks` slot iMessage uses. Text is mojibake-encoded (latin-1 over
utf-8) and is repaired on the way in.
"""
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from ..schema import Conversation, Message

# Instagram auto-generates activity lines as message `content` — a message-like,
# a reaction, or an unavailable-message placeholder. These are NOT typed words and
# must never reach the word/emoji stats. Anchored so real messages that merely
# contain "liked"/"message" (e.g. "bro stop ignoring my messages") are kept.
_SYSTEM_RE = re.compile(
    r"^(?:.+ )?liked a message\s*$"          # "Liked a message", "x liked a message"
    r"|^reacted\b.*\bto your message\s*$"     # "Reacted 😭 to your message"
    r"|^message unavailable\s*$",             # deleted / unavailable placeholder
    re.IGNORECASE)


def _is_system(content):
    return bool(content) and bool(_SYSTEM_RE.match(content))


def _fix(s):
    """IG exports double-encode utf-8 as latin-1; undo it."""
    if not s:
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _kind(m):
    sh = m.get("share")
    if sh:
        link = sh.get("link", "")
        if "/reel/" in link:
            return "reel", {"link": link, "owner": _fix(sh.get("original_content_owner", ""))}
        if "/p/" in link:
            return "post", {"link": link, "owner": _fix(sh.get("original_content_owner", ""))}
        return "share", {"link": link, "owner": _fix(sh.get("original_content_owner", ""))}
    if m.get("photos"):
        return "photo", {}
    if m.get("videos"):
        return "video", {}
    if m.get("gifs"):
        return "gif", {}
    if m.get("audio_files"):
        return "audio", {}
    if "call_duration" in m:
        return "call", {"seconds": m.get("call_duration", 0)}
    return "text", {}


def _detect_me(inbox):
    pc = Counter()
    for f in inbox.glob("*/message_1.json"):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for p in j.get("participants", []):
            pc[_fix(p.get("name", ""))] += 1
    return pc.most_common(1)[0][0] if pc else "Me"


def parse_thread(path, me):
    return parse_thread_json(json.loads(path.read_text(encoding="utf-8")), me, path.parent.name)


def parse_thread_json(j, me, folder=""):
    """Core: an already-loaded thread dict -> Conversation. Shared by the file
    parser and the in-browser (Pyodide) path, which has no filesystem."""
    parts = [_fix(p.get("name", "")) for p in j.get("participants", [])]
    others = [p for p in parts if p != me]
    is_group = len(others) > 1
    title = _fix(j.get("title", "")) or (others[0] if others else folder)
    name = title if is_group else (others[0] if others else title)

    msgs = []
    for m in j.get("messages", []):
        sender = _fix(m.get("sender_name", ""))
        if not sender:
            continue
        ts = datetime.fromtimestamp(m.get("timestamp_ms", 0) / 1000)
        kind, meta = _kind(m)
        content = _fix(m.get("content", ""))
        # only real typed words count as text; system "sent an attachment.",
        # "Liked a message", "Reacted 😭 to your message" etc. are not words
        text = content if (kind == "text" and content and not content.endswith("attachment.")
                           and "shared" not in content[:20] and not _is_system(content)) else ""
        tapbacks = [{"kind": _fix(r.get("reaction", "")),
                     "by": "Me" if _fix(r.get("actor", "")) == me else _fix(r.get("actor", ""))}
                    for r in m.get("reactions", [])]
        if kind == "text" and not text and not tapbacks:
            continue
        msgs.append(Message(ts=ts, sender=sender, is_me=(sender == me), text=text,
                            tapbacks=tapbacks, kind=kind, meta=meta))
    msgs.sort(key=lambda m: m.ts)
    if not msgs:
        return None
    return Conversation(name=name, file=folder, is_group=is_group,
                        participants=sorted(set(others)), messages=msgs)


def parse_instagram(export_dir, exclude=None):
    """export_dir points at .../messages (containing an `inbox/` folder)."""
    exclude = exclude or set()
    root = Path(export_dir)
    inbox = root / "inbox" if (root / "inbox").is_dir() else root
    me = _detect_me(inbox)
    convos = []
    for thread in sorted(inbox.iterdir()):
        f = thread / "message_1.json"
        if not f.exists() or thread.name in exclude:
            continue
        c = parse_thread(f, me)
        if c:
            convos.append(c)
    return convos


def parse_instagram_json(threads, exclude=None):
    """In-memory variant for the browser. `threads` = list of (folder_name, data_dict),
    one per inbox/<thread>/message_1.json. No filesystem access."""
    exclude = exclude or set()
    pc = Counter()
    for _, j in threads:
        for p in j.get("participants", []):
            pc[_fix(p.get("name", ""))] += 1
    me = pc.most_common(1)[0][0] if pc else "Me"
    convos = []
    for folder, j in sorted(threads, key=lambda t: t[0]):
        if folder in exclude:
            continue
        c = parse_thread_json(j, me, folder)
        if c:
            convos.append(c)
    return convos
