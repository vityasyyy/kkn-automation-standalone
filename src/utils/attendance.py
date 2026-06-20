import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import httpx
import requests
from rich import box
from rich.prompt import Confirm, Prompt
from rich.table import Table

from datatypes import CheckInPayload, RequestHeader
from ui.tui import console, print_log
from utils.common import env_bool, env_float, env_int, generate_random_points, get_usernames
from utils.locations import Location, build_payload_for_location, load_location_config, resolve_location
from utils.logger import get_logger
from utils.oauth import OAuthClient

log = get_logger("attendance")

CLIENT_ID = "e6abd4e380a5462e83873fe22ab8c219yVaU"
CLIENT_SECRET = "THFnhmQ6jckSWWzV6m9Mj78CexLCKjd009f4h9gQaIo8fUUULOhWP7DD"
REDIRECT_URI = "id.ac.ugm.student.vnext.simaster://oauth2"
BASE_URL = "https://api.simaster.ugm.ac.id/vnext/v1/checkpoint"

RESULT_FILE = Path(os.getenv("REPORT_DIR", "reports")) / "result.json"


def check_in(username: str, data: CheckInPayload):
  header: RequestHeader = {
    "Content-type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {data.access_token}",
  }

  client = httpx.Client()
  with console.status(
    f"[blue]Checking in for [#89dceb]{username}[/]...", spinner="dots", spinner_style="#89dceb"
  ) as status:
    random_lat, random_long = generate_random_points(data.latitude, data.longitude, data.radius)
    time.sleep(0.4)
    status.update(f"[blue]Generated random point: [yellow]([#fab387]{random_lat}[#89dceb],[/] {random_long}[/])[/]")
    time.sleep(0.4)

    params = {"lat": random_lat, "long": random_long}
    full_url = f"{BASE_URL}/checkin/{username}/{data.qr_value}"

    try:
      status.update("[blue]Hitting the endpoint....")
      resp = client.post(full_url, params=params, headers=header)
    except Exception as e:
      print_log(f"Request Error: {e}", "ERROR")
      log.error("Check-in request failed for %s: %s", username, e)
      return False

  if resp.status_code == 200:
    print_log(f"Succesfully checked-in as [bold #89dceb]{username}[/]!", "SUCCESS")
    log.info("Checked in successfully as %s", username)
    return True
  else:
    print_log(f"Status Code {resp.status_code}", "ERROR")
    log.error("Check-in for %s returned status %s: %s", username, resp.status_code, resp.text[:200])
    return False


def check_active_session(username: str, access_token: str):
  header: RequestHeader = {
    "Content-type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {access_token}",
  }

  url = f"{BASE_URL}/get_active_session/{username}"
  resp = requests.get(url, headers=header)

  if resp.status_code == 200:
    data = resp.json()
    return {
      "id": data["check_point_log_id"],
      "location": data["check_point_nama"],
      "time": data["check_point_log_check_in"],
    }

  return None


def _is_already_checked_in(username: str, access_token: str) -> bool:
  """Idempotency check: skip check-in if the user has an active session today."""
  try:
    return check_active_session(username, access_token) is not None
  except Exception as e:
    log.warning("Idempotency check failed for %s: %s — proceeding with check-in", username, e)
    return False


def _write_result_json(results: list[dict]):
  try:
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
      json.dump({"generated_at": datetime.now().isoformat(), "results": results}, f, indent=2, ensure_ascii=False)
    log.info("result.json written to %s (%d users)", RESULT_FILE, len(results))
  except Exception as e:
    log.error("Failed to write result.json: %s", e)


def _print_summary(results: list[dict]):
  table = Table(box=box.ROUNDED, title="Attendance Run Summary")
  table.add_column("User")
  table.add_column("Location")
  table.add_column("Status")
  table.add_column("Detail")

  for r in results:
    status = r["status"]
    if status == "checked_in":
      icon = "[green]✓ checked_in[/]"
    elif status == "skipped":
      icon = "[yellow]– skipped[/]"
    elif status == "would_check_in":
      icon = "[blue]? would_check_in[/]"
    else:
      icon = "[red]✗ failed[/]"
    table.add_row(r["username"], r.get("location", "—"), icon, r.get("detail", ""))

  console.print(table)


