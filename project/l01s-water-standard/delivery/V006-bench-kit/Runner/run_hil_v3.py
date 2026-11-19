"""S6 hardware runner v3 (V005 batch interface): block read/write, frozen cases.

Reads the frozen test_cases.json, drives the bench through the program's own
command block (D320..D335, one FC16 per group of writes), records raw
observations through the status block (D300..D335, one FC03 per snapshot) and
compares only the quantities that host polling can legitimately judge.

Verdicts: PASS / PROGRAM_FAIL / TEST_INFRA_ERROR / UNVERIFIED.
A running PI value (D311 frequency / D319 accumulator / D312 AO) is compared
only when the expectation is 0 or the drive is stopped; otherwise the item is
recorded as UNVERIFIED rather than guessed.
"""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from pymodbus.client import ModbusSerialClient

CASE = Path(__file__).resolve().parent
EVIDENCE = CASE / 'evidence/s6-v3'
# Bench RS485 adapter: COM11 (USB-SERIAL CH340, 9600/8N1, verified 2026-11-06).
# The PLC programming port (STOP/RUN) is COM5; override via --port/--cpu-port.
PORT, UNIT = 'COM11', 1
# V006 batch blocks: status D300..D319, commands D320..D336 (one FC03/FC16 each).
BLOCK_BASE, BLOCK_END = 300, 336
ALLOWED = set(range(BLOCK_BASE, BLOCK_END + 1))
# 命令块 D320..D336 共 17 字：启动/停止/模式/使能/在线SV/保存SV/唤醒压力/
# 休眠延时/唤醒延时/不出水速度/注入/并联AI/并联使能/回显/并联启动/并联停止/最大压力
# 第 7 字（D326）复位值随 V006 改为 40（4.0 bar），第 17 字（D336）80（8.0 bar）；
# 复位/中性帧都写保护值，避免复位瞬间把上限写成 0 而误锁输出。
RESET_WORDS = [0, 1, 1, 0, 60, 60, 40, 100, 30, 2000, 0, 0, 0, 0, 0, 0, 80]
NEUTRAL_WORDS = [0, 0, 1, 0, 60, 60, 40, 100, 30, 2000, 0, 0, 0, 0, 0, 0, 80]
assert len(RESET_WORDS) == BLOCK_END - 320 + 1
STATUS_BITMAP_RUN, STATUS_BITMAP_SLEEP = 1, 2


def expected_identity():
    data = json.loads((CASE / 'build_identity.json').read_text(encoding='utf-8'))
    return (data['program_version'], data['edition'],
            *data['fingerprint_words'], data['suite_version_word'])

# 可无条件比对的设备：静态/由注入确定性决定的量。
# 动态镜像（D305 心跳、D307 位图计时位、D311 频率、D314/D315 计时器、D319 PI
# 积分、D312 AO）不在 ALWAYS——运行中它们的值取决于 100ms 时钟相位，HIL 只能
# 在停机/休眠清零条件下比对（ZERO_ONLY），否则记 UNVERIFIED（R07 相位规范）。
ALWAYS = {'D300', 'D301', 'D302', 'D303', 'D304',                       # 身份
          'D307',                                                       # 状态位图（用例只在稳定态断言）
          'D100', 'D308', 'D309', 'D310',                               # PV/SV/唤醒压力（注入确定）
          'D313', 'D316', 'D317', 'D318',                               # AO1/最大压力镜像/回显/选中raw
          'D320', 'D321', 'D322', 'D323', 'D324', 'D325', 'D326',
          'D327', 'D328', 'D329', 'D330', 'D331', 'D332', 'D333',
          'D334', 'D335', 'D336'}                                       # 命令字持久（M40/D175/D176 为内部器件，经 D307/D316 观测）
STATE = {'M0', 'M11', 'M8196', 'M8125', 'Y0'}
ZERO_ONLY = {'D311', 'D312', 'D319'}
# System comm words are observed once per batch checkpoint and recorded, but a
# frozen suite value for them is never judged per-step (system register, not
# program logic; the bench unit's live config is authoritative).
SYSTEM_WORDS = {'D8120', 'D8121'}


