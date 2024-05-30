import logging
import random

logger = logging.getLogger(__name__)

class RankManager:
    def __init__(self, config):
        self.config = config
        self.rankings_messages = [
            "Forge unbreakable bonds and rise through the ranks",
        ]
        self.tie_messages = [
            "ᴀ ʙᴏɴᴅ ᴏꜰ ᴇǫᴜᴀʟꜱ",
            "ᴛɪᴇᴅ ʙʏ ꜰᴀᴛᴇ",
            "ᴀ ꜱʜᴀʀᴇᴅ ᴅᴇꜱᴛɪɴʏ",
            "ᴇǫᴜᴀʟʟʏ ᴍᴀᴛᴄʜᴇᴅ",
            "ɴᴏ ᴏɴᴇ ꜱᴛᴀɴᴅꜱ ᴀʙᴏᴠᴇ.",
        ]

    async def get_rankings_leaderboard(self, runner_id: int) -> str:
        """
        Calculates scores, ranks users, and formats a leaderboard message.

        Args:
        ----
            runner_id: The ID of the runner to highlight in the leaderboard.

        Returns:
        -------
            The formatted leaderboard message.

        """
        logger.info("Starting score calculation and ranking process")

        sorted_users_data = await self._calculate_and_sort_scores()
        logger.debug("Sorted users: %s", list(sorted_users_data))

        leaderboard_message = self._format_leaderboard(sorted_users_data, runner_id)

        logger.info("Completed score calculation and ranking process")
        return leaderboard_message

    async def _calculate_and_sort_scores(self) -> list[tuple[int, dict]]:
        """
        Fetches user data, calculates scores, and sorts users.

        Returns
        -------
            A list of tuples where each tuple contains (user_id, user_data)
            and user_data is a dictionary with 'aggregate_score' key.

        """
        all_users = await self.config.all_users()
        logger.debug("Retrieved user data: %s", all_users)

        aggregate_scores = {}
        for user_id, user_data in all_users.items():
            try:
                aggregate_scores[user_id] = {
                    "aggregate_score": sum(user_data["scores"].values()),
                    **user_data,  # Include other user data if needed
                }
            except KeyError:
                logger.warning("User %d has no scores data.", user_id)

        logger.debug("Calculated aggregate scores: %s", aggregate_scores)
        return sorted(aggregate_scores.items(), key=lambda x: x[1]["aggregate_score"], reverse=True)

    def _format_leaderboard(self, sorted_users_data: list[tuple[int, dict]], runner_id: int) -> str:
        """
        Formats the leaderboard message from sorted user data.

        Args:
        ----
            sorted_users_data: A list of tuples containing (user_id, user_data).
            runner_id: The ID of the runner to highlight.

        Returns:
        -------
            The formatted leaderboard message.

        """
        if not sorted_users_data:
            return "_No rankings available. Strengthen your connections to rise above the rest._"

        rank_message = "# <a:ui_fire:1239938986630447226> Rankings\n\n"
        previous_score = None
        current_rank = 0
        tie_group = []

        for user_id, data in sorted_users_data:
            score = data["aggregate_score"]
            if score == 0:  # Skip users with 0 points
                continue
            if score != previous_score:
                if tie_group:
                    rank_message += self._format_tie_group(tie_group, current_rank, runner_id)
                    tie_group = []
                current_rank += 1
                previous_score = score
            tie_group.append((user_id, score))

        if tie_group:
            rank_message += self._format_tie_group(tie_group, current_rank, runner_id)

        return rank_message

    def _format_tie_group(self, tie_group, rank, runner_id: int):
        if len(tie_group) == 1:
            user_id, score = tie_group[0]
            return f"{rank}. {self._format_user_mention(user_id, runner_id)} **{score}pts**\n"

        if len(tie_group) >= 3:
            user_mentions = ", ".join([self._format_user_mention(user_id, runner_id) for user_id, _ in tie_group[:-1]])
            user_mentions += f", and {self._format_user_mention(tie_group[-1][0], runner_id)}"
        else:
            user_mentions = " & ".join([self._format_user_mention(user_id, runner_id) for user_id, _ in tie_group])

        score = tie_group[0][1]
        return f"{rank}.{user_mentions} {score}pts — {random.choice(self.tie_messages)}\n"  # noqa: S311

    def _format_user_mention(self, user_id: int, runner_id: int) -> str:
        """Helper function to format user mentions consistently, highlighting the command runner."""
        if user_id == runner_id:
            return f"<a:ui_star_new:1239795055150104647><@{user_id}>"
        return f"<@{user_id}>"

    def get_rank_up_message(self) -> str:
        return random.choice(self.rank_up_messages)  # noqa: S311


