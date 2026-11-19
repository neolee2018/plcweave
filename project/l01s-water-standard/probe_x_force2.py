"""Bench probe #2: validate programming-port force mechanics and give a
visible X0 window. Task PW-20261106-XFORCE.

1. Force M100 (unused by the water program) at candidate base 0x0E00 and
   read it back through Modbus FC01 coil 100 — proves the force path
   actually acts on a device this unit maps.
2. Force X0 at 0x0400 and HOLD it for 3 s — the operator watches the unit's
   X0 LED directly, independent of any Modbus X map.
3. Release both in finally.
"""
import time

from pymodbus.client import ModbusSerialClient


def force(serial, base, index, on):
    address = f'{base + index:04X}'
    body = (('7' if on else '8') + address[2:] + address[:2]).encode('ascii') + b'\x03'
    frame = b'\x02' + body + f'{sum(body) & 255:02X}'.encode('ascii')
    serial.reset_input_buffer()
    serial.write(frame)
    return serial.read(1).hex()


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
    m_forced = x_forced = False
    try:
        assert modbus.connect(), 'COM11 open failed (GUI holding the port?)'

        def read_m100():
            r = modbus.read_coils(100, count=1, device_id=1)
            return None if r.isError() else int(r.bits[0])

        print('FC01 M100 before:', read_m100())
        ack = force(cpu, 0x0E00, 100, True)
        print('force M100 ON  addr=0x0E64 ack:', ack)
        if ack == '06':
            m_forced = True
            time.sleep(0.2)
            print('FC01 M100 while forced:', read_m100())

        def read_x0():
            r = modbus.read_discrete_inputs(0x3400, count=1, device_id=1)
            return None if r.isError() else int(r.bits[0])

        print('--- X0 visible window: watch the unit X0 LED for 3 s ---')
        ack = force(cpu, 0x0400, 0, True)
        print('force X0 ON addr=0x0400 ack:', ack)
        if ack == '06':
            x_forced = True
            time.sleep(3.0)
            print('FC02 X0 while forced:', read_x0())
    finally:
        if x_forced:
            print('release X0 ack:', force(cpu, 0x0400, 0, False))
        if m_forced:
            print('release M100 ack:', force(cpu, 0x0E00, 100, False))
            time.sleep(0.2)
            print('FC01 M100 after release:', read_m100())
        cpu.close()
        modbus.close()
    print('cleanup done')


if __name__ == '__main__':
    main()
