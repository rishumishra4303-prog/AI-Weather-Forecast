"""
Blizzard Buddy — Weather Intelligence Dashboard
Run with: streamlit run streamlit_app.py

Secrets:
- Preferred: .streamlit/secrets.toml or environment variables
- Optional legacy support: config.toml

This app's core weather dashboard works without an OpenAI API key.
OpenAI-powered features gracefully fall back to deterministic local responses.
"""

import os
import random
from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont

try:
    import toml
except ImportError:
    toml = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import speech_recognition as sr
except Exception:
    sr = None


# ----------------------------- PAGE CONFIG -----------------------------
st.set_page_config(
    page_title="Blizzard Buddy | Weather Intelligence",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ----------------------------- CONFIGURATION -----------------------------
def load_legacy_config():
    """Load config.toml if it exists; missing config should not crash the app."""
    if toml is None or not os.path.exists("config.toml"):
        return {}
    try:
        return toml.load("config.toml")
    except Exception:
        return {}


CONFIG = load_legacy_config()


def read_setting(section, key, env_name, default=""):
    """Read a value from Streamlit secrets, environment, or config.toml."""
    value = os.getenv(env_name, "")
    if value:
        return value.strip()

    try:
        value = st.secrets.get(section, {}).get(key, "")
        if value:
            return str(value).strip()
    except Exception:
        pass

    value = CONFIG.get(section, {}).get(key, default)
    return str(value).strip() if value is not None else default


OPENWEATHER_API_KEY = read_setting(
    "openweather", "api_key", "OPENWEATHER_API_KEY"
)
OPENAI_API_KEY = read_setting("openai", "api_key", "OPENAI_API_KEY")
OPENAI_MODEL = read_setting("openai", "model", "OPENAI_MODEL", "gpt-4o-mini")
NASA_API_KEY = read_setting("nasa", "api_key", "NASA_API_KEY", "DEMO_KEY")
UNSPLASH_ACCESS_KEY = read_setting("unsplash", "access_key", "UNSPLASH_ACCESS_KEY")

OPENAI_CLIENT = None
if OpenAI is not None and OPENAI_API_KEY:
    try:
        OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY, timeout=15.0, max_retries=1)
    except Exception:
        OPENAI_CLIENT = None


# ----------------------------- VISUAL DESIGN -----------------------------
THEMES = {
    "Midnight Cyan": {
        # Quiet, premium dark mode: charcoal-navy with restrained cyan accents
        "background": "#080D18",
        "panel": "#121B2B",
        "text": "#F1F5F9",
        "muted": "#A4B1C2",
        "accent": "#7DD3FC",
        "border": "rgba(125, 211, 252, 0.22)",
    },
    "Pastel Dream": {
        "background": "#FFF4FA",
        "panel": "#FFE1EF",
        "text": "#39233F",
        "muted": "#80677F",
        "accent": "#E64FA3",
        "border": "rgba(230, 79, 163, 0.28)",
    },
    "Forest Green": {
        # Pale mint surfaces keep the dashboard readable; green is used as an accent.
        "background": "#F2FAF5",
        "panel": "#E1F2E7",
        "text": "#183B2A",
        "muted": "#557463",
        "accent": "#218653",
        "border": "rgba(33, 134, 83, 0.24)",
    },
    "Sunset Glow": {
        "background": "#FFF7F1",
        "panel": "#FFE8DA",
        "text": "#4B2A28",
        "muted": "#88645B",
        "accent": "#E76536",
        "border": "rgba(231, 101, 54, 0.24)",
    },
    "Royal Purple": {
        "background": "#F8F4FF",
        "panel": "#EDE3FF",
        "text": "#34234F",
        "muted": "#76638E",
        "accent": "#7C3FC6",
        "border": "rgba(124, 63, 198, 0.24)",
    },
    "Ice Blue Light": {
        "background": "#F2FBFF",
        "panel": "#DFF4FF",
        "text": "#123650",
        "muted": "#52758C",
        "accent": "#087EA4",
        "border": "rgba(8, 126, 164, 0.23)",
    },
}

with st.sidebar:
    st.markdown("## 🌦️ Blizzard Buddy")
    theme_name = st.radio("Dashboard theme", list(THEMES.keys()), index=0)
    st.divider()
    st.markdown("### ⚙️ Preferences")
    use_voice_input = st.checkbox("🎙️ Speak city name", value=False)
    enable_ambient_audio = st.checkbox("🎵 Show ambient audio", value=False)
    st.caption("Voice input needs a microphone and speech-recognition dependencies.")

