"""Tests for SQL Server version detection from @@VERSION output."""

from singularity.version import ServerVersion, parse_version_string


class TestParseVersionString:
    """parse_version_string() correctly identifies SQL Server versions."""

    def test_modern_2016(self) -> None:
        """A version string containing '2016' is detected as MODERN."""
        result = parse_version_string("Microsoft SQL Server 2016 (RTM) - 13.0.1601.5")
        assert result == ServerVersion.MODERN

    def test_modern_2017(self) -> None:
        """A version string containing '2017' is detected as MODERN."""
        result = parse_version_string("Microsoft SQL Server 2017 (RTM) - 14.0.1000.169")
        assert result == ServerVersion.MODERN

    def test_modern_2019(self) -> None:
        """A version string containing '2019' is detected as MODERN."""
        result = parse_version_string("Microsoft SQL Server 2019 (RTM) - 15.0.2000.5")
        assert result == ServerVersion.MODERN

    def test_modern_2022(self) -> None:
        """A version string containing '2022' is detected as MODERN."""
        result = parse_version_string(
            "Microsoft SQL Server 2022 (RTM-GDR) - 16.0.1050.5"
        )
        assert result == ServerVersion.MODERN

    def test_legacy_2008(self) -> None:
        """A version string containing '2008' (not 2016+) is detected as LEGACY."""
        result = parse_version_string("Microsoft SQL Server 2008 R2 (SP3) - 10.50.6000.34")
        assert result == ServerVersion.LEGACY

    def test_legacy_2012(self) -> None:
        """A version string containing '2012' is detected as LEGACY."""
        result = parse_version_string("Microsoft SQL Server 2012 (SP4) - 11.0.7507.2")
        assert result == ServerVersion.LEGACY

    def test_legacy_2014(self) -> None:
        """A version string containing '2014' is detected as LEGACY."""
        result = parse_version_string("Microsoft SQL Server 2014 (SP3) - 12.0.6433.1")
        assert result == ServerVersion.LEGACY

    def test_azure(self) -> None:
        """A version string containing 'Azure SQL' is detected as AZURE."""
        result = parse_version_string(
            "Microsoft SQL Azure (RTM) - 12.0.2000.8\n"
            "\tCopyright (c) Microsoft Corporation"
        )
        assert result == ServerVersion.AZURE

    def test_azure_different_format(self) -> None:
        """Azure detection works regardless of surroundings."""
        result = parse_version_string(
            "Azure SQL Database v12.0.2000.8 (some additional info)"
        )
        assert result == ServerVersion.AZURE

    def test_case_insensitive_azure(self) -> None:
        """Azure detection is case-insensitive."""
        result = parse_version_string("microsoft sql azure (rtm)")
        assert result == ServerVersion.AZURE

    def test_unknown_version_falls_to_legacy(self) -> None:
        """An unrecognised version string defaults to LEGACY."""
        result = parse_version_string("Some unknown database v1.0")
        assert result == ServerVersion.LEGACY
