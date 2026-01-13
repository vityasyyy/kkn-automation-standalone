from rich import box
from rich.align import Align
from rich.box import Box
from rich.panel import Panel
from rich.table import Table

from datatypes import AssistedProgram, EntryData, RPPData
from ui.tui import console, log

# fmt: off
ROUNDED_HOLLOW: Box = Box(
    "╭──╮\n"
    "│  │\n"
    "├──┤\n"
    "│  │\n"
    "├──┤\n"
    "├──┤\n"
    "│  │\n"
    "╰──╯\n"
)
# fmt: on


STATUS_COLORS = {"Sudah Presensi": "[green]", "Persetujuan DPL": "[yellow]", "Belum Presensi": "[red]"}


def _create_nested_table(data: EntryData | AssistedProgram) -> Panel | Table:
    table = Table(box=ROUNDED_HOLLOW, expand=True)

    table.add_column(Align.center(data["title"]), style="#89b4fa", ratio=5)
    table.add_column("Status", justify="center", min_width=16)

    has_item = False
    for sub in data["sub_entries"]:
        has_item = True
        status = "Sudah Presensi" if sub.get("is_attended") else sub.get("status", "-")
        color = STATUS_COLORS.get(status, "")

        table.add_row(sub["title"], f"{color}{status}[/]")

    if not has_item:
        table.box = None
        table.show_edge = False
        table.padding = 0
        return Panel(table)

    return table


def _print_program_table(title: str, data: dict, is_assisted: bool = False):
    if not data:
        log.warning(f"No data found for {title}")
        return

    outer_table = Table(box=box.ROUNDED, title=title, expand=True)
    outer_table.add_column("No", justify="center", style="#fab387", width=2)
    outer_table.add_column(Align.center("PIC" if is_assisted else "Program"), ratio=1)

    for i, (key, value) in enumerate(data.items(), 1):
        main_label = key if is_assisted else value["title"]
        outer_table.add_row(str(i), f"[bold]{main_label}[/]")

        entries_to_process = value if is_assisted else value.get("entries", [])

        for entry in entries_to_process:
            inner_table = _create_nested_table(entry)
            outer_table.add_row("", inner_table)

    console.print(outer_table)


def _print_simple_list(data: list):
    if not data:
        return

    table = Table(box=box.ROUNDED)
    table.add_column("No", justify="center", style="#fab387", width=2)
    table.add_column(Align.center("Entries"))
    table.add_column(Align.center("Date"))

    for i, item in enumerate(data, 1):
        table.add_row(str(i), item.get("title", "N/A"), item.get("date", "N/A"))

    console.print(table)


def print_program_title(data: dict[str, RPPData] | None):
    if not data:
        log.warning("No data found")
        return None

    table = Table(box=box.ROUNDED)

    table.add_column("No", justify="center", style="#fab387")
    table.add_column(Align.center("Title"))

    for i, (k, v) in enumerate(data.items(), 1):
        table.add_row(str(i), v["title"])

    console.print(table)


def print_assisted_program(data: dict[str, list[AssistedProgram]] | None):
    _print_program_table("Program Bantu", data or {}, is_assisted=True)


def print_program_details(data: dict[str, RPPData] | None):
    _print_program_table("Program Utama", data or {}, is_assisted=False)


def print_program_entries(data: RPPData):
    _print_simple_list(data.get("entries", []))


def print_program_sub_entries(data: EntryData):
    _print_simple_list(data.get("sub_entries", []))
