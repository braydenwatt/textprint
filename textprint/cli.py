"""Textprint CLI:  textprint analyze <export_dir> [options] -> report.html"""
import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

from .ig_stats import ig_dossier, ig_overview, ig_wrapped
from .interpret import (member_reads, narrate_contact, narrate_group, narrate_ig,
                        personality, pick_highlights, synthesize)
from .parsers import parse_export
from .parsers.instagram import parse_instagram
from .providers import get_provider
from .render import build_data, render_report
from .sampler import member_message_samples, sample_exchanges
from .schema import Conversation
from .stats import contact_dossier, global_dossier, overview_stats
from .wrapped import wrapped_stats

try:
    sys.stdout.reconfigure(encoding="utf-8")   # group/contact names may contain emoji
except Exception:
    pass


def _load_excludes(path):
    if not path or not Path(path).exists():
        return set()
    return {l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")}


def merge_by_contact(convos):
    """A person can span several export files (number change, SMS fallback).
    Merge all 1-on-1 conversations that share a contact name into one."""
    groups, out = defaultdict(list), []
    for c in convos:
        if c.is_group:
            out.append(c)
        else:
            groups[c.name].append(c)
    for name, cs in groups.items():
        msgs = sorted((m for c in cs for m in c.messages), key=lambda m: m.ts)
        parts = sorted({p for c in cs for p in c.participants})
        out.append(Conversation(name=name, file="; ".join(c.file for c in cs),
                                is_group=False, participants=parts, messages=msgs))
    return out


def _date_filter(convos, min_date):
    if min_date:
        for c in convos:
            c.messages = [m for m in c.messages if m.ts.isoformat()[:10] >= min_date]
        convos = [c for c in convos if c.messages]
    return convos


def _add_llm_highlights(provider, convo, d):
    """Ask the LLM to pick standout messages; merge into the dossier's highlights."""
    txt = [m for m in convo.messages if m.text and len(m.text.split()) >= 2]
    if len(txt) < 10:
        return
    reacted = [m for m in txt if m.tapbacks][:8]
    step = max(1, len(txt) // 36)
    seen, pool = set(), []
    for m in reacted + txt[::step]:
        if id(m) not in seen:
            seen.add(id(m))
            pool.append(m)
    pool = sorted(pool, key=lambda m: m.ts)[:40]
    numbered = [(i, f"{'You' if m.is_me else m.sender}: {m.text[:140]}") for i, m in enumerate(pool)]
    picks = pick_highlights(provider, numbered)
    have = {h["text"][:50] for h in d.get("highlights", [])}
    for idx, label in picks:
        if 0 <= idx < len(pool) and pool[idx].text[:50] not in have:
            m = pool[idx]
            have.add(m.text[:50])
            d.setdefault("highlights", []).append(
                {"text": m.text[:400], "who": "You" if m.is_me else m.sender, "me": m.is_me,
                 "date": m.ts.date().isoformat(), "tag": label,
                 "react": [t["kind"] for t in m.tapbacks][:4]})


def analyze_source(kind, convos, a, provider):
    """Narrate + stat one platform's conversations -> a built app dataset (or None)."""
    ov_fn = ig_overview if kind == "instagram" else overview_stats
    dos_fn = ig_dossier if kind == "instagram" else contact_dossier
    wrap_fn = ig_wrapped if kind == "instagram" else wrapped_stats
    narr_fn = narrate_ig if kind == "instagram" else narrate_contact
    tag = kind[:3]

    act = lambda c: sum(1 for m in c.messages if m.is_me)   # counts reels too (IG-fair)
    gmin = a.group_min if getattr(a, "group_min", 0) > 0 else max(10, a.min_messages // 2)
    people_all = sorted([c for c in convos if not c.is_group and act(c) >= a.min_messages],
                        key=lambda c: -act(c))
    groups = sorted([c for c in convos if c.is_group and act(c) >= gmin],
                    key=lambda c: -act(c))[:a.group_limit]
    people = people_all[:a.limit] if a.limit else people_all
    if not people_all:
        print(f"  [{kind}] no contacts met the threshold — skipping.")
        return None
    print(f"  [{kind}] {len(people_all)} people ({len(people)} narrated), {len(groups)} groups", flush=True)

    overview = ov_fn(convos)
    months = overview["months"]
    now_date = max(m.ts.date() for c in convos for m in c.messages)
    all_dossiers = [dos_fn(c, months) for c in people_all]
    wrapped = wrap_fn(people_all, all_dossiers, overview, now_date)
    dmap = {c.name: d for c, d in zip(people_all, all_dossiers)}

    # Below the narration cutoff we still include the conversation with all its
    # deterministic data (stats, charts, fingerprints, deterministic highlights) —
    # we just don't spend the local LLM narrating small, low-signal chats.
    nmin = getattr(a, "narrate_min", 0) or 0
    do_narr = lambda c: nmin <= 0 or act(c) >= nmin

    people_data, briefs = [], []
    for i, c in enumerate(people):
        d = dmap[c.name]
        if do_narr(c):
            samples = sample_exchanges(c, n=a.samples)
            t0 = time.time()
            print(f"  [{tag} {i+1}/{len(people)}] {c.name} … ", end="", flush=True)
            narrative = narr_fn(provider, d, samples, temperature=a.temperature)
            _add_llm_highlights(provider, c, d)
            print(f"{time.time()-t0:.0f}s", flush=True)
            briefs.append(f"{c.name} — {(narrative.strip().splitlines() or ['—'])[0][:200]}")
        else:
            narrative = ""
            print(f"  [{tag} {i+1}/{len(people)}] {c.name} … data only ({act(c)} msgs)", flush=True)
        people_data.append({"idx": i, "dossier": d, "narrative": narrative, "dataonly": not do_narr(c)})

    groups_data = []
    for i, c in enumerate(groups):
        d = dos_fn(c, months)
        if do_narr(c):
            samples = sample_exchanges(c, n=a.samples)
            t0 = time.time()
            print(f"  [{tag} grp {i+1}/{len(groups)}] {c.name} … ", end="", flush=True)
            narrative = narrate_group(provider, d, samples, temperature=a.temperature)
            _add_llm_highlights(provider, c, d)
            mreads = member_reads(provider, c.name, member_message_samples(c))
            print(f"{time.time()-t0:.0f}s", flush=True)
        else:
            narrative, mreads = "", {}
            print(f"  [{tag} grp {i+1}/{len(groups)}] {c.name} … data only ({act(c)} msgs)", flush=True)
        groups_data.append({"idx": i, "dossier": d, "narrative": narrative,
                            "member_reads": mreads, "dataonly": not do_narr(c)})

    print(f"  [{kind}] synopsis + personality …", flush=True)
    synopsis = synthesize(provider, global_dossier(people_all), briefs, temperature=a.temperature + .1)
    persona = personality(provider, synopsis)
    return build_data(a.name, overview, persona, people_data, groups_data, synopsis, wrapped, kind)


def cmd_analyze(a):
    provider = get_provider(a.provider, model=a.model)
    status = provider.check()
    print("llm: " + status, flush=True)
    if "NOT" in status:
        print("Fix the model/server and re-run.", file=sys.stderr)
        return 2

    apps = []
    print(f"parsing iMessage export {a.export_dir} …", flush=True)
    sms = _date_filter(merge_by_contact(parse_export(a.export_dir, exclude=_load_excludes(a.exclude))), a.min_date)
    d = analyze_source("imessage", sms, a, provider)
    if d:
        apps.append({"id": "messages", "name": "Messages", "accent": "#34C759", "data": d})

    if a.ig_export:
        print(f"parsing Instagram export {a.ig_export} …", flush=True)
        ig = _date_filter(parse_instagram(a.ig_export, exclude=_load_excludes(a.exclude)), a.min_date)
        d = analyze_source("instagram", ig, a, provider)
        if d:
            apps.append({"id": "instagram", "name": "Instagram", "accent": "#E1306C", "data": d})

    if not apps:
        print("nothing to analyze.")
        return 1
    meta = f"{a.provider}:{a.model} · {len(apps)} app(s)"
    render_report(a.out, a.title, a.name, apps, meta)
    print(f"\nwrote {a.out}  —  {', '.join(x['name'] for x in apps)}", flush=True)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="textprint", description="Narrated report from an iMessage export (local LLM).")
    sub = p.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analyze", help="analyze an export and write an HTML report")
    an.add_argument("export_dir", help="folder of imessage-exporter .html files")
    an.add_argument("--ig-export", default=None,
                    help="path to an Instagram export's messages/ folder (adds an Instagram app)")
    an.add_argument("--out", default="report.html")
    an.add_argument("--title", default="Textprint")
    an.add_argument("--name", default="You", help="your display name in the report")
    an.add_argument("--provider", default="ollama")
    an.add_argument("--model", default="qwen2.5:14b")
    an.add_argument("--limit", type=int, default=0, help="top-N contacts (0 = all that qualify)")
    an.add_argument("--group-limit", type=int, default=6, help="top-N group chats")
    an.add_argument("--group-min", type=int, default=0,
                    help="min of your own messages for a group to qualify (0 = max(10, min-messages/2))")
    an.add_argument("--narrate-min", type=int, default=0,
                    help="only narrate (LLM) conversations with >= this many of your own messages; "
                         "smaller ones are included with their data but no AI read (0 = narrate all)")
    an.add_argument("--min-messages", type=int, default=40)
    an.add_argument("--min-date", default=None, help="YYYY-MM-DD; drop older messages")
    an.add_argument("--samples", type=int, default=5)
    an.add_argument("--temperature", type=float, default=0.4)
    an.add_argument("--exclude", default=None, help="file of conversation filenames to skip")
    an.set_defaults(func=cmd_analyze)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
