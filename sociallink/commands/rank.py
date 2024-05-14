import random


class RankManager:
    def __init__(self):
        self.rank_up_messages = [
            "Your bond has grown stronger!",
            "Your relationship has reached a level of trust!",
            "Your connection has deepened, unlocking new potential!",
            "Your bond has evolved, revealing new paths ahead!",
            "You feel a surge of power!",
            "A new level of trust has been reached!",
        ]
        self.rankings_messages = [
            "Forge unbreakable bonds and rise through the ranks",
        ]
        self.tie_messages = [
            "A bond of equals.",
            "Tied by fate.",
            "A shared destiny.",
            "Equally matched.",
            "No one stands above.",
        ]

    async def get_rankings(self, config):
        all_users = await config.all_users()
        return sorted(all_users.items(), key=lambda x: x[1]["aggregate_score"], reverse=True)

    def format_rankings(self, sorted_users, runner_id: int):
        if not sorted_users:
            return "No rankings available. Strengthen your connections to rise above the rest."

        rank_message = "# <a:ui_fire:1239938986630447226> Rankings\n\n"
        previous_score = None
        current_rank = 0
        tie_group = []

        for user_id, data in sorted_users:
            score = data["aggregate_score"]
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
            return f"{rank}. {self._format_user_mention(user_id, runner_id)} ({score} pts)\n"

        if len(tie_group) >= 3:
            user_mentions = ", ".join([self._format_user_mention(user_id, runner_id) for user_id, _ in tie_group[:-1]])
            user_mentions += f", and {self._format_user_mention(tie_group[-1][0], runner_id)}"
        else:
            user_mentions = " & ".join([self._format_user_mention(user_id, runner_id) for user_id, _ in tie_group])

        score = tie_group[0][1]
        return f"{rank}. {user_mentions} ({score} pts) - {random.choice(self.tie_messages)}\n"  # noqa: S311

    def _format_user_mention(self, user_id: int, runner_id: int) -> str:
        """Helper function to format user mentions consistently, highlighting the command runner."""
        if user_id == runner_id:
            return f"<a:ui_star_new:1239795055150104647><@{user_id}>"  # Highlighted mention
        return f"<@{user_id}>"

    def get_rank_up_message(self) -> str:
        return random.choice(self.rank_up_messages)  # noqa: S311
