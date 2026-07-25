"""Builds the PRIVATE morning-brief dashboard (HTML), fully SERVER-RENDERED.

All content is rendered into the HTML on the Python side, so the page displays
completely with NO JavaScript — it works in Gmail's attachment preview, on mobile,
and in clients that strip scripts. JavaScript is an optional enhancement that only
powers the search + label filtering of the mail list (progressive enhancement).

PRIVATE (subjects/senders) — never published to the public page.
"""
import html
import re
from datetime import datetime

_STYLE = r"""<style>
  :root{
    --bg:#F6F7F9; --card:#FFFFFF; --border:#E5E7EB; --ink:#1B2333; --ink-soft:#697586;
    --accent:#2E5A87; --track:#EBEDF0;
    --urgent:#DC2626; --urgent-bg:#FCEBEB; --reply:#C2740B; --reply-bg:#FBF0DC;
    --payment:#0E8A5F; --payment-bg:#E4F2EC; --deadline:#7C4DD6; --deadline-bg:#F0EAFB;
    --waiting:#2563EB; --waiting-bg:#E9EFFC; --info:#6B7280; --info-bg:#F0F0EC;
    --shadow:0 1px 2px rgba(31,39,46,0.04),0 6px 20px rgba(31,39,46,0.05);
    --font-display:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
    --font-sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  }
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font-sans);
       -webkit-font-smoothing:antialiased;}
  .wrap{max-width:660px;margin:0 auto;padding:30px 18px 52px;}
  .eyebrow{margin:0;font-size:12px;letter-spacing:0.14em;text-transform:uppercase;color:var(--ink-soft);font-weight:600;}
  h1{margin:5px 0 3px;font-size:26px;font-weight:700;letter-spacing:-0.02em;}
  .sub{margin:0 0 20px;color:var(--ink-soft);font-size:14px;}
  .topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px;padding-bottom:13px;border-bottom:1px solid var(--border);}
  .brand{display:flex;align-items:center;gap:9px;font-size:12.5px;font-weight:700;letter-spacing:0.09em;text-transform:uppercase;color:var(--ink);}
  .brand .mark{width:15px;height:15px;border-radius:5px;background:var(--accent);}
  .updated{font-size:12px;color:var(--ink-soft);font-variant-numeric:tabular-nums;}
  .card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:18px 20px;
        box-shadow:var(--shadow);margin-bottom:14px;}
  .h2{margin:0 0 13px;font-size:13px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:var(--ink-soft);}
  .h2 .count{color:var(--ink-soft);font-weight:600;}
  .summary{font-size:15px;line-height:1.6;}
  .priorities{list-style:none;margin:15px 0 0;padding:0;display:flex;flex-direction:column;gap:9px;}
  .priorities li{display:flex;gap:10px;align-items:flex-start;font-size:14.5px;line-height:1.4;}
  .priorities .rank{flex:none;width:20px;height:20px;border-radius:50%;background:var(--ink);color:#fff;
                    font-size:11px;font-weight:700;display:grid;place-items:center;margin-top:1px;}
  /* needs-you list */
  .need{display:flex;flex-direction:column;gap:4px;padding:12px 0;border-top:1px solid var(--border);}
  .need:first-child{border-top:none;padding-top:0;}
  .need-top{display:flex;align-items:baseline;gap:9px;}
  .need-subj{font-weight:600;font-size:15px;flex:1;line-height:1.35;}
  .need-from{font-size:12.5px;color:var(--ink-soft);}
  .need-action{font-size:13.5px;color:var(--ink);opacity:.85;margin-top:2px;}
  .empty-good{display:flex;gap:10px;align-items:center;font-size:15px;color:var(--payment);}
  .empty-good .dot{width:22px;height:22px;border-radius:50%;background:var(--payment-bg);color:var(--payment);
                   display:grid;place-items:center;font-weight:700;flex:none;}
  /* label pill */
  .pill{flex:none;font-size:11px;font-weight:700;letter-spacing:.02em;padding:3px 9px;border-radius:999px;white-space:nowrap;}
  .lbl-urgent{color:var(--urgent);background:var(--urgent-bg);}
  .lbl-reply{color:var(--reply);background:var(--reply-bg);}
  .lbl-payment{color:var(--payment);background:var(--payment-bg);}
  .lbl-deadline{color:var(--deadline);background:var(--deadline-bg);}
  .lbl-waiting{color:var(--waiting);background:var(--waiting-bg);}
  .lbl-info{color:var(--info);background:var(--info-bg);}
  .lbl-shipping{color:#0E7490;background:#E2F1F4;}
  .lbl-receipt{color:#4B7A52;background:#EAF1EA;}
  .lbl-account{color:#4F5D82;background:#ECEEF6;}
  .lbl-notice{color:#8A6D3B;background:#F3EDDF;}
  /* composition bar */
  .compbar{display:flex;height:34px;border-radius:9px;overflow:hidden;border:1px solid var(--border);}
  .compseg{display:grid;place-items:center;font-size:12px;font-weight:700;color:#fff;min-width:2px;}
  .seg-real{background:var(--accent);}
  .seg-news{background:#C4CBD4;}
  .complegend{display:flex;flex-wrap:wrap;gap:14px 20px;margin-top:12px;font-size:13px;}
  .complegend .k{display:flex;align-items:center;gap:7px;color:var(--ink-soft);}
  .swatch{width:11px;height:11px;border-radius:3px;flex:none;}
  .complegend b{color:var(--ink);font-variant-numeric:tabular-nums;}
  .spamnote{margin-top:11px;font-size:12.5px;color:var(--ink-soft);}
  .ev{display:flex;gap:12px;padding:11px 0;border-top:1px solid var(--border);}
  .ev:first-child{border-top:none;padding-top:0;}
  .ev-time{flex:none;width:140px;font-size:13px;color:var(--ink-soft);font-variant-numeric:tabular-nums;}
  .ev-title{font-size:14.5px;font-weight:500;line-height:1.35;}
  .ev-conflict{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;color:var(--urgent);background:var(--urgent-bg);padding:2px 7px;border-radius:999px;margin-left:4px;}
  .clear-day{color:var(--ink-soft);font-size:14px;}
  .up{display:flex;gap:11px;padding:9px 0;border-top:1px solid var(--border);font-size:13.5px;align-items:baseline;}
  .up:first-child{border-top:none;padding-top:0;}
  .up-day{flex:none;width:82px;color:var(--ink-soft);}
  .up-time{flex:none;width:74px;color:var(--ink-soft);font-variant-numeric:tabular-nums;}
  .up-title{line-height:1.35;}
  /* plan */
  .plan{margin:0;padding-left:0;list-style:none;counter-reset:s;display:flex;flex-direction:column;gap:10px;}
  .plan li{display:flex;gap:11px;font-size:14.5px;line-height:1.45;}
  .plan li::before{counter-increment:s;content:counter(s);flex:none;width:22px;height:22px;border-radius:6px;
                   background:var(--track);color:var(--ink-soft);font-size:12px;font-weight:700;display:grid;place-items:center;}
  /* filterable list */
  #q{width:100%;padding:10px 13px;border:1px solid var(--border);border-radius:10px;background:#fff;color:var(--ink);
     font-size:14px;font-family:inherit;margin-bottom:11px;}
  #q:focus{outline:2px solid var(--accent);outline-offset:1px;}
  .chips{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:13px;}
  .chip{border:1px solid var(--border);background:#fff;color:var(--ink);border-radius:999px;padding:5px 12px;
        font-size:12.5px;cursor:pointer;font-family:inherit;}
  .chip.active{background:var(--ink);color:#fff;border-color:var(--ink);}
  .list{display:flex;flex-direction:column;gap:9px;}
  .item{border:1px solid var(--border);border-radius:12px;padding:12px 14px;}
  .item-top{display:flex;gap:9px;align-items:baseline;}
  .item-subj{font-weight:600;font-size:14.5px;flex:1;line-height:1.35;}
  .item-from{margin:3px 0 0;font-size:12px;color:var(--ink-soft);}
  .item-snip{margin:6px 0 0;font-size:12px;color:var(--ink-soft);line-height:1.5;
             display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
  .empty{text-align:center;color:var(--ink-soft);padding:26px 10px;font-size:14px;}
  .foot{margin-top:22px;text-align:center;color:var(--ink-soft);font-size:12px;line-height:1.5;}
  a.linked{color:inherit;text-decoration:none;cursor:pointer;}
  a.linked:hover{color:var(--accent);text-decoration:underline;}
  a.linked::after{content:" \2197";color:var(--accent);font-size:.8em;font-weight:700;}
</style>"""

