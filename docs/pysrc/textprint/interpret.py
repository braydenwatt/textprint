"""LLM interpretation layer (map-reduce).

map:    per contact, (stats dossier + sampled exchanges) -> a narrative read
reduce: (global stats + all contact briefs)             -> an overall synopsis

Bounded by contact count, not message count — so it runs on a local model and
scales to any history size.
"""
import re


def _dur(s):
    if s is None:
        return "—"
    s = float(s)
    if s < 60: return f"{round(s)}s"
    if s < 3600: return f"{round(s/60)}m"
    if s < 86400: return f"{s/3600:.1f}h"
    return f"{s/86400:.1f}d"


def dossier_text(d):
    em = lambda x: " ".join(f"{e}×{n}" for e, n in x) or "none"
    return (
        f"Contact: {d['name']}\n"
        f"Period: {d['period'][0]} to {d['period'][1]}\n"
        f"Messages: you {d['n_me']}, them {d['n_them']}  (words/msg: you {d['wpm_me']}, them {d['wpm_them']})\n"
        f"By year: {d['by_year']}\n"
        f"Busiest months: {', '.join(f'{m}({n})' for m,n in d['busy_months'])}\n"
        f"Your peak texting hours: {', '.join(str(h)+':00' for h in d['peak_hours'])}\n"
        f"Median reply time — you {_dur(d['reply_med_me_s'])}, them {_dur(d['reply_med_them_s'])}\n"
        f"Conversation starts: you {d['starts_me']}, them {d['starts_them']}\n"
        f"Double-texts: you {d['doubles_me']}, them {d['doubles_them']}\n"
        f"Questions asked: you {d['questions_me']}, them {d['questions_them']}\n"
        f"Laughs (lol/haha/😂): you {d['laughs_me']}, them {d['laughs_them']}\n"
        f"Your emoji: {em(d['emoji_me'])}\nTheir emoji: {em(d['emoji_them'])}\n"
        f"Your distinctive words: {', '.join(w for w, _ in d['words_me'])}\n"
        f"Their distinctive words: {', '.join(w for w, _ in d['words_them'])}\n"
        f"Avg sentiment (-1..+1): you {d['mood_me']}, them {d['mood_them']}\n"
    )


CONTACT_SYS = (
    "You are a sharp, warm analyst of someone's texting history. You are given hard "
    "statistics AND a few real sampled conversations with one contact. Write a concrete, "
    "evidence-grounded read of the relationship — never generic. Synthesize ACROSS the "
    "numbers into meaning (e.g. 'writes longer here than anywhere = more invested'), and "
    "quote or paraphrase the samples to back claims. Be candid but kind. Use the person's "
    "own framing (they are 'you'). Plain prose, ~180-260 words, no headers, no bullet lists."
)

CONTACT_TASK = (
    "Write the analysis of this relationship. Cover, woven together: the SHAPE and arc over "
    "time (is it growing, fading, bursty?); HOW they text this person vs their usual (length, "
    "tone, slang, emoji, timing); WHAT they talk about; and the QUALITY of the exchanges — are "
    "they substantive and reciprocal, or one-sided/logistical/low-effort? Call out anything "
    "striking. Ground every claim in a number or a sample."
)

SYNTH_SYS = (
    "You are analyzing how someone texts overall, across all their contacts. You are given "
    "global stats and a one-line brief per contact. Write a cohesive synopsis of their texting "
    "PERSONALITY: their default style, how they vary it by relationship, their rhythms and "
    "tendencies, and what the pattern says about them. Concrete and specific, ~200-300 words, "
    "plain prose."
)


def narrate_contact(provider, dossier, samples, temperature=0.4):
    prompt = (dossier_text(dossier) + "\nSampled real conversations:\n\n"
              + "\n\n".join(samples) + "\n\n" + CONTACT_TASK)
    return provider.complete(CONTACT_SYS, prompt, temperature=temperature, max_tokens=520)


IG_SYS = (
    "You are analyzing an INSTAGRAM DM thread. Unlike texting, a huge share of an IG relationship "
    "is SHARED CONTENT — reels and posts sent back and forth — plus emoji reactions, not typed "
    "sentences. Sending someone reels IS how they talk; a '[shared a reel]' line is a real message. "
    "Weigh that heavily. Given the stats and sampled messages, write a concrete read: is this a "
    "'we don't talk, we just send each other things' relationship or a real conversation? Who shares "
    "more, what the reaction dynamic is, and the vibe. ~180-240 words, plain prose, grounded in the numbers."
)


def ig_prompt(dossier, samples):
    ig = dossier.get("ig", {})
    extra = (f"\nInstagram signal — reels/posts shared: you {ig.get('reels_me')}, them {ig.get('reels_them')}; "
             f"typed texts: you {ig.get('text_me')}, them {ig.get('text_them')}; "
             f"reactions you gave {ig.get('react_given')}, you received {ig.get('react_recv')}.\n")
    prompt = (dossier_text(dossier) + extra + "\nSampled real messages:\n\n"
              + "\n\n".join(samples) + "\n\nWrite the read.")
    return IG_SYS, prompt


def narrate_ig(provider, dossier, samples, temperature=0.4):
    system, prompt = ig_prompt(dossier, samples)
    return provider.complete(system, prompt, temperature=temperature, max_tokens=520)


