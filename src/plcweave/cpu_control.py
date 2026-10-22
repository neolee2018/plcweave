"""Narrow, opt-in programming-port CPU control for an isolated L01S bench.

The L01S V26.31 special-relay list defines M8035/36/37. Coil mapping
M8000..M8511 -> 0x1E00..0x1FFF is established separately by readback.
COM7 Modbus becomes unavailable in STOP on the verified L01S. Always control
through COM5, which remains responsive. Never downloads application or firmware.
"""
import time
from .fx_serial import FXReadOnly,read_frame,decode_read

class CPUControl:
    def __init__(self,bench,*,isolated_bench=False,audit_callback=None):
        if not isolated_bench or not bench.verified:
            raise ValueError("CPU control requires verified identity and an isolated bench")
        self.bench=bench
        self.audit_callback=audit_callback

    def write(self,relay,value):
        if relay not in {8035,8036,8037}:
            raise ValueError("Only the documented CPU control relays are allowed")
        # FX force bit uses byte-swapped ASCII bit address. This is NOT the
        # Modbus coil address. Restrict to the three documented CPU controls.
        address=f'{0x0F00+relay-8000:04X}'
        body=(('7' if value else '8')+address[2:]+address[:2]).encode('ascii')+b'\x03'
        frame=b'\x02'+body+f'{sum(body)&255:02X}'.encode('ascii')
        with FXReadOnly() as fx:
            fx.audit_callback=self.audit_callback
            expected=list(getattr(self.bench,'expected_identity',(1,31)))
            if fx.read_words(196,2)!=expected:
                raise ValueError('Programming-port identity mismatch')
            fingerprint=getattr(self.bench,'expected_fingerprint',None)
            suite=getattr(self.bench,'expected_suite',None)
            if fingerprint is not None or suite is not None:
                actual=fx.read_words(200,3)
                if fingerprint is not None and actual[:2]!=list(fingerprint):
                    raise ValueError('Programming-port fingerprint mismatch')
                if suite is not None and actual[2]!=suite:
                    raise ValueError('Programming-port suite identity mismatch')
            fx.serial.reset_input_buffer();started=time.monotonic_ns();fx.serial.write(frame)
            ack=fx.serial.read(1)
            if self.audit_callback:
                self.audit_callback({'port':'COM5','operation':'native_force','relay':relay,'value':bool(value),'request_ns':started,'response_ns':time.monotonic_ns(),'request_hex':frame.hex(),'response_hex':ack.hex(),'valid':ack==b'\x06'})
            if ack!=b'\x06':
                raise ConnectionError(f'Programming-port CPU control M{relay} ACK={ack.hex()}')

    def state(self):
        with FXReadOnly() as fx:
            fx.audit_callback=self.audit_callback
            frame=read_frame(0x01E0,8)
            fx.serial.reset_input_buffer();started=time.monotonic_ns();fx.serial.write(frame)
            response=fx.serial.read(20)
            if self.audit_callback:
                self.audit_callback({'port':'COM5','operation':'native_control_state','request_ns':started,'response_ns':time.monotonic_ns(),'request_hex':frame.hex(),'response_hex':response.hex()})
            data=decode_read(response,8)
            result={f'M{n}':int(bool(data[(n-8000)//8]&(1<<((n-8000)%8)))) for n in [8000,8035,8036,8037]}
            result['D199']=fx.read_words(199,1)[0]
            return result

    def wait(self,running,timeout=3):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            state=self.state()
            if bool(state['M8000'])==running:
                return state
            time.sleep(0.1)
        raise TimeoutError(f"CPU did not confirm RUN={running}")

    def stop(self):
        self.write(8037,True)
        return self.wait(False)

    def start(self):
        self.write(8037,False)
        self.write(8035,True)
        self.write(8036,True)
        return self.wait(True)

    def restore(self,original):
        # Caller first returns to its verified original RUN state; remove only
        # the forced-control bits this helper changed, never a global reset.
        for relay in (8037,8036,8035):
            self.write(relay,bool(original[f'M{relay}']))
