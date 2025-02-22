import json
import logging
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class DialogNotFoundError(Exception):

    """Raised when a dialog is not found."""


class DialogManager:
    def __init__(self):
        self.dialogs_path = os.path.join(os.path.dirname(__file__), "dialogs.json")
        self.dialogs = self._load_dialogs()

    def _load_dialogs(self) -> dict[str, str]:
        """Load the dialogs from the JSON file and return them as a dictionary."""
        if os.path.exists(self.dialogs_path):
            try:
                with open(self.dialogs_path, encoding="utf-8") as file:
                    return json.load(file)
            except json.JSONDecodeError:
                logger.exception(f"Error decoding JSON from {self.dialogs_path}")
                return {}
        else:
            logger.error(f"Dialog file {self.dialogs_path} does not exist!")
            return {}

    def get_dialog(self, dialog_id: str) -> str:
        """
        Retrieve a specific dialog by its ID.

        Args:
        ----
            dialog_id (str): The ID of the dialog to retrieve.

        Returns:
        -------
            str: The dialog associated with the given ID.

        Raises:
        ------
            DialogNotFoundError: If the dialog ID is not found.

        """
        dialog = self.dialogs.get(dialog_id)
        if not dialog:
            msg = f"Dialog ID '{dialog_id}' not found."
            raise DialogNotFoundError(msg)
        return dialog

    def reload_dialogs(self) -> None:
        """Reload the dialogs from the JSON file."""
        self.dialogs = self._load_dialogs()
