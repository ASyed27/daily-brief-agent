"""Dad's Daily Update agent (week 2) — run by GitHub Actions each morning at 9 AM ET.

Each run:
  - fetches the weather for Monroe Township, NJ and counts Danish's emails today
  - generates a visual dashboard (week2/site/index.html) that GitHub Pages publishes
  - sends Danish TWO messages via an AI agent — a SHORT Telegram note + a FULL email,
    both linking to the dashboard

Secrets come from environment variables: GitHub Actions repository secrets in CI,
or a local .env file (git-ignored) when run locally.
"""
import os
import smtplib
import imaplib
import requests
from email.mime.text import MIMEText
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()  # no-op in CI (no .env); loads .env when run locally

from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent

from weather import fetch_weather_data, summary_line
import dashboard

DASHBOARD_URL = "https://asyed27.github.io/Phnx-genai-prep/"
SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")


def fetch_email_count() -> int:
    """Number of emails in Danish's inbox since midnight today, as an int."""
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(os.getenv("DAD_GMAIL_ADDRESS"), os.getenv("DAD_GMAIL_APP_PASSWORD"))
    imap.select("inbox")
    today_str = datetime.now().strftime("%d-%b-%Y")
    status, message_ids = imap.search(None, f'(SINCE "{today_str}")')
    count = len(message_ids[0].split()) if message_ids[0] else 0
    imap.logout()
    return count


@tool
def get_weather_forecast() -> str:
    """Fetches today's current + evening (5-8 PM) weather for Monroe Township, NJ,
    including temperature, conditions, rain chance, wind, and sunset time.
    Returns a one-line summary the agent can reason over."""
    return summary_line(fetch_weather_data())


@tool
def count_dads_emails_today() -> str:
    """Counts how many emails arrived in Danish's Gmail inbox today."""
    try:
        return f"{fetch_email_count()} emails received today"
    except Exception as e:
        return f"Failed to check email: {str(e)}"


@tool
def send_telegram_to_dad(message: str) -> str:
    """Sends a SHORT, concise update to Dad via Telegram. Keep it to a few lines.
    Use this for the quick Telegram version of the daily update."""
    try:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("DAD_TELEGRAM_CHAT_ID")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, data={"chat_id": chat_id, "text": message})
        result = resp.json()
        if result.get("ok"):
            return "Telegram message sent successfully"
        return f"Telegram send failed: {result.get('description', resp.text)}"
    except Exception as e:
        return f"Telegram send failed: {str(e)}"


@tool
def send_email_to_dad(message: str) -> str:
    """Emails the FULL, detailed daily update to Dad's Gmail via Gmail SMTP.
    Use this for the longer, warm email version of the daily update."""
    try:
        sender = os.getenv("GMAIL_ADDRESS")
        recipient = os.getenv("DAD_GMAIL_ADDRESS")
        msg = MIMEText(message)
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = f"Your Daily Update — {datetime.now().strftime('%A, %b %d')}"
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, os.getenv("GMAIL_APP_PASSWORD"))
            server.sendmail(sender, recipient, msg.as_string())
        return f"Email sent successfully to {recipient}"
    except Exception as e:
        return f"Email send failed: {str(e)}"


def build_dashboard():
    """Fetch today's data and write the dashboard HTML that GitHub Pages serves."""
    data = fetch_weather_data()
    try:
        count = fetch_email_count()
    except Exception as e:
        print(f"Email count failed for dashboard: {e}")
        count = "—"
    os.makedirs(SITE_DIR, exist_ok=True)
    out = os.path.join(SITE_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(dashboard.build_page(data, count))
    print(f"Dashboard written to {out}")


def main():
    # 1) Build the dashboard FIRST, so it still publishes even if messaging errors later.
    build_dashboard()

    # 2) Run the agent to send the two messages (each linking to the dashboard).
    model = ChatAnthropic(model="claude-sonnet-4-6", api_key=os.getenv("ANTHROPIC_API_KEY"))
    tools = [get_weather_forecast, count_dads_emails_today,
             send_telegram_to_dad, send_email_to_dad]
    agent = create_agent(model, tools)

    instruction = (
        "Check today's weather and how many emails Dad received today. "
        "Then send Dad TWO separate messages:\n\n"
        "1. A SHORT, concise TELEGRAM message (2-4 lines max) using send_telegram_to_dad. "
        "Just the essentials: current conditions, whether tonight is good for a walk or "
        "tennis, and his email count. Punchy and warm, no fluff. End with a short line "
        f"inviting him to view his full dashboard: {DASHBOARD_URL}\n\n"
        "2. A LONGER, warm EMAIL using send_email_to_dad, in a friendly natural tone with "
        "the full rundown: current conditions, the evening (5-8 PM) outlook, a walk/tennis "
        "recommendation with your reasoning, his email count, and a natural sign-off. "
        f"Include a line with his dashboard link: {DASHBOARD_URL}\n\n"
        "You MUST send BOTH messages. Don't be robotic in either one."
    )

    response = agent.invoke({"messages": [("user", instruction)]})

    # Encoding-safe transcript so CI logs / Windows consoles won't choke on emojis
    print(f"\n=== Dad agent run: {datetime.now().isoformat()} ===")
    for m in response["messages"]:
        content = m.content if hasattr(m, "content") else m
        print("-" * 60)
        print(f"[{type(m).__name__}]")
        print(str(content).encode("utf-8", "replace").decode("utf-8"))


if __name__ == "__main__":
    main()
