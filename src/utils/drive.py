import json
import os
from pathlib import Path

from utils.logger import get_logger

log = get_logger("drive")


def _get_drive_service():
  """Build an authorized Drive service from the service-account JSON secret."""
  from google.oauth2 import service_account
  from googleapiclient.discovery import build

  raw = os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON")
  if not raw:
    raise RuntimeError("GDRIVE_SERVICE_ACCOUNT_JSON env var is not set")

  info = json.loads(raw)
  scopes = ["https://www.googleapis.com/auth/drive.file"]
  creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
  return build("drive", "v3", credentials=creds, cache_discovery=False)


def _list_folders(service, parent_id: str, name: str) -> str | None:
  """Find a folder by name under parent_id. Returns folder ID or None."""
  query = (
    f"'{parent_id}' in parents and "
    f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
  )
  resp = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
  files = resp.get("files", [])
  return files[0]["id"] if files else None


def _create_folder(service, parent_id: str, name: str) -> str:
  """Create a folder under parent_id and return its ID."""
  body = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
  resp = service.files().create(body=body, fields="id").execute()
  return resp["id"]


def _ensure_folder_path(service, root_id: str, parts: list[str]) -> str:
  """Walk/create a nested folder path under root_id. Returns the final folder ID."""
  current = root_id
  for part in parts:
    fid = _list_folders(service, current, part)
    if not fid:
      fid = _create_folder(service, current, part)
      log.info("Created Drive folder: %s", "/".join(parts[: parts.index(part) + 1]))
    current = fid
  return current


def _file_exists(service, folder_id: str, name: str) -> bool:
  query = f"'{folder_id}' in parents and name = '{name}' and trashed = false"
  resp = service.files().list(q=query, fields="files(id)", pageSize=1).execute()
  return bool(resp.get("files", []))


def upload_file(local_path: Path, drive_parts: list[str], root_folder_id: str | None = None) -> str | None:
  """
  Upload a single file to Drive under root_folder_id/drive_parts[-1 dir]/filename.
  drive_parts: list of folder names to nest, e.g. ["alice", "2026-06-20"].
  The filename is taken from local_path.name.
  Returns the Drive file ID, or None on failure / skip.
  """
  root_id = root_folder_id or os.getenv("GDRIVE_FOLDER_ID")
  if not root_id:
    log.warning("GDRIVE_FOLDER_ID not set — skipping Drive upload for %s", local_path.name)
    return None

  try:
    service = _get_drive_service()
  except Exception as e:
    log.error("Drive auth failed: %s — skipping upload", e)
    return None

  try:
    folder_id = _ensure_folder_path(service, root_id, drive_parts)

    if _file_exists(service, folder_id, local_path.name):
      log.info("Drive: %s already exists in %s — skipping", local_path.name, "/".join(drive_parts))
      return None

    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(local_path), resumable=True)
    body = {"name": local_path.name, "parents": [folder_id]}
    resp = service.files().create(body=body, media_body=media, fields="id").execute()
    file_id = resp.get("id")
    log.info("Uploaded %s -> Drive %s (id=%s)", local_path.name, "/".join(drive_parts), file_id)
    return file_id
  except Exception as e:
    log.error("Drive upload failed for %s: %s", local_path.name, e)
    return None


def upload_directory(
  local_dir: Path, drive_parts: list[str], root_folder_id: str | None = None
) -> dict[str, str | None]:
  """Upload all files in local_dir to drive_parts under root. Returns {filename: drive_id|None}."""
  results = {}
  if not local_dir.exists():
    log.warning("Directory %s does not exist — skipping Drive upload", local_dir)
    return results

  for f in local_dir.iterdir():
    if f.is_file():
      results[f.name] = upload_file(f, drive_parts, root_folder_id)
  return results
