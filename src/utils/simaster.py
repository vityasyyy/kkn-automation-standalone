import hashlib
from contextlib import nullcontext

import httpx
from cachelib import SimpleCache

from ui.tui import console

BASE_URL = "https://simaster.ugm.ac.id"
HOME_URL = f"{BASE_URL}/beranda"
LOGIN_URL = f"{BASE_URL}/services/simaster/service_login"


class Simaster:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.cache: SimpleCache = SimpleCache()

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
                console.status(f"[bold green]Logging in as {self.username}...", spinner="dots")
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
                    console.print("[bold red]Login failed, Please check your username and password.[/]")

                await client.aclose()
                return None

        except Exception as e:
            if verbose:
                console.print(f"[bold red]An error occured during login: {e}[/]")

            await client.aclose()
            return None