GROUP_SYS = (
    "You are analyzing a GROUP CHAT — NOT a one-on-one conversation. The chat has a name, but "
    "that name is often an inside joke or nickname and is NOT a person; never describe the chat "
    "as if you were talking to an individual. You are given group stats, the history of what the "
    "chat has been renamed to, and sampled real messages (each line is prefixed with who said it). "
    "Write a concrete, evidence-grounded read of the group's DYNAMIC: what it's for, the overall "
    "vibe, who drives it vs who lurks, recurring bits/jokes (the rename war is often one), and how "
    "the members bounce off each other. Refer to members by name. ~180-240 words, plain prose."
)


def group_prompt(dossier, samples):
    members = ", ".join(m["name"] for m in dossier.get("members", []))
    ncs = dossier.get("name_changes", [])
    hist = " → ".join(f'"{n["name"]}"' for n in ncs) if ncs else "(never renamed)"
    head = (f'Group chat currently named "{dossier["name"]}" — {len(dossier.get("members", []))} '
            f"people: {members}.\nIt has been renamed over time: {hist}\n\n")
    prompt = (head + dossier_text(dossier) + "\nSampled real group messages:\n\n"
              + "\n\n".join(samples) + "\n\nWrite the group read.")
    return GROUP_SYS, prompt


def narrate_group(provider, dossier, samples, temperature=0.4):
    system, prompt = group_prompt(dossier, samples)
    return provider.complete(system, prompt, temperature=temperature, max_tokens=520)


MEMBERS_SYS = (
    "You characterize each person in a group chat. You are given, per member, a batch of their "
    "real messages from the chat. For EACH member, output exactly one line:\n"
    "<Name> || <one sharp, specific sentence about their role and texting style in THIS group>\n"
    "Use the '||' separator. No preamble, no extra lines. Be concrete and a little playful."
)


HIGHLIGHT_SYS = (
    "You are given numbered real messages from one conversation. Pick the 2-3 that most STAND OUT "
    "— the funniest, most emotional, most iconic, or most revealing lines. Output ONLY lines of the "
    "form:\n<number> || <a 2-5 word label of why it's a highlight>\nNothing else, no preamble."
)


def pick_highlights(provider, numbered, temperature=0.5):
    """numbered: list of (idx, 'Who: text'). Returns [(idx, label)]."""
    if len(numbered) < 6:
        return []
    prompt = "Messages:\n" + "\n".join(f"{i}. {t}" for i, t in numbered)
    raw = provider.complete(HIGHLIGHT_SYS, prompt, temperature=temperature, max_tokens=140)
    out = []
    for line in raw.splitlines():
        if "||" not in line:
            continue
        left, label = line.split("||", 1)
        m = re.search(r"\d+", left)
        if m:
            out.append((int(m.group()), label.strip().strip('"')[:44]))
    return out[:3]


def member_reads(provider, group_name, member_samples, temperature=0.5):
    """member_samples: list of (name, [message strings]). Returns {name: one-line read}."""
    parts = []
    for name, msgs in member_samples:
        joined = " / ".join(m.replace("\n", " ")[:120] for m in msgs[:14])
        parts.append(f"### {name}\n{joined}")
    prompt = (f'Group chat "{group_name}". Characterize each member below.\n\n'
              + "\n\n".join(parts))
    raw = provider.complete(MEMBERS_SYS, prompt, temperature=temperature, max_tokens=360)
    out = {}
    for line in raw.splitlines():
        if "||" in line:
            nm, read = line.split("||", 1)
            out[nm.strip().lstrip("-• ").strip()] = read.strip()
    return out


PERSONA_SYS = (
    "You name someone's texting personality from a summary of how they text. Reply with exactly "
    "two lines and nothing else:\nTitle: <a punchy, playful 2-5 word archetype, like 'The Midnight "
    "Diplomat'>\nTagline: <one vivid sentence, ~15-22 words, capturing their style>"
)


def persona_prompt(synopsis):
    return PERSONA_SYS, "How they text:\n" + synopsis


def parse_persona(raw, synopsis=""):
    title, tagline = "Your Textprint", ""
    for line in raw.splitlines():
        low = line.lower()
        if low.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip('"') or title
        elif low.startswith("tagline:"):
            tagline = line.split(":", 1)[1].strip().strip('"')
    if not tagline:
        tagline = (synopsis.split(".")[0].strip() + ".") if synopsis else ""
    return {"title": title, "blurb": tagline}


def personality(provider, synopsis, temperature=0.6):
    system, prompt = persona_prompt(synopsis)
    raw = provider.complete(system, prompt, temperature=temperature, max_tokens=90)
    return parse_persona(raw, synopsis)


def synth_prompt(gdoss, briefs):
    g = (f"Overall: {gdoss['n_me']} messages you sent across {gdoss['n_contacts']} contacts, "
         f"{gdoss['words_me']} words, {gdoss['wpm_me']} words/msg. By year: {gdoss['by_year']}. "
         f"Peak hours: {', '.join(str(h)+':00' for h in gdoss['peak_hours'])}.\n\n"
         "Per-contact briefs (name — relationship read):\n" + "\n".join(briefs))
    return SYNTH_SYS, g + "\n\nWrite the overall synopsis of how they text."


def synthesize(provider, gdoss, briefs, temperature=0.5):
    system, prompt = synth_prompt(gdoss, briefs)
    return provider.complete(system, prompt, temperature=temperature, max_tokens=620)
