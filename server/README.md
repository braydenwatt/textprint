# Textprint narration proxy

The public site parses the Instagram export and computes **every stat in the
visitor's browser**. The only thing it can't do locally is run the LLM, so it
sends a few *sampled* exchanges to this proxy, which relays them to your local
Ollama and returns the prose. **The raw export never reaches this server** — only
samples + prompts.

Because the stats are client-side, the site stays fully useful even when this
proxy is offline: visitors still get the whole report, and the narration cards
just say the host's machine is asleep.

## Run

```bash
pip install -r requirements.txt

# Ollama must be running with a model pulled:
ollama serve
ollama pull gemma4:26b

# start the proxy (defaults shown; all overridable by env):
export TEXTPRINT_MODEL=gemma4:26b
export TEXTPRINT_ORIGINS=https://your-site.pages.dev   # the deployed site's origin
export TEXTPRINT_TOKEN=some-shared-secret              # optional; blank disables
uvicorn proxy:app --host 127.0.0.1 --port 8100
```

## Expose it — over Tailscale (recommended for personal / phone use)

If your devices are on [Tailscale](https://tailscale.com), you can reach the proxy
from your phone privately over your tailnet — HTTPS, stable hostname, no public
tunnel. Bind Ollama to all interfaces once (`OLLAMA_HOST=0.0.0.0`), then:

```powershell
cd server
.\start_tailscale.ps1        # starts the proxy + Tailscale Serve
```

One-time: it will print a link if **Tailscale Serve** isn't enabled on your
tailnet yet — click it (one toggle), then re-run. It then prints your stable URL,
e.g. `https://homepc.<tailnet>.ts.net`. On your phone (Tailscale app connected to
the same tailnet), open the Textprint site and paste that URL into "Ollama proxy
URL". Because the site's origin is still the same, the existing CORS allowlist
already covers it — no config change needed.

Private to your tailnet only. To share with people who aren't on your tailnet,
use the Cloudflare tunnel below instead (or `tailscale funnel` to go public).

## Expose it — stable URL via a named tunnel

A **named tunnel** gives you a permanent hostname (e.g. `https://textprint.yourdomain.com`)
instead of a random URL that changes every restart. Two PowerShell scripts automate it.

Prereqs (one-time, yours): a domain on Cloudflare (free plan is fine) and
`winget install Cloudflare.cloudflared`.

```powershell
cd server
# one-time: logs in (browser), creates the tunnel, writes config, routes DNS
.\setup_tunnel.ps1 -Hostname textprint.yourdomain.com

# every day after: starts the proxy + tunnel together (Ctrl+C stops both)
.\start.ps1
# .\start.ps1 -Model qwen2.5:14b -Token my-secret
```

`start.ps1` prints your public URL — paste it into the site's "Ollama proxy URL" box.

### Quick tunnel (no domain, throwaway URL)

```bash
cloudflared tunnel --url http://127.0.0.1:8100
```

Gives a `https://<random>.trycloudflare.com` URL that changes each run.

## Config (env vars)

| var | default | meaning |
|---|---|---|
| `TEXTPRINT_MODEL` | `qwen2.5:14b` | Ollama model to narrate with |
| `TEXTPRINT_ORIGINS` | localhost dev origins | comma-separated CORS allowlist |
| `TEXTPRINT_OLLAMA` | `http://localhost:11434` | Ollama host |
| `TEXTPRINT_TOKEN` | `` (off) | shared secret; clients send `Authorization: Bearer <token>` |
| `TEXTPRINT_MAX_QUEUE` | `12` | reject with 429 when this many requests are in flight |
| `TEXTPRINT_TIMEOUT` | `120` | seconds per completion before 504 |
| `TEXTPRINT_MAX_PROMPT` | `24000` | reject prompts longer than this (chars) |

## Endpoints

- `GET /health` → `{ok, status, model, inflight, max_queue}`
- `POST /complete` → body `{system, prompt, temperature?, max_tokens?}` → `{text, ms}`
  - `401` bad/missing token · `429` busy · `504` model timeout · `502` ollama error

## Hardening notes

- Only `/complete` and `/health` are exposed; **raw Ollama (11434) is never
  tunneled** — the proxy is the only door, and it validates + size-caps input.
- CORS is locked to `TEXTPRINT_ORIGINS`; other origins get no allow header.
- `TEXTPRINT_TOKEN` keeps casual scanners off your GPU. For a friends tool the
  token can live in the site config (soft protection); rotate it if abused.
- Concurrency is globally 1 (one GPU). Requests serialize; excess sheds at 429.
