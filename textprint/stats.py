"""Deterministic stats -> dossiers the LLM reasons over AND the report renders.

Reply times are burst-grouped so double-texts never register as instant replies.
Produces per-contact dossiers, plus an overview aggregate for the home tab.
"""
import math
import re
from collections import Counter, defaultdict
from datetime import timedelta

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER = SentimentIntensityAnalyzer()
except Exception:
    _VADER = None

BURST_S = 180
SESSION_S = 3 * 3600
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF"
                   "\U0001FA70-\U0001FAFF❤♥☺]")
STOP = set("i the to a you and it is that of in do so my me for on but not have this be we with are u "
           "at im can will did if or no yes was up ok get go it's don't just what your out about how "
           "when they he she them all as an there here we're i'm you're like a of at be in on it now oh".split())
LAUGH = re.compile(r"\b(l+o+l+|lmao+|ha(ha)+)\b|😂|🤣|💀", re.I)
QMARK = re.compile(r"\?")


def _words(t):
    return re.findall(r"[a-z']{2,}", t.lower())


def _band(h):
    return 0 if 5 <= h < 9 else 1 if 9 <= h < 12 else 2 if 12 <= h < 17 else 3 if 17 <= h < 22 else 4


def _turnify(msgs):
    turns = []
    for m in msgs:
        if turns and turns[-1]["me"] == m.is_me and (m.ts - turns[-1]["end"]).total_seconds() <= BURST_S:
            turns[-1]["end"] = m.ts
            turns[-1]["n"] += 1
        else:
            turns.append({"me": m.is_me, "start": m.ts, "end": m.ts, "n": 1})
    return turns


def _sessions(turns):
    out, cur = [], []
    for t in turns:
        if cur and (t["start"] - cur[-1]["end"]).total_seconds() > SESSION_S:
            out.append(cur)
            cur = []
        cur.append(t)
    if cur:
        out.append(cur)
    return out


def _median(v):
    if not v:
        return None
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def _distinctive(side, other, k=12):
    cw = Counter(w for m in side for w in _words(m.text) if w not in STOP)
    ow = Counter(w for m in other for w in _words(m.text) if w not in STOP)
    st, ot = sum(cw.values()) or 1, sum(ow.values()) or 1
    sc = sorted(((w, (c / st) / (ow[w] / ot if ow[w] else 5e-5)) for w, c in cw.items() if c >= 5),
                key=lambda x: -x[1])
    return [(w, cw[w]) for w, _ in sc[:k]]   # (word, raw count)


def _sentiment(side):
    """Return (avg compound, {pos,neu,neg} counts) for a set of messages."""
    if not (_VADER and side):
        return 0.0, {"pos": 0, "neu": 0, "neg": 0}
    sp = {"pos": 0, "neu": 0, "neg": 0}
    tot = 0.0
    for m in side:
        c = _VADER.polarity_scores(m.text)["compound"]
        tot += c
        sp["pos" if c >= .05 else "neg" if c <= -.05 else "neu"] += 1
    return round(tot / len(side), 3), sp


def _emoji(side):
    return Counter(e for m in side for e in EMOJI.findall(m.text))


def _tag(peak_hours, reply_med, starts_me, starts_them, monthly):
    """A short, always-true behavioral label (not a guessed relationship type)."""
    if peak_hours and peak_hours[0] in (22, 23, 0, 1, 2):
        return ("Night owl", "b-night")
    half = len(monthly) // 2
    if half and sum(monthly[:half]) > sum(monthly[half:]) * 2.2:
        return ("Fading", "b-fade")
    if half and sum(monthly[half:]) > sum(monthly[:half]) * 2.2:
        return ("Heating up", "b-fam")
    if reply_med is not None and reply_med < 60:
        return ("Fast replies", "b-fam")
    if starts_me > starts_them * 1.6:
        return ("You reach out", "b-pro")
    if starts_them > starts_me * 1.6:
        return ("They reach out", "b-pro")
    return ("Steady", "b-pro")