def _resolve_payload(
  user: str,
  default_payload: CheckInPayload,
  locations: dict[str, Location],
  user_locations: dict[str, str],
  default_location: str | None,
) -> tuple[CheckInPayload, str]:
  """Return (payload, location_name) for a user."""
  loc = resolve_location(user, locations, user_locations, default_location)
  if loc:
    return build_payload_for_location(loc, default_payload.access_token), loc.name
  return default_payload, "default"


def _handle_attendance_env(
  data: CheckInPayload,
  func: Callable,
  headless: bool = False,
  idempotent: bool = True,
  dry_run: bool = False,
  verify: bool = False,
):
  if headless:
    throttle = env_bool("THROTTLE", default=False)
    shuffle = env_bool("SHUFFLE", default=True)
  else:
    throttle = Confirm.ask("Throttle in between check-in?", default=False)
    shuffle = Confirm.ask("Shuffle the check-in order?", default=True)

  usernames = get_usernames()
  if shuffle:
    random.shuffle(usernames)

  if not usernames:
    print_log("No usernames configured in USERNAMES env var", "ERROR")
    return False, []

  locations, user_locations, default_location = load_location_config()

  length = len(usernames)
  all_ok = True
  results = []

  for idx, user in enumerate(usernames, 1):
    payload, loc_name = _resolve_payload(user, data, locations, user_locations, default_location)

    if idempotent and _is_already_checked_in(user, data.access_token):
      print_log(f"[yellow]{user} already has an active session — skipping[/]")
      log.info("Skipped %s (already checked in)", user)
      results.append(
        {
          "username": user,
          "location": loc_name,
          "status": "skipped",
          "attempts": 0,
          "detail": "already has an active session",
        }
      )
      continue

    if dry_run:
      print_log(f"[blue]DRY RUN: would check in {user}@{loc_name}[/]")
      results.append(
        {
          "username": user,
          "location": loc_name,
          "status": "would_check_in",
          "attempts": 0,
          "detail": "dry run — no POST sent",
        }
      )
      continue

    print(f"Checking in for {user}@{loc_name}")
    ok, attempts = _retry_check_in(user, payload, return_attempts=True)
    result = {
      "username": user,
      "location": loc_name,
      "status": "checked_in" if ok else "failed",
      "attempts": attempts,
      "detail": "" if ok else f"failed after {attempts} attempts",
    }

    if verify:
      session = check_active_session(user, data.access_token)
      if session:
        result["verified"] = True
        result["checked_in_at"] = session["time"]
        result["verified_location"] = session["location"]
      else:
        result["verified"] = False
        result["checked_in_at"] = None
        log.warning("Verify: %s has no active session after check-in", user)

    results.append(result)
    if not ok:
      all_ok = False

    if throttle and idx < length:
      time.sleep(random.uniform(0.0, 5.0))

  _print_summary(results)
  _write_result_json(results)
  return all_ok, results


def _handle_attendance_manual(data: CheckInPayload, func: Callable):
  while True:
    table = Table(box=box.ROUNDED, show_header=False)
    table.add_row("1", "Latitude", str(data.latitude), "Latitude of your KKN location")
    table.add_row("2", "Longitude", str(data.longitude), "Longitude of your KKN location")
    table.add_row("3", "Radius", str(data.radius), "Radius of the randomly generated location")
    table.add_row("4", "QR Value", str(data.qr_value), "QR Value of the checkpoint")
    console.print(table)

    change = Confirm.ask("Do you want to change the location?", default=False)

    if change:
      data.latitude = float(Prompt.ask("Enter new latitude value", default=data.latitude))
      data.longitude = float(Prompt.ask("Enter new longitude value", default=data.longitude))
      data.radius = int(Prompt.ask("Enter new radius value", default=data.radius))
      data.qr_value = int(Prompt.ask("Enter new QR code value", default=data.qr_value))

    username = Prompt.ask("Enter username to check in")
    _retry_check_in(username, data)

    if not Confirm.ask("Input another username?", default=False):
      break

  return True, []


