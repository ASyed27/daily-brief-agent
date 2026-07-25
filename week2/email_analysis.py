"""Email analysis engine for the Daily Brief project.

Reliable-signal approach (Gmail's date-filtered category search and per-message
category labels proved unreliable over IMAP, so we don't depend on them):

  1. IMAP SINCE            -> today's inbox messages
  2. List-Unsubscribe hdr  -> bulk / newsletters / promotions (vs. non-bulk "real" mail)
  3. [Gmail]/Spam folder   -> spam filtered
  4. Claude                -> action-labels + summary/priorities/plan for the non-bulk mail
  5. Claude                -> sub-categorize the newsletters into types

Accounting (important — these reconcile):
  total (inbox) = newsletters + non-bulk
  spam is a SEPARATE bucket (never enters the inbox)
  "needs attention" is a SUBSET of non-bulk
"""
import email
import imaplib
import json
from collections import Counter
from datetime import datetime
from email.header import decode_header
from urllib.parse import quote

import anthropic

# Action labels for the important (non-bulk) mail — from the daily-dashboard spec
LABELS = ["Urgent", "Reply Needed", "Payment", "Deadline", "Waiting",
          "Shipping", "Receipt", "Account", "Notice", "FYI"]
ATTENTION_LABELS = {"Urgent", "Reply Needed", "Payment", "Deadline"}  # these "need you"

# Newsletter/bulk sub-types for the breakdown chart
NEWSLETTER_TYPES = [
    "Shopping & Retail", "News & Media", "Finance & Offers", "Social",
    "Food & Dining", "Travel", "Entertainment", "Other",
]


def _decode(value):
    if value is None:
        return ""
    out = ""
    for text, enc in decode_header(value):
        out += text.decode(enc or "utf-8", "replace") if isinstance(text, bytes) else text
    return " ".join(out.split())


def _snippet(msg, limit=240):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(part.get_content_charset() or "utf-8", "replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(msg.get_content_charset() or "utf-8", "replace")
    return " ".join(body.split())[:limit]


def gmail_link(message_id):
    """Deep link that opens this exact message in the recipient's Gmail.
    Uses an rfc822msgid: search, so it lands on the specific email — and it only
    works for someone already logged into that Gmail account."""
    if not message_id:
        return ""
    mid = message_id.strip().strip("<>").strip()
    if not mid:
        return ""
    return "https://mail.google.com/mail/u/0/#search/" + quote(f"rfc822msgid:{mid}", safe="")


def _claude_json(api_key, prompt, max_tokens=2000):
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:].strip() if text.lower().startswith("json") else text
    return json.loads(text)


def fetch_today(address, app_password, on_date=None):
    """Split today's inbox into bulk vs non-bulk; collect metadata; count spam."""
    on_date = on_date or datetime.now()
    since = on_date.strftime("%d-%b-%Y")

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(address, app_password)
    imap.select("inbox")

    typ, d = imap.search(None, f'(SINCE "{since}")')
    ids = d[0].split() if d and d[0] else []

    bulk = []      # {from, subject}
    nonbulk = []   # {from, subject, snippet}
    for mid in ids:
        typ, md = imap.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT MESSAGE-ID LIST-UNSUBSCRIBE)])")
        if typ != "OK" or not md or not md[0]:
            continue
        hdr = email.message_from_bytes(md[0][1])
        meta = {"from": _decode(hdr.get("From")), "subject": _decode(hdr.get("Subject"))}
        if hdr.get("List-Unsubscribe") is not None:
            bulk.append(meta)
            continue
        typ2, fd = imap.fetch(mid, "(RFC822)")
        msg = email.message_from_bytes(fd[0][1]) if (typ2 == "OK" and fd and fd[0]) else hdr
        meta["snippet"] = _snippet(msg)
        meta["link"] = gmail_link(hdr.get("Message-ID"))
        nonbulk.append(meta)

    spam = 0
    try:
        imap.select('"[Gmail]/Spam"')
        typ, sd = imap.search(None, f'(SINCE "{since}")')
        spam = len(sd[0].split()) if sd and sd[0] else 0
    except Exception as e:
        print(f"spam check failed: {e}")

    imap.logout()
    return {"total": len(ids), "spam": spam, "bulk": bulk, "nonbulk": nonbulk}


