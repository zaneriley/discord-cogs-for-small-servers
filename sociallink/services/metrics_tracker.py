
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import pandas as pd

from sociallink.services.events import Events, event_bus

logger = logging.getLogger(__name__)

# Log a csv to the root of this cog's directory
current_directory = Path(__file__).resolve().parent.parent
metrics_directory = current_directory / "metrics"
logger.info(f"Metrics directory: {metrics_directory}")
metrics_directory.mkdir(parents=True, exist_ok=True)

class MetricsTracker:
    metrics: ClassVar[defaultdict] = defaultdict(list)

    def __init__(self, bot, config, event_bus):
        self.bot = bot
        self.config = config
        self.event_bus = event_bus
        self.metrics = defaultdict(list)

        logging.basicConfig(filename="metrics-sociallink.log", level=logging.INFO, format="%(asctime)s - %(message)s")

    async def setup(self):
        await self.load_metrics_enabled()

    async def load_metrics_enabled(self):
        # Use the appropriate method to get a value from config
        self.metrics_enabled = await self.config.get_raw("metrics_enabled", default=False)

    def calculate_metrics(self):
        if not self.metrics_enabled:
            return False, "Metrics are not enabled."


    @classmethod
    async def log_event(cls, event_type, details):
        log_entry = {"timestamp": datetime.now(tz=UTC), "event_type": event_type}
        log_entry.update(details)

        cls.metrics[event_type].append(log_entry)
        logging.info("%s: %s", event_type, details)
        event_count_before_save = 10
        if sum(len(events) for events in cls.metrics.values()) >= 1:
            await cls.save_metrics()

    @classmethod
    async def save_metrics(cls):
        try:
            metric_df = pd.DataFrame(cls.metrics)
            csv_path = metrics_directory / "metrics.csv"
            metric_df.to_csv(csv_path, mode="a", header=not csv_path.exists(), index=False)
            cls.metrics.clear()  # Clear the list once saved.

        except Exception:
            logger.exception("Error saving metrics to CSV:")

    def generate_report(self):
        pass

    def enable_metrics(self):
        self.metrics_enabled = True

    def disable_metrics(self):
        self.metrics_enabled = False

    def get_metrics(self):
        return self.metrics if self.metrics_enabled else None

    @event_bus.subscribe(Events.ON_MESSAGE_MENTION)
    def handle_user_activity(self, *args, **kwargs):
        # Increment active user count
        pass

    @event_bus.subscribe(Events.ON_VOICE_CHANNEL_JOIN)
    def handle_voice_channel_join(*args, **kwargs):
        user_id = kwargs.get("user_id")
        MetricsTracker.metrics["voice_channel_joins"].append({
            "timestamp": datetime.now(tz=UTC),
            "user_id": user_id,
        })

    @event_bus.subscribe(Events.ON_SOCIAL_LINK)
    def handle_social_link(self, *args, **kwargs):
        # Increment social links created count
        # Update total social link score
        pass

    @event_bus.subscribe(Events.ON_LEVEL_UP)
    def handle_level_up(self, *args, **kwargs):
        # Increment rank changes count
        pass
