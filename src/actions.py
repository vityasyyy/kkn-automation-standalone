import asyncio
import getpass
import os

import httpx

from ui.prompt import get_entry_details_from_user, get_sub_entry_details_from_user, parse_selection
from ui.tables import print_assisted_program, print_program_details, print_program_title, print_unattended_program
from ui.tui import console, log
from utils.common import async_input, generate_random_points, load_background
from utils.kkn import KKN
from utils.simaster import Simaster


def _filter_unattended_program(data: dict | None) -> list[dict]:
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


async def show_all_program(kkn: KKN):
    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)
    print_program_details(kkn.main_program)
    print_assisted_program(kkn.assisted_program)


async def add_new_entry(kkn: KKN):
    """Option 3: Add a new logbook entry."""
    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

    print_program_title(kkn.main_program)
    p_ids = list(kkn.main_program.keys())

    choice = await async_input(
        f"Enter your choice [cyan]([#fab387]1[cyan]-[/]{len(p_ids)}[/])[/]",
        int,
        choices=[str(i + 1) for i in range(len(p_ids))],
    )

    p_id = p_ids[choice - 1]
    if data := get_entry_details_from_user(kkn.main_program[p_id]):
        await kkn.add_logbook_entry(p_id, data)
        kkn.loader = asyncio.create_task(kkn.update_logbook_entries(p_id))


async def add_new_sub_entry(kkn: KKN):
    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

    print_program_title(kkn.main_program)
    p_ids = list(kkn.main_program.keys())

    choice = await async_input(
        f"Enter your choice [cyan]([#fab387]1[cyan]-[/]{len(p_ids)}[/])[/]",
        int,
        choices=[str(i + 1) for i in range(len(p_ids))],
    )

    p_id = p_ids[choice - 1]
    if result := get_sub_entry_details_from_user(kkn.main_program[p_id]):
        await kkn.add_logbook_sub_entry(result[0], result[1])
        kkn.loader = asyncio.create_task(kkn.update_logbook_entries(p_id))


async def handle_unattended_entries(kkn: KKN):
    try:
        default_lat = float(os.getenv("KKN_LOCATION_LATITUDE", ""))
        default_long = float(os.getenv("KKN_LOCATION_LONGITUDE", ""))
        radius = int(os.getenv("KKN_LOCATION_RADIUS_METERS", ""))
    except (TypeError, ValueError):
        console.print(
            "\n[bold red]ERROR[/]: Either one of the following is not set correctly in .env file:"
            "\n[#fab387]1[/][cyan].[/] KKN_LOCATION_LATITUDE[cyan]:[/] [yellow]float[/]"
            "\n[#fab387]2[/][cyan].[/] KKN_LOCATION_LONGITUDE[cyan]:[/] [yellow]float[/]"
            "\n[#fab387]3[/][cyan].[/] KKN_LOCATION_RADIUS_METERS[cyan]:[/] [yellow]int[/]"
        )
        return

    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

    unattended_main = _filter_unattended_program(kkn.main_program)
    unattended_assisted = _filter_unattended_program(kkn.assisted_program)
    unattended = [*unattended_main, *unattended_assisted]

    if not unattended:
        console.print("[green]No unattended programs found![/]")
        return

    print_unattended_program(unattended)
    indices = await async_input('Enter indices to process (e.g "1 2 3" or "1-4")', parse_selection)

    unattended_len = len(unattended)
    final_indices = [i for i in indices if i <= unattended_len]

    id_to_update = set()
    for id in final_indices:
        item = unattended[id - 1]
        entry = item.get("sub_entry")
        console.print(f"Sending attendance for {entry}...")

        latitude, longitude = generate_random_points(default_lat, default_long, radius)
        if await kkn.post_logbook_attendance(item.get("url"), latitude, longitude):
            id_to_update.add(item.get("id"))

    kkn.loader = asyncio.create_task(
        kkn.get_logbook_entries(kkn.simaster_account, list(id_to_update), len(id_to_update) + 1)
    )


async def change_account() -> tuple[Simaster, httpx.AsyncClient, KKN] | None:
    new_username = input("Username: ")
    new_password = getpass.getpass()

    new_simaster = Simaster(new_username, new_password)
    if new_session := await new_simaster.login(verbose=True):
        new_kkn = KKN(new_session, new_simaster)
        return new_simaster, new_session, new_kkn

    return None
