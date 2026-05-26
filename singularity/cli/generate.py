"""CLI generate command — orchestrates the full pipeline.

Delegates all introspection and model generation to the library.
Never reimplements library logic.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
)
from rich.table import Table

from singularity.cli._app import app
from singularity.cli.config import load_config
from singularity.introspector import SQLServerIntrospector
from singularity.model_generator import generate_model

console = Console()


@app.command()
def generate(
    config: str = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to TOML configuration file.",
    ),
) -> None:
    """Introspect stored procedures and generate Pydantic models.

    Reads configuration from a TOML file, connects to SQL Server,
    introspects the specified stored procedures, and writes the
    generated models to the output directory.
    """
    # --- Load config -------------------------------------------------------
    cfg_path = Path(config)
    if not cfg_path.exists():
        console.print(f"[red]Error:[/red] Config file not found: [bold]{cfg_path}[/bold]")
        raise typer.Exit(code=1)

    try:
        cfg = load_config(str(cfg_path))
    except Exception as exc:
        console.print(f"[red]Error loading config:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # --- Connect to SQL Server ---------------------------------------------
    conn_str = cfg.connection.build_connection_string()
    introspector = SQLServerIntrospector(conn_str)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Connecting to SQL Server...", total=None)
            introspector.connect()
            version = introspector.detect_version()
        console.print(f"[green]Connected.[/green] Detected version: [bold]{version.value}[/bold]")
    except Exception as exc:
        console.print(f"[red]Error connecting to SQL Server:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # --- Resolve SPs to introspect -----------------------------------------
    sp_names: list[str] = []

    if cfg.sp_selection.procedures:
        sp_names.extend(cfg.sp_selection.procedures)

    if cfg.sp_selection.pattern:
        try:
            cursor = introspector._connection.cursor()  # type: ignore[union-attr]
            cursor.execute(
                """
                SELECT ROUTINE_NAME
                FROM INFORMATION_SCHEMA.ROUTINES
                WHERE ROUTINE_TYPE = 'PROCEDURE'
                  AND ROUTINE_NAME LIKE ?
                """,
                (cfg.sp_selection.pattern,),
            )
            sp_names.extend(row[0] for row in cursor.fetchall())
        except Exception as exc:
            console.print(
                f"[yellow]Error resolving SP pattern '{cfg.sp_selection.pattern}':[/yellow] {exc}"
            )

    if not sp_names:
        console.print(
            "[yellow]No stored procedures selected.[/yellow] "
            "Check your [bold][sp_selection][/bold] config."
        )
        raise typer.Exit(code=0)

    # --- Introspect each SP and generate models ----------------------------
    out_dir = Path(cfg.output.directory)
    out_dir.mkdir(parents=True, exist_ok=True)

    naming_convention = cfg.output.naming_convention
    mode = cfg.output.mode
    file_naming = cfg.output.file_naming

    summary_data: list[dict[str, str | int]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Introspecting [bold]{len(sp_names)}[/bold] stored procedure(s)...",
            total=len(sp_names),
        )

        for sp_name in sp_names:
            try:
                meta = introspector.introspect(sp_name)

                result = generate_model(
                    meta,
                    mode=mode,
                    naming_convention=naming_convention,
                )

                if mode == "source":
                    parts = sp_name.split(".")
                    schema = parts[0] if len(parts) > 1 else "dbo"
                    filename = file_naming.format(
                        sp_name=sp_name,
                        schema=schema,
                        database=cfg.connection.database,
                    )
                    filepath = out_dir / filename

                    if isinstance(result, str):
                        filepath.write_text(result, encoding="utf-8")
                    else:
                        console.print(
                            f"[red]  {sp_name}:[/red] unexpected type returned"
                        )
                        summary_data.append({
                            "sp_name": sp_name,
                            "params": len(meta.parameters),
                            "columns": len(meta.columns),
                            "status": "ERROR",
                        })
                        progress.advance(task)
                        continue
                else:
                    pass  # dynamic mode

                summary_data.append({
                    "sp_name": sp_name,
                    "params": len(meta.parameters),
                    "columns": len(meta.columns),
                    "status": "OK",
                })

            except Exception as exc:
                console.print(f"[red]  Error processing {sp_name}:[/red] {exc}")
                summary_data.append({
                    "sp_name": sp_name,
                    "params": 0,
                    "columns": 0,
                    "status": "ERROR",
                })

            progress.advance(task)

    # --- Summary table -----------------------------------------------------
    table = Table(title="Generation Summary")
    table.add_column("SP Name", style="cyan")
    table.add_column("Params", justify="right")
    table.add_column("Columns", justify="right")
    table.add_column("Status")

    success_count = 0
    error_count = 0
    for row in summary_data:
        status = row["status"]
        if status == "OK":
            status_style = "[green]OK[/green]"
            success_count += 1
        else:
            status_style = "[red]ERROR[/red]"
            error_count += 1
        table.add_row(
            str(row["sp_name"]),
            str(row["params"]),
            str(row["columns"]),
            status_style,
        )

    console.print(table)
    console.print(
        f"\nDone. [green]{success_count} succeeded[/green], "
        f"[red]{error_count} failed[/red]."
    )

    if error_count > 0:
        raise typer.Exit(code=1)
