"""Read-only legacy FX programming-port diagnostics.

Protocol facts: STX + ASCII read-command/address/count + ETX + additive BCC.
Reference: https://github.com/Ramy-Sorial/Mitsubishi_FX_Protocol (no code copied).
Legacy address mapping is explicitly limited to D0..D511 here.
"""
import time

def read_frame(address, count):
    if not (0<=address<=65535 and 1<=count<=64):
        raise ValueError("Read address/count outside legacy frame")
    body=f"0{address:04X}{count:02X}".encode("ascii")+b"\x03"
    return b"\x02"+body+f"{sum(body)&255:02X}".encode("ascii")

def decode_read(response, count):
    if len(response)!=2*count+4 or response[0]!=2 or response[-3]!=3:
        raise ValueError("Invalid FX response framing or length")
    if response[-2:].upper()!=f"{sum(response[1:-2])&255:02X}".encode("ascii"):
        raise ValueError("Invalid FX response checksum")
    return bytes.fromhex(response[1:-3].decode("ascii"))

class FXReadOnly:
    def __init__(self,port="COM5",baudrate=9600):
        self.port,self.baudrate,self.serial=port,baudrate,None

    def __enter__(self):
        import serial
        self.serial=serial.Serial(port=None,baudrate=self.baudrate,bytesize=7,parity="E",stopbits=1,timeout=0.8,write_timeout=0.8)
        self.serial.port=self.port
        self.serial.dtr=False
        self.serial.rts=False
        try:
            self.serial.open()
        except Exception:
            self.serial.close()
            raise
        return self

    def read_words(self,start,count):
        if not (0<=start<=511 and 1<=count<=32 and start+count<=512):
            raise ValueError("Only documented legacy D0..D511 is allowed")
        self.serial.reset_input_buffer()
        frame=read_frame(0x1000+2*start,2*count)
        started=time.monotonic_ns()
        self.serial.write(frame)
        response=self.serial.read(4*count+4)
        if getattr(self,'audit_callback',None):
            self.audit_callback({'port':self.port,'operation':'native_read_words','first':start,'count':count,'request_ns':started,'response_ns':time.monotonic_ns(),'request_hex':frame.hex(),'response_hex':response.hex()})
        raw=decode_read(response,2*count)
        return [int.from_bytes(raw[i:i+2],"little",signed=True) for i in range(0,len(raw),2)]

    def __exit__(self,*_):
        if self.serial:
            self.serial.close()

