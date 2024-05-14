import discord


class ConfidantsManager:
    def __init__(self, config):
        self.config = config

    # View confidant
    async def view_confidant(self, ctx, user_id):
        # TODO: Implement logic in view_confidant
        pass

    async def create_confidant_embed(
        self, username: str, journal_entry: str, rank: int, stars: str, avatar_url: str
    ) -> discord.Embed:
        # Create the embed object
        embed = discord.Embed(
            title="𝘾𝙊𝙉𝙁𝙄𝘿𝘼𝙉𝙏",
            description="Though still worried about the track team, Rye said he has the Phantom Thieves now.",
            color=discord.Color.blue(),
        )

        # Add the rank and stars as a field
        embed.add_field(name=f"Rank {rank}", value=stars, inline=True)

        # Set the author name
        # embed.set_author(name=".")   # noqa: RUF003𝘼𝙉𝙏") 001𝘼𝙉𝙏")

        # Set the thumbnail to the confidant's avatar
        embed.set_thumbnail(url=avatar_url)

        return embed
