import os
from datetime import datetime
from collections import defaultdict

import requests
import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

st.set_page_config(page_title="3D AI Weather Chatbot", page_icon="🌦️", layout="wide")

# ---------- CSS ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

* {font-family: 'Inter', sans-serif;}
.stApp {
    background: radial-gradient(circle at top left, #4b3f72 0%, #20264f 35%, #11193b 70%, #0b1028 100%);
    color: white;
}
.block-container {padding-top: 1.3rem; padding-bottom: 2rem;}

.main-title {
    font-size: 38px;
    font-weight: 800;
    color: #ffffff;
    text-shadow: 0 10px 30px rgba(0,0,0,.45);
    margin-bottom: 5px;
}
.sub-title {color:#cbd5ff; margin-bottom:20px;}

.glass-card {
    background: linear-gradient(145deg, rgba(255,255,255,.15), rgba(255,255,255,.06));
    border: 1px solid rgba(255,255,255,.18);
    border-radius: 24px;
    box-shadow: 0 24px 55px rgba(0,0,0,.38);
    padding: 24px;
    backdrop-filter: blur(16px);
}
.weather-big {font-size: 76px; font-weight: 800; line-height: 1;}
.weather-icon {font-size: 78px; filter: drop-shadow(0 15px 16px rgba(0,0,0,.35));}
.badge-alert {
    display:inline-block; padding: 10px 18px; border-radius: 30px;
    background: linear-gradient(135deg, #ff4d4d, #ff7a3d);
    font-weight: 800; box-shadow: 0 10px 25px rgba(255,80,80,.35);
}
.metric-row {display:grid; grid-template-columns: repeat(6,1fr); gap: 14px; margin-top: 22px;}
.metric {background: rgba(255,255,255,.08); border-radius:18px; padding:14px; border:1px solid rgba(255,255,255,.1);}
.metric span {color:#c9d2ff; font-size:13px;}
.metric b {font-size:20px; display:block; margin-top:4px;}

.forecast-grid {display:grid; grid-template-columns: repeat(5,1fr); gap: 16px; margin-top: 16px;}
.forecast-card {
    background: linear-gradient(145deg, rgba(255,255,255,.13), rgba(255,255,255,.05));
    border:1px solid rgba(255,255,255,.14); border-radius:22px; padding:18px;
    box-shadow: 0 16px 35px rgba(0,0,0,.28); min-height:150px;
    transition: .25s;
}
.forecast-card:hover {transform: translateY(-6px) scale(1.02);}
.day {font-size:18px; font-weight:800; color:#fff;}
.f-icon {font-size:43px; margin:13px 0;}
.high {font-size:27px; font-weight:800;}
.low {font-size:19px; color:#b6c2ff;}

.chat-card {
    background: linear-gradient(145deg, rgba(255,255,255,.15), rgba(15,20,50,.75));
    border: 1px solid rgba(255,255,255,.16);
    border-radius: 24px;
    box-shadow: 0 24px 55px rgba(0,0,0,.4);
    padding: 22px;
}

div.stButton > button {
    background: linear-gradient(135deg, #ffd43b, #ff9f1c) !important;
    color: #11193b !important;
    border: none !important;
    border-radius: 16px !important;
    padding: 12px 22px !important;
    font-size: 16px !important;
    font-weight: 800 !important;
    box-shadow: 0 12px 24px rgba(0,0,0,.35) !important;
}
div.stButton > button:hover {transform: scale(1.03); filter: brightness(1.06);}

.stTextInput input, .stTextArea textarea {
    background: rgba(255,255,255,.12) !important;
    color: white !important;
    border-radius: 14px !important;
    border: 1px solid rgba(255,255,255,.22) !important;
}

[data-testid="stSidebar"] {background: linear-gradient(180deg,#171c3f,#0c1028);}
@media(max-width:900px){.metric-row{grid-template-columns:repeat(2,1fr)} .forecast-grid{grid-template-columns:repeat(1,1fr)} .weather-big{font-size:55px}}
</style>
""", unsafe_allow_html=True)

# ---------- Helper functions ----------
def icon_for_weather(desc: str) -> str:
    d = desc.lower()
    if "thunder" in d: return "⛈️"
    if "rain" in d or "drizzle" in d: return "🌧️"
    if "snow" in d: return "❄️"
    if "cloud" in d: return "☁️"
    if "mist" in d or "haze" in d or "fog" in d: return "🌫️"
    if "clear" in d: return "🌙" if datetime.now().hour >= 18 or datetime.now().hour <= 5 else "☀️"
    return "🌤️"

def fetch_weather(city, api_key):
    current_url = "https://api.openweathermap.org/data/2.5/weather"
    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city.strip(), "appid": api_key, "units": "metric"}
    current = requests.get(current_url, params=params, timeout=20).json()
    if str(current.get("cod")) != "200":
        return current, None
    forecast = requests.get(forecast_url, params=params, timeout=20).json()
    return current, forecast

def make_hourly_chart(forecast):
    items = forecast.get("list", [])[:10]
    times = [datetime.fromtimestamp(x["dt"]).strftime("%I %p") for x in items]
    temps = [x["main"]["temp"] for x in items]
    pops = [round(x.get("pop", 0) * 100) for x in items]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=times, y=temps, mode="lines+markers+text",
        text=[f"{t:.0f}°" for t in temps], textposition="top center",
        fill="tozeroy", name="Temperature"
    ))
    fig.add_trace(go.Bar(x=times, y=pops, name="Rain %", yaxis="y2", opacity=.35))
    fig.update_layout(
        height=390,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.04)",
        font=dict(color="white"),
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis=dict(title="Temperature °C", gridcolor="rgba(255,255,255,.1)"),
        yaxis2=dict(title="Rain %", overlaying="y", side="right", range=[0,100], showgrid=False),
        legend=dict(orientation="h")
    )
    return fig

def daily_cards(forecast):
    days = defaultdict(list)
    for item in forecast.get("list", []):
        dt = datetime.fromtimestamp(item["dt"])
        key = dt.strftime("%a %d")
        days[key].append(item)
    cards = []
    for day, items in list(days.items())[:5]:
        temps = [i["main"]["temp"] for i in items]
        desc = items[len(items)//2]["weather"][0]["description"]
        cards.append((day, max(temps), min(temps), desc, icon_for_weather(desc)))
    return cards

def ai_answer(hf_token, weather_text, question):
    client = InferenceClient(token=hf_token)
    res = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct",
        messages=[
            {"role":"system", "content":"You are an AI weather assistant. Answer in simple Hinglish. Answer only when user asks. Use the given weather data. Give practical advice like going outside, umbrella, travel, clothes, health."},
            {"role":"user", "content":f"Weather data:\n{weather_text}\n\nUser question:\n{question}"}
        ],
        max_tokens=180,
        temperature=0.6
    )
    return res.choices[0].message.content

# ================= API KEYS =================

load_dotenv()

openweather_key = os.getenv("OPENWEATHER_API_KEY")
hf_token = os.getenv("HF_TOKEN")

# Debug check
if not openweather_key:
    st.error("OPENWEATHER_API_KEY missing in .env file")
    st.stop()

if not hf_token:
    st.error("HF_TOKEN missing in .env file")
    st.stop()

st.markdown("<div class='main-title'>🌦️ 3D AI Weather Dashboard</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Current weather, hourly forecast, 5-day cards aur smart AI chatbot.</div>", unsafe_allow_html=True)

col_search, col_btn = st.columns([4,1])
with col_search:
    city = st.text_input("City name", placeholder="Example: Darbhanga, Delhi, Patna, Mumbai")
with col_btn:
    st.write("")
    get_weather = st.button("Get Weather")

if "current" not in st.session_state: st.session_state.current = None
if "forecast" not in st.session_state: st.session_state.forecast = None
if "weather_text" not in st.session_state: st.session_state.weather_text = ""

if get_weather:
    if not city.strip():
        st.error("Please city name likho.")
    elif not openweather_key:
        st.error("OpenWeather API key missing .")
    else:
        with st.spinner("Weather data loading..."):
            current, forecast = fetch_weather(city, openweather_key)
        if forecast is None:
            st.error("Weather data nahi mila.")
            st.write(current)
        else:
            st.session_state.current = current
            st.session_state.forecast = forecast
            desc = current["weather"][0]["description"]
            st.session_state.weather_text = f"""
City: {current.get('name')}, {current.get('sys',{}).get('country','')}
Temperature: {current['main']['temp']}°C
Feels Like: {current['main']['feels_like']}°C
Humidity: {current['main']['humidity']}%
Pressure: {current['main']['pressure']} mb
Visibility: {round(current.get('visibility',0)/1000,1)} km
Wind Speed: {current['wind']['speed']} m/s
Weather: {desc}
"""

current = st.session_state.current
forecast = st.session_state.forecast

if current and forecast:
    desc = current["weather"][0]["description"]
    icon = icon_for_weather(desc)
    temp = current["main"]["temp"]
    feels = current["main"]["feels_like"]
    humidity = current["main"]["humidity"]
    pressure = current["main"]["pressure"]
    wind = current["wind"]["speed"]
    visibility = round(current.get("visibility", 0)/1000, 1)
    city_name = f"{current.get('name')}, {current.get('sys',{}).get('country','')}"

    alert_text = "⚠️ Thunderstorm / rain possible" if any(x in desc.lower() for x in ["thunder", "rain", "storm"]) else "✅ No severe alert detected"

    left, right = st.columns([2.1,1])
    with left:
        st.markdown(f"""
        <div class='glass-card'>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <div><h3>Current weather</h3><p style='color:#cbd5ff'>{datetime.now().strftime('%I:%M %p')} • {city_name}</p></div>
                <div class='badge-alert'>{alert_text}</div>
            </div>
            <div style='display:flex; gap:25px; align-items:center; margin-top:12px;'>
                <div class='weather-icon'>{icon}</div>
                <div class='weather-big'>{temp:.0f}°C</div>
                <div><h2 style='margin:0'>{desc.title()}</h2><p>Feels like <b>{feels:.0f}°</b></p></div>
            </div>
            <p style='font-size:20px; margin-top:20px;'>Aaj ka weather <b>{desc}</b> hai. Low/high forecast chart niche dekho.</p>
            <div class='metric-row'>
                <div class='metric'><span>Wind</span><b>{wind} m/s</b></div>
                <div class='metric'><span>Humidity</span><b>{humidity}%</b></div>
                <div class='metric'><span>Visibility</span><b>{visibility} km</b></div>
                <div class='metric'><span>Pressure</span><b>{pressure} mb</b></div>
                <div class='metric'><span>Feels Like</span><b>{feels:.0f}°C</b></div>
                <div class='metric'><span>Condition</span><b>{icon}</b></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with right:
        st.markdown("<div class='glass-card'><h3>🤖 Weather AI Chatbot</h3><p style='color:#cbd5ff'>Ask a question about the weather!</p>", unsafe_allow_html=True)
        question = st.text_area("Ask anything", placeholder="Ask a question...", height=115)
        ask = st.button("Ask AI")
        st.markdown("</div>", unsafe_allow_html=True)
        if ask:
            if not question.strip():
                st.warning("Please type a question.")
            elif not hf_token:
                st.error("Hugging Face token issue.")
            else:
                with st.spinner("AI thinking..."):
                    try:
                        answer = ai_answer(hf_token, st.session_state.weather_text, question)
                        st.success(answer)
                    except Exception as e:
                        st.error("AI chatbot me error aaya.")
                        st.write(e)

    st.markdown("### Hourly overview")
    st.plotly_chart(make_hourly_chart(forecast), use_container_width=True)

    st.markdown("### 5 Day Forecast")

    # Safe forecast cards - code screen par show nahi hoga
    forecast_cols = st.columns(5)
    for col, (day, high, low, d, ic) in zip(forecast_cols, daily_cards(forecast)):
        with col:
            st.markdown(f"""
            <div class='forecast-card'>
                <div class='day'>{day}</div>
                <div class='f-icon'>{ic}</div>
                <div>{d.title()}</div>
                <div style='margin-top:10px'>
                    <span class='high'>{high:.0f}°</span>
                    <span class='low'>{low:.0f}°</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

else:
    st.info("type a city name.")
