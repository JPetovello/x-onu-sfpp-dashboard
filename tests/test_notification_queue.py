import unittest
from unittest.mock import Mock, patch

from notifications import (
    LatestNotificationQueue,
    NotificationManager,
    NOTIFICATION_QUEUE_TTL_SECONDS,
)


class NotificationQueueTests(unittest.TestCase):

    def make_manager(self, maxsize=2):
        manager = NotificationManager.__new__(
            NotificationManager
        )

        manager.notification_queue = (
            LatestNotificationQueue(
                maxsize=maxsize
            )
        )

        return manager

    def get_queued(self, manager):
        return manager.notification_queue.get_nowait()

    def finish_queued(self, manager):
        manager.notification_queue.task_done()

    def test_normal_enqueue_preserves_fifo_order(self):
        manager = self.make_manager()

        manager.process_event({"id": 1})
        manager.process_event({"id": 2})

        first = self.get_queued(manager)
        self.assertEqual(first["event"]["id"], 1)
        self.finish_queued(manager)

        second = self.get_queued(manager)
        self.assertEqual(second["event"]["id"], 2)
        self.finish_queued(manager)

    def test_full_queue_drops_oldest_and_keeps_newest(self):
        manager = self.make_manager()

        manager.process_event({"id": 1})
        manager.process_event({"id": 2})
        manager.process_event({"id": 3})

        self.assertEqual(
            manager.notification_queue.qsize(),
            2,
        )

        first = self.get_queued(manager)
        self.assertEqual(first["event"]["id"], 2)
        self.finish_queued(manager)

        second = self.get_queued(manager)
        self.assertEqual(second["event"]["id"], 3)
        self.finish_queued(manager)

    def test_enqueue_copies_event(self):
        manager = self.make_manager()

        event = {
            "id": 1,
            "nested": {
                "value": "original",
            },
        }

        manager.process_event(event)
        event["nested"]["value"] = "changed"

        queued = self.get_queued(manager)

        self.assertEqual(
            queued["event"]["nested"]["value"],
            "original",
        )

        self.finish_queued(manager)

    def test_drop_oldest_keeps_task_accounting_balanced(self):
        manager = self.make_manager()

        manager.process_event({"id": 1})
        manager.process_event({"id": 2})
        manager.process_event({"id": 3})

        self.assertEqual(
            manager.notification_queue.unfinished_tasks,
            2,
        )

        self.get_queued(manager)
        self.finish_queued(manager)

        self.get_queued(manager)
        self.finish_queued(manager)

        self.assertEqual(
            manager.notification_queue.unfinished_tasks,
            0,
        )

    def test_expired_notification_is_not_delivered(self):
        manager = self.make_manager()

        with patch(
            "notifications.time.monotonic",
            return_value=100.0,
        ):
            manager.process_event({"id": 1})

        queued = self.get_queued(manager)

        manager._send_discord = Mock()
        manager._send_pushover = Mock()
        manager._send_gotify = Mock()
        manager._send_ntfy = Mock()
        manager._send_webhook = Mock()

        with patch(
            "notifications.time.monotonic",
            return_value=(
                100.0
                + NOTIFICATION_QUEUE_TTL_SECONDS
                + 1
            ),
        ):
            delivered = (
                manager._deliver_queued_notification(
                    queued
                )
            )

        self.assertFalse(delivered)

        manager._send_discord.assert_not_called()
        manager._send_pushover.assert_not_called()
        manager._send_gotify.assert_not_called()
        manager._send_ntfy.assert_not_called()
        manager._send_webhook.assert_not_called()

        self.finish_queued(manager)

    def test_recent_notification_is_delivered(self):
        manager = self.make_manager()

        event = {"id": 1}

        with patch(
            "notifications.time.monotonic",
            return_value=100.0,
        ):
            manager.process_event(event)

        queued = self.get_queued(manager)

        manager._send_discord = Mock()
        manager._send_pushover = Mock()
        manager._send_gotify = Mock()
        manager._send_ntfy = Mock()
        manager._send_webhook = Mock()

        with patch(
            "notifications.time.monotonic",
            return_value=(
                100.0
                + NOTIFICATION_QUEUE_TTL_SECONDS
                - 1
            ),
        ):
            delivered = (
                manager._deliver_queued_notification(
                    queued
                )
            )

        self.assertTrue(delivered)

        manager._send_discord.assert_called_once_with(event)
        manager._send_pushover.assert_called_once_with(event)
        manager._send_gotify.assert_called_once_with(event)
        manager._send_ntfy.assert_called_once_with(event)
        manager._send_webhook.assert_called_once_with(event)

        self.finish_queued(manager)


if __name__ == "__main__":
    unittest.main()
