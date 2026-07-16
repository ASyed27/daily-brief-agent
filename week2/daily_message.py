"""Dad's Daily Update agent (week 2) — run by GitHub Actions each morning at 9 AM ET.

An AI agent (Claude via LangChain) that each run:
  - checks the weather forecast for Monroe Township, NJ
  - counts how many emails Dad received today
  - sends Dad TWO messages: a SHORT Telegram note + a FULL warm email

Secrets come from environment variables. In GitHub Actions they're injected from
repository secrets; locally they're loaded from a .env file (git-ignored).
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

LAT = 40.3364
LON = -74.4330

WEATHER_DESCRIPTIONS = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 51: "light drizzle", 61: "light rain",
    63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
    75: "heavy snow", 80: "rain showers", 95: "thunderstorms"
}
BAD_WEATHER_CODES = {45, 48, 51, 61, 63, 65, 71, 73, 75, 80, 95}


@tool
def get_weather_forecast() -> str:
    """Fetches today's current weather and evening (5-8 PM) forecast for
    Monroe Township, NJ, including temperature, conditions, rain chance,
    wind, and sunset time. Returns a summary the agent can reason over."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT, "longitude": LON,
        "current": "temperature_2m,weather_code",
        "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m",
        "daily": "sunset",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "America/New_York",
        "forecast_days": 1
    }
    data = requests.get(url, params=params).json()

    current_temp = round(data["current"]["temperature_2m"])
    current_desc = WEATHER_DESCRIPTIONS.get(data["current"]["weather_code"], "mixed conditions")

    hourly = data["hourly"]
    evening_hours = [17, 18, 19, 20]
    evening_temp = round(sum(hourly["temperature_2m"][h] for h in evening_hours) / 4)
    evening_precip = max(hourly["precipitation_probability"][h] for h in evening_hours)
    evening_wind = round(sum(hourly["wind_speed_10m"][h] for h in evening_hours) / 4)
    evening_code = max(hourly["weather_code"][h] for h in evening_hours)
    evening_desc = WEATHER_DESCRIPTIONS.get(evening_code, "mixed conditions")

    sunset_dt = datetime.fromisoformat(data["daily"]["sunset"][0])
    hour_12 = sunset_dt.hour % 12 or 12
    sunset_time = f"{hour_12}:{sunset_dt.strftime('%M %p')}"

    outdoor_ok = (
        evening_code not in BAD_WEATHER_CODES
        and evening_precip <= 30
        and 45 <= evening_temp <= 90
        and evening_wind <= 20
    )

    return (
        f"Current: {current_temp}°F, {current_desc}. "
        f"Evening (5-8 PM): {evening_temp}°F, {evening_desc}, "
        f"{evening_precip}% rain chance, {evening_wind} mph wind. "
        f"Sunset at {sunset_time}. "
        f"Outdoor conditions tonight: {'good' if outdoor_ok else 'poor'}."
    )


@tool
def count_dads_emails_today() -> str:
    """Counts how many emails arrived in the user's dad's Gmail inbox today.
    Returns the count as a string."""
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(os.getenv("DAD_GMAIL_ADDRESS"), os.getenv("DAD_GMAIL_APP_PASSWORD"))
        imap.select("inbox")
        today_str = datetime.now().strftime("%d-%b-%Y")
        status, message_ids = imap.search(None, f'(SINCE "{today_str}")')
        count = len(message_ids[0].split()) if message_ids[0] else 0
        imap.logout()
        return f"{count} emails received today"
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


def main():
    model = ChatAnthropic(model="claude-sonnet-4-6", api_key=os.getenv("ANTHROPIC_API_KEY"))
    tools = [get_weather_forecast, count_dads_emails_today,
             send_telegram_to_dad, send_email_to_dad]
    agent = create_agent(model, tools)

    instruction = (
        "Check today's weather and how many emails Dad received today. "
        "Then send Dad TWO separate messages:\n\n"
        "1. A SHORT, concise TELEGRAM message (2-4 lines max) using send_telegram_to_dad. "
        "Just the essentials: current conditions, whether tonight is good for a walk or "
        "tennis, and his email count. Punchy and warm, no fluff.\n\n"
        "2. A LONGER, warm EMAIL using send_email_to_dad, in a friendly natural tone with "
        "the full rundown: current conditions, the evening (5-8 PM) outlook, a walk/tennis "
        "recommendation with your reasoning, his email count, and a natural sign-off.\n\n"
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
