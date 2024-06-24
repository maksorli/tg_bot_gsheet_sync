import aiohttp
import logging
from config import id_notification_list


class NotificationSender:
    """
    Initializes the NotificationSender instance with the provided bot token.

    Args:
        token (str): The bot token for authentication with the Telegram API.
    """

    def __init__(self, token: str) -> None:
        """
        Initializes the NotificationSender instance with the provided bot token.

        Args:
            token (str): The bot token for authentication with the Telegram API.
        """
        self.token = token

    def escape_markdown_v2(self, text: str) -> str:
        """
        Escapes special characters in the text for MarkdownV2 format used by Telegram.

        Args:
            text (str): The text to be escaped.

        Returns:
            str: The escaped text suitable for MarkdownV2 formatting.
        """
        escape_chars = r"\_*[]()~`>#+-=|{}.!"
        return "".join(["\\" + char if char in escape_chars else char for char in text])

    async def send_notification(
        self, payload: dict = None, old_payload: dict = None, manager_id=None
    ) -> list:
        """
        Asynchronously sends a notification to all chat IDs stored in id_notification_list using Telegram API.

        Args:
            payload (dict, optional): The current data to be notified about. Defaults to None.
            old_payload (dict, optional): The previous data for comparison. Defaults to None.
            manager_id (any): The manager's ID and name information.

        Returns:
            dict: The response data from the Telegram API upon successful notification.

        Raises:
            Exception: If the notification fails to send due to API errors or connection issues.
        """
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload_changes = {}
        payload_changes_str = ""
        logging.info(f"Type of payload: {type(payload)}")
        logging.info(f"Type of old_payload: {type(old_payload)}")
        logging.info(f"Payload: {payload}")

        for key in payload:
            if key in old_payload:
                try:
                    if payload[key] != old_payload[key]:
                        payload_changes[key] = {
                            "old": old_payload.get(key),
                            "new": payload[key],
                        }
                        payload_changes_str = "\n".join(
                            f"{idx + 1}. {key}: {value['old']} -> {value['new']}"
                            for idx, (key, value) in enumerate(payload_changes.items())
                        )

                        logging.info(
                            f"payload_changes created: {payload_changes}\n {manager_id.id} {manager_id.name}\n {payload_changes_str}"
                        )

                except:
                    logging.info(
                        f"payload_changes NO changes: {payload_changes}\n {manager_id.id} {manager_id.name}"
                    )

        results = []
        async with aiohttp.ClientSession() as session:
            for id in id_notification_list:
                first_name = self.escape_markdown_v2(
                    str(manager_id.first_name) if manager_id.first_name else ""
                )
                last_name = self.escape_markdown_v2(
                    str(manager_id.last_name) if manager_id.last_name else ""
                )
                name = self.escape_markdown_v2(old_payload["name"])
                changes = self.escape_markdown_v2(payload_changes_str)
                payload_message = {
                    "chat_id": id,
                    "text": (
                        f"*From:* {first_name} {last_name}\n"
                        f"*Name:* {name}\n"
                        f"*Changes:*\n{changes}"
                        if payload
                        else "No new updates."
                    ),
                    "parse_mode": "MarkdownV2",
                }

                async with session.post(url, json=payload_message) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        logging.info(
                            f"200 Notification sent successfully to {id}: {response_data}"
                        )
                        results.append(response_data)
                    else:
                        response_text = await response.text()
                        logging.error(
                            f"Failed to send notification to {id}: {response.status}, {response_text}"
                        )
                        results.append(
                            {"status": response.status, "error": response_text}
                        )
        return results
