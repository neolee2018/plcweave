"""Bench output demonstration: stop -> run -> pre-sleep -> sleep -> wake -> stop.

Reads M0/M10/M11/Y0 and D154/D8050 over Modbus RTU and prints one line per state
change, so a lamp on Y0 can be filmed together with the register readback.
Only the program's own input-mapping registers are written; the sequence ends
stopped with every output at zero.
"""
import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from pymodbus.client import ModbusSerialClient

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM7')
    parser.add_argument('--unit', type=int, default=1)
    parser.add_argument('--out', default=str(HERE / 'evidence/s6-v3'))
    args = parser.parse_args()
    client = ModbusSerialClient(port=args.port, baudrate=9600, bytesize=8, parity='N',
                                stopbits=1, timeout=0.5, retries=0)

    def read(first, count=1):
        r = client.read_holding_registers(first, count=count, device_id=args.unit)
        if r.isError():
            raise RuntimeError(str(r))
        return [v - 65536 if v >= 32768 else v for v in r.registers]

    def write(device, value):
        r = client.write_register(int(device[1:]), int(value) & 0xFFFF, device_id=args.unit)
        if r.isError():
            raise RuntimeError(str(r))

    def coil(address):
        r = client.read_coils(address, count=1, device_id=args.unit)
        if r.isError():
            raise RuntimeError(str(r))
        return int(r.bits[0])

    def snapshot():
        return {'M0': coil(0), 'M10': coil(10), 'M11': coil(11), 'Y0': coil(0x3300),
                'D154': read(154)[0], 'D8050': read(8050)[0],
                'D120': read(120)[0], 'D100': read(100)[0]}

    rows = []
    start = time.monotonic()

    def phase(code, title, seconds, writes=None):
        print(f"\n=== {code}  {title}  ===  (hold {seconds}s)", flush=True)
        if writes:
            for device, value in writes.items():
                write(device, value)
        phase_start = time.monotonic()
        last = None
        while time.monotonic() - phase_start < seconds:
            state = snapshot()
            state['t_ms'] = round((time.monotonic() - start) * 1000)
            state['phase'] = code
            rows.append(state)
            key = (state['M0'], state['M10'], state['M11'], state['Y0'])
            if key != last:
                print(f"  {state['t_ms']:6d} ms | M0={state['M0']} M10={state['M10']} "
                      f"M11={state['M11']} Y0={state['Y0']} | D154={state['D154']} "
                      f"D8050={state['D8050']}", flush=True)
                last = key
            time.sleep(0.25)

    try:
        if not client.connect():
            raise ConnectionError(f'Cannot open {args.port}')
        print('identity D196..D202 =', read(196, 7), flush=True)
        for device, value in (('D192', 1), ('D191', 0), ('D193', 0), ('D190', 1),
                              ('D1056', 0), ('D102', 60), ('D1070', 0), ('D1071', 0)):
            write(device, value)
        time.sleep(0.3)
        phase('P1', 'STOPPED - outputs off', 6)
        phase('P2', 'RUNNING at 5.0 bar, output enabled', 12,
              {'D192': 0, 'D191': 1, 'D193': 1, 'D1056': 1250})
        phase('P3', 'PRE-SLEEP at 5.8 bar', 12, {'D1056': 1450})
        phase('P4', 'SLEEP latched - outputs off', 8)
        phase('P5', 'WAKE at 5.0 bar - outputs back on', 10, {'D1056': 1250})
        phase('P6', 'STOP - outputs off', 6, {'D192': 1})
    finally:
        try:
            for device, value in (('D192', 1), ('D191', 0), ('D193', 0), ('D1056', 0),
                                  ('D102', 60), ('D190', 1), ('D1070', 0), ('D1071', 0)):
                write(device, value)
            time.sleep(0.2)
            state = snapshot()
            state['t_ms'] = round((time.monotonic() - start) * 1000)
            state['phase'] = 'P7'
            rows.append(state)
            print(f"\n=== P7  CLEANUP ===  M0={state['M0']} M10={state['M10']} "
                  f"M11={state['M11']} Y0={state['Y0']} D154={state['D154']} "
                  f"D8050={state['D8050']}", flush=True)
        finally:
            client.close()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (out / f'output-demo-{stamp}.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    with (out / f'output-demo-{stamp}.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['t_ms', 'phase', 'M0', 'M10', 'M11',
                                                    'Y0', 'D154', 'D8050', 'D120', 'D100'])
        writer.writeheader()
        writer.writerows(rows)
    print('\nrecords', len(rows), 'written to', out, flush=True)


if __name__ == '__main__':
    main()
