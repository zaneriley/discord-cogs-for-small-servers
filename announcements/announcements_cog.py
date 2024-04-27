class AnnouncementAPI:

    def schedule_announcement(self, channel_id, message, event_time, 
                             pre_event_days=7, post_event_days=1, mention_roles=None):
        """
        Schedules an announcement with customizable timing and optional role mentions.

        Args:
            channel_id (int): The ID of the Discord channel where announcements should be made.
            message (str): The announcement text.
            event_time (datetime): A datetime object representing the event's start time.
            pre_event_days (int, optional): Days before the event to send the first announcement (default: 7).
            post_event_days (int, optional): Days after the event to send the final announcement (default: 1).
            mention_roles (list, optional): A list of role IDs to mention in the announcements (default: None).

        Returns:
            int: The unique ID of the scheduled announcement.
        """
        # ... (Internal logic)

    def get_scheduled_announcements(self, channel_id=None, include_past=False):
        """
        Retrieves scheduled announcements with filtering and past announcement options.

        Args:
            channel_id (int, optional): The ID of the channel to filter announcements by.
            include_past (bool, optional): Whether to include past announcements in the results (default: False).

        Returns:
            list: A list of dictionaries, each representing a scheduled announcement. 
                  Each dictionary contains the following keys:
                  - announcement_id (int)
                  - channel_id (int)
                  - message (str)
                  - event_time (datetime)
                  - pre_announcement_time (datetime)
                  - event_announcement_time (datetime)
                  - post_announcement_time (datetime)
                  - mention_roles (list of ints)
        """
        # ... (Internal logic)

    def cancel_announcement(self, announcement_id):
        """
        Cancels a previously scheduled announcement.

        Args:
            announcement_id (int): A unique identifier for the announcement.

        Returns:
            str: A message indicating the outcome ("Announcement canceled" or "Announcement not found").
        """
        # ... (Internal logic)
