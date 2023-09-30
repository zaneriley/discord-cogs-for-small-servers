# dialog_manager.py
import json
from ...logging_config import get_logger

logger = get_logger(__name__)


class DialogManager:
    def __init__(self, dialog_file: str = "dialogs.json"):
        try:
            with open(dialog_file, "r") as f:
                self.dialogs = json.load(f)
        except FileNotFoundError:
            logger.error(f"Dialog file {dialog_file} not found!")
            self.dialogs = {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {dialog_file}")
            self.dialogs = {}

    def get_dialog(self, dialog_id: str, **kwargs) -> str:
        dialog = self.dialogs.get(dialog_id, "Unknown dialog.")
        return dialog.format(**kwargs)
