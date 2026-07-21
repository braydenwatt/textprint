"""Render the report as a self-contained, app-style HTML file (no network calls
except Google Fonts). Overview / People / Groups / You tabs + per-chat pages."""
import html
import json
import re

PALETTE = ["#2563EB", "#F43F7E", "#059669", "#6366F1", "#0EA5E9", "#F59E0B",
           "#EF4444", "#8B5CF6", "#14B8A6", "#EC4899", "#3B82F6", "#10B981"]


def _dur(s):
    if s is None:
        return "—"
    s = float(s)
    if s < 60: return f"{round(s)}s"
    if s < 3600: return f"{round(s/60)}m"
    if s < 86400: return f"{s/3600:.1f}h"
    return f"{s/86400:.1f}d"


def _snip(narr):
    m = re.match(r".+?[.!?](\s|$)", narr.strip())
    s = (m.group(0) if m else narr).strip().rstrip(".")
    return s[:96]


def _chat_entry(d, narrative, color, mreads=None):
    mreads = mreads or {}
    mprof = d.get("member_profiles", {})
    members = [dict(m, read=mreads.get(m["name"], ""), prof=mprof.get(m["name"]))
               for m in d.get("members", [])]
    return {
        "name_changes": d.get("name_changes", []),
        "n": d["name"], "c": color,
        "msgs": d["n_total"], "sent": d["n_me"], "them": d["n_them"],
        "rating": d["rating"], "reply": _dur(d["reply_med_me_s"]),
        "theirReply": _dur(d["reply_med_them_s"]), "you": d["you_share"],
        "replyResp": _dur(d["reply_resp_me_s"]), "replyConv": _dur(d["reply_conv_me_s"]),
        "theirResp": _dur(d["reply_resp_them_s"]), "theirConv": _dur(d["reply_conv_them_s"]),
        "mood": d["mood_me"], "badge": [d["tag_class"], d["tag"]],
        "emoji": d["emoji_me"], "stars": d["stars"], "spark": d["monthly"] or [0],
        "mem": d.get("participants", [])[:4], "group": d["is_group"], "period": d["period"],
        "members": members, "split": d.get("sent_split", {"pos": 0, "neu": 0, "neg": 0}),
        "moodThem": d["mood_them"], "ig": d.get("ig"),
        "words": d.get("words_them", []), "mywords": d.get("words_me", []),
        "reactMe": d.get("react_me", []), "reactThem": d.get("react_them", []),
        "highlights": d.get("highlights", []),
        "snip": _snip(narrative), "narr": html.escape(narrative),
    }


def build_data(name, overview, personality, people, groups, synopsis, wrapped, platform="imessage"):
    peo = []
    for i, c in enumerate(people):
        e = _chat_entry(c["dossier"], c["narrative"], PALETTE[i % len(PALETTE)])
        e["dataOnly"] = bool(c.get("dataonly"))
        peo.append(e)
    grp = []
    for i, c in enumerate(groups):
        e = _chat_entry(c["dossier"], c["narrative"], PALETTE[i % len(PALETTE)], c.get("member_reads"))
        e["dataOnly"] = bool(c.get("dataonly"))
        grp.append(e)
    mood = overview["mood"]
    tot = max(1, mood["pos"] + mood["neu"] + mood["neg"])
    return {
        "me": {
            "name": name, "sent": overview["sent"], "received": overview["received"],
            "words": overview["words"], "contacts": len(people), "streak": overview["streak"],
            "busy": overview["busiest"], "tapbacks": overview["tapbacks"],
            "topEmoji": overview["emoji"][0][0] if overview["emoji"] else "💬",
            "latePct": overview["late_pct"],
            "persona": {"k": "Your texting personality", "t": personality["title"],
                        "b": personality["blurb"]},
            "synopsis": html.escape(synopsis),
        },
        "activity": [a["me"] for a in overview["activity"]] or [0],
        "heat": overview["heat"], "emoji": overview["emoji"],
        "mood": {"pos": round(100 * mood["pos"] / tot), "neu": round(100 * mood["neu"] / tot),
                 "neg": round(100 * mood["neg"] / tot)},
        "people": peo, "groups": grp, "wrapped": wrapped,
        "platform": platform, "ig": overview.get("ig"), "months": overview.get("months", []),
    }


def render_html(title, name, apps, meta, live=False):
    """apps: list of {id, name, accent, data}. Returns the full self-contained HTML.
    live=True builds the browser-app shell: apps may be empty and get populated in
    place after the visitor imports from the Settings app (see docs/import.js)."""
    payload = {"title": title, "name": name, "live": live,
               "apps": [{"id": a["id"], "name": a["name"], "accent": a["accent"], "data": a["data"]}
                        for a in apps]}
    libs = ('<script src="https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js"></script>'
            '<script src="https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js"></script>'
            '<script src="import.js"></script>') if live else ''
    return (HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
                .replace("__META__", html.escape(meta))
                .replace("__LIBS__", libs))


def render_report(out_path, title, name, apps, meta):
    """Renders a home screen + each app and writes it to disk."""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_html(title, name, apps, meta))


