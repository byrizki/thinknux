"""Main application entry point for ThinkNux."""

import sys

from .ui.app import ThinkNuxApplication


def main() -> int:
    app = ThinkNuxApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
