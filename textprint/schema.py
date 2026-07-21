"""Normalized data model shared across parsers, stats, and rendering."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    ts: datetime
    sender: str          # contact display name, or "Me"
    is_me: bool
    text: str
    tapbacks: list = field(default_factory=list)   # [{"kind": str, "by": str}] (IG reactions too)
    reply_to: Optional[str] = None                 # guid of the message this replies to
    kind: str = "text"   # text | reel | post | share | photo | video | gif | call | audio
    meta: dict = field(default_factory=dict)       # e.g. {"link":..., "owner":..., "seconds":...}


@dataclass
class Conversation:
    name: str            # 1-on-1: the contact's name; group: a label
    file: str
    is_group: bool
    participants: list    # sender names other than "Me"
    messages: list        # list[Message], sorted by ts
    name_changes: list = field(default_factory=list)   # [{ts, who, name}] for group renames

    @property
    def mine(self):
        return [m for m in self.messages if m.is_me and m.text]

    @property
    def theirs(self):
        return [m for m in self.messages if not m.is_me and m.text]
