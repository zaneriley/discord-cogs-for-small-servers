from __future__ import annotations

import logging
from pathlib import Path

import discord

from .role.role_decision import decide_role_action

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class RoleManager:
    def __init__(self, config):
        self.config = config

    async def create_or_update_role(
        self,
        guild: discord.Guild,
        name: str,
        color: str,
        date: str,
        image: str | None = None,
    ) -> discord.Role:
        """
        Creates a new role or updates an existing one with the given attributes.
        """
        # Use business logic to determine role action and name
        action, name_with_date = decide_role_action(name, date, guild.roles)

        role_args = {"color": discord.Color(int(color[1:], 16))}

        # Handle image if provided and guild supports role icons
        if image and "ROLE_ICONS" in guild.features:
            image_path = Path(__file__).parent / image
            if image_path.exists():
                try:
                    img_data = image_path.read_bytes()
                    role_args["display_icon"] = img_data
                except Exception:
                    logger.exception(
                        f"Failed to process the image data for {name} role"
                    )
                    return None
            else:
                logger.error(f"Image file not found at path: {image_path}")
                return None

        # Use the action determined by business logic
        if action == "update":
            # Find the role that starts with the holiday name
            existing_role = next(
                (
                    role
                    for role in guild.roles
                    if role.name.lower().startswith(name.lower())
                ),
                None,
            )
            try:
                await existing_role.edit(name=name_with_date, **role_args)
                logger.debug(f"Updated role {existing_role.name} in {guild.name}")
            except Exception:
                logger.exception(
                    f"Error updating role {existing_role.name} in {guild.name}"
                )
                return None
            else:
                return existing_role
        else:  # action == "create"
            try:
                new_role = await guild.create_role(name=name_with_date, **role_args)
                logger.debug(f"Created role {new_role.name} in {guild.name}")
            except Exception:
                logger.exception(f"Error creating role {name} in {guild.name}")
                return None
            else:
                return new_role

    async def assign_role_to_all_members(
        self, guild: discord.Guild, role: discord.Role
    ) -> None:
        """
        Assigns the given role to all members in the guild who have opted in.
        """
        try:
            opt_in_users = await self.config.guild(guild).opt_in_users()
            if not opt_in_users:
                logger.debug(f"No opted-in users found in guild '{guild.name}'.")
                return

            dry_run_mode = await self.config.guild(guild).dry_run_mode()
            if dry_run_mode:
                logger.info(
                    f"[Dry Run] Would assign role '{role.name}' to all members in '{guild.name}' if not in dry run mode."
                )
                return

            for member_id in opt_in_users:
                member = guild.get_member(member_id)
                if member:
                    await member.add_roles(role)
                    logger.debug(
                        f"Added role {role.name} to {member.name} in {guild.name}"
                    )
        except Exception:
            logger.exception(
                f"Error assigning role {role.name} to members in {guild.name}"
            )

    async def remove_role_from_all_members(
        self, guild: discord.Guild, role: discord.Role
    ) -> None:
        """
        Removes the given role from all members in the guild.
        """
        try:
            dry_run_mode = await self.config.guild(guild).dry_run_mode()
            if dry_run_mode:
                for _member in guild.members:
                    logger.info(
                        f"[Dry Run] Would remove role '{role.name}' from all members in '{guild.name}' if not in dry run mode."
                    )
                    break
                return

            for member in guild.members:
                if role in member.roles:
                    try:
                        await member.remove_roles(role)
                        logger.debug(
                            f"Removed role {role.name} from {member.name} in {guild.name}"
                        )
                    except discord.Forbidden:
                        logger.exception(
                            f"Permission error when trying to remove role from member {member.name} in {guild.name}"
                        )
        except Exception:
            logger.exception(
                f"Error removing role {role.name} from members in {guild.name}"
            )

    async def delete_role_from_guild(
        self, guild: discord.Guild, role: discord.Role
    ) -> None:
        """
        Deletes the given role from the guild.
        """
        try:
            await role.delete()
            logger.debug(f"Deleted role {role.name} in guild {guild.name}")
        except Exception:
            logger.exception(f"Error deleting role {role.name} in guild {guild.name}")

    async def move_role_to_top_priority(
        self, guild: discord.Guild, role: discord.Role
    ) -> None:
        """
        Moves the given role to the top of the role list, just below the bot's role.
        """
        try:
            # Get the bot's top role
            bot_member = guild.me
            if bot_member:
                bot_top_role = bot_member.top_role
                if bot_top_role.position > role.position:
                    try:
                        new_position = bot_top_role.position - 1
                        await role.edit(position=new_position)
                        logger.debug(
                            f"Role '{role.name}' set to position {new_position} in guild '{guild.name}'."
                        )
                    except Exception:
                        logger.exception(
                            f"Error setting position of role '{role.name}' in guild '{guild.name}'"
                        )
                else:
                    logger.warning(
                        f"Role '{role.name}' already has a higher position than the bot's top role in guild '{guild.name}'."
                    )
            else:
                logger.warning(f"Bot member not found in guild '{guild.name}'.")
        except Exception:
            logger.exception(f"Error determining role position in guild '{guild.name}'")
