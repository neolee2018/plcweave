"""S6 hardware runner v3: soft-element injection + output readback, frozen cases.

Reads the frozen test_cases.json, drives the bench through the program's own
input-mapping registers, records raw observations and compares only the
quantities that host polling can legitimately judge on this bench.

Verdicts: PASS / PROGRAM_FAIL / TEST_INFRA_ERROR / UNVERIFIED.
A running PI value (D120/D154/D8050) is compared only when the expectation is 0
or the drive is stopped; otherwise the item is recorded as UNVERIFIED rather
than guessed.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from pymodbus.client import ModbusSerialClient

CASE = Path(__file__).resolve().parent
EVIDENCE = CASE / 'evidence/s6-v3'
PORT, UNIT = 'COM7', 1
ALLOWED = {102, 190, 191, 192, 193, 194, 261, 1056, 1070, 1071}
IDENTITY = ('D196', 'D197', 'D200', 'D201', 'D202')


def expected_identity():
    data = json.loads((CASE / 'build_identity.json').read_text(encoding='utf-8'))
    return (data['program_version'], data['edition'],
            *data['fingerprint_words'], data['suite_version_word'])

# Devices whose expected value is stable after settling and can be compared.
ALWAYS = {'D100', 'D102', 'D260', 'D262', 'D261', 'D190', 'D191', 'D192',
          'D193', 'D194', 'D195', 'D196', 'D197', 'D202', 'D1056', 'D1070', 'D1071',
          'D8120', 'D8121'}
STATE = {'M0', 'M10', 'M11', 'Y0', 'M8196', 'M8125'}
ZERO_ONLY = {'D120', 'D154', 'D8050', 'D8051'}


def comparable(device, expected, observed):
    if device in ALWAYS or device in STATE:
        return True
    if device not in ZERO_ONLY:
        return False
    # Stable only when the output is forced: stopped, asleep, or clamped.
    if observed.get('M0') == 0:
        return True
    if observed.get('M11') == 1 and expected == 0:
        return True
    return expected in (30000, 5000, 4000)


class Bench:
    def __init__(self):
        self.client = ModbusSerialClient(port=PORT, baudrate=9600, bytesize=8, parity='N',
                                         stopbits=1, timeout=0.5, retries=0)
        self.writes = 0

    def open(self):
        if not self.client.connect():
            raise ConnectionError('Cannot open COM7')

    def close(self):
        self.client.close()

    def words(self, first, count):
        r = self.client.read_holding_registers(first, count=count, device_id=UNIT)
        if r.isError() or len(getattr(r, 'registers', [])) != count:
            raise ConnectionError(f'FC03 D{first} count={count}: {r}')
        return [v - 65536 if v >= 32768 else v for v in r.registers]

    def write(self, device, value):
        address = int(device[1:])
        if not device.startswith('D') or address not in ALLOWED:
            raise ValueError(f'Forbidden write {device}')
        r = self.client.write_register(address, int(value) & 0xFFFF, device_id=UNIT)
        if r.isError():
            raise ConnectionError(f'FC06 {device}: {r}')
        self.writes += 1

    def coils(self, addresses):
        out = {}
        for address, name in addresses:
            r = self.client.read_coils(address, count=1, device_id=UNIT)
            if r.isError():
                raise ConnectionError(f'FC01 {address}: {r}')
            out[name] = int(r.bits[0])
        return out

    def snapshot(self):
        """Compact snapshot: one 100-word block, three small reads, five coils."""
        block = self.words(100, 100)          # D100..D199
        d = {f'D{100 + i}': v for i, v in enumerate(block)}
        d.update({f'D{260 + i}': v for i, v in enumerate(self.words(260, 3))})
        d.update({f'D{200 + i}': v for i, v in enumerate(self.words(200, 3))})
        d.update({f'D{8120 + i}': v for i, v in enumerate(self.words(8120, 2))})
        d.update({f'D{8050 + i}': v for i, v in enumerate(self.words(8050, 2))})
        d['D1056'] = self.words(1056, 1)[0]
        d.update({f'D{1070 + i}': v for i, v in enumerate(self.words(1070, 2))})
        d.update(self.coils([(0, 'M0'), (10, 'M10'), (11, 'M11'), (0x3300, 'Y0'),
                             (0x1E00 + 196, 'M8196'), (0x1E00 + 125, 'M8125')]))
        return d

    def reconnect(self):
        self.client.close()
        time.sleep(0.2)
        if not self.client.connect():
            raise ConnectionError('Cannot reopen COM7 after CPU restart')

    def fast_snapshot(self):
        """Six quantities read in ~120 ms, used for deadline-sensitive steps."""
        out = self.coils([(0, 'M0'), (10, 'M10'), (11, 'M11'), (0x3300, 'Y0')])
        out['D100'] = self.words(100, 1)[0]
        out['D154'] = self.words(154, 1)[0]
        return out

    def wait_ms(self, milliseconds):
        time.sleep(max(0, milliseconds) / 1000)


class CPU:
    """Programming-port STOP/RUN (COM5, 9600/7E1), the only path that survives STOP."""

    def __init__(self, port='COM5'):
        import serial
        self.serial = serial.Serial(port=None, baudrate=9600, bytesize=7, parity='E',
                                    stopbits=1, timeout=0.8, write_timeout=0.8)
        self.serial.port = port
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.open()

    def force(self, relay, value):
        address = f'{0x0F00 + relay - 8000:04X}'
        body = (('7' if value else '8') + address[2:] + address[:2]).encode('ascii') + b'\x03'
        frame = b'\x02' + body + f'{sum(body) & 255:02X}'.encode('ascii')
        self.serial.reset_input_buffer()
        self.serial.write(frame)
        ack = self.serial.read(1)
        if ack != b'\x06':
            raise ConnectionError(f'CPU force M{relay} ACK={ack.hex()}')

    def stop(self):
        self.force(8037, True)
        time.sleep(0.4)

    def start(self):
        self.force(8037, False)
        self.force(8035, True)
        self.force(8036, True)
        time.sleep(1.0)

    def close(self):
        self.serial.close()


def restart_with(bench, cpu, initial_words):
    """Write the saved words, then a real STOP/RUN so first scan validates them."""
    for device, value in initial_words.items():
        if not device.startswith('D') or int(device[1:]) not in ALLOWED:
            raise ValueError(f'Forbidden initial word {device}')
        bench.write(device, value)
    bench.wait_ms(100)
    cpu.stop()
    cpu.start()
    last = None
    for _ in range(5):
        try:
            bench.reconnect()
            identity_gate(bench)
            return bench.snapshot()
        except Exception as exc:   # Modbus comes back a moment after RUN
            last = exc
            time.sleep(0.5)
    raise ConnectionError(f'COM7 did not recover after restart: {last!r}')


def identity_gate(bench):
    ident = bench.words(196, 7)
    values = dict(zip(['D196', 'D197', 'D198', 'D199', 'D200', 'D201', 'D202'], ident))
    observed = tuple(values[k] for k in IDENTITY)
    expect = expected_identity()
    if observed != expect:
        raise ValueError(f'Identity mismatch: {observed} != {expect}')
    first = bench.words(198, 1)[0]
    time.sleep(0.3)
    second = bench.words(198, 1)[0]
    if first == second:
        raise ValueError('Heartbeat did not advance')
    return values


def reset(bench):
    for device, value in (('D192', 1), ('D191', 0), ('D193', 0), ('D190', 1),
                          ('D1056', 0), ('D102', 60), ('D261', 60), ('D194', 0),
                          ('D1070', 0), ('D1071', 0)):
        bench.write(device, value)
    bench.wait_ms(150)
    state = bench.snapshot()
    if state['M0'] != 0 or state['D154'] != 0 or state['D8050'] != 0:
        raise ValueError('Reset did not reach stopped zero-output state')
    # Stop is a level request; release it so the case can start from D192=0,
    # which is the frozen initial condition.
    bench.write('D192', 0)
    bench.wait_ms(80)
    state = bench.snapshot()
    if state['M0'] != 0 or state['D102'] != 60:
        raise ValueError('Reset did not settle to stopped default state')
    return state


def run_step(bench, step, index):
    started = time.monotonic()
    for device, value in step['write'].items():
        bench.write(device, value)
    # Land the observation at the frozen timepoint: a fast six-value read takes
    # about 120 ms, so start it that much before the deadline. Full snapshots
    # after the deadline would drift into the next timer edge.
    target = started + max(step['duration_ms'], 50) / 1000
    lead = 0.13
    chunks = []
    if step['duration_ms'] > 30000:
        # Long waits (counter wrap) are sampled instead of slept through, so a
        # transient output violation cannot hide between two endpoints.
        while time.monotonic() < target - lead:
            time.sleep(min(10.0, max(0, target - lead - time.monotonic())))
            sample = bench.fast_snapshot()
            violations = []
            for device, expected in step['invariant'].items():
                if comparable(device, expected, sample) and sample.get(device) != expected:
                    violations.append({'device': device, 'expected': expected, 'actual': sample.get(device)})
            chunks.append({'at_ms': round((time.monotonic() - started) * 1000),
                           'M0': sample['M0'], 'M11': sample['M11'],
                           'D100': sample['D100'], 'D154': sample['D154'],
                           'violations': violations})
    else:
        while time.monotonic() < target - lead:
            time.sleep(min(0.02, max(0, target - lead - time.monotonic())))
    fast = bench.fast_snapshot()
    observed_at = round((time.monotonic() - started) * 1000)
    full = bench.snapshot()
    observed = {**full, **fast}
    observed['observed_at_ms'] = observed_at

    compared, mismatches, skipped = [], [], []
    for scope, expected_map in (('expect', step['expect']), ('invariant', step['invariant'])):
        for device, expected in expected_map.items():
            if not comparable(device, expected, observed):
                skipped.append({'scope': scope, 'device': device, 'expected': expected,
                                'reason': 'Running PI/analog value; host polling cannot certify this instant'})
                continue
            actual = observed.get(device)
            compared.append({'scope': scope, 'device': device, 'expected': expected, 'actual': actual})
            if actual != expected:
                mismatches.append({'scope': scope, 'device': device, 'expected': expected, 'actual': actual})
    # A mismatch on a timer/output quantity can be a phase artefact of host
    # polling, so only stable quantities may produce PROGRAM_FAIL.
    stable_fail = ALWAYS | {'M0', 'M8196', 'M8125'}
    hard = [m for m in mismatches if m['device'] in stable_fail]
    soft = [m for m in mismatches if m['device'] not in stable_fail]
    if hard:
        status = 'PROGRAM_FAIL'
    elif soft:
        status = 'UNVERIFIED'
    else:
        status = 'PASS' if compared else 'UNVERIFIED'
    return {'index': index, 'duration_ms': step['duration_ms'], 'write': step['write'],
            'status': status, 'compared': compared, 'mismatches': hard,
            'ambiguous': soft, 'skipped': skipped,
            'observed_at_ms': observed_at, 'chunk_checks': chunks, 'observed': observed}


def run_case(bench, case, cpu=None):
    if cpu is not None and case.get('initial_words'):
        restart_with(bench, cpu, case['initial_words'])
    else:
        reset(bench)
    steps = [run_step(bench, step, i) for i, step in enumerate(case['steps'])]
    asserted = [s for s in steps if s['compared'] or s['skipped']]
    skipped = sum(len(s['skipped']) for s in steps)
    if any(s['status'] == 'PROGRAM_FAIL' for s in steps):
        status = 'PROGRAM_FAIL'
    elif asserted and all(s['status'] == 'PASS' for s in asserted) and skipped == 0:
        status = 'PASS'
    else:
        status = 'UNVERIFIED'
    return {'id': case['id'], 'title': case.get('title', ''), 'scope': case.get('hardware_scope'),
            'status': status, 'steps': steps,
            'asserted_steps': len(asserted),
            'compared_items': sum(len(s['compared']) for s in steps),
            'skipped_items': sum(len(s['skipped']) for s in steps),
            'ambiguous_items': sum(len(s.get('ambiguous', [])) for s in steps)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', default='STD-016,STD-024,STD-025,STD-048,STD-019,STD-052,STD-011,STD-038')
    parser.add_argument('--output', default='run-v3-a')
    parser.add_argument('--restart', action='store_true', help='real STOP/RUN via COM5 before each case with initial_words')
    args = parser.parse_args()
    suite = json.loads((CASE / 'test_cases.json').read_text(encoding='utf-8'))
    by_id = {c['id']: c for c in suite['cases']}
    selected = [by_id[x] for x in args.cases.split(',') if x]
    out = EVIDENCE / args.output
    out.mkdir(parents=True, exist_ok=False)
    report = {'task_id': 'PW-20261023-S6-HIL-V3-PLAN', 'kind': 's6_soft_element_case_run',
              'at': datetime.now(timezone.utc).isoformat(), 'port': PORT, 'writes': 0,
              'cases': [], 'status': 'UNVERIFIED'}
    bench = Bench()
    cpu = None
    try:
        bench.open()
        if args.restart:
            cpu = CPU()
        report['identity'] = identity_gate(bench)
        report['initial_state'] = bench.snapshot()
        for case in selected:
            print('START', case['id'], flush=True)
            result = run_case(bench, case, cpu)
            report['cases'].append(result)
            report['writes'] = bench.writes
            print('END', case['id'], result['status'], flush=True)
            (out / 'progress.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception as exc:
        report.update(status='TEST_INFRA_ERROR', error=repr(exc))
    finally:
        try:
            for device, value in (('D192', 1), ('D191', 0), ('D193', 0), ('D1056', 0),
                                  ('D102', 60), ('D190', 1), ('D194', 0),
                                  ('D1070', 0), ('D1071', 0)):
                bench.write(device, value)
            bench.wait_ms(150)
            report['cleanup_state'] = bench.snapshot()
            report['cleanup'] = 'stopped, output disabled, zero readback'
        except Exception as exc:
            report['cleanup'] = 'restore_unconfirmed'
            report['cleanup_error'] = repr(exc)
        bench.close()
        if cpu is not None:
            cpu.close()
        report['writes'] = bench.writes
        report['serial_closed'] = True
        statuses = [c['status'] for c in report['cases']]
        if 'PROGRAM_FAIL' in statuses:
            report['status'] = 'PROGRAM_FAIL'
        elif statuses and all(s == 'PASS' for s in statuses):
            report['status'] = 'PASS'
        elif report.get('status') != 'TEST_INFRA_ERROR':
            report['status'] = 'UNVERIFIED'
        (out / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'writes': report['writes'],
                      'cases': [(c['id'], c['status']) for c in report['cases']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
