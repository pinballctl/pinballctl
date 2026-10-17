"""Validate and compile independently bounded coil assemblies."""
from pinballctl.ops.mapping_blob import _parse_gpio_pin

DEFAULT_MAX_ON_MS = 20
DEFAULT_MIN_OFF_MS = 1000
MODES = {'Pulse only':'pulse', 'Pulse + PWM hold':'pwm',
         'Separate power and hold':'dual', 'Continuous duty':'continuous',
         'Hold winding':'hold'}
PWM_FREQUENCIES = (50, 100, 250, 500)


def normalize_coil_settings(row):
    result = {}
    for key, default, minimum, maximum in (
        ('coilMaxOnMs', DEFAULT_MAX_ON_MS, 1, 1000),
        ('coilMinOffMs', DEFAULT_MIN_OFF_MS, 1, 60000),
        ('coilPulseMs', 10, 1, 1000),
        ('coilMaxHoldMs', 1000, 1, 60000),
        ('coilHoldDuty', 0, 0, 95),
    ):
        value = row.get(key, default)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f'{key} must be an integer from {minimum} to {maximum}')
        result[key] = value
    mode = row.get('coilMode', 'Pulse only')
    if not isinstance(mode, str) or mode not in MODES:
        raise ValueError('Unsupported coil operating mode')
    if result['coilMinOffMs'] < result['coilMaxOnMs']:
        raise ValueError('Coil cooldown must be at least the maximum on-time')
    if mode in ('Pulse only', 'Pulse + PWM hold', 'Separate power and hold') and result['coilPulseMs'] > result['coilMaxOnMs']:
        raise ValueError('Initial pulse must not exceed the hard pulse limit')
    enabled = row.get('coilEnabled', 'Disabled')
    if enabled not in ('Disabled', 'Enabled'):
        raise ValueError('coilEnabled must be Disabled or Enabled')
    frequency = row.get('coilPwmHz', '100')
    if str(frequency) not in tuple(map(str, PWM_FREQUENCIES)):
        raise ValueError('Unsupported PWM frequency')
    if result['coilHoldDuty'] % 5:
        raise ValueError('PWM hold duty must use 5% increments')
    if mode == 'Pulse + PWM hold' and enabled == 'Enabled' and not result['coilHoldDuty']:
        raise ValueError('Set a hardware-appropriate hold duty before enabling PWM hold')
    off = row.get('safety') or 'LOW'
    if off not in ('LOW', 'HIGH'):
        raise ValueError('PIN Safe must be LOW or HIGH')
    partner = row.get('coilHoldPinUid', '')
    if not isinstance(partner, str):
        raise ValueError('Invalid hold pin')
    result.update(coilEnabled=enabled, safety=off, coilMode=mode,
                  coilPwmHz=str(frequency), coilHoldPinUid=partner if mode == 'Separate power and hold' else '')
    return result


def build_coil_configs(mapping):
    configs, by_uid, seen = [], {}, set()
    for uid, row in mapping.items():
        if not isinstance(row, dict) or row.get('function') not in ('Coil', 'Solenoid'):
            continue
        pin = _parse_gpio_pin(uid)
        if pin is None or not 0 <= pin < 49 or pin in seen:
            raise ValueError('Each coil requires a unique ESP GPIO pin')
        if row.get('driver', 'Default') != 'Default':
            raise ValueError('Unsupported coil driver')
        seen.add(pin)
        s = normalize_coil_settings(row)
        config = dict(pin=pin, max_on_ms=s['coilMaxOnMs'], min_off_ms=s['coilMinOffMs'],
                      off_high=s['safety'] == 'HIGH', enabled=s['coilEnabled'] == 'Enabled',
                      mode=MODES[s['coilMode']], pulse_ms=s['coilPulseMs'],
                      max_hold_ms=s['coilMaxHoldMs'], hold_duty=s['coilHoldDuty'],
                      pwm_hz=int(s['coilPwmHz']), hold_pin=-1)
        configs.append(config)
        by_uid[uid] = config
    linked = set()
    for uid, config in by_uid.items():
        if config['mode'] != 'dual':
            continue
        partner_uid = mapping[uid].get('coilHoldPinUid', '')
        partner = by_uid.get(partner_uid)
        if not partner or partner['mode'] != 'hold' or partner_uid in linked or partner_uid == uid:
            raise ValueError('Select a unique Coil / Hold winding pin for each paired coil')
        if partner_uid.rsplit('__GPIO__', 1)[0] != uid.rsplit('__GPIO__', 1)[0]:
            raise ValueError('Power and hold pins must be on the same controller and board')
        if config['enabled'] and not partner['enabled']:
            raise ValueError('Enable the linked hold winding before enabling the power pin')
        if config['max_hold_ms'] > partner['max_hold_ms']:
            raise ValueError('Assembly hold limit exceeds the hold winding limit')
        config['hold_pin'] = partner['pin']
        linked.add(partner_uid)
    for uid, config in by_uid.items():
        if config['mode'] == 'hold' and config['enabled'] and uid not in linked:
            raise ValueError('An enabled hold winding must belong to a paired power pin')
    return configs
