import hashlib
import os
from contextlib import nullcontext
from pathlib import Path

import httpx
from cachelib import FileSystemCache

from ui.tui import console, print_log

BASE_URL = "https://simaster.ugm.ac.id"
HOME_URL = f"{BASE_URL}/beranda"
LOGIN_URL = f"{BASE_URL}/services/simaster/service_login"
CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
CACHE_THRESHOLD = int(os.getenv("CACHE_THRESHOLD", str(500)))


class Simaster:
  def __init__(self, username: str, password: str):
    self.username = username
    self.password = password
    try:
      CACHE_DIR.mkdir(parents=True, exist_ok=True)
      self.cache: FileSystemCache = FileSystemCache(str(CACHE_DIR), threshold=CACHE_THRESHOLD)
    except OSError:
      from cachelib import SimpleCache

      self.cache = SimpleCache()

  def _get_cache_key(self, username: str, password: str):
    return hashlib.md5(f"{username}:{password}".encode()).hexdigest()

  async def _check_cache(self, key: str) -> httpx.AsyncClient | None:
    if not (cookies := self.cache.get(key)):
      return None

    client = httpx.AsyncClient(cookies=cookies, timeout=5.0)

    try:
      resp = await client.get(HOME_URL, follow_redirects=True)
      if resp.status_code == 200:
        print("Cached session is valid.")
        return client
      else:
        print("Cached session is invalid or expired.")
        await client.aclose()
    except httpx.RequestError as e:
      print(f"Failed to validate cached session: {e}")
      await client.aclose()

    return None

  async def login(
    self,
    username: str | None = None,
    password: str | None = None,
    reuse_session: bool = True,
    verbose: bool = False,
  ) -> httpx.AsyncClient | None:
    self.username = username or self.username
    self.password = password or self.password

    key = self._get_cache_key(self.username, self.password)
    if reuse_session and (client := await self._check_cache(key)):
      return client

    client = httpx.AsyncClient(timeout=5.0)
    login_data = {"aId": "", "username": self.username, "password": self.password}

    try:
      status_context = (
        console.status(f"[bold green]Logging in as [bold #89dceb]{self.username}[/]...", spinner="dots")
        if verbose
        else nullcontext()
      )

      with status_context:
        resp = await client.post(LOGIN_URL, data=login_data, follow_redirects=True)
        resp.raise_for_status()
        resp_json = resp.json()

      if resp_json.get("isLogin") == 1:
        if verbose:
          console.print(f"[green]Succesfully logged in as {resp_json.get('namaLengkap')}[/]")

        self.cache.set(key, dict(client.cookies), timeout=60 * 60 * 24 * 2)
        return client
      else:
        if verbose:
          print_log("Login failed, Please check your username and password.", "ERROR")

        await client.aclose()
        return None

    except Exception as e:
      if verbose:
        print_log(f"An error occured during login: {e}", "ERROR")

      await client.aclose()
      return None