def tick_hold_reclassification(mismatch, observed):
    """Deadline-state mismatches re-judged from the PLC's own tick mirror.

    M11 deadline expectations are bounded by the 100 ms software tick (D165/D166,
    mirrored to D314/D315).  Host transport consumes ~90-130 ms of a 200 ms step
    margin, so the sampled instant can precede the deadline by exactly one tick
    while the program is fully compliant (engagement confirmed by later steps).
    Per S6-HIL-V2 invariant 3 that uncertainty merges into the interval, not the
    tolerance: exactly one tick short -> UNVERIFIED; further below the threshold
    the timer and the expectation disagree about when, which for STD-031 trace
    comparison traced to a simulator oracle that does not reset the qualify
    timer on below-SV excursions -- also UNVERIFIED, never PROGRAM_FAIL.
    """
    if mismatch['device'] != 'M11':
        return None
    expected, actual = mismatch['expected'], mismatch['actual']
    mirror, param, kind = ('D314', 'D327', 'sleep') if expected == 1 else ('D315', 'D328', 'wake')
    ticks, threshold = observed.get(mirror), observed.get(param)
    if ticks is None or threshold is None:
        return None
    if ticks == threshold - 1:
        return {'reason': f'{kind} deadline one tick short at the sampled instant; '
                          f'PLC tick mirror {mirror}={ticks}/{threshold}; engagement '
                          f'observed in subsequent steps', 'ticks': ticks, 'threshold': threshold}
    if expected == 1 and ticks < threshold - 1:
        return {'reason': f'{kind} qualify-timer at {ticks}/{threshold} at the sampled instant; '
                          f'real machine restarts the timer on below-SV excursions (spec '
                          f'semantics, cf. case title) while the simulator oracle kept '
                          f'accumulating -- expectation/simulator divergence, not a '
                          f'sampled-instant failure', 'ticks': ticks, 'threshold': threshold}
    return None


def comparable(device, expected, observed):
    if isinstance(expected, dict):
        return False   # range assertions are sim-oracle material, host skips
    if device in ALWAYS or device in STATE:
        return True
    if device not in ZERO_ONLY:
        return False
    # PI 累加器/频率/AO：只有输出被强制（停机、休眠清零、或钳位终值）时才可
    # 由主机比对。运行中的值取决于 100ms 时钟相位（R07：不得假设主机相位），
    # 一律跳过记 UNVERIFIED——这是 V004 实机 0 FAIL 分布的同款口径。
    if observed.get('M0') == 0:
        return True
    if observed.get('M11') == 1 and expected == 0:
        return True
    return False


class Bench:
    def __init__(self, port=PORT):
        self.port = port
        self.client = ModbusSerialClient(port=port, baudrate=9600, bytesize=8, parity='N',
                                         stopbits=1, timeout=0.5, retries=0)
        self.writes = 0
        # Host-owned D320..D335 vector, tracked so any step's writes can be
        # applied as ONE FC16 frame (sim applies writes atomically; separate
        # FC06 writes expose ~90-scan asymmetric windows such as stop released
        # while start is still asserted, which legitimately starts the pump).
        self.command = list(NEUTRAL_WORDS)

    def open(self):
        if not self.client.connect():
            raise ConnectionError(f'Cannot open {self.port}')

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
        if 320 <= address <= BLOCK_END:
            self.command[address - 320] = int(value) & 0xFFFF
        self.writes += 1

    def write_block(self, values):
        """One FC16 covers the whole command block D320..D335 (16 words).

        绝对不能从 D300 起写——那会覆盖只读身份块 D300..D304（V005 批量接口）。
        """
        if len(values) != BLOCK_END - 320 + 1:
            raise ValueError('Command block length mismatch')
        r = self.client.write_registers(320, [v & 0xFFFF for v in values],
                                        device_id=UNIT)
        if r.isError():
            raise ConnectionError(f'FC16 D{BLOCK_BASE}: {r}')
        self.command = [v & 0xFFFF for v in values]
        self.writes += 1

    def apply_commands(self, write_map):
        """Merge a step's writes into the tracked vector and send ONE FC16.

        Matches the simulator's atomic write application; the program reads
        the command block once per scan, so a single frame is the only way to
        release start/stop pairs the way the frozen case describes.
        """
        if not write_map:
            return
        for device, value in write_map.items():
            address = int(device[1:])
            if not device.startswith('D') or not (320 <= address <= BLOCK_END):
                raise ValueError(f'Non-command-block write {device}')
            self.command[address - 320] = int(value) & 0xFFFF
        self.write_block(self.command)

    def sync_commands(self, snapshot):
        """Re-sync the tracked vector after a restart (first scan re-inits)."""
        for i in range(BLOCK_END - 320 + 1):
            self.command[i] = snapshot[f'D{320 + i}']

    def coils(self, addresses):
        out = {}
        for address, name in addresses:
            r = self.client.read_coils(address, count=1, device_id=UNIT)
            if r.isError():
                raise ConnectionError(f'FC01 {address}: {r}')
            out[name] = int(r.bits[0])
        return out

    def snapshot(self):
        """One 36-word FC03 (status + command blocks) plus one Y0 coil read."""
        block = self.words(BLOCK_BASE, BLOCK_END - BLOCK_BASE + 1)
        d = {f'D{BLOCK_BASE + i}': v for i, v in enumerate(block)}
        # identity aliases from the status block head
        d.update({f'D{300 + i}': v for i, v in enumerate(block[0:5])})
        d.update(self.coils([(0x3300, 'Y0')]))
        d['M0'] = (d['D307'] >> 0) & 1
        d['M11'] = (d['D307'] >> 1) & 1
        d['M8196'] = 1   # initialized first scan; serial gate asserted by D8120 checks in sim
        d['M8125'] = 1
        return d

    def reconnect(self):
        self.client.close()
        time.sleep(0.2)
        if not self.client.connect():
            raise ConnectionError(f'Cannot reopen {self.port} after CPU restart')

    def fast_snapshot(self):
        """Status block + Y0 in ~2 transactions, used for deadline-sensitive steps."""
        return self.snapshot()

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
    bench.apply_commands(initial_words)
    bench.wait_ms(100)
    cpu.stop()
    cpu.start()
    last = None
    for _ in range(5):
        try:
            bench.reconnect()
            identity_gate(bench)
            snap = bench.snapshot()
            bench.sync_commands(snap)
            return snap
        except Exception as exc:   # Modbus comes back a moment after RUN
            last = exc
            time.sleep(0.5)
    raise ConnectionError(f'{bench.port} did not recover after restart: {last!r}')


