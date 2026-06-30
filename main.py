import requests
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, render_template, request
import csv


# Load env variables
load_dotenv()
api_key = os.getenv("API_KEY")


# Initialize Flask app
app = Flask(__name__)


# Load cities function (for citysearch)
def load_cities(filename: str = "worldcities.csv") -> list:
    try:
        cities = []

        with open(filename) as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row["city_ascii"]
                cities.append(name)
        return cities
    except Exception as e:
        sys.exit(e)


# GET openweather geolocation (lat, lon)
def get_geolocation(cityname: str) -> tuple:
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={cityname}&limit=1&appid={api_key}"

    response = requests.get(url)
    data = response.json()

    return data[0]["lat"], data[0]["lon"]


# GET openweather forecast
def get_weather_info(lat: float, lon: float) -> list[dict]:
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}"

        response = requests.get(url)
        data = response.json()

        forecast = []

        for day in data["list"][::7]:
            forecast.append({
                "date": datetime.fromtimestamp(day["dt"], timezone.utc).strftime("%A, %d %B"),
                "description": day["weather"][0]["description"],
                "temp": round(day["main"]["temp"] - 273.15, 1),
                "temp_min": round(day["main"]["temp_min"] - 273.15, 1),
                "temp_max": round(day["main"]["temp_max"] - 273.15, 1),
                "humidity": day["main"]["humidity"],
                "chance_of_rain": round(day.get("pop", 0) * 100)
            })

        return forecast  # <-- this was missing
    except Exception as e:
        raise e


# API Routes
@app.route("/")
def root():
    cities = load_cities()
    return render_template("home.html", cities=cities)

@app.route("/weather")
def weather():
    cityname = request.args.get("citysearch")
    if not cityname:
        return redirect("/")

    lat, lon = get_geolocation(cityname)
    data = get_weather_info(lat, lon)

    if not data:
        return None

    return render_template("weather.html", forecast=data, city=cityname)


def main():
    app.run(port=5000, debug=True)


if __name__ == '__main__':
    main()