import asyncio
import os

import httpx
from prompt_toolkit import HTML

from ui.prompt import get_entry_details_from_user, get_sub_entry_details_from_user, parse_selection
from ui.tables import print_assisted_program, print_program_details, print_program_title, print_unattended_program
from ui.tui import console, print_log
from utils.common import async_input, generate_random_points, load_background
from utils.kkn import KKN
from utils.simaster import Simaster


def _filter_unattended_program(data: dict | None, source: str = "assisted") -> list[dict]:
  if not data:
    print_log(f"No {source} program found", "ERROR")
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
  await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

  print_program_title(kkn.main_program)
  p_ids = list(kkn.main_program.keys())

  choice = await async_input(
    HTML(
      f'Enter your choice <delim fg="#89dceb">(<num fg="#fab387">1<dash fg="#89dceb">-</dash>{len(p_ids)}</num>) '
      f'<choice fg="ansimagenta">[{"/".join(str(i + 1) for i in range(len(p_ids)))}]</choice>: </delim>'
    ),
    int,
  )

  p_id = p_ids[choice - 1]
  if data := get_entry_details_from_user(kkn.main_program[p_id]):
    await kkn.add_logbook_entry(p_id, data)
    kkn.loader = asyncio.create_task(kkn.update_logbook_entries(programs=[p_id]))


async def add_new_sub_entry(kkn: KKN):
  await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

  print_program_title(kkn.main_program)
  p_ids = list(kkn.main_program.keys())

  choice = await async_input(
    HTML(
      f'Enter your choice <delim fg="#89dceb">(<num fg="#fab387">1<dash fg="#89dceb">-</dash>{len(p_ids)}</num>) '
      f'<choice fg="ansimagenta">[{"/".join(str(i + 1) for i in range(len(p_ids)))}]</choice>: </delim>'
    ),
    int,
  )

  p_id = p_ids[choice - 1]
  try:
    if result := get_sub_entry_details_from_user(kkn.main_program[p_id]):
      await kkn.add_logbook_sub_entry(result[0], result[1])
      kkn.loader = asyncio.create_task(kkn.update_logbook_entries(programs=[p_id], pool_size=2))
  except KeyboardInterrupt:
    return


async def handle_unattended_entries(kkn: KKN):
  try:
    default_lat = float(os.getenv("KKN_LOCATION_LATITUDE", ""))
    default_long = float(os.getenv("KKN_LOCATION_LONGITUDE", ""))
    radius = int(os.getenv("KKN_LOCATION_RADIUS_METERS", ""))
  except (TypeError, ValueError):
    print_log(
      "Either one of the following is not set correctly in .env file:"
      "\n[#fab387]1[/][#89dceb].[white] KKN_LOCATION_LATITUDE[/]:[/] [yellow]float[/]"
      "\n[#fab387]2[/][#89dceb].[white] KKN_LOCATION_LONGITUDE[/]:[/] [yellow]float[/]"
      "\n[#fab387]3[/][#89dceb].[white] QR_CODE_VALUE[/]:[/] [yellow]int[/]"
    )
    return

  await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

  unattended_main = _filter_unattended_program(kkn.main_program, source="main")
  unattended_assisted = _filter_unattended_program(kkn.assisted_program, source="assisted")
  unattended = [*unattended_main, *unattended_assisted]

  if not unattended:
    print_log("No unattended programs found!")
    return

  print_unattended_program(unattended)
  indices = await async_input(
    HTML(
      'Enter indices to process <delim fg="#89dceb">(<num fg="#a6e3a1">"1 2 3"<dash fg="#89dceb"> or </dash>"1-4"</num>): </delim>'
    ),
    parse_selection,
  )

  unattended_len = len(unattended)
  final_indices = [i for i in indices if i <= unattended_len]

  id_to_update = set()
  update_assisted = False
  for id in final_indices:
    item = unattended[id - 1]
    entry = item.get("sub_entry")
    console.print(f"Sending attendance for {entry}...")

    latitude, longitude = generate_random_points(default_lat, default_long, radius)
    if await kkn.post_logbook_attendance(item.get("url"), latitude, longitude):
      if item.get("type") == "bantu":
        update_assisted = True
      else:
        id_to_update.add(item.get("id"))

  kkn.loader = asyncio.create_task(
    kkn.update_logbook_entries(kkn.simaster_account, list(id_to_update), len(id_to_update) + 1, update_assisted)
  )


async def change_account() -> tuple[Simaster, httpx.AsyncClient, KKN] | None:
  new_username = await async_input(HTML('Username<delim fg="#89dceb">:</delim> '))
  new_password = await async_input(HTML('Password<delim fg="#89dceb">:</delim> '), is_password=True)

  new_simaster = Simaster(new_username, new_password)
  if new_session := await new_simaster.login(verbose=True):
    new_kkn = KKN(new_session, new_simaster)
    return new_simaster, new_session, new_kkn

  return None