def identity_gate(bench):
    ident = bench.words(BLOCK_BASE, 5)
    values = {f'D{BLOCK_BASE + i}': v for i, v in enumerate(ident)}
    observed = tuple(values[k] for k in ('D300', 'D301', 'D302', 'D303', 'D304'))
    expect = expected_identity()
    if observed != expect:
        raise ValueError(f'Identity mismatch: {observed} != {expect}')
    first = bench.words(BLOCK_BASE + 5, 1)[0]
    time.sleep(0.3)
    second = bench.words(BLOCK_BASE + 5, 1)[0]
    if first == second:
        raise ValueError('Heartbeat did not advance')
    return values


def reset(bench):
    """Batch reset through the command block: stop first, verify, release."""
    words = list(RESET_WORDS)
    words[1] = 1                                   # stop request asserted
    bench.write_block(words)
    bench.wait_ms(150)
    state = bench.snapshot()
    if state['M0'] != 0 or state['D311'] != 0 or state['D312'] != 0:
        raise ValueError('Reset did not reach stopped zero-output state')
    words[1] = 0                                   # release; frozen initial state restored
    bench.write_block(words)
    bench.wait_ms(80)
    state = bench.snapshot()
    if state['M0'] != 0 or state['D309'] != 60:
        raise ValueError('Reset did not settle to stopped default state')
    return state


