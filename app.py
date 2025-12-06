from datetime import datetime, timedelta

import numpy as np
from flask import Flask, render_template, request, jsonify
import requests
import logging
import sqlite3
import os
import json

from data_processing import save_daily_records_to_db, compute_monthly_averages, read_cached_monthly_averages

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "weather_data.db")
API_KEY = "01a17c9029e57ed3c9e1ad4fdb701838"
def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row  # Optional: allows dict-like row access
        return conn
    except Exception as e:
        app.logger.error(f"Database connection error: {e}")
        return None


# Create SQLite DB
def init_db():
    conn = sqlite3.connect(DATABASE)
    if conn is None:
        app.logger.error("Failed to initialize database.")
        return

    cursor = conn.cursor()

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT NOT NULL,
                temperature REAL,
                description TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
                CREATE TABLE IF NOT EXISTS climate_monthly_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city TEXT NOT NULL,
                    month INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    avg_temp REAL,
                    total_precip REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(city, month, year)
                );
            ''')
        conn.commit()
    except Exception as e:
        app.logger.error(f"Error creating tables: {e}")
    finally:
        conn.close()

init_db()

# code a city name to latitude and logittude using OpenWeather Geocoding

def geocode_city(city):
    key = API_KEY
    if not key:
        app.logger.warning("OPENWEATHER_API_KEY not set - geocoding may fail.")
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={key}"
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        app.logger.error(f"Geocoding failed: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    if not data:
        return None
    return {"lat": data[0]["lat"], "lon": data[0]["lon"], "name": data[0].get("name", city)}

# Historical fetch: NOTE - OpenWeather One Call "timemachine" historically returns daily/hourly for a given timestamp.
# Many accounts must call once per day for each historical day;
# This function demonstrates approach and includes a fallback to generate synthetic data if API is not available.
def fetch_historical_daily(lat, lon, start_date, end_date):
    """
    Fetch daily historical records between start_date and end_date (inclusive).
    Returns list of dicts: {'date': 'YYYY-MM-DD', 'temp': float, 'precip': float}
    WARNING: Replace with your paid/allowed endpoint logic if necessary.
    """
    key = API_KEY
    results = []
    # Attempt a simple approach: use OpenWeather "onecall/timemachine" for each day (note: hourly data returned)
    current = start_date
    while current <= end_date:
        timestamp = int(datetime(current.year, current.month, current.day, 24).timestamp())
        url = f"https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={lat}&lon={lon}&dt={timestamp}&units=metric&appid={key}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # compute daily avg temp from hourly (if present)
                temps = []
                precip = 0.0
                hourly = data.get("hourly") or []
                for h in hourly:
                    temps.append(h.get("temp"))
                    # precipitation may be inside 'rain' or 'snow'
                    r = h.get("rain", {}).get("1h", 0) if isinstance(h.get("rain", {}), dict) else 0
                    s = h.get("snow", {}).get("1h", 0) if isinstance(h.get("snow", {}), dict) else 0
                    precip += (r or 0) + (s or 0)
                avg_temp = float(np.mean(temps)) if temps else None
                results.append({"date": current.strftime("%Y-%m-%d"), "temp": avg_temp, "precip": precip})
            else:
                app.logger.warning(f"Timemachine API failed for {current}: {resp.status_code}")
                # fallback: append None or skip
                results.append({"date": current.strftime("%Y-%m-%d"), "temp": None, "precip": None})
        except Exception as e:
            app.logger.error(f"Error fetching historical for {current}: {e}")
            results.append({"date": current.strftime("%Y-%m-%d"), "temp": None, "precip": None})
        current = current + timedelta(days=1)
    return results


# This is a 'fake' history generator used for offline devloping of the api, if needed
def generate_synthetic_history(start_date, end_date, base_temp=12.0, seasonal_amp=10.0):
    results = []
    current = start_date
    while current <= end_date:
        doy = current.timetuple().tm_yday
        season = seasonal_amp * np.sin(2 * np.pi * (doy / 365.0))
        temp = base_temp + season + np.random.normal(0, 2)
        precip = max(0.0, np.random.normal(2.0, 2.0))
        results.append({"date": current.strftime("%Y-%m-%d"), "temp": float(temp), "precip": float(precip)})
        current += timedelta(days=1)
    return results

@app.route('/')
def home ():

    # Fetch previous searches from SQLite DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT city, temperature, description, date FROM searches ORDER BY id DESC LIMIT 5")
    recent = cursor.fetchall()
    conn.close()
    return render_template('index.html', recent=recent)

@app.route('/weather', methods=['POST'])
def weather():
    city = request.form['city']
    api_key = "01a17c9029e57ed3c9e1ad4fdb701838"


   # if not api_key:
        # error message that is visible to myself(developer)
       # app.logger.error("OpenWeather API Key not found. Set key above at api_key")

        # error message that gets seen by the end user  if no api key is set or not set properly
       # render_template("index.html", error="Service temporarily unavailable. Please try again later.")

    # API Call to OpenWeather API
    # Current weather endpoint
    current_url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=imperial&appid={api_key}"
    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&units=imperial&appid={api_key}"

    current_response = requests.get(current_url)
    forecast_response = requests.get(forecast_url)
    current_data = current_response.json()
    forecast_data = forecast_response.json()
    # Error message displayed if city is not found when searching



    if current_response.status_code != 200 or current_data.get("cod") != 200:
        app.logger.warning(f"City not found: {city}")
        return render_template("index.html", error=f"City '{city}' not found.")
    weather_data = {
        "city": current_data["name"],
        "temperature": current_data["main"]["temp"],
        "description": current_data["weather"][0]["description"].capitalize(),
        "humidity": current_data["main"]["humidity"],
        "icon": current_data["weather"][0]["icon"]
    }


    # Extract 5 day forecast
    forecast_list = []
    for i in range(0, len(forecast_data["list"]), 8):
        day = forecast_data["list"][i]
        forecast_list.append({
            "date": day["dt_txt"].split(" ")[0],
            "temp": day["main"]["temp"],
            "desc": day["weather"][0]["description"].capitalize(),
            "icon": day["weather"][0]["icon"]
        })

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO searches (city, temperature, description) VALUES (?, ?, ?)",
        (weather_data["city"], weather_data["temperature"], weather_data["description"])
    )
    conn.commit()

    cursor.execute("SELECT city, temperature, description, date FROM searches ORDER BY id DESC LIMIT 5")
    recent = cursor.fetchall()
    conn.close()

    return render_template("index.html", weather=weather_data, forecast = forecast_list, recent = recent)


@app.route('/trends', methods=['GET'])
def trends_page():
    # page with charts (separate template)
    return render_template('trends.html')

@app.route('/climate')
def climate_page():
    # Get recent cities so you can pre-fill a dropdown
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT city FROM searches ORDER BY date DESC")
    rows = cursor.fetchall()
    conn.close()

    # Turn rows into plain list of city names
    cities = [row['city'] for row in rows] if rows else []

    # Default city for the form (optional)
    default_city = cities[0] if cities else ""

    return render_template("climate.html", cities=cities, default_city=default_city)

@app.route('/api/trends', methods=['POST'])
def api_trends():
    """
    Accepts JSON: { "city": "Chicago", "years": 30 }
    Returns monthly averages for the last `years` years in JSON:
    { "months": ["Jan", ...], "avg_temps": [...], "avg_precips": [...] }
    """
    payload = request.get_json() or {}
    city = payload.get("city")
    years = int(payload.get("years", 30))
    if not city:
        return jsonify({"error": "Please provide a city"}), 400

    # geocode
    geo = geocode_city(city)
    if not geo:
        return jsonify({"error": "Could not geocode city"}), 400

    lat = geo["lat"]
    lon = geo["lon"]

    # Determine date range: last `years` years up to today
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=365 * years)

    # First, try to read pre-computed monthly averages from cache
    cached = read_cached_monthly_averages(DATABASE, city, years)
    if cached is not None:
        app.logger.info("Serving cached monthly averages")
        return jsonify(cached)

    # Otherwise, attempt to fetch daily historical data for the range
    app.logger.info(f"Fetching historical data for {city} from {start_date} to {end_date}")
    try:
        # NOTE: Full-range calls to timemachine will be slow and rate-limited; do small batches or use paid endpoints.
        # For demo / testing we generate synthetic data if timemachine is not accessible.
        daily_records = fetch_historical_daily(lat, lon, start_date, end_date)
        # If API provided mostly None, fallback to synthetic
        valid_count = sum(1 for r in daily_records if r.get("temp") is not None)
        if valid_count < len(daily_records) * 0.5:
            app.logger.warning("Insufficient historical data from API. Generating synthetic history for demo.")
            daily_records = generate_synthetic_history(start_date, end_date, base_temp=12.0, seasonal_amp=10.0)
    except Exception as e:
        app.logger.error(f"Error fetching historical: {e}")
        # fallback
        daily_records = generate_synthetic_history(start_date, end_date, base_temp=12.0, seasonal_amp=10.0)

    # Save daily records to DB for caching
    save_daily_records_to_db(DATABASE, city, daily_records)

    # Compute monthly averages using data_processing helper
    months, avg_temps, avg_precips = compute_monthly_averages(DATABASE, city, years)

    result = {
        "city": city,
        "months": months,
        "avg_temps": avg_temps,
        "avg_precips": avg_precips
    }
    return jsonify(result), 200


if __name__ == "__main__":
    app.run(debug=True)
