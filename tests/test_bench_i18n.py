"""i18n 字典测试：各语言 key 齐全、zh 与界面/引擎既有文案逐字一致、数据词往返映射。

字典是 GUI 多语言的唯一来源；这里同时锁住两类不变量：
1. STRINGS 每个 key 在 LANGUAGES 内译文齐全且占位符一致（i18n.validate）；
2. zh 译文与引擎原值/既有测试断言逐字一致——默认语言下界面必须与旧版渲染相同。
"""
import pytest

from plcweave.bench import i18n
from plcweave.bench.engine import State
from plcweave.bench.i18n import LANGUAGES, t, tr, untr, validate


@pytest.fixture(autouse=True)
def restore_language():
    yield
    i18n.set_language(i18n.DEFAULT_LANGUAGE)


def test_validate_reports_no_problems():
    assert validate() == []


def test_six_languages_registered():
    assert set(LANGUAGES) == {"zh", "en", "fr", "pt", "es", "ar"}
    assert set(LANGUAGES) == {"zh", *i18n.STRINGS["lang.label"]}
    assert i18n.DEFAULT_LANGUAGE == "zh"


def test_every_language_has_every_key():
    for key, entry in i18n.STRINGS.items():
        assert set(entry) == set(LANGUAGES), key


def test_fallback_missing_language_and_key():
    # 单语言缺译文回退中文；缺 key 回退 key 本身
    assert t("no.such.key") == "no.such.key"
    entry = i18n.STRINGS["btn.start"]
    entry["en"] = ""
    try:
        i18n.set_language("en")
        assert t("btn.start") == "开始仿真"
    finally:
        entry["en"] = "Start simulation"


def test_zh_matches_existing_ui_strings():
    i18n.set_language("zh")
    assert t("app.title", version="0.6.2") == "PLCWeave · 手动硬件在环仿真台  V0.6.2"
    assert t("btn.start") == "开始仿真"
    assert t("btn.stop_sim") == "结束仿真"
    assert t("btn.stop_manual") == "结束手动测试"
    assert t("btn.script_confirm") == "确认测试结束"
    assert t("cust.exported", count=2) == "已导出 2 条监控"
    assert t("cust.imported", count=3) == "CSV 导入 3 条"
    assert t("da.raw_alias", raw=3000, alias=t("ao.alias0")) == "raw 3000 · 手册 DA0 / D8050"
    assert t("script.loaded", name="run.py") == "脚本：run.py"
    assert t("status.data_age", age="—", refresh="—", state="—") == \
        "数据年龄：—   刷新耗时：—   状态：—"


def test_state_map_covers_all_states():
    states = (State.DISCONNECTED, State.CONNECTING, State.CONNECTED, State.STARTING,
              State.SIMULATING, State.ENDING, State.FAULT, State.SCRIPT_RUNNING,
              State.SCRIPT_CONFIRM, State.MANUAL)
    for state in states:
        assert state in i18n.DATA_KEYS, state
        assert untr(tr(state)) == state
    i18n.set_language("en")
    assert tr(State.SIMULATING) == "Simulating"
    assert tr(State.MANUAL) == "Manual test"


def test_engine_log_vocabulary_round_trip():
    # 抽样覆盖动作/结果/原因/权限/交互模式；未收录词原样透传
    samples = ("已读回", "已发送（不读回）", "待应用", "钳位", "结果未知",
               "添加或更新寄存器监控", "导入监控CSV", "导出监控CSV",
               "该点位需要原测试工程的输入映射", "正常结束", "异常中断",
               "只读", "只写", "读写", "保持开关", "按住有效")
    for word in samples:
        assert untr(tr(word)) == word, word
    assert tr("自由文本 不在字典") == "自由文本 不在字典"
    assert untr("自由文本 不在字典") == "自由文本 不在字典"
    i18n.set_language("en")
    assert tr("已发送（不读回）") == "Sent (no read-back)"
    assert tr("读写") == "RW"
    assert tr("按住有效") == "Hold"


def test_language_switch_reverses_combobox_words():
    for code in LANGUAGES:
        i18n.set_language(code)
        for display, canonical in (("只读", "只读"), ("读写", "读写"),
                                   ("按住有效", "按住有效")):
            assert untr(tr(canonical)) == canonical


def test_sample_translations_per_language():
    # 每个 lock 一条代表译文，防止后续批量修改时串语种
    i18n.set_language("fr")
    assert t("btn.start") == "Démarrer la simulation"
    assert t("lang.label") == "Langue"
    assert tr("仿真中") == "En simulation"
    i18n.set_language("pt")
    assert t("btn.start") == "Iniciar simulação"
    assert tr("仿真中") == "Simulando"
    i18n.set_language("es")
    assert t("btn.start") == "Iniciar simulación"
    assert tr("仿真中") == "Simulando"
    assert tr("已读回") == "Releído"
    i18n.set_language("ar")
    assert t("btn.start") == "بدء المحاكاة"
    assert t("lang.label") == "اللغة"
    assert tr("仿真中") == "قيد المحاكاة"


def test_arabic_uses_arabic_capable_font_family():
    # 字体策略：阿拉伯语必须用 Segoe UI（雅黑无阿拉伯字形），其余用微软雅黑
    assert i18n.ui_family() == "Microsoft YaHei UI"
    i18n.set_language("ar")
    assert i18n.ui_family() == "Segoe UI"
    i18n.set_language("fr")
    assert i18n.ui_family() == "Microsoft YaHei UI"
