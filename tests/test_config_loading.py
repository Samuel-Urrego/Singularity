"""Tests for TOML config file loading and validation."""

import pytest
from pydantic import ValidationError

from singularity.cli.config import (
    ConnectionConfig,
    OutputConfig,
    SingularityConfig,
    SpSelectionConfig,
    load_config,
)


class TestConnectionConfig:
    """ConnectionConfig validation and connection string building."""

    def test_valid_trusted(self) -> None:
        """Windows Authentication builds correct connection string."""
        cfg = ConnectionConfig(
            server="localhost",
            database="AdventureWorks",
            trusted_connection=True,
        )
        conn_str = cfg.build_connection_string()
        assert "DRIVER=" in conn_str
        assert "SERVER=localhost" in conn_str
        assert "DATABASE=AdventureWorks" in conn_str
        assert "Trusted_Connection=yes" in conn_str

    def test_valid_sql_auth(self) -> None:
        """SQL Server Authentication builds correct connection string."""
        cfg = ConnectionConfig(
            server="localhost",
            database="TestDB",
            trusted_connection=False,
            username="sa",
            password="secret123",
        )
        conn_str = cfg.build_connection_string()
        assert "UID=sa" in conn_str
        assert "PWD=secret123" in conn_str
        assert "Trusted_Connection=yes" not in conn_str

    def test_required_server(self) -> None:
        """server is a required field."""
        with pytest.raises(ValidationError) as exc:
            ConnectionConfig(database="TestDB")
        assert "server" in str(exc.value)

    def test_required_database(self) -> None:
        """database is a required field."""
        with pytest.raises(ValidationError) as exc:
            ConnectionConfig(server="localhost")
        assert "database" in str(exc.value)

    def test_default_driver(self) -> None:
        """Default driver is ODBC Driver 18."""
        cfg = ConnectionConfig(server="localhost", database="TestDB")
        assert "ODBC Driver 18" in cfg.driver


class TestSpSelectionConfig:
    """SpSelectionConfig validation."""

    def test_empty_selection_allowed(self) -> None:
        """Both fields can be None."""
        cfg = SpSelectionConfig()
        assert cfg.procedures is None
        assert cfg.pattern is None

    def test_explicit_list(self) -> None:
        """A list of procedures is accepted."""
        cfg = SpSelectionConfig(procedures=["usp_A", "usp_B"])
        assert cfg.procedures == ["usp_A", "usp_B"]

    def test_wildcard_pattern(self) -> None:
        """A pattern string is accepted."""
        cfg = SpSelectionConfig(pattern="usp_%")
        assert cfg.pattern == "usp_%"


class TestOutputConfig:
    """OutputConfig defaults and validation."""

    def test_default_mode(self) -> None:
        """Default mode is 'source'."""
        cfg = OutputConfig()
        assert cfg.mode == "source"

    def test_valid_modes(self) -> None:
        """Both 'dynamic' and 'source' are accepted."""
        OutputConfig(mode="dynamic")
        OutputConfig(mode="source")

    def test_invalid_mode(self) -> None:
        """Invalid mode raises ValidationError."""
        with pytest.raises(ValidationError):
            OutputConfig(mode="invalid")

    def test_default_naming_convention(self) -> None:
        """Default naming_convention is 'snake_case'."""
        cfg = OutputConfig()
        assert cfg.naming_convention == "snake_case"

    def test_valid_conventions(self) -> None:
        """All three naming conventions are accepted."""
        OutputConfig(naming_convention="snake_case")
        OutputConfig(naming_convention="camelCase")
        OutputConfig(naming_convention="PascalCase")

    def test_invalid_convention(self) -> None:
        """Invalid naming_convention raises ValidationError."""
        with pytest.raises(ValidationError):
            OutputConfig(naming_convention="kebab-case")

    def test_default_directory(self) -> None:
        """Default directory is '.'."""
        cfg = OutputConfig()
        assert cfg.directory == "."

    def test_default_file_naming(self) -> None:
        """Default file_naming is '{sp_name}.py'."""
        cfg = OutputConfig()
        assert cfg.file_naming == "{sp_name}.py"


class TestSingularityConfig:
    """Top-level SingularityConfig validation."""

    def test_minimal_valid(self) -> None:
        """A config with only required fields parses successfully."""
        cfg = SingularityConfig(
            connection=ConnectionConfig(server="localhost", database="TestDB"),
            sp_selection=SpSelectionConfig(procedures=["usp_Test"]),
        )
        assert cfg.connection.server == "localhost"
        assert cfg.sp_selection.procedures == ["usp_Test"]
        assert cfg.output.mode == "source"  # default

    def test_custom_output_overrides_default(self) -> None:
        """Custom output settings override defaults."""
        cfg = SingularityConfig(
            connection=ConnectionConfig(server="localhost", database="TestDB"),
            sp_selection=SpSelectionConfig(procedures=["usp_Test"]),
            output=OutputConfig(mode="dynamic", naming_convention="camelCase"),
        )
        assert cfg.output.mode == "dynamic"
        assert cfg.output.naming_convention == "camelCase"


class TestLoadConfig:
    """load_config() reads and validates TOML files."""

    def test_load_valid(self, valid_toml_path) -> None:
        """A valid TOML file returns a populated SingularityConfig."""
        cfg = load_config(valid_toml_path)
        assert cfg.connection.server == "localhost"
        assert cfg.connection.database == "AdventureWorks"
        assert cfg.sp_selection.procedures == ["usp_GetOrders", "usp_GetCustomers"]
        assert cfg.output.directory == "models"
        assert cfg.output.mode == "source"
        assert cfg.output.naming_convention == "snake_case"
        assert cfg.output.file_naming == "{schema}_{sp_name}.py"

    def test_missing_file(self) -> None:
        """A non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.toml")

    def test_invalid_toml(self, tmp_path) -> None:
        """Invalid TOML raises an error."""
        bad = tmp_path / "bad.toml"
        bad.write_text("[[connection]\nserver = broken")
        with pytest.raises(ValueError):
            load_config(bad)

    def test_missing_required_field(self, tmp_path) -> None:
        """A TOML file missing required fields raises ValidationError."""
        bad = tmp_path / "missing.toml"
        bad.write_text(
            "[connection]\n"
            'server = "localhost"\n'
            # missing 'database'
            "\n"
            "[sp_selection]\n"
            'procedures = ["usp_Test"]\n'
        )
        with pytest.raises(ValidationError):
            load_config(bad)

    def test_empty_file(self, tmp_path) -> None:
        """An empty TOML file raises ValidationError."""
        empty = tmp_path / "empty.toml"
        empty.write_text("")
        with pytest.raises(ValidationError):
            load_config(empty)
