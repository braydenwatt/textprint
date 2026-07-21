"""Select representative exchanges to show the LLM.

The whole corpus won't fit in context, so we pick a handful of telling
conversations — spread across the timeline plus the richest ones — and render
them as compact transcripts. Turns are grouped by *sender* (not just you/them),
so group chats show who actually said what.
"""
SESSION_S = 3 * 3600
BURST_S = 180


def _disp(m):
    if m.text:
        return m.text
    return f"[shared a {m.kind}]" if m.kind != "text" else ""


def _sessions(msgs):
    turns = []
    for m in msgs:
        sender = "You" if m.is_me else m.sender
        d = _disp(m)
        if not d:
            continue
        if turns and turns[-1]["who"] == sender and (m.ts - turns[-1]["end"]).total_seconds() <= BURST_S:
            turns[-1]["texts"].append(d)
            turns[-1]["end"] = m.ts
        else:
            turns.append({"who": sender, "start": m.ts, "end": m.ts, "texts": [d]})
    sess, cur = [], [turns[0]] if turns else []
    for t in turns[1:]:
        if (t["start"] - cur[-1]["end"]).total_seconds() > SESSION_S:
            sess.append(cur)
            cur = [t]
        else:
            cur.append(t)
    if cur:
        sess.append(cur)
    return sess


def _render(sess, max_turns=14):
    lines = [f"[{sess[0]['start'].strftime('%b %d %Y')}]"]
    for t in sess[:max_turns]:
        lines.append(f"{t['who']}: " + " / ".join(x.replace(chr(10), " ")[:140] for x in t["texts"]))
    return "\n".join(lines)


def sample_exchanges(convo, n=5, min_turns=5, max_turns=14):
    """Return up to n rendered sample conversations: a spread across time plus
    the single richest one, all of a readable size."""
    sess = [s for s in _sessions(convo.messages) if min_turns <= len(s) <= max_turns * 2]
    if not sess:
        sess = _sessions(convo.messages)
    if not sess:
        return []
    sess.sort(key=lambda s: s[0]["start"])
    idxs = set()
    for i in range(n - 1):
        j = round(i * (len(sess) - 1) / max(1, n - 2)) if n > 2 else 0
        idxs.add(min(j, len(sess) - 1))
    idxs.add(max(range(len(sess)), key=lambda k: len(sess[k])))
    return [_render(sess[j], max_turns) for j in sorted(idxs)]


def member_message_samples(convo, top_n=6, per=12):
    """For a group: a spread of each top member's own messages, for per-member reads.
    Returns list of (name, [message strings]), most-active member first."""
    from collections import defaultdict
    by = defaultdict(list)
    for m in convo.messages:
        if m.text:
            by["You" if m.is_me else m.sender].append(m.text)
    out = []
    for name, msgs in sorted(by.items(), key=lambda kv: -len(kv[1]))[:top_n]:
        if len(msgs) < 5:
            continue
        step = max(1, len(msgs) // per)
        out.append((name, msgs[::step][:per]))
    return out
