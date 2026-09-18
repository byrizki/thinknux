"""Tests for asynchronous TelemetryService and snapshot caching."""

import unittest
import time

from thinknux.core.telemetry import TelemetryService, TelemetrySnapshot


class TestTelemetry(unittest.TestCase):
    def test_telemetry_snapshot_defaults(self):
        snap = TelemetrySnapshot()
        self.assertEqual(snap.power_profile, "balanced")
        self.assertEqual(snap.cpu_percent, 0.0)
        self.assertEqual(snap.threshold_stop, 100)

    def test_telemetry_service_lifecycle(self):
        service = TelemetryService(poll_interval=0.5)
        self.assertIsNotNone(service.snapshot)

        received = []
        def on_update(snap):
            received.append(snap)

        service.subscribe("test_sub", on_update)

        # Process any pending GLib idle handlers in test context
        try:
            from gi.repository import GLib
            ctx = GLib.MainContext.default()
            while ctx.iteration(False):
                pass
        except ImportError:
            pass

        self.assertGreaterEqual(len(received), 1)

        service.start()
        service.set_active_view("monitor")
        service.request_poll()
        time.sleep(0.1)

        service.unsubscribe("test_sub")
        service.stop()

        self.assertIsNone(service._thread)


if __name__ == "__main__":
    unittest.main()