def highlights(convo):
    """A few genuinely notable real messages: how it started, the most-reacted
    banger, and the longest paragraph. All deterministic, all real content."""
    txt = [m for m in convo.messages if m.text]
    if not txt:
        return []

    def entry(m, tag, extra=None):
        e = {"text": m.text[:400], "who": "You" if m.is_me else m.sender,
             "me": m.is_me, "date": m.ts.date().isoformat(), "tag": tag}
        if extra:
            e.update(extra)
        return e

    out = [entry(txt[0], "how it started")]
    mr = max(convo.messages, key=lambda m: len(m.tapbacks), default=None)
    if mr and mr.text and mr.tapbacks:
        out.append(entry(mr, f"most-reacted · {len(mr.tapbacks)}",
                         {"react": [t["kind"] for t in mr.tapbacks][:4]}))
    lg = max(txt, key=lambda m: len(m.text.split()))
    if len(lg.text.split()) >= 12:
        out.append(entry(lg, f"longest · {len(lg.text.split())} words"))
    seen, ded = set(), []
    for h in out:
        k = h["text"][:50]
        if k not in seen:
            seen.add(k)
            ded.append(h)
    return ded[:4]


def member_profiles(convo, months=None):
    """Per-member behavior WITHIN a group chat, so each person gets a detail page:
    volume, verbosity, how fast they jump in, initiation, emoji, reactions, rhythm."""
    ms = sorted(convo.messages, key=lambda m: m.ts)
    turns = []
    for m in ms:
        who = "You" if m.is_me else m.sender
        if turns and turns[-1]["who"] == who and (m.ts - turns[-1]["end"]).total_seconds() <= BURST_S:
            turns[-1]["end"] = m.ts
        else:
            turns.append({"who": who, "start": m.ts, "end": m.ts})
    P = defaultdict(lambda: {"msgs": 0, "words": 0, "reply": [], "starts": 0, "emoji": Counter(),
                             "given": 0, "recv": 0, "givenk": Counter(), "recvk": Counter(),
                             "monthly": Counter(), "bands": Counter(), "wc": Counter()})
    for m in ms:
        who = "You" if m.is_me else m.sender
        p = P[who]
        p["msgs"] += 1
        p["monthly"][m.ts.strftime("%Y-%m")] += 1
        p["bands"][_band(m.ts.hour)] += 1
        if m.text:
            p["words"] += len(m.text.split())
            for w in _words(m.text):
                if w not in STOP:
                    p["wc"][w] += 1
            p["emoji"].update(EMOJI.findall(m.text))
        for t in m.tapbacks:
            r = P["You" if t["by"] == "Me" else t["by"]]
            r["given"] += 1
            r["givenk"][t["kind"]] += 1
            p["recv"] += 1
            p["recvk"][t["kind"]] += 1
    for i, t in enumerate(turns):
        if i == 0 or (t["start"] - turns[i - 1]["end"]).total_seconds() > SESSION_S:
            P[t["who"]]["starts"] += 1
        elif turns[i - 1]["who"] != t["who"]:
            g = (t["start"] - turns[i - 1]["end"]).total_seconds()
            if g <= 24 * 3600:
                P[t["who"]]["reply"].append(g)
    bands = ["early morning", "morning", "afternoon", "evening", "late night"]
    total = sum(p["msgs"] for p in P.values()) or 1
    out = {}
    for who, p in P.items():
        if p["msgs"] < 5:
            continue
        pb = max(range(5), key=lambda b: p["bands"].get(b, 0)) if p["bands"] else 2
        out[who] = {
            "name": who, "msgs": p["msgs"], "words": p["words"],
            "wpm": round(p["words"] / max(1, p["msgs"]), 1), "share": round(100 * p["msgs"] / total),
            "reply_med_s": _median(p["reply"]), "starts": p["starts"],
            "emoji": p["emoji"].most_common(5), "given": p["given"], "recv": p["recv"],
            "react_given": p["givenk"].most_common(6), "react_recv": p["recvk"].most_common(6),
            "monthly": [p["monthly"][k] for k in months] if months else [],
            "peak": bands[pb], "words_top": p["wc"].most_common(8),
        }
    return out