THEME = THEMES[theme_name]
st.markdown(
    f"""
    <style>
    :root {{ color-scheme: {'light' if theme_name == 'Light' else 'dark'}; }}
    .stApp {{
        background:
          radial-gradient(circle at 15% 0%, {THEME['panel']} 0%, transparent 38%),
          {THEME['background']};
        color: {THEME['text']};
    }}
    [data-testid="stHeader"] {{ background: transparent; }}
    [data-testid="stSidebar"] {{
        background: {THEME['panel']};
        border-right: 1px solid {THEME['border']};
    }}
    .hero {{
        padding: 1.35rem 1.5rem;
        border: 1px solid {THEME['border']};
        border-radius: 22px;
        background: linear-gradient(125deg, {THEME['panel']}, {THEME['background']});
        margin-bottom: 1.2rem;
    }}
    .hero-kicker {{
        color: {THEME['accent']};
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .16em;
        text-transform: uppercase;
    }}
    .hero-title {{
        color: {THEME['text']};
        font-size: clamp(2rem, 4vw, 3.2rem);
        line-height: 1.1;
        font-weight: 800;
        margin: .35rem 0;
    }}
    .hero-subtitle {{ color: {THEME['muted']}; margin: 0; }}
    .metric-card {{
        padding: 1rem;
        border-radius: 16px;
        border: 1px solid {THEME['border']};
        background: {THEME['panel']};
        min-height: 112px;
    }}
    .metric-label {{
        color: {THEME['muted']};
        font-size: .82rem;
        margin-bottom: .35rem;
    }}
    .metric-value {{
        color: {THEME['text']};
        font-size: 1.65rem;
        font-weight: 750;
    }}
    .holo-card {{
        background: linear-gradient(145deg, {THEME['panel']}, {THEME['background']});
        border: 1px solid {THEME['border']};
        border-radius: 18px;
        padding: 1rem .6rem;
        min-height: 205px;
        text-align: center;
        transition: transform .2s ease, box-shadow .2s ease;
    }}
    .holo-card:hover {{ transform: translateY(-4px); box-shadow: 0 8px 26px {THEME['border']}; }}
    .holo-day {{ color: {THEME['accent']}; font-weight: 750; }}
    .holo-icon {{ font-size: 2rem; margin: .6rem 0; }}
    .holo-condition {{ color: {THEME['muted']}; text-transform: capitalize; }}
    .holo-temp {{ color: {THEME['text']}; margin-top: .8rem; line-height: 1.8; }}
    .section-note {{ color: {THEME['muted']}; font-size: .9rem; }}
    div[data-testid="stAlert"] {{ border-radius: 12px; }}
    footer {{ visibility: hidden; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------- WEATHER API -----------------------------
WEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"


@st.cache_data(ttl=600, show_spinner=False)
def get_weather(city: str, api_key: str):
    """Fetch current weather; return a predictable error object on failure."""
    if not api_key:
        return {"error": "missing_key"}
    try:
        response = requests.get(
            f"{WEATHER_BASE_URL}/weather",
            params={"q": city, "appid": api_key, "units": "metric"},
            timeout=12,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.status_code != 200:
            return {
                "error": payload.get("message", f"Weather service returned HTTP {response.status_code}")
            }
        return payload
    except requests.RequestException as exc:
        return {"error": f"Network request failed: {exc}"}


@st.cache_data(ttl=600, show_spinner=False)
def get_forecast(city: str, api_key: str):
    """Fetch five-day / three-hour forecast."""
    if not api_key:
        return {"error": "missing_key", "list": []}
    try:
        response = requests.get(
            f"{WEATHER_BASE_URL}/forecast",
            params={"q": city, "appid": api_key, "units": "metric"},
            timeout=12,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.status_code != 200:
            return {
                "error": payload.get("message", f"Forecast service returned HTTP {response.status_code}"),
                "list": [],
            }
        return payload
    except requests.RequestException as exc:
        return {"error": str(exc), "list": []}


WEATHER_EMOJI = {
    "Clear": "☀️",
    "Clouds": "☁️",
    "Rain": "🌧️",
    "Drizzle": "🌦️",
    "Thunderstorm": "⛈️",
    "Snow": "❄️",
    "Mist": "🌫️",
    "Fog": "🌫️",
    "Haze": "🌫️",
    "Smoke": "🌫️",
    "Dust": "🌪️",
    "Sand": "🌪️",
    "Squall": "💨",
    "Tornado": "🌪️",
}


def determine_mood(condition, temperature):
    try:
        temp_value = float(temperature)
    except (TypeError, ValueError):
        temp_value = 20.0
    if temp_value >= 33:
        return "warm and energetic"
    if temp_value <= 8:
        return "calm and cozy"
    return {
        "Clear": "bright and cheerful",
        "Clouds": "relaxed",
        "Rain": "cozy",
        "Drizzle": "cozy",
        "Thunderstorm": "cautious",
        "Snow": "calm",
        "Mist": "quiet",
        "Fog": "quiet",
    }.get(condition, "balanced")


def local_time_from_timestamp(timestamp, timezone_offset=0):
    """Convert a UTC timestamp using the city's timezone offset."""
    return datetime.utcfromtimestamp(timestamp + timezone_offset)


def fallback_weather_summary(city, current, forecast):
    current_weather = current.get("weather", [{}])[0]
    main = current.get("main", {})
    condition = current_weather.get("main", "Unknown").lower()
    description = current_weather.get("description", condition)
    temp = main.get("temp", "N/A")
    feels = main.get("feels_like")
    humidity = main.get("humidity")
    next_items = forecast.get("list", [])[:4]
    forecast_line = ""
    if next_items:
        next_conditions = [item.get("weather", [{}])[0].get("description", "changing conditions") for item in next_items]
        forecast_line = " Near-term outlook: " + ", ".join(next_conditions[:3]) + "."
    advice = {
        "rain": "Take an umbrella and allow extra time outdoors.",
        "drizzle": "A light waterproof layer may be useful.",
        "thunderstorm": "Stay indoors during thunder and lightning.",
        "clear": "Good visibility is likely; consider sun protection.",
        "clouds": "Keep a light layer handy if you will be out for long.",
        "snow": "Wear warm layers and watch for slippery surfaces.",
        "mist": "Use extra care while travelling because visibility may be reduced.",
        "fog": "Use extra care while travelling because visibility may be reduced.",
    }.get(condition, "Dress for the conditions and keep hydrated.")
    feels_line = f" It feels like {feels:.1f}°C." if isinstance(feels, (int, float)) else ""
    humidity_line = f" Humidity is {humidity}%." if isinstance(humidity, (int, float)) else ""
    return f"{city}: {description.capitalize()} with a temperature of {temp}°C.{feels_line}{humidity_line}{forecast_line} {advice}"


def local_day_planner(current):
    weather_main = current.get("weather", [{}])[0].get("main", "Clear")
    temp = current.get("main", {}).get("temp", 20)
    try:
        temp = float(temp)
    except (ValueError, TypeError):
        temp = 20
    if weather_main in ("Thunderstorm", "Rain", "Drizzle"):
        return "Plan an indoor activity, keep waterproof clothing nearby, and check local conditions before travelling."
    if temp >= 33:
        return "Choose shaded or indoor activities during the hottest part of the day and drink water regularly."
    if temp <= 8:
        return "Consider a warm indoor plan or dress in layers if you head outside."
    if weather_main == "Clear":
        return "A walk or outdoor break could be enjoyable; use sun protection if you will be outside for long."
    return "A flexible plan works best today. Check the forecast again before a longer outdoor activity."


def ai_chat(system_prompt, user_prompt, fallback_text):
    """Use OpenAI when configured; never let an AI outage break the dashboard."""
    if OPENAI_CLIENT is None:
        return fallback_text
    try:
        response = OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=220,
        )
        answer = response.choices[0].message.content
        if answer and answer.strip():
            return answer.strip()
        return fallback_text
    except Exception:
        return fallback_text