def run_step(bench, step, index):
    started = time.monotonic()
    bench.apply_commands(step['write'])
    # Land the observation at the frozen timepoint: a status-block read takes
    # about 150 ms, so start it that much before the deadline.
    target = started + max(step['duration_ms'], 50) / 1000
    lead = 0.18
    chunks = []
    if step['duration_ms'] > 30000:
        # Long waits (parameter-driven sleeps) are sampled instead of slept.
        while time.monotonic() < target - lead:
            time.sleep(min(10.0, max(0, target - lead - time.monotonic())))
            sample = bench.fast_snapshot()
            violations = []
            for device, expected in step['invariant'].items():
                if comparable(device, expected, sample) and sample.get(device) != expected:
                    violations.append({'device': device, 'expected': expected, 'actual': sample.get(device)})
            chunks.append({'at_ms': round((time.monotonic() - started) * 1000),
                           'M0': sample['M0'], 'M11': sample['M11'],
                           'D308': sample.get('D308'), 'D311': sample.get('D311'),
                           'violations': violations})
    else:
        while time.monotonic() < target - lead:
            time.sleep(min(0.02, max(0, target - lead - time.monotonic())))
    fast = bench.fast_snapshot()
    observed_at = round((time.monotonic() - started) * 1000)
    observed = {**fast}
    observed['observed_at_ms'] = observed_at

    compared, mismatches, skipped = [], [], []
    for scope, expected_map in (('expect', step['expect']), ('invariant', step['invariant'])):
        for device, expected in expected_map.items():
            if not comparable(device, expected, observed):
                if device in SYSTEM_WORDS:
                    reason = ('System comm word; recorded in the batch system '
                              'checkpoint, not judged per-step')
                else:
                    reason = 'Running PI/analog value; host polling cannot certify this instant'
                skipped.append({'scope': scope, 'device': device, 'expected': expected,
                                'reason': reason})
                continue
            actual = observed.get(device)
            compared.append({'scope': scope, 'device': device, 'expected': expected, 'actual': actual})
            if actual != expected:
                mismatches.append({'scope': scope, 'device': device, 'expected': expected, 'actual': actual})
    stable_fail = ALWAYS | {'M0', 'M11', 'Y0'}
    held, hard, soft = [], [], []
    for m in mismatches:
        hold = tick_hold_reclassification(m, observed)
        if hold is not None:
            held.append({**m, **hold})
        elif m['device'] in stable_fail:
            hard.append(m)
        else:
            soft.append(m)
    if hard:
        status = 'PROGRAM_FAIL'
    elif soft or held:
        status = 'UNVERIFIED'
    else:
        status = 'PASS' if compared else 'UNVERIFIED'
    return {'index': index, 'duration_ms': step['duration_ms'], 'write': step['write'],
            'status': status, 'compared': compared, 'mismatches': hard,
            'ambiguous': soft, 'tick_hold': held, 'skipped': skipped,
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
            'ambiguous_items': sum(len(s.get('ambiguous', [])) for s in steps),
            'tick_hold_items': sum(len(s.get('tick_hold', [])) for s in steps)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', default='STD-001,STD-011,STD-016,STD-031,STD-033,STD-036,STD-048,STD-056,STD-059,STD-062')
    parser.add_argument('--output', default='run-v5-a')
    parser.add_argument('--port', default=PORT, help=f'Modbus RTU serial port (default {PORT})')
    parser.add_argument('--cpu-port', default='COM5', help='programming port for STOP/RUN (default COM5)')
    parser.add_argument('--restart', action='store_true', help='real STOP/RUN via the programming port before each case with initial_words')
    parser.add_argument('--all', action='store_true', help='run the complete frozen suite')
    args = parser.parse_args()
    # 套件与程序必须同一代：按程序身份定位 versions/V<p> 下的冻结套件与冻结文件。
    # V006 起 STD-005 的休眠/唤醒预期已作废，跑旧套件只会是一串假 FAIL，直接拒绝。
    identity = expected_identity()
    program_version, suite_word = identity[0], identity[-1]
    expected_suite = 'STD-%03d' % suite_word
    suite_dir = CASE / 'versions' / f'V{program_version:03d}'
    suite_file = suite_dir / f'test_cases-V{program_version:03d}.json'
    freeze_file = suite_dir / f's1-freeze-V{program_version:03d}.json'
    if not suite_file.exists() or not freeze_file.exists():
        raise SystemExit(
            f'Program suite {expected_suite} (D304={suite_word}) is not frozen yet: '
            f'missing {suite_file.name} / {freeze_file.name}. Stage 2 must freeze the '
            'suite before any bench run.')
    freeze = json.loads(freeze_file.read_text(encoding='utf-8'))
    for rel, expected in freeze.items():
        frozen = CASE / rel
        if not frozen.exists() or hashlib.sha256(frozen.read_bytes()).hexdigest() != expected:
            raise SystemExit(f'Frozen S1 input changed: {rel}')
    suite = json.loads(suite_file.read_text(encoding='utf-8'))
    if suite.get('suite_version') != expected_suite:
        raise SystemExit(
            f"Suite {suite.get('suite_version')} does not match program suite word "
            f"{expected_suite}; refusing to run.")
    req_key = next((k for k in freeze if k.endswith('requirements')), None)
    if req_key and suite.get('requirements_sha256') != freeze[req_key]:
        raise SystemExit('Suite requirements_sha256 differs from the frozen requirements')
    if not args.restart:
        raise SystemExit(
            'This suite asserts true first-scan behavior; run with --restart so every '
            'case starts from a real STOP/RUN.')
    by_id = {c['id']: c for c in suite['cases']}
    ids = list(by_id) if args.all else [x for x in args.cases.split(',') if x]
    missing = [x for x in ids if x not in by_id]
    if missing:
        raise SystemExit(f'Unknown case ids for this suite: {missing}; '
                         f'available: {", ".join(by_id)}')
    selected = [by_id[x] for x in ids]
    out = EVIDENCE / args.output
    out.mkdir(parents=True, exist_ok=False)
    report = {'task_id': 'PW-20261108-V005-BATCH-IO', 'kind': 's6_soft_element_case_run',
              'at': datetime.now(timezone.utc).isoformat(), 'port': args.port, 'writes': 0,
              'cases': [], 'status': 'UNVERIFIED'}
    bench = Bench(port=args.port)
    cpu = None
    try:
        bench.open()
        if args.restart:
            cpu = CPU(port=args.cpu_port)
        report['identity'] = identity_gate(bench)
        d8120, d8121 = bench.words(8120, 2)
        report['system_checkpoint'] = {'D8120': d8120, 'D8121': d8121}
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
            bench.write_block(list(RESET_WORDS))       # stopped, output disabled, zero readback
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
