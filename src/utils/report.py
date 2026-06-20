import os
from datetime import datetime
from pathlib import Path

from ics import Calendar, Event
from weasyprint import HTML as WeasyHTML

from datatypes import AssistedProgram, RPPData
from ui.tui import console, print_log
from utils.generative import generate_content, generate_report_narrative_prompt, is_generative_ai_available
from utils.kkn import KKN
from utils.logger import get_logger
from utils.simaster import Simaster

log = get_logger("report")

REPORT_DIR = Path(os.getenv("REPORT_DIR", "reports"))


def _collect_attendance_data(main_program: dict[str, RPPData], assisted_program: dict[str, list[AssistedProgram]]):
  """Flatten programs/entries/sub-entries into a list of attendance records."""
  records = []

  for p_id, program in main_program.items():
    title = program.get("title", "N/A")
    for entry in program.get("entries", []) or []:
      for sub in entry.get("sub_entries", []) or []:
        records.append(
          {
            "program": title,
            "type": "Main",
            "entry": entry.get("title", "N/A"),
            "sub_entry": sub.get("title", "N/A"),
            "date": sub.get("date", "N/A"),
            "duration": sub.get("duration", "N/A"),
            "status": sub.get("status", "N/A"),
            "attended": sub.get("is_attended", False),
          }
        )

  for pic, entries in (assisted_program or {}).items():
    for entry in entries:
      for sub in entry.get("sub_entries", []) or []:
        records.append(
          {
            "program": entry.get("title", "N/A"),
            "type": f"Bantu ({pic})",
            "entry": entry.get("title", "N/A"),
            "sub_entry": sub.get("title", "N/A"),
            "date": sub.get("date", "N/A"),
            "duration": sub.get("duration", "N/A"),
            "status": sub.get("status", "N/A"),
            "attended": sub.get("is_attended", False),
          }
        )

  return records


def _parse_date(date_str: str) -> datetime | None:
  """Try to parse Indonesian/common date formats from SIMASTER."""
  if not date_str or date_str == "N/A":
    return None
  formats = ["%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y"]
  for fmt in formats:
    try:
      return datetime.strptime(date_str.strip(), fmt)
    except ValueError:
      continue
  return None


def generate_ics(records: list[dict], out_path: Path) -> bool:
  cal = Calendar()
  for rec in records:
    if not rec["attended"]:
      continue
    dt = _parse_date(rec["date"])
    if not dt:
      continue
    ev = Event()
    ev.name = f"KKN: {rec['sub_entry']}"
    ev.begin = dt
    ev.duration = {"hours": 2}
    ev.description = f"Program: {rec['program']}\nEntry: {rec['entry']}\nStatus: {rec['status']}"
    cal.events.add(ev)

  try:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
      f.write(cal.serialize())
    log.info("ICS report written to %s (%d events)", out_path, len(cal.events))
    return True
  except Exception as e:
    log.error("Failed to write ICS: %s", e, exc_info=True)
    return False


def _build_html(records: list[dict], narrative: str | None, title_prefix: str = "") -> str:
  rows_html = []
  for rec in records:
    badge = "✓" if rec["attended"] else "—"
    badge_color = "#a6e3a1" if rec["attended"] else "#f38ba8"
    rows_html.append(
      f"<tr>"
      f"<td>{rec['program']}</td>"
      f"<td>{rec['type']}</td>"
      f"<td>{rec['entry']}</td>"
      f"<td>{rec['sub_entry']}</td>"
      f"<td>{rec['date']}</td>"
      f"<td>{rec['duration']}</td>"
      f"<td style='color:{badge_color}; font-weight:bold'>{badge}</td>"
      f"</tr>"
    )

  total = len(records)
  attended = sum(1 for r in records if r["attended"])
  generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
  report_title = f"Laporan Kehadiran KKN — {title_prefix}" if title_prefix else "Laporan Kehadiran KKN"

  narrative_section = ""
  if narrative:
    paragraphs = "".join(f"<p>{p.strip()}</p>" for p in narrative.split("\n\n") if p.strip())
    narrative_section = f"<section class='narrative'><h2>Ringkasan</h2>{paragraphs}</section>"

  return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<title>KKN Attendance Report — {generated_at}</title>
