"""Execute independently frozen S6 supplements; no download or S1 changes."""
import argparse
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plcweave.cpu_control import CPUControl
from plcweave.hil import ALLOWED_WRITES, candidate_bench
from plcweave.sampled import evaluate_checkpoint, evaluate_timing_interval
from plcweave.testing import compare, digest, frozen_suite
from plcweave.validation import TraceOracle

CASE = Path(__file__).resolve().parent
WORKSPACE = CASE.parents[1]
EVIDENCE = CASE / 'evidence/hil02'
ZERO = dict.fromkeys('M0 M10 M11 D120 D154 Y0 D8050 D8051'.split(), 0)
IDENTITY_WATCH = 'D196 D197 D200 D201 D202'.split()


def aggregate(statuses):
    statuses = list(statuses)
    for status in ('TEST_INFRA_ERROR', 'PROGRAM_FAIL', 'UNVERIFIED'):
        if status in statuses:
            return status
    return 'PASS' if statuses else 'UNVERIFIED'


def load_inputs():
    capture_freeze = json.loads((EVIDENCE/'S6-deadline-capture-freeze.json').read_text(encoding='utf-8'))
    for name, sha in capture_freeze['files'].items():
        if digest(WORKSPACE/name) != sha:
            raise ValueError(f'Frozen capture policy changed: {name}')
    freeze = json.loads((EVIDENCE/'S6-qualification-freeze.json').read_text(encoding='utf-8'))
    for name, sha in freeze['files'].items():
        if digest(WORKSPACE/name) != sha:
            raise ValueError(f'Frozen S6 input changed: {name}')
    plan = json.loads((EVIDENCE/'S6-qualification-plan.json').read_text(encoding='utf-8'))
    for name, sha in plan['bindings'].items():
        if digest(CASE/name) != sha:
            raise ValueError(f'S6 candidate binding changed: {name}')
    suite = frozen_suite(CASE)
    record = json.loads((CASE/'manual_download.json').read_text(encoding='utf-8'))
    if (record.get('source_sha256') != digest(CASE/'source.fxil') or
            record.get('test_sha256') != digest(CASE/'test_cases.json') or
            not record.get('confirmed_by') or not record.get('downloaded_at')):
        raise ValueError('New manual download record must bind this source and suite')
    if len(plan['supplemental_procedures']) != 28:
        raise ValueError('Unexpected qualified procedure count')
    for proc in plan['supplemental_procedures']:
        if proc['kind'] not in {'initialization', 'steady', 'saturation', 'output_gate', 'edge_timing', 'jitter'}:
            raise ValueError('Unsupported procedure type')
        if not set(proc['source_case_ids']) <= {case['id'] for case in suite['cases']}:
            raise ValueError('Procedure references absent frozen case')
    return plan, suite, record


def capability_audit(suite):
    results = []
    for case in suite['cases']:
        oracle = TraceOracle(suite, case, capabilities={'full_scan_trace': False, 'verified_applied_inputs': False})
        oracle.consume({}, {}, 440)
        scalar = []
        for index, step in enumerate(case['steps']):
            for scope, expected in (('each_scan', step['invariant']), ('endpoint', step['expect'])):
                scalar.extend({'step': index, 'scope': scope, 'device': name, 'expected': value,
                               'status': 'UNVERIFIED', 'reason': 'Original scan waveform/checkpoint not captured'}
                              for name, value in expected.items())
        results.append({'id': case['id'], 'hardware_scope': case['hardware_scope'], 'status': 'UNVERIFIED',
                        'execution': 'capability_only', 'not_replayed_reason': 'Host polling cannot reproduce frozen scan waveform; ADC writes forbidden for local-only cases',
                        'scalar_assertions': scalar, 'global_invariants': [
                            {'device': name, 'expected': expected, 'status': 'UNVERIFIED'}
                            for name, expected in suite['global_invariants'].items()],
                        'relationships': oracle.finish()})
    return results


