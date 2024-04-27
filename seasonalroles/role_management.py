import discord
import logging
from typing import Optional
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class RoleManager:
    def __init__(self, config):
        self.config = config

    async def create_or_update_role(self, guild: discord.Guild, name: str, color: str, date: str, image: Optional[str] = None) -> discord.Role:
        """
        Creates a new role or updates an existing one with the given attributes.
        """
        name_with_date = f"{name} {date}"
        role_args = {"color": discord.Color(int(color[1:], 16))}
        existing_role = next((role for role in guild.roles if role.name.startswith(name)), None)

        # Handle image if provided and guild supports role icons
        if image and "ROLE_ICONS" in guild.features:
            image_path = os.path.join(os.path.dirname(__file__), image)
            if os.path.exists(image_path):
                try:
                    with open(image_path, "rb") as img_file:
                        img_data = img_file.read()
                        role_args["display_icon"] = img_data
                except Exception as e:
                    logger.error(f"Failed to process the image data for {name} role: {e}")
                    return None
            else:
                logger.error(f"Image file not found at path: {image_path}")
                return None

        if existing_role:
            try:
                await existing_role.edit(name=name_with_date, **role_args)
                logger.debug(f"Updated role {existing_role.name} in {guild.name}")
                return existing_role
            except Exception as e:
                logger.error(f"Error updating role {existing_role.name} in {guild.name}: {e}")
                return None
        else:
            try:
                new_role = await guild.create_role(name=name_with_date, **role_args)
                logger.debug(f"Created role {new_role.name} in {guild.name}")
                return new_role
            except Exception as e:
                logger.error(f"Error creating role {name} in {guild.name}: {e}")
                return None
            
    async def assign_role_to_all_members(self, guild: discord.Guild, role: discord.Role) -> None:
        """
        Assigns a specified role to all members who have opted in to the seasonal role, in a guild.
        """
        # Retrieve the dry run mode setting from the guild's configuration
        dry_run_mode = await self.config.guild(guild).dry_run_mode()

        if dry_run_mode:
            logger.info(
                f"Would have applied role to {len(guild.members)} members in {guild.name} if not in dry run mode"
            )
        else:
            opt_in_users = await self.config.guild(guild).opt_in_users()

            for member in guild.members:
                if member.id in opt_in_users:
                    try:
                        await member.add_roles(role)
                        logger.info(
                            f"[Dry Run] Would assign role '{role.name}' to {len(guild.members)} opted-in members in '{guild.name}' if not in dry run mode."
                        )
                    except discord.Forbidden:
                        logger.error(
                            f"Permission error when trying to add role to member {member.name} in {guild.name}"
                        )
                        
    async def remove_role_from_all_members(self, guild: discord.Guild, role: discord.Role) -> None:
        """
        Removes a specified role from all members who have opted in to the seasonal role, in a guild.
        """
        dry_run_mode = await self.config.guild(guild).dry_run_mode()
        if dry_run_mode:
            for member in guild.members:
                logger.info(
                    f"[Dry Run] Would remove role '{role.name}' from all members in '{guild.name}' if not in dry run mode."
                )
        else:
            for member in guild.members:
                try:
                    await member.remove_roles(role)
                    logger.debug(f"Removed role {role.name} from {member.name} in {guild.name}")
                except discord.Forbidden:
                    logger.error(f"Permission error when trying to remove role from member {member.name} in {guild.name}")

    async def delete_role_from_guild(self, guild: discord.Guild, role: discord.Role) -> None:
        """
        Deletes a role from a guild.
        """
        try:
            await role.delete()
            logger.debug(f"Deleted role {role.name} in guild {guild.name}")
        except Exception as e:
            logger.error(f"Error deleting role {role.name} in guild {guild.name}: {e}")

    async def move_role_to_top_priority(self, guild: discord.Guild, role: discord.Role) -> None:
        # This works by getting the bot's highest role, then setting the role's position to one less than that
        bot_member = guild.me  # The bot's member object in the guild
        bot_roles = sorted(bot_member.roles, key=lambda x: x.position, reverse=True)
        highest_bot_role = bot_roles[0]  # The highest role the bot has

        if highest_bot_role.position > 1:
            # Set the seasonal role position to one less than the bot's highest role
            new_position = highest_bot_role.position - 1
            positions = {role: new_position}
            try:
                await guild.edit_role_positions(positions)
                logger.debug(f"Role '{role.name}' set to position {new_position} in guild '{guild.name}'.")
            except Exception as e:
                logger.error(f"Error setting position of role '{role.name}' in guild '{guild.name}': {e}")
        else:
            logger.warning(f"Bot does not have sufficient role hierarchy to set the role position in guild '{guild.name}'.")