<style>
  body {{ font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; margin: 2rem; color: #1e1e2e; }}
  h1 {{ color: #89dceb; border-bottom: 2px solid #89dceb; padding-bottom: .3rem; }}
  h2 {{ color: #fab387; margin-top: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; font-size: 0.9rem; }}
  th, td {{ border: 1px solid #cdd6f4; padding: 0.5rem 0.7rem; text-align: left; }}
  th {{ background: #181825; color: #cdd6f4; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
  .summary {{ display: flex; gap: 2rem; margin: 1rem 0; }}
  .card {{ background: #f0f0f0; padding: 1rem 1.5rem; border-radius: 8px; }}
  .card .num {{ font-size: 1.8rem; font-weight: bold; color: #89dceb; }}
  .narrative {{ background: #f9f9f9; padding: 1rem 1.5rem; border-left: 4px solid #fab387; margin-top: 1.5rem; }}
  footer {{ margin-top: 2rem; color: #6c7086; font-size: 0.8rem; }}
</style>
</head>
<body>
  <h1>{report_title}</h1>
  <p>Dibuat: {generated_at}</p>
  <div class="summary">
    <div class="card"><div class="num">{total}</div>Total Sub-entri</div>
    <div class="card"><div class="num">{attended}</div>Hadir</div>
    <div class="card"><div class="num">{total - attended}</div>Belum Hadir</div>
  </div>
  {narrative_section}
  <h2>Detail Kegiatan</h2>
  <table>
    <thead><tr>
      <th>Program</th><th>Tipe</th><th>Entri</th><th>Sub-entri</th>
      <th>Tanggal</th><th>Durasi</th><th>Hadir</th>
    </tr></thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
  <footer>Generated by kkn-automation</footer>
</body>
</html>"""


def generate_html(records: list[dict], narrative: str | None, out_path: Path, title_prefix: str = "") -> bool:
  try:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = _build_html(records, narrative, title_prefix=title_prefix)
    with open(out_path, "w", encoding="utf-8") as f:
      f.write(html)
    log.info("HTML report written to %s", out_path)
    return True
  except Exception as e:
    log.error("Failed to write HTML: %s", e, exc_info=True)
    return False


def generate_pdf(records: list[dict], narrative: str | None, out_path: Path, title_prefix: str = "") -> bool:
  try:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = _build_html(records, narrative, title_prefix=title_prefix)
    WeasyHTML(string=html).write_pdf(str(out_path))
    log.info("PDF report written to %s", out_path)
    return True
  except Exception as e:
    log.error("Failed to write PDF: %s", e, exc_info=True)
    return False


def _build_summary_for_ai(records: list[dict]) -> str:
  lines = []
  for rec in records:
    status = "Hadir" if rec["attended"] else "Belum"
    lines.append(f"- [{status}] {rec['sub_entry']} ({rec['program']}, {rec['date']})")
  return "\n".join(lines[:50])


def _maybe_generate_narrative(records: list[dict]) -> str | None:
  if not is_generative_ai_available():
    log.info("AI unavailable — skipping narrative generation")
    return None
  summary = _build_summary_for_ai(records)
  prompt = generate_report_narrative_prompt(summary)
  return generate_content(prompt)


def generate_reports(kkn: KKN, output_dir: Path | None = None, title_prefix: str = "") -> dict[str, Path]:
  """Generate ICS + HTML + PDF reports. Returns dict of format->path."""
  records = _collect_attendance_data(kkn.main_program, kkn.assisted_program)
  log.info("Collected %d attendance records", len(records))

  out_dir = output_dir or REPORT_DIR
  timestamp = datetime.now().strftime("%Y%m%d_%H%M")
  prefix = f"{title_prefix}-" if title_prefix else ""
  ics_path = out_dir / f"{prefix}kkn-attendance-{timestamp}.ics"
  html_path = out_dir / f"{prefix}kkn-report-{timestamp}.html"
  pdf_path = out_dir / f"{prefix}kkn-report-{timestamp}.pdf"

  results = {}

  narrative = None
  try:
    narrative = _maybe_generate_narrative(records)
  except Exception as e:
    log.warning("Narrative generation failed (non-fatal): %s", e)

  if generate_ics(records, ics_path):
    results["ics"] = ics_path
  if generate_html(records, narrative, html_path, title_prefix=title_prefix):
    results["html"] = html_path
  if generate_pdf(records, narrative, pdf_path, title_prefix=title_prefix):
    results["pdf"] = pdf_path

  return results


async def generate_report_headless(username: str, password: str) -> bool:
  """Login, fetch KKN data, generate reports. For CLI --report / GitHub Actions."""
  log.info("Starting headless report generation")
  simaster_acc = Simaster(username, password)

  if not (session := await simaster_acc.login(verbose=False)):
    print_log("Login failed — cannot generate report", "ERROR")
    return False

  kkn = KKN(session, simaster_acc, autostart=True)
  if kkn.loader:
    await kkn.loader

  results = generate_reports(kkn)
  if results:
    print_log(f"Reports generated: {', '.join(f'{k}={v}' for k, v in results.items())}", "SUCCESS")
    await session.aclose()
    return True

  print_log("Report generation produced no files", "ERROR")
  await session.aclose()
  return False


async def generate_report_interactive(kkn: KKN):
  """Generate reports from within the interactive TUI (option 6)."""
  if kkn.loader and not kkn.loader.done():
    with console.status("[blue]Fetching KKN data for report...", spinner="dots"):
      await kkn.loader

  results = generate_reports(kkn)
  if results:
    print_log(f"Reports generated: {', '.join(str(v) for v in results.values())}", "SUCCESS")
  else:
    print_log("Report generation failed", "ERROR")
