import math
import random


def generate_random_points(lat: float, long: float, radius_m: int) -> tuple[str, str]:
    earth_radius = 6378137.0  # (WGS84 spheroid)

    random_dist = math.sqrt(random.random()) * radius_m
    random_angle = 2 * math.pi * random.random()

    delta_lat_rad = (random_dist / earth_radius) * math.sin(random_angle)
    delta_long_rad = (random_dist / (earth_radius * math.cos(math.radians(lat)))) * math.cos(random_angle)

    delta_lat_deg = math.degrees(delta_lat_rad)
    delta_long_deg = math.degrees(delta_long_rad)

    new_lat = lat + delta_lat_deg
    new_long = long + delta_long_deg

    new_lat = f"{new_lat:.6f}"
    new_long = f"{new_long:.6f}"

    return (new_lat, new_long)
