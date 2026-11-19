"""Bench probe: can the programming port (COM5) force X inputs, and does
Modbus FC02 see them? Task PW-20261106-XFORCE.

Sequence (with cleanup in finally):
  1. Force X0 ON via programming-port force (candidate address 0x0400 + index).
  2. Read X0 back through Modbus FC02 (discrete input 0x3400).
  3. Force X0 OFF and verify the readback returns 0.

The water program never reads X, so a forced input cannot actuate anything;
this only drives the input image and its unit LED.
"""
import time

from pymodbus.client import ModbusSerialClient


def force(serial, base, index, on):
    address = f'{base + index:04X}'
    body = (('7' if on else '8') + address[2:] + address[:2]).encode('ascii') + b'\x03'
    frame = b'\x02' + body + f'{sum(body) & 255:02X}'.encode('ascii')
    serial.reset_input_buffer()
    serial.write(frame)
    ack = serial.read(1)
    return ack.hex()


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
    forced = False
    try:
        assert modbus.connect(), 'COM11 open failed (GUI holding the port?)'
        def read_x0():
            r = modbus.read_discrete_inputs(0x3400, count=1, device_id=1)
            return None if r.isError() else int(r.bits[0])

        print('FC02 X0 before force:', read_x0())
        ack = force(cpu, 0x0400, 0, True)
        print('force X0 ON  addr=0x0400 ack:', ack)
        if ack == '06':
            forced = True
            time.sleep(0.2)
            print('FC02 X0 while forced :', read_x0())
            ack = force(cpu, 0x0400, 0, False)
            print('force X0 OFF ack:', ack)
            forced = ack != '06'
            time.sleep(0.2)
            print('FC02 X0 after release:', read_x0())
    finally:
        if forced:
            force(cpu, 0x0400, 0, False)
        cpu.close()
        modbus.close()
    print('cleanup done')


if __name__ == '__main__':
    main()
