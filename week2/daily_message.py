import os
import random
import requests
from twilio.rest import Client
from datetime import datetime

LAT = 40.3364
LON = -74.4330

WEATHER_DESCRIPTIONS = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 51: "light drizzle", 61: "light rain",
    63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
    75: "heavy snow", 80: "rain showers", 95: "thunderstorms"
}

BAD_WEATHER_CODES = {45, 48, 51, 61, 63, 65, 71, 73, 75, 80, 95}

def get_forecast():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "current": "temperature_2m,weather_code",
        "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m",
        "daily": "sunset",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "America/New_York",
        "forecast_days": 1
    }
    resp = requests.get(url, params=params)
    data = resp.json()

    current_temp = round(data["current"]["temperature_2m"])
    current_code = data["current"]["weather_code"]

    hourly = data["hourly"]
    evening_hours = [17, 18, 19, 20]  # 5 PM - 8 PM

    evening_temps = [hourly["temperature_2m"][h] for h in evening_hours]
    evening_precip = [hourly["precipitation_probability"][h] for h in evening_hours]
    evening_codes = [hourly["weather_code"][h] for h in evening_hours]
    evening_winds = [hourly["wind_speed_10m"][h] for h in evening_hours]

    sunset_raw = data["daily"]["sunset"][0]
    sunset_dt = datetime.fromisoformat(sunset_raw)
    hour_12 = sunset_dt.hour % 12 or 12
    sunset_time = f"{hour_12}:{sunset_dt.strftime('%M %p')}"

    return {
        "current_temp": current_temp,
        "current_code": current_code,
        "evening_temp": round(sum(evening_temps) / len(evening_temps)),
        "evening_precip": max(evening_precip),
        "evening_wind": round(sum(evening_winds) / len(evening_winds)),
        "evening_code": max(evening_codes),
        "sunset": sunset_time
    }

def is_good_for_outdoors(temp, precip_chance, wind, code):
    if code in BAD_WEATHER_CODES:
        return False
    if precip_chance > 30:
        return False
    if temp < 45 or temp > 90:
        return False
    if wind > 20:
        return False
    return True

def pick_activity(temp, wind, code):
    if wind > 12:
        return "a walk"
    if code in (0, 1) and 55 <= temp <= 85:
        return "tennis"
    return "a walk or some tennis"

GOOD_WEATHER_LINES = [
    "Good evening for {activity}!",
    "Great conditions tonight — worth getting out for {activity}.",
    "Evening's looking solid for {activity}.",
    "Nice window tonight for {activity}.",
    "Conditions look good tonight — {activity} would be a good call."
]

BAD_WEATHER_LINES = [
    "Might be better to stay in this evening.",
    "Evening looks rough — probably a stay-indoors night.",
    "Not the best night to be outside, might want to skip it.",
    "Conditions aren't great tonight — indoor plans might be smarter.",
    "Evening weather isn't cooperating, might want to sit this one out."
]

def build_message():
    f = get_forecast()
    day_description = WEATHER_DESCRIPTIONS.get(f["current_code"], "mixed conditions")
    evening_description = WEATHER_DESCRIPTIONS.get(f["evening_code"], "mixed conditions")

    good_to_go = is_good_for_outdoors(
        f["evening_temp"], f["evening_precip"], f["evening_wind"], f["evening_code"]
    )

    if good_to_go:
        activity = pick_activity(f["evening_temp"], f["evening_wind"], f["evening_code"])
        recommendation = random.choice(GOOD_WEATHER_LINES).format(activity=activity)
    else:
        recommendation = random.choice(BAD_WEATHER_LINES)

    return (
        f"Good morning Danish! Your daily weather report: {f['current_temp']}°F, {day_description}. "
        f"Evening (5-8 PM): {f['evening_temp']}°F, {evening_description}, "
        f"{f['evening_precip']}% chance of rain. Sunset at {f['sunset']}. "
        f"{recommendation}"
    )

client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

message = client.messages.create(
    body=build_message(),
    from_=os.getenv("TWILIO_PHONE_NUMBER"),
    to=os.getenv("DAD_PHONE_NUMBER")
)

print(message.sid, message.status)
