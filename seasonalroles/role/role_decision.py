"""Pure functions for making role update/create decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .role_namer import generate_role_name

if TYPE_CHECKING:
    from discord import Role


def decide_role_action(
    holiday_name: str,
    date: str,
    existing_roles: list[Role] | list[str],
) -> tuple[str, str]:
    """
    Determine whether to create a new role or update an existing one.

    This function checks if there's already a role that begins with the
    holiday name and determines if it should be updated or a new role
    should be created.

    Args:
    ----
        holiday_name: The name of the holiday
        date: The date of the holiday in MM-DD format
        existing_roles: List of existing roles to check against

    Returns:
    -------
        tuple: (action, role_name) where action is either "update" or "create"

    """
    # Create the formatted role name using the role namer function
    role_name = generate_role_name(holiday_name, date)

    # Check if a role for this holiday already exists (case-insensitive)
    for role in existing_roles:
        role_name_str = role.name if hasattr(role, "name") else str(role)
        if role_name_str.lower().startswith(holiday_name.lower()):
            return "update", role_name

    # No existing role found, create a new one
    return "create", role_name