class LoggedClient:
    """Log every Modbus transaction without changing the existing driver."""
    def __init__(self, client, executor):
        self.inner,self.executor=client,executor

    def __getattr__(self, name):
        return getattr(self.inner,name)

    def transact(self, operation, first, **kwargs):
        start=time.monotonic_ns()
        try:
            response=getattr(self.inner,operation)(first,**kwargs)
        except BaseException as exc:
            self.executor.audit_transport({'port':'COM7','operation':operation,'first':first,**kwargs,'request_ns':start,'response_ns':time.monotonic_ns(),'error':repr(exc)})
            raise
        payload={'port':'COM7','operation':operation,'first':first,**kwargs,'request_ns':start,'response_ns':time.monotonic_ns(),'is_error':response.isError()}
        if hasattr(response,'registers'):payload['registers']=response.registers
        if hasattr(response,'bits'):payload['bits']=[int(x) for x in response.bits[:kwargs.get('count',len(response.bits))]]
        self.executor.audit_transport(payload)
        return response

    def read_holding_registers(self,first,**kwargs):
        return self.transact('read_holding_registers',first,**kwargs)

    def read_coils(self,first,**kwargs):
        return self.transact('read_coils',first,**kwargs)

    def write_register(self,first,value,**kwargs):
        return self.transact('write_register',first,value=value,**kwargs)


