import sys

from tiff2png.cli import main as cli_main
from tiff2png.ui.app import main as gui_main

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(cli_main())
    gui_main()
