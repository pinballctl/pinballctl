"""Live View must retain press/release edges across SSE drain batches."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from pinballctl.events.bus import EventBus
from pinballctl.app.modules.events.api import stream_events


class EventStreamTests(unittest.TestCase):
    def test_burst_preserves_every_event_across_batches_and_partial_lines(self):
        app = Flask(__name__)
        bus = EventBus()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.log'
            path.touch()
            with app.test_request_context('/stream'), patch(
                    'pinballctl.app.modules.events.api.get_bus', return_value=bus), patch(
                    'pinballctl.app.modules.events.api.events_log_path', return_value=path):
                response = stream_events()
                iterator = iter(response.response)
                ready = bus.emit('ready')
                self.assertIn('ready', next(iterator))
                records = [json.dumps(dict(origin='bridge', direction='esp->pi', name='switch',
                           params=dict(seq=i, eventType='RELEASED' if i % 2 else 'PRESSED')))
                           for i in range(81)]
                # Force a read boundary inside a JSON line, beyond the read cap.
                records[40] = records[40][:-1] + ',"padding":"' + 'x' * 65536 + '"}'
                records.append(json.dumps(dict(origin='scoring', direction='pi->pi', name='SCORE_CHANGED',
                    params=dict(seq=81, score=99), meta=dict(event_id='score-local'))))
                duplicate = json.dumps(dict(origin='scoring', direction='pi->pi', name='ready',
                                           params={}, meta=dict(event_id=ready.id)))
                path.write_text(duplicate + '\n' + '\n'.join(records) + '\n')
                received = [json.loads(next(iterator).removeprefix('data: ').strip()) for _ in records]
                self.assertEqual([r['params']['seq'] for r in received], list(range(82)))
                self.assertEqual(received[79]['params']['eventType'], 'RELEASED')
                self.assertEqual(received[-1]['params']['score'], 99)
                iterator.close()
                self.assertFalse(bus._subscribers)
