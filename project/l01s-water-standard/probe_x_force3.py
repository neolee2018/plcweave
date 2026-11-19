"""Bench probe #4: search the programming-port force map with full-device
diffing, so every trial shows exactly which device (if any) moved. Task
PW-20261106-XFORCE. Each trial: force ON -> diff M0..M199 / X0..X17 / Y0 ->
force OFF -> verify cleared. Candidates avoid the proven M8000 block
(0x0F00+, RUN/STOP specials) entirely.
"""
import time

from pymodbus.client import ModbusSerialClient

CANDIDATES = [0x0400, 0x0500, 0x0480, 0x0300, 0x0040, 0x0E64]


def force(serial, address, on):
    text = f'{address:04X}'
    body = (('7' if on else '8') + text[2:] + text[:2]).encode('ascii') + b'\x03'
    frame = b'\x02' + body + f'{sum(body) & 255:02X}'.encode('ascii')
    serial.reset_input_buffer()
    serial.write(frame)
    return serial.read(1).hex()


def read_coils(client, first, count):
    r = client.read_coils(first, count=count, device_id=1)
    return None if r.isError() else list(r.bits[:count])


def read_x(client):
    r = client.read_discrete_inputs(0x3400, count=16, device_id=1)
    return None if r.isError() else list(r.bits[:16])


def main():
    import serial
    cpu = serial.Serial(port=None, baudrate=9600, bytesize=7, parity='E',
                        stopbits=1, timeout=0.8, write_timeout=0.8)
    cpu.port = 'COM5'
    cpu.dtr = False
    cpu.rts = False
    cpu.open()
    modbus = ModbusSerialClient(port='COM11', baudrate=9600, bytesize=8, parity='N',
                                stopbits=1, timeout=0.5, retries=0)
    touched = []
    try:
        assert modbus.connect(), 'COM11 open failed'
        base_m = read_coils(modbus, 0, 200)
        base_x = read_x(modbus)
        print('baseline M0-199 nonzero:', [i for i, v in enumerate(base_m) if v])
        print('baseline X0-X17:', [i for i, v in enumerate(base_x) if v])
        for address in CANDIDATES:
            ack = force(cpu, address, True)
            if ack != '06':
                print(f'{address:04X}: NAK {ack}')
                continue
            time.sleep(0.3)
            m = read_coils(modbus, 0, 200)
            x = read_x(modbus)
            moved = [f'M{i}' for i, (a, b) in enumerate(zip(base_m, m)) if a != b]
            moved += [f'X{i:o}' for i, (a, b) in enumerate(zip(base_x, x)) if a != b]
            ack2 = force(cpu, address, False)
            time.sleep(0.3)
            m2 = read_coils(modbus, 0, 200)
            residue = [f'M{i}' for i, (a, b) in enumerate(zip(base_m, m2)) if a != b]
            print(f'{address:04X}: ON-ack={ack} changed={moved or "无"} OFF-ack={ack2} residue={residue or "无"}')
            if residue:
                touched.append((address, residue))
        print('final check X0-X17:', [i for i, v in enumerate(read_x(modbus)) if v])
    finally:
        for address, _ in [(a, r) for a, r in touched]:
            force(cpu, address, False)
        cpu.close()
        modbus.close()
    print('probe done')


if __name__ == '__main__':
    main()