def get_city_by_voice():
    if sr is None:
        st.sidebar.warning("Voice input is unavailable. Install SpeechRecognition and microphone dependencies.")
        return None
    try:
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            st.sidebar.info("Listening for a city name…")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)
        return recognizer.recognize_google(audio)
    except Exception as exc:
        st.sidebar.warning(f"Voice input could not be used: {exc}")
        return None


# ----------------------------- HEADER / CITY SEARCH -----------------------------
st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">Weather intelligence · Live conditions · Forecast insights</div>
      <div class="hero-title">🌦️ Blizzard Buddy</div>
      <p class="hero-subtitle">A weather dashboard designed to turn current conditions into practical decisions.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not OPENWEATHER_API_KEY:
    st.error(
        "OpenWeather API key is missing. Add OPENWEATHER_API_KEY to your environment, "
        "or set openweather.api_key in config.toml / Streamlit secrets."
    )
    st.code(
        '[openweather]\napi_key = "YOUR_OPENWEATHER_API_KEY"\n\n'
        '[openai]\napi_key = ""\nmodel = "gpt-4o-mini"',
        language="toml",
    )
    st.stop()

default_city = "Noida"
if use_voice_input:
    voice_city = get_city_by_voice()
else:
    voice_city = None

city_col, button_col = st.columns([4, 1])
with city_col:
    city = st.text_input("Search city", value=voice_city or default_city, placeholder="e.g. Noida, India")
