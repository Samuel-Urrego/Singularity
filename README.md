# Singularity

> SQL Server → Pydantic v2. Automatically.

[![CI](https://github.com/Samuel-Urrego/Singularity/actions/workflows/ci.yml/badge.svg)](https://github.com/Samuel-Urrego/Singularity/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/singularity.svg)](https://pypi.org/project/singularity/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Singularity bridges the gap between SQL Server and Python. Connect to your database, point at a stored procedure, and get a **Pydantic v2 model** — as a runtime class or a `.py` file you can commit.

```bash
singularity --config config.toml
```

```python
from singularity import SQLServerIntrospector, generate_model

introspector = SQLServerIntrospector("DRIVER={ODBC Driver 17};SERVER=...;DATABASE=...")
meta = introspector.introspect("usp_GetOrders")
model = generate_model(meta, mode="dynamic")
# <class 'pydantic.main.UspGetOrders'>
```

## Why Singularity?

**The problem**: You have dozens of complex stored procedures in SQL Server. Calling them from Python means manually writing Pydantic models for every parameter and result set. One typo, and you get a runtime error.

**The solution**: Singularity reads SQL Server's system catalog (`sys.parameters`, `sp_describe_first_result_set`) and generates the models for you. Zero manual mapping.

| Approach | Lines of code | Maintainable | Type-safe |
|---|---|---|---|
| Manual Pydantic models | 100s–1000s | ❌ | ⚠️ (manual) |
| Raw dicts / tuples | Fewer | ❌ | ❌ |
| **Singularity** | **Zero** | ✅ | ✅ |

## Features

- 🔌 **Auto-connect** — pyodbc connection with `@@VERSION` detection
- 🧠 **Version-aware** — Modern (2016+), Legacy (2008–2014), and Azure SQL strategies
- 📦 **Two output modes**:
  - `"dynamic"` — `create_model()` at runtime, usable immediately
  - `"source"` — `.py` files you can commit and review
- 🏷️ **Full type mapping** — `INT`→`int`, `VARCHAR`→`str`, `DATETIME`→`datetime`, `BIT`→`bool`, etc.
- 🎨 **Configurable naming** — snake_case, camelCase, PascalCase for field names
- 🗂️ **File naming templates** — `{schema}_{sp_name}.py`, `{database}_{sp_name}.py`, etc.
- 🛡️ **Nullable awareness** — `Optional[T]` for nullable columns
- ⚡ **UV-first** — fast dependency management

## Installation

```bash
uv add singularity
# or
pip install singularity
```

**Prerequisite**: [ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) (17 or 18).

## Quick Start

### 1. Create a config file

```toml
# config.toml
[connection]
server = "localhost"
database = "AdventureWorks"
driver = "ODBC Driver 18 for SQL Server"
trusted_connection = true

[sp_selection]
pattern = "usp_%"

[output]
directory = "generated_models"
mode = "source"
file_naming = "{schema}_{sp_name}.py"
naming_convention = "snake_case"
```

### 2. Generate models

```bash
singularity --config config.toml
```

```
Connected. Detected version: modern
  Introspecting usp_GetOrders... → generated_models/dbo_usp_GetOrders.py
  Introspecting usp_GetCustomers... → generated_models/dbo_usp_GetCustomers.py

Done. 2 succeeded, 0 failed.
```

### 3. Use the generated models

```python
from generated_models.dbo_usp_GetOrders import UspGetOrders

order = UspGetOrders(id=1, customer_name="Acme Corp", total=99.99)
```

## Library Usage

```python
from singularity import SQLServerIntrospector, generate_model

# Connect and introspect
introspector = SQLServerIntrospector(conn_str)
introspector.connect()
version = introspector.detect_version()  # ServerVersion.MODERN
metadata = introspector.introspect("usp_GetOrders")

# Runtime model
DynamicModel = generate_model(metadata, mode="dynamic")
instance = DynamicModel(id=1, customer_name="Acme")

# Source code string
source_code = generate_model(metadata, mode="source")
with open("models/usp_GetOrders.py", "w") as f:
    f.write(source_code)
```

## Configuration Reference

### `[connection]`

| Field | Required | Default | Description |
|---|---|---|---|
| `server` | ✅ | — | Server hostname or IP |
| `database` | ✅ | — | Database name |
| `driver` | ❌ | `ODBC Driver 18 for SQL Server` | ODBC driver name |
| `trusted_connection` | ❌ | `true` | Use Windows auth |
| `username` | ❌ | — | SQL auth username |
| `password` | ❌ | — | SQL auth password |

### `[sp_selection]`

| Field | Required | Description |
|---|---|---|
| `procedures` | ❌ | Explicit list of SP names |
| `pattern` | ❌ | Wildcard pattern (e.g. `usp_%`) |

At least one of `procedures` or `pattern` must be specified.

### `[output]`

| Field | Required | Default | Description |
|---|---|---|---|
| `directory` | ❌ | `.` | Output directory |
| `mode` | ❌ | `source` | `source` or `dynamic` |
| `file_naming` | ❌ | `{sp_name}.py` | Template with `{schema}`, `{database}`, `{sp_name}` |
| `naming_convention` | ❌ | `snake_case` | `snake_case`, `camelCase`, or `PascalCase` |

## Supported SQL Server Versions

| Version | Strategy | Parameter introspection | Result set metadata |
|---|---|---|---|
| 2016+ | Modern | `sys.parameters` | `sp_describe_first_result_set` |
| 2008–2014 | Legacy | `sys.parameters` | `sp_describe_first_result_set` + `sys.columns` fallback |
| Azure SQL | Azure | `sys.parameters` | `sys.dm_exec_describe_first_result_set` |

## Type Mapping

| SQL Server | Python | Pydantic |
|---|---|---|
| `INT`, `BIGINT`, `SMALLINT`, `TINYINT` | `int` | `int` |
| `VARCHAR`, `NVARCHAR`, `CHAR`, `NCHAR`, `TEXT` | `str` | `str` |
| `DATETIME`, `DATETIME2`, `DATE`, `SMALLDATETIME` | `datetime` | `datetime` |
| `BIT` | `bool` | `bool` |
| `DECIMAL`, `NUMERIC`, `FLOAT`, `REAL`, `MONEY` | `float` | `float` |
| `UNIQUEIDENTIFIER` | `str` | `str` |
| Unknown types | `str` + warning | `str` |

## Development

```bash
# Clone and install
git clone https://github.com/Samuel-Urrego/Singularity
cd singularity
uv sync

# Run tests
uv run pytest

# Lint and type-check
uv run ruff check .
uv run mypy singularity/

# Install pre-commit hooks
uv run pre-commit install
```

## License

MIT — see [LICENSE](LICENSE) for details.
