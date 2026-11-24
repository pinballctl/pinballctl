import unittest
from unittest.mock import patch

from pinballctl.runtime.bridge import daemon
from pinballctl.runtime.bridge.compact_event import decode_event


# Produced by the native compact_event_test fixture.
PAYLOAD = bytes.fromhex(
    "39 03 ff ff ff fe 01 02 03 04 00 00 01 f4 00 0a 42 5f 5f 47 50 49 4f 5f 5f 31 "
    "00 06 43 4c 4f 53 45 44 09 02 00 01 32 00 05 00 04 63 6f 69 6c"
)


class CompactEventTests(unittest.TestCase):
    def test_legacy_event_fields_and_full_observations_are_expanded(self):
        typed, frame_type, payload = daemon._decode_frame(bytes([4]) + PAYLOAD)
        self.assertTrue(typed)
        self.assertEqual(frame_type, 4)
        with patch.object(daemon, "_raw_log_write") as log:
            event = daemon._expand_compact_event(payload)
        self.assertEqual(event, {
            "t": "EVT", "name": "B__GPIO__1_CLOSED", "source": "B__GPIO__1",
            "seq": 0xfffffffe, "tsMs": 0x01020304, "detailMs": 500, "physical": True,
            "eventType": "CLOSED", "inputHigh": False, "rulesApplied": True, "rulesVersion": 3,
            "observedDevices": {"B__GPIO__2": "OPEN", "coil": "ACTIVE"},
        })
        import json
        self.assertEqual(log.call_args.args[0], "RX_JSON")
        self.assertEqual(json.loads(log.call_args.args[1]), event)

    def test_bad_frame_cannot_become_a_physical_edge(self):
        for corrupt in (PAYLOAD[:9], PAYLOAD[:-1], bytes([0x3b]) + PAYLOAD[1:],
                        PAYLOAD[:32] + b'\xff' + PAYLOAD[33:], PAYLOAD + PAYLOAD[-8:]):
            with self.subTest(corrupt=corrupt), self.assertRaises(ValueError):
                decode_event(corrupt)

    def test_diagnostic_frame_has_no_physical_authority(self):
        payload = bytes.fromhex("00 00 00 00 00 01 00 00 00 32 00 01 73 00 00 00 01 6e")
        self.assertEqual(decode_event(payload), {
            "t": "EVT", "name": "n", "source": "s", "seq": 1, "tsMs": 50,
        })