class Executor:
    def __init__(self, bench, stream, deadline):
        self.bench, self.stream, self.deadline = bench, stream, deadline
        self.start = time.monotonic()
        self.procedure = 'setup'
        self.sequence = 0

    def now(self):
        return (time.monotonic()-self.start)*1000

    def check_deadline(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError('Qualified hardware batch deadline reached')

    def emit(self, kind, **fields):
        self.sequence += 1
        row = {'sequence': self.sequence, 'procedure': self.procedure, 'kind': kind, **fields}
        self.stream.write(json.dumps(row)+'\n')
        self.stream.flush()
        return row

    def audit_transport(self, data):
        fields=dict(data)
        fields['start_ms']=(fields.pop('request_ns')/1e9-self.start)*1000
        fields['end_ms']=(fields.pop('response_ns')/1e9-self.start)*1000
        return self.emit('transaction',**fields)

    def wait_ms(self, milliseconds):
        target = time.monotonic()+max(0, milliseconds)/1000
        while time.monotonic() < target:
            self.check_deadline()
            time.sleep(max(0,min(.05, target-time.monotonic())))

    def read(self, watch, *, check_identity=False):
        self.check_deadline()
        watch = list(dict.fromkeys([*watch, *(IDENTITY_WATCH if check_identity else [])]))
        start = self.now()
        values = self.bench.sample(watch)
        end = self.now()
        row = self.emit('read', start_ms=start, end_ms=end, values=values)
        if check_identity:
            expected = dict(zip(IDENTITY_WATCH, [*self.bench.expected_identity, *self.bench.expected_fingerprint, self.bench.expected_suite]))
            if compare(values, expected):
                self.bench.verified = False
                raise ValueError('Identity changed during observation')
        return row

    def apply(self, writes):
        rows = []
        for name, value in writes.items():
            self.check_deadline()
            if not name.startswith('D') or int(name[1:]) not in ALLOWED_WRITES:
                raise ValueError(f'Forbidden stimulus {name}')
            start = self.now()
            self.bench.write(name, value)
            ack = self.now()
            expected = max(10, min(160, value)) if name == 'D102' else value
            actual = self.bench.read_words(int(name[1:]), 1)[0]
            readback_end = self.now()
            row = self.emit('write', device=name, value=value, request_ms=start, ack_ms=ack,
                            readback_end_ms=readback_end, expected_readback=expected, actual_readback=actual)
            rows.append(row)
            if actual != expected:
                raise ValueError(f'Applied input not verified: {name} expected {expected}, got {actual}')
        return rows

    def observe(self, expectation, hold_ms, stable_devices, *, settle_ms=200, input_verified=True, phase_sensitive=()):
        anchor = self.now()
        self.wait_ms(settle_ms)
        watch = list(dict.fromkeys([*expectation, *IDENTITY_WATCH]))
        rows = [self.read(watch, check_identity=True), self.read(watch, check_identity=True)]
        self.wait_ms(hold_ms-(self.now()-anchor))
        relative = [{'values': row['values'], 'start_ms': row['start_ms']-anchor, 'end_ms': row['end_ms']-anchor} for row in rows]
        quality = {'transport_ok': True, 'identity_ok': True, 'applied_inputs_verified': input_verified,
                   'settled_after_ms': settle_ms, 'checkpoint_window_ms': [0, hold_ms]}
        verdicts = evaluate_checkpoint(expectation, relative, quality=quality,
                                       stable_devices=stable_devices, phase_sensitive_devices=phase_sensitive)
        return {'status': aggregate(r['status'] for r in verdicts), 'kind': 'supplemental_stable_observation',
                'expect': expectation, 'hold_ms': hold_ms, 'actual_hold_ms': self.now()-anchor,
                'observation_sequences': [r['sequence'] for r in rows], 'quality': quality, 'assertions': verdicts}

    def step(self, step):
        writes = self.apply(step['write'])
        result = self.observe(step['expect'], step['hold_ms'], step['stable_devices'])
        result['write_sequences'] = [r['sequence'] for r in writes]
        if 'original_duration_ms' in step:
            result['original_checkpoint_ms'] = step['original_duration_ms']
            result['original_checkpoint_status'] = 'UNVERIFIED'
        return result

    def reset(self, controller, original, initial_words):
        self.apply({'D192': 1, 'D191': 0, 'D193': 0})
        self.wait_ms(100)
        if compare(self.read(list(ZERO))['values'], ZERO):
            raise ValueError('Unable to establish stopped zero-output reset state')
        self.apply({'D190': 1, 'D1056': 0, 'D261': 60})
        self.apply(initial_words)
        start = self.now()
        stopped = controller.stop()
        running = controller.start()
        controller.restore(original)
        identity = self.bench.verify()
        self.emit('cpu_restart', start_ms=start, end_ms=self.now(), stopped=stopped, running=running, identity=identity)

    def event(self, event):
        device = event['device']
        before = self.read([device])
        if before['values'][device] != event['from']:
            raise ValueError(f'Event precondition missing: {event["id"]}')
        writes = self.apply(event['write'])
        effective = self.read(list(event['effective_trigger']))
        if compare(effective['values'], event['effective_trigger']):
            return {'id': event['id'], 'status': 'UNVERIFIED', 'reason': 'Effective trigger not established', 'effective_sample': effective}
        trigger = [writes[0]['request_ms'], effective['end_ms']]
        last_old = before
        transition = None
        target = time.monotonic()+event['deadline_ms']/1000
        while time.monotonic() < target:
            sample = self.read([device])
            if sample['values'][device] == event['to']:
                transition = [last_old['start_ms'], sample['end_ms']]
                break
            last_old = sample
        result = evaluate_timing_interval(trigger_ms=trigger, transition_ms=transition, expected_ms=event['expected_ms'])
        result.update(id=event['id'], effective_trigger_sample=effective['sequence'])
        if event.get('post_event_expect') and transition is not None:
            expected = event['post_event_expect']
            result['post_event'] = self.observe(expected, 1500, list(expected))
            result['status'] = aggregate([result['status'], result['post_event']['status']])
        return result

    def saturation(self, procedure):
        params = procedure['params']
        self.apply(params['setup_words'])
        before = self.read([params['poll_device']])
        writes = self.apply(params['trigger_write'])
        effective = self.read(list(params['trigger_state']))
        established = not compare(effective['values'], params['trigger_state'])
        trigger = [writes[0]['request_ms'], effective['end_ms']]
        last_old = before
        transition = None
        while self.now()-trigger[0] < params['first_event_deadline_ms']:
            sample = self.read([params['poll_device']])
            if sample['values'][params['poll_device']] == params['becomes']:
                transition = [last_old['start_ms'], sample['end_ms']]
                break
            last_old = sample
        timing = evaluate_timing_interval(trigger_ms=trigger if established else None,
                                          transition_ms=transition, expected_ms=params['event_expected_ms'])
        # Positive evidence before the original deadline; an early non-cap
        # value cannot prove failure because saturation may legally occur later.
        self.wait_ms(trigger[0]+params['final_expected_by_ms']-150-self.now())
        cap_rows=[]
        cap_proven=False
        while self.now()-trigger[0] < params['final_expected_by_ms']:
            cap_rows.append(self.read(['D120']))
            pair=cap_rows[-2:]
            cap_proven=(len(pair)==2 and pair[0]['end_ms']<=pair[1]['start_ms'] and
                        all(r['values']['D120']==procedure['expect']['D120'] and
                            r['end_ms']-trigger[0]<=params['final_expected_by_ms'] for r in pair))
            if cap_proven:
                break
        by_deadline={'status':'PASS' if cap_proven else 'UNVERIFIED','reason':'Saturated accumulator positively observed twice before conservative deadline' if cap_proven else 'No qualified proof of saturation by original deadline','observation_sequences':[r['sequence'] for r in cap_rows[-2:]],'capture_sequences':[r['sequence'] for r in cap_rows]}
        self.wait_ms(trigger[1]+params['final_expected_by_ms']-self.now())
        plateau = self.observe(procedure['expect'], params['final_observation_hold_ms'], list(procedure['expect']))
        return {'status': aggregate([timing['status'], plateau['status'],by_deadline['status']]), 'timing': timing, 'plateau': plateau,'integral_by_deadline':by_deadline}

    def jitter(self, procedure, suite):
        params = procedure['params']
        self.apply(params['setup_words'])
        case = next(c for c in suite['cases'] if c['id'] == 'STD-044')
        steps = case['steps'][2:62]
        if len(steps) != 60 or any(s['duration_ms'] != 100 for s in steps):
            raise ValueError('Unexpected frozen jitter schedule')
        start = self.now()
        for index, step in enumerate(steps):
            self.wait_ms(start+100*index-self.now())
            rows = self.apply(step['write'])
            self.emit('jitter_schedule', index=index, nominal_start_ms=start+100*index,
                      write_sequences=[r['sequence'] for r in rows])
        self.wait_ms(start+6000-self.now())
        self.apply(params['recovery_write'])
        recovery = self.observe(procedure['expect'], params['recovery_hold_ms'], list(procedure['expect']))
        return {'status': 'UNVERIFIED' if recovery['status'] == 'PASS' else recovery['status'],
                'waveform_status': 'UNVERIFIED', 'reason': 'Applied 60 timed requests; physical 100ms waveform not captured',
                'recovery': recovery}


def run(*, isolated_bench=False, audit_only=False, output_name='run01'):
    plan, suite, record = load_inputs()
    if not audit_only and not isolated_bench:
        raise ValueError('Explicit isolated bench authorization required')
    if not output_name or output_name in {'.','..'} or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in output_name):
        raise ValueError('Output name must be a task-local identifier')
    out = EVIDENCE/output_name
    out.mkdir(parents=True, exist_ok=False)
    report = {'task_id': plan['task_id'], 'at': datetime.now(timezone.utc).isoformat(),
              'source_sha256': digest(CASE/'source.fxil'), 'test_sha256': digest(CASE/'test_cases.json'),
              'plan_sha256': digest(EVIDENCE/'S6-qualification-plan.json'),
              'backend_sha256': digest(__file__), 'grader_sha256': digest(WORKSPACE/'src/plcweave/sampled.py'),
              'cpu_control_sha256': digest(WORKSPACE/'src/plcweave/cpu_control.py'),
              'capture_policy_sha256': digest(EVIDENCE/'S6-deadline-capture-addendum.json'),
              'capture_freeze_sha256': digest(EVIDENCE/'S6-deadline-capture-freeze.json'),
              'capture_fixture_sha256': digest(WORKSPACE/'tests/test_saturation_deadline.py'),
              'original_cases': capability_audit(suite), 'supplemental_procedures': [
                  {'id':p['id'],'source_case_ids':p['source_case_ids'],'execution':'not_executed','status':'UNVERIFIED','reason':'Procedure not reached'} for p in plan['supplemental_procedures']],
              'status': 'UNVERIFIED', 'limits': ['No original scan waveform replay','No electrical or plant validation','No binary readback attestation']}
    if audit_only:
        (out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        return report
    lock = EVIDENCE/'serial.lock'
    token = str(uuid.uuid4())
    descriptor = os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    with os.fdopen(descriptor,'w') as stream:
        json.dump({'owner': 'codex', 'pid': os.getpid(), 'token': token}, stream)
    bench = None
    controller = None
    original = None
    executor = None
    try:
        with (out/'trace.jsonl').open('w', encoding='utf-8') as stream:
            try:
                bench = candidate_bench(CASE)
                executor = Executor(bench, stream, time.monotonic()+1500)
                bench.client=LoggedClient(bench.client,executor)
                report['identity'] = bench.verify()
                controller = CPUControl(bench, isolated_bench=True,audit_callback=executor.audit_transport)
                original = controller.state()
                if original['M8000'] != 1:
                    raise ValueError('Expected verified original RUN state')
                plateau_passed = False
                current_index=None
                for current_index,proc in enumerate(plan['supplemental_procedures']):
                    executor.procedure = proc['id']
                    print('START', proc['id'], flush=True)
                    if proc['kind'] == 'output_gate':
                        if not plateau_passed:
                            report['supplemental_procedures'][current_index]['reason']='Saturated prerequisite not established'
                            continue
                    else:
                        report['supplemental_procedures'][current_index]['execution']='attempted'
                        executor.reset(controller, original, proc.get('initial_words', {}))
                    report['supplemental_procedures'][current_index]['execution']='attempted'
                    result = {'id': proc['id'], 'source_case_ids': proc['source_case_ids'], 'scope': proc['scope'],'execution':'executed'}
                    if proc['kind'] in {'initialization', 'steady', 'output_gate'}:
                        result['steps'] = [executor.step(step) for step in proc['steps']]
                        result['status'] = aggregate(step['status'] for step in result['steps'])
                    elif proc['kind'] == 'edge_timing':
                        executor.apply(proc['params']['setup_words'])
                        executor.wait_ms(proc['params'].get('setup_hold_ms', 200))
                        result['steps'] = [executor.step(step) for step in proc.get('steps', [])]
                        result['events'] = [executor.event(event) for event in proc['events']]
                        result['status'] = aggregate([r['status'] for r in [*result['steps'], *result['events']]])
                    elif proc['kind'] == 'saturation':
                        result.update(executor.saturation(proc))
                        plateau_passed = result['plateau']['status'] == 'PASS'
                    elif proc['kind'] == 'jitter':
                        result.update(executor.jitter(proc, suite))
                    report['supplemental_procedures'][current_index]=result
                    print('END', proc['id'], result['status'], flush=True)
                    (out/'progress.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
                    if result['status'] in {'PROGRAM_FAIL', 'TEST_INFRA_ERROR'}:
                        report['status'] = result['status']
                        break
            except BaseException as exc:
                report.update(status='TEST_INFRA_ERROR', error=repr(exc))
                if 'current_index' in locals() and current_index is not None and report['supplemental_procedures'][current_index]['execution']=='attempted':
                    report['supplemental_procedures'][current_index].update(status='TEST_INFRA_ERROR',error=repr(exc))
            finally:
                if bench is not None and bench.verified and controller is not None and original is not None:
                    try:
                        if controller.state()['M8000'] != 1:
                            controller.start()
                        controller.restore(original)
                        report['final_identity'] = bench.verify()
                        if executor is None:
                            raise ValueError('No owned executor for cleanup')
                        executor.deadline = time.monotonic()+30
                        executor.procedure = 'cleanup'
                        executor.apply({'D192':1,'D191':0,'D193':0,'D190':1,'D1056':0,'D102':60,'D261':60})
                        report['cleanup_observation'] = executor.observe(ZERO,1500,list(ZERO))
                        if report['cleanup_observation']['status'] != 'PASS':
                            raise ValueError('Stopped zero-output cleanup not confirmed')
                        report['cpu_exit'] = controller.state()
                        report['cleanup'] = 'RUN retained, original control flags restored, application stopped/output disabled/zero readback'
                    except BaseException as exc:
                        report.update(status='TEST_INFRA_ERROR', cleanup='restore_unconfirmed', cleanup_error=repr(exc))
                else:
                    report['cleanup'] = 'No verified identity, no cleanup writes permitted'
                if bench is not None:
                    bench.close()
                report['serial_closed'] = True
    finally:
        if lock.exists() and json.loads(lock.read_text(encoding='utf-8')).get('token') == token:
            lock.unlink()
        report['serial_lock_removed'] = not lock.exists()
        try:load_inputs()
        except Exception as exc:report.update(status='TEST_INFRA_ERROR',freeze_error=repr(exc))
        report['actual_executed_count']=sum(p['execution']=='executed' for p in report['supplemental_procedures'])
        report['attempted_count']=sum(p['execution']=='attempted' for p in report['supplemental_procedures'])
        report['supplemental_status']=aggregate(p['status'] for p in report['supplemental_procedures'])
        (out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--isolated-bench', action='store_true')
    parser.add_argument('--audit-only', action='store_true')
    parser.add_argument('--output-name', default='run01')
    args = parser.parse_args()
    result = run(isolated_bench=args.isolated_bench, audit_only=args.audit_only, output_name=args.output_name)
    print(json.dumps({'status':result['status'],'supplemental_executed':result.get('actual_executed_count',0),'procedure_count':len(result['supplemental_procedures']),'original_cases':len(result['original_cases'])}))
    raise SystemExit(1 if result['status'] in {'PROGRAM_FAIL','TEST_INFRA_ERROR'} else 0)
