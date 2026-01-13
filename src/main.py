import asyncio
import getpass
import os

from dotenv import load_dotenv
from tap import Tap

import actions
from ui.tui import console, print_choice, print_title
from utils.attendance import handle_check_status, handle_checkin
from utils.common import async_input, load_background
from utils.kkn import KKN
from utils.simaster import Simaster

CLIENT_ID = "e6abd4e380a5462e83873fe22ab8c219yVaU"
CLIENT_SECRET = "THFnhmQ6jckSWWzV6m9Mj78CexLCKjd009f4h9gQaIo8fUUULOhWP7DD"
REDIRECT_URI = "id.ac.ugm.student.vnext.simaster://oauth2"


class Parser(Tap):
    submit: bool = False  # Submit your attendance
    check: bool = False  # Check whether if you have logged in or not

    def configure(self):
        self.add_argument("-s", "--submit")
        self.add_argument("-c", "--check")


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
        choice = await async_input("Enter your choice [cyan]([#fab387]1[cyan]-[/]9[/])[/]")
        print()

        if choice == "1":
            handle_checkin(username, password)
        elif choice == "2":
            await actions.show_all_program(kkn_manager)
        elif choice == "3":
            await actions.add_new_entry(kkn_manager)
        elif choice == "4":
            await actions.add_new_sub_entry(kkn_manager)
        elif choice == "5":
            # await actions.handle_unattended_entries(kkn_manager)
            pass
        elif choice == "6":
            await load_background("[blue]Background fetch in progress...[/]", kkn_manager.loader)
            # TODO: handle report generation
            pass
        elif choice == "7":
            if result := await actions.change_account():
                simaster_acc, session, kkn_manager = result
                username = simaster_acc.username
                password = simaster_acc.password
        elif choice == "8":
            kkn_manager.loader = asyncio.create_task(kkn_manager._load_all(kkn_manager.simaster_account))
            console.print("[green]Data refresh started in background...[/]")
        elif choice == "9":
            console.print("[yellow]Exiting...[/]")
            if not kkn_manager.loader.done():
                kkn_manager.loader.cancel()
            break
        else:
            console.print("[yellow] [/]Invalid Choice. Please try again")

        with console.status("Press Enter to return to the main menu...", spinner="dots"):
            input()

        # HACK: we need to remove the spinner somehow since it doesn't work with input()...
        print("\033[A\033[K")


def main():
    args = Parser().parse_args()

    print_title()
    username = os.getenv("SIMASTER_USERNAME") or input("Username: ")
    password = os.getenv("SIMASTER_PASSWORD") or getpass.getpass()

    if args.submit:
        handle_checkin(username, password)
    elif args.check:
        handle_check_status(username, password)
    else:
        asyncio.run(main_async(username, password))


if __name__ == "__main__":
    load_dotenv()
    main()
