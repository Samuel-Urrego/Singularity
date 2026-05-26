"""Custom exception hierarchy for Singularity."""


class SingularityError(Exception):
    """Base exception for all Singularity errors."""


class SpNotFoundError(SingularityError):
    """Raised when a requested stored procedure does not exist."""

    def __init__(self, sp_name: str) -> None:
        self.sp_name = sp_name
        super().__init__(f"Stored procedure '{sp_name}' not found in the database.")
