import asyncio
import logging
from pathlib import Path

import discord

from sociallink.services.events import Events
from utilities.image_utils import get_image_handler

logger = logging.getLogger(__name__)


# Below code is incomplete, does not yet function as intended.
# init first level -> create roles for both users -> ask to upload emojis -> associate emoji with level 1 and 10.
class SLinkManager:
    # This is a hotfix for the eventbus pattern not working as intended
    # using the decorator pattern causes conflicts between the instance and the class
    # But refactoring would involve updating all event listeners in /sociallink
    @classmethod
    def _wrap_handler(cls, instance, func):
        async def wrapper(*args, **kwargs):
            logger.debug("args: %s, kwargs: %s", args, kwargs)

            await func(*args, **kwargs)

        return wrapper

    def __init__(self, bot, config, event_bus):
        self.bot = bot
        self.config = config
        self.event_bus = event_bus
        self.level_handlers = {
            1: self.handle_level_1,
        }
        self.role_icons = None  # Will be dynamically fetched per user
        self.guild_id = self.config.get_raw("guild_id")
        self.guild = self.bot.get_guild(self.guild_id)

        # Manual Event Subscription
        wrapped_handler = self._wrap_handler(self, self.handle_level_up)
        event_bus.events[Events.ON_LEVEL_UP].append(wrapped_handler)

    async def handle_level_up(self, *args, **kwargs):
        logger.debug("Entered handle_level_up with args: %s, kwargs: %s", args, kwargs)

        ctx = kwargs.get("ctx")
        config = kwargs.get("config")
        max_levels = await config.max_levels()
        user = kwargs.get("user_1")
        confidant = kwargs.get("user_2")
        logger.debug("user_1: %s, user_2: %s", user, confidant)
        level = kwargs.get("level")
        guild = ctx.guild if ctx else user.guild

        if confidant is None:
            logger.error("Confidant is None. Cannot proceed with level up.")
            return None
        default_icon_path = Path(__file__).parent.parent / "assets/default-role.png"

        role_format = await self.config.guild(guild).role_format()
        logger.debug("Role format: %s with confidant display name %s", role_format, confidant)

        role_name_user1 = role_format.format(user=user.nick if user.nick else user.name, level=level)
        role_name_user2 = role_format.format(user=confidant.nick if confidant.nick else confidant.name, level=level)

        role_user1 = discord.utils.get(guild.roles, name=role_name_user1)
        if not role_user1:
            await self.create_or_update_role(guild, role_name_user1, default_icon_path)
            role_user1 = discord.utils.get(guild.roles, name=role_name_user1)

        role_user2 = discord.utils.get(guild.roles, name=role_name_user2)
        if not role_user2:
            await self.create_or_update_role(guild, role_name_user2, default_icon_path)
            role_user2 = discord.utils.get(guild.roles, name=role_name_user2)

        await user.add_roles(role_user2, reason=f"Reached level {level} with {confidant.name}")
        await confidant.add_roles(role_user1, reason=f"Reached level {level} with {user.name}")

        onboarding_sent_user = await self.config.user(user).onboarding_sent()
        onboarding_sent_confidant = await self.config.user(confidant).onboarding_sent()

        if not onboarding_sent_user:
            await self.send_onboarding_message(user)
            await self.config.user(user).onboarding_sent.set(True)  # noqa: FBT003

        if not onboarding_sent_confidant:
            await self.send_onboarding_message(confidant)
            await self.config.user(confidant).onboarding_sent.set(True)  # noqa: FBT003

        handler = self.level_handlers.get(level)
        if handler:
            return await handler(ctx, user, confidant)

        logger.warning(f"No handler found for level {level}")
        return None

    async def handle_level_1(self, ctx, user, confidant):
        guild = ctx.guild if ctx else user.guild
        role_format = await self.config.roles.get_raw("role_format")
        role_name_user1 = role_format.format(user=user.nick, level=1)
        role_name_user2 = role_format.format(user=confidant.nick, level=1)
        role_user1 = discord.utils.get(guild.roles, name=role_name_user1)
        role_user2 = discord.utils.get(guild.roles, name=role_name_user2)

        self.send_onboarding_message(user)
        # self.send_onboarding_message(confidant)
        # restricted_emojis = []
        # for emoji in emojis:
        #     await self.emoji_locker.allow_roles(ctx, emoji, [role], remove_all=True)  # Restrict the emoji to the role
        #     restricted_emojis.append(str(emoji))

        # reward_message = f"These {name} emojis are now available for use in this server: {' '.join(restricted_emojis)}"
        # return (reward_message, restricted_emojis)

    async def send_onboarding_message(self, user: discord.User):
        messages = [
            """
## ⠀   ⠀   _A new bond has been formed..._
""",
            """_⠀⠀  ⠀⠀⠀Throughout your journey,         ⠀⠀
⠀⠀⠀⠀⠀you will encounter individuals      ⠀⠀
⠀⠀⠀⠀who can become your Confidants.     ⠀⠀
⠀⠀These bonds are crucial for your growth._⠀
""",
            """_
⠀⠀⠀⠀By spending time **in the server** ⠀⠀
⠀⠀⠀⠀  with these individuals you can     ⠀⠀
⠀⠀⠀  ⠀ deepen your relationship and
⠀⠀ ⠀ ⠀ increase your Confidant rank._
""",
            """
_
⠀⠀To check your status with your Confidants, ⠀⠀
⠀type `/confidants` to see your connections._
""",
            """
\n⠀
> **Please note:** This is an early prototype of a game.
> Not all functionality may exist, it may not even be fun, 
> and you may encounter bugs or incomplete features.
> 
> See post for more info: https://discord.com/channels/947277446678470696/1092080357286883438
> Feedback, ideas or other contributions are welcome.
— Rye
""",
        ]

        for message in messages:
            async with user.typing():
                # Calculate dynamic delay based on message length
                base_delay = 1.25  # Base delay in seconds
                char_delay = 0.02  # Additional delay per character
                total_delay = base_delay + (char_delay * len(message))
                await asyncio.sleep(total_delay)

                try:
                    await user.send(message)
                except discord.Forbidden:
                    logger.exception("Failed to send message to %s", user.name)
                except discord.HTTPException:
                    logger.exception("Failed to send message to %s", user.name)

    # TODO: This should be in discord_utils but due to a circular dependency issue, it's here
    async def create_or_update_role(self, guild: discord.Guild, role_name: str, image_source: str):
        # Fetch the role if it exists
        role = discord.utils.get(guild.roles, name=role_name)
        if not image_source:
            image_source = Path(__file__).parent.parent / "assets/default-role.png"
        # Convert Path object to string
        image_source = str(image_source)
        # Fetch image data for the role icon
        logger.info("image_source: %s", image_source)

        image_handler = get_image_handler(image_source)
        image_data = await image_handler.fetch_image_data()

        logger.debug("Image handler: %s, image", image_handler)

        if role:
            # If the role exists, update it with the new icon
            try:
                await role.edit(display_icon=image_data, color=discord.Color.blurple(), reason="Updating role icon")
                logger.info("Updated role %s with new icon.", role.name)
            except discord.Forbidden:
                logger.exception("Bot does not have permission to edit roles.")
            except discord.HTTPException:
                logger.exception("Failed to edit role:")
        else:
            # If the role does not exist, create it with the icon
            try:
                role = await guild.create_role(
                    name=role_name,
                    display_icon=image_data,
                    color=discord.Color.blurple(),
                    reason="Creating new role with icon",
                )
                logger.info("Created new role %s with a new icon.", role.name)
            except discord.Forbidden:
                logger.exception("Bot does not have permission to create roles.")
            except discord.HTTPException:
                logger.exception("Failed to create role:")

        return role

    async def create_roles_for_user(self, ctx, user):
        """
        Creates roles for every level for a specific user if they don't exist.
        Roles are not assigned to the user and are hoisted to the bottom of the role list.
        """
        guild = ctx.guild if ctx else user.guild
        max_levels = await self.config.max_levels()
        role_format = await self.config.roles.get_raw("role_format")
        default_icon_path = Path(__file__).parent.parent / "assets/default-role.png"

        for level in range(1, max_levels + 1):
            role_name = role_format.format(user=user.display_name, level=level)

            # Create or update the role with the default icon
            await self.create_or_update_role(guild, role_name, default_icon_path)

    async def create_confidant_emoji():
        pass

    async def fetch_confidants_emojis(confidant, level):
        return

    async def add_emoji_to_role(self, ctx, emoji: discord.Emoji, level: int):
        """Allows a user to add an emoji to their level-based role."""
        guild = self.guild
        role_name = self.role_format
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            await ctx.send("Role does not exist.")
            return

        try:
            await emoji.edit(roles=[role], reason="Assigning emoji to specific role")
            await ctx.send(f"Emoji {emoji} is now restricted to {role.name}")
        except discord.Forbidden:
            await ctx.send("I do not have permission to edit this emoji.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to edit emoji: {e}")
