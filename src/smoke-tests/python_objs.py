from __future__ import annotations

import os
import polars as pl
import numpy as np
from plotsrv import plotsrv

HOST = os.getenv("PLOTSRV_HOST", os.getenv("HOST", "127.0.0.1"))
PORT = int(os.getenv("PLOTSRV_PORT", os.getenv("PORT", "8998")))


@plotsrv(label="planets (nested dict)", host=HOST, port=PORT)
def get_planets():
    planets = {
        "earth": {
            "type": "terrestrial",
            "moons": ["Moon"],
            "radius_km": 6371,
            "atmosphere": {
                "composition": {
                    "nitrogen": 78.08,
                    "oxygen": 20.95,
                    "argon": 0.93,
                    "co2": 0.04,
                },
                "pressure_kpa": 101.325,
            },
            "life": True,
        },
        "mars": {
            "type": "terrestrial",
            "moons": ["Phobos", "Deimos"],
            "radius_km": 3389,
            "atmosphere": {
                "composition": {
                    "co2": 95.0,
                    "nitrogen": 2.7,
                    "argon": 1.6,
                },
                "pressure_kpa": 0.61,
            },
            "life": False,
        },
        "jupiter": {
            "type": "gas_giant",
            "moons": ["Io", "Europa", "Ganymede", "Callisto"],
            "radius_km": 69911,
            "atmosphere": {
                "composition": {
                    "hydrogen": 89.8,
                    "helium": 10.2,
                },
                "storms": {
                    "great_red_spot": {
                        "duration_years": 350,
                        "wind_speed_kmh": 430,
                    }
                },
            },
            "life": None,
        },
    }

    return planets


@plotsrv(label="weather_observations (nested list)", host=HOST, port=PORT)
def get_weather_observations():
    weather_observations = [
        {
            "city": "New York",
            "timestamp": "2025-01-15T08:00:00",
            "temperature_c": -3,
            "humidity": 65,
            "conditions": ["snow", "wind"],
        },
        {
            "city": "London",
            "timestamp": "2025-01-15T13:00:00",
            "temperature_c": 7,
            "humidity": 82,
            "conditions": ["rain"],
            "wind_kmh": 18,
        },
        {
            "city": "Tokyo",
            "timestamp": "2025-01-15T21:00:00",
            "temperature_c": 10,
            "humidity": 55,
            "conditions": [],
            "air_quality": {
                "pm2_5": 12,
                "pm10": 20,
            },
        },
    ]

    return weather_observations


@plotsrv(label="computer_resources (nested dict)", host=HOST, port=PORT)
def get_computer_resources():
    computer_resources = {
        "servers": {
            "srv-001": {
                "cpu_cores": 32,
                "memory_gb": 128,
                "disks": [
                    {"mount": "/", "size_gb": 500, "used_gb": 320},
                    {"mount": "/data", "size_gb": 2000, "used_gb": 1530},
                ],
                "status": "online",
            },
            "srv-002": {
                "cpu_cores": 16,
                "memory_gb": 64,
                "disks": [
                    {"mount": "/", "size_gb": 250, "used_gb": 249},
                ],
                "status": "degraded",
                "alerts": ["disk_full"],
            },
        },
        "clusters": {
            "alpha": {
                "region": "us-east",
                "servers": ["srv-001", "srv-002"],
            }
        },
    }

    return computer_resources


@plotsrv(label="Satellite (class)", host=HOST, port=PORT)
class Satellite:
    def __init__(self, name, planet, altitude_km, instruments):
        self.name = name
        self.planet = planet
        self.altitude_km = altitude_km
        self.instruments = instruments
        self.operational = True

    def deactivate(self):
        self.operational = False

    def summary(self):
        return {
            "name": self.name,
            "planet": self.planet,
            "altitude_km": self.altitude_km,
            "instrument_count": len(self.instruments),
            "operational": self.operational,
        }


@plotsrv(label="random array (np.array)", host=HOST, port=PORT)
def get_random_np():
    arr = np.random.randn(5000, 10)
    return arr


@plotsrv(label="satellites (nested list)", host=HOST, port=PORT)
def get_satellites_list():
    satellites = [
        Satellite(
            name="Hubble",
            planet="earth",
            altitude_km=547,
            instruments=["camera", "spectrograph"],
        ),
        Satellite(
            name="Mars Recon Orbiter",
            planet="mars",
            altitude_km=300,
            instruments=["radar", "camera"],
        ),
    ]

    return satellites


@plotsrv(label="planet_metrics (pl.df)", host=HOST, port=PORT)
def get_planet_metrics_df():
    planet_metrics = pl.DataFrame(
        {
            "planet": ["Earth", "Mars", "Jupiter"],
            "gravity_m_s2": [9.81, 3.71, 24.79],
            "escape_velocity_km_s": [11.2, 5.0, 59.5],
            "mean_temp_c": [15, -63, -110],
        }
    )

    return planet_metrics


@plotsrv(label="mixed_objects (nested list)", host=HOST, port=PORT)
def get_mixed_objects_list():
    mixed_objects = [
        planets["earth"],
        weather_observations[0],
        satellites[0],
        {"note": "this list is intentionally heterogeneous"},
    ]

    return mixed_objects


if __name__ == "__main__":
    planets = get_planets()
    weather_observations = get_weather_observations()
    computer_resources = get_computer_resources()
    satellites = get_satellites_list()
    planet_metrics = get_planet_metrics_df()
    mixed_objects = get_mixed_objects_list()
    array = get_random_np()
