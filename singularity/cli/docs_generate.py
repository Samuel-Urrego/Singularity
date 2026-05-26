"""CLI docs command — generates Markdown documentation for stored procedures."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from singularity.cli._app import app
from singularity.cli.config import load_config
from singularity.introspector import SQLServerIntrospector
from singularity.model_generator import _generate_source
from singularity.types import SPMetadata

console = Console()


@app.command()
def docs(
    config: str = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to TOML configuration file.",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for documentation. Overrides config.",
    ),
) -> None:
    """Generate Markdown documentation for stored procedures.

    Introspects the configured stored procedures and writes a Markdown
    file per SP with parameter tables, result set columns, descriptions
    (from ``sys.extended_properties``), and the generated Pydantic model
    source code.
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

    # --- Resolve output directory ------------------------------------------
    docs_dir: Path
    if output:
        docs_dir = Path(output)
    elif cfg.output.docs_directory:
        docs_dir = Path(cfg.output.docs_directory)
    else:
        docs_dir = Path("docs")

    docs_dir.mkdir(parents=True, exist_ok=True)

    # --- Connect to SQL Server ---------------------------------------------
    conn_str = cfg.connection.build_connection_string()
    introspector = SQLServerIntrospector(conn_str)

    try:
        introspector.connect()
        version = introspector.detect_version()
        console.print(f"[green]Connected.[/green] Detected version: [bold]{version.value}[/bold]")
    except Exception as exc:
        console.print(f"[red]Error connecting to SQL Server:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # --- Resolve SPs -------------------------------------------------------
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

    # --- Generate docs -----------------------------------------------------
    success_count = 0
    error_count = 0

    for sp_name in sp_names:
        try:
            meta = introspector.introspect(sp_name)
            doc_content = _render_doc(meta)
            doc_path = docs_dir / f"{sp_name}.md"
            doc_path.write_text(doc_content, encoding="utf-8")
            console.print(f"  [green]✓[/green] {sp_name} → {doc_path}")
            success_count += 1
        except Exception as exc:
            console.print(f"  [red]✗[/red] {sp_name}: {exc}")
            error_count += 1

    console.print(
        f"\nDone. [green]{success_count} docs generated[/green], "
        f"[red]{error_count} failed[/red]."
    )
    if error_count > 0:
        raise typer.Exit(code=1)


def _render_doc(meta: SPMetadata) -> str:
    """Render a stored procedure's documentation as Markdown.

    Args:
        meta: Fully introspected SP metadata (includes descriptions).

    Returns:
        A Markdown string suitable for writing to a .md file.
    """
    lines: list[str] = []
    lines.append(f"# {meta.name}")
    lines.append("")

    # Schema
    schema = meta.name.split(".")[0] if "." in meta.name else "dbo"
    lines.append(f"**Schema:** {schema}")
    lines.append("")

    # --- Parameters table --------------------------------------------------
    if meta.parameters:
        lines.append("## Parameters")
        lines.append("")
        lines.append("| Name | Type | Direction | Default | Nullable | Description |")
        lines.append("|------|------|-----------|---------|----------|-------------|")
        for p in meta.parameters:
            name = p.name
            sql_type = p.sql_type
            direction = p.direction
            default = p.default or "—"
            nullable = "YES" if p.nullable else "NO"
            desc = p.description or "—"
            lines.append(
                f"| {name} | {sql_type} | {direction} | {default} | {nullable} | {desc} |"
            )
        lines.append("")

    # --- Result set(s) table -----------------------------------------------
    if meta.columns:
        lines.append("## Result Set")
        lines.append("")
        lines.append("| Column | Type | Nullable | Description |")
        lines.append("|--------|------|----------|-------------|")
        for col in meta.columns:
            name = col.name
            sql_type = col.sql_type
            nullable = "YES" if col.nullable else "NO"
            desc = col.description or "—"
            lines.append(f"| {name} | {sql_type} | {nullable} | {desc} |")
        lines.append("")

    # --- Generated model ---------------------------------------------------
    try:
        source_code = _generate_source(meta)
        lines.append("## Generated Model")
        lines.append("")
        lines.append("```python")
        lines.append(source_code.rstrip("\n"))
        lines.append("```")
        lines.append("")
    except Exception:
        lines.append("## Generated Model")
        lines.append("")
        lines.append("*Model generation failed for this stored procedure.*")
        lines.append("")

    return "\n".join(lines) + "\n"
