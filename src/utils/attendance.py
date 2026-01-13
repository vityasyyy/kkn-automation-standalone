import os
import random
import sys
import time

import httpx
import requests
from rich.prompt import Confirm

from datatypes import RequestHeader
from ui.tui import console, log
from utils.common import generate_random_points
from utils.oauth import OAuthClient

CLIENT_ID = "e6abd4e380a5462e83873fe22ab8c219yVaU"
CLIENT_SECRET = "THFnhmQ6jckSWWzV6m9Mj78CexLCKjd009f4h9gQaIo8fUUULOhWP7DD"
REDIRECT_URI = "id.ac.ugm.student.vnext.simaster://oauth2"
BASE_URL = "https://api.simaster.ugm.ac.id/vnext/v1/checkpoint"


def checkin(username: str, access_token: str):
    header: RequestHeader = {
        "Content-type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    client = httpx.Client()
    with console.status(f"[blue]Checking in for [cyan]{username}[/]...", spinner="dots") as status:
        try:
            latitude = float(os.getenv("KKN_LOCATION_LATITUDE", "0.0"))
            longitude = float(os.getenv("KKN_LOCATION_LONGITUDE", "0.0"))
            radius = int(os.getenv("KKN_LOCATION_RADIUS_METERS", "0"))
            qr_value = int(os.getenv("QR_CODE_VALUE", "0"))
        except (TypeError, ValueError):
            console.print(
                "\n[bold red]ERROR[/]: Either one of the following is not set correctly in .env file:"
                "\n[#fab387]1[/][cyan].[/] KKN_LOCATION_LATITUDE[cyan]:[/] [yellow]float[/]"
                "\n[#fab387]2[/][cyan].[/] KKN_LOCATION_LONGITUDE[cyan]:[/] [yellow]float[/]"
                "\n[#fab387]3[/][cyan].[/] KKN_LOCATION_RADIUS_METERS[cyan]:[/] [yellow]int[/]"
                "\n[#fab387]4[/][cyan].[/] QR_CODE_VALUE[cyan]:[/] [yellow]int[/]"
            )
            sys.exit(2)

        random_lat, random_long = generate_random_points(latitude, longitude, radius)
        status.update(f"[blue]Generated random point: [yellow]([#fab387]{random_lat}[cyan],[/] {random_long}[/])[/]")

        params = {"lat": random_lat, "long": random_long}
        full_url = f"{BASE_URL}/checkin/{username}/{qr_value}"

        try:
            status.update("[blue]Hitting the endpoint....")
            resp = client.post(full_url, params=params, headers=header)
        except Exception as e:
            log.error(f"Request Error: {e}")

    if resp.status_code == 200:
        console.print(f"\n[bold green]SUCCESS[/]: Succesfully checked-in as [bold cyan]{username}[/]!")
    else:
        console.print(f"\n[bold red]FAILED[/]: Status Code {resp.status_code}")


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


def handle_checkin(username: str, password: str):
    throttle = Confirm.ask("Throttle in between check-in?", default=False)
    shuffle = Confirm.ask("Shuffle the check-in order?", default=True)

    oauth_client = OAuthClient(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
    login_result = oauth_client.complete_oauth_flow(username, password)

    if not login_result["success"]:
        console.print(f"[bold red]ERROR[/]: ({login_result['step']}) {login_result['error']}")
        return

    access_token = login_result["access_token"]
    console.print("Login successful!")
    assert type(access_token) is str

    usernames = os.getenv("USERNAMES", "").split(",")
    if shuffle:
        random.shuffle(usernames)

    for username in usernames:
        print(f"Checking in for {username}")
        checkin(username, access_token)

        if throttle:
            time.sleep(random.uniform(0.0, 5.0))


def handle_check_status(username: str, password: str):
    oauth_client = OAuthClient(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
    login_result = oauth_client.complete_oauth_flow(username, password)

    if not login_result["success"]:
        console.print(f"[bold red]ERROR ({login_result['step']})[/]: {login_result['error']}")
        return

    access_token = login_result["access_token"]
    print("Login successful!")
    assert type(access_token) is str

    usernames = os.getenv("USERNAMES", "").split(",")
    for username in usernames:
        print(f"Checking status for {username}")
        data = check_active_session(username, access_token)

        if not data:
            print(f"User {username} haven't checked-in")
            continue

        print(f"ID: {data['id']}\nLocation: {data['location']}\nCheck-in time: {data['time']}")