def contact_dossier(convo, months=None):
    ms = convo.messages
    mine, theirs = convo.mine, convo.theirs
    turns = _turnify(ms)
    sess = _sessions(turns)

    starts = {True: 0, False: 0}
    doubles = {True: 0, False: 0}
    for t in turns:
        doubles[t["me"]] += t["n"] - 1
    # Two reply metrics, so rapid in-conversation volleys don't drown out the real
    # "how long to get back to you" number:
    #   resp_first — you answered when you'd been quiet a while (a genuine response)
    #   resp_conv  — you answered while already actively chatting (a fast volley)
    # Reply time is measured from the FIRST message of the other person's unanswered run,
    # so their follow-up nudges don't reset the clock.
    LULL = 30 * 60          # away this long -> your reply counts as a "response", not a volley
    REPLY_CAP = 24 * 3600
    resp_first = {True: [], False: []}
    resp_conv = {True: [], False: []}
    last_end = {True: None, False: None}
    run_owner = run_first = prev = None
    for t in turns:
        if prev is None or (t["start"] - prev["end"]).total_seconds() > SESSION_S:
            starts[t["me"]] += 1
        if run_owner is not None and t["me"] != run_owner:
            rt = (t["start"] - run_first).total_seconds()
            if rt <= REPLY_CAP:
                le = last_end[t["me"]]
                away = le is None or (t["start"] - le).total_seconds() > LULL
                (resp_first if away else resp_conv)[t["me"]].append(rt)
        if run_owner is None or t["me"] != run_owner:
            run_owner, run_first = t["me"], t["start"]
        last_end[t["me"]] = t["end"]
        prev = t

    stars = [0] * 5
    for s in sess:
        n = sum(t["n"] for t in s)
        stars[4 if n >= 50 else 3 if n >= 25 else 2 if n >= 10 else 1 if n >= 4 else 0] += 1

    hours = Counter(m.ts.hour for m in mine)
    peak_hours = [h for h, _ in hours.most_common(4)]
    reply_resp_me, reply_conv_me = _median(resp_first[True]), _median(resp_conv[True])
    reply_resp_them, reply_conv_them = _median(resp_first[False]), _median(resp_conv[False])
    reply_me = reply_resp_me if reply_resp_me is not None else reply_conv_me   # headline = response time
    reply_them = reply_resp_them if reply_resp_them is not None else reply_conv_them

    # monthly series aligned to the report-wide month axis (for the sparkline)
    mcount = Counter(m.ts.strftime("%Y-%m") for m in ms)
    monthly = [mcount[k] for k in months] if months else [mcount[k] for k in sorted(mcount)]

    # rating 0-100: balance + your speed + consistency + volume, 25 each
    w_me = sum(len(m.text.split()) for m in mine)
    w_th = sum(len(m.text.split()) for m in theirs)
    pts_me, pts_th = len(mine) + w_me, len(theirs) + w_th
    share = pts_me / max(1, pts_me + pts_th)
    bal = 1 - abs(share - 0.5) * 2
    mymed = reply_me or reply_them or 3600
    spd = min(1, max(0, 1 - math.log(max(mymed, 30) / 30) / math.log(7200 / 30)))
    span = max(1, (ms[-1].ts.year - ms[0].ts.year) * 12 + ms[-1].ts.month - ms[0].ts.month + 1)
    act = min(1, len({m.ts.strftime("%Y-%m") for m in ms}) / span)
    vol = min(1, len(ms) / 1500)
    rating = round(25 * (bal + spd + act + vol))

    tag = _tag(peak_hours, reply_me, starts[True], starts[False], monthly) if not convo.is_group else ("Group", "b-night")

    mood_me, split_me = _sentiment(mine)
    mood_them, _ = _sentiment(theirs)
    # per-sender breakdown (the point of a group page: who's who, including you)
    smsg = Counter("You" if m.is_me else m.sender for m in ms)
    sword = Counter()
    for m in ms:
        sword["You" if m.is_me else m.sender] += len(m.text.split())
    tot_m = sum(smsg.values()) or 1
    members = [{"name": s, "msgs": smsg[s], "words": sword[s],
                "share": round(100 * smsg[s] / tot_m), "me": s == "You"}
               for s in sorted(smsg, key=lambda x: -smsg[x])]

    # reaction fingerprint — which tapbacks you hand out vs. which come back at you
    react_me, react_them = Counter(), Counter()
    for m in ms:
        for t in m.tapbacks:
            (react_me if t["by"] == "Me" else react_them)[t["kind"]] += 1

    return {
        "name": convo.name, "is_group": convo.is_group,
        "participants": convo.participants,
        "period": [ms[0].ts.date().isoformat(), ms[-1].ts.date().isoformat()],
        "n_me": len(mine), "n_them": len(theirs), "n_total": len(mine) + len(theirs),
        "wpm_me": round(w_me / max(1, len(mine)), 1), "wpm_them": round(w_th / max(1, len(theirs)), 1),
        "words_me_n": w_me, "words_them_n": w_th,
        "uniq_me": len({w for m in mine for w in _words(m.text)}),
        "uniq_them": len({w for m in theirs for w in _words(m.text)}),
        "you_share": round(100 * len(mine) / max(1, len(mine) + len(theirs))),
        "by_year": dict(sorted(Counter(m.ts.year for m in ms).items())),
        "busy_months": Counter(m.ts.strftime("%Y-%m") for m in ms).most_common(3),
        "peak_hours": peak_hours,
        "reply_med_me_s": reply_me, "reply_med_them_s": reply_them,
        "reply_resp_me_s": reply_resp_me, "reply_conv_me_s": reply_conv_me,
        "reply_resp_them_s": reply_resp_them, "reply_conv_them_s": reply_conv_them,
        "starts_me": starts[True], "starts_them": starts[False],
        "doubles_me": doubles[True], "doubles_them": doubles[False],
        "questions_me": sum(1 for m in mine if QMARK.search(m.text)),
        "questions_them": sum(1 for m in theirs if QMARK.search(m.text)),
        "laughs_me": sum(1 for m in mine if LAUGH.search(m.text)),
        "laughs_them": sum(1 for m in theirs if LAUGH.search(m.text)),
        "emoji_me": _emoji(mine).most_common(5), "emoji_them": _emoji(theirs).most_common(5),
        "emoji_me_total": sum(_emoji(mine).values()), "emoji_them_total": sum(_emoji(theirs).values()),
        "words_me": _distinctive(mine, theirs), "words_them": _distinctive(theirs, mine),
        "mood_me": mood_me, "mood_them": mood_them, "sent_split": split_me,
        "highlights": highlights(convo),
        "react_me": react_me.most_common(6), "react_them": react_them.most_common(6),
        "react_me_total": sum(react_me.values()), "react_them_total": sum(react_them.values()),
        "members": members, "name_changes": getattr(convo, "name_changes", []),
        "member_profiles": member_profiles(convo, months) if convo.is_group else {},
        "rating": rating, "stars": stars, "monthly": monthly,
        "tag": tag[0], "tag_class": tag[1], "n_sessions": len(sess),
    }


