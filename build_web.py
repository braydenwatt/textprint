"""Assemble docs/pysrc/ — the pure-stdlib Python the browser (Pyodide) needs.

Copies only the Instagram-path modules and writes a STUB parsers/__init__.py so
importing the IG parser never pulls in BeautifulSoup (the iMessage-only dep).
Run after editing any copied module:  python build_web.py
GitHub Pages serves the site from docs/.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent            # repo root (.../textprint)
PKG = ROOT / "textprint"
OUT = ROOT / "docs" / "pysrc" / "textprint"

MODULES = ["__init__.py", "schema.py", "stats.py", "ig_stats.py", "wrapped.py",
           "sampler.py", "interpret.py", "render.py", "webbuild.py"]
PARSERS = ["instagram.py"]

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "parsers").mkdir(exist_ok=True)

# GitHub Pages runs Jekyll, which drops files whose names start with "_"
# (e.g. __init__.py) -> they 404. .nojekyll disables that so all files serve.
(ROOT / "docs" / ".nojekyll").write_text("", encoding="utf-8")

for m in MODULES:
    src = PKG / m
    if src.exists():
        shutil.copy2(src, OUT / m)
    elif m == "__init__.py":
        (OUT / "__init__.py").write_text("", encoding="utf-8")

for m in PARSERS:
    shutil.copy2(PKG / "parsers" / m, OUT / "parsers" / m)

# stub package init — no html_export/bs4 import in the browser
(OUT / "parsers" / "__init__.py").write_text(
    '"""Browser stub — only the in-memory Instagram parser is loaded here."""\n', encoding="utf-8")

manifest = ["textprint/" + m for m in MODULES] + ["textprint/parsers/__init__.py",
            "textprint/parsers/instagram.py"]
(OUT.parent / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
print(f"assembled {len(manifest)} modules into {OUT}")
