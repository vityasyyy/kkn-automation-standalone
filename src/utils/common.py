import asyncio
import math
import os
import random
from asyncio import Task
from typing import Callable

from prompt_toolkit.formatted_text import AnyFormattedText

from ui.tui import console, prompt_session


async def async_input(prompt: str | AnyFormattedText = "", func: type | Callable = str, **kwargs):
  try:
    result = await prompt_session.prompt_async(prompt, **kwargs)
    return func(result)
  except (KeyboardInterrupt, asyncio.CancelledError, EOFError):
    raise


async def load_background(status: str, job: Task):
  if job is None or job.done():
    return

  with console.status(status, spinner="dots", spinner_style="#89dceb"):
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


def env_bool(name: str, default: bool = False) -> bool:
  raw = os.getenv(name)
  if raw is None:
    return default
  return raw.strip().lower() in {"1", "true", "yes", "on", "y", "t"}


def env_int(name: str, default: int) -> int:
  try:
    return int(os.getenv(name, str(default)))
  except (TypeError, ValueError):
    return default


def env_float(name: str, default: float) -> float:
  try:
    return float(os.getenv(name, str(default)))
  except (TypeError, ValueError):
    return default


def get_usernames() -> list[str]:
  return [u for u in os.getenv("USERNAMES", "").split(",") if u]
