"""Bench probe #3 (READ-ONLY): discover the programming-port device map by
reading known-changing devices. Task PW-20261106-XFORCE.

Candidates per common FX programming-port (format 1) documentation:
  word units  'WR' addr(L,H) count(L,H) ETX sum   -> STX data ETX sum
  bit units   'BR' addr(L,H) count(L,H) ETX sum   -> STX data ETX sum
Devices: D198 heartbeat (compare with Modbus FC03), M8012 100 ms clock,
X0 block. No force, no write of any kind in this probe.
"""
import time

from pymodbus.client import ModbusSerialClient


def frame(serial, payload):
    body = payload + b'\x03'
    serial.reset_input_buffer()
    serial.write(b'\x05' + body + f'{sum(body) & 255:02X}'.encode('ascii'))
    ack = serial.read(1)
    if ack != b'\x02':
        return None
    data = serial.read_until(b'\x03', 512)
    if not data.endswith(b'\x03'):
        return None
    return data[:-1].decode('ascii')


def word_read(serial, address, count):
    payload = b'WR' + bytes([address & 255, address >> 8, count & 255, count >> 8])
    return frame(serial, payload)


def bit_read(serial, address, count):
    payload = b'BR' + bytes([address & 255, address >> 8, count & 255, count >> 8])
    return frame(serial, payload)


def nibbles(text):
    return [int(ch, 16) for ch in text] if text and all(c in '0123456789ABCDEF' for c in text) else None


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
    try:
        assert modbus.connect(), 'COM11 open failed'

        def modbus_d198():
            r = modbus.read_holding_registers(198, count=1, device_id=1)
            v = r.registers[0] if not r.isError() else None
            return v - 65536 if v is not None and v >= 32768 else v

        print('== word read: D base candidates for D198 heartbeat ==')
        for base, label in ((0x4000, '0x4000'), (0x0000, '0x0000'), (0x0800, '0x0800')):
            r1 = word_read(cpu, base + 198, 1)
            time.sleep(0.3)
            r2 = word_read(cpu, base + 198, 1)
            print(f'  {label}: {r1!r} -> {r2!r}   (Modbus FC03 D198 = {modbus_d198()})')

        print('== bit read: M8012 100ms clock at 0x0F00+12 ==')
        for _ in range(2):
            r1 = bit_read(cpu, 0x0F00 + 12, 4)
            time.sleep(0.15)
            r2 = bit_read(cpu, 0x0F00 + 12, 4)
            print(f'  nibbles {nibbles(r1 or "")} -> {nibbles(r2 or "")} raw={r1!r} {r2!r}')

        print('== bit read: X block at 0x0400 ==')
        r = bit_read(cpu, 0x0400, 8)
        print('  nibbles', nibbles(r or ''), 'raw', repr(r))
    finally:
        cpu.close()
        modbus.close()
    print('probe done (read-only)')


if __name__ == '__main__':
    main()
