"""Titik masuk: `tickerquill`, `tickerquill-gui` (tanpa jendela konsol) dan `python -m tickerquill`."""
import argparse
import os
import sys
from pathlib import Path

from . import __version__


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="tickerquill", description="TickerQuill: YouTube stock video -> Whisper -> structured summary.")
    parser.add_argument("--version", action="version", version=f"TickerQuill {__version__}")
    parser.add_argument("--data", metavar="FOLDER",
                        help="use FOLDER for settings, cache, archive and transcripts (same as TICKERQUILL_HOME)")
    parser.add_argument("--where", action="store_true", help="print the data folder and exit")
    parser.add_argument("--shortcut", action="store_true",
                        help="create a shortcut with the app icon (Start Menu + Desktop, ~/Applications, or the app menu)")
    parser.add_argument("--remove-shortcut", action="store_true", help="remove the shortcuts made by --shortcut")
    parser.add_argument("--migrate", metavar="OLD_FOLDER",
                        help="copy .env, settings.json, cache, analyses and transcripts from an older install")
    args = parser.parse_args(argv)
    if args.data:  # sebelum app diimpor: lokasi data dibaca saat impor
        os.environ["TICKERQUILL_HOME"] = str(Path(args.data).expanduser().resolve())

    from . import paths

    if args.where:
        print(paths.data_dir())
        return 0
    if args.migrate:
        copied = paths.migrate(args.migrate)
        print(f"Copied {len(copied)} files to {paths.data_dir()}")
        return 0
    if args.shortcut or args.remove_shortcut:
        from . import shortcuts

        done = shortcuts.create() if args.shortcut else shortcuts.remove()
        for path in done:
            print(path)
        if not done:
            print("Nothing to do.")
        return 0

    from .app import App

    App().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
