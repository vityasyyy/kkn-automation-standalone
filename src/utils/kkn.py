import asyncio
import itertools
import json
import re
from asyncio.tasks import Task

import httpx
from selectolax.parser import HTMLParser

from datatypes import AssistedProgram, EntryData, LogEntryPayload, RPPData, SubEntryData
from ui.tui import print_log
from utils.simaster import BASE_URL, Simaster

KKN_MAIN_URL = f"{BASE_URL}/kkn/kkn"
KKN_ATTENDANCE_URL = f"{KKN_MAIN_URL}/logbook_kegiatan_presensi"

DATA_URL_PATTERN = re.compile(r"'url'\s*:\s*[\"'](https://simaster\.ugm\.ac\.id/kkn/kkn/logbook_program_data/[^\"']+)")
LOGBOOK_LINK_PATTERN = re.compile(
  r"<a href=['\"]([^'\"]*logbook_program[^'\"]*)['\"][^>]*>.*?Pelaksanaan Program.*?</a>", re.IGNORECASE | re.DOTALL
)
RPP_LINK_PATTERN = re.compile(r"href='([^']+logbook_program_rpp[^']+)'")
MAIN_SUB_ENTRY_PATTERN = re.compile(
  r"^(?P<title>.*?)\s+"
  r"\((?P<datetime>.*? \d{2}:\d{2}.*?)\)\s+"
  r"\[(?P<duration>.*?)\]"
)
ASSISTED_SUB_ENTRY_PATTERN = re.compile(r"^(?P<title>.*?)\s+\((?P<datetime>.*?WIB)\)\s+\[(?P<duration>.*?)\]")


