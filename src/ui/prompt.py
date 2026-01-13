import os
from datetime import datetime

from rich import box
from rich.align import Align
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

import utils.generative as gen
from datatypes import LogEntryPayload, RPPData
from ui.tables import print_program_entries, print_program_sub_entries
from ui.tui import console, log
from utils.common import generate_random_points


def parse_selection(input_str: str) -> list[int]:
    selected = set()
    tokens = input_str.split()

    for token in tokens:
        try:
            if "-" in token:
                start_str, end_str = token.split("-", 1)
                start, end = int(start_str), int(end_str)

                lower, upper = min(start, end), max(start, end)
                selected.update(range(lower, upper + 1))
            else:
                selected.add(int(token))
        except ValueError:
            log.warning(f"Token: '{token}' is not a number or a hyphen")
            continue

    return sorted(list(selected))


def get_entry_details_from_user(data: RPPData) -> LogEntryPayload | None:
    console.print(f"Current entries for {data['title']}")
    print_program_entries(data)

    entry_title = Prompt.ask("Enter the title for the new logbook entry (Kegiatan)")
    default_date = datetime.now().strftime("%Y-%m-%d")
    activity_datetime = Prompt.ask("Enter date (YYYY-MM-DD)", default=default_date)

    default_lat = os.getenv("KKN_LOCATION_LATITUDE", "0.0")
    default_long = os.getenv("KKN_LOCATION_LONGITUDE", "0.0")
    console.print(f"[blue]Generated random point: [yellow]([#fab387]{default_lat}[cyan],[/] {default_long}[/])[/]")
    use_coord = Confirm.ask("Use default location?", default=True)

    latitude = float(default_lat)
    longitude = float(default_long)

    if not use_coord:
        try:
            latitude = float(input("Enter new latitude: "))
            longitude = float(input("Enter new longitude: "))
        except ValueError:
            console.print("[red]ERROR[/]: Invalid input for location. Using defaults...")
            latitude = float(default_lat)
            longitude = float(default_long)

    form_data = Table(box=box.ROUNDED, title="Summary")
    form_data.add_column(Align.center("Field"))
    form_data.add_column(Align.center("Content"), overflow="fold")

    form_data.add_row("[cyan]-[bold white] Title", entry_title)
    form_data.add_row("[cyan]-[bold white] Date", activity_datetime)

    location = Table(box=box.ROUNDED, show_header=False)
    location.add_row("[bold]Latitude", f"[#fab387]{latitude}")
    location.add_row("[bold]Longitude", f"[#fab387]{longitude}")

    form_data.add_row("[cyan]-[bold white] Location", location)

    console.print(form_data)
    confirm = Confirm.ask("Do you want to add this entry?", default=True)

    if not confirm:
        console.print("Operation cancelled.")
        return

    random_lat, random_long = generate_random_points(latitude, longitude, 15)

    return {"title": entry_title, "date": activity_datetime, "longitude": longitude, "latitude": latitude}