def classify_nonbulk(nonbulk, api_key, calendar_context=""):
    """Label + flag the non-bulk mail and produce summary / priorities / plan."""
    cal_line = f"\n\nToday's calendar context: {calendar_context}" if calendar_context else ""
    if not nonbulk:
        summary = "No personal (non-newsletter) emails today — a quiet inbox."
        if calendar_context:
            summary = f"No personal emails to handle today. {calendar_context}"
        return {"items": [], "summary": summary, "priorities": [], "plan": []}
    listing = "\n".join(
        f"{i}. From: {e['from']}\n   Subject: {e['subject']}\n   Snippet: {e.get('snippet','')}"
        for i, e in enumerate(nonbulk)
    )
    prompt = (
        "You are triaging today's inbox for a busy person named Danish. Below are today's "
        "non-newsletter emails. For EACH email assign ONE label from EXACTLY this list: "
        f"{LABELS} (Urgent=time-sensitive/important; 'Reply Needed'=expects a response; "
        "Payment=a bill/invoice/money to pay; Deadline=has a due date; Waiting=you're awaiting "
        "something; Shipping=an order/delivery/tracking update; Receipt=a receipt, statement or "
        "order confirmation with no action; Account=an account, security or service notification; "
        "Notice=an announcement or community/informational notice; FYI=anything else informational). "
        "Prefer a specific label over FYI when one fits. Give a short action (<=12 words). Then write: a warm 1-2 "
        "sentence summary of what matters today (mention the schedule if relevant); the top 3 "
        "priorities as short phrases; and a short suggested plan (3-4 short steps) that fits around "
        "today's calendar events." + cal_line + "\n\n"
        'Respond ONLY with strict JSON: {"items":[{"index":0,"label":"...","action":"..."}],'
        '"summary":"...","priorities":["..."],"plan":["..."]}\n\n'
        f"Emails:\n{listing}"
    )
    data = _claude_json(api_key, prompt)
    for it in data.get("items", []):
        idx = it.get("index")
        if isinstance(idx, int) and 0 <= idx < len(nonbulk):
            label = it.get("label", "FYI")
            nonbulk[idx].update({
                "label": label,
                "action": it.get("action", ""),
                "important": label in ATTENTION_LABELS,
            })
    return {"items": nonbulk, "summary": data.get("summary", ""),
            "priorities": data.get("priorities", []), "plan": data.get("plan", [])}


def classify_newsletters(bulk, api_key):
    """Sub-categorize the newsletters/promotions into NEWSLETTER_TYPES; return counts."""
    if not bulk:
        return {}
    listing = "\n".join(f"{i}. From: {e['from']} | Subject: {e['subject']}" for i, e in enumerate(bulk))
    prompt = (
        "Below are today's newsletter/promotional emails. Assign EACH one a single type from "
        f"EXACTLY this list: {NEWSLETTER_TYPES}. Respond ONLY with strict JSON: "
        '{"types":[{"index":0,"type":"..."}]}\n\n'
        f"Emails:\n{listing}"
    )
    try:
        data = _claude_json(api_key, prompt)
    except Exception as e:
        print(f"newsletter classification failed: {e}")
        return {"Other": len(bulk)}
    counts = Counter()
    for it in data.get("types", []):
        t = it.get("type", "Other")
        counts[t if t in NEWSLETTER_TYPES else "Other"] += 1
    # anything unclassified -> Other
    classified = sum(counts.values())
    if classified < len(bulk):
        counts["Other"] += len(bulk) - classified
    return dict(counts)


def _calendar_context(cal):
    if not cal:
        return ""
    parts = []
    if cal.get("today"):
        parts.append("Today: " + "; ".join(f"{e['time']} {e['title']}" for e in cal["today"]))
    else:
        parts.append("Today's calendar is clear.")
    if cal.get("upcoming"):
        parts.append("Coming up: " + "; ".join(
            f"{e['day']} {e['time']} {e['title']}" for e in cal["upcoming"][:6]))
    return " ".join(parts)


def analyze(address, app_password, api_key, on_date=None, ical_url=None):
    base = fetch_today(address, app_password, on_date)

    calendar = {"today": [], "upcoming": []}
    if ical_url:
        try:
            import calendar_source
            calendar = calendar_source.fetch_events(ical_url, now=on_date)
        except Exception as e:
            print(f"Calendar fetch failed: {e}")

    nb = classify_nonbulk(base["nonbulk"], api_key, _calendar_context(calendar))

    items = nb["items"]
    return {
        "total": base["total"],
        "spam": base["spam"],
        "newsletters": len(base["bulk"]),
        "newsletter_breakdown": {},
        "nonbulk": items,
        "nonbulk_count": len(items),
        "attention": sum(1 for e in items if e.get("important")),
        "label_counts": dict(Counter(e.get("label", "FYI") for e in items)),
        "summary": nb["summary"],
        "priorities": nb["priorities"],
        "plan": nb["plan"],
        "calendar": calendar,
    }


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    r = analyze(os.getenv("RECIPIENT_GMAIL_ADDRESS"),
                os.getenv("RECIPIENT_GMAIL_APP_PASSWORD"),
                os.getenv("ANTHROPIC_API_KEY"))
    print("ACCOUNTING CHECK:")
    print(f"  total {r['total']} = newsletters {r['newsletters']} + non-bulk {r['nonbulk_count']} "
          f"-> {r['newsletters'] + r['nonbulk_count']} {'OK' if r['newsletters']+r['nonbulk_count']==r['total'] else 'MISMATCH'}")
    print(f"  spam (separate): {r['spam']}   |   needs attention (subset of non-bulk): {r['attention']}")
    print(f"\nNEWSLETTER BREAKDOWN: {r['newsletter_breakdown']}")
    print(f"LABELS: {r['label_counts']}")
    print(f"\nSUMMARY: {r['summary']}")
    print(f"PRIORITIES: {r['priorities']}")
    print(f"PLAN: {r['plan']}")
    print("\nNON-BULK:")
    for e in r["nonbulk"]:
        print(f"  [{e.get('label','?'):12s}] {e['subject'][:52]:52s} — {e.get('action','')}")
