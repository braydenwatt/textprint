"""Local Ollama provider (default). Talks to the Ollama HTTP API on localhost.

No third-party dependency — uses urllib. Start Ollama with `ollama serve` and
pull a model, e.g. `ollama pull qwen2.5:14b`. Nothing leaves your machine.
"""
import json
import urllib.error
import urllib.request

from .base import LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, model="qwen2.5:14b", host="http://localhost:11434", timeout=900, think=False):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.think = think          # reasoning models otherwise spend all tokens "thinking"

    def _post(self, path, payload):
        req = urllib.request.Request(
            self.host + path, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())

    def complete(self, system, prompt, temperature=0.4, max_tokens=700):
        payload = {
            "model": self.model, "stream": False, "think": self.think,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            data = self._post("/api/chat", payload)
        except urllib.error.HTTPError:
            payload.pop("think", None)   # model doesn't accept the think flag
            data = self._post("/api/chat", payload)
        msg = data.get("message", {})
        out = (msg.get("content") or "").strip()
        # some reasoning models still stream into 'thinking' — salvage it if content is empty
        if not out and msg.get("thinking"):
            out = msg["thinking"].strip()
        return out

    def check(self):
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=5) as r:
                tags = json.loads(r.read())
            names = [m["name"] for m in tags.get("models", [])]
            have = any(self.model.split(":")[0] in n for n in names)
            return (f"ollama up · model '{self.model}' "
                    + ("available" if have else f"NOT pulled (have: {', '.join(names) or 'none'})"))
        except urllib.error.URLError:
            return "ollama NOT reachable — run `ollama serve` and pull a model"
