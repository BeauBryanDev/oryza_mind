
import requests
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class WeatherInput(BaseModel):
    location: str = Field(
        description="Name of the City or County from the farmer."
    )


def _get_coordinates(location: str) -> Optional[tuple[float, float, str]]:
    """Get lat, long and official name by  Open-Meteo Geocoding API."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    
    params = {"name": location, 
              "count": 1, 
              "language": "es", 
              "format": "json"}
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("results"):
            return None
            
        result = data["results"][0]
        return result["latitude"], result["longitude"], result.get("name", location)
    
    except Exception:
        return None


@tool("get_crop_weather", args_schema=WeatherInput)
def get_crop_weather(location: str) -> str:
    """
    Check current weather conditions and the daily forecast for an agricultural region.

    Use this tool when a farmer asks about the current weather, rainfall, temperatures, or whether conditions are favorable or detrimental to rice planting.
    """
    coords = _get_coordinates(location)
    
    if not coords:
        return f"Error: unable to fetch coordainates '{location}'."
        
    lat, lon, resolved_name = coords
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "wind_speed_10m",
            "weather_code"
        ],
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max"
        ],
        "timezone": "auto",
        "forecast_days": 3
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        current = data.get("current", {})
        daily = data.get("daily", {})
        
        # Format the payload into a summary string for the model to use in its response.
        summary = (
            f"Weather conditions for {resolved_name} (Lat: {lat:.2f}, Lon: {lon:.2f}):\n"
            f"- Current weather :\n"
            f"  * Temperature: {current.get('temperature_2m')} °C\n"
            f"  * Relative  Humidity {current.get('relative_humidity_2m')} %\n"
            f"  * Precipitation: {current.get('precipitation')} mm\n"
            f"  * Wind Speed: {current.get('wind_speed_10m')} km/h\n"
            f"- Forecasting +  3 Days :\n"
            f"  * Max : {daily.get('temperature_2m_max')}\n"
            f"  * Mín: {daily.get('temperature_2m_min')}\n"
            f"  * Cumulate precipitation (mm): {daily.get('precipitation_sum')}\n"
            f"  * Rain Probs (%): {daily.get('precipitation_probability_max')}"
        )
        return summary
        
    except requests.RequestException as e:
        
        return f"Error getting the APi : {str(e)}"