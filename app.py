
from flask import Flask, render_template, request
import requests
import logging
import sqlite3
import os
import json
app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "weather_data.db")

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
    conn = get_db_connection()
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
        conn.commit()
    except Exception as e:
        app.logger.error(f"Error creating tables: {e}")
    finally:
        conn.close()

init_db()


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



if __name__ == "__main__":
    app.run(debug=True)
