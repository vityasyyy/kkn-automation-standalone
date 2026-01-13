# KKN Attendance Automation

A simple program that can automatically (soon™) submits your KKN-PPM UGM attendance using the new VNEXT Checkpoint API

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

## TODO

- [ ] Automation (Docker/Termux/GitHub actions?)
- [x] Use [rich](https://github.com/textualize/rich) for a nicer UI
- [ ] More features related to KKN
  - [x] Program caching to minimize request to SIMASTER
  - [x] Add entry to logbook
  - [x] ~Automate~ Handle attendance of those entry
  - [ ] ~Handle case when we want to backdate (set the date to the current date, post attendance, then revert the date back)~

---