class KKN:
  def __init__(self, client: httpx.AsyncClient, simaster_acc: Simaster, autostart: bool = True):
    self.client: httpx.AsyncClient = client
    self.simaster_account: Simaster = simaster_acc
    self.loader: Task | None = None
    self.main_program: dict[str, RPPData] = {}
    self.assisted_program: dict[str, list[AssistedProgram]] = {}
    if autostart:
      self.start()

  def start(self):
    if self.loader is None or self.loader.done():
      self.loader = asyncio.create_task(self._load_all(self.simaster_account))

  async def _load_all(self, auth_provider: Simaster | None = None):
    self.main_program: dict[str, RPPData] = await self._get_kkn_program()
    p_id = next(iter(self.main_program)) if self.main_program else ""
    pool_size = len(self.main_program) + 1

    tasks = []
    tasks.append(self._get_logbook_entries(auth_provider, pool_size=pool_size))
    tasks.append(self._get_assisted_program(p_id))

    results = await asyncio.gather(*tasks)
    self.assisted_program = results[1]

  async def _get_kkn_program(self) -> dict[str, RPPData] | None:
    try:
      resp = await self.client.get(KKN_MAIN_URL, follow_redirects=True)
      resp.raise_for_status()

      if not (match := LOGBOOK_LINK_PATTERN.search(resp.text)):
        print_log("Couldn't find 'Pelaksanaan Program' link on the KKN main page")
        return None

      logbook_url: str = match.group(1)
      if not logbook_url.startswith("http"):
        logbook_url = f"{BASE_URL}{logbook_url.lstrip('/')}"

      resp = await self.client.get(logbook_url, follow_redirects=True)
      resp.raise_for_status()

      if not (cookie := self.client.cookies.get("simasterUGM_cookie", None)):
        print_log("Could not find 'simasterUGM_cookie' in the session after visiting the logbook page.")
        return None

      if not (match := DATA_URL_PATTERN.search(resp.text)):
        print_log("Could not find data URL in logbook page's JavaScript.")
        return None

      data_url = match.group(1)

      headers = {"X-Requested-With": "XMLHttpRequest"}
      # fmt: off
      post_data = {
        "draw": "1", "start": "0", "length": "25", "search[value]": "", "search[regex]": "false", "dt": "{}", "simasterUGM_token": cookie,
        "columns[0][data]": "no",                        "columns[0][name]": "", "columns[0][searchable]": "false", "columns[0][orderable]": "false", "columns[0][search][value]": "", "columns[0][search][regex]": "false",
        "columns[1][data]": "program_nama",              "columns[1][name]": "", "columns[1][searchable]": "true",  "columns[1][orderable]": "true",  "columns[1][search][value]": "", "columns[1][search][regex]": "false",
        "columns[2][data]": "program_mhs_judul",         "columns[2][name]": "", "columns[2][searchable]": "true",  "columns[2][orderable]": "true",  "columns[2][search][value]": "", "columns[2][search][regex]": "false",
        "columns[3][data]": "program_jenis_id",          "columns[3][name]": "", "columns[3][searchable]": "true",  "columns[3][orderable]": "true",  "columns[3][search][value]": "", "columns[3][search][regex]": "false",
        "columns[4][data]": "program_mhs_keberlanjutan", "columns[4][name]": "", "columns[4][searchable]": "true",  "columns[4][orderable]": "true",  "columns[4][search][value]": "", "columns[4][search][regex]": "false",
        "columns[5][data]": "status_nama",               "columns[5][name]": "", "columns[5][searchable]": "true",  "columns[5][orderable]": "true",  "columns[5][search][value]": "", "columns[5][search][regex]": "false",
        "columns[6][data]": "action",                    "columns[6][name]": "", "columns[6][searchable]": "false", "columns[6][orderable]": "false", "columns[6][search][value]": "", "columns[6][search][regex]": "false",
      }
      # fmt: on

      resp = await self.client.post(data_url, data=post_data, headers=headers, follow_redirects=True)
      resp.raise_for_status()

      programs = resp.json()

      if new_token := programs.get("csrf_value"):
        self.client.cookies.set("simasterUGM_cookie", new_token, "simaster.ugm.ac.id")

      programs_list = programs.get("data", [])

      data: dict[str, RPPData] = {}
      for p in programs_list:
        p_id = p.get("program_mhs_id", "")
        title = p.get("program_mhs_judul", "")

        if action_match := RPP_LINK_PATTERN.search(p.get("action", "")):
          data[p_id]: RPPData = {"title": title, "action": action_match.group(1)}
        else:
          print_log(f"Could not find RPP URL for program {p_id}")

      return data

    except httpx.HTTPStatusError as e:
      print_log(f"HTTP error occurred: {e.response.status_code} - {e}", "ERROR")
      return None
    except httpx.RequestError as e:
      print_log(f"An error occurred when fetching programs: {repr(e)}", "ERROR")
      return None
    except Exception as e:
      print_log(f"An unexpected error occurred in _get_kkn_program: {e}", "ERROR")
      return None

  # HACK:
  # - SIMASTER Seems to have some sort of server-side lock when we send them a GET request to fetch the
  #   RPP. This means doing the fetching using only one account will take 5 lock and unlock sequence.
  # - Since 1 request takes around 2.5 seconds (SIMASTER sends back a 96kb HTML page bruh), it will take
  #   around 12 seconds to get all the RPP entries.
  # - As a workaround, we log in n amount of times with n being the pool_size to get n different account
  #   cookies and assign them to each program to avoid the lock-unlock chain.
  async def _get_logbook_entries(
    self, auth_provider: Simaster | None = None, programs: list[str] | None = None, pool_size: int = 6
  ):
    if not self.main_program:
      print_log("No Programs found")
      return

    temp_pool = []
    if auth_provider:
      login_task = [auth_provider.login(reuse_session=False) for _ in range(pool_size)]
      temp_pool = await asyncio.gather(*login_task)
      temp_pool = [c for c in temp_pool if c is not None]

    active_clients = temp_pool if temp_pool else [self.client]
    client_cycle = itertools.cycle(active_clients)

    tasks = []
    program_list = programs or self.main_program.keys()
    for p_id in program_list:
      worker = next(client_cycle)
      tasks.append(self.get_logbook_entries_by_id(p_id, worker))

    results = await asyncio.gather(*tasks)

    if temp_pool:
      await asyncio.gather(*[c.aclose() for c in temp_pool])

    for p_id, entries in zip(program_list, results):
      self.main_program[p_id]["entries"] = entries

  async def update_logbook_entries(
    self,
    auth_provider: Simaster | None = None,
    programs: list[str] | None = None,
    pool_size: int = 6,
    update_assisted: bool = False,
  ):
    tasks = []
    tasks.append(self._get_logbook_entries(auth_provider, programs=programs, pool_size=pool_size))
    if update_assisted:
      if not (p_id := programs[-1] if programs else (next(iter(self.main_program)) if self.main_program else "")):
        print_log("update_logbook_entries: No Programs Found!", "ERROR")
        return

      tasks.append(self._get_assisted_program(p_id))

    results = await asyncio.gather(*tasks)

    if update_assisted:
      self.assisted_program = results[1]

  async def get_logbook_entries_by_id(
    self, program_id: str, client: httpx.AsyncClient | None = None
  ) -> list[EntryData] | None:
    if not self.main_program or not (target := self.main_program.get(program_id)):
      return None

    use_client = client if client else self.client
    url = target["action"]

    try:
      resp = await use_client.get(url)
      resp.raise_for_status()

      tree = HTMLParser(resp.content)
      rows = tree.css("table#datatables2 tbody tr")

      entries = []
      current_entry = None

      for row in rows:
        if not (cols := row.css("td")):
          continue

        first_col_text = cols[0].text(strip=True)

        if len(cols) == 5 and first_col_text:
          kegiatan_url = None
          if link_node := cols[4].css_first("a[href*='logbook_kegiatan']"):
            kegiatan_url = link_node.attributes.get("href")

          current_entry: EntryData = {
            "entry_index": int(cols[0].text(strip=True)),
            "activity_url": str(kegiatan_url),
            "title": cols[1].text(strip=True),
            "date": cols[2].text(strip=True),
            "location": cols[3].text(strip=True),
            "sub_entries": [],
            "attendance_status": "Belum Presensi",
          }

          entries.append(current_entry)
        elif current_entry is not None and not first_col_text and len(cols) >= 2:
          content_node = cols[1]
          status_node = content_node.css_first("span.label")

          attendance_link = None
          if presensi_node := content_node.css_first("span.pull-right a[ajaxify]"):
            attendance_link = presensi_node.attributes.get("ajaxify")

          full_text = content_node.text().replace("\n", "").strip()
          if status_text := status_node.text(strip=True) if status_node else "Belum Presensi":
            full_text = full_text.replace(status_text, "").strip()

          is_attended = "Sudah Presensi" in status_text

          match = MAIN_SUB_ENTRY_PATTERN.search(full_text)

          sub_data: SubEntryData = {
            "title": match.group("title").strip() if match else full_text,
            "date": match.group("datetime").strip() if match else "N/A",
            "duration": match.group("duration").strip() if match else "N/A",
            "status": status_text,
            "is_attended": is_attended,
            "attendance_link": attendance_link,
          }

          current_entry["sub_entries"].append(sub_data)

      for entry in entries:
        if not entry["sub_entries"]:
          entry["attendance_status"] = "Belum Presensi"
          continue

        statuses = sorted([sub["status"] for sub in entry["sub_entries"]])
        entry["attendance_status"] = statuses[0]

      return entries

    except httpx.RequestError as e:
      print_log(f"An error occurred while fetching logbook entries: {repr(e)}")
      return None
    except Exception as e:
      print_log(f"An unexpected error occurred in get_logbook_entries_by_id: {e}")
      return None

  async def _get_assisted_program(self, program_id: str) -> dict[str, list[AssistedProgram]] | None:
    if not self.main_program or not (target := self.main_program.get(program_id)):
      return None

    url = target["action"]

    try:
      resp = await self.client.get(url, follow_redirects=True)
      resp.raise_for_status()

      tree = HTMLParser(resp.content)
      assisted_panel = None
      for panel in tree.css("div.panel"):
        heading = panel.css_first("div.panel-heading span.panel-title")
        if heading and "Program Bantu" in heading.text():
          assisted_panel = panel
          break

      if not assisted_panel:
        print_log("Could not find 'Program Bantu' panel on the RPP page.")
        return None

      rows = assisted_panel.css("div.table-primary table tbody tr")
      pic_entries = {}

      current_pic = ""
      for row in rows:
        if not (cols := row.css("td")):
          continue

        first_col_text = cols[0].text(strip=True)

        if len(cols) == 6 and first_col_text.isdigit():
          pic = cols[3].text(strip=True)
          current_pic = pic
          pic_entries[pic] = pic_entries.get(pic, [])

          pic_data: AssistedProgram = {
            "title": cols[1].text(strip=True),
            "date": cols[4].text(strip=True),
            "location": cols[5].text(strip=True),
            "sub_entries": [],
          }
          pic_entries[pic].append(pic_data)
        elif len(cols) == 2 and not first_col_text and pic_entries:
          content_node = cols[1]
          status_node = content_node.css_first("span.label")

          attendance_link = None
          if presensi_node := content_node.css_first("span.pull-right a[ajaxify]"):
            attendance_link = presensi_node.attributes.get("ajaxify")

          full_text = content_node.text().replace("\n", "").strip()
          if status_text := status_node.text(strip=True) if status_node else "Belum Presensi":
            full_text = full_text.replace(status_text, "").strip()

          is_attended = "Sudah Presensi" in status_text

          match = ASSISTED_SUB_ENTRY_PATTERN.search(full_text)
          sub_data: SubEntryData = {
            "title": match.group("title").strip() if match else full_text,
            "date": match.group("datetime").strip() if match else "N/A",
            "duration": match.group("duration").strip() if match else "N/A",
            "status": status_text,
            "is_attended": is_attended,
            "attendance_link": attendance_link,
          }

          pic_entries[current_pic][-1]["sub_entries"].append(sub_data)

      return pic_entries
    except httpx.RequestError as e:
      print_log(f"An error occurred while fetching assisted programs: {repr(e)}", "ERROR")
      return None
    except Exception as e:
      print_log(f"An unexpected error occurred in get_assisted_program: {e}", "ERROR")
      return None

  async def add_logbook_entry(self, program_id: str, data: LogEntryPayload):
    if not self.main_program or not (target := self.main_program.get(program_id)):
      return None

    url = target["action"]

    try:
      resp = await self.client.get(url, follow_redirects=True)
      resp.raise_for_status()

      tree = HTMLParser(resp.content)
      if not (add_link_node := tree.css_first("a[title='Tambah']")):
        print_log("Could not find 'Tambah' link on the RPP page.")
        return False

      add_page_url = add_link_node.attributes.get("href")
      assert add_page_url is not None
      resp = await self.client.get(add_page_url, follow_redirects=True)
      resp.raise_for_status()

      tree = HTMLParser(resp.content)
      if not (form := tree.css_first("form#form-usulan-program")):
        print_log("Could not find the add form on the page.")
        return False

      action_url = form.attributes.get("action")

      form_data = {}
      for inp in form.css("input[type='hidden']"):
        name = inp.attributes.get("name")
        value = inp.attributes.get("value")
        if name:
          form_data[name] = value

      form_data["dParam[judul]"] = data["title"]
      form_data["dParam[pelaksanaan]"] = data["date"]
      form_data["dParam[lokasi]"] = f"{data['latitude']}, {data['longitude']}"

      assert action_url is not None
      resp = await self.client.post(action_url, data=form_data, follow_redirects=True)
      resp.raise_for_status()

      resp_json = resp.json()
      if resp_json.get("status") == "success":
        print_log(f"Added logbook entry: {resp_json.get('msg')}", "SUCCESS")
        return True
      else:
        print_log(f"Failed to add logbook entry: {resp_json.get('msg')}", "ERROR")
        return False

    except httpx.RequestError as e:
      print_log(f"Network error occurred: {e}", "ERROR")
      return False
    except Exception as e:
      print_log(f"An unexpected error occurred in add_kkn_logbook_entry: {e}", "ERROR")
      return False

  # WARN:
  # Currently this function can only handle 1 source of fund, If your program have more than 1 fund source,
  # just edit it from SIMASTER
  async def add_logbook_sub_entry(self, kegiatan_url: str, form_details: dict[str, str]) -> bool:
    try:
      resp = await self.client.get(kegiatan_url, follow_redirects=True)
      resp.raise_for_status()

      tree = HTMLParser(resp.content)
      if not (add_link_node := tree.css_first("a[title='Tambah']")):
        print_log("Couldn't find 'Tambah' link on the Kegiatan page.", "ERROR")
        return False

      if not (add_form_url := add_link_node.attributes.get("href")):
        print_log("Couldn't find form url in the Node", "ERROR")
        return False

      resp = await self.client.get(add_form_url, follow_redirects=True)
      resp.raise_for_status()

      tree = HTMLParser(resp.content)
      if not (form := tree.css_first("form")):
        print_log("Could not find the sub-entry form.", "ERROR")
        return False

      if not (action_url := form.attributes.get("action")):
        print_log("Couldn't find action url in the Node", "ERROR")
        return False

      form_data = {}
      for inp in form.css("input[type='hidden']"):
        name = inp.attributes.get("name")
        value = inp.attributes.get("value")
        if name:
          form_data[name] = value

      form_data.update(
        {
          "dParam[judul]": form_details.get("title", ""),
          "dParam[pelaksanaan]": form_details.get("datetime", ""),
          "dParam[durasi]": str(form_details.get("duration", "0")),
          "dParam[sasaran]": form_details.get("target", "-"),
          "dParam[jok]": form_details.get("jok", "0"),
          "dParam[jumPeserta]": form_details.get("audience", "0"),
          "dParam[deskripsi]": form_details.get("description", ""),
          "dParam[sumberDanaMulti][]": ["1"],
          "dParam[sumberDanaLainMulti][]": [""],
          "dParam[jumDanaMulti][]": [form_details.get("budget", "0")],
          "dParam[hasilKegiatan]": form_details.get("result", ""),
        }
      )

      resp = await self.client.post(action_url, data=form_data, follow_redirects=True)
      resp.raise_for_status()

      try:
        resp_json = resp.json()
        if resp_json.get("status") == "success":
          print_log(f"Created sub-entry: {resp_json.get('msg')}", "SUCCESS")
          return True
        else:
          print_log(f"Server Response[#89dceb]:[/] {resp_json}", "ERROR")
          return False
      except json.JSONDecodeError:
        if resp.status_code == 200:
          print_log("Created new sub-entry (judging by status code)", "SUCCESS")
          return True

        print_log("Failed to create sub-entry and response was not valid JSON", "ERROR")
        return False

    except httpx.RequestError as e:
      print_log(f"Network error creating sub-entry[#89dceb]:[/] {repr(e)}", "ERROR")
      return False
    except Exception as e:
      print_log(f"Unexpected error in create_sub_entry_base[#89dceb]:[/] {e}", "ERROR")
      return False

  async def post_logbook_attendance(self, url: str, latitude: str, longitude: str):
    url_parts = [p for p in url.split("/") if p]

    if not (page_token := self.client.cookies.get("simasterUGM_cookie", None)):
      print_log("No `cookie` found", "ERROR")
      return

    payload = {
      "timelineId": url_parts[-5],
      "rppJenisProgram": url_parts[-4],
      "rppMhsId": url_parts[-3],
      "kegiatanMhsId": url_parts[-2],
      "programMhsId": url_parts[-1],
      "agreement": "1",
      "latitude": str(latitude),
      "longtitude": str(longitude),
      "simasterUGM_token": page_token,
    }

    try:
      resp = await self.client.post(KKN_ATTENDANCE_URL, data=payload)
      resp.raise_for_status()

      resp_json = resp.json()
      if resp_json.get("status") == "success":
        print_log(resp_json.get("msg"), "SUCCESS")
        return True
      else:
        print_log(resp_json.get("msg"), "ERROR")
        return False
    except Exception as e:
      print_log(f"Unexpected error in post_logbook_attendance[#89dceb]:[/] {e}", "ERROR")
      return False
