"""
Blizzard Buddy — Weather Dashboard
Run with: streamlit run Blizzard_Buddy_Reference_Dashboard.py

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
    page_title="Blizzard Buddy | AI Weather Dashboard",
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
    "Pastel Dream": {
        "background": "#FFF7FB",
        "panel": "#FCE8F2",
        "text": "#34243D",
        "muted": "#76647D",
        "accent": "#D9469A",
        "border": "rgba(217, 70, 154, 0.22)",
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
    "Midnight Blue": {
        # Light icy surfaces with navy and blue accents, not a dark full-page background.
        "background": "#F2F7FF",
        "panel": "#E1ECFC",
        "text": "#1B2F50",
        "muted": "#5B7191",
        "accent": "#2869C7",
        "border": "rgba(40, 105, 199, 0.24)",
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
    st.caption("Weather intelligence · Personal planning")
    theme_name = st.selectbox("Appearance", list(THEMES.keys()), index=5, help="Choose a calm, readable color palette.")
    st.divider()
    st.markdown("### ⚙️ Dashboard settings")
    default_city = st.text_input("Default city", value=st.session_state.get("bb_default_city", "Noida"), key="bb_default_city_input", help="Used as the starting city each time the app opens.").strip() or "Noida"
    st.session_state["bb_default_city"] = default_city
    forecast_horizon = st.select_slider("Hourly outlook", options=[8, 16, 24, 40], value=16, format_func=lambda x: f"Next {x} hours")
    show_forecast_table = st.toggle("Show detailed forecast table", value=True)
    show_extra_insights = st.toggle("Show planning insights", value=True)
    use_voice_input = st.checkbox("🎙️ Speak city name", value=False, help="Requires a microphone and speech-recognition dependencies.")
    enable_ambient_audio = st.checkbox("🎵 Show ambient audio controls", value=False)
    st.caption("Weather readings come from the configured provider. AI text is optional and may fall back to rule-based guidance.")

THEME = THEMES[theme_name]
st.markdown(
    f"""
    <style>
    :root {{ color-scheme: light; }}
    .stApp {{ background: {THEME['background']}; color: {THEME['text']}; }}
    .block-container {{ max-width: 1320px; padding-top: 1.5rem; padding-bottom: 3rem; }}
    h1, h2, h3 {{ letter-spacing: -.025em; color: {THEME['text']}; }}
    [data-testid="stHeader"] {{ background: transparent; }}
    [data-testid="stSidebar"] {{ background: #ffffff; border-right: 1px solid #e4e9f1; }}
    [data-testid="stSidebar"] * {{ color: #263548; }}
    [data-testid="stMetric"] {{ background: #ffffff; border: 1px solid #e4e9f1; border-radius: 16px; padding: 1rem; box-shadow: 0 2px 8px rgba(25,45,75,.035); }}
    [data-testid="stMetricLabel"] {{ color: #64748b; font-weight: 600; }}
    [data-testid="stMetricValue"] {{ color: {THEME['text']}; letter-spacing: -.035em; }}
    .stTextInput input, .stSelectbox [data-baseweb="select"] > div {{ border-radius: 12px !important; border-color: #d8e0eb !important; }}
    .stButton > button, [data-testid="stDownloadButton"] button {{ border-radius: 12px !important; font-weight: 650; border-color: #d4deeb !important; transition: background .15s ease, transform .15s ease; }}
    .stButton > button:hover, [data-testid="stDownloadButton"] button:hover {{ transform: translateY(-1px); }}
    [data-testid="stTabs"] button {{ font-weight: 650; }}
    .hero {{ padding: 1.65rem 1.8rem; border: 1px solid #e2e8f0; border-radius: 22px; background: linear-gradient(120deg,#ffffff,#edf4ff); margin-bottom: 1.2rem; box-shadow: 0 4px 16px rgba(30,55,90,.04); }}
    .hero-kicker {{ color: #526b8b; font-size: .75rem; font-weight: 750; letter-spacing: .1em; text-transform: uppercase; }}
    .hero-title {{ color: #1d3557; font-size: clamp(2rem,4vw,3rem); line-height: 1.12; font-weight: 780; margin: .45rem 0; }}
    .hero-subtitle {{ color: #61738b; margin: 0; }}
    .weather-console {{ display:grid; grid-template-columns:minmax(0,1.3fr) minmax(160px,.7fr); gap:1rem; padding:clamp(1.3rem,3vw,2rem); margin:.5rem 0 1.25rem; border:1px solid #e0e7f0; border-radius:24px; background:#ffffff; box-shadow:0 4px 18px rgba(30,55,90,.045); }}
    .console-kicker {{ color:#526b8b; font-size:.72rem; font-weight:750; letter-spacing:.1em; text-transform:uppercase; }}
    .console-location {{ color:#263b59; font-size:clamp(1.1rem,2vw,1.45rem); font-weight:700; margin:.45rem 0 .2rem; }}
    .console-condition {{ color:#60728a; font-size:1rem; text-transform:capitalize; }}
    .console-temperature {{ color:#172b4d; font-size:clamp(3.6rem,8vw,5.8rem); font-weight:750; line-height:1; letter-spacing:-.075em; margin:.8rem 0 .55rem; }}
    .console-temp-unit {{ font-size:.42em; vertical-align:top; letter-spacing:-.02em; color:#50627b; }}
    .console-status {{ display:inline-flex; align-items:center; gap:.45rem; padding:.4rem .7rem; border-radius:999px; border:1px solid #dce7f5; color:#315b89; background:#f4f8fe; font-size:.76rem; font-weight:700; }}
    .console-orb {{ display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:175px; text-align:center; }}
    .console-weather-icon {{ font-size:clamp(4rem,7vw,6rem); }}
    .console-orb-label {{ color:#667991; font-size:.84rem; margin-top:.3rem; }}
    .metric-card {{ padding:1.05rem 1.1rem; border-radius:16px; border:1px solid #e2e8f0; background:#ffffff; min-height:116px; box-shadow:0 2px 8px rgba(25,45,75,.025); }}
    .metric-label {{ color:#667991; font-size:.75rem; font-weight:700; letter-spacing:.045em; text-transform:uppercase; margin-bottom:.5rem; }}
    .metric-value {{ color:#203654; font-size:clamp(1.25rem,2vw,1.7rem); font-weight:750; letter-spacing:-.035em; }}
    .holo-card {{ background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:1rem .6rem; min-height:195px; text-align:center; box-shadow:0 2px 8px rgba(25,45,75,.025); }}
    .holo-day {{ color:#526b8b; font-weight:700; }} .holo-icon {{ font-size:1.9rem; margin:.55rem 0; }} .holo-condition {{ color:#667991; text-transform:capitalize; }} .holo-temp {{ color:#203654; margin-top:.7rem; line-height:1.8; }}
    .section-note {{ color:#667991; font-size:.88rem; }}
    div[data-testid="stAlert"] {{ border-radius:14px; }}
    [data-testid="stDataFrame"], [data-testid="stTable"] {{ background:#fff; border-radius:12px; }}
    footer {{ visibility:hidden; }}
    @media(max-width:640px) {{ .weather-console {{ grid-template-columns:1fr; }} .console-orb {{ min-height:110px; flex-direction:row; gap:1rem; justify-content:flex-start; }} .console-weather-icon {{ font-size:3.5rem; }} .hero {{ padding:1.2rem; }} }}

    /* Blizzard Buddy reference-inspired dashboard polish */
    .block-container {{ max-width: 1560px; padding-top: .8rem; padding-left: 1.15rem; padding-right: 1.15rem; }}
    [data-testid="stSidebar"] {{ background: linear-gradient(180deg,#082d50 0%,#10294d 58%,#18284b 100%); border-right: 1px solid rgba(255,255,255,.12); }}
    [data-testid="stSidebar"] * {{ color: #f4f8ff; }}
    [data-testid="stSidebar"] [data-baseweb="select"] *, [data-testid="stSidebar"] input {{ color: #10294d !important; }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ color: #dceaff; }}
    [data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.16); }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: .65rem; }}
    .hero {{ position:relative; overflow:hidden; padding:1.35rem 1.6rem; border:1px solid {THEME['border']}; border-radius:20px; background:linear-gradient(115deg,{THEME['panel']} 0%,{THEME['background']} 46%,#dceeff 100%); box-shadow:0 8px 28px rgba(16,42,80,.08); }}
    .hero:after {{ content:""; position:absolute; right:-4rem; top:-7rem; width:19rem; height:19rem; border-radius:50%; background:radial-gradient(circle,rgba(255,255,255,.72),rgba(255,255,255,0) 70%); pointer-events:none; }}
    .hero-kicker {{ color:{THEME['accent']}; }} .hero-title {{ color:{THEME['text']}; }} .hero-subtitle {{ color:{THEME['muted']}; }}
    .weather-console {{ position:relative; overflow:hidden; grid-template-columns:minmax(0,1.45fr) minmax(180px,.55fr); background:linear-gradient(125deg,{THEME['panel']} 0%,#ffffff 58%,{THEME['background']} 100%); border:1px solid {THEME['border']}; border-radius:22px; box-shadow:0 10px 28px rgba(17,43,80,.08); }}
    .weather-console:before {{ content:""; position:absolute; right:-3rem; bottom:-8rem; width:24rem; height:24rem; border-radius:50%; background:radial-gradient(circle,rgba(255,255,255,.85),rgba(255,255,255,0) 68%); pointer-events:none; }}
    .console-temperature {{ color:{THEME['text']}; }} .console-location {{ color:{THEME['text']}; }} .console-condition,.console-kicker,.console-orb-label {{ color:{THEME['muted']}; }}
    .console-status {{ color:{THEME['accent']}; background:{THEME['background']}; border-color:{THEME['border']}; }}
    .metric-card,.holo-card,[data-testid="stMetric"] {{ border:1px solid {THEME['border']}; border-radius:17px; box-shadow:0 5px 18px rgba(16,42,80,.045); transition:transform .16s ease, box-shadow .16s ease; }}
    .metric-card:hover,.holo-card:hover,[data-testid="stMetric"]:hover {{ transform:translateY(-2px); box-shadow:0 9px 22px rgba(16,42,80,.08); }}
    .metric-card {{ background:linear-gradient(145deg,#fff,{THEME['background']}); }}
    .metric-label,.section-note,.holo-day,.holo-condition {{ color:{THEME['muted']}; }} .metric-value,.holo-temp {{ color:{THEME['text']}; }}
    h1,h2,h3 {{ color:{THEME['text']}; }}
    [data-testid="stHeading"] {{ padding-top:.2rem; }}
    [data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap:.35rem; background:{THEME['panel']}; padding:.35rem; border-radius:13px; }}
    [data-testid="stTabs"] button {{ border-radius:10px; }}
    .stButton > button, [data-testid="stDownloadButton"] button {{ background:linear-gradient(120deg,{THEME['accent']},color-mix(in srgb,{THEME['accent']} 72%,#4f8cff)); color:white; border:0 !important; box-shadow:0 4px 12px rgba(25,55,100,.10); }}
    .stButton > button:hover, [data-testid="stDownloadButton"] button:hover {{ color:white; filter:brightness(1.04); }}
    .stTextInput input, .stSelectbox [data-baseweb="select"] > div {{ border-radius:12px !important; }}
    [data-testid="stAlert"] {{ border-radius:15px; border-width:1px; }}
    [data-testid="stDataFrame"], [data-testid="stTable"] {{ border:1px solid {THEME['border']}; border-radius:14px; overflow:hidden; }}
    div[data-testid="stExpander"] {{ border:1px solid {THEME['border']}; border-radius:14px; background:rgba(255,255,255,.72); }}
    footer {{ visibility:hidden; }}
    @media(max-width:640px) {{ .block-container {{ padding-left:.75rem; padding-right:.75rem; }} .weather-console {{ grid-template-columns:1fr; }} .hero {{ padding:1.1rem; }} }}
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


@st.cache_data(ttl=900, show_spinner=False)
def get_air_quality(latitude: float, longitude: float, api_key: str):
    """Fetch OpenWeather air pollution data for the current coordinates."""
    if not api_key:
        return {"error": "missing_key"}
    try:
        response = requests.get(
            f"{WEATHER_BASE_URL}/air_pollution",
            params={"lat": latitude, "lon": longitude, "appid": api_key},
            timeout=12,
        )
        payload = response.json()
        if response.status_code != 200:
            return {"error": payload.get("message", f"Air-quality service returned HTTP {response.status_code}")}
        entries = payload.get("list", [])
        return entries[0] if entries else {"error": "No air-quality readings returned"}
    except (requests.RequestException, ValueError) as exc:
        return {"error": f"Air-quality request failed: {exc}"}


def aqi_description(aqi):
    # OpenWeather Air Pollution API uses a categorical 1–5 scale, not the US AQI scale.
    return {1: ("Good", "Air quality is considered good by this provider's scale."),
            2: ("Fair", "Air quality is fair by this provider's scale."),
            3: ("Moderate", "Sensitive people may prefer to limit prolonged strenuous outdoor activity."),
            4: ("Poor", "Consider reducing prolonged or strenuous outdoor activity."),
            5: ("Very poor", "Consider limiting outdoor exertion and check local health guidance.")}.get(aqi, ("Unavailable", "No categorized reading is available."))


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
      <div class="hero-kicker">WEATHER INTELLIGENCE  ·  LOCAL CONTEXT  ·  PERSONAL PLANNING</div>
      <div class="hero-title">🌦️ Blizzard Buddy</div>
      <p class="hero-subtitle">A personal weather intelligence workspace for forecasts, air quality, readiness planning and transparent data context.</p>
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

default_city = st.session_state.get("bb_default_city", "Noida")
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

# ----------------------------- FUTURISTIC WEATHER CONSOLE -----------------------------
st.markdown(
    f"""
    <div class="weather-console">
      <div>
        <div class="console-kicker">CURRENT WEATHER</div>
        <div class="console-location">📍 {location_label}</div>
        <div class="console-condition">{description} · Local observation {observed_at.strftime('%I:%M %p')}</div>
        <div class="console-temperature">{temp:.1f}<span class="console-temp-unit">°C</span></div>
        <div class="console-status"><span>●</span> CURRENT CONDITIONS LOADED</div>
      </div>
      <div class="console-orb">
        <div class="console-weather-icon">{icon}</div>
        <div>
          <div style="font-weight:800;color:{THEME['text']};font-size:1.05rem">{condition}</div>
          <div class="console-orb-label">Feels like {feels_like:.1f}°C</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("### Weather conditions")
st.caption(f"Live weather snapshot for {location_label} · Updated {observed_at.strftime('%d %b %Y, %I:%M %p')} local time")

metric_specs = [
    ("Feels like", f"{feels_like:.1f}°C", "Perceived temperature"),
    ("Humidity", f"{humidity}%", "Relative humidity"),
    ("Wind speed", f"{wind_speed} m/s", "Surface wind"),
    ("Pressure", f"{pressure} hPa", "Atmospheric pressure"),
    ("Visibility", visibility_km, "Reported visibility"),
    ("Conditions", condition, "Current weather system"),
]
metric_cols = st.columns(3, gap="medium")
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

# Sunlight timing comes from the current-weather response and uses the city's timezone.
sys_data = data.get("sys", {})
def format_city_time(timestamp):
    if not timestamp:
        return "—"
    return local_time_from_timestamp(timestamp, timezone_offset).strftime("%I:%M %p").lstrip("0")
sunrise_text = format_city_time(sys_data.get("sunrise"))
sunset_text = format_city_time(sys_data.get("sunset"))
st.markdown("### Daylight")
sun_cols = st.columns(3)
with sun_cols[0]: st.metric("Sunrise", sunrise_text, help="Local time reported by the weather provider")
with sun_cols[1]: st.metric("Sunset", sunset_text, help="Local time reported by the weather provider")
with sun_cols[2]:
    st.metric("Wind direction", f"{data.get('wind', {}).get('deg', '—')}°", help="Degrees clockwise from north; unavailable if not reported")

if show_extra_insights:
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

# ----------------------------- WEATHER READINESS INDEX -----------------------------
# A transparent, heuristic planning indicator, not an official forecast or safety rating.
readiness_score = 100
readiness_reasons = []
if condition in ("Thunderstorm", "Tornado", "Squall"):
    readiness_score -= 45
    readiness_reasons.append("Severe-weather condition reported")
elif condition in ("Rain", "Drizzle", "Snow"):
    readiness_score -= 18
    readiness_reasons.append("Precipitation may affect outdoor plans")
if temp >= 35 or temp <= 2:
    readiness_score -= 18
    readiness_reasons.append("Temperature is at an extreme for comfort")
if isinstance(wind_speed, (int, float)) and wind_speed >= 10:
    readiness_score -= 15
    readiness_reasons.append("High reported wind speed")
if isinstance(humidity, (int, float)) and humidity >= 85:
    readiness_score -= 8
    readiness_reasons.append("High humidity may feel uncomfortable")
readiness_score = max(0, min(100, readiness_score))
readiness_label = "Favorable" if readiness_score >= 80 else "Use some caution" if readiness_score >= 55 else "Plan carefully"
st.markdown("## 🧭 Weather readiness")
st.caption("A transparent planning aid derived from current conditions—not an official warning, medical assessment, or guarantee of safety.")
ready_col, reason_col = st.columns([1, 2])
with ready_col:
    st.metric("Outdoor planning indicator", f"{readiness_score}/100", readiness_label)
    st.progress(readiness_score / 100)
with reason_col:
    if readiness_reasons:
        st.markdown("**Signals affecting the score**")
        for reason in readiness_reasons:
            st.markdown(f"- {reason}")
    else:
        st.markdown("**No major comfort flags detected in the available current readings.**")
        st.caption("Always check official alerts and the forecast before making safety-critical decisions.")

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
st.markdown("## 5-day forecast")
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

# ----------------------------- HOURLY OUTLOOK -----------------------------
st.markdown("## Hourly outlook")
st.caption("Next available forecast steps from OpenWeather. These are forecast intervals, not guaranteed observations.")
if forecast_items:
    hourly_rows = []
    for item in forecast_items[:forecast_horizon]:
        try:
            local_dt = local_time_from_timestamp(item["dt"], timezone_offset)
            item_weather = item.get("weather", [{}])[0]
            hourly_rows.append({
                "Local time": local_dt.strftime("%a %I %p").lstrip("0"),
                "Condition": item_weather.get("description", "—").capitalize(),
                "Temperature (°C)": round(float(item["main"]["temp"]), 1),
                "Feels like (°C)": round(float(item["main"].get("feels_like", item["main"]["temp"])), 1),
                "Rain chance (%)": round(float(item.get("pop", 0) or 0) * 100),
                "Wind (m/s)": round(float(item.get("wind", {}).get("speed", 0) or 0), 1),
            })
        except (KeyError, TypeError, ValueError):
            continue
    if hourly_rows:
        hourly_df = pd.DataFrame(hourly_rows)
        st.line_chart(hourly_df.set_index("Local time")[["Temperature (°C)", "Feels like (°C)"]])
        if show_forecast_table:
            st.dataframe(hourly_df, use_container_width=True, hide_index=True)
    else:
        st.info("Hourly forecast details are not available in this response.")
else:
    st.info("Hourly forecast is unavailable right now.")

# ----------------------------- AIR QUALITY -----------------------------
st.markdown("## Air quality")
st.caption("Provider-reported air pollution category and pollutant concentrations. This is not a government-issued health alert or the US AQI scale.")
try:
    air_data = get_air_quality(float(data["coord"]["lat"]), float(data["coord"]["lon"]), OPENWEATHER_API_KEY)
except (KeyError, TypeError, ValueError):
    air_data = {"error": "Coordinates were not supplied by the weather service."}
if air_data.get("error"):
    st.info(f"Air-quality readings are unavailable: {air_data['error']}")
else:
    aqi_value = air_data.get("main", {}).get("aqi")
    aqi_label, aqi_note = aqi_description(aqi_value)
    pollutant_components = air_data.get("components", {})
    aq_cols = st.columns(3)
    with aq_cols[0]: st.metric("Provider AQI category", f"{aqi_value}/5" if aqi_value is not None else "—", aqi_label)
    with aq_cols[1]: st.metric("PM₂.₅", f"{pollutant_components.get('pm2_5', '—')} µg/m³")
    with aq_cols[2]: st.metric("PM₁₀", f"{pollutant_components.get('pm10', '—')} µg/m³")
    st.caption(aqi_note + " Pollutant readings are provider data; consult official local guidance for health decisions.")
    with st.expander("More pollutant measurements"):
        pollutant_labels = {"co":"CO (µg/m³)", "no":"NO (µg/m³)", "no2":"NO₂ (µg/m³)", "o3":"O₃ (µg/m³)", "so2":"SO₂ (µg/m³)", "nh3":"NH₃ (µg/m³)"}
        pollutant_rows = [{"Pollutant": label, "Concentration": pollutant_components.get(key, "—")} for key, label in pollutant_labels.items()]
        st.dataframe(pd.DataFrame(pollutant_rows), use_container_width=True, hide_index=True)

# ----------------------------- MICROCLIMATE SNAPSHOT -----------------------------
st.markdown("## 📍 Local environment snapshot")
st.caption("A compact readout of the provider's reported conditions for the selected city. It does not represent street-level sensors.")
local_cols = st.columns(4)
local_facts = [
    ("Cloud cover", f"{data.get('clouds', {}).get('all', '—')}%", "Reported sky coverage"),
    ("Rain in last 1h", f"{data.get('rain', {}).get('1h', 0)} mm", "If supplied by provider"),
    ("Snow in last 1h", f"{data.get('snow', {}).get('1h', 0)} mm", "If supplied by provider"),
    ("Wind direction", f"{data.get('wind', {}).get('deg', '—')}°", "Clockwise from north"),
]
for col, (label, value, help_text) in zip(local_cols, local_facts):
    with col:
        st.metric(label, value, help=help_text)

# ----------------------------- LOCAL ALERT GUIDANCE -----------------------------
st.markdown("## Official weather advisories")
st.caption("The current-weather endpoint used here does not provide official severe-weather alerts. Check your local meteorological authority for warnings before travel or outdoor activities.")
st.markdown("[India Meteorological Department (IMD) — official website](https://mausam.imd.gov.in/) · [OpenWeather data documentation](https://openweathermap.org/api)")

# ----------------------------- ASK SKYLER -----------------------------
st.markdown("## Ask the weather assistant")
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
st.markdown("## Weather fact")
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
st.markdown("## Compare cities")
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

# ----------------------------- SKY VIEW / LIVE WEATHER EXPLORER -----------------------------
st.markdown(
    f"""
    <div class="hero" style="margin-top:1.2rem;">
      <div class="hero-kicker">Atmospheric intelligence · Interactive visualization</div>
      <div class="hero-title">🌐 Live Weather Explorer</div>
      <p class="hero-subtitle">Explore wind, precipitation, temperature and cloud patterns around the world, centered on {city_name}.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

map_layer = st.selectbox(
    "Choose atmospheric layer",
    options=["wind", "rain", "temp", "clouds"],
    format_func=lambda layer: {
        "wind": "💨 Wind flow",
        "rain": "🌧️ Rain & precipitation",
        "temp": "🌡️ Temperature",
        "clouds": "☁️ Cloud cover",
    }[layer],
    key="sky_weather_layer",
    help="Select the weather layer displayed by the external interactive map.",
)

try:
    geo_response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": city_name, "format": "jsonv2", "limit": 1},
        headers={"User-Agent": "BlizzardBuddyWeatherDashboard/1.0"},
        timeout=10,
    )
    geo_response.raise_for_status()
    locations = geo_response.json()
    if locations:
        latitude = float(locations[0]["lat"])
        longitude = float(locations[0]["lon"])
    else:
        latitude, longitude = 20.0, 0.0
        st.info("City coordinates were not found; showing a general global view instead.")
except (requests.RequestException, ValueError, KeyError, TypeError):
    latitude, longitude = 20.0, 0.0
    st.info("Could not locate this city right now; showing a general global view instead.")

map_info_left, map_info_right = st.columns([3, 1])
with map_info_left:
    st.markdown(
        f"""
        <div class="metric-card" style="min-height:unset;">
          <div class="metric-label">ACTIVE VIEW · EXTERNAL MAP SERVICE</div>
          <div class="metric-value" style="font-size:1.25rem;">📍 {city_name}</div>
          <div class="section-note">Selected layer: {map_layer.capitalize()} · Drag to explore the map</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with map_info_right:
    st.markdown(
        f"""
        <div class="metric-card" style="min-height:unset;">
          <div class="metric-label">MAP PROVIDER</div>
          <div class="metric-value" style="font-size:1.15rem;">Windy</div>
          <div class="section-note">Interactive embed</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

map_url = (
    "https://embed.windy.com/embed.html?type=map&location=coordinates"
    f"&lat={latitude}&lon={longitude}&zoom=5&overlay={map_layer}"
    "&level=surface&product=ecmwf&metricTemp=default"
    "&metricWind=default&metricRain=default"
)

components.html(
    f"""
    <iframe src="{map_url}" title="Interactive weather map for {city_name}"
      width="100%" height="560"
      style="display:block;border:0;border-radius:16px;background:#0b1728;"
      loading="lazy" allowfullscreen>
    </iframe>
    """,
    height=570,
    scrolling=False,
)

feature_cols = st.columns(3, gap="medium")
feature_items = [
    ("🌍", "Global perspective", "Explore weather patterns beyond a single city."),
    ("🧭", "City-centered view", "The map starts near your selected location when coordinates are available."),
    ("🛰️", "External visualization", "Map layers and availability depend on the provider."),
]
for col, (symbol, title, note) in zip(feature_cols, feature_items):
    with col:
        st.markdown(
            f"""
            <div class="metric-card" style="min-height:140px;">
              <div style="font-size:1.4rem;margin-bottom:.45rem;">{symbol}</div>
              <div style="font-weight:750;color:{THEME['text']};">{title}</div>
              <div class="section-note" style="margin-top:.45rem;">{note}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
st.markdown("[Open the full interactive map ↗](https://www.windy.com/)")
st.caption("Weather map imagery and forecasts are supplied externally. Availability, layers and update timing depend on the map provider; this dashboard does not independently verify the embedded map data.")

# ----------------------------- WEATHER ART -----------------------------
st.markdown("## Weather snapshot studio")
st.caption("Generate a downloadable illustration using the selected city's current weather data. This is local artwork, not AI-generated imagery.")

def create_weather_art(city_name, weather_description, temperature, size=(1200, 650)):
    image = Image.new("RGB", size, "#14223b")
    draw = ImageDraw.Draw(image)
    width, height = size
    # Smooth vertical gradient
    for y in range(height):
        t = y / max(height - 1, 1)
        color = (int(20 + 45*t), int(36 + 60*t), int(65 + 85*t))
        draw.line((0, y, width, y), fill=color)
    # Soft horizon and atmospheric sun
    draw.ellipse((width-360, 70, width-130, 300), fill="#ffd9a1")
    draw.ellipse((width-335, 95, width-155, 275), fill="#fff0c8")
    draw.polygon([(0, 500), (170, 390), (330, 485), (510, 350), (720, 500), (900, 390), (width, 490), (width, height), (0, height)], fill="#233b58")
    draw.polygon([(0, 555), (220, 465), (420, 565), (690, 450), (900, 560), (width, 470), (width, height), (0, height)], fill="#172d49")
    try:
        title_font = ImageFont.truetype("DejaVuSans.ttf", 54)
        city_font = ImageFont.truetype("DejaVuSans.ttf", 76)
        body_font = ImageFont.truetype("DejaVuSans.ttf", 34)
    except OSError:
        title_font = city_font = body_font = ImageFont.load_default()
    draw.text((64, 58), "BLIZZARD BUDDY  /  WEATHER SNAPSHOT", fill="#aeeaff", font=body_font)
    draw.text((64, 150), city_name[:28], fill="#ffffff", font=city_font)
    draw.text((64, 265), weather_description[:42].capitalize(), fill="#e3efff", font=title_font)
    draw.text((64, 365), f"{temperature:.1f}°C", fill="#ffffff", font=city_font)
    draw.text((64, height-68), f"GENERATED LOCALLY  •  {datetime.now().strftime('%d %b %Y, %H:%M')}", fill="#c8d9ee", font=body_font)
    return image

art_col, art_info_col = st.columns([1.4, 1], gap="large")
with art_col:
    artwork = create_weather_art(city_name, description, temp)
    st.image(artwork, use_container_width=True)
with art_info_col:
    st.markdown("### Your weather card")
    st.markdown(
        f"<div class='metric-card'><div class='metric-label'>CURRENT CONDITIONS</div><div class='metric-value'>{WEATHER_EMOJI.get(weather.get('main', ''), '🌤️')} {temp:.1f}°C</div><div class='section-note'>{description.capitalize()}</div><div class='section-note'>📍 {city_name}</div></div>",
        unsafe_allow_html=True,
    )
    art_bytes = BytesIO()
    artwork.save(art_bytes, format="PNG")
    st.download_button(
        "Download weather card (PNG)", data=art_bytes.getvalue(),
        file_name=f"{city_name.lower().replace(' ', '_')}_weather_snapshot.png",
        mime="image/png", use_container_width=True,
    )
    st.caption("Designed locally with Pillow. No paid image-generation service is used.")

# ----------------------------- EXPORT -----------------------------
st.markdown("## Forecast data export")
st.caption("Download forecast records for reporting, analysis, or your own Python workflows.")
export_rows = []
for item in forecast.get("list", []):
    try:
        local_dt = local_time_from_timestamp(item["dt"], timezone_offset)
        item_weather = item.get("weather", [{}])[0]
        export_rows.append({
            "datetime_local": local_dt.isoformat(sep=" ", timespec="minutes"),
            "temperature_c": item["main"].get("temp"),
            "feels_like_c": item["main"].get("feels_like"),
            "humidity_percent": item["main"].get("humidity"),
            "wind_speed_m_s": item.get("wind", {}).get("speed"),
            "weather": item_weather.get("main"),
            "description": item_weather.get("description"),
            "precipitation_probability": item.get("pop"),
        })
    except (KeyError, TypeError):
        continue

export_df = pd.DataFrame(export_rows)
if export_df.empty:
    st.info("Forecast export will appear here when forecast records are available.")
else:
    export_csv = export_df.to_csv(index=False).encode("utf-8")
    export_json = export_df.to_json(orient="records", indent=2).encode("utf-8")
    export_stats = st.columns(3)
    export_stats[0].metric("Forecast records", f"{len(export_df):,}")
    export_stats[1].metric("Export formats", "CSV · JSON")
    export_stats[2].metric("Selected location", city_name)
    export_left, export_right = st.columns(2, gap="medium")
    with export_left:
        st.download_button("Download CSV", data=export_csv, file_name=f"{city_name.lower().replace(' ', '_')}_forecast.csv", mime="text/csv", use_container_width=True)
    with export_right:
        st.download_button("Download JSON", data=export_json, file_name=f"{city_name.lower().replace(' ', '_')}_forecast.json", mime="application/json", use_container_width=True)
    with st.expander("Preview forecast records"):
        st.dataframe(export_df.head(12), use_container_width=True, hide_index=True)

# ----------------------------- AUDIO / TTS -----------------------------
if enable_ambient_audio:
    st.markdown("## Ambient audio")
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

# ----------------------------- SETTINGS & DATA TRANSPARENCY -----------------------------
with st.expander("⚙️ Settings, data sources & privacy", expanded=False):
    settings_left, settings_right = st.columns(2)
    with settings_left:
        st.markdown("**Your dashboard setup**")
        st.write(f"- Appearance: {theme_name}")
        st.write(f"- Default city: {default_city}")
        st.write(f"- Hourly forecast range: next {forecast_horizon} hours")
        st.write(f"- Detailed forecast table: {'On' if show_forecast_table else 'Off'}")
        st.write(f"- Planning insights: {'On' if show_extra_insights else 'Off'}")
    with settings_right:
        st.markdown("**Data & privacy notes**")
        st.write("- Weather requests are sent to OpenWeather for the city you enter.")
        st.write("- AI questions may be sent to the configured AI provider when an API key is available.")
        st.write("- No account sign-in or location tracking is added by this dashboard.")
        st.write("- Current conditions and forecasts can be delayed or unavailable; use official alerts for safety-critical decisions.")
    st.markdown("**Reference links:** [OpenWeather](https://openweathermap.org/api) · [India Meteorological Department](https://mausam.imd.gov.in/) · [OpenAI API documentation](https://platform.openai.com/docs) ")

# ----------------------------- FOOTER -----------------------------
st.divider()
footer_left, footer_right = st.columns([2, 1])
with footer_left:
    st.markdown(f"**🌦️ Blizzard Buddy**  \n    <span style='color:{THEME['muted']}'>Weather Dashboard</span>", unsafe_allow_html=True)
    st.caption("Built with Python · Streamlit · Pandas · OpenWeather API")
with footer_right:
    st.caption("Weather data and external visualizations may be delayed or unavailable. AI features are optional.")