def get_sub_entry_details_from_user(data: RPPData):
    program_title = data["title"]
    console.print(f"Current entries for {data['title']}")
    print_program_entries(data)

    length = len(data["entries"])
    choice = int(
        Prompt.ask(
            f"Enter your choice [cyan]([#fab387]1[cyan]-[/]{length}[/])[/]:",
            choices=[str(i + 1) for i in range(length)],
        )
    )
    sub_entry = data["entries"][choice - 1]
    print_program_sub_entries(sub_entry)

    sub_entry_title = Prompt.ask("Enter the title for the new logbook sub-entry (Kegiatan)")
    duration = Prompt.ask("Enter the duration in minutes", default="60")

    activity_datetime = datetime.now().strftime("%Y-%m-%d %H:%M")
    target = "-"
    audience = "0"
    budget = "0"

    fill_details = Confirm.ask(
        "Do you want to fill in additional details (date, time, participants, etc.)?", default=False
    )

    if fill_details:
        default_date = datetime.now().strftime("%Y-%m-%d")
        default_time = datetime.now().strftime("%H:%M")

        date_input = Prompt.ask("Enter date (YYYY-MM-DD)", default=default_date)
        time_input = Prompt.ask("Enter time (HH:MM)", default=default_time)

        activity_datetime = f"{date_input} {time_input}"
        target = Prompt.ask("Enter target audience (sasaran)", default="-")
        audience = Prompt.ask("Enter number of participants (jumlah peserta)", default="0")
        budget = Prompt.ask("Enter amount of funds (jumlah dana)", default="0")

    description = ""
    result = "Kegiatan terlaksana dengan baik."
    jok = 2 * int(audience) * 20_000

    use_ai = False
    if gen.is_generative_ai_available():
        use_ai = Confirm.ask("[blue]󰫢 [/]Gemini AI is available. Generate description and results?", default=False)

    if use_ai:
        with console.status("Generating Content with Gemini...") as status:
            while True:
                desc_prompt = gen.generate_description_prompt(program_title, sub_entry_title)
                console.print(Panel(Markdown(desc_prompt), title="Current Prompt"))
                if Confirm.ask("Add additional context?", default=False):
                    context = Prompt.ask("Enter additional context")
                    desc_prompt = gen.generate_description_prompt(program_title, sub_entry_title, context)

                status.update("Generating program description...")
                generated_desc = gen.generate_content(desc_prompt)

                result_prompt = gen.generate_result_prompt(program_title, sub_entry_title, generated_desc)
                status.update("Generating program description...")

                while len((generated_result := gen.generate_content(result_prompt))) > 256:
                    pass

                generated_content = f"Deskripsi kegiatan:\n{generated_desc}\nHasil Kegiatan:\n{generated_result}"
                console.print(Panel(generated_content, title="AI Generated Content"))

                choice = Prompt.ask(
                    "Accept (a), Regenerate (r), or write Manually (m)?", choices=["a", "r", "m"], default="a"
                )
                if choice == "r":
                    print("Regenerating content...")
                    continue
                elif choice == "m":
                    description = input("\nEnter Deskripsi Kegiatan: ")
                    result = input("Enter Hasil Kegiatan: ")
                    break
                else:
                    description, result = generated_desc, generated_result
                    break
    else:
        description = input("\nEnter Deskripsi Kegiatan: ")
        result = input("Enter Hasil Kegiatan: ")

    form_data = Table(box=box.ROUNDED, title="Summary")
    form_data.add_column(Align.center("Field"))
    form_data.add_column(Align.center("Content"), overflow="fold")

    form_data.add_row("[cyan]-[bold white] Title", sub_entry_title)
    form_data.add_row("[cyan]-[bold white] Date", activity_datetime)
    form_data.add_row("[cyan]-[bold white] Duration", f"{duration} minutes")
    form_data.add_row("[cyan]-[bold white] Target", target)
    form_data.add_row("[cyan]-[bold white] Audience", f"{audience} people")
    form_data.add_row("[cyan]-[bold white] JOK", f"Rp. {jok}")
    form_data.add_row("[cyan]-[bold white] Description", description)
    form_data.add_row("[cyan]-[bold white] Budget source", "UGM")
    form_data.add_row("[cyan]-[bold white] Budget", budget)
    form_data.add_row("[cyan]-[bold white] Result", result)

    console.print(form_data)
    confirm = Confirm.ask("Do you want to add this entry?", default=True)

    if not confirm:
        console.print("Operation cancelled.")
        return

    return sub_entry["activity_url"], {
        "title": sub_entry_title,  # judul
        "datetime": activity_datetime,  # pelaksanaan
        "duration": int(duration),  # durasi
        "target": target,  # sasaran
        "jok": jok,  # jok
        "audience": audience,  # jumPeserta
        "description": description,  # deskripsi
        "budget": budget,  # jumDana
        "result": result,  # hasilKegiatan
    }
