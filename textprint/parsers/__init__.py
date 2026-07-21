"""Input adapters. Each returns list[Conversation] in the normalized schema.

Currently: imessage-exporter HTML. Add chat.db / other formats here later —
the rest of the pipeline only depends on the schema, not the source.
"""
from .html_export import parse_export

__all__ = ["parse_export"]
