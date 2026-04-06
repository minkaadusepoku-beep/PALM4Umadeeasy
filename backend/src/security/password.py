"""Password complexity validation."""

import re


class PasswordValidationError(ValueError):
    pass


def validate_password(password: str) -> None:
    """Validate password meets complexity requirements.

    Raises PasswordValidationError if invalid.
    """
    errors: list[str] = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain a lowercase letter")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain an uppercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must contain a digit")

    if errors:
        raise PasswordValidationError("; ".join(errors))
