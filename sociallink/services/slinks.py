import logging
from datetime import UTC, datetime

import discord

from emojilocker import EmojiLocker
from sociallink.services.events import Events, event_bus

logger = logging.getLogger(__name__)

# Below code is incomplete, does not yet function as intended.
# init first level -> create roles for both users -> ask to upload emojis -> associate emoji with level 1 and 10.
class SLinkManager:
    role_format = "u_{user.display_name}_level{level}"

    def __init__(self, bot, config, event_bus):
        self.bot = bot
        self.config = config 
        self.event_bus = event_bus

    @event_bus.subscribe(Events.ON_LEVEL_UP)
    async def handle_level_up(cls, ctx, config, *args, **kwargs):
        logger.debug("Entered handle_level_up with args: %s, kwargs: %s", args, kwargs)
        max_levels = await config.max_levels()
        user = kwargs.get("user")
        confidant = kwargs.get("confidant")
        level = kwargs.get("level")
        role_name = cls.role_format.format(user=confidant, level=level)
        role = discord.utils.get(ctx.guild.roles, name=role_name)

        if not role:
            role = await ctx.guild.create_role(name=role_name, reason=f"{confidant.name} reached level {level}")

        await user.add_roles(role, reason=f"Reached level {level} with {confidant.name}")

        handler_name = f"handle_level_{level}"
        handler = getattr(cls, handler_name, None)
        if handler:
            return await handler(confidant.name, confidant.emojis)
        else:
            logger.warning(f"No handler found for level {level}")
            return None

    async def handle_level_1(self,name, emojis):
        role_name = self.role_format.format(user=name, level=1)
        role = discord.utils.get(ctx.guild.roles, name=role_name)

        restricted_emojis = []
        for emoji in emojis:
            await self.emoji_locker.allow_roles(ctx, emoji, [role], remove_all=True)  # Restrict the emoji to the role
            restricted_emojis.append(str(emoji))

        reward_message = f"These {name} emojis are now available for use in this server: {' '.join(restricted_emojis)}"
        return (reward_message, restricted_emojis)


    async def create_onboarding():
        pass

    async def create_roles_for_user(self, ctx, user):
            """
            Creates roles for every level for a specific user if they don't exist.
            Roles are not assigned to the user and are hoisted to the bottom of the role list.
            """
            max_levels = await self.config.max_levels()

            for level in range(1, max_levels + 1):
                role_name = self.role_format

                # Check if the role already exists
                role = discord.utils.get(ctx.guild.roles, name=role_name)

                # If the role does not exist, create it
                if not role:
                    try:
                        role = await ctx.guild.create_role(name=role_name, hoist=False, mentionable=False, reason="Creating level-based role")
                        logger.info(f"Created new role: {role_name}")
                    except discord.Forbidden:
                        logger.exception("I do not have permission to create roles.")
                        return
                    except discord.HTTPException as e:
                        logger.exception("Failed to create role:")
                        return
                else:
                    logger.info(f"Role '{role_name}' already exists.")


    async def create_confidant_emoji():
        pass
    
    async def fetch_confidants_emojis(confidant,level):
        return 

    async def add_emoji_to_role(self, ctx, emoji: discord.Emoji, level: int):
        """Allows a user to add an emoji to their level-based role."""
        role_name = self.role_format
        role = discord.utils.get(ctx.guild.roles, name=role_name)
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