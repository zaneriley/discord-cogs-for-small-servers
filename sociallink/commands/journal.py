import logging
from datetime import UTC, datetime

import discord

from sociallink.services.events import Events, event_bus
from sociallink.services.observer import Observer

logger = logging.getLogger(__name__)


class JournalManager(Observer):
    def __init__(self, config, event_bus):
        self.config = config
        self.event_bus = event_bus

    async def create_journal_entry(
        self, event_type, initiator: discord.Member, confidant: discord.Member, timestamp: datetime, details: str = None
    ) -> tuple:
        """
        Creates a social link journal entry based on a Discord interaction and confirms its addition.

        Returns
        -------
            tuple: (bool, str or dict) Indicates success or failure, and provides a message or the created journal entry.

        """
        try:
            current_time = datetime.now(tz=UTC)  # Ensure current_time is timezone-aware
            logger.debug(f"Current time (UTC): {current_time}")

            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            logger.debug(f"Original timestamp: {timestamp}")

            time_difference = current_time - timestamp
            logger.debug(f"Time difference: {time_difference}")

            timestamp_unix = int(timestamp.timestamp())
            logger.debug(f"Timestamp (Unix): {timestamp_unix}")

            days_until_use_absolute_date = 3

            formatted_timestamp = (
                f"<t:{timestamp_unix}:R>"
                if time_difference.days < days_until_use_absolute_date
                else f"<t:{timestamp_unix}:D>"
            )
            logger.debug(f"Formatted timestamp: {formatted_timestamp}")

            entry = {
                "event_type": event_type,
                "initiator_id": str(initiator.id),
                "confidant_id": str(confidant.id),
                "timestamp": formatted_timestamp,
                "description": details or "No details provided.",
            }

            # Get the user's data
            user_data = await self.config.user(initiator).all()

            user_data["journal"].append(entry)

            # Save the updated user data
            await self.config.user(initiator).set(user_data)

            # Verify data persistence by retrieving it again
            updated_user_data = await self.config.user(initiator).all()

            if entry in updated_user_data["journal"]:
                logger.info(f"Journal entry successfully added for user {initiator}: {entry}")
                return (True, entry)
            else:  # noqa: RET505
                logger.error(f"Journal entry NOT found in user data after save for {initiator}. Entry: {entry}")
                return (False, f"Failed to verify journal entry persistence: {entry}")

        except KeyError as e:
            logger.exception(f"KeyError while creating journal entry for user {initiator}")
            return (False, f"KeyError while creating journal entry: {e}")

        except TypeError as e:
            logger.exception(f"TypeError while creating journal entry for user {initiator}")
            return (False, f"TypeError while creating journal entry: {e}")

        except Exception as e:
            logger.exception(f"Unexpected error while creating journal entry for user {initiator}")
            return (False, f"Unexpected error while creating journal entry: {e}")

    async def display_journal(self, user, entries_per_page=15):
        """
        Fetches and paginates journal entries
        """
        user_data = await self.config.user(user).get_raw()
        journal_entries = user_data.get("journal", [])

        if not journal_entries:
            return ["Your journal is empty. Engage with others to fill these pages with memories."]

        pages = []
        current_page_entries = []

        for entry in reversed(journal_entries):
            current_page_entries.append(f"{entry['timestamp']}: {entry['description']} with <@{entry['confidant_id']}>")

            if len(current_page_entries) >= entries_per_page:
                pages.append("# <a:game_journal:1238442679382052934>  Journal \n\n" + "\n".join(current_page_entries))
                current_page_entries = []

        # Append the remaining entries (if any)
        if current_page_entries:
            pages.append("# <a:game_journal:1238442679382052934>  Journal \n\n" + "\n".join(current_page_entries))

        return pages

    async def get_latest_journal_entry(self, user_id, confidant_id):
        user_data = await self.config.user_from_id(user_id).all()
        journal_entries = user_data.get("journal", [])
        for entry in reversed(journal_entries):  # Start from the most recent entry
            if entry["confidant_id"] == str(confidant_id):
                return entry
        return None

    @event_bus.subscribe(Events.ON_LEVEL_UP)
    async def handle_level_up(self, *args, **kwargs):
        logger.debug("Received event %s", kwargs)

        user_1 = kwargs.get("user_1")
        user_2 = kwargs.get("user_2")
        event_type = kwargs.get("event_type")
        timestamp = kwargs.get("timestamp")

        # TODO: Switch to LLM journal entries
        # description_user_1 = await generate_journal_description(event_type, user_1.id, user_2.id, details)
        # description_user_2 = await generate_journal_description(event_type, user_2.id, user_1.id, details)

        # Create journal entries for both users
        await self.journal_manager.create_journal_entry(event_type, user_1, user_2, timestamp, description_user_1)
        await self.journal_manager.create_journal_entry(event_type, user_2, user_1, timestamp, description_user_2)


async def generate_journal_description(self, event_type, initiator_id, confidant_id, details):
    prompt = f"""
    Given a dialogue with a friend, classify the dialogue as being associated with a certain level and provide a concise 1 sentence summary of the dialogue, focusing on the NPC/friend's connection growing. Write in 2nd person. Write in the style of Persona 5.

    Example 1:
    Friend: Ryuichi
    Dialogue:
    "But for some reason it don't look like he's gettin' along with the others." Nakaoka? "It's good they're keepin' their heads low now though. I don't want 'em endin' up like me." But you're doing great.
    Level: 4
    Summary: "Though still worried about the track team, Ryuichi said he has the Phantom Thieves now."

    Example 2:
    Friend: Sakamoto
    Dialogue:
    "You're not causing any trouble, are you?" I'm not. "If you could lend a hand, it'd really be a great help..." I'd be glad to. "I'll teach you how to make the perfect cup of coffee. Not a bad trade, eh?" I guess.
    Level: 1
    Summary: "Something about the smell of coffee, and "her"..."

    Example 3:
    Friend: Yoshida
    Dialogue:
    "Okay, I'm going to get started." Do your best. "Perhaps, it's the effect of you moving my heart." What are you talking about?
    Level: 9
    Summary: "Yoshida mentioned nothing about the false charge, which moves his colleague to support his run."

    Friend: User {confidant_id}
    Dialogue:
    {details}
    Level: {level}
    Summary:
    """

    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=100,
        n=1,
        stop=None,
        temperature=0.7,
    )

    return response.choices[0].text.strip()
