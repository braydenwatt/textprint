"""Textprint narration proxy.

The public site does ALL parsing + stats in the visitor's browser. The one thing
it can't do locally is run the LLM, so it POSTs a few *sampled* exchanges here and
this proxy relays them to your local Ollama and returns the prose. The raw export
never reaches this server — only samples + prompts.

Hardened for internet exposure via a Cloudflare tunnel:
  * CORS locked to your site origin(s)
  * global concurrency = 1 (one GPU, serialized) behind a bounded wait queue
  * per-request timeout + prompt-size caps
  * optional shared-secret token

Run:
    pip install -r requirements.txt
    # optional overrides:
    set TEXTPRINT_ORIGINS=https://your-site.pages.dev
    set TEXTPRINT_MODEL=gemma3:27b
    set TEXTPRINT_TOKEN=some-shared-secret
    uvicorn proxy:app --host 127.0.0.1 --port 8100

Then point a Cloudflare tunnel at 127.0.0.1:8100:
    cloudflared tunnel --url http://127.0.0.1:8100
"""
import asyncio
import os
import pathlib
import sys
import time

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# reuse the exact Ollama handling (think:false fallback + thinking salvage)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from textprint.providers.ollama import OllamaProvider

# ── config (all overridable by env) ─────────────────────────────────────────
ORIGINS = [o.strip() for o in os.environ.get(
    "TEXTPRINT_ORIGINS",
    "https://braydenwatt.github.io,http://localhost:8014,http://127.0.0.1:8014,http://localhost:5173").split(",") if o.strip()]
MODEL = os.environ.get("TEXTPRINT_MODEL", "qwen2.5:14b")
OLLAMA_HOST = os.environ.get("TEXTPRINT_OLLAMA", "http://localhost:11434")
TOKEN = os.environ.get("TEXTPRINT_TOKEN", "")          # "" disables the check
MAX_QUEUE = int(os.environ.get("TEXTPRINT_MAX_QUEUE", "12"))   # reject when this many are in flight
REQ_TIMEOUT = int(os.environ.get("TEXTPRINT_TIMEOUT", "120"))  # seconds per completion
MAX_PROMPT = int(os.environ.get("TEXTPRINT_MAX_PROMPT", "24000"))
MAX_SYSTEM = 8000

provider = OllamaProvider(model=MODEL, host=OLLAMA_HOST, timeout=REQ_TIMEOUT)

app = FastAPI(title="Textprint narration proxy", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"], allow_credentials=False, max_age=600)

# one GPU → serialize every completion across all visitors; cap how many may wait
_gpu = asyncio.Semaphore(1)
_inflight = 0


class CompleteIn(BaseModel):
    system: str = Field(..., max_length=MAX_SYSTEM)
    prompt: str = Field(..., max_length=MAX_PROMPT)
    temperature: float = Field(0.4, ge=0.0, le=1.5)
    max_tokens: int = Field(700, ge=16, le=1200)


def _check_token(authorization: str):
    if TOKEN and authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "bad or missing token")


@app.get("/health")
async def health():
    status = await asyncio.to_thread(provider.check)
    return {"ok": status.startswith("ollama up"), "status": status,
            "model": MODEL, "inflight": _inflight, "max_queue": MAX_QUEUE}


@app.post("/complete")
async def complete(body: CompleteIn, authorization: str = Header(default="")):
    _check_token(authorization)
    global _inflight
    if _inflight >= MAX_QUEUE:
        raise HTTPException(429, "host busy — try again shortly",
                            headers={"Retry-After": "30"})
    _inflight += 1
    try:
        async with _gpu:                       # one at a time
            t0 = time.time()
            try:
                text = await asyncio.wait_for(
                    asyncio.to_thread(provider.complete, body.system, body.prompt,
                                      body.temperature, body.max_tokens),
                    timeout=REQ_TIMEOUT)
            except asyncio.TimeoutError:
                raise HTTPException(504, "model timed out")
            except HTTPException:
                raise
            except Exception as e:             # ollama down / model missing / etc.
                raise HTTPException(502, f"ollama error: {e}")
            if not text:
                raise HTTPException(502, "model returned empty output")
            return {"text": text, "ms": int((time.time() - t0) * 1000)}
    finally:
        _inflight -= 1


@app.get("/info")
async def info():
    return {"service": "textprint-narration-proxy", "model": MODEL,
            "origins": ORIGINS, "token_required": bool(TOKEN)}


# Serve the app itself from the proxy too, so the whole thing can run over plain
# HTTP on one origin (e.g. over Tailscale) — same-origin, no HTTPS/CORS needed.
# The phone opens http://<host>:<port>/ and reads go to /complete on the same origin.
_DOCS = pathlib.Path(__file__).resolve().parents[1] / "docs"
if _DOCS.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_DOCS), html=True), name="app")


if __name__ == "__main__":
    import uvicorn
    print(f"[textprint proxy] model={MODEL} origins={ORIGINS} "
          f"token={'on' if TOKEN else 'off'} max_queue={MAX_QUEUE}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8100")))
