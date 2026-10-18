import copy
import unittest

from pinballctl.app.modules.playfield.api import _remap_layout_ids


class LinkedDisplayBindingsTests(unittest.TestCase):
    def test_secondary_display_pin_keeps_layout_and_resolves_primary(self):
        primary = 'ESP-new__MAIN__GPIO__3'
        secondary = 'ESP-new__MAIN__GPIO__8'
        old = 'ESP-old__MAIN__GPIO__8'
        mapping = {'data': {primary: {'function': 'LCD Display'}, secondary: {'linkedPrimaryUid': primary}}}
        layout = {'elements': [{'id': old, 'hardwareId': old, 'icon': 'lcd-display',
                                'nx': .84, 'ny': .05, 'scale': 2.45}],
                  'keymap': {'x': {'id': old}}}
        original = copy.deepcopy(layout)
        result = _remap_layout_ids(layout, mapping)
        self.assertEqual(result['elements'][0], {**original['elements'][0], 'id': primary, 'hardwareId': primary})
        self.assertEqual(result['keymap']['x']['id'], primary)
        self.assertEqual(layout, original)

    def test_custom_element_id_is_preserved_and_missing_primary_is_not_invented(self):
        secondary = 'ESP__MAIN__GPIO__8'
        layout = {'elements': [{'id': 'display-instance', 'hardwareId': secondary}]}
        mapping = {'data': {secondary: {'linkedPrimaryUid': 'ESP__MAIN__GPIO__3'}}}
        self.assertEqual(_remap_layout_ids(layout, mapping), layout)
        mapping['data']['ESP__MAIN__GPIO__3'] = {}
        self.assertEqual(_remap_layout_ids(layout, mapping)['elements'][0],
                         {'id': 'display-instance', 'hardwareId': 'ESP__MAIN__GPIO__3'})

    def test_legacy_element_id_and_cyclic_links(self):
        a, b = 'ESP__MAIN__GPIO__3', 'ESP__MAIN__GPIO__8'
        layout = {'elements': [{'id': b, 'icon': 'lcd-display'}]}
        self.assertEqual(_remap_layout_ids(layout, {'data': {a: {}, b: {'linkedPrimaryUid': a}}})['elements'][0]['id'], a)
        self.assertEqual(_remap_layout_ids(layout, {'data': {a: {'linkedPrimaryUid': b}, b: {'linkedPrimaryUid': a}}}), layout)
