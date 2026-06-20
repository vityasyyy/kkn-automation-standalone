# KKN Attendance Automation

A simple program that manage your KKN-PPM UGM administrative works, which includes:

- Entering logbook entries and sub-entries
- Post attendance for logbook entries
- Daily attendance using the new VNEXT Checkpoint API

![app](./assets/app.jpeg)

---

## Motivation

This program exist for a couple of reasons:

1. SIMASTER web UI is ass and the UX is even worse
2. The API handling is as consistent as my will to live (which is never /s)
3. I mean who doesn't like automation when the system is bad and time-consuming
4. I have free will

---

## Getting Started

There are currently only one way to run this, for planned feature see [TODO](#todo)

1. Clone the repository

```sh
git clone https://github.com/davinjason09/kkn-automation
cd kkn-automation
```

2. Setup the Python environment

- If you're using `pip`:
  - Set up a Virtual environment

    ```sh
    python -m venv .venv
    source .venv/bin/activate
    ```

  - Install the dependencies

    ```sh
    pip install -r requirements.txt
    ```

- If you're using [`uv`](https://github.com/astral-sh/uv/)

  ```sh
  uv sync
  ```

3. Create the Environment File \
   Create a file named `.env` in the project's root directory.

4. Configure your settings \
   Copy the template below into your `.env` or see [example](./.env.example).

```sh
# QR Code Location Value (Required)
QR_CODE_VALUE=the_qr_value

# KKN Location Settings (Required)
KKN_LOCATION_LATITUDE=-7.9547226
KKN_LOCATION_LONGITUDE=110.2788225
KKN_LOCATION_RADIUS_METERS=50

# A comma separated value for multiple usernames
USERNAMES=a,b,c,d

# SIMASTER credentials (Optional)
SIMASTER_USERNAME=username
SIMASTER_PASSWORD=password

# Gemini API Key (Optional)
GEMINI_API_KEY=
```

5. Run `main.py`

```text
usage: main.py [-s] [-c] [-h]

options:
  -s, --submit  (bool, default=False) Submit your attendance
  -c, --check   (bool, default=False) Check whether if you have logged in or not
  -h, --help    show this help message and exit

```

## Limitations

- It can only add logbook entries and sub-entries, if you wish to edit them, you have to edit them through the web.

## Daily Unattended Runs

The tool supports a **headless mode** (`--headless`) that skips all interactive
prompts and reads behavior from environment variables. This makes it safe to
schedule via GitHub Actions, `launchd`, or `cron`.

### CLI flags

```text
usage: main.py [-s] [-c] [-r] [--headless]

options:
  -s, --submit   Submit attendance for everyone in USERNAMES
  -c, --check    Check active session status for everyone in USERNAMES
  -r, --report   Generate attendance reports (ICS + HTML + PDF)
      --headless Run without interactive prompts (reads env vars)
  -h, --help     show this help message and exit
```

You can combine flags, e.g. `python src/main.py -s --headless --report` to
submit attendance and generate reports in one headless run.

### Option A: GitHub Actions (recommended — laptop can stay off)

A workflow is included at `.github/workflows/daily-attendance.yml`. It runs at
**10:00 WIB (03:00 UTC)** daily, submits attendance for everyone in `USERNAMES`,
generates reports, and uploads them as artifacts (7-day retention). If the run
fails, GitHub emails you automatically.

To use it on your fork:

1. Fork this repo to your GitHub account (done — `vityasyyy/kkn-automation`).
2. In the fork, go to **Settings → Secrets and variables → Actions** and add:
   - `SIMASTER_USERNAME`, `SIMASTER_PASSWORD`
   - `USERNAMES` (comma-separated, include yourself)
   - `QR_CODE_VALUE`, `KKN_LOCATION_LATITUDE`, `KKN_LOCATION_LONGITUDE`, `KKN_LOCATION_RADIUS_METERS`
   - `AI_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_API_KEY`, `OLLAMA_MODEL`
3. Enable Actions in the fork's **Actions** tab.
4. The schedule fires daily. You can also trigger it manually via
   **Run workflow** in the Actions tab.

Your laptop does **not** need to be on — GitHub runs it in the cloud.

### Option B: launchd on macOS (laptop must be on or allowed to wake)

A template plist is at `docs/launchd/kkn-attendance.plist`.

1. Edit the paths in the plist (replace `YOUR_USERNAME` and the project path).
2. Copy to `~/Library/LaunchAgents/com.vityasyyy.kkn-attendance.plist`.
3. Load: `launchctl load ~/Library/LaunchAgents/com.vityasyyy.kkn-attendance.plist`.

`launchd` with `StartCalendarInterval` catches up missed runs on wake — if the
laptop was asleep at 10:00, the job runs shortly after you wake it.

### Option C: cron

```cron
0 10 * * * cd /path/to/kkn-automation && .venv/bin/python src/main.py -s --headless --report >> logs/cron.log 2>&1
```

### Env vars for headless behavior

| Variable | Default | Purpose |
|---|---|---|
| `IDEMPOTENT` | `true` | Skip check-in if user already has an active session |
| `THROTTLE` | `false` | Random 0–5s delay between usernames |
| `SHUFFLE` | `true` | Shuffle the check-in order |
| `MAX_RETRIES` | `3` | Bounded retry attempts on failure |
| `RETRY_BACKOFF` | `2.0` | Exponential backoff base (seconds) |
| `AI_PROVIDER` | `gemini` | `ollama` or `gemini` |
| `OLLAMA_BASE_URL` | — | Ollama Cloud endpoint (OpenAI-compatible) |
| `OLLAMA_API_KEY` | — | Bearer token for Ollama Cloud |
| `OLLAMA_MODEL` | `qwen2.5` | Model name for drafting + report narrative |
| `GEMINI_API_KEY` | — | Google Gemini API key (alternative provider) |

See [`.env.example`](./.env.example) for the full list including logging/cache paths.

## Report Generation

The tool generates three report formats (written to `reports/`):

- **ICS** — calendar file of attended sub-entries (import to Google Calendar / Apple Calendar)
- **HTML** — styled summary table with attendance counts + AI narrative
- **PDF** — printable version of the HTML report

When `AI_PROVIDER` is configured, an AI-generated Indonesian narrative summary
is embedded in the HTML/PDF. Works with Ollama Cloud or Gemini.

## TODO

- [x] Automation (GitHub Actions + headless mode)
- [x] Use [rich](https://github.com/textualize/rich) for a nicer UI
- [x] More features related to KKN
  - [x] Program caching to minimize request to SIMASTER
  - [x] Add entry to logbook
  - [x] ~Automate~ Handle attendance of those entry
  - [x] Report generation (HTML, PDF, ICS)
  - [ ] ~Handle case when we want to backdate (set the date to the current date, post attendance, then revert the date back)~

---
