import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from pinballctl.app.modules.hardware.coil_safety import coil_safety
from pinballctl.ops.coil_config import normalize_coil_settings, build_coil_configs


class CoilSafetyTests(unittest.TestCase):
    def test_conservative_defaults_and_independent_overrides(self):
        mapping = {
            'ESP__MAIN__GPIO__6': {'function':'Coil','driver':'Default','safety':'LOW'},
            'ESP__MAIN__GPIO__7': {'function':'Coil','driver':'Default','safety':'HIGH',
                                 'coilEnabled':'Enabled','coilMaxOnMs':60,'coilMinOffMs':2000},
        }
        a,b = build_coil_configs(mapping)
        self.assertEqual({k:a[k] for k in ('pin','max_on_ms','min_off_ms','off_high','enabled')}, dict(pin=6,max_on_ms=20,min_off_ms=1000,off_high=False,enabled=False))
        self.assertEqual({k:b[k] for k in ('pin','max_on_ms','min_off_ms','off_high','enabled')}, dict(pin=7,max_on_ms=60,min_off_ms=2000,off_high=True,enabled=True))
        self.assertNotIn('coilMaxOnMs', mapping['ESP__MAIN__GPIO__6'])

    def test_invalid_overrides_are_rejected(self):
        for row in ({'coilMaxOnMs':0}, {'coilMaxOnMs':1001}, {'coilMinOffMs':1},
                    {'coilMaxOnMs':True}, {'coilMaxOnMs':1.5}, {'coilMaxOnMs':'20'},
                    {'coilEnabled':'yes'}, {'safety':'unknown'}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                normalize_coil_settings(row)

    def test_modes_and_pair_constraints(self):
        power='ESP__MAIN__GPIO__6'; hold='ESP__MAIN__GPIO__7'
        rows={power:dict(function='Coil',coilEnabled='Enabled',coilMode='Separate power and hold',coilHoldPinUid=hold),
              hold:dict(function='Coil',coilEnabled='Enabled',coilMode='Hold winding',safety='HIGH')}
        configs=build_coil_configs(rows)
        self.assertEqual(configs[0]['hold_pin'],7)
        self.assertTrue(configs[1]['off_high'])
        for changes in ({'coilMode':'Pulse only'}, {'coilEnabled':'Disabled'}, {'coilMaxHoldMs':500}):
            invalid={power:rows[power],hold:dict(rows[hold],**changes)}
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                build_coil_configs(invalid)
        rows[power]['coilHoldPinUid']=power
        with self.assertRaises(ValueError): build_coil_configs(rows)
        with self.assertRaises(ValueError):
            normalize_coil_settings(dict(coilMode='Pulse + PWM hold',coilEnabled='Enabled'))
        for changes in ({'coilHoldDuty':3}, {'coilPwmHz':'999'}, {'coilPulseMs':21}, {'coilMode':'Board-managed hold'}, {'coilMode':[]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): normalize_coil_settings(changes)
        valid=normalize_coil_settings(dict(coilMode='Pulse + PWM hold',coilEnabled='Enabled',coilHoldDuty=25))
        self.assertEqual(valid['coilHoldDuty'],25)

    def test_hold_windings_are_not_independent_rule_targets(self):
        from pinballctl.app.modules.rules.api import _build_hardware_devices
        rows={'power':dict(function='Coil',coilMode='Separate power and hold',coilHoldPinUid='hold'),
              'hold':dict(function='Coil',coilMode='Hold winding'),
              'led':dict(function='LED')}
        devices,_=_build_hardware_devices(rows)
        self.assertEqual({d['id'] for d in devices},{'power','led'})

    def test_mapping_save_persists_defaults_and_rejects_bad_cooldown(self):
        from pinballctl.app.modules.hardware.api import api_bp
        with tempfile.TemporaryDirectory() as tmp:
            app=Flask(__name__,instance_path=tmp)
            app.register_blueprint(api_bp,url_prefix='/api/hardware')
            pins=[dict(uid=f'ESP__MAIN__GPIO__{pin}',type='GPIO',chan=str(pin),safe=True) for pin in (6,7)]
            mapping={p['uid']:dict(function='Coil',driver='Default',safety='LOW') for p in pins}
            with patch('pinballctl.app.modules.hardware.api._load_discovered_payload',return_value={'pins':pins,'controller':'ESP'}):
                response=app.test_client().post('/api/hardware/save',json=mapping)
                self.assertEqual(response.status_code,200,response.json)
                saved=json.loads((Path(tmp)/'hardware/mapping.json').read_text())['data']
                self.assertEqual(saved[pins[0]['uid']]['coilEnabled'],'Disabled')
                self.assertEqual(saved[pins[1]['uid']]['coilMaxOnMs'],20)
                mapping[pins[1]['uid']]['coilMinOffMs']=2
                response=app.test_client().post('/api/hardware/save',json=mapping)
                self.assertEqual(response.status_code,422)
                self.assertEqual(json.loads((Path(tmp)/'hardware/mapping.json').read_text())['data'],saved)

    def test_hardware_sync_requires_acknowledged_limits_before_blob(self):
        from datetime import datetime, timezone
        from pinballctl.app.modules.hardware.api import api_bp
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'hardware'
            base.mkdir()
            mapping={'ESP__MAIN__GPIO__6':dict(function='Coil',driver='Default',safety='LOW')}
            (base/'mapping.json').write_text(json.dumps(mapping))
            (base/'discovered.json').write_text('{}')
            app=Flask(__name__,instance_path=tmp)
            app.register_blueprint(api_bp,url_prefix='/api/hardware')
            state=dict(connected=True,port='test',updated_at=datetime.now(timezone.utc).isoformat())
            prefix='pinballctl.app.modules.hardware.api.'
            with patch('pinballctl.app.modules.esplink.api.ensure_bridge_connection',return_value=True), \
                    patch(prefix+'read_bridge_state',return_value=state), patch(prefix+'rpc_command') as rpc, \
                    patch(prefix+'queue_blob_put') as queue, patch(prefix+'enqueue_command'):
                rpc.return_value=None
                response=app.test_client().post('/api/hardware/sync')
                self.assertEqual(response.status_code,409)
                self.assertEqual(response.json['reason'],'firmware_upgrade_or_connection_check_required')
                self.assertIn('Install firmware built from the current source',response.json['message'])
                queue.assert_not_called()
                rpc.return_value=dict(t='COIL_STATUS',ok=True,armed=True,coils=build_coil_configs(mapping))
                response=app.test_client().post('/api/hardware/sync')
                self.assertEqual(response.status_code,409)
                self.assertEqual(response.json['reason'],'configuration_mismatch')
                queue.assert_not_called()
                rpc.return_value=dict(t='COIL_STATUS',ok=True,armed=False,coils=build_coil_configs(mapping))
                self.assertEqual(app.test_client().post('/api/hardware/sync').status_code,200)
                queue.assert_called_once()
                self.assertEqual(rpc.call_args.args[0]['coils'][0]['enabled'],False)

    def test_api_requires_explicit_arm_token_and_no_automatic_retry(self):
        app=Flask(__name__)
        app.add_url_rule('/safety', view_func=coil_safety, methods=['GET','POST'])
        client=app.test_client()
        with patch('pinballctl.app.modules.hardware.coil_safety.rpc_command') as rpc:
            self.assertEqual(client.post('/safety',json={'action':'arm'}).status_code,400)
            self.assertEqual(client.post('/safety',json={'action':'arm'},headers={'X-Coil-Control':'1'}).status_code,400)
            rpc.assert_not_called()
            rpc.side_effect=TimeoutError()
            response=client.post('/safety',json={'action':'arm','generation':42},headers={'X-Coil-Control':'1'})
            self.assertEqual(response.status_code,503)
            rpc.assert_called_once_with({'cmd':'ENABLE','generation':42},match_t='COIL_STATUS',timeout_s=2.0)

    def test_native_firmware_policy(self):
        compiler=shutil.which('c++')
        if not compiler: self.skipTest('C++ compiler unavailable')
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            executable=str(Path(tmp)/'coil-safety-test')
            subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',
                            '-I'+str(root/'src/firmware/src'),str(root/'tests/firmware/coil_safety_test.cpp'),
                            '-o',executable],check=True)
            subprocess.run([executable],check=True)