def global_dossier(convos):
    """Compact 'how you text overall' summary for the synopsis prompt."""
    mine = [m for c in convos for m in c.mine]
    return {
        "n_me": len(mine), "n_contacts": len(convos),
        "words_me": sum(len(m.text.split()) for m in mine),
        "wpm_me": round(sum(len(m.text.split()) for m in mine) / max(1, len(mine)), 1),
        "by_year": dict(sorted(Counter(m.ts.year for m in mine).items())),
        "peak_hours": [h for h, _ in Counter(m.ts.hour for m in mine).most_common(4)],
    }


def overview_stats(convos):
    """Aggregate 'how you text overall' data for the home tab. `convos` = all in-scope."""
    allm = [m for c in convos for m in c.messages]
    mine = [m for m in allm if m.is_me and m.text]
    months = sorted({m.ts.strftime("%Y-%m") for m in allm if m.text})
    mo_me = Counter(m.ts.strftime("%Y-%m") for m in mine)
    mo_th = Counter(m.ts.strftime("%Y-%m") for m in allm if not m.is_me and m.text)
    activity = [{"m": k, "me": mo_me[k], "them": mo_th[k]} for k in months]

    heat = [[0] * 7 for _ in range(5)]
    for m in mine:
        heat[_band(m.ts.hour)][m.ts.weekday()] += 1

    days = Counter(m.ts.date() for m in mine)
    dayset = sorted(days)
    streak = best = 1 if dayset else 0
    for a, b in zip(dayset, dayset[1:]):
        streak = streak + 1 if (b - a).days == 1 else 1
        best = max(best, streak)
    busiest = max(days.values()) if days else 0

    pos = neu = neg = 0
    if _VADER:
        for m in mine:
            c = _VADER.polarity_scores(m.text)["compound"]
            pos += c >= 0.05
            neg += c <= -0.05
            neu += -0.05 < c < 0.05
    late = sum(1 for m in mine if m.ts.hour < 5)
    tb = sum(sum(1 for t in m.tapbacks if t["by"] == "Me") for m in allm)

    return {
        "months": months, "activity": activity, "heat": heat,
        "streak": best, "busiest": busiest, "late_pct": round(100 * late / max(1, len(mine)), 1),
        "sent": len(mine), "received": sum(1 for m in allm if not m.is_me and m.text),
        "words": sum(len(m.text.split()) for m in mine),
        "wpm": round(sum(len(m.text.split()) for m in mine) / max(1, len(mine)), 1),
        "tapbacks": tb, "emoji": _emoji(mine).most_common(8),
        "mood": {"pos": pos, "neu": neu, "neg": neg},
        "peak_hours": [h for h, _ in Counter(m.ts.hour for m in mine).most_common(3)],
    }
