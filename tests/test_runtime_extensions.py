"""Independent small arithmetic/contact oracles, frozen before implementation."""
import pytest
import gxwlib
from plcweave.fx import write_program

def sim(tmp_path, text):
    instructions = [{"mnemonic": row.split()[0], "operands": row.split()[1:]} for row in text.split(";")]
    path = tmp_path / "case.csv"
    write_program(path, instructions, quoted=True)
    return gxwlib.Simulator(gxwlib.compile_program(gxwlib.load_csv(path, device_profile="fx"), profile="fx3u"), scan_period_ns=10_000_000)

@pytest.mark.parametrize("op,a,b,expected", [("=",-3,-3,True),("<",-1,0,True),("<=",2,2,True),(">",2,3,False),(">=",-2,-3,True)])
def test_signed_contacts(tmp_path,op,a,b,expected):
    s = sim(tmp_path, f"LD M8000;AND{op} K{a} K{b};OUT M0;END")
    assert s.step().get("M0") == expected

def test_arithmetic_width_and_division_sign(tmp_path):
    s = sim(tmp_path,"LD M8000;SUB K-32768 K1 D0;MUL K-300 K300 D2;DIV K-17 K5 D4;END")
    r = s.step()
    assert r.get_word("D0") == 32767
    assert r.get_word("D2") == -24464 and r.get_word("D3") == -2
    assert r.get_word("D4") == -3 and r.get_word("D5") == -2

def test_conditioned_arithmetic_and_same_scan(tmp_path):
    s = sim(tmp_path,"LD M8000;MOV K12 D0;SUB D0 K5 D0;AND= D0 K7;OUT M2;LDI M8000;MUL K3 K4 D2;END")
    r = s.step()
    assert r.get("M2") and r.get_word("D2") == 0

@pytest.mark.parametrize("relay,scan_ns",[("M8012",10_000_000),("M8013",100_000_000)])
def test_clock_label_means_full_period(tmp_path, relay, scan_ns):
    s=sim(tmp_path,f"LD {relay};OUT M0;END")
    s.set_scan_period_ns(scan_ns)
    assert [s.step().get("M0") for _ in range(10)] == [True]*5+[False]*5

@pytest.mark.parametrize("instruction",["PID D0 D1 D2 D3","DIV K1 K0 D0","DIV K1 D0 D2","MUL K1 K1 D8511"])
def test_unverified_forms_fail_closed(tmp_path, instruction):
    with pytest.raises(gxwlib.GxwError):
        sim(tmp_path, f"LD M8000;{instruction};END")