def _retry_check_in(
  username: str,
  data: CheckInPayload,
  max_retries: int | None = None,
  backoff: float | None = None,
  return_attempts: bool = False,
) -> bool | tuple[bool, int]:
  if max_retries is None:
    max_retries = env_int("MAX_RETRIES", default=3)
  if backoff is None:
    backoff = env_float("RETRY_BACKOFF", default=2.0)

  for attempt in range(1, max_retries + 1):
    if check_in(username, data):
      if return_attempts:
        return True, attempt
      return True
    if attempt < max_retries:
      delay = backoff**attempt
      print_log(f"Check-in attempt {attempt}/{max_retries} failed, retrying in {delay:.1f}s...", "WARN")
      time.sleep(delay)
  print_log(f"Check-in for {username} failed after {max_retries} attempts", "ERROR")
  if return_attempts:
    return False, max_retries
  return False


def handle_attendance(
  username: str, password: str, headless: bool = False, dry_run: bool = False, verify: bool = False
) -> bool:
  try:
    latitude = float(os.getenv("KKN_LOCATION_LATITUDE", ""))
    longitude = float(os.getenv("KKN_LOCATION_LONGITUDE", ""))
    radius = int(os.getenv("KKN_LOCATION_RADIUS_METERS", "100"))
    qr_value = int(os.getenv("QR_CODE_VALUE", ""))
  except (TypeError, ValueError):
    print_log(
      "Either one of the following is not set correctly in .env file:"
      "\n[#fab387]1[/][#89dceb].[white] KKN_LOCATION_LATITUDE[/]:[/] [yellow]float[/]"
      "\n[#fab387]2[/][#89dceb].[white] KKN_LOCATION_LONGITUDE[/]:[/] [yellow]float[/]"
      "\n[#fab387]3[/][#89dceb].[white] QR_CODE_VALUE[/]:[/] [yellow]int[/]"
    )
    return False

  oauth_client = OAuthClient(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
  login_result = oauth_client.complete_oauth_flow(username, password)

  if not login_result["success"]:
    print_log(f"({login_result['step']}) {login_result['error']}", "ERROR")
    return False

  if not (access_token := login_result["access_token"]):
    print_log("No access token found!", "ERROR")
    return False

  print_log("Successfully logged in via [#89dceb]oauth.ugm.ac.id[/]!", "SUCCESS")
  log.info("OAuth login successful for %s", username)

  data = CheckInPayload(
    access_token=access_token,
    qr_value=qr_value,
    latitude=latitude,
    longitude=longitude,
    radius=radius,
  )

  func = check_in

  if headless:
    is_manual = False
    idempotent = env_bool("IDEMPOTENT", default=True)
  else:
    is_manual = Confirm.ask("Do you want to input usernames manually?", default=False)
    idempotent = env_bool("IDEMPOTENT", default=True)

  if is_manual:
    ok, _ = _handle_attendance_manual(data, func)
    return ok
  else:
    ok, _ = _handle_attendance_env(data, func, headless=headless, idempotent=idempotent, dry_run=dry_run, verify=verify)
    return ok


def handle_check_status(username: str, password: str) -> bool:
  oauth_client = OAuthClient(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
  login_result = oauth_client.complete_oauth_flow(username, password)

  if not login_result["success"]:
    print_log(f"({login_result['step']})[/]: {login_result['error']}", "ERROR")
    return False

  access_token = login_result["access_token"]
  print("Login successful!")
  log.info("OAuth login successful for status check")
  assert type(access_token) is str

  usernames = get_usernames()
  if not usernames:
    print_log("No usernames configured in USERNAMES env var", "ERROR")
    return False

  for user in usernames:
    print(f"Checking status for {user}")
    data = check_active_session(user, access_token)

    if not data:
      print(f"User {user} haven't checked-in")
      continue

    print(f"ID: {data['id']}\nLocation: {data['location']}\nCheck-in time: {data['time']}")

  return True
