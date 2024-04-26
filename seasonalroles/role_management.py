import discord
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class RoleManager:
    def __init__(self, config):
        self.config = config

    async def assign_role_to_all_members(self, guild: discord.Guild, role: discord.Role) -> None:
        """
        Assigns a specified role to all members who have opted in, in a guild.
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
                        logger.debug(
                            f"Added role {role.name} to {member.name} in {guild.name}"
                        )
                    except discord.Forbidden:
                        logger.error(
                            f"Permission error when trying to add role to member {member.name} in {guild.name}"
                        )