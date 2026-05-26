"""CLI generate command — orchestrates the full pipeline.

Delegates all introspection and model generation to the library.
Never reimplements library logic.
"""

from __future__ import annotations

from pathlib import Path

import typer

from singularity.cli._app import app
from singularity.cli.config import load_config
from singularity.introspector import SQLServerIntrospector
from singularity.model_generator import generate_model


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
        typer.secho(
            f"Error: Config file not found: {cfg_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        cfg = load_config(str(cfg_path))
    except Exception as exc:
        typer.secho(
            f"Error loading config: {exc}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc

    # --- Connect to SQL Server ---------------------------------------------
    conn_str = cfg.connection.build_connection_string()
    introspector = SQLServerIntrospector(conn_str)

    try:
        introspector.connect()
        version = introspector.detect_version()
        typer.echo(f"Connected. Detected version: {version.value}")
    except Exception as exc:
        typer.secho(
            f"Error connecting to SQL Server: {exc}",
            fg=typer.colors.RED,
            err=True,
        )
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
            typer.secho(
                f"Error resolving SP pattern '{cfg.sp_selection.pattern}': {exc}",
                fg=typer.colors.YELLOW,
                err=True,
            )

    if not sp_names:
        typer.secho(
            "No stored procedures selected. Check your [sp_selection] config.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=0)

    # --- Introspect each SP and generate models ----------------------------
    out_dir = Path(cfg.output.directory)
    out_dir.mkdir(parents=True, exist_ok=True)

    naming_convention = cfg.output.naming_convention
    mode = cfg.output.mode
    file_naming = cfg.output.file_naming

    success_count = 0
    error_count = 0

    for sp_name in sp_names:
        try:
            typer.echo(f"  Introspecting {sp_name}...", nl=False)

            meta = introspector.introspect(sp_name)

            result = generate_model(
                meta,
                mode=mode,
                naming_convention=naming_convention,
            )

            if mode == "source":
                # Build file name from template
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
                    typer.echo(f" → {filepath}")
                else:
                    # Should not happen in source mode
                    typer.echo(" → unexpected type returned", err=True)
                    error_count += 1
                    continue
            else:
                # dynamic mode — show class info
                typer.echo(f" → {result.__name__} (dynamic)")  # type: ignore[union-attr]

            success_count += 1

        except Exception as exc:
            typer.secho(
                f"  Error processing {sp_name}: {exc}",
                fg=typer.colors.RED,
                err=True,
            )
            error_count += 1

    # --- Summary -----------------------------------------------------------
    typer.echo("")
    typer.echo(f"Done. {success_count} succeeded, {error_count} failed.")
    if error_count > 0:
        raise typer.Exit(code=1)
