import asyncio
import os
import sys

from dotenv import load_dotenv
from prompt_toolkit import HTML
from tap import Tap

import actions
from ui.tui import console, print_choice, print_log, print_title, prompt_session
from utils.attendance import handle_attendance, handle_check_status
from utils.common import async_input
from utils.kkn import KKN
from utils.logger import setup_logging
from utils.simaster import Simaster

CLIENT_ID = "e6abd4e380a5462e83873fe22ab8c219yVaU"
CLIENT_SECRET = "THFnhmQ6jckSWWzV6m9Mj78CexLCKjd009f4h9gQaIo8fUUULOhWP7DD"
REDIRECT_URI = "id.ac.ugm.student.vnext.simaster://oauth2"


class Parser(Tap):
  submit: bool = False  # Submit your attendance
  check: bool = False  # Check whether if you have logged in or not
  report: bool = False  # Generate attendance report
  headless: bool = False  # Run without interactive prompts (for cron/CI)
  dry_run: bool = False  # Validate everything but skip the final check-in POST
  verify: bool = False  # After submit, verify each user's active session
  group_report: bool = False  # Generate per-user reports for all SIMASTER_CREDENTIALS

  def configure(self):
    self.add_argument("-s", "--submit")
    self.add_argument("-c", "--check")
    self.add_argument("-r", "--report")


async def main_async(username: str, password: str):
  simaster_acc = Simaster(username, password)

  if not (session := await simaster_acc.login(verbose=True)):
    return

  kkn_manager = KKN(session, simaster_acc)

  first = True
  while True:
    print_title() if not first else print()
    first = False

    print_choice()
    choice = await async_input(
      HTML('Enter your choice <delim fg="#89dceb">(<num fg="#fab387">1<dash fg="#89dceb">-</dash>9</num>): </delim>')
    )
    print()

    try:
      if choice == "1":
        handle_attendance(username, password)
      elif choice == "2":
        await actions.show_all_program(kkn_manager)
      elif choice == "3":
        await actions.add_new_entry(kkn_manager)
      elif choice == "4":
        await actions.add_new_sub_entry(kkn_manager)
      elif choice == "5":
        await actions.handle_unattended_entries(kkn_manager)
        pass
      elif choice == "6":
        from utils.report import generate_report_interactive

        await generate_report_interactive(kkn_manager)
      elif choice == "7":
        if result := await actions.change_account():
          simaster_acc, session, kkn_manager = result
          username = simaster_acc.username
          password = simaster_acc.password
      elif choice == "8":
        kkn_manager.start()
        console.print("[blue]Data refresh started in background...")
      elif choice == "9":
        console.print("[yellow]Exiting...[/]")
        if kkn_manager.loader and not kkn_manager.loader.done():
          kkn_manager.loader.cancel()
        break
      else:
        print_log(f"Invalid Choice ({choice}). Please try again")

      with console.status("Press Enter to return to the main menu...", spinner="dots"):
        await async_input()

      # HACK: we need to remove the spinner somehow since it doesn't work with input()...
      print("\033[A\033[K")
    except (KeyboardInterrupt, asyncio.CancelledError, EOFError):
      print()
      print_log("Action interrupted! returning to Main Menu[#89dceb]...")
      print()


def signal_handler(_sig, _frame):
  print()
  print_log("Program interrupted by user, exiting...")
  os._exit(0)


def main() -> int:
  args = Parser().parse_args()
  log = setup_logging(headless=args.headless)

  if not args.headless:
    print_title()

  username = os.getenv("SIMASTER_USERNAME") or prompt_session.prompt(HTML('Username<delim fg="#89dceb">:</delim> '))
  password = os.getenv("SIMASTER_PASSWORD") or prompt_session.prompt(
    HTML('Password<delim fg="#89dceb">:</delim> '), is_password=True
  )

  try:
    if args.submit:
      ok = handle_attendance(username, password, headless=args.headless, dry_run=args.dry_run, verify=args.verify)
      if args.report:
        _generate_report_headless(username, password)
      if args.group_report:
        _generate_group_report()
      return 0 if ok else 1
    elif args.check:
      ok = handle_check_status(username, password)
      return 0 if ok else 1
    elif args.report:
      ok = _generate_report_headless(username, password)
      if args.group_report:
        _generate_group_report()
      return 0 if ok else 1
    elif args.group_report:
      ok = _generate_group_report()
      return 0 if ok else 1
    elif args.dry_run:
      ok = handle_attendance(username, password, headless=True, dry_run=True, verify=args.verify)
      return 0 if ok else 1
    else:
      asyncio.run(main_async(username, password))
      return 0
  except KeyboardInterrupt:
    print()
    print_log("Program interrupted! Exiting[#89dceb]...")
    return 130
  except Exception as e:
    log.error("Fatal error in main: %s", e, exc_info=True)
    return 1


def _generate_report_headless(username: str, password: str) -> bool:
  try:
    from utils.report import generate_report_headless

    return asyncio.run(generate_report_headless(username, password))
  except Exception as e:
    setup_logging().error("Report generation failed: %s", e, exc_info=True)
    return False


def _generate_group_report() -> bool:
  try:
    from utils.group_report import generate_group_reports

    return asyncio.run(generate_group_reports())
  except Exception as e:
    setup_logging().error("Group report generation failed: %s", e, exc_info=True)
    return False


if __name__ == "__main__":
  load_dotenv()
  sys.exit(main())
