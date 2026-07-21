"""Parser for imessage-exporter HTML exports -> list[Conversation].

Handles: sent/received bubbles, sender labels, timestamps, tapback reactions,
edited-message final versions, threaded replies (deduped by guid), and drops
attachment/app-only and URL-only messages.
"""
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from ..schema import Conversation, Message

GUID_RE = re.compile(r"message-guid=([A-F0-9-]+)")
TS_FMT = "%b %d, %Y %I:%M:%S %p"
NAME_CHANGE_RE = re.compile(
    r"^(?P<date>[A-Z][a-z]{2} \d{1,2}, \d{4} \d{1,2}:\d{2}:\d{2} [AP]M) "
    r"(?P<who>.+?) named the conversation (?P<name>.+)$")
URL_ONLY_RE = re.compile(r"^\s*https?://\S+\s*$", re.I)
SMART = {"‘": "'", "’": "'", "“": '"', "”": '"',
         "–": "-", "—": "-", "�": "'", " ": " "}


def clean_text(s):
    for k, v in SMART.items():
        s = s.replace(k, v)
    s = s.replace(" ", "\n").replace(" ", "\n").replace("\r", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def _extract(mdiv, reply_map, parent_guid=None):
    inner = mdiv.find("div", recursive=False)
    if inner is None:
        return None
    classes = inner.get("class", [])
    if "sent" not in classes and "received" not in classes:
        return None
    is_me = "sent" in classes

    guid = ts = None
    tlink = inner.find("a", title="Reveal in Messages app")
    if tlink is not None:
        m = GUID_RE.search(tlink.get("href", ""))
        if m:
            guid = m.group(1)
        try:
            ts = datetime.strptime(re.sub(r"\s+", " ", tlink.get_text()).strip(), TS_FMT)
        except ValueError:
            ts = None
    if guid is None or ts is None:
        return None

    span = inner.find("span", class_="sender")
    sender = span.get_text().strip() if span else ("Me" if is_me else "?")

    nested = []
    for rdiv in inner.find_all("div", class_="replies"):
        for reply in rdiv.find_all("div", class_="reply", recursive=False):
            for sub in reply.find_all("div", class_="message", recursive=False):
                child = _extract(sub, reply_map, parent_guid=guid)
                if child:
                    nested.append(child)
        rdiv.decompose()
    if parent_guid is not None:
        reply_map[guid] = parent_guid

    tapbacks = []
    for tb in inner.find_all("div", class_="tapbacks"):
        for sp in tb.find_all("span", class_="tapback"):
            txt = re.sub(r"\s+", " ", sp.get_text()).strip()
            if " by " in txt:
                kind, by = txt.rsplit(" by ", 1)
                tapbacks.append({"kind": clean_text(kind), "by": by.strip()})
        tb.decompose()

    parts = []
    for part in inner.find_all("div", class_="message_part"):
        edited = part.find("div", class_="edited")
        if edited is not None:
            rows = edited.find_all("tr")
            if rows:
                cells = rows[-1].find_all("td")
                t = cells[-1].get_text() if cells else ""
                if t.strip():
                    parts.append(t)
            continue
        for bub in part.find_all("span", class_="bubble"):
            if bub.get_text().strip():
                parts.append(bub.get_text())
    text = clean_text("\n".join(parts))
    if URL_ONLY_RE.match(text):
        text = ""

    return {"guid": guid, "ts": ts, "sender": sender, "is_me": is_me,
            "text": text, "tapbacks": tapbacks, "nested": nested}


def parse_file(path):
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "lxml")
    if soup.body is None:
        return None
    name_changes = []
    for ann in soup.find_all("div", class_="announcement"):
        txt = re.sub(r"\s+", " ", ann.get_text(" ")).strip()
        mc = NAME_CHANGE_RE.match(txt)
        if mc:
            try:
                ts = datetime.strptime(mc.group("date"), TS_FMT)
            except ValueError:
                continue
            name_changes.append({"ts": ts.isoformat(), "who": clean_text(mc.group("who")).strip(),
                                 "name": clean_text(mc.group("name")).strip()})
    name_changes.sort(key=lambda x: x["ts"])
    reply_map, by_guid = {}, {}
    for mdiv in soup.body.find_all("div", class_="message", recursive=False):
        res = _extract(mdiv, reply_map)
        if res is None:
            continue
        stack = [(res, True)]
        while stack:
            node, top = stack.pop()
            g = node["guid"]
            if g not in by_guid or (top and not by_guid[g][1]):
                by_guid[g] = (node, top)
            for c in node["nested"]:
                stack.append((c, False))

    nodes = sorted((n for n, _ in by_guid.values()), key=lambda n: n["ts"])
    msgs = []
    for n in nodes:
        if not n["text"] and not n["tapbacks"]:
            continue
        msgs.append(Message(ts=n["ts"], sender=n["sender"], is_me=n["is_me"],
                            text=n["text"], tapbacks=n["tapbacks"],
                            reply_to=reply_map.get(n["guid"])))
    if not msgs:
        return None
    senders = sorted({m.sender for m in msgs if not m.is_me})
    is_group = len(senders) > 1
    if is_group:
        name = re.sub(r"\s*-\s*\d+$", "", path.stem).strip() or path.stem
    else:
        name = senders[0] if senders else path.stem
    return Conversation(name=name, file=path.name, is_group=is_group,
                        participants=senders, messages=msgs, name_changes=name_changes)


def parse_export(export_dir, exclude=None):
    """Parse every .html in export_dir. `exclude` = set of filenames to skip."""
    exclude = exclude or set()
    convos = []
    for p in sorted(Path(export_dir).glob("*.html")):
        if p.name in exclude:
            continue
        c = parse_file(p)
        if c:
            convos.append(c)
    return convos
