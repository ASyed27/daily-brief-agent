"""Danish's Daily Update agent (week 2) — run by GitHub Actions each morning.

Each run:
  - fetches weather for Monroe Township, NJ
  - analyzes today's inbox (categorize / flag important / filter newsletters & spam)
  - publishes the PUBLIC dashboard (weather + aggregate inbox counts) to GitHub Pages
  - builds the PRIVATE interactive inbox breakdown and ATTACHES it to the email
  - sends Danish a SHORT Telegram note + a FULL email, both linking the dashboard

Secrets come from environment variables (GitHub Actions secrets in CI; local .env otherwise).
"""
import os
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from dotenv import load_dotenv
load_dotenv()  # no-op in CI (no .env); loads .env when run locally

from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent

from weather import fetch_weather_data, summary_line
from email_analysis import analyze
from email_dashboard import build_email_dashboard
import dashboard

DASHBOARD_URL = "https://asyed27.github.io/daily-brief-agent/"
SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
ATTACHMENT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inbox-breakdown.html")


@tool
def send_telegram(message: str) -> str:
    """Sends a SHORT, concise update to Danish via Telegram (a few lines)."""
    try:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("RECIPIENT_TELEGRAM_CHAT_ID")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, data={"chat_id": chat_id, "text": message})
        result = resp.json()
        if result.get("ok"):
            return "Telegram message sent successfully"
        return f"Telegram send failed: {result.get('description', resp.text)}"
    except Exception as e:
        return f"Telegram send failed: {str(e)}"


@tool
def send_email(message: str) -> str:
    """Emails the full daily update to Danish, attaching his interactive inbox
    breakdown (inbox-breakdown.html) if it was generated this run."""
    try:
        sender = os.getenv("GMAIL_ADDRESS")
        recipient = os.getenv("RECIPIENT_GMAIL_ADDRESS")
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = f"Your Daily Update — {datetime.now().strftime('%A, %b %d')}"
        msg.attach(MIMEText(message, "plain"))
        if os.path.exists(ATTACHMENT_PATH):
            with open(ATTACHMENT_PATH, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="html")
            part.add_header("Content-Disposition", "attachment", filename="inbox-breakdown.html")
            msg.attach(part)
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, os.getenv("GMAIL_APP_PASSWORD"))
            server.sendmail(sender, recipient, msg.as_string())
        return f"Email sent successfully to {recipient}"
    except Exception as e:
        return f"Email send failed: {str(e)}"


def build_everything():
    """Fetch weather, analyze inbox, write the public page + the private attachment.
    Returns (weather_dict, analysis_dict_or_None)."""
    weather = fetch_weather_data()

    analysis = None
    email_stats = None
    try:
        analysis = analyze(os.getenv("RECIPIENT_GMAIL_ADDRESS"),
                           os.getenv("RECIPIENT_GMAIL_APP_PASSWORD"),
                           os.getenv("ANTHROPIC_API_KEY"),
                           ical_url=os.getenv("RECIPIENT_ICAL_URL"))
        email_stats = {
            "total": analysis["total"], "newsletters": analysis["newsletters"],
            "spam": analysis["spam"], "attention": analysis["attention"],
            "categories": analysis["label_counts"],
        }
        with open(ATTACHMENT_PATH, "w", encoding="utf-8") as f:
            f.write(build_email_dashboard(analysis))
        print(f"Inbox analyzed: {analysis['total']} total, {len(analysis['nonbulk'])} non-bulk, "
              f"{analysis['attention']} need attention. Attachment written.")
    except Exception as e:
        print(f"Email analysis failed (continuing with weather only): {e}")

    os.makedirs(SITE_DIR, exist_ok=True)
    total = email_stats["total"] if email_stats else 0
    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(dashboard.build_page(weather, total, email_stats=email_stats))
    print(f"Public dashboard written to {SITE_DIR}/index.html")
    return weather, analysis


def main():
    weather, analysis = build_everything()

    if analysis:
        email_facts = (
            f"His inbox got {analysis['total']} emails today; you filtered out {analysis['newsletters']} "
            f"newsletters/promotions and {analysis['spam']} spam, leaving {len(analysis['nonbulk'])} that "
            f"matter, of which {analysis['attention']} need attention. What matters: {analysis['summary']}"
        )
        attach_note = "His full interactive inbox breakdown is attached to this email (inbox-breakdown.html)."
    else:
        email_facts = "Email analysis was unavailable today, so just cover the weather."
        attach_note = ""

    model = ChatAnthropic(model="claude-sonnet-4-6", api_key=os.getenv("ANTHROPIC_API_KEY"))
    agent = create_agent(model, [send_telegram, send_email])

    instruction = (
        "You are writing Danish's warm morning update from the data below. Do not invent facts.\n\n"
        f"WEATHER: {summary_line(weather)}\n\n"
        f"EMAIL: {email_facts}\n\n"
        "Send TWO messages:\n"
        "1. send_telegram — a SHORT note (2-4 lines): current conditions, whether tonight is good for a "
        "walk or tennis, and a one-line inbox note (how many need his attention). End with the dashboard "
        f"link: {DASHBOARD_URL}\n\n"
        "2. send_email — a warm, fuller note: the weather rundown, the evening walk/tennis recommendation "
        f"with reasoning, and a short inbox rundown. {attach_note} Include the dashboard link: {DASHBOARD_URL}\n\n"
        "Address him as 'Danish'. You MUST send BOTH messages. Don't be robotic."
    )

    response = agent.invoke({"messages": [("user", instruction)]})

    print(f"\n=== Daily brief run: {datetime.now().isoformat()} ===")
    for m in response["messages"]:
        content = m.content if hasattr(m, "content") else m
        print("-" * 60)
        print(f"[{type(m).__name__}]")
        print(str(content).encode("utf-8", "replace").decode("utf-8"))


if __name__ == "__main__":
    main()
