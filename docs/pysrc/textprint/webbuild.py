"""Browser (Pyodide) entry point.

Runs the ENTIRE deterministic pipeline — parse + stats + render — with zero LLM
calls, and returns the report HTML (narration left as streaming placeholders)
plus a list of narration *jobs*. The host page runs the jobs against the Ollama
proxy and streams each read back into the report via postMessage.

Kept dependency-light on purpose: the Instagram path is pure-stdlib so it loads
in Pyodide with no wheels.
"""
from datetime import date

from .ig_stats import ig_dossier, ig_overview, ig_wrapped
from .interpret import (group_prompt, highlight_prompt, ig_prompt, members_prompt,
                        persona_prompt, synth_prompt)
from .parsers.instagram import parse_instagram_json
from .render import build_data
from .sampler import member_message_samples, sample_exchanges
from .stats import global_dossier

ACCENT = "#E1306C"


def _highlight_job(convo, slot):
    """A 'pick the standout messages' job. Carries the candidate `pool` so the
    browser can turn the model's index picks back into highlight cards."""
    txt = [m for m in convo.messages if m.text and len(m.text.split()) >= 2]
    if len(txt) < 10:
        return None
    reacted = [m for m in txt if m.tapbacks][:8]
    step = max(1, len(txt) // 36)
    seen, pool = set(), []
    for m in reacted + txt[::step]:
        if id(m) not in seen:
            seen.add(id(m))
            pool.append(m)
    pool = sorted(pool, key=lambda m: m.ts)[:40]
    if len(pool) < 6:
        return None
    numbered = [(i, f"{'You' if m.is_me else m.sender}: {m.text[:140]}") for i, m in enumerate(pool)]
    system, prompt = highlight_prompt(numbered)
    poolmeta = [{"text": m.text[:400], "who": "You" if m.is_me else m.sender, "me": m.is_me,
                 "date": m.ts.date().isoformat(), "react": [t["kind"] for t in m.tapbacks][:4]}
                for m in pool]
    return {"slot": slot, "system": system, "prompt": prompt, "temperature": 0.5,
            "max_tokens": 140, "post": "highlights", "pool": poolmeta}


def _member_reads_job(convo, gi):
    ms = member_message_samples(convo)
    if not ms:
        return None
    system, prompt = members_prompt(convo.name, ms)
    return {"slot": {"app": "instagram", "kind": "member_reads", "idx": gi},
            "system": system, "prompt": prompt, "temperature": 0.5, "max_tokens": 360,
            "post": "member_reads"}


def _act(c):
    return sum(1 for m in c.messages if m.is_me)   # counts reels too (IG-fair)


def _brief(d):
    """Deterministic one-line brief per contact for the synopsis prompt (no LLM
    dependency, so the synopsis can stream independently of the per-contact reads)."""
    return (f"{d['name']} — {d['n_total']} msgs, you {d['you_share']}%, "
            f"{d['wpm_me']} w/msg, starts you {d['starts_me']}/them {d['starts_them']}, "
            f"tag {d['tag']}")


def build_ig(threads, name="You", title="Textprint", min_date=None,
             min_messages=25, limit=20, group_limit=6, samples=5):
    """threads: list of (folder_name, thread_dict). Returns a JSON-able dict:
    {html, jobs, stats}. jobs: [{slot, system, prompt, temperature, max_tokens, dep?}]."""
    convos = parse_instagram_json(threads)
    if min_date:
        for c in convos:
            c.messages = [m for m in c.messages if m.ts.isoformat()[:10] >= min_date]
        convos = [c for c in convos if c.messages]
    if not convos:
        return {"html": "", "jobs": [], "stats": {"error": "no conversations found"}}

    people_all = sorted([c for c in convos if not c.is_group and _act(c) >= min_messages],
                        key=lambda c: -_act(c))
    groups = sorted([c for c in convos if c.is_group and _act(c) >= max(10, min_messages // 2)],
                    key=lambda c: -_act(c))[:group_limit]
    people = people_all[:limit] if limit else people_all
    if not people:
        return {"html": "", "jobs": [], "stats": {"error": "no contacts met the threshold"}}

    overview = ig_overview(convos)
    months = overview["months"]
    now_date = max((m.ts.date() for c in convos for m in c.messages), default=date.today())
    dossiers = [ig_dossier(c, months) for c in people_all]
    wrapped = ig_wrapped(people_all, dossiers, overview, now_date)

    jobs = []
    people_data = []
    for i, c in enumerate(people):
        d = dossiers[i]
        sm = sample_exchanges(c, n=samples)
        system, prompt = ig_prompt(d, sm)
        jobs.append({"slot": {"app": "instagram", "kind": "person", "idx": i},
                     "system": system, "prompt": prompt, "temperature": 0.4, "max_tokens": 520})
        hl = _highlight_job(c, {"app": "instagram", "kind": "highlights", "target": "person", "idx": i})
        if hl:
            jobs.append(hl)
        people_data.append({"idx": i, "dossier": d, "narrative": ""})

    groups_data = []
    for i, c in enumerate(groups):
        d = ig_dossier(c, months)
        sm = sample_exchanges(c, n=samples)
        system, prompt = group_prompt(d, sm)
        jobs.append({"slot": {"app": "instagram", "kind": "group", "idx": i},
                     "system": system, "prompt": prompt, "temperature": 0.4, "max_tokens": 520})
        hl = _highlight_job(c, {"app": "instagram", "kind": "highlights", "target": "group", "idx": i})
        if hl:
            jobs.append(hl)
        mr = _member_reads_job(c, i)
        if mr:
            jobs.append(mr)
        groups_data.append({"idx": i, "dossier": d, "narrative": "", "member_reads": {}})

    # synopsis (deterministic briefs → independent) then persona (depends on synopsis)
    briefs = [_brief(dossiers[i]) for i in range(len(people))]
    s_sys, s_prompt = synth_prompt(global_dossier(people_all), briefs)
    jobs.append({"slot": {"app": "instagram", "kind": "synopsis"},
                 "system": s_sys, "prompt": s_prompt, "temperature": 0.6, "max_tokens": 620})
    p_sys, _ = persona_prompt("")
    jobs.append({"slot": {"app": "instagram", "kind": "persona"},
                 "system": p_sys, "prompt": "How they text:\n{{SYNOPSIS}}",
                 "temperature": 0.6, "max_tokens": 90, "dep": "synopsis"})

    persona = {"title": "Reading your DMs…", "blurb": ""}
    data = build_data(name, overview, persona, people_data, groups_data, "", wrapped, "instagram")
    app = {"id": "instagram", "name": "Instagram", "accent": ACCENT, "data": data}
    return {"apps": [app], "name": name or "You", "jobs": jobs,
            "stats": {"people": len(people), "groups": len(groups),
                      "people_total": len(people_all), "reads": len(jobs)}}
