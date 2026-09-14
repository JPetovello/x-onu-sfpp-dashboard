import unittest

from alerts import (
    ALERT_HISTORY_MAX_OFFSET,
    AlertManager,
)


class FakeCursor:

    def fetchall(self):
        return []


class FakeConnection:

    def __init__(self):
        self.params = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False

    def close(self):
        self.closed = True

    def execute(
        self,
        _query,
        params,
    ):
        self.params = params
        return FakeCursor()


class AlertPaginationTests(unittest.TestCase):

    def setUp(self):
        self.manager = AlertManager.__new__(
            AlertManager
        )
        self.connection = FakeConnection()
        self.manager._connect_db = (
            lambda: self.connection
        )

    def test_normal_offset_is_preserved(self):
        self.manager.recent_events(
            limit=100,
            offset=250,
        )

        self.assertTrue(self.connection.closed)

        self.assertEqual(
            self.connection.params,
            (
                100,
                250,
            ),
        )

    def test_negative_offset_is_clamped_to_zero(self):
        self.manager.recent_events(
            limit=100,
            offset=-500,
        )

        self.assertTrue(self.connection.closed)

        self.assertEqual(
            self.connection.params,
            (
                100,
                0,
            ),
        )

    def test_excessive_offset_is_bounded(self):
        self.manager.recent_events(
            limit=5000,
            offset=10**12,
        )

        self.assertTrue(self.connection.closed)

        self.assertEqual(
            self.connection.params,
            (
                1000,
                ALERT_HISTORY_MAX_OFFSET,
            ),
        )


if __name__ == "__main__":
    unittest.main()