with button_col:
    st.markdown("<div style='height: 1.8rem'></div>", unsafe_allow_html=True)
    refresh = st.button("↻ Refresh", use_container_width=True)

city = city.strip()
if not city:
    st.info("Enter a city to see the weather dashboard.")
    st.stop()

if refresh:
    get_weather.clear()
    get_forecast.clear()

with st.spinner(f"Loading weather for {city}…"):
    data = get_weather(city, OPENWEATHER_API_KEY)

if not data or data.get("error"):
    error = data.get("error", "No response from weather service") if data else "No response from weather service"
    if error == "missing_key":
        st.error("OpenWeather API key is missing.")
    elif "city not found" in str(error).lower():
        st.error(f"City '{city}' was not found. Try a city name plus country, such as 'Noida, IN'.")
    else:
        st.error(f"Could not load current weather: {error}")
    st.stop()

if not data.get("main") or not data.get("weather"):
    st.error("The weather service returned incomplete data. Please try again.")
    st.stop()

forecast = get_forecast(city, OPENWEATHER_API_KEY)
if forecast.get("error"):
    st.warning("The forecast could not be loaded. Current weather is still available.")
    forecast = {"list": []}

weather = data.get("weather", [{}])[0]
condition = weather.get("main", "Clear")
description = weather.get("description", condition).capitalize()
main_data = data.get("main", {})
temp = float(main_data.get("temp", 0))
feels_like = float(main_data.get("feels_like", temp))
humidity = main_data.get("humidity", "—")
wind_speed = data.get("wind", {}).get("speed", "—")
pressure = main_data.get("pressure", "—")
visibility_km = data.get("visibility")
visibility_km = f"{visibility_km / 1000:.1f} km" if isinstance(visibility_km, (int, float)) else "—"
icon = WEATHER_EMOJI.get(condition, "🌤️")
city_name = data.get("name", city)
country = data.get("sys", {}).get("country", "")
location_label = f"{city_name}, {country}" if country else city_name
timezone_offset = data.get("timezone", 0)
observed_at = local_time_from_timestamp(data.get("dt", datetime.utcnow().timestamp()), timezone_offset)

# ----------------------------- CURRENT CONDITIONS -----------------------------
st.markdown(f"## {icon} Current conditions — {location_label}")
st.caption(f"Observation time (city local time): {observed_at.strftime('%d %b %Y, %I:%M %p')}")

