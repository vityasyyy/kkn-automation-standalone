import re
from urllib.parse import parse_qs, urlparse

import requests
from selectolax.parser import HTMLParser

from datatypes import OAuthResponse, RequestData, RequestHeader, RequestParam

OAUTH_BASE_URL = "https://oauth.simaster.ugm.ac.id"
SSO_BASE_URL = "https://sso.ugm.ac.id"
ALL_SCOPE = "user.read user.read-write-update userDetail.read alumni.read student pegawai.all.read pegawai.unit.read staff tte notif.create-read ldap parent.read parent.read-write-update mygate.read-write vehicle.read transgama.read"


class OAuthClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.session = requests.Session()

        self.default_headers: RequestHeader = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; sdk_gphone64_x86_64 Build/SE1A.220826.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "id.ac.ugm.student.vnext.simaster",
        }

        self.jsessionid = None
        self.lt_token = None
        self.ticket = None
        self.session_cookie = None
        self.access_token = None

    def _extract_jsession(self, cookie_header: str) -> str | None:
        parts = cookie_header.split(";")
        for part in parts:
            part = part.strip()
            if part.startswith("JSESSIONID="):
                return part.split("=", 1)[1]

        return None

    def _extract_lt_value(self, html_content: str) -> str | None:
        tree = HTMLParser(html_content)
        node = tree.css_first('input[name="lt"][type="hidden"]')

        return node.attributes.get("value") if node else None

    def _extract_location_header(self, location_header: str, field: str) -> str | None:
        try:
            parsed_url = urlparse(location_header)
            query_params = parse_qs(parsed_url.query)

            return query_params[field][0] if field in query_params else None
        except Exception as e:
            print(f"Error extracting ticket: {e}")
            return None

    def _extract_session_cookie(self, set_cookie_header: str) -> str | None:
        match = re.search(r"session=([^;]+)", set_cookie_header)
        return match.group(1) if match else None

    def get_auth_url(self) -> OAuthResponse:
        url = f"{OAUTH_BASE_URL}/oauth/authorize"
        params: RequestParam = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": ALL_SCOPE,
        }

        headers = self.default_headers.copy()
        headers.update(
            {
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document",
            }
        )

        try:
            resp = self.session.get(url, params=params, headers=headers)
            resp.raise_for_status()

            self.jsessionid = self._extract_jsession(resp.headers.get("Set-Cookie", ""))
            self.lt_token = self._extract_lt_value(resp.text)

            return {
                "success": True,
                "status_code": resp.status_code,
                "jsessionid": self.jsessionid,
                "lt_token": self.lt_token,
                "scope": ALL_SCOPE,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def login(self, username: str, password: str) -> OAuthResponse:
        if not self.jsessionid or not self.lt_token:
            auth_result = self.get_auth_url()
            if not auth_result["success"]:
                return auth_result

        url = f"{SSO_BASE_URL}/cas/login;jsessionid={self.jsessionid}"
        params: RequestParam = {
            "service": f"{OAUTH_BASE_URL}/oauth/authorize?response_type=code&client_id={self.client_id}&redirect_uri={self.redirect_uri}&scope={ALL_SCOPE}"
        }

        assert self.lt_token is not None, "`lt_token` is empty!"
        data: RequestData = {
            "username": username,
            "password": password,
            "lt": self.lt_token,
            "_eventId": "submit",
            "submit": "LOGIN",
        }

        headers = self.default_headers.copy()
        headers.update(
            {
                "Cache-Control": "max-age=0",
                "Upgrade-Insecure-Requests": "1",
                "Origin": SSO_BASE_URL,
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document",
                "Referer": f"{SSO_BASE_URL}/cas/login?service={OAUTH_BASE_URL}/oauth/authorize?response_type=code&client_id={self.client_id}&redirect_uri={self.redirect_uri}&scope={ALL_SCOPE}",
                "Cookie": f"JSESSIONID={self.jsessionid}",
            }
        )

        try:
            resp = self.session.post(url, params=params, data=data, headers=headers, allow_redirects=False)

            if resp.status_code == 302:
                loc = resp.headers.get("Location", "")
                self.ticket = self._extract_location_header(loc, "ticket")

                return {"success": True, "status_code": resp.status_code, "ticket": self.ticket, "location": loc}
            else:
                tree = HTMLParser(resp.text)
                error = tree.css('div[class="alert alert-danger"]')
                return {"success": False, "status_code": resp.status_code, "error": error[0].text(strip=True)}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_session_cookie(self) -> OAuthResponse:
        if not self.ticket:
            return {"success": False, "error": "No ticket available. Please login first."}

        url = f"{OAUTH_BASE_URL}/oauth/authorize"

        params: RequestParam = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": ALL_SCOPE,
            "ticket": self.ticket,
        }

        headers = self.default_headers.copy()
        headers.update(
            {
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document",
            }
        )

        try:
            resp = self.session.get(url, params=params, headers=headers, allow_redirects=False)

            if resp.status_code == 302:
                set_cookie = resp.headers.get("Set-Cookie", "")
                self.session_cookie = self._extract_session_cookie(set_cookie)

                return {"success": True, "status_code": resp.status_code, "session_cookie": self.session_cookie}
            else:
                return {"success": False, "status_code": resp.status_code, "error": "Failed to get session cookie"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def authorize_access(self) -> OAuthResponse:
        if not self.session_cookie or not self.ticket:
            return {"success": False, "error": "No session cookie or ticket available. Please complete previous steps."}

        url = f"{OAUTH_BASE_URL}/oauth/authorize"

        params: RequestParam = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": ALL_SCOPE,
            "ticket": self.ticket,
        }

        data: RequestData = {"confirm": "Izinkan"}
        headers = self.default_headers.copy()
        headers.update(
            {
                "Cache-Control": "max-age=0",
                "Upgrade-Insecure-Requests": "1",
                "Origin": OAUTH_BASE_URL,
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document",
                "Referer": f"{OAUTH_BASE_URL}/oauth/authorize?response_type=code&client_id={self.client_id}&redirect_uri={self.redirect_uri}&scope={ALL_SCOPE}&ticket={self.ticket}",
                "Cookie": f"session={self.session_cookie}; _ga_B3TESR985X=GS2.1.s1754044819$o1$g0$t1754044819$j60$l0$h0; _ga_L4JC39NX24=GS2.1.s1754044820$o1$g0$t1754044820$j60$l0$h0; _ga=GA1.3.1600030693.1754044819; _gid=GA1.3.1789808150.1754044821",
            }
        )

        try:
            resp = self.session.post(url, params=params, data=data, headers=headers, allow_redirects=False)

            if resp.status_code == 302:
                loc = resp.headers.get("Location", "")
                code = self._extract_location_header(loc, "code")

                return {"success": True, "status_code": resp.status_code, "authorization_code": code, "location": loc}
            else:
                return {"success": False, "status_code": resp.status_code, "error": "Authorization failed"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_access_token(self, authorization_code: str) -> dict[str, bool | str | None]:
        url = f"{OAUTH_BASE_URL}/oauth/token"

        data: RequestData = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        headers: RequestHeader = {
            "User-Agent": "Dart/3.1 (dart:io)",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            resp = self.session.post(url, data=data, headers=headers, allow_redirects=False)
            resp.raise_for_status()

            token_data = resp.json()
            self.access_token = token_data.get("access_token")

            return {
                "success": True,
                "status_code": resp.status_code,
                "token_data": token_data,
                "access_token": self.access_token,
            }

        except Exception as e:
            return {"success": False, "error": str(e), "response_text": resp.text if "response" in locals() else None}

    def complete_oauth_flow(self, username: str, password: str) -> OAuthResponse:
        auth_result = self.get_auth_url()
        if not auth_result["success"]:
            return {"success": False, "step": "authorization_url", "error": auth_result["error"]}

        login_result = self.login(username, password)
        if not login_result["success"]:
            return {"success": False, "step": "login", "error": login_result["error"]}

        session_result = self.get_session_cookie()
        if not session_result["success"]:
            return {"success": False, "step": "session_cookie", "error": session_result["error"]}

        auth_code_result = self.authorize_access()
        if not auth_code_result["success"]:
            return {"success": False, "step": "authorize_access", "error": auth_code_result["error"]}

        assert type(auth_code_result["authorization_code"]) is str
        token_result = self.get_access_token(auth_code_result["authorization_code"])
        if not token_result["success"]:
            return {"success": False, "step": "access_token", "error": token_result["error"]}

        return {
            "success": True,
            "access_token": self.access_token,
            "token_data": token_result["token_data"],
            "flow_completed": True,
        }
