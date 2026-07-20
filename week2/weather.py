"""Shared weather data source for the Dad Daily Update project.

Both the messaging agent (daily_message.py) and the dashboard (dashboard.py)
pull from fetch_weather_data() so the text and the visualization always agree.
"""
import requests
from datetime import datetime

LAT = 40.3364
LON = -74.4330
LOCATION = "Monroe Township, NJ"

WEATHER_DESCRIPTIONS = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 51: "light drizzle", 61: "light rain",
    63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
    75: "heavy snow", 80: "rain showers", 95: "thunderstorms"
}
WEATHER_EMOJI = {
    0: "☀️", 1: "\U0001f324️", 2: "⛅", 3: "☁️",
    45: "\U0001f32b️", 48: "\U0001f32b️", 51: "\U0001f326️",
    61: "\U0001f327️", 63: "\U0001f327️", 65: "\U0001f327️",
    71: "\U0001f328️", 73: "\U0001f328️", 75: "❄️",
    80: "\U0001f326️", 95: "⛈️"
}
BAD_WEATHER_CODES = {45, 48, 51, 61, 63, 65, 71, 73, 75, 80, 95}


def fetch_weather_data() -> dict:
    """Fetch and shape today's weather for Monroe Township, NJ into a dict
    that both the agent and the dashboard can consume."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT, "longitude": LON,
        "current": "temperature_2m,weather_code",
        "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m",
        "daily": "sunset",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "America/New_York",
        "forecast_days": 1,
    }
    data = requests.get(url, params=params, timeout=30).json()

    current_code = data["current"]["weather_code"]
    current_temp = round(data["current"]["temperature_2m"])

    hourly = data["hourly"]
    evening_hours = [17, 18, 19, 20]
    evening_temp = round(sum(hourly["temperature_2m"][h] for h in evening_hours) / 4)
    evening_precip = max(hourly["precipitation_probability"][h] for h in evening_hours)
    evening_wind = round(sum(hourly["wind_speed_10m"][h] for h in evening_hours) / 4)
    evening_code = max(hourly["weather_code"][h] for h in evening_hours)

    sunset_dt = datetime.fromisoformat(data["daily"]["sunset"][0])
    hour_12 = sunset_dt.hour % 12 or 12
    sunset_time = f"{hour_12}:{sunset_dt.strftime('%M %p')}"

    outdoor_ok = (
        evening_code not in BAD_WEATHER_CODES
        and evening_precip <= 30
        and 45 <= evening_temp <= 90
        and evening_wind <= 20
    )

    # Hourly series (for the dashboard chart): temp per hour of the day
    hourly_series = [
        {"hour": h, "temp": round(hourly["temperature_2m"][h]),
         "precip": hourly["precipitation_probability"][h]}
        for h in range(len(hourly["temperature_2m"]))
    ]

    return {
        "location": LOCATION,
        "current_temp": current_temp,
        "current_desc": WEATHER_DESCRIPTIONS.get(current_code, "mixed conditions"),
        "current_emoji": WEATHER_EMOJI.get(current_code, "\U0001f321️"),
        "evening_temp": evening_temp,
        "evening_desc": WEATHER_DESCRIPTIONS.get(evening_code, "mixed conditions"),
        "evening_emoji": WEATHER_EMOJI.get(evening_code, "\U0001f321️"),
        "evening_precip": evening_precip,
        "evening_wind": evening_wind,
        "sunset_time": sunset_time,
        "outdoor_ok": outdoor_ok,
        "hourly": hourly_series,
    }


def summary_line(d: dict) -> str:
    """The one-line summary string the messaging agent reasons over."""
    return (
        f"Current: {d['current_temp']}°F, {d['current_desc']}. "
        f"Evening (5-8 PM): {d['evening_temp']}°F, {d['evening_desc']}, "
        f"{d['evening_precip']}% rain chance, {d['evening_wind']} mph wind. "
        f"Sunset at {d['sunset_time']}. "
        f"Outdoor conditions tonight: {'good' if d['outdoor_ok'] else 'poor'}."
    )


if __name__ == "__main__":
    import json
    print(json.dumps(fetch_weather_data(), indent=2))
