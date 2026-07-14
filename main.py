import requests
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
import csv
import geocoder


# Load env variables
load_dotenv()
api_key = os.getenv("API_KEY")


# Initialize Flask app
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DB_URI")
db = SQLAlchemy(app)


# Database schema
class SavedLocations(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cityname = db.Column(db.String(50), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    is_default = db.Column(db.Boolean, default=False)

    # Cached weather data
    temp = db.Column(db.Float)
    temp_min = db.Column(db.Float)
    temp_max = db.Column(db.Float)
    description = db.Column(db.String(100))
    last_updated = db.Column(db.DateTime)

with app.app_context():
    db.create_all()


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
    try:
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={cityname}&limit=1&appid={api_key}"

        response = requests.get(url)
        data = response.json()

        return data[0]["lat"], data[0]["lon"]
    except Exception as e:
        sys.exit(e)


# GET openweather forecast
def get_weather_info(lat: float, lon: float) -> list[dict]:
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}"

        response = requests.get(url)
        data = response.json()

        forecast = []

        for day in data["list"][::8]:
            forecast.append({
                "date": datetime.fromtimestamp(day["dt"], timezone.utc).strftime("%A, %d %B"),
                "description": day["weather"][0]["description"],
                "temp": round(day["main"]["temp"] - 273.15, 1),
                "temp_min": round(day["main"]["temp_min"] - 273.15, 1),
                "temp_max": round(day["main"]["temp_max"] - 273.15, 1),
                "humidity": day["main"]["humidity"],
                "chance_of_rain": round(day.get("pop", 0) * 100)
            })

        return forecast
    except Exception as e:
        sys.exit(e)
    

# Reload cached data for saved locations
def refresh_location_cache(location: SavedLocations):
    data = get_weather_info(location.lat, location.lon)
    today = data[0]

    location.temp = today["temp"]
    location.temp_min = today["temp_min"]
    location.temp_max = today["temp_max"]
    location.description = today["description"]
    location.last_updated = datetime.now(timezone.utc)
    db.session.commit()


# Set default location
def set_default():
    g = geocoder.ip("me")
    cityname = g.city
    lat, lon = g.latlng

    existing_default = SavedLocations.query.filter_by(is_default=True).first()
    if existing_default:
        existing_default.is_default=False
    
    location = SavedLocations.query.filter_by(cityname=cityname).first()
    if not location:
        location = SavedLocations(cityname=cityname, lat=lat, lon=lon, is_default=True)
        db.session.add(location)
    else:
        location.is_default=True

    db.session.commit()
    return ""


CACHED_TIME = timedelta(minutes=30)
# API Routes
@app.route("/")
def root():
    set_default()
    cities = load_cities()
    saved_locations = SavedLocations.query.order_by(SavedLocations.is_default.desc()).all()
    now = datetime.now(timezone.utc)

    for location in saved_locations:
        is_expired = (
            location.last_updated is None or now - location.last_updated.replace(tzinfo=timezone.utc) > CACHED_TIME
        )
        if is_expired:
            refresh_location_cache(location)

    return render_template("home.html", cities=cities, saved_locations=saved_locations)

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

@app.route("/save", methods=["POST"])
def save_location():
    cityname = request.form.get("cityname")

    if not cityname:
        return redirect("/")

    lat, lon = get_geolocation(cityname)

    existing = SavedLocations.query.filter_by(cityname=cityname).first()
    if not existing:
        location = SavedLocations(cityname=cityname, lat=lat, lon=lon)
        db.session.add(location)
        db.session.commit()
    
    return redirect("/")

@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    location = SavedLocations.query.get_or_404(id)
    db.session.delete(location)
    db.session.commit()

    return redirect("/")


def main():
    app.run(port=5000, debug=True)


if __name__ == '__main__':
    main()