metric_specs = [
    ("Temperature", f"{temp:.1f}°C", description),
    ("Feels like", f"{feels_like:.1f}°C", "Perceived temperature"),
    ("Humidity", f"{humidity}%", "Relative humidity"),
    ("Wind speed", f"{wind_speed} m/s", "Reported surface wind"),
    ("Pressure", f"{pressure} hPa", "Sea-level / station reading"),
    ("Visibility", visibility_km, "Reported visibility"),
]
metric_cols = st.columns(3)
for index, (label, value, note) in enumerate(metric_specs):
    with metric_cols[index % 3]:
        st.markdown(
            f"""
            <div class="metric-card">
              <div class="metric-label">{label}</div>
              <div class="metric-value">{value}</div>
              <div class="section-note">{note}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.write("")
left, right = st.columns([1.2, 1])
with left:
    st.markdown("### 🧭 Weather briefing")
    fallback_summary = fallback_weather_summary(city_name, data, forecast)
    summary = ai_chat(
        "You are a concise weather briefing assistant. Use only the supplied weather facts; do not invent alerts or measurements.",
        f"Rewrite this weather briefing in a friendly professional tone, in 2-3 short sentences: {fallback_summary}",
        fallback_summary,
    )
    st.info(summary)
with right:
    st.markdown("### 🌿 Practical day planner")
    planner_fallback = local_day_planner(data)
    planner = ai_chat(
        "You provide practical, concise activities based only on weather conditions. Do not make medical claims.",
        f"Weather: {description}, {temp:.1f} C. Improve this practical advice in one or two sentences: {planner_fallback}",
        planner_fallback,
    )
    st.success(planner)

if condition in ("Thunderstorm", "Tornado", "Squall"):
    st.warning("Severe-weather condition reported by the weather provider. Check official local alerts and follow local authorities.")
elif condition in ("Rain", "Drizzle", "Snow"):
    st.info("Precipitation is reported. Check the latest local forecast before travel.")

# ----------------------------- HEALTH / COMFORT TIP -----------------------------
st.markdown("### 💚 Weather comfort tip")
if condition in ("Thunderstorm", "Rain", "Drizzle"):
    comfort_tip = "Carry rain protection. During thunder or lightning, move indoors and avoid exposed areas."
elif temp >= 35:
    comfort_tip = "High temperature: drink water, seek shade, and limit strenuous activity during peak heat."
elif temp >= 30:
    comfort_tip = "Warm conditions: keep water handy and take breaks in shade during outdoor activity."
elif temp <= 8:
    comfort_tip = "Cold conditions: wear warm layers and protect exposed skin if staying outdoors."
elif isinstance(humidity, (int, float)) and humidity >= 80:
    comfort_tip = "Humidity is high. Take breaks if you feel overheated and keep hydrated."
elif isinstance(wind_speed, (int, float)) and wind_speed >= 10:
    comfort_tip = "Wind is strong. Be cautious around trees, construction areas, and loose outdoor objects."
else:
    comfort_tip = "Dress comfortably for the conditions, stay hydrated, and check the forecast before longer trips."
st.info(comfort_tip)

# ----------------------------- FIVE-DAY FORECAST -----------------------------
st.markdown("## 📅 Five-day forecast")
forecast_items = forecast.get("list", [])
daily_data = {}

for item in forecast_items:
    try:
        local_dt = local_time_from_timestamp(item["dt"], timezone_offset)
        day_key = local_dt.strftime("%Y-%m-%d")
        day_weather = item.get("weather", [{}])[0]
        day_record = daily_data.setdefault(
            day_key,
            {"date": local_dt, "temps": [], "conditions": [], "icons": [], "precip": []},
        )
        day_record["temps"].append(float(item["main"]["temp"]))
        day_record["conditions"].append(day_weather.get("main", "Unknown"))
        day_record["icons"].append(day_weather.get("icon", ""))
        day_record["precip"].append(float(item.get("pop", 0) or 0))
    except (KeyError, TypeError, ValueError):
        continue

if not daily_data:
    st.warning("Forecast data is unavailable right now.")
else:
    days = list(daily_data.values())[:5]
    forecast_cols = st.columns(len(days))
    for col, day in zip(forecast_cols, days):
        with col:
            counts = pd.Series(day["conditions"]).value_counts()
            day_condition = counts.index[0] if not counts.empty else "Unknown"
            day_emoji = WEATHER_EMOJI.get(day_condition, "🌤️")
            rain_chance = round(max(day["precip"]) * 100) if day["precip"] else 0
            st.markdown(
                f"""
                <div class="holo-card">
                  <div class="holo-day">{day['date'].strftime('%a, %d %b')}</div>
                  <div class="holo-icon">{day_emoji}</div>
                  <div class="holo-condition">{day_condition}</div>
                  <div class="holo-temp">
                    <div>Low <b>{min(day['temps']):.1f}°C</b></div>
                    <div>High <b>{max(day['temps']):.1f}°C</b></div>
                    <div>Precipitation chance <b>{rain_chance}%</b></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    chart_rows = []
    for day_key, day in daily_data.items():
        chart_rows.append(
            {
                "Date": day["date"].strftime("%a %d %b"),
                "Low (°C)": min(day["temps"]),
                "High (°C)": max(day["temps"]),
            }
        )
    st.markdown("### Temperature trend")
    chart_df = pd.DataFrame(chart_rows).set_index("Date")
    st.line_chart(chart_df)

# ----------------------------- ASK SKYLER -----------------------------
st.markdown("## 💬 Ask Skyler")
st.caption("Ask about the weather shown above. If the AI API is unavailable, the dashboard still works.")
question = st.text_input("Your question", placeholder="Should I carry an umbrella today?")
if st.button("Get answer", type="primary") and question.strip():
    fallback_answer = (
        f"For {city_name}, current conditions are {description} at {temp:.1f}°C. "
        f"{comfort_tip} I can only answer reliably from the current conditions and forecast displayed here."
    )
    answer = ai_chat(
        "You are a weather assistant. Answer briefly using only the weather information supplied. If it is not enough to answer, say so.",
        f"Location: {location_label}. Current: {description}, {temp:.1f} C. "
        f"Humidity: {humidity}%. Wind: {wind_speed} m/s. Question: {question}",
        fallback_answer,
    )
    st.info(answer)

# ----------------------------- FUN WEATHER FACT -----------------------------
st.markdown("## 💡 Weather fact")
facts = [
    "Clouds are made of tiny water droplets, ice crystals, or a mixture of both.",
    "The temperature in a standard weather report is measured in the shade, not in direct sunlight.",
    "A rainbow is formed when sunlight is refracted, reflected, and dispersed in water droplets.",
    "Wind is air moving from areas of higher pressure toward areas of lower pressure.",
    "Fog is a cloud that forms at ground level and can reduce visibility.",
    "Snowflakes form when ice crystals grow in cold clouds; their shapes depend on temperature and humidity.",
]
if "weather_fact" not in st.session_state:
    st.session_state.weather_fact = random.choice(facts)
fact_col1, fact_col2 = st.columns([4, 1])
with fact_col1:
    st.info(st.session_state.weather_fact)
with fact_col2:
    if st.button("New fact"):
        st.session_state.weather_fact = random.choice(facts)
        st.rerun()

# ----------------------------- CITY COMPARISON -----------------------------
st.markdown("## 🌍 Compare another city")
comparison_city = st.text_input("Second city", placeholder="e.g. Mumbai")
if comparison_city.strip():
    if comparison_city.strip().lower() == city.strip().lower():
        st.caption("Enter a different city to compare.")
    else:
        comparison = get_weather(comparison_city.strip(), OPENWEATHER_API_KEY)
        if comparison.get("error") or not comparison.get("main"):
            st.warning(f"Could not load weather for {comparison_city}: {comparison.get('error', 'incomplete response')}")
        else:
            comparison_weather = comparison.get("weather", [{}])[0]
            compare_cols = st.columns(2)
            compare_items = [
                (location_label, data, weather),
                (
                    f"{comparison.get('name', comparison_city)}"
                    + (f", {comparison.get('sys', {}).get('country')}" if comparison.get('sys', {}).get('country') else ""),
                    comparison,
                    comparison_weather,
                ),
            ]
            for col, (label, record, weather_record) in zip(compare_cols, compare_items):
                with col:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                          <div class="metric-label">{label}</div>
                          <div class="metric-value">{WEATHER_EMOJI.get(weather_record.get('main', ''), '🌤️')} {record['main'].get('temp', 0):.1f}°C</div>
                          <div class="section-note">{weather_record.get('description', 'Conditions unavailable').capitalize()}</div>
                          <div class="section-note">Feels like {record['main'].get('feels_like', '—')}°C · Humidity {record['main'].get('humidity', '—')}%</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

# ----------------------------- SKY VIEW -----------------------------

st.markdown(
    f"""
    <div style="
        padding: 22px 24px;
        border-radius: 18px;
        border: 1px solid {THEME['border']};
        background: {THEME['panel']};
        margin-bottom: 18px;
    ">
        <div style="
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 1.8px;
            color: {THEME['muted']};
            text-transform: uppercase;
        ">
            WEATHER INTELLIGENCE
        </div>
        <div style="
            font-size: 28px;
            font-weight: 750;
            color: {THEME['text']};
            margin-top: 6px;
        ">
            🌦️ Live Weather Explorer
        </div>
        <div style="
            font-size: 14px;
            color: {THEME['muted']};
            margin-top: 8px;
        ">
            Explore atmospheric conditions around {city_name}.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    geo_response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": city_name,
            "format": "jsonv2",
            "limit": 1,
        },
        headers={
            "User-Agent": "BlizzardBuddyWeatherDashboard/1.0"
        },
        timeout=10,
    )
    geo_response.raise_for_status()
    locations = geo_response.json()

    if locations:
        latitude = float(locations[0]["lat"])
        longitude = float(locations[0]["lon"])

        st.markdown("### Map display settings")

        map_layer = st.selectbox(
            "Weather layer",
            options=["rain", "wind", "temp", "clouds"],
            format_func=lambda layer: {
                "rain": "🌧️ Rain & precipitation",
                "wind": "💨 Wind speed",
                "temp": "🌡️ Temperature",
                "clouds": "☁️ Cloud cover",
            }[layer],
            key="sky_weather_layer",
            help="Choose which weather conditions to display on the map.",
        )

        st.markdown(
            f"""
            <div style="
                padding: 12px 16px;
                border: 1px solid {THEME['border']};
                border-radius: 14px;
                background: {THEME['panel']};
                margin-bottom: 12px;
            ">
                <div style="
                    font-weight: 700;
                    color: {THEME['text']};
                ">
                    📍 {city_name}
                </div>
                <div style="
                    font-size: 12px;
                    color: {THEME['muted']};
                ">
                    Interactive weather map · Windy
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        map_url = (
            "https://embed.windy.com/embed.html"
            f"?type=map&location=coordinates"
            f"&lat={latitude}&lon={longitude}"
            f"&zoom=7&overlay={map_layer}"
            "&level=surface&product=ecmwf"
            "&metricTemp=default&metricWind=default"
            "&metricRain=default"
        )

        components.html(
            f"""
            <iframe
                src="{map_url}"
                title="Interactive weather map"
                width="100%"
                height="480"
                style="
                    border: 0;
                    border-radius: 16px;
                    overflow: hidden;
                "
                loading="lazy"
                allowfullscreen>
            </iframe>
            """,
            height=490,
            scrolling=False,
        )

        st.caption(
            "Map imagery and forecasts are provided externally. "
            "Availability and displayed conditions depend on Windy."
        )

    else:
        st.warning(
            "We couldn't locate this city. "
            "Check the city name and try again."
        )

except (
    requests.RequestException,
    ValueError,
    KeyError,
    TypeError,
):
    st.warning(
        "The weather map couldn't load right now. "
        "Check your internet connection and refresh the dashboard."
    )


# ----------------------------- GLOBAL WIND MAP -----------------------------

# Premium section header — adapts to the selected app theme
st.markdown(
    f"""
    <div style="
        padding: 26px;
        border-radius: 20px;
        border: 1px solid {THEME['border']};
        background: {THEME['panel']};
        margin: 10px 0 18px 0;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.07);
    ">
        <div style="
            display: flex;
            align-items: center;
            gap: 9px;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 2px;
            color: {THEME['muted']};
            text-transform: uppercase;
        ">
            <span>ATMOSPHERIC INTELLIGENCE</span>
        </div>
        <div style="
            font-size: clamp(25px, 3vw, 34px);
            font-weight: 800;
            letter-spacing: -1px;
            line-height: 1.2;
            color: {THEME['text']};
            margin-top: 10px;
        ">
            Global Wind Explorer
        </div>
        <div style="
            font-size: 14px;
            line-height: 1.7;
            color: {THEME['muted']};
            margin-top: 10px;
            max-width: 680px;
        ">
            Explore atmospheric circulation across the planet with an
            interactive global wind visualization.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Compact information bar
st.markdown(
    f"""
    <div style="
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 14px 18px;
        border: 1px solid {THEME['border']};
        border-radius: 14px;
        background: {THEME['panel']};
        margin-bottom: 12px;
    ">
        <div>
            <div style="
                font-size: 14px;
                font-weight: 700;
                color: {THEME['text']};
            ">
                🌐 Planetary wind patterns
            </div>
            <div style="
                font-size: 12px;
                color: {THEME['muted']};
                margin-top: 4px;
            ">
                Surface level · Interactive globe
            </div>
        </div>
        <div style="
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.7px;
            color: {THEME['muted']};
            padding: 7px 10px;
            border: 1px solid {THEME['border']};
            border-radius: 9px;
        ">
            EXTERNAL VISUALIZATION
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Large, responsive embedded globe
st.markdown(
    f"""
    <div style="
        border: 1px solid {THEME['border']};
        border-radius: 18px;
        padding: 7px;
        background: {THEME['panel']};
        overflow: hidden;
        box-shadow: 0 10px 32px rgba(0, 0, 0, 0.08);
    ">
    """,
    unsafe_allow_html=True,
)

components.html(
    """
    <iframe
        src="https://earth.nullschool.net/#current/wind/surface/level/orthographic=-90,20,300"
        title="Interactive global wind explorer"
        width="100%"
        height="540"
        style="
            display: block;
            width: 100%;
            border: none;
            border-radius: 13px;
            background: #101820;
        "
        loading="lazy"
        allowfullscreen>
    </iframe>
    """,
    height=550,
    scrolling=False,
)

st.markdown("</div>", unsafe_allow_html=True)

st.caption(
    "Navigate the globe by dragging and zooming. "
    "Wind visualization is provided by earth.nullschool.net; "
    "data availability and update timing depend on that service."
)

st.markdown(
    "[Explore the full wind visualization ↗](https://earth.nullschool.net/)"
)


# ----------------------------- WEATHER ART -----------------------------
st.markdown("## 🎨 Weather art")
st.caption("Creates a local illustrative card from the current conditions; it does not call a paid image-generation API.")

def create_weather_art(city_name, weather_description, temperature, size=(1000, 600)):
    image = Image.new("RGB", size, "#0b1b34")
    draw = ImageDraw.Draw(image)
    # Decorative gradient-like horizontal bands
    for y in range(size[1]):
        blend = y / max(size[1] - 1, 1)
        r = int(9 + 25 * blend)
        g = int(25 + 55 * blend)
        b = int(53 + 90 * blend)
        draw.line((0, y, size[0], y), fill=(r, g, b))
    # Glowing sun / moon illustration
    draw.ellipse((size[0] - 300, 70, size[0] - 100, 270), fill="#80e8f4")
    draw.ellipse((size[0] - 280, 90, size[0] - 120, 250), fill="#baf7ff")
    try:
        title_font = ImageFont.truetype("DejaVuSans.ttf", 48)
        body_font = ImageFont.truetype("DejaVuSans.ttf", 30)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    draw.text((55, 70), "WEATHER SNAPSHOT", fill="#75efff", font=body_font)
    draw.text((55, 155), city_name[:35], fill="white", font=title_font)
    draw.text((55, 235), weather_description[:45].capitalize(), fill="#dceeff", font=body_font)
    draw.text((55, 305), f"{temperature:.1f}°C", fill="white", font=title_font)
    draw.text((55, 520), "BLIZZARD BUDDY  •  WEATHER INTELLIGENCE", fill="#b8d9ee", font=body_font)
    return image

if st.button("Create weather art"):
    artwork = create_weather_art(city_name, description, temp)
    st.image(artwork, caption=f"Weather snapshot for {city_name}", use_container_width=True)
    image_bytes = BytesIO()
    artwork.save(image_bytes, format="PNG")
    st.download_button(
        "Download weather art (PNG)",
        data=image_bytes.getvalue(),
        file_name=f"{city_name.lower().replace(' ', '_')}_weather_art.png",
        mime="image/png",
    )

# ----------------------------- EXPORT -----------------------------
st.markdown("## 📦 Export forecast data")
export_rows = []
for item in forecast.get("list", []):
    try:
        local_dt = local_time_from_timestamp(item["dt"], timezone_offset)
        item_weather = item.get("weather", [{}])[0]
        export_rows.append(
            {
                "datetime_local": local_dt.isoformat(sep=" ", timespec="minutes"),
                "temperature_c": item["main"].get("temp"),
                "feels_like_c": item["main"].get("feels_like"),
                "humidity_percent": item["main"].get("humidity"),
                "wind_speed_m_s": item.get("wind", {}).get("speed"),
                "weather": item_weather.get("main"),
                "description": item_weather.get("description"),
                "precipitation_probability": item.get("pop"),
            }
        )
    except (KeyError, TypeError):
        continue

export_df = pd.DataFrame(export_rows)
if export_df.empty:
    st.caption("Forecast export is unavailable because no forecast records were returned.")
else:
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    json_bytes = export_df.to_json(orient="records", indent=2).encode("utf-8")
    export_col1, export_col2 = st.columns(2)
    with export_col1:
        st.download_button(
            "⬇️ Download forecast CSV",
            data=csv_bytes,
            file_name=f"{city_name.lower().replace(' ', '_')}_forecast.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with export_col2:
        st.download_button(
            "⬇️ Download forecast JSON",
            data=json_bytes,
            file_name=f"{city_name.lower().replace(' ', '_')}_forecast.json",
            mime="application/json",
            use_container_width=True,
        )
    with st.expander("Preview export data"):
        st.dataframe(export_df.head(10), use_container_width=True)

# ----------------------------- AUDIO / TTS -----------------------------
if enable_ambient_audio:
    st.markdown("## 🎵 Ambient audio")
    st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")
    st.caption("Audio is hosted externally and requires an internet connection.")

# Optional local text-to-speech is intentionally user-triggered.
if pyttsx3 is not None:
    if st.button("🔊 Speak current weather (local voice)"):
        try:
            engine = pyttsx3.init()
            engine.say(f"In {city_name}, it is {temp:.1f} degrees Celsius with {description}. {comfort_tip}")
            engine.runAndWait()
        except Exception:
            st.warning("Local text-to-speech is not available in this environment. The dashboard will continue to work.")
else:
    st.caption("Local text-to-speech is optional and is not installed in this environment.")

# ----------------------------- FOOTER -----------------------------
st.divider()
st.markdown(
    f"""
    <div style="text-align:center;color:{THEME['muted']};padding: .5rem 0 1.2rem;">
      <strong>Blizzard Buddy</strong> · Weather Intelligence Dashboard<br>
      <span style="font-size:.82rem;">Built with Python, Streamlit, Pandas and OpenWeather. AI features are optional.</span>
    </div>
    """,
    unsafe_allow_html=True,
)
