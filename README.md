# Textprint

Turn an **iMessage or Instagram export** into a **narrated report** about how you text — not just charts, but an actual written read of each relationship and your overall style. The analysis runs **on your machine** with a local LLM (Ollama). No cloud, no API keys, no data leaving your computer.

Most "texting stats" tools stop at numbers. Textprint feeds those numbers **plus real sampled conversations** to a local language model, which reads them the way a person would and writes the analysis — the shape of each relationship, how your style shifts per person, what you talk about, and the quality of the exchanges. It surfaces the *revealing* stuff: reply-time asymmetry, who chases whom, relationship arcs, reaction fingerprints, and — for Instagram — the "we don't talk, we just send each other reels" dynamic.

The report is an **iPhone-style home screen**: a Messages app and an Instagram app, each with dashboards (Overview / People / Groups / You) and a paced "Wrapped" reveal.

## How it works

```
export ──▶ parse ──▶ stats (deterministic) ──▶ sample ──▶ interpret (local LLM) ──▶ report
```

The LLM only ever sees a compact **stats dossier** and a handful of **sampled conversations** per contact (map-reduce), so it works on a modest local model and scales to years of history — cost grows with your number of contacts, not messages.

## CLI

```bash
pip install -e .
# local model backend:  install Ollama (https://ollama.com), then:  ollama pull qwen2.5:14b

# iMessage (imessage-exporter HTML):
textprint analyze ./export --model qwen2.5:14b --out report.html

# add Instagram (Download your information → Messages → JSON):
textprint analyze ./export --ig-export ".../your_instagram_activity/messages"
```

Open `report.html` — a single self-contained file.

## Web version (share it with friends)

The `docs/` folder is a **static site** that does the *entire* parse + stats in the visitor's
browser via [Pyodide](https://pyodide.org) — **their export never leaves their device**. Only
the AI "reads" need a model, so the site sends a few *sampled* messages to a small proxy in
front of your home Ollama, and the reads **stream into the report** as they're written. When the
host is offline, visitors still get the whole report — just without the prose.

```
[ friend's browser ]                        [ your PC, behind a Cloudflare tunnel ]
 unzip + parse + stats + render             server/proxy.py  →  local Ollama
 report shown in ~seconds                   (CORS-locked, queue, timeouts, token)
        └────── sampled snippets ──▶ reads stream back ──┘
```

Run the host:

```bash
cd server
pip install -r requirements.txt
export TEXTPRINT_MODEL=gemma4:26b
export TEXTPRINT_ORIGINS=https://<you>.github.io   # your Pages origin
uvicorn proxy:app --host 127.0.0.1 --port 8100
cloudflared tunnel --url http://127.0.0.1:8100     # paste the https URL into the site
```

See [`server/README.md`](server/README.md) for all options. Rebuild the browser bundle after
editing any analysis module: `python build_web.py` (copies the stdlib-only modules into
`docs/pysrc/`, stubbing out the BeautifulSoup-only iMessage parser).

## Privacy

- **Parsing + every statistic run on-device** — CLI on your machine, web version in the visitor's browser.
- The only thing that ever leaves a device is a handful of *sampled* messages, and only to a
  model host you control (your local Ollama). No telemetry, no third-party calls beyond loading
  the Pyodide/JSZip runtimes from a CDN.

## Layout

```
textprint/     analysis engine (parsers, stats, interpret, render)
server/        FastAPI narration proxy for the web version
docs/          static browser app (GitHub Pages) + generated pysrc/ bundle
build_web.py   assembles docs/pysrc from the package
```

## Status

v0.1 — iMessage HTML + Instagram JSON input, Ollama backend, browser (Pyodide) deploy.
Planned: raw macOS `chat.db` input, LLM-picked highlights + member reads in the web version,
cloud provider adapters, redaction mode.

MIT licensed.
