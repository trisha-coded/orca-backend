import requests

url = "https://marine-api.open-meteo.com/v1/marine"

params = {
    "latitude": 12.87,
    "longitude": 74.84,
    "current": "wave_height"
}

response = requests.get(url, params=params)

print("Status code:", response.status_code)
data = response.json()

wave_height = data["current"]["wave_height"]

print("Mangalore wave height:", wave_height, "meters")