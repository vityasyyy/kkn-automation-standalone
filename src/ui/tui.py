import random
from typing import Literal

from prompt_toolkit import PromptSession
from rich.console import Console

console = Console()
prompt_session = PromptSession()

type Level = Literal["SUCCESS", "ERROR", "WARN"]

PREFIX = {
  "SUCCESS": "[bold green] SUCCESS[/][#89dceb]:[/] ",
  "ERROR": "[bold red] ERROR[/][#89dceb]:[/] ",
  "WARN": "[bold yellow] WARNING[/][#89dceb]:[/] ",
}


def print_log(message: str, level: Level = "WARN"):
  prefix = PREFIX[level]
  console.print(f"{prefix}{message}")


def print_title():
  title = [
    "[#99FF99]▄▄▄    ▄▄▄          ████                         ▄▄▄  ▄▄▄ ▄▄▄  ▄▄▄ ▄▄▄  ▄▄▄[/]",
    "[#99FFB2]███▄  ▄███  ██████▄  ███   ██████▄ ▄███████      ███  ███ ███  ███ ███▄ ███[/]",
    "[#99FFCC]██████████ ▄▄▄▄▄███  ███  ▄▄▄▄▄███ ▀██▄▄▀▀▀ ▄▄▄▄ ████▄██▀ ████▄██▀ ████▄███[/]",
    "[#99FFE5]███ ▀▀ ███ ███▀▀███  ███  ███▀▀███   ▀▀███▄ ▀▀▀▀ ███▀███▄ ███▀███▄ ███▀████[/]",
    "[#99FFFF]███    ███ ▀███████ █████ ▀███████ ███████▀      ███  ███ ███  ███ ███ ▀███[/]",
  ]

  splash_text = [
    "Because life is too short for manual logbook",
    "I don't have enough time to deal with this sh*t",
    "Imagine doing this manually through the web, lmao",
    "Speedrunning KKN Administrative Tasks (Any%)",
    "Constructing payload... Target locked... Attendance posted",
    "Powered by caffeine and hatred for legacy code",
    "Who's in the right mind sending back a 100kb HTML file??",
    "Does anyone actually read these logbooks? asking for a script.",
    "Generating 'productive' activity descriptions...",
    "Fake it 'til you automate it.",
  ]

  random_quotes = f"\n{random.choice(splash_text):^75}\n"
  console.print(("\n".join(title)))
  print(random_quotes)


def print_choice():
  options = [
    "Post Daily Attendance",  # done
    "Show Programs",  # done
    "Add New Logbook Entry (My Program)",  # hook this
    "Add New Sub-Entry (My Program)",  # test this
    "Post Attendance for Unattended Entries",
    "Generate Activity Timeline",
    "Change Account",
    "Refresh",
    "Exit",
  ]

  opt_len = len(str(len(options)))
  for i, opt in enumerate(options, 1):
    fmt_opt = f"[#89dceb][[#fab387]{i:0{opt_len}}[/]][/] {opt}"
    console.print(fmt_opt)

  print()
