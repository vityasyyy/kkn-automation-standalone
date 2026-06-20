import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from datatypes import CheckInPayload
from utils.logger import get_logger

log = get_logger("locations")


@dataclass
class Location:
  name: str
  qr_value: int
  latitude: float
  longitude: float
  radius: int


def _load_locations_yaml(path: str) -> dict:
  with open(path, encoding="utf-8") as f:
    return yaml.safe_load(f) or {}


def _load_locations_env() -> dict:
  """Load from LOCATIONS env (JSON string) as a fallback when no yaml file exists."""
  raw = os.getenv("LOCATIONS")
  if not raw:
    return {}
  try:
    return json.loads(raw)
  except json.JSONDecodeError as e:
    log.error("LOCATIONS env is not valid JSON: %s", e)
    return {}


def load_location_config() -> tuple[dict[str, Location], dict[str, str], str | None]:
  """Returns (locations, user_locations, default_location_name)."""
  yaml_path = os.getenv("LOCATIONS_FILE", "locations.yaml")
  path = Path(yaml_path)

  if path.exists():
    log.info("Loading locations from %s", path)
    data = _load_locations_yaml(str(path))
  else:
    data = _load_locations_env()

  if not data:
    return {}, {}, None

  raw_locations = data.get("locations", {})
  locations: dict[str, Location] = {}
  for name, loc in raw_locations.items():
    try:
      locations[name] = Location(
        name=name,
        qr_value=int(loc["qr_value"]),
        latitude=float(loc["latitude"]),
        longitude=float(loc["longitude"]),
        radius=int(loc.get("radius", 100)),
      )
    except (KeyError, TypeError, ValueError) as e:
      log.error("Invalid location '%s': %s", name, e)

  user_locations = data.get("user_locations", {})
  default_location = data.get("default_location")

  return locations, user_locations, default_location


def resolve_location(
  username: str,
  locations: dict[str, Location],
  user_locations: dict[str, str],
  default_location: str | None,
) -> Location | None:
  """Resolve which Location a user should check into. Returns None if none configured."""
  if not locations:
    return None

  loc_name = user_locations.get(username, default_location)
  if not loc_name:
    return None
  return locations.get(loc_name)


def build_payload_for_location(loc: Location, access_token: str) -> CheckInPayload:
  return CheckInPayload(
    access_token=access_token,
    qr_value=loc.qr_value,
    latitude=loc.latitude,
    longitude=loc.longitude,
    radius=loc.radius,
  )
