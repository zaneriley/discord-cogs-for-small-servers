import asyncio
import logging

import discord
from discord.http import HTTPException
from discord.ui import Select, View
from redbot.core import Config, commands

from utilities.discord_utils import PaginatorView
from utilities.image_utils import get_image_handler

logger = logging.getLogger(__name__)

class EmojiRoleSelect(Select):
    def __init__(self, emojis, roles):
        options = [discord.SelectOption(label=str(emoji), value=str(emoji.id)) for emoji in emojis if emoji is not None]
        super().__init__(placeholder="Select an emoji", min_values=1, max_values=1, options=options)
        self.roles = roles

    async def callback(self, interaction: discord.Interaction):
        emoji_id = int(self.values[0])
        emoji = interaction.guild.get_emoji(emoji_id)
        if not emoji:
            await interaction.response.send_message("Emoji not found.", ephemeral=True)
            return

        role_select = RoleSelect(self.roles, self.cog, emoji)
        view = View()
        view.add_item(role_select)
        await interaction.response.send_message("Select a role to assign to the emoji:", view=view, ephemeral=True)

class ViewWithCog(View):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

class RoleSelect(discord.ui.Select):
    def __init__(self, roles, cog, emoji):
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in roles]
        super().__init__(placeholder="Choose a role", min_values=1, max_values=1, options=options, custom_id="role_select")
        self.cog = cog
        self.emoji = emoji

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("Role not found.", ephemeral=True)
            return

        # Get the admin roles
        admin_roles = await self.bot.get_admin_roles(interaction.guild)

        try:
            # Add the selected role and the admin roles to the emoji
            await self.emoji.edit(roles=[role, admin_roles], reason="Restricting emoji to specific role")
            await interaction.response.send_message(f"Emoji {self.emoji} is now restricted to role {role.name} and admin roles", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to edit this emoji.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Failed to edit emoji: {e}", ephemeral=True)

            async with self.cog.config.guild(interaction.guild).emoji_roles() as emoji_roles:
                emoji_roles[str(self.emoji.id)] = {"role_id": role.id, "roles": [role.id for role in admin_roles]}

class UnrestrictEmojiSelect(discord.ui.Select):
    def __init__(self, cog, restricted_emojis: list[discord.Emoji]):
        options = [discord.SelectOption(label=str(emoji), value=str(emoji.id)) for emoji in restricted_emojis]
        super().__init__(placeholder="Select an emoji to unrestrict", min_values=1, max_values=1, options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        try:
            emoji_id = int(self.values[0])
            emoji = interaction.guild.get_emoji(emoji_id)
            if not emoji:
                await interaction.response.send_message("Emoji not found.", ephemeral=True)
                return

            logger.debug(f"Unrestricting emoji: {emoji}")

            if not emoji.roles:  # Check if the emoji already has no roles assigned
                await interaction.response.send_message(
                    f"Emoji {emoji} is not restricted.", ephemeral=True
                )
                return

            await emoji.edit(roles=[], reason="Unrestricting emoji")
            logger.debug("Emoji unrestricted: %s", emoji)
            await interaction.response.send_message(
                f"Emoji {emoji} is now unrestricted and can be used by all roles.",
                ephemeral=True,
            )

        except discord.Forbidden:
            logger.exception("Failed to unrestrict emoji due to insufficient permissions.")
            await interaction.response.send_message(
                "I do not have permission to edit this emoji.", ephemeral=True
            )
        except discord.HTTPException as e:
            logger.exception("Failed to unrestrict emoji due to an HTTP exception:")
            await interaction.response.send_message(f"Failed to edit emoji: {e}", ephemeral=True)
        except Exception as e:  # Catch more general exceptions for configuration saving
            logger.exception("An unexpected error occurred while unrestricting emoji:")
            await interaction.response.send_message(
                "An error occurred while saving the configuration. Please try again later.",
                ephemeral=True,
            )

class UnrestrictEmojiView(discord.ui.View):
    def __init__(self, cog, restricted_emojis):
        super().__init__()
        self.add_item(UnrestrictEmojiSelect(cog, restricted_emojis))

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.guild_permissions.manage_roles


class EmojiLocker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "emoji_roles": {}
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("EmojiLocker cog ready")

    @commands.group(name="emojilocker", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def emojilocker(self, ctx):
        """Limit emojis to specific roles"""
        await ctx.send_help()

    @emojilocker.command(name="create")
    @commands.has_permissions(manage_emojis=True)
    async def create_emoji(self, ctx, name: str, image: str):
        """Create a new emoji from an image, URL, or existing emoji from another server"""
        try:
            # Get the image handler based on the input type
            handler = get_image_handler(image)

            # Fetch the image data
            image_data = await handler.fetch_image_data()

            # Create the emoji
            await ctx.guild.create_custom_emoji(name=name, image=image_data)
            await ctx.send(f"Emoji :{name}: created successfully.")
        except Exception as e:
            logger.exception(f"An error occurred while creating emoji: {e}")
            await ctx.send("An error occurred while creating the emoji. Please try again later.")


    @emojilocker.command(name="set")
    @commands.has_permissions(manage_roles=True)
    async def restrict(self, ctx, emojis: commands.Greedy[discord.Emoji]):
        """Restrict an emoji to specific roles."""
        await ctx.send("Please reply with the name of the role you want to restrict the emoji to.")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await ctx.send("No reply within 60 seconds, cancelling operation.")
            return

        role_converter = commands.RoleConverter()
        try:
            role = await role_converter.convert(ctx, msg.content)
        except commands.RoleNotFound:
            await ctx.send(f"No role named '{msg.content}' found.")
            return

        # Add backup roles to role restriction, helpful if a role is deleted
        # and the emoji is still restricted to it
        admin_roles = await self.bot.get_admin_roles(ctx.guild)

        retry_attempts = 5
        backoff_delay = 2
        http_status_rate_limited = 429

        for emoji in emojis:
            for attempt in range(retry_attempts):
                try:
                    await emoji.edit(roles=[role, *admin_roles], reason="Restricting emojis to specific role")
                    await ctx.send(f"Emoji {emoji} is now restricted to role {role.name}")
                    break  # Exit the retry loop if successful
                except HTTPException as e:
                    if e.status == http_status_rate_limited:
                        retry_after = int(e.response.headers.get("Retry-After", backoff_delay * (2**attempt)))
                        logger.warning("Rate limited. Retrying in %s seconds", retry_after)
                        await asyncio.sleep(retry_after)
                    else:
                        logger.exception("An error occurred while restricting emoji:")
                        await ctx.send("An error occurred while restricting the emoji. Please try again later.")
                        break
                except Exception:
                    logger.exception("An unexpected error occurred while restricting emoji:")
                    await ctx.send("An unexpected error occurred while restricting the emoji. Please try again later.")
                    break

    @emojilocker.command(name="unset")
    @commands.has_permissions(manage_roles=True)
    async def unrestrict_emoji(self, ctx):
        """Unrestrict an emoji, allowing all roles to use it."""
        restricted_emojis = []
        for emoji in ctx.guild.emojis:
            if emoji.roles:  # Check if the emoji has roles assigned
                restricted_emojis.append(emoji)
            else:
                # Check if the emoji is restricted to a non-existent role
                emoji_roles = await self.config.guild(ctx.guild).emoji_roles()
                if str(emoji.id) in emoji_roles and not ctx.guild.get_role(emoji_roles[str(emoji.id)]["role_id"]):
                    restricted_emojis.append(emoji)

        if not restricted_emojis:
            await ctx.send("There are no restricted emojis in this server.")
            return

        view = UnrestrictEmojiView(self, restricted_emojis)
        await ctx.send("Select an emoji to unrestrict:", view=view)


    @emojilocker.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def list_emoji_roles(self, ctx):
        """List all emojis that are restricted to specific roles."""
        emojis = ctx.guild.emojis
        restricted_emojis = [emoji for emoji in emojis if emoji.roles]

        if restricted_emojis:
            # Prepare the data
            pages = []
            for i in range(0, len(restricted_emojis), 10):  # Adjust the number as needed
                page = ""
                for emoji in restricted_emojis[i:i+10]:
                    role_names = [role.name for role in emoji.roles]
                    page += f"{emoji}: {', '.join(role_names)}\n"
                pages.append(page)

            if not pages:
                pages.append("No restricted emojis found.")

            view = PaginatorView(pages)

            await ctx.send("Emojis restricted to specific roles:", view=view)
        else:
            await ctx.send("No emojis are restricted to specific roles in this server.")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        emoji_roles = await self.config.guild(reaction.message.guild).emoji_roles()
        if str(reaction.emoji.id) in emoji_roles:
            role_id = emoji_roles[str(reaction.emoji.id)]["role_id"]
            allowed_roles = emoji_roles[str(reaction.emoji.id)]["roles"]
            if any(role.id in allowed_roles for role in user.roles):
                role = reaction.message.guild.get_role(role_id)
                await user.add_roles(role)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot:
            return

        emoji_roles = await self.config.guild(reaction.message.guild).emoji_roles()
        if str(reaction.emoji.id) in emoji_roles:
            role_id = emoji_roles[str(reaction.emoji.id)]["role_id"]
            allowed_roles = emoji_roles[str(reaction.emoji.id)]["roles"]
            if any(role.id in allowed_roles for role in user.roles):
                role = reaction.message.guild.get_role(role_id)
                await user.remove_roles(role)


def setup(bot):
    bot.add_cog(EmojiLocker(bot))
