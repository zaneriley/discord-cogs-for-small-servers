import logging

from sociallink.services.observer import Observer

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.observers = []

    def register_observer(self, observer: Observer):
        self.observers.append(observer)

    def unregister_observer(self, observer: Observer):
        self.observers.remove(observer)

    async def notify_observers(self, user_1, user_2, level, stars):
        for observer in self.observers:
            await observer.update(user_1, user_2, level, stars)

 async def create_level_up_embed(
        self, username: str, journal_entry: str, rank: int, stars: str, avatar_url: str, level_up: bool = False
    ) -> discord.Embed:
        """
        Creates an embed for a confidant.
        """
        title = "𝘾𝙊𝙉𝙁𝙄𝘿𝘼𝙉𝙏"  # noqa: RUF001, RUF003𝘿𝘼𝙉𝙏"F001𝘿𝘼𝙉𝙏"
        description = (
            "Though still worried about the track team, Rye said he has the Phantom Thieves now."
        )
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
        )

        embed.add_field(name=f"Rank {rank}", value=stars, inline=True)
        embed.set_thumbnail(url=avatar_url)

        return embed

    async def send_rank_increase_notification(self, user_1, user_2, level, stars):
        user_1_id_str = str(user_1.id)
        user_2_id_str = str(user_2.id)

        stars = await self.generate_star_rating(level, is_level_up=True)

        if not user_1_id_str or not user_2_id_str:
            logger.error("One or both users not found.")
            return

        # The confidant the user ranked up with
        embed_for_user_2 = await self.confidants_manager.create_confidant_embed(
            username=user_2.display_name,
            journal_entry="",
            rank=level,
            stars=stars,
            avatar_url=user_2.display_avatar.url,
            level_up=True
        )

        embed_for_user_1 = await self.confidants_manager.create_confidant_embed(
            username=user_1.display_name,
            journal_entry="",
            rank=level,
            stars=stars,
            avatar_url=user_1.display_avatar.url,
            level_up=True
        )

        try:
            await user_1.send(content=f"## Rank up!!\n\n# <@{user_2.id}> \n", embed=embed_for_user_2)
            # TODO: TURNED OFF FOR PROTOTYPING DO NOT REMOVE
            # await user_2.send(content=f"## Rank up!!\n\n# <@{user_1.id}> \n", embed=embed_for_user_1)
            logger.info(
                "Notified %s and %s of their increased social rank with stars.",
                user_1.display_name,
                user_2.display_name,
            )
            await self.notify_observers(user_1, user_2, level, stars)
        except Exception:
            logger.exception("Failed to send notification:")