HTML = r"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Textprint</title>
<link rel=preconnect href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&family=Nunito:wght@400;500;600;700;800&display=swap" rel=stylesheet>
<style>
:root{--blue:#2563EB;--green:#059669;--indigo:#6366F1;--pink:#F43F7E;--amber:#F59E0B;
 --ink:#0F172A;--mut:#64748B;--line:#E9EEF6;--card:#FFFFFF;--bg:#F4F6FB;
 --grad:linear-gradient(135deg,#6366F1,#2563EB 55%,#06B6D4);--shadow:0 10px 30px rgba(37,99,235,.10)}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;font-family:Nunito,system-ui,sans-serif;color:var(--ink);
 background:radial-gradient(1200px 700px at 20% -10%,#dfe7ff,transparent),radial-gradient(1000px 700px at 110% 10%,#ffe0ec,transparent),#eef1f8;
 min-height:100dvh;display:flex;align-items:center;justify-content:center;padding:26px 14px}
@media(min-width:680px){body{align-items:flex-start;padding-bottom:180px}.phone{transform:scale(1.22);transform-origin:top center;margin-top:12px}}
@media(min-width:1200px){body{padding-bottom:260px}.phone{transform:scale(1.4)}}
h1,h2,h3,.f{font-family:Fredoka,system-ui,sans-serif;font-weight:600;letter-spacing:.2px}
.phone{width:400px;max-width:100%;height:840px;max-height:94dvh;background:var(--bg);border-radius:42px;
 box-shadow:0 30px 80px rgba(15,23,42,.28),0 0 0 10px #0b1020,0 0 0 12px #1e293b;overflow:hidden;position:relative;display:flex;flex-direction:column}
.notch{position:absolute;top:0;left:50%;transform:translateX(-50%);width:140px;height:26px;background:#0b1020;border-radius:0 0 18px 18px;z-index:40}
.screen{flex:1;overflow-y:auto;overflow-x:hidden;padding:52px 16px 96px}
.screen::-webkit-scrollbar{display:none}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.brand{display:flex;align-items:center;gap:9px}
.logo{width:34px;height:34px;border-radius:11px;background:var(--grad);display:grid;place-items:center;box-shadow:var(--shadow)}
.title{font-size:21px}.sub{color:var(--mut);font-size:12.5px;font-weight:600}
.iconbtn{width:38px;height:38px;border-radius:12px;background:#fff;border:1px solid var(--line);display:grid;place-items:center;color:var(--mut);cursor:pointer}
.card{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:16px;box-shadow:0 4px 14px rgba(15,23,42,.04);margin-bottom:12px}
.chips{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.chip{border-radius:18px;padding:14px;color:#fff;position:relative;overflow:hidden;min-height:84px;display:flex;flex-direction:column;justify-content:flex-end}
.chip .n{font-family:Fredoka;font-size:26px;font-weight:700;line-height:1}.chip .l{font-size:12px;font-weight:700;opacity:.92;margin-top:3px}
.chip .em{position:absolute;top:8px;right:10px;font-size:30px;filter:drop-shadow(0 2px 4px rgba(0,0,0,.15))}
.c-blue{background:linear-gradient(135deg,#3b82f6,#2563EB)}.c-green{background:linear-gradient(135deg,#10b981,#059669)}
.c-indigo{background:linear-gradient(135deg,#818cf8,#6366F1)}.c-pink{background:linear-gradient(135deg,#fb7185,#F43F7E)}
.perso{background:var(--grad);color:#fff;border-radius:22px;padding:18px;position:relative;overflow:hidden;box-shadow:var(--shadow)}
.perso .k{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.1em;opacity:.85}
.perso .t{font-family:Fredoka;font-size:24px;font-weight:700;margin:4px 0 6px}
.perso .b{font-size:13.5px;line-height:1.5;opacity:.95;font-weight:600}
.perso .spark{position:absolute;font-size:70px;right:-6px;bottom:-16px;opacity:.18}
.sec{font-family:Fredoka;font-size:13px;text-transform:uppercase;letter-spacing:.09em;color:var(--mut);margin:16px 4px 8px}
.rowh{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.rowh h3{font-size:16px;margin:0}.pill{font-size:11px;font-weight:800;color:var(--blue);background:#EAF1FE;padding:4px 9px;border-radius:20px}
.legend{font-size:11.5px;color:var(--mut);font-weight:700;display:flex;gap:12px;margin-top:8px;align-items:center;flex-wrap:wrap}
.dot{width:9px;height:9px;border-radius:3px;display:inline-block;margin-right:4px;vertical-align:-1px}
.emoji-row{display:flex;gap:6px;flex-wrap:wrap}
.emoji-row .e{font-size:22px;background:#F5F7FC;border:1px solid var(--line);border-radius:13px;width:44px;height:44px;display:grid;place-items:center;position:relative}
.emoji-row .e b{position:absolute;bottom:-6px;right:-4px;font-size:10px;font-family:Nunito;font-weight:800;background:#fff;border:1px solid var(--line);border-radius:8px;padding:0 4px;color:var(--mut)}
.hm{display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin-top:4px}
.hm .cell{aspect-ratio:1;border-radius:6px}.hm .lab{font-size:9.5px;color:var(--mut);text-align:center;font-weight:700}
.mood{display:flex;height:16px;border-radius:10px;overflow:hidden;margin:6px 0}.mood i{display:block;height:100%}
.contact{display:flex;align-items:center;gap:12px;padding:11px 8px;border-radius:16px;cursor:pointer;transition:background .15s}
.contact:hover,.contact:active{background:#fff}
.av{width:50px;height:50px;border-radius:50%;display:grid;place-items:center;color:#fff;font-family:Fredoka;font-weight:600;font-size:19px;flex:0 0 50px;box-shadow:0 3px 8px rgba(15,23,42,.12)}
.cbody{flex:1;min-width:0}.cbody .nm{font-family:Fredoka;font-weight:600;font-size:16px;display:flex;align-items:center;gap:6px}
.cbody .snip{color:var(--mut);font-size:12.8px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:1px}
.cmeta{text-align:right}.cmeta .cnt{font-family:Fredoka;font-weight:600;font-size:13px}
.cmeta .rate{font-size:10.5px;font-weight:800;color:#fff;background:var(--green);border-radius:20px;padding:2px 7px;margin-top:3px;display:inline-block}
.badge{font-size:10px;font-weight:800;padding:2px 7px;border-radius:20px}
.b-night{background:#EEF0FF;color:#6366F1}.b-fam{background:#E7F6EF;color:#059669}.b-pro{background:#EDF2FA;color:#2563EB}.b-fade{background:#FCE9EF;color:#E11D6B}
.search{width:100%;border:1px solid var(--line);background:#fff;border-radius:14px;padding:11px 14px;font:600 14px Nunito;color:var(--ink);margin-bottom:6px}
.nav{position:absolute;bottom:0;left:0;right:0;height:76px;background:#ffffffee;backdrop-filter:blur(14px);border-top:1px solid var(--line);display:flex;justify-content:space-around;align-items:center;padding-bottom:10px;z-index:30}
.nav button{background:none;border:0;display:flex;flex-direction:column;align-items:center;gap:3px;color:var(--mut);font:800 10.5px Nunito;cursor:pointer;padding:6px 12px;border-radius:12px}
.nav button svg{width:24px;height:24px}.nav button.on{color:var(--blue)}
.back{display:inline-flex;align-items:center;gap:5px;color:var(--blue);font-family:Fredoka;font-weight:600;font-size:15px;cursor:pointer;margin-bottom:6px}
.dhead{display:flex;flex-direction:column;align-items:center;text-align:center;padding:4px 0 10px}
.dhead .av{width:74px;height:74px;font-size:28px;margin-bottom:8px;flex:none}
.hm2{display:grid;grid-template-columns:66px repeat(7,1fr);gap:5px;align-items:center}
.hm2 .cell{aspect-ratio:1;border-radius:6px;cursor:default}
.hm2 .lab2{font-size:9.5px;color:var(--mut);font-weight:700;text-align:center}
.hm2 .row2l{font-size:10px;color:var(--mut);font-weight:700;text-align:right;padding-right:2px}
.member{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}
.member:last-child{border:0}.mav{width:36px;height:36px;border-radius:50%;flex:none;display:grid;place-items:center;color:#fff;font-family:Fredoka;font-weight:600;font-size:14px}
.mbody{flex:1;min-width:0}.mname{font-family:Fredoka;font-weight:600;font-size:14px}
.mbar{height:8px;border-radius:5px;background:#EDF1F8;overflow:hidden;margin-top:4px}.mbar i{display:block;height:100%}
.mshare{text-align:right;font-size:11.5px;font-weight:800;color:var(--mut);white-space:nowrap;flex:none}
.member{align-items:flex-start}.mread{font-size:12.2px;color:var(--mut);font-weight:600;margin-top:4px;line-height:1.4}
.nclist{display:flex;flex-direction:column}
.ncrow{display:flex;justify-content:space-between;align-items:baseline;padding:8px 0;border-bottom:1px solid var(--line)}
.ncrow:last-child{border:0}.ncname{font-family:Fredoka;font-weight:600;font-size:15px}
.ncmeta{font-size:11.5px;color:var(--mut);font-weight:700;white-space:nowrap;margin-left:12px}
.statrow{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:4px 0 6px}
.stat{background:#F6F8FD;border:1px solid var(--line);border-radius:15px;padding:11px 6px;text-align:center}
.stat .n{font-family:Fredoka;font-weight:600;font-size:18px}.stat .l{font-size:10.5px;color:var(--mut);font-weight:700;margin-top:2px}
.bal{height:14px;border-radius:9px;overflow:hidden;display:flex;margin:6px 0}
.narr{font-size:14px;line-height:1.62;font-weight:600;color:#1e293b}
.gen{display:flex;flex-direction:column;gap:9px;padding:2px 0}
.gen .gl{height:11px;border-radius:6px;background:linear-gradient(90deg,#e9ebf2 25%,#f4f5f9 50%,#e9ebf2 75%);background-size:200% 100%;animation:sh 1.25s ease-in-out infinite}
.gen .genlbl{font-size:11px;font-weight:700;color:#9aa0b4;margin-top:4px;letter-spacing:.2px}
@keyframes sh{0%{background-position:200% 0}100%{background-position:-200% 0}}
.rt{display:flex;align-items:center;gap:9px;margin:7px 0}.rt .k{width:66px;font-size:11.5px;color:var(--mut);font-weight:800}
.rt .bar{flex:1;height:9px;border-radius:6px;background:#EDF1F8;overflow:hidden}.rt .bar i{display:block;height:100%;background:var(--blue)}
.rt .v{width:40px;text-align:right;font-size:11.5px;font-weight:800;color:var(--mut)}
.fade{animation:fade .28s ease}@keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){.fade{animation:none}}
.starline{color:var(--amber);font-size:15px;letter-spacing:2px}.stardim{color:#E2E8F0}
.hltag{font-size:10.5px;font-weight:800;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin:14px 0 3px}
.hlrow{display:flex;margin:2px 0}.hlrow.me{justify-content:flex-end}
.bub{max-width:82%;padding:9px 13px;border-radius:17px;font-size:14px;line-height:1.38;word-wrap:break-word;white-space:pre-wrap}
.hlrow.me .bub{background:#0b84fe;color:#fff;border-bottom-right-radius:5px}
.hlrow.them .bub{background:#2c2c34;color:#f2f2f7;border-bottom-left-radius:5px}
.bubwho{font-size:11px;font-weight:800;color:#8e8e99;margin-bottom:2px}
.wcloud{display:flex;flex-wrap:wrap;align-items:baseline;gap:9px 16px;padding:8px 2px 2px;font-family:Fredoka}
.clw{display:inline-flex;align-items:baseline;gap:3px;line-height:1;color:#1c1c22;letter-spacing:.2px}
.clw .wn{font-size:11px;font-weight:800;font-family:Nunito}
.rfp{display:flex;flex-direction:column;gap:16px}
.rfpside .rl{font-size:12px;color:#8a8a95;font-weight:700;margin-bottom:6px;font-family:Nunito}
.rfrow{display:flex;align-items:center;gap:9px;margin:5px 0}
.rfe{font-size:17px;width:22px;text-align:center;flex:none}
.rfbar{flex:1;height:9px;border-radius:6px;background:#ececf1;overflow:hidden}
.rfbar>i{display:block;height:100%;border-radius:6px}
.rfn{font-size:12px;font-weight:800;color:#3a3a44;width:32px;text-align:right;font-family:Nunito}
.rfempty{color:#9a9aa4;font-size:12.5px}
.wlaunch{display:flex;align-items:center;gap:12px;background:var(--grad);color:#fff;border-radius:20px;padding:15px 16px;box-shadow:var(--shadow);cursor:pointer;margin-top:14px;margin-bottom:6px}
.wlaunch .t{font-family:Fredoka;font-weight:700;font-size:18px}.wlaunch .s{font-size:12.5px;font-weight:700;opacity:.9}
.wrapv{position:absolute;inset:0;z-index:60;background:#0b1020;overflow:hidden}
.wslide{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:60px 30px 80px;color:#fff}
.wprog{position:absolute;top:44px;left:14px;right:14px;display:flex;gap:4px;z-index:7}
.wprog i{flex:1;height:3px;border-radius:2px;background:#ffffff44}.wprog i.done{background:#fff}.wprog i.cur{background:#fff}
.wclose{position:absolute;top:52px;right:18px;z-index:8;color:#fff;font-size:20px;cursor:pointer;opacity:.85;font-family:Fredoka;line-height:1}
.wkick{font-size:12.5px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;opacity:.85;margin-bottom:14px}
.wbig{font-family:Fredoka;font-weight:700;font-size:54px;line-height:1.03;margin:2px 0}.wbig.sm{font-size:34px}.wbig.xl{font-size:72px}
.wsub{font-size:16px;font-weight:700;opacity:.96;margin-top:18px;max-width:280px;line-height:1.5}
.wtap{position:absolute;top:0;bottom:0;z-index:5;cursor:pointer}.wtap.l{left:0;width:35%}.wtap.r{right:0;width:65%}
.wemoji{font-size:92px;margin:4px 0;line-height:1}
.wchips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:8px}
.wchip{background:#ffffff26;border:1px solid #ffffff40;border-radius:16px;padding:8px 13px;font-size:13.5px;font-weight:800}
.wfin{animation:wfin .45s ease}@keyframes wfin{from{opacity:0;transform:scale(.98)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){.wfin{animation:none}}
.phone.home{background:linear-gradient(165deg,#5b6cff,#9b59f6 48%,#ff6ec7)}
.hb{position:absolute;bottom:7px;left:50%;transform:translateX(-50%);width:120px;height:5px;border-radius:3px;background:#0b102055;z-index:55;cursor:pointer}
.phone.home .hb{background:#ffffffaa}
/* on a real phone, drop the phone-in-a-phone chrome and go full-screen */
@media(max-width:680px){
 body{display:block;padding:0;background:var(--bg)}
 .phone{width:100%;max-width:none;height:100dvh;max-height:none;border-radius:0;box-shadow:none;transform:none;margin:0}
 .notch{display:none}
 .screen{padding-top:max(16px,env(safe-area-inset-top));padding-bottom:calc(94px + env(safe-area-inset-bottom))}
 .nav{height:calc(76px + env(safe-area-inset-bottom));padding-bottom:calc(10px + env(safe-area-inset-bottom))}
 .hb{bottom:calc(7px + env(safe-area-inset-bottom))}
}
.springboard{min-height:100%;display:flex;flex-direction:column;padding-top:8px}
.sb-top{text-align:center;color:#fff;margin:4px 0 26px;text-shadow:0 2px 10px rgba(0,0,0,.28)}
.sb-time{font-family:Fredoka;font-size:62px;font-weight:600;line-height:1}
.sb-date{font-size:15px;font-weight:700;opacity:.96;margin-top:2px}
.grid-apps{display:grid;grid-template-columns:repeat(4,1fr);gap:22px 12px}
.appicon{display:flex;flex-direction:column;align-items:center;gap:7px;cursor:pointer}
.appicon .ic{width:62px;height:62px;border-radius:14px;box-shadow:0 8px 18px rgba(0,0,0,.28);transition:transform .12s}
.appicon .ic svg{width:100%;height:100%;display:block}
.appicon:active .ic{transform:scale(.9)}
.appicon.locked .ic{filter:grayscale(.7);opacity:.55}
.appicon.locked .nm{opacity:.6}
.impbtn{background:#0f172a;color:#fff;border:0;border-radius:10px;padding:10px 16px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.impbtn.sec{background:#eef1f7;color:#0f172a}
.idrop{border:2px dashed #cbd5e1;border-radius:14px;padding:26px 16px;text-align:center;cursor:pointer;background:#fff;transition:.15s}
.idrop.over{border-color:#E1306C;background:#fff5f9}
.idrop .big{font-size:32px}.idrop .t{font-weight:700;font-size:15px;margin:8px 0 3px}.idrop .s{color:var(--mut);font-size:12.5px}
.ifield{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:9px;font-size:13.5px;font-family:inherit;margin-top:4px}
.ilabel{font-size:12px;font-weight:700;color:var(--mut)}
.ipill{display:inline-flex;align-items:center;font-size:11.5px;font-weight:700;padding:3px 9px;border-radius:999px}
.ipill.ok{background:#dcfce7;color:#166534}.ipill.bad{background:#fee2e2;color:#991b1b}.ipill.wait{background:#fef9c3;color:#854d0e}
.iprog{height:7px;background:#eef1f7;border-radius:5px;overflow:hidden;margin:8px 0 5px}.iprog>i{display:block;height:100%;width:0;background:linear-gradient(90deg,#FA7E1E,#D62976);transition:width .3s}
.steps{list-style:none;margin:4px 0 0;padding:0;counter-reset:s}
.steps li{position:relative;padding:0 0 13px 34px;font-size:13.5px;line-height:1.5;color:#334155}
.steps li:last-child{padding-bottom:2px}
.steps li:before{counter-increment:s;content:counter(s);position:absolute;left:0;top:-1px;width:23px;height:23px;border-radius:50%;background:linear-gradient(135deg,#f9ce34,#ee2a7b);color:#fff;font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center;font-family:Nunito}
.steps li:not(:last-child):after{content:"";position:absolute;left:11px;top:24px;bottom:1px;width:2px;background:#f3d9e4}
.kbd{display:inline-block;background:#f1f3f9;border:1px solid #e2e8f0;border-radius:6px;padding:0 7px;font-size:12px;font-weight:700;color:#1e293b;line-height:18px}
.kbd.hot{background:#fce7f0;border-color:#f6c2d8;color:#be1e63}
.appicon .nm{font-size:11.5px;color:#fff;font-weight:700;text-shadow:0 1px 3px rgba(0,0,0,.45)}
.igbig{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.igstat{border-radius:18px;padding:14px;color:#fff;min-height:88px;display:flex;flex-direction:column;justify-content:flex-end;position:relative;overflow:hidden}
.igstat .n{font-family:Fredoka;font-size:26px;font-weight:700;line-height:1}.igstat .l{font-size:12px;font-weight:700;opacity:.93;margin-top:3px}
.igstat .em{position:absolute;top:8px;right:10px;font-size:26px}
.mixbar{display:flex;height:20px;border-radius:10px;overflow:hidden;margin:4px 0}.mixbar i{height:100%}
.creator{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)}
.creator:last-child{border:0}.cav{width:34px;height:34px;border-radius:50%;flex:none;display:grid;place-items:center;color:#fff;font-weight:700;font-size:13px;font-family:Fredoka}
.creator .h{flex:1;font-weight:700;font-size:14px}.creator .c{color:var(--mut);font-weight:800;font-size:12.5px}
</style></head><body>
<div class=phone><div class=notch></div><div class=screen id=screen></div><nav class=nav id=nav></nav><div class=hb onclick=showHome()></div></div>
<script>
let APP=__DATA__;let APPS=APP.apps;
let D=null,CUR=null,CURDET=null,CURMEM=null;
const SVG={
 overview:'<svg viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M3 3v18h18"/><path d="M7 15l3-4 3 2 4-6"/></svg>',
 people:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
 groups:'<svg viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-6.4A8 8 0 1 1 21 12z"/></svg>',
 you:'<svg viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M12 3l1.9 4.7L19 9l-4 3.4L16.2 18 12 15.3 7.8 18 9 12.4 5 9l5.1-1.3z"/></svg>',
 bell:'<svg viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>',
 back:'<svg viewBox="0 0 24 24" width=20 height=20 fill=none stroke=currentColor stroke-width=2.4 stroke-linecap=round stroke-linejoin=round><path d="M15 18l-6-6 6-6"/></svg>'};
const $=h=>{const t=document.createElement('template');t.innerHTML=h.trim();return t.content.firstChild};
const scr=document.getElementById('screen');
const esc=s=>String(s);
const num=n=>n.toLocaleString();
const kk=n=>n>=1000?(n/1000).toFixed(1)+'k':''+n;
const init=n=>n.replace(/[^A-Za-z ]/g,'').trim().split(/\s+/).slice(0,2).map(w=>w[0]||'').join('').toUpperCase()||'#';
const DAYS=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const BANDS=['Early','Morn','Aft','Eve','Late'];
const BANDS_FULL=['early morning','morning','afternoon','evening','late night'];
const MCOL=['#2563EB','#F43F7E','#0EA5E9','#6366F1','#F59E0B','#EF4444','#8B5CF6','#14B8A6'];
const mcolor=(m,i)=>m.me?'#059669':MCOL[i%MCOL.length];
function bars(v,color){const mx=Math.max(...v,1),W=300,H=64,step=W/Math.max(1,v.length-1);
 const line=v.map((x,i)=>`${(i*step).toFixed(1)},${(H-x/mx*H).toFixed(1)}`).join(' ');
 return `<svg viewBox="0 -4 ${W} ${H+6}"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs><polygon points="0,${H} ${line} ${W},${H}" fill="url(#g)"/><polyline points="${line}" fill="none" stroke="${color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`}
function spark(v,color){const mx=Math.max(...v,1),W=64,H=22;const p=v.map((x,i)=>`${(i/Math.max(1,v.length-1)*W).toFixed(1)},${(H-x/mx*H).toFixed(1)}`).join(' ');return `<svg width="64" height="22"><polyline points="${p}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`}
let _cid=0;const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function tsChart(seriesArr,colors){const M=D.months||[],all=seriesArr.flat(),mx=Math.max(...all,1),n=seriesArr[0].length,gid='ts'+(++_cid);
 const W=640,H=210,PB=56,PT=12,PL=12,PR=8;
 const X=i=>n<2?W/2:PL+i/(n-1)*(W-PL-PR), Y=v=>PT+(1-v/mx)*(H-PT-PB);
 let ticks='',labels='';
 M.forEach((m,i)=>{const x=X(i).toFixed(1),yr=m.slice(5)=='01';
  ticks+=`<line x1="${x}" x2="${x}" y1="${H-PB}" y2="${yr?PT:H-PB-7}" stroke="${yr?'#c9ccd6':'#e4e6ee'}" stroke-width="1"/>`;
  if(i%3==0){const t=MON[+m.slice(5)-1]+" '"+m.slice(2,4),ly=H-PB+14;labels+=`<text x="${x}" y="${ly}" transform="rotate(-45 ${x} ${ly})" text-anchor="end" fill="#8e8e99" font-size="11" font-family="Nunito">${t}</text>`}});
 let defs='',paths='';
 seriesArr.forEach((vals,si)=>{const c=colors[si],g=gid+'_'+si;defs+=`<linearGradient id="${g}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c}" stop-opacity="0.3"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></linearGradient>`;
  const line=vals.map((v,i)=>`${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
  paths+=`<polygon points="${PL},${(H-PB).toFixed(0)} ${line} ${(W-PR)},${(H-PB).toFixed(0)}" fill="url(#${g})"/><polyline points="${line}" fill="none" stroke="${c}" stroke-width="${si==seriesArr.length-1?2.4:1.6}" stroke-linecap="round" stroke-linejoin="round"/>`});
 return `<svg viewBox="0 0 ${W} ${H}"><defs>${defs}</defs>${ticks}<line x1="0" x2="${W}" y1="${H-PB}" y2="${H-PB}" stroke="#d2d5df" stroke-width="1"/>${paths}${labels}</svg>`;
}
function monthlyChart(vals,color){return tsChart([vals],[color])}
function wordCloud(words,color){if(!words||!words.length)return '';const cs=words.map(w=>w[1]),mx=Math.max(...cs),mn=Math.min(...cs);
 return '<div class=wcloud>'+words.map(([w,n])=>{const t=mx>mn?(n-mn)/(mx-mn):1;const fs=(15+t*13).toFixed(0);const op=(0.72+t*0.28).toFixed(2);const wt=t>0.62?700:t>0.32?600:500;
  return `<span class=clw title="${n} times" style="font-size:${fs}px;font-weight:${wt};opacity:${op}">${esc(w)}<span class=wn style="color:${color}">${n}</span></span>`}).join('')+'</div>';
}
const RMAP={Loved:'❤️',Liked:'👍',Disliked:'👎',Laughed:'😂',Emphasized:'‼️',Emphasised:'‼️',Questioned:'❓'};
function remoji(k){return RMAP[k]||k}
function rsum(p){return (p||[]).reduce((a,b)=>a+b[1],0)}
function reactFP(pairs,color){if(!pairs||!pairs.length)return '<div class=rfempty>none yet</div>';const mx=Math.max(...pairs.map(p=>p[1]));
 return pairs.map(([k,n])=>`<div class=rfrow><span class=rfe>${remoji(k)}</span><div class=rfbar><i style="width:${Math.max(7,n/mx*100).toFixed(0)}%;background:${color}"></i></div><span class=rfn>${n}</span></div>`).join('');}
function reactCard(p,accent){const you=p.reactMe||[],them=p.reactThem||[];if(!you.length&&!them.length)return '';
 const first=esc((p.n||'').split(' ')[0]),grp=p.group,youL=grp?'You react to the group':'You react to '+first,themL=grp?'The group reacts to you':first+' reacts to you';
 return `<div class=card><div class=rowh><h3 class=f>Reaction fingerprint</h3><span class=pill>${rsum(you)+rsum(them)} tapbacks</span></div>
  <div class=rfp><div class=rfpside><div class=rl>${youL} · ${rsum(you)}</div>${reactFP(you,'#0b84fe')}</div>
  <div class=rfpside><div class=rl>${themL} · ${rsum(them)}</div>${reactFP(them,accent)}</div></div></div>`;}
function igContactCard(p){const ig=p.ig,tot=(ig.reels+ig.text_me+ig.text_them)||1;
 return `<div class=card><div class=rowh><h3 class=f>Reels vs words</h3><span class=pill>${ig.reel_ratio}× reels/text</span></div>
  <div class=rt><span class=k>Reels</span><span class=bar><i style="width:${(ig.reels/tot*100).toFixed(0)}%;background:#E1306C"></i></span><span class=v>${num(ig.reels)}</span></div>
  <div class=rt><span class=k>Words</span><span class=bar><i style="width:${((ig.text_me+ig.text_them)/tot*100).toFixed(0)}%;background:#405DE6"></i></span><span class=v>${num(ig.text_me+ig.text_them)}</span></div>
  <div class=legend style=margin-top:8px>you shared ${num(ig.reels_me)} · they shared ${num(ig.reels_them)} · reactions you gave ${num(ig.react_given)}, got ${num(ig.react_recv)}</div>
  ${ig.owners&&ig.owners.length&&ig.owners[0][0]?`<div class=legend style=margin-top:4px>top creator you trade: @${esc(ig.owners[0][0])} (${num(ig.owners[0][1])})</div>`:''}</div>`;
}
function spd(t){if(t==='—')return 8;const s=t.endsWith('s')?parseFloat(t):t.endsWith('m')?parseFloat(t)*60:t.endsWith('h')?parseFloat(t)*3600:parseFloat(t)*86400;return Math.max(8,Math.min(100,100-Math.log(Math.max(s,20)/20)/Math.log(3600/20)*100)).toFixed(0)}
function durS(s){if(s==null)return '—';return s<60?Math.round(s)+'s':s<3600?Math.round(s/60)+'m':s<86400?(s/3600).toFixed(1)+'h':(s/86400).toFixed(1)+'d'}
function memberDetail(gi,mi){const g=D.groups[gi],m=g.members[mi],pr=m.prof||{},col=mcolor(m,mi);const rt=pr.reply_med_s,rtot=((pr.given||0)+(pr.recv||0))||1;scr.className='screen fade';
 CURMEM={app:CUR&&CUR.id,gi:gi,mi:mi};CURDET=null;
 scr.innerHTML=`<span class=back onclick="detail('gr',${gi})">${SVG.back} ${esc(g.n)}</span>
  <div class=dhead><div class=av style="background:${col}">${init(m.name)}</div><div class=f style=font-size:22px>${esc(m.name)}${m.me?' (you)':''}</div><div class=sub>in “${esc(g.n)}” · ${m.share}% of all messages</div></div>
  <div class=statrow><div class=stat title="messages in this group"><div class=n>${kk(m.msgs)}</div><div class=l>messages</div></div>
   <div class=stat title="their words per message"><div class=n>${pr.wpm!=null?pr.wpm:'—'}</div><div class=l>words/msg</div></div>
   <div class=stat title="how fast they jump into the chat"><div class=n>${durS(rt)}</div><div class=l>reply speed</div></div></div>
  <div class=card id=mbvibe style="${m.read?'':'display:none'}">${m.read?`<div class=rowh><h3 class=f>Their vibe</h3><span class=pill>AI · on-device</span></div><div class=narr>${esc(m.read)}</div>`:''}</div>
  <div class=card><div class=rowh><h3 class=f>How they show up</h3></div>
   <div class=rt title="time from someone else's message to theirs"><span class=k>Reply speed</span><span class=bar><i style="width:${spd(durS(rt))}%;background:${col}"></i></span><span class=v>${durS(rt)}</span></div>
   <div class=legend>starts a fresh thread <b>${pr.starts||0}×</b> · most active in the <b>${pr.peak||'—'}</b></div></div>
  ${((pr.react_given&&pr.react_given.length)||(pr.react_recv&&pr.react_recv.length))?`<div class=card><div class=rowh><h3 class=f>Reaction fingerprint</h3><span class=pill>${rsum(pr.react_given)+rsum(pr.react_recv)} tapbacks</span></div>
   <div class=rfp><div class=rfpside><div class=rl>Reactions they give · ${rsum(pr.react_given)}</div>${reactFP(pr.react_given,col)}</div>
   <div class=rfpside><div class=rl>Reactions they get · ${rsum(pr.react_recv)}</div>${reactFP(pr.react_recv,'#0b84fe')}</div></div></div>`:''}
  ${(pr.emoji&&pr.emoji.length)?`<div class=card><div class=rowh><h3 class=f>Their emoji</h3></div><div class=emoji-row>${pr.emoji.map(([e,n])=>`<div class=e title="${n} times">${e}<b>${n}</b></div>`).join('')}</div></div>`:''}
  ${(pr.monthly&&pr.monthly.some(x=>x))?`<div class=card><div class=rowh><h3 class=f>Their rhythm here</h3><span class=pill>msgs / month</span></div>${monthlyChart(pr.monthly,col)}</div>`:''}
  ${(pr.words_top&&pr.words_top.length)?`<div class=card><div class=rowh><h3 class=f>Their words</h3><span class=pill>size = how often</span></div>${wordCloud(pr.words_top,col)}</div>`:''}`;
 scr.scrollTo(0,0);
}
window.memberDetail=memberDetail;
function logoMark(){return '<svg width=18 height=18 viewBox="0 0 24 24" fill=none stroke=white stroke-width=2.4 stroke-linecap=round stroke-linejoin=round><path d="M21 11.5a7.5 7.5 0 0 1-10.9 6.7L4 20l1.8-5.3A7.5 7.5 0 1 1 21 11.5z"/><path d="M8.5 11h.01M12 11h.01M15.5 11h.01"/></svg>'}

function overview(){const m=D.me;const hmx=Math.max(1,...D.heat.flat());scr.className='screen fade';scr.innerHTML=`
 <div class=topbar><div class=brand><div class=logo>${logoMark()}</div><div><div class="title f">Textprint</div><div class=sub>${m.name} · ${num(m.sent)} sent</div></div></div><div class=iconbtn>${SVG.bell}</div></div>
 <div class=perso><div class=k>${m.persona.k}</div><div class=t id=persona-t>${m.persona.t}</div><div class=b id=persona-b>${m.persona.b}</div><div class=spark>${m.topEmoji}</div></div>
 ${D.wrapped&&D.wrapped.volume?`<div class=wlaunch onclick=openWrapped()><div style=font-size:26px>✨</div><div><div class=t>Your Wrapped</div><div class=s>the year, one reveal at a time</div></div><svg style=margin-left:auto width=20 height=20 viewBox="0 0 24 24" fill=none stroke=white stroke-width=2.5 stroke-linecap=round stroke-linejoin=round><path d="M9 6l6 6-6 6"/></svg></div>`:''}
 ${D.platform=='instagram'&&D.ig?igHero():''}
 <div class=sec>Your headline numbers</div>
 <div class=chips>
  <div class="chip c-blue"><span class=em>💬</span><div class=n>${kk(m.sent)}</div><div class=l>messages sent</div></div>
  <div class="chip c-green"><span class=em>🔥</span><div class=n>${m.streak}</div><div class=l>day streak</div></div>
  <div class="chip c-indigo"><span class=em>${m.topEmoji}</span><div class=n>${num(m.tapbacks)}</div><div class=l>tapbacks given</div></div>
  <div class="chip c-pink"><span class=em>🌙</span><div class=n>${m.latePct}%</div><div class=l>after midnight</div></div></div>
 <div class="card" style=margin-top:22px><div class=rowh><h3 class=f>Activity</h3><span class=pill>messages / month</span></div>${tsChart([D.activity],['#2563EB'])}</div>
 <div class=card><div class=rowh><h3 class=f>When you text</h3><span class=pill>peak: ${BANDS_FULL[maxBand()]}</span></div>
  <div class=hm2><div></div>${DAYS.map(d=>`<div class=lab2>${d}</div>`).join('')}${D.heat.map((row,bi)=>`<div class=row2l>${BANDS[bi]}</div>`+row.map((v,di)=>`<div class=cell title="${DAYS[di]} ${BANDS_FULL[bi]} · ${v} text${v==1?'':'s'}" style="background:rgba(37,99,235,${(.08+v/hmx*.92).toFixed(2)})"></div>`).join('')).join('')}</div>
  <div class=legend style=margin-top:8px>hover a square for the exact count</div></div>
 <div class=card><div class=rowh><h3 class=f>Your emoji</h3><span class=pill>${m.topEmoji} is home</span></div><div class=emoji-row>${D.emoji.map(([e,n])=>`<div class=e>${e}<b>${n}</b></div>`).join('')}</div></div>
 <div class=card><div class=rowh><h3 class=f>Mood</h3><span class=pill>your messages</span></div>
  <div class=mood><i style="width:${D.mood.pos}%;background:#059669"></i><i style="width:${D.mood.neu}%;background:#CBD5E1"></i><i style="width:${D.mood.neg}%;background:#F43F7E"></i></div>
  <div class=legend><span><span class=dot style=background:#059669></span>${D.mood.pos}% positive</span><span><span class=dot style=background:#CBD5E1></span>${D.mood.neu}% neutral</span><span><span class=dot style=background:#F43F7E></span>${D.mood.neg}% negative</span></div></div>`}
function maxBand(){let bi=0,bv=-1;D.heat.forEach((r,i)=>{const s=r.reduce((a,b)=>a+b,0);if(s>bv){bv=s;bi=i}});return bi}
function igHero(){const ig=D.ig,mix=ig.mix,cols={reels:'#E1306C',text:'#405DE6',media:'#F59E0B'};
 return `<div class=sec>You speak in reels</div>
  <div class=igbig>
   <div class=igstat style="background:linear-gradient(135deg,#f9ce34,#ee2a7b)"><span class=em>🎬</span><div class=n>${kk(ig.reels)}</div><div class=l>reels & posts shared</div></div>
   <div class=igstat style="background:linear-gradient(135deg,#833ab4,#fd1d1d)"><span class=em>❤️</span><div class=n>${num(ig.react_given+ig.react_recv)}</div><div class=l>reactions traded</div></div></div>
  <div class="card" style="margin-top:20px"><div class=rowh><h3 class=f>Content mix</h3><span class=pill>how you actually DM</span></div>
   <div class=mixbar>${mix.map(x=>`<i title="${num(x.n)} ${x.k}" style="width:${x.pct}%;background:${cols[x.k]}"></i>`).join('')}</div>
   <div class=legend>${mix.map(x=>`<span><span class=dot style=background:${cols[x.k]}></span>${x.pct}% ${x.k}</span>`).join('')}</div></div>
  <div class=card><div class=rowh><h3 class=f>Your reel taste</h3><span class=pill>most-shared creators</span></div>
   ${ig.owners.filter(o=>o[0]).slice(0,6).map((o,i)=>`<div class=creator><div class=cav style="background:${['#E1306C','#405DE6','#F59E0B','#833ab4','#00c6ff','#43cea2'][i%6]}">${init(o[0])}</div><div class=h>@${esc(o[0])}</div><div class=c>${num(o[1])} reels</div></div>`).join('')}</div>`;
}

function list(items,tab,label,note){scr.className='screen fade';
 scr.innerHTML=`<div class=topbar><div class="title f">${label}</div><div class=iconbtn>${SVG.bell}</div></div>${tab=='pp'?'<input class=search placeholder="Search contacts" oninput="filterC(this.value)">':''}<div class=sec>${note}</div><div id=rows></div>`;
 const rows=document.getElementById('rows');
 items.forEach((p,i)=>{rows.appendChild($(`<div class=contact data-n="${(p.n||'').toLowerCase()}" onclick="detail('${tab}',${i})">
   <div class=av style="background:${p.c}">${init(p.n)}</div>
   <div class=cbody><div class=nm>${esc(p.n)} ${p.badge[1]?`<span class="badge ${p.badge[0]}">${p.badge[1]}</span>`:''}</div><div class=snip>${esc(p.snip)}</div></div>
   <div class=cmeta><div class=cnt>${kk(p.ig?p.msgs+p.ig.reels_me+p.ig.reels_them:p.msgs)}</div><div class=rate ${p.group?'style=background:#6366F1':''}>${p.group?p.you+'% you':(p.ig?'🎬 '+kk(p.ig.reels_me+p.ig.reels_them):p.rating)}</div></div></div>`))})}
function filterC(q){q=q.toLowerCase();document.querySelectorAll('#rows .contact').forEach(r=>{r.style.display=r.dataset.n.includes(q)?'':'none'})}
function peopleList(){list(D.people,'pp','People','Sorted by how much you text')}
function groupsList(){D.groups.length?list(D.groups,'gr','Group chats','Where the chaos lives'):emptyGroups()}
function emptyGroups(){scr.className='screen fade';scr.innerHTML=`<div class=topbar><div class="title f">Group chats</div></div><div class=card style=text-align:center;padding:32px><div style=font-size:34px>👥</div><div class=f style=margin-top:8px>No group chats yet</div><div class=legend style=justify-content:center>None met the message threshold in this export.</div></div>`}

function youTab(){const m=D.me;scr.className='screen fade';scr.innerHTML=`
 <div class=topbar><div class="title f">You</div></div>
 <div class=dhead><div class=av style="background:var(--grad);width:82px;height:82px;font-size:30px">${init(m.name)}</div><div class=f style=font-size:22px>${esc(m.name)}</div><div class=sub>${m.contacts} people · ${kk(m.words)} words written</div></div>
 <div class=statrow><div class=stat><div class=n>${kk(m.sent)}</div><div class=l>sent</div></div><div class=stat><div class=n>${kk(m.received)}</div><div class=l>received</div></div><div class=stat><div class=n>${m.busy}</div><div class=l>busiest day</div></div></div>
 <div class=card><div class=rowh><h3 class=f>How you text</h3><span class=pill>AI · on-device</span></div><div class=narr id=synopsis>${m.synopsis?narrBlocks(m.synopsis):narrPh(5)}</div></div>
 <div class=card><div class=rowh><h3 class=f>Private by design</h3></div><div class=legend style=margin:0>Everything here was computed on your machine. No message ever left the device.</div></div>`}

function detail(tab,i){const p=(tab=='gr'?D.groups:D.people)[i];scr.className='screen fade';
 CURDET={app:CUR&&CUR.id,kind:tab=='gr'?'group':'person',idx:i};CURMEM=null;
 const smx=Math.max(1,...p.stars),sp=p.split,spt=Math.max(1,sp.pos+sp.neu+sp.neg);
 const pc=v=>(100*v/spt).toFixed(0);
 let mid;
 if(p.group){const mmx=Math.max(1,...p.members.map(m=>m.msgs));const nc=p.name_changes||[];
  mid=`<div class=card><div class=rowh><h3 class=f>Who's who in here</h3><span class=pill>${p.members.length} people</span></div>
   ${p.members.map((m,mi)=>`<div class=member style=cursor:pointer onclick="memberDetail(${i},${mi})"><div class=mav style="background:${mcolor(m,mi)}">${init(m.name)}</div>
     <div class=mbody><div class=mname style="${m.me?'color:#059669':''}">${esc(m.name)} <span class=mut style=font-size:12px>›</span></div>
      <div class=mbar><i style="width:${(m.msgs/mmx*100).toFixed(0)}%;background:${mcolor(m,mi)}"></i></div>
      ${m.read?`<div class=mread>${esc(m.read)}</div>`:''}</div>
     <div class=mshare title="${num(m.msgs)} messages">${kk(m.msgs)}<br>${m.share}%</div></div>`).join('')}</div>
   <div class=legend style="margin:-4px 4px 12px">tap anyone for their full breakdown</div>`
   + (nc.length?`<div class=card><div class=rowh><h3 class=f>Name history</h3><span class=pill>${nc.length} renames</span></div>
     <div class=nclist>${nc.slice().reverse().map(x=>`<div class=ncrow><span class=ncname>"${esc(x.name)}"</span><span class=ncmeta>${esc(x.who)} · ${x.ts.slice(0,10)}</span></div>`).join('')}</div>
     <div class=legend style=margin-top:8px>the running joke this group calls itself</div></div>`:'');
 }else{
  mid=`<div class=card><div class=rowh><h3 class=f>Balance</h3><span class=pill>${p.you}% you</span></div>
    <div class=bal><i style="width:${p.you}%;background:#059669" title="you: ${num(p.sent)} messages"></i><i style="flex:1;background:#2563EB" title="${esc(p.n)}: ${num(p.them)} messages"></i></div>
    <div class=legend><span><span class=dot style=background:#059669></span>you ${kk(p.sent)}</span><span><span class=dot style=background:#2563EB></span>${esc(p.n)} ${kk(p.them)}</span></div></div>
   <div class=card><div class=rowh><h3 class=f>Reply speed</h3><span class=pill>median</span></div>
    <div class=legend style="margin:0 0 4px" title="how long to answer when you'd been away — the real 'time to get back to you'">Response time · after a lull</div>
    <div class=rt><span class=k>You</span><span class=bar><i style="width:${spd(p.replyResp)}%"></i></span><span class=v>${p.replyResp}</span></div>
    <div class=rt><span class=k>${esc(p.n.split(' ')[0])}</span><span class=bar><i style="width:${spd(p.theirResp)}%;background:#6366F1"></i></span><span class=v>${p.theirResp}</span></div>
    <div class=legend style="margin:10px 0 4px" title="typical reply while already actively chatting (fast back-and-forth)">In-conversation · active volley</div>
    <div class=rt><span class=k>You</span><span class=bar><i style="width:${spd(p.replyConv)}%;background:#059669"></i></span><span class=v>${p.replyConv}</span></div>
    <div class=rt><span class=k>${esc(p.n.split(' ')[0])}</span><span class=bar><i style="width:${spd(p.theirConv)}%;background:#059669"></i></span><span class=v>${p.theirConv}</span></div>
    <div class=legend style=margin-top:8px>timed from their first unanswered text, so nudges don't reset the clock</div></div>`;
 }
 scr.innerHTML=`<span class=back onclick="go('${tab}')">${SVG.back} ${tab=='gr'?'Groups':'People'}</span>
 <div class=dhead><div class=av style="background:${p.c}">${init(p.n)}</div><div class=f style=font-size:22px>${esc(p.n)}</div>
  <div class=sub>${p.badge[1]||''} · ${p.period[0]} → ${p.period[1]}</div>
  ${p.group&&p.mem.length?`<div class=legend style=justify-content:center;margin-top:6px>${p.mem.map(x=>esc(x)).join(' · ')}</div>`:''}
  <div style=margin-top:6px title="chat rating ${p.rating}/100"><span class=starline>${'★'.repeat(Math.round(p.rating/20))}<span class=stardim>${'★'.repeat(5-Math.round(p.rating/20))}</span></span></div></div>
 <div class=statrow><div class=stat title="total messages exchanged"><div class=n>${kk(p.msgs)}</div><div class=l>messages</div></div>
  <div class=stat title="how long you typically take to first reply after a lull"><div class=n>${p.reply}</div><div class=l>your response</div></div>
  <div class=stat title="avg sentiment of your messages (-1 to +1)"><div class=n>${p.mood>0?'+':''}${p.mood}</div><div class=l>your mood</div></div></div>
 ${(p.narr||(!p.dataOnly&&(window.TP_NARRATING||APP.live)))?`<div class=card><div class=rowh><h3 class=f>The read</h3><span class=pill>AI · on-device</span></div><div class=narr id=narr-${tab=='gr'?'group':'person'}-${i}>${p.narr?narrBlocks(p.narr):narrPh(4)}</div></div>`:''}
 <div class=card id=hlcard style="${(p.highlights&&p.highlights.length)?'':'display:none'}">${hlInner(p)}</div>
 ${mid}
 ${p.ig?igContactCard(p):''}
 <div class=card><div class=rowh><h3 class=f>Monthly rhythm</h3><span class=pill>messages / month</span></div>${monthlyChart(p.spark,p.c)}<div class=legend>${p.period[0]} → ${p.period[1]}</div></div>
 <div class=card><div class=rowh><h3 class=f>Conversations</h3><span class=pill>★ by size</span></div>
  ${p.stars.map((n,s)=>`<div class=rt title="${['1–3','4–9','10–24','25–49','50+'][4-s]} messages"><span class=k style=color:#F59E0B>${'★'.repeat(5-s)}</span><span class=bar><i style="width:${(n/smx*100).toFixed(0)}%;background:#F59E0B"></i></span><span class=v>${n}</span></div>`).join('')}</div>
 <div class=card><div class=rowh><h3 class=f>Sentiment</h3><span class=pill>your messages</span></div>
  <div class=mood><i style="width:${pc(sp.pos)}%;background:#059669" title="${sp.pos} positive"></i><i style="width:${pc(sp.neu)}%;background:#CBD5E1" title="${sp.neu} neutral"></i><i style="width:${pc(sp.neg)}%;background:#F43F7E" title="${sp.neg} negative"></i></div>
  <div class=legend><span><span class=dot style=background:#059669></span>${pc(sp.pos)}% positive</span><span><span class=dot style=background:#CBD5E1></span>${pc(sp.neu)}% neutral</span><span><span class=dot style=background:#F43F7E></span>${pc(sp.neg)}% negative</span></div>
  ${p.group?'':`<div class=legend style=margin-top:6px>avg mood — you <b style=color:#059669>${p.mood>0?'+':''}${p.mood}</b> · ${esc(p.n.split(' ')[0])} <b style=color:#2563EB>${p.moodThem>0?'+':''}${p.moodThem}</b></div>`}</div>
 <div class=card><div class=rowh><h3 class=f>Emoji fingerprint</h3></div><div class=emoji-row>${p.emoji.length?p.emoji.map(([e,n])=>`<div class=e title="${n} times">${e}<b>${n}</b></div>`).join(''):'<span class=legend>no emoji</span>'}</div></div>
 ${reactCard(p,p.c)}
 ${!p.group&&p.words&&p.words.length?`<div class=card><div class=rowh><h3 class=f>${esc(p.n.split(' ')[0])}'s words</h3><span class=pill>size = how often</span></div>${wordCloud(p.words,p.c)}</div>`:''}
 ${!p.group&&p.mywords&&p.mywords.length?`<div class=card><div class=rowh><h3 class=f>Your words with them</h3><span class=pill>size = how often</span></div>${wordCloud(p.mywords,'#0b84fe')}</div>`:''}`}

const WBG=['linear-gradient(160deg,#6366F1,#2563EB)','linear-gradient(160deg,#0EA5E9,#2563EB)','linear-gradient(160deg,#059669,#0EA5E9)','linear-gradient(160deg,#F43F7E,#8B5CF6)','linear-gradient(160deg,#F59E0B,#F43F7E)','linear-gradient(160deg,#8B5CF6,#EC4899)','linear-gradient(160deg,#0f172a,#334155)'];
function openWrapped(){const W=D.wrapped,m=D.me;if(!W||!W.volume)return;const v=W.verbal||{},vol=W.volume;const S=[];
 S.push(`<div class=wkick>✨ Textprint Wrapped</div><div class="wbig xl">${esc(m.name)}</div><div class=wsub>Your year in texts. Tap to move through it.</div>`);
 S.push(`<div class=wkick>You sent</div><div class="wbig xl">${num(vol.sent)}</div><div class=wsub>messages — <b>${vol.per_day}</b> a day, one every <b>${vol.every_min} min</b> you're awake.</div>`);
 if(W.reels_sent)S.push(`<div class=wkick>…and you sent</div><div class="wbig xl">${num(W.reels_sent)}</div><div class=wsub>reels & posts — plus <b>${num(W.reels_recv)}</b> sent back. content is the conversation here.</div>`);
 S.push(`<div class=wkick>You typed</div><div class=wbig>${num(vol.words)}</div><div class=wsub>words. That's a <b>${vol.novel_pages}-page novel</b>, written with your thumbs.</div>`);
 S.push(`<div class=wkick>Time on the keyboard</div><div class="wbig xl">≈ ${vol.hours}h</div><div class=wsub>about <b>${vol.days} days</b> of your life, one text at a time.</div>`);
 if(W.reel_lang)S.push(`<div class=wkick>You and ${esc(W.reel_lang.who)}</div><div class="wbig xl">${num(W.reel_lang.reels)}</div><div class=wsub>reels sent — but only <b>${num(W.reel_lang.words)}</b> words. You don't talk. You speak in reels.</div>`);
 if(W.taste&&W.taste.owners&&W.taste.owners.length)S.push(`<div class=wkick>Your love language is</div><div class=wbig sm>@${esc(W.taste.owners[0][0])}</div><div class=wsub>you shared their reels <b>${num(W.taste.owners[0][1])}</b> times. that's the whole personality.</div>`);
 if(W.reaction)S.push(`<div class=wkick>The reaction economy</div><div class=wemoji>${W.reaction.emoji[0]||'❤️'}</div><div class=wsub>you left <b>${num(W.reaction.given)}</b> reactions and got <b>${num(W.reaction.recv)}</b> back.</div>`);
 if(W.heart_dip)S.push(`<div class=wkick>The ❤️-and-dip</div><div class=wbig>${esc(W.heart_dip.who)}</div><div class=wsub>reacted to you <b>${num(W.heart_dip.reacts)}</b> times… and typed back <b>${num(W.heart_dip.words)}</b> words.</div>`);
 if(v.top_word&&v.top_word[0])S.push(`<div class=wkick>Your most-used word</div><div class=wbig>"${esc(v.top_word[0])}"</div><div class=wsub>you said it <b>${num(v.top_word[1])}</b> times.</div>`);
 if(v.emoji&&v.emoji[0])S.push(`<div class=wkick>Your emoji</div><div class=wemoji>${v.emoji[0]}</div><div class=wsub><b>${num(v.emoji[1])}</b> times. it's basically punctuation now.</div>`);
 if(v.private)S.push(`<div class=wkick>Words only ${esc(v.private.who)} hears you say</div><div class=wchips>${v.private.words.map(w=>`<span class=wchip>${esc(w)}</span>`).join('')}</div><div class=wsub>your private language with them.</div>`);
 if(W.latest)S.push(`<div class=wkick>Your latest text ever</div><div class="wbig xl">${W.latest.time}</div><div class=wsub>to <b>${esc(W.latest.who)}</b>. go to sleep.</div>`);
 if(W.first_person)S.push(`<div class=wkick>Your first text of the day usually goes to</div><div class=wbig>${esc(W.first_person.who)}</div><div class=wsub><b>${W.first_person.days}</b> mornings, they were your first thought.</div>`);
 if(W.streak&&W.streak.who)S.push(`<div class=wkick>Longest streak</div><div class="wbig xl">${W.streak.days}</div><div class=wsub>days straight texting <b>${esc(W.streak.who)}</b> — not one missed.</div>`);
 (W.awards||[]).slice(0,4).forEach(a=>S.push(`<div class=wkick>${esc(a.title)}</div><div class=wbig>${esc(a.who)}</div><div class=wsub>${esc(a.detail)}</div>`));
 if(W.wordy&&W.wordy.ratio>1.4)S.push(`<div class=wkick>You write essays to</div><div class=wbig>${esc(W.wordy.who)}</div><div class=wsub><b>${W.wordy.you}</b> words out, <b>${W.wordy.them}</b> back. you okay?</div>`);
 if(W.fading)S.push(`<div class=wkick>Quietly drifting from</div><div class=wbig>${esc(W.fading.who)}</div><div class=wsub>your messages are down <b>${W.fading.drop}%</b> since the start.</div>`);
 if(W.graveyard)S.push(`<div class=wkick>A conversation that just… stopped</div><div class=wbig>${esc(W.graveyard.who)}</div><div class=wsub>silent for <b>${W.graveyard.days} days</b>. it ended on ${W.graveyard.last}.</div>`);
 if(W.asym_hero&&W.asym_hero.extreme>2.5){const a=W.asym_hero;
   if(a.dir=='you_chase')S.push(`<div class=wkick>And the one that stings</div><div class="wbig sm">You reply to ${esc(a.who)} in</div><div class="wbig xl">${a.you}</div><div class=wsub>they take <b>${a.them}</b> to reply to you.</div>`);
   else S.push(`<div class=wkick>And the one that stings</div><div class="wbig sm">${esc(a.who)} replies to you in</div><div class="wbig xl">${a.them}</div><div class=wsub>you take <b>${a.you}</b> to reply to them.</div>`);}
 S.push(`<div class=wkick>That was your year</div><div class=wemoji>${(v.emoji&&v.emoji[0])||'💬'}</div><div class=wchips><span class=wchip>${kk(vol.sent)} sent</span><span class=wchip>${vol.novel_pages}-pg novel</span><span class=wchip>“${esc(m.persona.t)}”</span></div><div class=wsub>Made with Textprint — all on your device.</div>`);
 let idx=0;const ov=$('<div class=wrapv></div>');document.querySelector('.phone').appendChild(ov);
 function draw(){ov.innerHTML=`<div class=wprog>${S.map((_,i)=>`<i class="${i<idx?'done':i==idx?'cur':''}"></i>`).join('')}</div><div class=wclose onclick=closeWrapped()>✕</div><div class="wslide wfin" style="background:${WBG[idx%WBG.length]}">${S[idx]}</div><div class="wtap l" onclick="wnav(-1)"></div><div class="wtap r" onclick="wnav(1)"></div>`}
 window.wnav=d=>{idx+=d;if(idx<0){idx=0;return}if(idx>=S.length){closeWrapped();return}draw()};
 window.closeWrapped=()=>ov.remove();
 draw();
}
window.openWrapped=openWrapped;
const TABS=[['ov','Overview',SVG.overview,overview],['pp','People',SVG.people,peopleList],['gr','Groups',SVG.groups,groupsList],['yo','You',SVG.you,youTab]];
const nav=document.getElementById('nav');let active='ov';
function go(id){if(!D)return;document.querySelector('.phone').classList.remove('home');nav.style.display='';active=id;const t=TABS.find(t=>t[0]==id);(t?t[3]:overview)();paint();scr.scrollTo(0,0)}
function paint(){nav.innerHTML='';TABS.forEach(([id,label,icon])=>nav.appendChild($(`<button class="${active==id?'on':''}" onclick="go('${id}')">${icon}<span>${label}</span></button>`)))}
function fullIcon(id){return {
 messages:'<svg viewBox="0 0 66.145836 66.145836" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id=imsg gradientUnits="userSpaceOnUse" x1="-25.272568" y1="207.52057" x2="-25.272568" y2="152.9982" gradientTransform="matrix(0.98209275,0,0,0.98209275,-1.0651782,3.7961838)"><stop offset="0" stop-color="#0cbd2a"/><stop offset="1" stop-color="#5bf675"/></linearGradient></defs><g transform="translate(59.483067,-145.8456)"><rect ry="14.567832" rx="14.567832" y="145.8456" x="-59.483067" height="66.145836" width="66.145836" fill="url(#imsg)"/><path fill="#ffffff" d="m -26.410149,157.29606 a 24.278298,20.222157 0 0 0 -24.278105,20.22202 24.278298,20.222157 0 0 0 11.79463,17.31574 27.365264,20.222157 0 0 1 -4.245218,5.94228 23.85735,20.222157 0 0 0 9.86038,-3.87367 24.278298,20.222157 0 0 0 6.868313,0.83768 24.278298,20.222157 0 0 0 24.2781059,-20.22203 24.278298,20.222157 0 0 0 -24.2781059,-20.22202 z"/></g></svg>',
 instagram:'<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id=iicon x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#FEDA75"/><stop offset="0.25" stop-color="#FA7E1E"/><stop offset="0.5" stop-color="#D62976"/><stop offset="0.75" stop-color="#962FBF"/><stop offset="1" stop-color="#4F5BD5"/></linearGradient></defs><rect width="64" height="64" rx="15" fill="url(#iicon)"/><g fill="none" stroke="#ffffff" stroke-width="3.6"><rect x="15.5" y="15.5" width="33" height="33" rx="10"/><circle cx="32" cy="32" r="8.3"/></g><circle cx="42" cy="22" r="2.3" fill="#ffffff"/></svg>',
 settings:'<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id=sicon x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#EBEBF0"/><stop offset="1" stop-color="#8A8A90"/></linearGradient></defs><rect width="64" height="64" rx="15" fill="url(#sicon)"/><path fill="#5b5b62" d="M32 22.5a9.5 9.5 0 1 0 0 19 9.5 9.5 0 0 0 0-19zm0 6a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7z"/><path fill="#5b5b62" d="M30 12h4l1 5.2 3.4 1.4 4.4-2.9 2.8 2.8-2.9 4.4 1.4 3.4 5.2 1v4l-5.2 1-1.4 3.4 2.9 4.4-2.8 2.8-4.4-2.9-3.4 1.4-1 5.2h-4l-1-5.2-3.4-1.4-4.4 2.9-2.8-2.8 2.9-4.4-1.4-3.4-5.2-1v-4l5.2-1 1.4-3.4-2.9-4.4 2.8-2.8 4.4 2.9 3.4-1.4z"/></svg>'}[id]||''}
const APPNAMES={messages:'Messages',instagram:'Instagram'};
function appTiles(){
 const ids=APP.live?Array.from(new Set(['instagram'].concat(APPS.map(a=>a.id)))):APPS.map(a=>a.id);
 return ids.map(id=>{const a=APPS.find(x=>x.id==id),locked=APP.live&&!a;
  return `<div class="appicon${locked?' locked':''}" onclick="openApp('${id}')"><div class=ic>${fullIcon(id)}</div><div class=nm>${esc(a?a.name:APPNAMES[id]||id)}</div></div>`}).join('');
}
function showHome(){D=null;CUR=null;CURDET=null;CURMEM=null;document.querySelector('.phone').classList.add('home');nav.style.display='none';scr.className='screen fade';
 const hint=APP.live&&!hasData()?'tap Settings to import your data':'tap an app';
 scr.innerHTML=`<div class=springboard><div class=sb-top><div class=sb-time>9:41</div><div class=sb-date>${esc(APP.name)} · ${hint}</div></div>
  <div class=grid-apps>${appTiles()}<div class=appicon onclick="openApp('settings')"><div class=ic>${fullIcon('settings')}</div><div class=nm>Settings</div></div></div></div>`;
 scr.scrollTo(0,0);
}
function emptyApp(id){document.querySelector('.phone').classList.remove('home');nav.style.display='none';CUR={id:id};scr.className='screen fade';
 scr.innerHTML=`<span class=back onclick=showHome()>‹ Home</span><div class=card style="text-align:center;padding:30px 20px;margin-top:40px"><div style=width:56px;height:56px;margin:0 auto>${fullIcon(id)}</div><div class=f style="margin-top:12px;font-size:18px">No ${esc(APPNAMES[id]||id)} data yet</div><div class=legend style="justify-content:center;margin-top:6px">Import your export in the Settings app, then it'll show up here.</div><div style=margin-top:16px><button class=impbtn onclick="openApp('settings')">Open Settings</button></div></div>`;
 scr.scrollTo(0,0);
}
function openApp(id){document.querySelector('.phone').classList.remove('home');
 if(id=='settings'){D=null;CUR={id:'settings'};nav.style.display='none';settingsScreen();return}
 const app=APPS.find(a=>a.id==id);if(!app){if(APP.live){emptyApp(id);return}showHome();return}
 D=app.data;CUR=app;active='ov';go('ov');
}
function settingsScreen(){scr.className='screen fade';
 if(APP.live){scr.innerHTML=`<span class=back onclick=showHome()>‹ Home</span><h1 style="margin:6px 0 10px">Settings</h1><div id=importmount></div>`;
  scr.scrollTo(0,0);if(window.tpMountImport)window.tpMountImport();return}
 scr.innerHTML=`<span class=back onclick=showHome()>‹ Home</span><h1 style="margin:6px 0 2px">Settings</h1>
  <div class=card><div class=rowh><h3 class=f>Your data is private</h3></div><div class=legend style=margin:0>Every number here was computed on your device. No message, reel, or reaction ever left your machine.</div></div>
  <div class=card><div class=rowh><h3 class=f>Import</h3></div><div class=legend style="margin:0;line-height:1.7"><b>Messages</b> — export with imessage-exporter (HTML).<br><b>Instagram</b> — Settings → Your activity → Download your information → JSON, then re-run with <b>--ig-export</b>.</div></div>
  <div class=card><div class=rowh><h3 class=f>Connected apps</h3></div>${APPS.map(a=>`<div class=row2><span class=lb><span class=dot style="background:${a.accent}"></span> ${esc(a.name)}</span><span class=chip>${a.data.people.length} people</span></div>`).join('')}</div>`;
 scr.scrollTo(0,0);
}
function narrBlocks(t){return t.split(String.fromCharCode(10)).filter(x=>x.trim()).map(x=>`<p style=margin:0 0 10px>${x}</p>`).join('')||('<p>'+t+'</p>')}
function genInner(n){const w=[94,86,96,72,82];return '<div class=gen>'+Array.from({length:n}).map((_,i)=>`<div class=gl style=width:${w[i%w.length]}%></div>`).join('')+'<div class=genlbl>writing the read…</div></div>'}
function narrPh(n){return window.TP_NARRATING?genInner(n):'<div class=legend style="margin:0">No AI read yet — add a host in Settings, then re-import.</div>'}
function parsePersonaJS(raw){let title='Your Textprint',tag='';raw.split(String.fromCharCode(10)).forEach(l=>{const low=l.toLowerCase();if(low.startsWith('title:'))title=l.split(':').slice(1).join(':').trim().replace(/^"|"$/g,'')||title;else if(low.startsWith('tagline:'))tag=l.split(':').slice(1).join(':').trim().replace(/^"|"$/g,'')});return{title:title,blurb:tag}}
function hlInner(p){if(!p.highlights||!p.highlights.length)return '';return '<div class=rowh><h3 class=f>Message highlights</h3><span class=pill>real messages</span></div>'+p.highlights.map(h=>`<div class=hltag>${esc(h.tag)}${h.react&&h.react.length?' '+h.react.join(''):''} · ${h.date}</div><div class="hlrow ${h.me?'me':'them'}"><div class=bub>${(!h.me&&p.group)?`<div class=bubwho>${esc(h.who)}</div>`:''}${esc(h.text)}</div></div>`).join('')}
// live narration patch (from the host page as reads stream back from the proxy)
function TP_UPDATE(slot,raw){const app=APPS.find(a=>a.id==slot.app);if(!app||!raw)return;const ad=app.data,here=CUR&&CUR.id==slot.app;
 if(slot.kind=='person'||slot.kind=='group'){const arr=slot.kind=='group'?ad.groups:ad.people,e=arr&&arr[slot.idx];if(!e)return;
  e.narr=esc(raw);e.snip=esc((raw.split(String.fromCharCode(10)).filter(x=>x.trim())[0]||'').slice(0,140));
  const el=document.getElementById(`narr-${slot.kind}-${slot.idx}`);if(el&&here){el.innerHTML=narrBlocks(e.narr)}}
 else if(slot.kind=='synopsis'){ad.me.synopsis=esc(raw);const el=document.getElementById('synopsis');if(el&&here)el.innerHTML=narrBlocks(ad.me.synopsis)}
 else if(slot.kind=='persona'){const pp=parsePersonaJS(raw);ad.me.persona.t=esc(pp.title);ad.me.persona.b=esc(pp.blurb);
  if(here&&active=='ov'){const t=document.getElementById('persona-t'),b=document.getElementById('persona-b');if(t)t.innerHTML=ad.me.persona.t;if(b)b.innerHTML=ad.me.persona.b}}}
function TP_HL(slot,items){const app=APPS.find(a=>a.id==slot.app);if(!app||!items||!items.length)return;const ad=app.data;
 const arr=slot.target=='group'?ad.groups:ad.people,e=arr&&arr[slot.idx];if(!e)return;e.highlights=e.highlights||[];
 const have=new Set(e.highlights.map(h=>(h.text||'').slice(0,50)));
 items.forEach(it=>{const k=(it.text||'').slice(0,50);if(!have.has(k)){have.add(k);e.highlights.push(it)}});
 if(CURDET&&CURDET.app==slot.app&&CURDET.kind==slot.target&&CURDET.idx==slot.idx){const c=document.getElementById('hlcard');if(c){c.style.display='';c.innerHTML=hlInner(e)}}}
function TP_MEM(slot,reads){const app=APPS.find(a=>a.id==slot.app);if(!app||!reads)return;const g=app.data.groups[slot.idx];if(!g)return;
 (g.members||[]).forEach(m=>{if(reads[m.name])m.read=esc(reads[m.name])});
 if(CURMEM&&CURMEM.app==slot.app&&CURMEM.gi==slot.idx){const m=g.members[CURMEM.mi],c=document.getElementById('mbvibe');
  if(c&&m&&m.read){c.style.display='';c.innerHTML='<div class=rowh><h3 class=f>Their vibe</h3><span class=pill>AI · on-device</span></div><div class=narr>'+m.read+'</div>'}}}
window.addEventListener('message',function(ev){const d=ev.data||{};
 if(d.type=='tp-narr')TP_UPDATE(d.slot,d.text);
 else if(d.type=='tp-highlights')TP_HL(d.slot,d.items);
 else if(d.type=='tp-members')TP_MEM(d.slot,d.reads);
 else if(d.type=='tp-ping'&&ev.source)ev.source.postMessage({type:'tp-ready'},'*')});
window.TP_UPDATE=TP_UPDATE;window.TP_HL=TP_HL;window.TP_MEM=TP_MEM;
window.go=go;window.detail=detail;window.filterC=filterC;window.showHome=showHome;window.openApp=openApp;
window.APP=APP;window.APPS=APPS;window.hasData=function(){return APPS&&APPS.length>0};window.TP_NARRATING=false;
showHome();
try{if(window.parent&&window.parent!==window)window.parent.postMessage({type:'tp-ready'},'*')}catch(e){}
</script>__LIBS__</body></html>"""
