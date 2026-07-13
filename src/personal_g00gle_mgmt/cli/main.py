"""pg0: unified CLI for the personal-g00gle-mgmt workspace.

Every capability exposed here is a thin, first-class front end over the same
underlying REST implementations (CLAUDE.md Rule 7, entry-point parity) - not
a reimplementation of them.
"""

import typer

from . import gmail

app = typer.Typer(
    name="pg0",
    help="Personal Google workspace management CLI.",
    no_args_is_help=True,
)
app.add_typer(gmail.app, name="gmail")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
