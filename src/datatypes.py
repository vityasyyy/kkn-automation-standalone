from typing import TypedDict

type RequestParam = dict[str, str]
type RequestData = dict[str, str]
type RequestHeader = dict[str, str]


# TODO: split
class OAuthResponse(TypedDict, total=False):
    # Status
    success: bool
    flow_completed: bool
    error: str
    status_code: str
    response_text: str | None

    # IDs / Code
    jsessionid: str | None
    lt_token: str | None
    session_cookie: str | None
    authorization_code: str | None
    access_token: str | None
    token_data: str

    ticket: str | None
    location: str
    scope: str

    step: str


class BasePayload(TypedDict):
    longitude: float
    latitude: float


class LogEntryPayload(BasePayload):
    title: str
    date: str


class SubEntryData(TypedDict, total=False):
    title: str
    date: str
    duration: str
    status: str
    is_attended: bool
    attendance_link: str | None


class EntryData(TypedDict, total=False):
    entry_index: int
    activity_url: str
    title: str
    date: str
    location: str
    sub_entries: list[SubEntryData]
    attendance_status: str


class RPPData(TypedDict, total=False):
    title: str
    action: str
    entries: list[EntryData]


class AssistedProgram(TypedDict, total=False):
    title: str
    action_url: str
    date: str
    location: str
    sub_entries: list[SubEntryData]