# JS is OPTIONAL — the page is fully rendered without it. It only filters the list.
_SCRIPT = r"""<script>
(function(){
  var q=document.getElementById("q"), chips=document.getElementById("chips"), list=document.getElementById("list");
  if(!q||!chips||!list) return;
  var active="All", term="";
  function apply(){
    var items=list.getElementsByClassName("item");
    for(var i=0;i<items.length;i++){
      var it=items[i];
      var okL = active==="All" || it.getAttribute("data-label")===active;
      var okT = !term || (it.getAttribute("data-text")||"").indexOf(term)>=0;
      it.style.display=(okL&&okT)?"":"none";
    }
  }
  chips.addEventListener("click",function(e){
    var b=e.target.closest("button.chip"); if(!b) return;
    active=b.getAttribute("data-label");
    var all=chips.getElementsByClassName("chip");
    for(var i=0;i<all.length;i++) all[i].classList.toggle("active", all[i]===b);
    apply();
  });
  q.addEventListener("input",function(){ term=q.value.toLowerCase(); apply(); });
})();
</script>"""

LABEL_CLASS = {
    "Urgent": "lbl-urgent", "Reply Needed": "lbl-reply", "Payment": "lbl-payment",
    "Deadline": "lbl-deadline", "Waiting": "lbl-waiting", "Shipping": "lbl-shipping",
    "Receipt": "lbl-receipt", "Account": "lbl-account", "Notice": "lbl-notice", "FYI": "lbl-info",
}
LABEL_ORDER = ["Urgent", "Reply Needed", "Payment", "Deadline", "Waiting",
               "Shipping", "Receipt", "Account", "Notice", "FYI"]


