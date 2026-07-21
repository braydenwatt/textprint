"""The 'reveal, don't count' layer — derived stats that land emotionally.

Volume reframed into human terms, timing quirks, power-dynamic asymmetries,
your verbal fingerprint (incl. private vocab per person), relationship arcs,
and per-contact awards. Feeds the Wrapped story mode. All deterministic.
"""
import re
from collections import Counter, defaultdict

from .stats import EMOJI, STOP, _sessions, _turnify

WORD = re.compile(r"[a-z']{2,}")
FILLER = STOP | {"lol", "yeah", "like", "just", "dont", "im", "youre", "thats", "ok", "okay",
                 "haha", "yes", "no", "u", "ur", "gonna", "wanna", "got", "one", "now",
                 "good", "know", "think", "want", "need", "sure", "oh", "idk", "bro"}


def _words(t):
    return WORD.findall(t.lower())


def _dur(s):
    if s is None:
        return "—"
    s = float(s)
    if s < 60: return f"{round(s)} sec"
    if s < 3600: return f"{round(s/60)} min"
    if s < 86400: return f"{s/3600:.1f} hr"
    return f"{s/86400:.1f} days"


def _fmt_time(dt):
    h12 = (dt.hour % 12) or 12
    return f"{h12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def wrapped_stats(convos, dossiers, overview, now_date):
    dz = list(zip(convos, dossiers))
    mine = [(m, c.name) for c in convos for m in c.mine]
    my_msgs = [m for m, _ in mine]
    if not my_msgs:
        return {}
    active_days = max(1, len({m.ts.date() for m in my_msgs}))
    sent = overview["sent"]
    words = overview["words"]
    per_day = round(sent / active_days)

    W = {}

    # ── volume, reframed ───────────────────────────────────────
    W["volume"] = {
        "sent": sent, "per_day": per_day,
        "every_min": round(16 * 60 / max(1, per_day)),          # one text every N waking minutes
        "words": words, "novel_pages": max(1, round(words / 275)),
        "hours": round(sent * 8 / 3600), "days": round(sent * 8 / 3600 / 24, 1),
    }

    # ── timing quirks ──────────────────────────────────────────
    # "latest text ever" = the most extreme small-hours text (00:00–05:59)
    night = [x for x in mine if x[0].ts.hour < 6]
    lm, lm_who = (max(night, key=lambda x: (x[0].ts.hour, x[0].ts.minute)) if night
                  else max(mine, key=lambda x: x[0].ts.hour))
    W["latest"] = {"time": _fmt_time(lm.ts), "who": lm_who, "date": lm.ts.date().isoformat()}
    first_of_day = {}
    for m, name in sorted(mine, key=lambda x: x[0].ts):
        first_of_day.setdefault(m.ts.date(), name)
    fp = Counter(first_of_day.values()).most_common(1)
    W["first_person"] = {"who": fp[0][0], "days": fp[0][1]} if fp else None
    best = (None, 0)
    for c in convos:
        ds = sorted({m.ts.date() for m in c.mine})
        run = top = 1 if ds else 0
        for a, b in zip(ds, ds[1:]):
            run = run + 1 if (b - a).days == 1 else 1
            top = max(top, run)
        if top > best[1]:
            best = (c.name, top)
    W["streak"] = {"who": best[0], "days": best[1]}

    # ── verbal fingerprint + private vocabulary ────────────────
    wc, big = Counter(), Counter()
    for m in my_msgs:
        ws = _words(m.text)
        for w in ws:
            if w not in FILLER:
                wc[w] += 1
        for a, b in zip(ws, ws[1:]):
            if a not in FILLER and b not in FILLER:
                big[a + " " + b] += 1
    word_contacts = defaultdict(set)
    cw = defaultdict(Counter)
    for c in convos:
        for m in c.mine:
            for w in _words(m.text):
                if len(w) >= 3 and w not in FILLER:
                    cw[c.name][w] += 1
                    word_contacts[w].add(c.name)
    private = {}
    for c in convos:
        pv = [w for w, n in cw[c.name].most_common(60) if n >= 4 and len(word_contacts[w]) == 1]
        if pv:
            private[c.name] = pv[:6]
    priv_pick = max(private.items(), key=lambda kv: len(kv[1]), default=None)
    W["verbal"] = {
        "top_word": (wc.most_common(1) or [("", 0)])[0],
        "phrase": (big.most_common(1) or [("", 0)])[0],
        "emoji": overview["emoji"][0] if overview["emoji"] else ["", 0],
        "private": {"who": priv_pick[0], "words": priv_pick[1]} if priv_pick else None,
    }

    # ── per-contact extras: night share + left-on-read ─────────
    night_share, left = {}, {}
    for c in convos:
        mn = c.mine
        night_share[c.name] = sum(1 for m in mn if m.ts.hour < 5) / max(1, len(mn))
        sess = _sessions(_turnify(sorted(c.messages, key=lambda m: m.ts)))
        you_left = sum(1 for s in sess if not s[-1]["me"])   # they spoke last, you didn't reply
        they_left = sum(1 for s in sess if s[-1]["me"])      # you spoke last, they didn't reply
        left[c.name] = {"you_left": you_left, "they_left": they_left}

    # ── awards (need enough data to be fair) ───────────────────
    cand = [(c, d) for c, d in dz if d["n_total"] >= 120]
    awards = []
    if cand:
        def add(title, sub, pick):
            if pick:
                awards.append({"title": title, "who": pick[0].name, "detail": sub(pick[1])})
        add("The Novelist", lambda d: f"{d['wpm_them']} words per text",
            max(cand, key=lambda cd: cd[1]["wpm_them"]))
        add("The One-Word Wonder", lambda d: f"{d['wpm_them']} words per text",
            min(cand, key=lambda cd: cd[1]["wpm_them"]))
        add("Your Ride or Die", lambda d: f"rating {d['rating']}/100",
            max(cand, key=lambda cd: cd[1]["rating"]))
        add("The Night Owl", lambda d: f"{round(100*night_share[d['name']])}% of texts after midnight",
            max(cand, key=lambda cd: night_share[cd[1]["name"]]))
        add("The Ghost", lambda d: f"left you on read {left[d['name']]['they_left']}×",
            max(cand, key=lambda cd: left[cd[1]["name"]]["they_left"]))
    W["awards"] = awards

    # ── asymmetry (the headliner) — meaningful, still-active relationships only ──
    asym = []
    for c, d in dz:
        yr, tr = d["reply_resp_me_s"], d["reply_resp_them_s"]
        days_since = (now_date - _parse(d["period"][1])).days
        if yr and tr and d["n_total"] >= 250 and days_since < 180:
            asym.append({"who": c.name, "you": _dur(yr), "them": _dur(tr),
                         "you_s": yr, "them_s": tr, "ratio": tr / yr})
    W["chase"] = max(asym, key=lambda a: a["ratio"], default=None)     # you fast, they slow
    W["chased"] = min(asym, key=lambda a: a["ratio"], default=None)    # they fast, you slow
    # the single most dramatic asymmetry (either direction) for the finale
    hero = None
    for a in asym:
        extreme = max(a["ratio"], 1 / a["ratio"])
        cand = dict(a, extreme=extreme, dir=("you_chase" if a["ratio"] >= 1 else "they_chase"))
        if hero is None or extreme > hero["extreme"]:
            hero = cand
    W["asym_hero"] = hero
    # initiation imbalance
    init = [{"who": c.name, "you": d["starts_me"], "them": d["starts_them"],
             "you_pct": round(100 * d["starts_me"] / max(1, d["starts_me"] + d["starts_them"]))}
            for c, d in dz if d["n_total"] >= 150]
    W["initiator"] = max(init, key=lambda x: x["you_pct"], default=None)
    W["initiated"] = min(init, key=lambda x: x["you_pct"], default=None)
    # word-count ratio (you write paragraphs, get one-liners)
    wr = [{"who": c.name, "ratio": round(d["wpm_me"] / max(0.1, d["wpm_them"]), 1),
           "you": d["wpm_me"], "them": d["wpm_them"]}
          for c, d in dz if d["n_total"] >= 150 and d["wpm_them"]]
    W["wordy"] = max(wr, key=lambda x: x["ratio"], default=None)

    # ── relationship arcs ──────────────────────────────────────
    fading = None
    for c, d in dz:
        mo = d["monthly"]
        if len(mo) < 8 or sum(mo) < 150:
            continue
        h = len(mo) // 2
        early, recent = sum(mo[:h]), sum(mo[h:])
        if early > 60 and recent < early * 0.5 and recent > 0:
            score = (early - recent) / early
            if not fading or score > fading["score"]:
                fading = {"who": c.name, "score": score, "monthly": mo,
                          "drop": round(100 * score)}
    W["fading"] = fading
    grave = None
    for c, d in dz:
        if d["n_total"] < 100:
            continue
        gap = (now_date - _parse(d["period"][1])).days
        if gap > 45 and (not grave or gap > grave["days"]):
            grave = {"who": c.name, "days": gap, "last": d["period"][1], "n": d["n_total"]}
    W["graveyard"] = grave
    return W


def _parse(iso):
    from datetime import date
    y, m, d = map(int, iso.split("-"))
    return date(y, m, d)
