"""Instagram-native stats. IG DMs are content, not words — so these lead with
reels shared, the reaction economy, reel taste, and content mix. Reuses the SMS
core (reply-time asymmetry, initiation, arcs) via contact_dossier / wrapped.
"""
from collections import Counter

from .stats import contact_dossier, overview_stats
from .wrapped import wrapped_stats, _dur, _parse

CONTENT = ("reel", "post", "share")


def ig_extra(convo):
    ms = convo.messages
    rc = lambda p: sum(1 for m in ms if p(m))
    reels_me = rc(lambda m: m.is_me and m.kind in CONTENT)
    reels_them = rc(lambda m: not m.is_me and m.kind in CONTENT)
    text_me = rc(lambda m: m.is_me and m.kind == "text" and m.text)
    text_them = rc(lambda m: not m.is_me and m.kind == "text" and m.text)
    react_given = sum(1 for m in ms for t in m.tapbacks if t["by"] == "Me")
    react_recv = sum(1 for m in ms if m.is_me for t in m.tapbacks)
    remoji_me = Counter(t["kind"] for m in ms for t in m.tapbacks if t["by"] == "Me")
    remoji_them = Counter(t["kind"] for m in ms if m.is_me for t in m.tapbacks)
    owners = Counter(m.meta.get("owner", "") for m in ms if m.kind == "reel" and m.meta.get("owner"))
    mix = Counter()
    for m in ms:
        if m.kind in CONTENT:
            mix["reels"] += 1
        elif m.kind == "text" and m.text:
            mix["text"] += 1
        elif m.kind in ("photo", "video", "gif"):
            mix["media"] += 1
    tot = sum(mix.values()) or 1
    return {
        "reels_me": reels_me, "reels_them": reels_them, "reels": reels_me + reels_them,
        "text_me": text_me, "text_them": text_them,
        "react_given": react_given, "react_recv": react_recv,
        "remoji_me": remoji_me.most_common(4), "remoji_them": remoji_them.most_common(4),
        "owners": owners.most_common(5),
        "reel_ratio": round((reels_me + reels_them) / max(1, text_me + text_them), 1),
        "mix": {k: round(100 * mix.get(k, 0) / tot) for k in ("reels", "text", "media")},
    }


def ig_dossier(convo, months):
    d = contact_dossier(convo, months)
    d["ig"] = ig_extra(convo)
    return d


def ig_overview(convos):
    ov = overview_stats(convos)   # reuse: activity/heat/emoji/mood over your typed messages
    ms = [m for c in convos for m in c.messages]
    reels = sum(1 for m in ms if m.kind in CONTENT)
    reels_me = sum(1 for m in ms if m.is_me and m.kind in CONTENT)
    react_given = sum(1 for m in ms for t in m.tapbacks if t["by"] == "Me")
    react_recv = sum(1 for m in ms if m.is_me for t in m.tapbacks)
    owners = Counter(m.meta.get("owner", "") for m in ms if m.kind == "reel" and m.meta.get("owner"))
    mix = Counter()
    for m in ms:
        if m.kind in CONTENT:
            mix["reels"] += 1
        elif m.kind == "text" and m.text:
            mix["text"] += 1
        elif m.kind in ("photo", "video", "gif"):
            mix["media"] += 1
    tot = sum(mix.values()) or 1
    ov["ig"] = {
        "reels": reels, "reels_me": reels_me, "texts": mix["text"],
        "react_given": react_given, "react_recv": react_recv,
        "owners": owners.most_common(6),
        "mix": [{"k": k, "pct": round(100 * mix.get(k, 0) / tot), "n": mix.get(k, 0)}
                for k in ("reels", "text", "media")],
    }
    return ov


def ig_wrapped(convos, dossiers, overview, now_date):
    W = wrapped_stats(convos, dossiers, overview, now_date)   # asymmetry/arcs/awards/verbal reused
    dz = list(zip(convos, dossiers))

    # reel language — the headliner: who you share the most content with
    reel_top = max(dz, key=lambda cd: cd[1]["ig"]["reels"], default=None)
    if reel_top:
        e = reel_top[1]["ig"]
        W["reel_lang"] = {"who": reel_top[0].name, "reels": e["reels"],
                          "words": e["text_me"] + e["text_them"],
                          "ratio": round(e["reels"] / max(1, e["text_me"] + e["text_them"]), 1)}

    # your reel taste — most-shared original creators, all threads
    owners = Counter()
    remoji = Counter()
    for c in convos:
        for m in c.messages:
            if m.kind == "reel" and m.meta.get("owner"):
                owners[m.meta["owner"]] += 1
            for t in m.tapbacks:
                if t["by"] == "Me":
                    remoji[t["kind"]] += 1
    W["taste"] = {"owners": owners.most_common(6)}
    W["reaction"] = {"emoji": remoji.most_common(1)[0] if remoji else ["", 0],
                     "given": overview["ig"]["react_given"], "recv": overview["ig"]["react_recv"]}

    # the "❤️ and dip" — reacts to you a lot but rarely types back
    dip = None
    for c, d in dz:
        e = d["ig"]
        recv = e["react_recv"]      # reactions they left on your messages
        if recv >= 15 and e["text_them"] < recv * 0.9:
            score = recv / max(1, e["text_them"])
            if not dip or score > dip["score"]:
                dip = {"who": c.name, "reacts": recv, "words": e["text_them"], "score": score}
    W["heart_dip"] = dip

    # content-mix reveal (overall) + reels sent/received totals
    W["mix"] = overview["ig"]["mix"]
    W["reels_sent"] = overview["ig"]["reels_me"]
    W["reels_recv"] = overview["ig"]["reels"] - overview["ig"]["reels_me"]
    return W