def _esc(s):
    return html.escape(str(s if s is not None else ""))


def _pill(label):
    return f'<span class="pill {LABEL_CLASS.get(label, "lbl-info")}">{_esc(label)}</span>'


def _subj(e, cls):
    subject = _esc(e.get("subject") or "(no subject)")
    link = e.get("link")
    if link:
        return (f'<a class="{cls} linked" href="{html.escape(str(link), quote=True)}" '
                f'target="_blank" rel="noopener">{subject}</a>')
    return f'<span class="{cls}">{subject}</span>'


def _summary_section(analysis):
    summ = _esc(analysis.get("summary", ""))
    prios = analysis.get("priorities", []) or []
    lis = "".join(f'<li><span class="rank">{i + 1}</span><span>{_esc(p)}</span></li>'
                  for i, p in enumerate(prios))
    prio_html = f'<ol class="priorities">{lis}</ol>' if lis else ""
    return f'<div class="card"><div class="summary">{summ}</div>{prio_html}</div>'


def _schedule_section(cal):
    today = cal.get("today", []) or []
    if not today:
        inner = '<div class="clear-day">Clear schedule today — no events.</div>'
    else:
        rows = []
        for e in today:
            conflict = '<span class="ev-conflict">overlap</span>' if e.get("conflict") else ""
            rows.append(f'<div class="ev"><div class="ev-time">{_esc(e.get("time"))}</div>'
                        f'<div class="ev-title">{_esc(e.get("title"))}{conflict}</div></div>')
        inner = "".join(rows)
    return f'<div class="card"><h2 class="h2">Today\'s schedule</h2><div>{inner}</div></div>'


def _upcoming_section(cal):
    up = cal.get("upcoming", []) or []
    if not up:
        return ""
    rows = "".join(f'<div class="up"><span class="up-day">{_esc(e.get("day"))}</span>'
                   f'<span class="up-time">{_esc(e.get("time"))}</span>'
                   f'<span class="up-title">{_esc(e.get("title"))}</span></div>' for e in up)
    return f'<div class="card"><h2 class="h2">Coming up · next 7 days</h2><div>{rows}</div></div>'


def _needs_section(items):
    need = [e for e in items if e.get("important")]
    if not need:
        inner = ('<div class="empty-good"><span class="dot">✓</span>'
                 '<span>Nothing needs a reply or action today.</span></div>')
    else:
        rows = []
        for e in need:
            action = f'<div class="need-action">{_esc(e.get("action", ""))}</div>' if e.get("action") else ""
            rows.append(f'<div class="need"><div class="need-top">{_subj(e, "need-subj")}'
                        f'{_pill(e.get("label", "FYI"))}</div>'
                        f'<div class="need-from">{_esc(e.get("from", ""))}</div>{action}</div>')
        inner = "".join(rows)
    return f'<div class="card"><h2 class="h2">Needs you today</h2><div>{inner}</div></div>'


def _composition_section(stats):
    total = max(stats.get("total", 0), 1)
    real, news, spam = stats.get("nonbulk", 0), stats.get("newsletters", 0), stats.get("spam", 0)

    def seg(cls, n):
        w = n / total * 100
        txt = str(n) if w > 8 else ""
        return f'<div class="compseg {cls}" style="width:{w:.1f}%">{txt}</div>'

    bar = seg("seg-real", real) + seg("seg-news", news)
    legend = (f'<span class="k"><span class="swatch" style="background:var(--accent)"></span>'
              f'<span>Real mail <b>{real}</b></span></span>'
              f'<span class="k"><span class="swatch" style="background:#C4CBD4"></span>'
              f'<span>Newsletters <b>{news}</b></span></span>')
    return (f'<div class="card"><h2 class="h2">Today\'s inbox</h2>'
            f'<div class="compbar">{bar}</div><div class="complegend">{legend}</div>'
            f'<p class="spamnote">Plus {spam} spam caught and filtered before your inbox.</p></div>')


