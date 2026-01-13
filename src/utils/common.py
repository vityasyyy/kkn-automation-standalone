import asyncio
import math
import random
from asyncio import Task
from typing import Callable

from rich.prompt import Prompt

from ui.tui import console, log


async def async_input(prompt: str = "", func: type | Callable = str, **kwargs):
    return func(await asyncio.to_thread(Prompt.ask, prompt, **kwargs))  # ty: ignore


async def load_background(status: str, job: Task):
    if job.done():
        return

    with console.status(status, spinner="dots"):
        await job


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


def filter_unattended_program(data: dict | None) -> list[dict]:
    if not data:
        log.error("No assisted program found")
        return []

    filtered_program = []

    for key, value in data.items():
        if isinstance(value, dict):
            entries = value.get("entries", [])
            base_info = {"title": value.get("title"), "type": "main", "id": key}
        else:
            entries = value
            base_info = {"pic": key, "type": "bantu"}

        for entry in entries:
            for sub in entry.get("sub_entries", []):
                if not (url := sub.get("attendance_link")):
                    continue

                info = {**base_info, "entry": entry.get("title"), "sub_entry": sub.get("title"), "url": url}
                filtered_program.append(info)

    return filtered_program
