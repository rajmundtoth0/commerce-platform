"""Small operational CLI shared by the platform.

`platform-admin projections` lists the registered projection contracts (name,
versions, key template) — handy for ops to see what the read model exposes.
"""

from __future__ import annotations

import json

import typer

from cplatform.contracts import ALL_SPECS

app = typer.Typer(help="commerce-platform admin CLI", no_args_is_help=True)


@app.command()
def projections() -> None:
    """List registered projection contracts and their versioned key templates."""
    typer.echo(json.dumps([spec.metadata() for spec in ALL_SPECS], indent=2))


if __name__ == "__main__":
    app()