def _plan_section(plan):
    plan = plan or []
    if not plan:
        return ""
    cleaned = [_esc(re.sub(r"^Step\s*\d+:\s*", "", str(s))) for s in plan]
    lis = "".join(f"<li>{x}</li>" for x in cleaned)
    return f'<div class="card"><h2 class="h2">Suggested plan</h2><ol class="plan">{lis}</ol></div>'


def _list_section(items):
    labels = [l for l in LABEL_ORDER if any(e.get("label") == l for e in items)]
    counts = {}
    for e in items:
        counts[e.get("label")] = counts.get(e.get("label"), 0) + 1
    chips = [f'<button class="chip active" data-label="All">All ({len(items)})</button>']
    for l in labels:
        chips.append(f'<button class="chip" data-label="{_esc(l)}">{_esc(l)} ({counts.get(l, 0)})</button>')
    rows = []
    for e in items:
        label = e.get("label", "FYI")
        text = _esc(f"{e.get('subject', '')} {e.get('from', '')} {e.get('snippet', '')}".lower())
        snip = f'<p class="item-snip">{_esc(e.get("snippet", ""))}</p>' if e.get("snippet") else ""
        rows.append(f'<div class="item" data-label="{_esc(label)}" data-text="{text}">'
                    f'<div class="item-top">{_subj(e, "item-subj")}{_pill(label)}</div>'
                    f'<p class="item-from">{_esc(e.get("from", ""))}</p>{snip}</div>')
    list_html = "".join(rows) if rows else '<div class="empty">No mail to show.</div>'
    return (f'<div class="card"><h2 class="h2">All your mail <span class="count">({len(items)})</span></h2>'
            f'<input id="q" type="search" placeholder="Search…" autocomplete="off">'
            f'<div class="chips" id="chips">{"".join(chips)}</div>'
            f'<div class="list" id="list">{list_html}</div></div>')


def build_email_dashboard(analysis: dict, generated_at: datetime = None) -> str:
    if generated_at is None:
        generated_at = datetime.now()
    cal = analysis.get("calendar", {"today": [], "upcoming": []})
    items = analysis.get("nonbulk", [])
    items = sorted(items, key=lambda e: (not e.get("important"), e.get("label", "")))
    stats = {
        "total": analysis.get("total", 0), "newsletters": analysis.get("newsletters", 0),
        "spam": analysis.get("spam", 0), "nonbulk": analysis.get("nonbulk_count", len(items)),
        "attention": analysis.get("attention", 0),
    }
    eyebrow = (generated_at.strftime("%A · %B ") + str(generated_at.day)).upper()
    hour12 = generated_at.hour % 12 or 12
    time_str = f"{hour12}:{generated_at.strftime('%M %p')}"
    date_short = generated_at.strftime("%b ") + str(generated_at.day)

    body = (
        '<div class="wrap">'
        f'<div class="topbar"><div class="brand"><span class="mark"></span>Daily Brief</div>'
        f'<div class="updated">Updated {time_str}</div></div>'
        f'<p class="eyebrow">{eyebrow}</p>'
        '<h1>Your morning brief</h1>'
        "<p class=\"sub\">Newsletters and spam are sorted out of the way — here's what's left.</p>"
        + _summary_section(analysis)
        + _schedule_section(cal)
        + _upcoming_section(cal)
        + _needs_section(items)
        + _composition_section(stats)
        + _plan_section(analysis.get("plan", []))
        + _list_section(items)
        + '<p class="foot">Tap a subject to open that email in your Gmail. '
          'Newsletters &amp; promotions and spam are filtered out.<br>'
          'Generated automatically each morning.</p>'
        '</div>'
    )
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Danish's Morning Brief — {date_short}</title>\n"
        + _STYLE + "\n</head>\n<body>\n" + body + "\n" + _SCRIPT + "\n</body>\n</html>\n"
    )


def build_email_inner(analysis: dict, generated_at: datetime = None) -> str:
    """Inner content (style + body + script), no <!doctype>/<head>/<body>, for Artifact preview."""
    full = build_email_dashboard(analysis, generated_at)
    style = full[full.index("<style>"):full.index("</style>") + len("</style>")]
    body_inner = full[full.index("<body>") + len("<body>"):full.index("</body>")]
    return style + "\n" + body_inner


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from email_analysis import analyze
    load_dotenv()
    result = analyze(os.getenv("RECIPIENT_GMAIL_ADDRESS"),
                     os.getenv("RECIPIENT_GMAIL_APP_PASSWORD"),
                     os.getenv("ANTHROPIC_API_KEY"),
                     ical_url=os.getenv("RECIPIENT_ICAL_URL"))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site", "_brief_preview.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(build_email_dashboard(result))
    print(f"wrote {out}")
