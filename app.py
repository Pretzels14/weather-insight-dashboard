
from flask import Flask, render_template, request
import requests
import logging
app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)

@app.route('/')
def home ():
    return render_template('index.html')

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
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=imperial"
    response = requests.get(url)
    data = response.json()

    # Error message displayed if city is not found when searching

    if response.status_code != 200 or data.get("cod") != 200:
        return render_template("index.html", error=f"City '{city}' not found or not available. Try again")

    weather_data = {
        "city": data["name"],
        "temperature": data["main"]["temp"],
        "description": data["weather"][0]["description"].capitalize(),
        "humidity": data["main"]["humidity"],
        "icon": data["weather"][0]["icon"]
    }

    print("DEBUG URL:", url)
    print("Response Code:", response.status_code)
    print("Response JSON:", data)

    return render_template("index.html", weather=weather_data)



if __name__ == "__main__":
    app.run(debug=True)
