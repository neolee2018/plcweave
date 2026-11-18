"""仿真台界面文案字典（i18n，6 语种：中/英/法/葡/西/阿拉伯）。

设计约定：
- 界面静态文案全部以稳定 key 收录在 STRINGS，每种语言一份译文；缺译文回退中文，
  缺 key 回退 key 本身（便于渐进补齐新语言）。
- 引擎/存储产生的数据词（State、日志 action/result/reason、会话状态、X 交互模式、
  监控权限）保持中文原值为唯一权威：持久化记录、ui_config、engine 比较逻辑都不翻译，
  仅在界面显示边界用 tr() 把原值映射为当前语言；untr() 做反向映射（下拉框选择）。
- 新增语言：在 LANGUAGES 注册显示名，并为 STRINGS 中每个 key 补齐译文、为
  app.py 的按钮宽度表（BTN_WIDTHS 与各 _bind_button 字典）补一列宽度即可；
  validate() 供测试校验各语言 key 与格式化占位符齐全。
- 字体：Tk 命名字体按语言切换 family——阿拉伯语用 Segoe UI（微软雅黑无阿拉伯字形），
  其余语言用 Microsoft YaHei UI（覆盖 CJK 与拉丁重音字母）。Segoe UI 无 CJK，
  阿拉伯语界面下中文监控名称可能显示为方框，属已知限制；Tk 8.6 不做 RTL 布局镜像。

线程模型：t()/tr() 只做字典查找，worker 线程与 UI 线程均可调用。
"""
from __future__ import annotations

import re
import string

# 语言注册表：代码 → 界面显示名。新增语言在此登记并补齐 STRINGS 译文。
LANGUAGES: dict[str, str] = {
    "zh": "中文",
    "en": "English",
    "fr": "Français",
    "pt": "Português",
    "es": "Español",
    "ar": "العربية",
}
DEFAULT_LANGUAGE = "zh"

# 各语言界面字体 family：YaHei 覆盖 CJK + 拉丁重音；阿拉伯文须用 Segoe UI。
UI_FONT_FAMILIES: dict[str, str] = {"ar": "Segoe UI"}
UI_FONT_DEFAULT = "Microsoft YaHei UI"

_language = DEFAULT_LANGUAGE

# ---------------------------------------------------------------------------
# 界面静态文案：key → {语言: 译文}。zh 必须与既有界面文案逐字一致（测试断言依赖）。
# ---------------------------------------------------------------------------
STRINGS: dict[str, dict[str, str]] = {
    # 应用框架
    "app.title": {"zh": "PLCWeave · 手动硬件在环仿真台  V{version}",
                  "en": "PLCWeave · Manual HIL Bench  V{version}",
                  "fr": "PLCWeave · Banc d'essai HIL manuel  V{version}",
                  "pt": "PLCWeave · Bancada HIL manual  V{version}",
                  "es": "PLCWeave · Banco HIL manual  V{version}",
                  "ar": "PLCWeave · منصة HIL اليدوية  V{version}"},
    "lang.label": {"zh": "语言", "en": "Language", "fr": "Langue", "pt": "Idioma",
                   "es": "Idioma", "ar": "اللغة"},
    "status.demo_suffix": {"zh": " · 演示模式", "en": " · Demo", "fr": " · Démo",
                           "pt": " · Demonstração", "es": " · Demo", "ar": " · وضع العرض"},
    "status.unknown_error": {"zh": "未知错误", "en": "Unknown error", "fr": "Erreur inconnue",
                             "pt": "Erro desconhecido", "es": "Error desconocido",
                             "ar": "خطأ غير معروف"},

    # 顶栏连接区
    "field.baud": {"zh": "波特率", "en": "Baud", "fr": "Bauds", "pt": "Baud",
                   "es": "Baudios", "ar": "سرعة البود"},
    "field.format": {"zh": "数据格式", "en": "Format", "fr": "Format", "pt": "Formato",
                     "es": "Formato", "ar": "التنسيق"},
    "field.station": {"zh": "从机地址", "en": "Station", "fr": "Station", "pt": "Estação",
                      "es": "Estación", "ar": "المحطة"},
    "field.version": {"zh": "版本地址", "en": "Version addr", "fr": "Adresse version",
                      "pt": "End. versão", "es": "Dir. versión", "ar": "عنوان الإصدار"},
    "btn.connect": {"zh": "连接", "en": "Connect", "fr": "Connecter", "pt": "Conectar",
                    "es": "Conectar", "ar": "اتصال"},
    "btn.disconnect": {"zh": "断开", "en": "Disconnect", "fr": "Déconnecter",
                       "pt": "Desconectar", "es": "Desconectar", "ar": "قطع الاتصال"},
    "version.none": {"zh": "程序版本：—", "en": "Program version: —",
                     "fr": "Version programme : —", "pt": "Versão do programa: —",
                     "es": "Versión del programa: —", "ar": "إصدار البرنامج: —"},
    "version.from": {"zh": "程序版本：{value}（来自 D{address}）",
                     "en": "Program version: {value} (from D{address})",
                     "fr": "Version programme : {value} (depuis D{address})",
                     "pt": "Versão do programa: {value} (de D{address})",
                     "es": "Versión del programa: {value} (de D{address})",
                     "ar": "إصدار البرنامج: {value} (من D{address})"},
    "version.unread": {"zh": "版本未读取", "en": "Version not read", "fr": "Version non lue",
                       "pt": "Versão não lida", "es": "Versión no leída",
                       "ar": "الإصدار غير مقروء"},
    "version.invalid": {"zh": "版本失效（断线）", "en": "Version invalid (offline)",
                        "fr": "Version invalide (hors ligne)", "pt": "Versão inválida (offline)",
                        "es": "Versión inválida (sin conexión)",
                        "ar": "الإصدار غير صالح (انقطاع الاتصال)"},
    "conn.ok_message": {"zh": "已连接", "en": "Connected", "fr": "Connecté",
                        "pt": "Conectado", "es": "Conectado", "ar": "تم الاتصال"},
    "conn.err.version": {"zh": "请填写实际程序的版本寄存器地址",
                         "en": "Enter the version register address of the real program",
                         "fr": "Saisissez l'adresse du registre de version du programme réel",
                         "pt": "Informe o endereço do registrador de versão do programa real",
                         "es": "Ingrese la dirección del registro de versión del programa real",
                         "ar": "أدخل عنوان سجل إصدار البرنامج الفعلي"},
    "conn.err.station": {"zh": "从机地址须为 1–247 的整数",
                         "en": "Station must be an integer from 1 to 247",
                         "fr": "L'adresse d'esclave doit être un entier de 1 à 247",
                         "pt": "A estação deve ser um inteiro de 1 a 247",
                         "es": "La estación debe ser un entero de 1 a 247",
                         "ar": "يجب أن يكون عنوان المحطة عددًا صحيحًا من 1 إلى 247"},

    # 状态行
    "status.data_age": {"zh": "数据年龄：{age}   刷新耗时：{refresh}   状态：{state}",
                        "en": "Data age: {age}   Poll time: {refresh}   State: {state}",
                        "fr": "Âge des données : {age}   Durée du sondage : {refresh}   État : {state}",
                        "pt": "Idade dos dados: {age}   Tempo de consulta: {refresh}   Estado: {state}",
                        "es": "Antigüedad de datos: {age}   Tiempo de sondeo: {refresh}   Estado: {state}",
                        "ar": "عمر البيانات: {age}   زمن الاستعلام: {refresh}   الحالة: {state}"},
    "status.age_ago": {"zh": "{seconds}s 前", "en": "{seconds}s ago", "fr": "il y a {seconds} s",
                       "pt": "há {seconds}s", "es": "hace {seconds}s", "ar": "قبل {seconds} ث"},
    "status.in_flight": {"zh": "   组{group}待确认", "en": "   group {group} awaiting confirm",
                         "fr": "   groupe {group} en attente de confirmation",
                         "pt": "   grupo {group} aguardando confirmação",
                         "es": "   grupo {group} en espera de confirmación",
                         "ar": "   المجموعة {group} بانتظار التأكيد"},

    # 小灯文字
    # 灯下文字宽度只有约 26px（每卡 8 列），非中文必须用缩写，否则被裁切成半个词。
    "led.on": {"zh": "ON", "en": "ON", "fr": "ON", "pt": "ON", "es": "ON", "ar": "ON"},
    "led.off": {"zh": "OFF", "en": "OFF", "fr": "OFF", "pt": "OFF", "es": "OFF", "ar": "OFF"},
    "led.unknown": {"zh": "未知", "en": "N/A", "fr": "n.d.", "pt": "n/d",
                    "es": "n/d", "ar": "غ.م"},
    "led.pending": {"zh": "待确认", "en": "TBC", "fr": "att.", "pt": "conf.",
                    "es": "pend.", "ar": "انتظار"},
    "led.stale": {"zh": "过期", "en": "OLD", "fr": "pér.", "pt": "velho",
                  "es": "viejo", "ar": "قديم"},

    # 数字输入卡
    "di.title": {"zh": "数字输入  X0–X7", "en": "Digital inputs  X0–X7",
                 "fr": "Entrées TOR  X0–X7", "pt": "Entradas  X0–X7",
                 "es": "Entradas  X0–X7", "ar": "مدخلات  X0–X7"},
    "di.interaction": {"zh": "交互", "en": "Mode", "fr": "Mode", "pt": "Modo",
                       "es": "Modo", "ar": "النمط"},
    "di.hint_layout": {"zh": "横向单排 · 下方小灯显示 PLC 确认的生效状态",
                       "en": "One row · LED shows the PLC-confirmed state",
                       "fr": "Une rangée · LED = état confirmé par le PLC",
                       "pt": "Uma fileira · LED = estado confirmado pelo PLC",
                       "es": "Una fila · LED = estado confirmado por el PLC",
                       "ar": "صف واحد · المؤشر = الحالة المؤكدة من PLC"},
    "di.hint_align": {"zh": "X0 与 Y0、X1 与 Y1 依次上下对齐；目标样式与状态灯分开",
                      "en": "X0 over Y0; target vs status LED separate",
                      "fr": "X0 au-dessus de Y0 ; cible et LED séparées",
                      "pt": "X0 acima de Y0; alvo e LED separados",
                      "es": "X0 sobre Y0; objetivo y LED separados",
                      "ar": "X0 فوق Y0؛ الهدف والمؤشر منفصلان"},
    "io.legend": {"zh": "脚本启用：{items}", "en": "Script I/O: {items}",
                  "fr": "E/S script : {items}", "pt": "E/S do script: {items}",
                  "es": "E/S del script: {items}", "ar": "إدخال/إخراج السكربت: {items}"},
    "di.hw_expand": {"zh": "展开硬件原值", "en": "Raw X",
                     "fr": "Valeurs X brutes", "pt": "Valores X brutos",
                     "es": "Valores X en bruto", "ar": "قيم X الخام"},
    "di.hw_collapse": {"zh": "收起硬件原值", "en": "Hide X",
                       "fr": "Masquer X bruts", "pt": "Ocultar X brutos",
                       "es": "Ocultar X en bruto", "ar": "إخفاء قيم X الخام"},

    # 模拟输入卡
    "ai.title": {"zh": "模拟输入  AD0–AD3", "en": "Analog inputs  AD0–AD3",
                 "fr": "Entrées analog.  AD0–AD3", "pt": "Entradas analóg.  AD0–AD3",
                 "es": "Entradas analóg.  AD0–AD3", "ar": "مدخلات تناظرية  AD0–AD3"},
    "ai.hint": {"zh": "每路竖直显示 · −/＋ 调节 · 滑条不可拖动 · 数值在滑条下方",
                "en": "Vertical · adjust with −/＋ · slider read-only · value below",
                "fr": "Vertical · −/＋ · curseur lecture seule · valeur dessous",
                "pt": "Vertical · −/＋ · barra só leitura · valor abaixo",
                "es": "Vertical · −/＋ · barra solo lectura · valor abajo",
                "ar": "رأسي · −/＋ · شريط للقراءة فقط · القيمة أدناه"},
    # 英文两行显示：AD 列宽约 78px，单行 "Target 0.00 / Effective 0.00" 会被裁切
    "ai.target_effective_none": {"zh": "目标 / 生效 —", "en": "Tgt —\nEff —",
                                 "fr": "Cible —\nEff —", "pt": "Alvo —\nEfet. —",
                                 "es": "Obj. —\nEfec. —", "ar": "الهدف —\nالفعلي —"},
    "ai.target_effective": {"zh": "目标 {target} / 生效 {effective}",
                            "en": "Tgt {target}\nEff {effective}",
                            "fr": "Cible {target}\nEff {effective}",
                            "pt": "Alvo {target}\nEfet. {effective}",
                            "es": "Obj. {target}\nEfec. {effective}",
                            "ar": "الهدف {target}\nالفعلي {effective}"},
    "ai.raw_over": {"zh": "raw {raw}（越量程）", "en": "raw {raw} (over range)",
                    "fr": "raw {raw} (hors plage)", "pt": "raw {raw} (fora da faixa)",
                    "es": "raw {raw} (fuera de rango)", "ar": "raw {raw} (خارج النطاق)"},
    "btn.apply": {"zh": "应用", "en": "OK", "fr": "OK", "pt": "OK",
                  "es": "OK", "ar": "OK"},
    # AD 加减按钮：全角 ＋ 在 Segoe UI（阿语字体）里缺字形、回退 CJK 字体后被裁
    "btn.minus": {"zh": "−", "en": "-", "fr": "-", "pt": "-", "es": "-", "ar": "-"},
    "btn.plus": {"zh": "＋", "en": "+", "fr": "+", "pt": "+", "es": "+", "ar": "+"},

    # 数字输出卡
    "do.title": {"zh": "数字输出  Y0–Y7", "en": "Digital outputs  Y0–Y7",
                 "fr": "Sorties TOR  Y0–Y7", "pt": "Saídas  Y0–Y7",
                 "es": "Salidas  Y0–Y7", "ar": "مخرجات  Y0–Y7"},
    "do.hint": {"zh": "横向单排 · 下方小灯直接显示读取的 Y 状态 · 只读",
                "en": "One row · LED shows read Y state · read-only",
                "fr": "Une rangée · LED = état Y lu · lecture seule",
                "pt": "Uma fileira · LED = estado Y lido · só leitura",
                "es": "Una fila · LED = estado Y leído · solo lectura",
                "ar": "صف واحد · المؤشر = حالة Y المقروءة · للقراءة فقط"},
    "do.note": {"zh": "点位牌不可点击强制输出；未知和过期状态另有文字标记",
                "en": "Tiles cannot force output; states shown as text",
                "fr": "Les tuiles ne forcent pas la sortie ; états affichés en texte",
                "pt": "As placas não forçam saída; estados em texto",
                "es": "Las placas no fuerzan salida; estados en texto",
                "ar": "لا تفرض البطاقات المخرجات؛ الحالات نصيًا"},

    # 模拟输出卡
    "ao.title": {"zh": "模拟输出  DA1–DA2", "en": "Analog outputs  DA1–DA2",
                 "fr": "Sorties analog.  DA1–DA2", "pt": "Saídas analóg.  DA1–DA2",
                 "es": "Salidas analóg.  DA1–DA2", "ar": "مخرجات تناظرية  DA1–DA2"},
    "ao.hint": {"zh": "直接读取 D8050 / D8051 · 竖直只读滑条与下方数值 · 无加减",
                "en": "D8050/D8051 · read-only bars · no adjust",
                "fr": "D8050/D8051 · curseurs lecture seule · sans réglage",
                "pt": "D8050/D8051 · barras só leitura · sem ajuste",
                "es": "D8050/D8051 · barras solo lectura · sin ajuste",
                "ar": "D8050/D8051 · أشرطة للقراءة فقط · بدون ضبط"},
    "ao.alias0": {"zh": "手册 DA0 / D8050", "en": "Manual DA0 / D8050",
                  "fr": "Manuel DA0 / D8050", "pt": "Manual DA0 / D8050",
                  "es": "Manual DA0 / D8050", "ar": "الدليل DA0 / D8050"},
    "ao.alias1": {"zh": "手册 DA1 / D8051", "en": "Manual DA1 / D8051",
                  "fr": "Manuel DA1 / D8051", "pt": "Manual DA1 / D8051",
                  "es": "Manual DA1 / D8051", "ar": "الدليل DA1 / D8051"},
    "da.raw_alias": {"zh": "raw {raw} · {alias}", "en": "raw {raw} · {alias}",
                     "fr": "raw {raw} · {alias}", "pt": "raw {raw} · {alias}",
                     "es": "raw {raw} · {alias}", "ar": "raw {raw} · {alias}"},
    "da.raw_none": {"zh": "raw —", "en": "raw —", "fr": "raw —", "pt": "raw —",
                    "es": "raw —", "ar": "raw —"},

    # 底部操作栏
    "btn.start": {"zh": "开始仿真", "en": "Start simulation", "fr": "Démarrer la simulation",
                  "pt": "Iniciar simulação", "es": "Iniciar simulación", "ar": "بدء المحاكاة"},
    "btn.stop_sim": {"zh": "结束仿真", "en": "End simulation", "fr": "Terminer la simulation",
                     "pt": "Encerrar simulação", "es": "Terminar simulación",
                     "ar": "إنهاء المحاكاة"},
    "btn.stop_manual": {"zh": "结束手动测试", "en": "End manual test",
                        "fr": "Terminer l'essai manuel", "pt": "Encerrar teste manual",
                        "es": "Terminar prueba manual", "ar": "إنهاء الاختبار اليدوي"},
    "btn.apply_all": {"zh": "应用全部", "en": "Apply all", "fr": "Tout appliquer",
                      "pt": "Aplicar tudo", "es": "Aplicar todo", "ar": "تطبيق الكل"},
    "btn.reset": {"zh": "复位仿真输入", "en": "Reset inputs", "fr": "Réinitialiser",
                  "pt": "Zerar entradas", "es": "Reiniciar entradas", "ar": "تصفير المدخلات"},
    "btn.export_log": {"zh": "导出本次日志", "en": "Export session log",
                       "fr": "Exporter le journal", "pt": "Exportar registro",
                       "es": "Exportar registro", "ar": "تصدير السجل"},
    "btn.records": {"zh": "最近30次调试记录", "en": "Last 30 sessions",
                    "fr": "30 dernières sessions", "pt": "Últimos 30 registros",
                    "es": "Últimos 30 registros", "ar": "آخر 30 جلسة"},
    "btn.settings": {"zh": "版本与接口设置", "en": "Version & interface settings",
                     "fr": "Paramètres version & interface", "pt": "Config. versão & interface",
                     "es": "Config. versión e interfaz", "ar": "إعدادات الإصدار والواجهة"},
    "label.step": {"zh": "步长", "en": "Step", "fr": "Pas", "pt": "Passo", "es": "Paso",
                   "ar": "الخطوة"},
    "label.step_hint": {"zh": "步长可设 1%–10%（满量程）·", "en": "Step is 1%–10% of full scale ·",
                        "fr": "Pas réglable de 1 % à 10 % (pleine échelle) ·",
                        "pt": "Passo de 1% a 10% (escala completa) ·",
                        "es": "Paso de 1% a 10% (escala completa) ·",
                        "ar": "الخطوة من 1% إلى 10% (المقياس الكامل) ·"},

    # 日志区
    "log.title": {"zh": "本次操作日志", "en": "Session log", "fr": "Journal de session",
                  "pt": "Registro da sessão", "es": "Registro de la sesión", "ar": "سجل الجلسة"},
    "btn.load_script": {"zh": "加载脚本", "en": "Load script", "fr": "Charger script",
                        "pt": "Carregar script", "es": "Cargar script", "ar": "تحميل سكربت"},
    "btn.script_start": {"zh": "开始脚本测试", "en": "Start script test",
                         "fr": "Lancer le test script", "pt": "Iniciar teste de script",
                         "es": "Iniciar prueba de script", "ar": "بدء اختبار السكربت"},
    "btn.script_confirm": {"zh": "确认测试结束", "en": "Confirm test end",
                           "fr": "Confirmer la fin du test", "pt": "Confirmar fim do teste",
                           "es": "Confirmar fin de prueba", "ar": "تأكيد انتهاء الاختبار"},
    "log.col.time": {"zh": "时间", "en": "Time", "fr": "Heure", "pt": "Hora", "es": "Hora",
                     "ar": "الوقت"},
    "log.col.object": {"zh": "操作对象", "en": "Object", "fr": "Objet", "pt": "Objeto",
                       "es": "Objeto", "ar": "العنصر"},
    "log.col.value": {"zh": "目标值 / 生效值", "en": "Target / Effective", "fr": "Cible / Effective",
                      "pt": "Alvo / Efetivo", "es": "Objetivo / Efectivo", "ar": "الهدف / الفعلي"},
    "log.col.result": {"zh": "结果", "en": "Result", "fr": "Résultat", "pt": "Resultado",
                       "es": "Resultado", "ar": "النتيجة"},

    # 客户寄存器卡
    "cust.title": {"zh": "客户寄存器监控", "en": "Customer register monitor",
                   "fr": "Surveillance des registres client", "pt": "Monitor de registradores do cliente",
                   "es": "Monitor de registros del cliente", "ar": "مراقبة سجلات العميل"},
    "cust.col.address": {"zh": "地址", "en": "Address", "fr": "Adresse", "pt": "Endereço",
                         "es": "Dirección", "ar": "العنوان"},
    "cust.col.name": {"zh": "名称", "en": "Name", "fr": "Nom", "pt": "Nome", "es": "Nombre",
                      "ar": "الاسم"},
    "cust.col.value": {"zh": "PLC 读数", "en": "PLC value", "fr": "Valeur PLC", "pt": "Valor PLC",
                       "es": "Valor PLC", "ar": "قراءة PLC"},
    "cust.col.unit": {"zh": "单位 / 量程", "en": "Unit / Range", "fr": "Unité / Plage",
                      "pt": "Unidade / Faixa", "es": "Unidad / Rango", "ar": "الوحدة / النطاق"},
    "cust.col.access": {"zh": "权限", "en": "Access", "fr": "Accès", "pt": "Acesso",
                        "es": "Acceso", "ar": "الصلاحية"},
    "cust.col.sample": {"zh": "采样", "en": "Sample", "fr": "Échant.", "pt": "Amostra",
                        "es": "Muestra", "ar": "العينة"},
    "cust.label.watch_addr": {"zh": "监控地址", "en": "Address", "fr": "Adresse",
                              "pt": "Endereço", "es": "Dirección", "ar": "عنوان المراقبة"},
    "cust.label.name": {"zh": "名称", "en": "Name", "fr": "Nom", "pt": "Nome", "es": "Nombre",
                        "ar": "الاسم"},
    "cust.label.access": {"zh": "权限", "en": "Access", "fr": "Accès", "pt": "Acesso",
                          "es": "Acceso", "ar": "الصلاحية"},
    "btn.add_watch": {"zh": "添加监控", "en": "Add", "fr": "Ajouter", "pt": "Adicionar",
                      "es": "Agregar", "ar": "إضافة"},
    "btn.remove_watch": {"zh": "移除选中", "en": "Remove", "fr": "Retirer",
                         "pt": "Remover", "es": "Quitar", "ar": "إزالة"},
    "btn.import_csv": {"zh": "导入CSV", "en": "Import", "fr": "Importer",
                       "pt": "Importar", "es": "Importar", "ar": "استيراد"},
    "btn.export_csv": {"zh": "导出CSV", "en": "Export", "fr": "Exporter",
                       "pt": "Exportar", "es": "Exportar", "ar": "تصدير"},
    "cust.label.send_addr": {"zh": "发送地址", "en": "Send address", "fr": "Adresse d'envoi",
                             "pt": "Endereço de envio", "es": "Dirección de envío",
                             "ar": "عنوان الإرسال"},
    "cust.label.send_value": {"zh": "整数值", "en": "Integer value", "fr": "Entier",
                              "pt": "Inteiro", "es": "Entero", "ar": "قيمة صحيحة"},
    "btn.send": {"zh": "发送", "en": "Send", "fr": "Envoyer", "pt": "Enviar", "es": "Enviar",
                 "ar": "إرسال"},
    "cust.status.hint": {"zh": "仿真中可发送权限含“写”的监控地址",
                         "en": "Send to writable watches during simulation",
                         "fr": "Envoi aux adresses inscriptibles",
                         "pt": "Enviar para registos com escrita",
                         "es": "Enviar a registros con escritura",
                         "ar": "الإرسال إلى السجلات القابلة للكتابة"},
    "cust.err.addr_range": {"zh": "请输入 D0–D8511 内的监控地址",
                            "en": "Enter a watch address within D0–D8511",
                            "fr": "Saisissez une adresse de surveillance entre D0 et D8511",
                            "pt": "Informe um endereço de monitoração entre D0 e D8511",
                            "es": "Ingrese una dirección de monitoreo entre D0 y D8511",
                            "ar": "أدخل عنوان مراقبة ضمن D0–D8511"},
    "cust.err.name_len": {"zh": "名称最多 40 个字符", "en": "Name is limited to 40 characters",
                          "fr": "Nom limité à 40 caractères", "pt": "Nome limitado a 40 caracteres",
                          "es": "Nombre limitado a 40 caracteres", "ar": "الاسم بحد أقصى 40 حرفًا"},
    "cust.err.read": {"zh": "读取失败: {error}", "en": "Read failed: {error}",
                      "fr": "Échec de lecture : {error}", "pt": "Falha na leitura: {error}",
                      "es": "Error de lectura: {error}", "ar": "فشل القراءة: {error}"},
    "cust.err.empty": {"zh": "监控列表为空，先添加或导入条目",
                       "en": "Watch list is empty; add or import entries first",
                       "fr": "Liste vide ; ajoutez ou importez d'abord des entrées",
                       "pt": "Lista de monitoração vazia; adicione ou importe primeiro",
                       "es": "Lista de monitoreo vacía; agregue o importe primero",
                       "ar": "قائمة المراقبة فارغة؛ أضف عناصر أو استوردها أولاً"},
    "cust.sending": {"zh": "正在发送并读取 PLC…", "en": "Sending and reading PLC…",
                     "fr": "Envoi et lecture du PLC…", "pt": "Enviando e lendo o PLC…",
                     "es": "Enviando y leyendo el PLC…", "ar": "جارٍ الإرسال والقراءة من PLC…"},
    "cust.exported": {"zh": "已导出 {count} 条监控", "en": "Exported {count} watches",
                      "fr": "{count} surveillances exportées", "pt": "{count} monitorações exportadas",
                      "es": "{count} monitoreos exportados", "ar": "تم تصدير {count} عنصر مراقبة"},
    "cust.imported": {"zh": "CSV 导入 {count} 条", "en": "CSV imported {count} rows",
                      "fr": "Import CSV : {count} lignes", "pt": "CSV importado: {count} linhas",
                      "es": "CSV importado: {count} filas", "ar": "استيراد CSV: {count} صف"},
    "cust.import_skipped": {"zh": "，跳过 {count} 条（{reasons}）",
                            "en": "; skipped {count} ({reasons})",
                            "fr": " ; {count} ignorées ({reasons})",
                            "pt": "; {count} ignoradas ({reasons})",
                            "es": "; se omitieron {count} ({reasons})",
                            "ar": "؛ تم تخطي {count} ({reasons})"},
    "cust.skip_line": {"zh": "行{line} {reason}", "en": "line {line}: {reason}",
                       "fr": "ligne {line} : {reason}", "pt": "linha {line}: {reason}",
                       "es": "línea {line}: {reason}", "ar": "السطر {line}: {reason}"},
    "cust.updated": {"zh": "{obj} 监控列表已更新", "en": "{obj}: watch list updated",
                     "fr": "{obj} : liste de surveillance mise à jour",
                     "pt": "{obj}: lista de monitoração atualizada",
                     "es": "{obj}: lista de monitoreo actualizada",
                     "ar": "{obj}: تم تحديث قائمة المراقبة"},
    "cust.status_pending": {"zh": "待读取", "en": "Pending read", "fr": "Lecture en attente",
                            "pt": "Aguardando leitura", "es": "Lectura pendiente",
                            "ar": "بانتظار القراءة"},
    "cust.status_write_only": {"zh": "只写·不轮询", "en": "WO · no poll",
                               "fr": "Écrit. · sans sondage", "pt": "Escrita · sem consulta",
                               "es": "Escritura · sin sondeo", "ar": "كتابة · دون استعلام"},
    "cust.status_stale": {"zh": "过期 · {error}", "en": "Stale · {error}", "fr": "Périmé · {error}",
                          "pt": "Desatualizado · {error}", "es": "Desactualizado · {error}",
                          "ar": "قديم · {error}"},

    # 脚本
    "script.loaded": {"zh": "脚本：{name}", "en": "Script: {name}", "fr": "Script : {name}",
                      "pt": "Script: {name}", "es": "Script: {name}", "ar": "السكربت: {name}"},
    "script.none": {"zh": "脚本：未加载", "en": "Script: not loaded", "fr": "Script : non chargé",
                    "pt": "Script: não carregado", "es": "Script: no cargado",
                    "ar": "السكربت: غير محمّل"},
    "script.err.select_first": {"zh": "请先点击“加载脚本”选择 .py 测试脚本",
                                "en": "Click \"Load script\" first to choose a .py test script",
                                "fr": "Cliquez d'abord sur « Charger script » pour choisir un script .py",
                                "pt": "Clique primeiro em \"Carregar script\" para escolher um script .py",
                                "es": "Haga clic primero en \"Cargar script\" para elegir un script .py",
                                "ar": "انقر \"تحميل سكربت\" أولاً لاختيار سكربت اختبار .py"},
    "script.err.addr_range": {"zh": "版本地址须为 D0–D9999", "en": "Version address must be D0–D9999",
                              "fr": "L'adresse de version doit être D0–D9999",
                              "pt": "O endereço de versão deve ser D0–D9999",
                              "es": "La dirección de versión debe ser D0–D9999",
                              "ar": "يجب أن يكون عنوان الإصدار ضمن D0–D9999"},
    "script.done_title": {"zh": "测试完毕", "en": "Test finished", "fr": "Test terminé",
                          "pt": "Teste concluído", "es": "Prueba finalizada", "ar": "انتهى الاختبار"},
    "script.done_ok": {"zh": "脚本已结束", "en": "Script finished", "fr": "Script terminé",
                       "pt": "Script concluído", "es": "Script finalizado", "ar": "انتهى السكربت"},
    "script.done_error": {"zh": "脚本执行异常，请查看操作日志",
                          "en": "Script ended with errors; see the session log",
                          "fr": "Le script s'est terminé avec des erreurs ; voir le journal de session",
                          "pt": "O script terminou com erros; consulte o registro da sessão",
                          "es": "El script terminó con errores; consulte el registro de la sesión",
                          "ar": "انتهى السكربت بأخطاء؛ راجع سجل الجلسة"},
    "script.done_body": {"zh": "{outcome}（退出码 {code}）。{report}\n已记录 {count} 条通讯命令。\n\n"
                               "{handoff}\n窗口由你手动关闭。",
                         "en": "{outcome} (exit code {code}). {report}\n{count} Modbus commands recorded.\n\n"
                               "{handoff}\nClose this dialog manually.",
                         "fr": "{outcome} (code de sortie {code}). {report}\n{count} commandes Modbus enregistrées.\n\n"
                               "{handoff}\nFermez cette boîte de dialogue manuellement.",
                         "pt": "{outcome} (código de saída {code}). {report}\n{count} comandos Modbus registrados.\n\n"
                               "{handoff}\nFeche esta janela manualmente.",
                         "es": "{outcome} (código de salida {code}). {report}\n{count} comandos Modbus registrados.\n\n"
                               "{handoff}\nCierre esta ventana manualmente.",
                         "ar": "{outcome} (رمز الخروج {code}). {report}\nتم تسجيل {count} أمر Modbus.\n\n"
                               "{handoff}\nأغلق هذا الحوار يدويًا."},
    "script.report": {"zh": "\n脚本报告：{status}", "en": "\nScript report: {status}",
                      "fr": "\nRapport du script : {status}", "pt": "\nRelatório do script: {status}",
                      "es": "\nInforme del script: {status}", "ar": "\nتقرير السكربت: {status}"},
    "script.handoff_connected": {"zh": "点击确定后连接 PLC，进入手动测试。",
                                 "en": "Click OK to connect to the PLC and switch to manual testing.",
                                 "fr": "Cliquez sur OK pour connecter le PLC et passer à l'essai manuel.",
                                 "pt": "Clique em OK para conectar o PLC e mudar para o teste manual.",
                                 "es": "Haga clic en Aceptar para conectar el PLC y pasar a la prueba manual.",
                                 "ar": "انقر موافق للاتصال بـ PLC والانتقال إلى الاختبار اليدوي."},
    "script.handoff_failed": {"zh": "本次没有成功的 PLC 通讯，请确认后检查连接设置。",
                              "en": "No successful PLC communication this run; check the connection settings.",
                              "fr": "Aucune communication PLC réussie ; vérifiez les paramètres de connexion.",
                              "pt": "Nenhuma comunicação PLC bem-sucedida; verifique as configurações de conexão.",
                              "es": "No hubo comunicación exitosa con el PLC; verifique la configuración de conexión.",
                              "ar": "لم تكن هناك اتصالات ناجحة مع PLC؛ تحقق من إعدادات الاتصال."},

    # 存储与会话
    "store.log_not_open": {"zh": "当前会话日志未打开", "en": "The session log is not open",
                           "fr": "Le journal de session n'est pas ouvert",
                           "pt": "O registro da sessão não está aberto",
                           "es": "El registro de la sesión no está abierto",
                           "ar": "سجل الجلسة غير مفتوح"},

    # 通用文件类型与标题
    "filetype.zip": {"zh": "ZIP 归档", "en": "ZIP archive", "fr": "Archive ZIP",
                     "pt": "Arquivo ZIP", "es": "Archivo ZIP", "ar": "أرشيف ZIP"},
    "filetype.csv": {"zh": "CSV", "en": "CSV", "fr": "CSV", "pt": "CSV", "es": "CSV", "ar": "CSV"},
    "filetype.csv_text": {"zh": "CSV / 文本", "en": "CSV / text", "fr": "CSV / texte",
                          "pt": "CSV / texto", "es": "CSV / texto", "ar": "CSV / نص"},
    "filetype.all": {"zh": "所有文件", "en": "All files", "fr": "Tous les fichiers",
                     "pt": "Todos os arquivos", "es": "Todos los archivos", "ar": "كل الملفات"},
    "filetype.python": {"zh": "Python", "en": "Python", "fr": "Python", "pt": "Python",
                        "es": "Python", "ar": "Python"},
    "filetype.json": {"zh": "JSON", "en": "JSON", "fr": "JSON", "pt": "JSON", "es": "JSON",
                      "ar": "JSON"},
    "watch.import_title": {"zh": "导入监控寄存器 CSV", "en": "Import watch registers CSV",
                           "fr": "Importer les registres surveillés (CSV)",
                           "pt": "Importar registradores monitorados (CSV)",
                           "es": "Importar registros monitoreados (CSV)",
                           "ar": "استيراد سجلات المراقبة CSV"},
    "watch.export_title": {"zh": "导出监控寄存器 CSV", "en": "Export watch registers CSV",
                           "fr": "Exporter les registres surveillés (CSV)",
                           "pt": "Exportar registradores monitorados (CSV)",
                           "es": "Exportar registros monitoreados (CSV)",
                           "ar": "تصدير سجلات المراقبة CSV"},
    "load_script.title": {"zh": "加载项目测试脚本", "en": "Load project test script",
                          "fr": "Charger le script de test du projet",
                          "pt": "Carregar script de teste do projeto",
                          "es": "Cargar script de prueba del proyecto",
                          "ar": "تحميل سكربت اختبار المشروع"},

    # 导出本次日志
    "export.info_title": {"zh": "导出本次日志", "en": "Export session log",
                          "fr": "Exporter le journal", "pt": "Exportar registro",
                          "es": "Exportar registro", "ar": "تصدير السجل"},
    "export.none": {"zh": "当前没有进行中的调试记录。", "en": "No session log is currently being recorded.",
                    "fr": "Aucun enregistrement de débogage en cours.",
                    "pt": "Nenhum registro de depuração em andamento.",
                    "es": "Ningún registro de depuración en curso.",
                    "ar": "لا يوجد سجل تصحيح قيد التسجيل حاليًا."},
    "export.done_title": {"zh": "导出完成", "en": "Export complete", "fr": "Export terminé",
                          "pt": "Exportação concluída", "es": "Exportación completada",
                          "ar": "اكتمل التصدير"},
    "export.done": {"zh": "已导出：\n{path}", "en": "Exported:\n{path}", "fr": "Exporté :\n{path}",
                    "pt": "Exportado:\n{path}", "es": "Exportado:\n{path}", "ar": "تم التصدير:\n{path}"},
    "export.failed_title": {"zh": "导出失败", "en": "Export failed", "fr": "Échec de l'export",
                            "pt": "Falha na exportação", "es": "Error de exportación",
                            "ar": "فشل التصدير"},
    "export.failed_msg": {"zh": "导出失败: {error}", "en": "Export failed: {error}",
                          "fr": "Échec de l'export : {error}", "pt": "Falha na exportação: {error}",
                          "es": "Error de exportación: {error}", "ar": "فشل التصدير: {error}"},

    # 开始仿真确认
    "confirm.start_title": {"zh": "开始仿真前确认", "en": "Confirm before starting",
                            "fr": "Confirmer avant de démarrer", "pt": "Confirmar antes de iniciar",
                            "es": "Confirmar antes de iniciar", "ar": "تأكيد قبل البدء"},
    "confirm.start_body": {"zh": "请确认台架已按现场流程准备：\n\n"
                                 "1. 配套 HIL 调试程序已下载到 PLC 并处于 RUN\n"
                                 "2. RS485/USB-RS485 已连接到本机所选串口\n"
                                 "3. 输入接口档案地址与目标程序一致\n\n"
                                 "确认无误后开始仿真？",
                           "en": "Confirm the bench is prepared per field procedure:\n\n"
                                 "1. The matching HIL debug program is downloaded to the PLC and in RUN\n"
                                 "2. RS485/USB-RS485 is connected to the selected COM port\n"
                                 "3. The interface profile address matches the target program\n\n"
                                 "Start simulation?",
                           "fr": "Confirmez que le banc est prêt selon la procédure terrain :\n\n"
                                 "1. Le programme HIL correspondant est téléchargé dans le PLC et en RUN\n"
                                 "2. RS485/USB-RS485 est connecté au port COM sélectionné\n"
                                 "3. L'adresse du profil d'interface correspond au programme cible\n\n"
                                 "Démarrer la simulation ?",
                           "pt": "Confirme que a bancada está preparada conforme o procedimento de campo:\n\n"
                                 "1. O programa HIL correspondente está gravado no PLC e em RUN\n"
                                 "2. RS485/USB-RS485 está conectado à porta COM selecionada\n"
                                 "3. O endereço do perfil de interface corresponde ao programa alvo\n\n"
                                 "Iniciar a simulação?",
                           "es": "Confirme que el banco está preparado según el procedimiento de campo:\n\n"
                                 "1. El programa HIL correspondiente está descargado en el PLC y en RUN\n"
                                 "2. RS485/USB-RS485 está conectado al puerto COM seleccionado\n"
                                 "3. La dirección del perfil de interfaz coincide con el programa objetivo\n\n"
                                 "¿Iniciar la simulación?",
                           "ar": "أكّد أن المنصة جاهزة وفق إجراء الميدان:\n\n"
                                 "1. تم تنزيل برنامج HIL المطابق إلى PLC وهو في وضع RUN\n"
                                 "2. RS485/USB-RS485 متصل بمنفذ COM المحدد على هذا الجهاز\n"
                                 "3. عنوان ملف تعريف الواجهة يطابق البرنامج الهدف\n\n"
                                 "بدء المحاكاة؟"},

    # 关闭窗口
    "close.script_title": {"zh": "关闭测试窗口", "en": "Close test window",
                           "fr": "Fermer la fenêtre de test", "pt": "Fechar janela de teste",
                           "es": "Cerrar ventana de prueba", "ar": "إغلاق نافذة الاختبار"},
    "close.script_body": {"zh": "关闭窗口将结束本次脚本测试。是否关闭？",
                          "en": "Closing the window ends this script test. Close anyway?",
                          "fr": "Fermer la fenêtre met fin à ce test de script. Fermer quand même ?",
                          "pt": "Fechar a janela encerra este teste de script. Fechar mesmo assim?",
                          "es": "Cerrar la ventana finaliza esta prueba de script. ¿Cerrar de todos modos?",
                          "ar": "إغلاق النافذة ينهي اختبار السكربت. هل تريد الإغلاق؟"},
    "close.title": {"zh": "退出确认", "en": "Confirm exit", "fr": "Confirmer la sortie",
                    "pt": "Confirmar saída", "es": "Confirmar salida", "ar": "تأكيد الخروج"},
    "close.manual_detail": {"zh": "将结束本次记录并断开连接。PLC 将保留当前程序状态。",
                            "en": "This ends the current record and disconnects. The PLC keeps its current program state.",
                            "fr": "Cela met fin à l'enregistrement en cours et déconnecte. Le PLC conserve son état de programme.",
                            "pt": "Isso encerra o registro atual e desconecta. O PLC mantém seu estado de programa.",
                            "es": "Esto finaliza el registro actual y desconecta. El PLC conserva su estado de programa.",
                            "ar": "سيتم إنهاء التسجيل الحالي وفصل الاتصال. يحتفظ PLC بحالة برنامجه."},
    "close.sim_detail": {"zh": "将向 PLC 发送结束请求并断开连接，本次记录按“关闭窗口结束”归档。",
                         "en": "An end request is sent to the PLC before disconnecting; the record is archived as \"ended by window close\".",
                         "fr": "Une demande de fin est envoyée au PLC avant déconnexion ; l'enregistrement est archivé comme « fermé par la fenêtre ».",
                         "pt": "Uma solicitação de fim é enviada ao PLC antes de desconectar; o registro é arquivado como \"encerrado pelo fechamento da janela\".",
                         "es": "Se envía una solicitud de fin al PLC antes de desconectar; el registro se archiva como \"finalizado por cierre de ventana\".",
                         "ar": "سيتم إرسال طلب إنهاء إلى PLC قبل فصل الاتصال، ويُؤرشف التسجيل بـ \"انتهى بإغلاق النافذة\"."},
    "close.confirm": {"zh": "{detail}\n确定退出？", "en": "{detail}\nExit now?",
                      "fr": "{detail}\nQuitter maintenant ?", "pt": "{detail}\nSair agora?",
                      "es": "{detail}\n¿Salir ahora?", "ar": "{detail}\nهل تريد الخروج؟"},

    # 版本与接口设置对话框
    "dlg.settings_title": {"zh": "版本与接口设置", "en": "Version & interface settings",
                           "fr": "Paramètres version & interface", "pt": "Config. versão & interface",
                           "es": "Config. versión e interfaz", "ar": "إعدادات الإصدار والواجهة"},
    "dlg.settings.version_label": {"zh": "版本寄存器（目标程序实际维护的只读 Dn）",
                                   "en": "Version register (read-only Dn maintained by the target program)",
                                   "fr": "Registre de version (Dn en lecture seule maintenu par le programme cible)",
                                   "pt": "Registrador de versão (Dn somente leitura mantido pelo programa alvo)",
                                   "es": "Registro de versión (Dn de solo lectura mantenido por el programa objetivo)",
                                   "ar": "سجل الإصدار (Dn للقراءة فقط يحتفظ به البرنامج الهدف)"},
    "dlg.settings.profile": {"zh": "输入接口档案（JSON）", "en": "Input interface profile (JSON)",
                             "fr": "Profil d'interface d'entrée (JSON)",
                             "pt": "Perfil de interface de entrada (JSON)",
                             "es": "Perfil de interfaz de entrada (JSON)",
                             "ar": "ملف تعريف واجهة الإدخال (JSON)"},
    "dlg.settings.pick": {"zh": "选择…", "en": "Browse…", "fr": "Parcourir…", "pt": "Procurar…",
                          "es": "Examinar…", "ar": "استعراض…"},
    "dlg.settings.pick_title": {"zh": "选择接口档案 JSON", "en": "Choose interface profile JSON",
                                "fr": "Choisir le profil d'interface JSON",
                                "pt": "Escolher perfil de interface JSON",
                                "es": "Elegir perfil de interfaz JSON",
                                "ar": "اختيار ملف واجهة JSON"},
    "dlg.settings.refresh": {"zh": "刷新目标", "en": "Poll interval", "fr": "Intervalle de sondage",
                             "pt": "Intervalo de consulta", "es": "Intervalo de sondeo",
                             "ar": "فاصل الاستعلام"},
    "dlg.settings.storage": {"zh": "记录目录", "en": "Record folder", "fr": "Dossier d'enregistrement",
                             "pt": "Pasta de registros", "es": "Carpeta de registros",
                             "ar": "مجلد التسجيلات"},
    "dlg.settings.open_dir": {"zh": "打开目录", "en": "Open folder", "fr": "Ouvrir le dossier",
                              "pt": "Abrir pasta", "es": "Abrir carpeta", "ar": "فتح المجلد"},
    "dlg.settings.save": {"zh": "保存并校验", "en": "Save & validate", "fr": "Enregistrer et valider",
                          "pt": "Salvar e validar", "es": "Guardar y validar", "ar": "حفظ والتحقق"},
    "dlg.settings.saved_title": {"zh": "设置已保存", "en": "Settings saved",
                                 "fr": "Paramètres enregistrés", "pt": "Configurações salvas",
                                 "es": "Configuración guardada", "ar": "تم حفظ الإعدادات"},
    "dlg.settings.saved": {"zh": "设置与接口档案已应用。", "en": "Settings and interface profile applied.",
                           "fr": "Paramètres et profil d'interface appliqués.",
                           "pt": "Configurações e perfil de interface aplicados.",
                           "es": "Configuración y perfil de interfaz aplicados.",
                           "ar": "تم تطبيق الإعدادات وملف الواجهة."},
    "dlg.settings.err_version_title": {"zh": "版本地址无效", "en": "Invalid version address",
                                       "fr": "Adresse de version invalide",
                                       "pt": "Endereço de versão inválido",
                                       "es": "Dirección de versión inválida",
                                       "ar": "عنوان إصدار غير صالح"},
    "dlg.settings.err_profile_title": {"zh": "接口档案无效", "en": "Invalid interface profile",
                                       "fr": "Profil d'interface invalide",
                                       "pt": "Perfil de interface inválido",
                                       "es": "Perfil de interfaz inválido",
                                       "ar": "ملف واجهة غير صالح"},
    "dlg.settings.err_open_title": {"zh": "打开失败", "en": "Failed to open", "fr": "Échec de l'ouverture",
                                    "pt": "Falha ao abrir", "es": "Error al abrir", "ar": "فشل الفتح"},
    "profile.confirmed": {"zh": "已确认（允许实机写入）",
                          "en": "Confirmed (real-hardware writes allowed)",
                          "fr": "Confirmé (écritures sur matériel réel autorisées)",
                          "pt": "Confirmado (gravações em hardware real permitidas)",
                          "es": "Confirmado (escrituras en hardware real permitidas)",
                          "ar": "مؤكد (مسموح الكتابة على العتاد الفعلي)"},
    "profile.unconfirmed": {"zh": "未确认（实机禁止写入，仅演示可用）",
                            "en": "Unconfirmed (writes to real hardware are blocked; demo only)",
                            "fr": "Non confirmé (écritures sur matériel réel bloquées ; démo uniquement)",
                            "pt": "Não confirmado (gravações em hardware real bloqueadas; apenas demonstração)",
                            "es": "No confirmado (escrituras en hardware real bloqueadas; solo demostración)",
                            "ar": "غير مؤكد (الكتابة على العتاد الفعلي محظورة؛ للعرض فقط)"},
    "profile.current": {"zh": "当前档案：{name} · 状态 {status} · {gate}\n摘要 {digest}… · {note}",
                        "en": "Current profile: {name} · status {status} · {gate}\nDigest {digest}… · {note}",
                        "fr": "Profil actuel : {name} · état {status} · {gate}\nEmpreinte {digest}… · {note}",
                        "pt": "Perfil atual: {name} · estado {status} · {gate}\nResumo {digest}… · {note}",
                        "es": "Perfil actual: {name} · estado {status} · {gate}\nResumen {digest}… · {note}",
                        "ar": "الملف الحالي: {name} · الحالة {status} · {gate}\nالبصمة {digest}… · {note}"},

    # 测试脚本对话框
    "dlg.script_title": {"zh": "测试脚本与参数", "en": "Test script & arguments",
                         "fr": "Script de test et arguments", "pt": "Script de teste e argumentos",
                         "es": "Script de prueba y argumentos", "ar": "سكربت الاختبار والوسائط"},
    "dlg.script.label": {"zh": "测试脚本", "en": "Test script", "fr": "Script de test",
                         "pt": "Script de teste", "es": "Script de prueba", "ar": "سكربت الاختبار"},
    "dlg.script.choose": {"zh": "选择文件", "en": "Choose file", "fr": "Choisir un fichier",
                          "pt": "Escolher arquivo", "es": "Elegir archivo", "ar": "اختيار ملف"},
    "dlg.script.pick_title": {"zh": "选择已有 Python 测试脚本", "en": "Choose an existing Python test script",
                              "fr": "Choisir un script de test Python existant",
                              "pt": "Escolher um script de teste Python existente",
                              "es": "Elegir un script de prueba Python existente",
                              "ar": "اختيار سكربت اختبار Python موجود"},
    "dlg.script.args": {"zh": "脚本参数\n每行一项", "en": "Script arguments\none per line",
                        "fr": "Arguments du script\nun par ligne", "pt": "Argumentos do script\num por linha",
                        "es": "Argumentos del script\nuno por línea",
                        "ar": "وسائط السكربت\nواحدة في كل سطر"},
    "dlg.script.run": {"zh": "保存并运行", "en": "Save & run", "fr": "Enregistrer et exécuter",
                       "pt": "Salvar e executar", "es": "Guardar y ejecutar", "ar": "حفظ وتشغيل"},
    "dlg.script.err": {"zh": "请选择有效的 Python 测试脚本", "en": "Choose a valid Python test script",
                       "fr": "Choisissez un script de test Python valide",
                       "pt": "Escolha um script de teste Python válido",
                       "es": "Elija un script de prueba Python válido",
                       "ar": "اختر سكربت اختبار Python صالحًا"},
    "dlg.script.note": {"zh": "参数按脚本路径分别记忆，切换项目互不覆盖；底部“开始脚本测试”直接用当前参数运行。\n"
                             "串口和站号以脚本为准；运行时显示真实收发，结束确认后可手动测试。",
                        "en": "Arguments are remembered per script path and switching projects does not overwrite them; "
                              "\"Start script test\" at the bottom runs with the current arguments.\n"
                              "Serial port and station follow the script; real traffic is shown while running, "
                              "and manual testing is available after end confirmation.",
                        "fr": "Les arguments sont mémorisés par chemin de script ; changer de projet ne les écrase pas ; "
                              "« Lancer le test script » en bas utilise les arguments actuels.\n"
                              "Port série et station suivent le script ; le trafic réel est affiché pendant l'exécution, "
                              "et l'essai manuel est disponible après confirmation de fin.",
                        "pt": "Os argumentos são memorizados por caminho de script; trocar de projeto não os sobrescreve; "
                              "\"Iniciar teste de script\" na base executa com os argumentos atuais.\n"
                              "Porta serial e estação seguem o script; o tráfego real é exibido durante a execução "
                              "e o teste manual fica disponível após a confirmação de fim.",
                        "es": "Los argumentos se recuerdan por ruta de script; cambiar de proyecto no los sobrescribe; "
                              "\"Iniciar prueba de script\" en la base ejecuta con los argumentos actuales.\n"
                              "El puerto serial y la estación siguen el script; el tráfico real se muestra durante la ejecución "
                              "y la prueba manual está disponible tras confirmar el fin.",
                        "ar": "تُحفظ الوسائط لكل مسار سكربت على حدة، وتغيير المشروع لا يستبدلها؛ "
                              "\"بدء اختبار السكربت\" في الأسفل يشغّل بالوسائط الحالية.\n"
                              "المنفذ التسلسلي والمحطة يتبعان السكربت؛ يُعرض التبادل الفعلي أثناء التشغيل، "
                              "ويتاح الاختبار اليدوي بعد تأكيد الانتهاء."},

    # 调试记录对话框
    "dlg.records_title": {"zh": "最近30次调试记录", "en": "Last 30 sessions",
                          "fr": "30 dernières sessions", "pt": "Últimos 30 registros",
                          "es": "Últimos 30 registros", "ar": "آخر 30 جلسة"},
    "rec.col.id": {"zh": "会话ID", "en": "Session ID", "fr": "ID de session", "pt": "ID da sessão",
                   "es": "ID de sesión", "ar": "معرّف الجلسة"},
    "rec.col.started": {"zh": "开始", "en": "Started", "fr": "Début", "pt": "Início", "es": "Inicio",
                        "ar": "البداية"},
    "rec.col.ended": {"zh": "结束", "en": "Ended", "fr": "Fin", "pt": "Fim", "es": "Fin",
                      "ar": "النهاية"},
    "rec.col.status": {"zh": "状态", "en": "Status", "fr": "État", "pt": "Estado", "es": "Estado",
                       "ar": "الحالة"},
    "rec.col.reason": {"zh": "结束原因", "en": "End reason", "fr": "Motif de fin",
                       "pt": "Motivo do fim", "es": "Motivo de fin", "ar": "سبب الانتهاء"},
    "rec.note": {"zh": "自动保留最近 30 次已结束记录 + 当前进行中记录 · 目录：{path}",
                 "en": "Keeps the last 30 finished sessions plus the one in progress · folder: {path}",
                 "fr": "Conserve les 30 dernières sessions terminées plus celle en cours · dossier : {path}",
                 "pt": "Mantém as últimas 30 sessões concluídas mais a em andamento · pasta: {path}",
                 "es": "Conserva las últimas 30 sesiones finalizadas más la en curso · carpeta: {path}",
                 "ar": "يحتفظ بآخر 30 جلسة منتهية + الجلسة الجارية · المجلد: {path}"},
    "btn.detail": {"zh": "查看详情", "en": "View detail", "fr": "Détails", "pt": "Ver detalhes",
                   "es": "Ver detalle", "ar": "عرض التفاصيل"},
    "btn.export_selected": {"zh": "导出选中记录", "en": "Export selected", "fr": "Exporter la sélection",
                            "pt": "Exportar selecionado", "es": "Exportar seleccionado",
                            "ar": "تصدير المحدد"},
    "btn.refresh": {"zh": "刷新", "en": "Refresh", "fr": "Actualiser", "pt": "Atualizar",
                    "es": "Actualizar", "ar": "تحديث"},
    "rec.export_title": {"zh": "导出选中记录", "en": "Export selected session",
                         "fr": "Exporter la session sélectionnée", "pt": "Exportar sessão selecionada",
                         "es": "Exportar sesión seleccionada", "ar": "تصدير الجلسة المحددة"},

    # 记录详情对话框
    "dlg.detail_title": {"zh": "记录详情 · {id}", "en": "Session detail · {id}",
                         "fr": "Détail de la session · {id}", "pt": "Detalhe da sessão · {id}",
                         "es": "Detalle de la sesión · {id}", "ar": "تفاصيل الجلسة · {id}"},
    "det.col.seq": {"zh": "序号", "en": "Seq", "fr": "N°", "pt": "Nº", "es": "N.º", "ar": "الرقم"},
    "det.col.time": {"zh": "时间", "en": "Time", "fr": "Heure", "pt": "Hora", "es": "Hora",
                     "ar": "الوقت"},
    "det.col.object": {"zh": "操作对象", "en": "Object", "fr": "Objet", "pt": "Objeto",
                       "es": "Objeto", "ar": "العنصر"},
    "det.col.action": {"zh": "动作", "en": "Action", "fr": "Action", "pt": "Ação", "es": "Acción",
                       "ar": "الإجراء"},
    "det.col.value": {"zh": "目标 / 生效", "en": "Target / Effective", "fr": "Cible / Effective",
                      "pt": "Alvo / Efetivo", "es": "Objetivo / Efectivo", "ar": "الهدف / الفعلي"},
    "det.col.result": {"zh": "结果", "en": "Result", "fr": "Résultat", "pt": "Resultado",
                       "es": "Resultado", "ar": "النتيجة"},

    # ---- 引擎/存储数据词（仅显示层翻译；原值为持久化权威） ----
    # State（engine.State）
    "state.disconnected": {"zh": "未连接", "en": "Disconnected", "fr": "Non connecté",
                           "pt": "Desconectado", "es": "Sin conexión", "ar": "غير متصل"},
    "state.connecting": {"zh": "连接中", "en": "Connecting", "fr": "Connexion en cours",
                         "pt": "Conectando", "es": "Conectando", "ar": "جارٍ الاتصال"},
    "state.connected": {"zh": "已连接·未仿真", "en": "Connected · not simulating",
                        "fr": "Connecté · sans simulation", "pt": "Conectado · sem simulação",
                        "es": "Conectado · sin simulación", "ar": "متصل · بلا محاكاة"},
    "state.starting": {"zh": "仿真启动中", "en": "Starting", "fr": "Démarrage", "pt": "Iniciando",
                       "es": "Iniciando", "ar": "جارٍ البدء"},
    "state.simulating": {"zh": "仿真中", "en": "Simulating", "fr": "En simulation", "pt": "Simulando",
                         "es": "Simulando", "ar": "قيد المحاكاة"},
    "state.ending": {"zh": "结束中", "en": "Ending", "fr": "Fin en cours", "pt": "Encerrando",
                     "es": "Finalizando", "ar": "جارٍ الإنهاء"},
    "state.fault": {"zh": "故障/断线", "en": "Fault / offline", "fr": "Défaut / hors ligne",
                    "pt": "Falha / offline", "es": "Fallo / sin conexión", "ar": "عطل / انقطاع"},
    "state.script_running": {"zh": "脚本测试中", "en": "Script test running",
                             "fr": "Test de script en cours", "pt": "Teste de script em execução",
                             "es": "Prueba de script en ejecución", "ar": "اختبار السكربت قيد التشغيل"},
    "state.script_confirm": {"zh": "测试完毕·待确认", "en": "Finished · awaiting confirm",
                             "fr": "Terminé · confirmation en attente",
                             "pt": "Concluído · aguardando confirmação",
                             "es": "Finalizado · en espera de confirmación",
                             "ar": "انتهى · بانتظار التأكيد"},
    "state.manual": {"zh": "手动测试", "en": "Manual test", "fr": "Essai manuel", "pt": "Teste manual",
                     "es": "Prueba manual", "ar": "اختبار يدوي"},

    # 日志操作对象（固定词；D{n}/X{n}/AD{n}/脚本名等动态对象原样显示）
    "obj.connection": {"zh": "连接", "en": "Connection", "fr": "Connexion", "pt": "Conexão",
                       "es": "Conexión", "ar": "الاتصال"},
    "obj.comms": {"zh": "通讯", "en": "Communication", "fr": "Communication", "pt": "Comunicação",
                  "es": "Comunicación", "ar": "الاتصال التسلسلي"},
    "obj.start_simulation": {"zh": "开始仿真", "en": "Start simulation", "fr": "Démarrer la simulation",
                             "pt": "Iniciar simulação", "es": "Iniciar simulación", "ar": "بدء المحاكاة"},
    "obj.end_simulation": {"zh": "结束仿真", "en": "End simulation", "fr": "Fin de simulation",
                           "pt": "Encerrar simulação", "es": "Terminar simulación",
                           "ar": "إنهاء المحاكاة"},
    "obj.customer_registers": {"zh": "客户寄存器", "en": "Customer registers",
                               "fr": "Registres client", "pt": "Registradores do cliente",
                               "es": "Registros del cliente", "ar": "سجلات العميل"},
    "obj.apply_all": {"zh": "应用全部", "en": "Apply all", "fr": "Tout appliquer",
                      "pt": "Aplicar tudo", "es": "Aplicar todo", "ar": "تطبيق الكل"},
    "obj.reset_inputs": {"zh": "复位仿真输入", "en": "Reset inputs", "fr": "Réinitialiser",
                         "pt": "Zerar entradas", "es": "Reiniciar entradas", "ar": "تصفير المدخلات"},
    "obj.step": {"zh": "步长", "en": "Step", "fr": "Pas", "pt": "Passo", "es": "Paso",
                 "ar": "الخطوة"},
    "obj.x_mode": {"zh": "X交互模式", "en": "X interaction mode", "fr": "Mode d'interaction X",
                   "pt": "Modo de interação X", "es": "Modo de interacción X",
                   "ar": "نمط تفاعل X"},
    "obj.session": {"zh": "会话", "en": "Session", "fr": "Session", "pt": "Sessão", "es": "Sesión",
                    "ar": "الجلسة"},
    "obj.initial_inputs": {"zh": "初始输入组", "en": "Initial input group",
                           "fr": "Groupe d'entrées initial", "pt": "Grupo de entradas inicial",
                           "es": "Grupo de entradas inicial", "ar": "مجموعة المدخلات الأولية"},

    # 日志动作
    "act.read_version": {"zh": "读取程序版本", "en": "Read program version",
                         "fr": "Lecture de la version du programme", "pt": "Ler versão do programa",
                         "es": "Leer versión del programa", "ar": "قراءة إصدار البرنامج"},
    "act.connect_failed": {"zh": "连接失败", "en": "Connect failed", "fr": "Échec de connexion",
                           "pt": "Falha na conexão", "es": "Fallo de conexión", "ar": "فشل الاتصال"},
    "act.disconnect": {"zh": "断开", "en": "Disconnect", "fr": "Déconnexion", "pt": "Desconectar",
                       "es": "Desconectar", "ar": "قطع الاتصال"},
    "act.fault": {"zh": "故障", "en": "Fault", "fr": "Défaut", "pt": "Avaria", "es": "Avería",
                  "ar": "عطل"},
    "act.manual_takeover": {"zh": "确认后手动接管", "en": "Manual takeover confirmed",
                            "fr": "Prise en main manuelle confirmée",
                            "pt": "Assunção manual confirmada",
                            "es": "Toma de control manual confirmada",
                            "ar": "تم تأكيد الانتقال للتحكم اليدوي"},
    "act.session_start": {"zh": "会话启动", "en": "Session start", "fr": "Démarrage de session",
                          "pt": "Início de sessão", "es": "Inicio de sesión", "ar": "بدء الجلسة"},
    "act.session_request_pending": {"zh": "会话申请待发送", "en": "Session request pending",
                                    "fr": "Demande de session en attente d'envoi",
                                    "pt": "Solicitação de sessão aguardando envio",
                                    "es": "Solicitud de sesión pendiente de envío",
                                    "ar": "طلب الجلسة بانتظار الإرسال"},
    "act.send_session_request": {"zh": "发送会话申请", "en": "Send session request",
                                 "fr": "Envoi de la demande de session",
                                 "pt": "Enviar solicitação de sessão",
                                 "es": "Enviar solicitud de sesión", "ar": "إرسال طلب الجلسة"},
    "act.session_confirm": {"zh": "会话确认", "en": "Session confirm", "fr": "Confirmation de session",
                            "pt": "Confirmação de sessão", "es": "Confirmación de sesión",
                            "ar": "تأكيد الجلسة"},
    "act.add_watch": {"zh": "添加或更新寄存器监控", "en": "Add/update register watch",
                      "fr": "Ajout/mise à jour d'une surveillance",
                      "pt": "Adicionar/atualizar monitoração", "es": "Agregar/actualizar monitoreo",
                      "ar": "إضافة/تحديث مراقبة السجل"},
    "act.remove_watch": {"zh": "移除寄存器监控", "en": "Remove register watch",
                         "fr": "Suppression d'une surveillance", "pt": "Remover monitoração",
                         "es": "Quitar monitoreo", "ar": "إزالة مراقبة السجل"},
    "act.import_watch_csv": {"zh": "导入监控CSV", "en": "Import watch CSV",
                             "fr": "Import CSV des surveillances", "pt": "Importar CSV de monitorações",
                             "es": "Importar CSV de monitoreos", "ar": "استيراد CSV للمراقبة"},
    "act.export_watch_csv": {"zh": "导出监控CSV", "en": "Export watch CSV",
                             "fr": "Export CSV des surveillances", "pt": "Exportar CSV de monitorações",
                             "es": "Exportar CSV de monitoreos", "ar": "تصدير CSV للمراقبة"},
    "act.edit_pending": {"zh": "编辑待应用值", "en": "Edit pending value",
                         "fr": "Édition de la valeur en attente", "pt": "Editar valor pendente",
                         "es": "Editar valor pendiente", "ar": "تحرير القيمة المعلقة"},
    "act.edit_pending_release": {"zh": "编辑待应用值（松开）", "en": "Edit pending value (release)",
                                 "fr": "Édition de la valeur en attente (relâché)",
                                 "pt": "Editar valor pendente (soltar)",
                                 "es": "Editar valor pendiente (soltar)",
                                 "ar": "تحرير القيمة المعلقة (عند الترك)"},
    "act.commit_input": {"zh": "提交输入", "en": "Commit input", "fr": "Validation de l'entrée",
                         "pt": "Confirmar entrada", "es": "Confirmar entrada", "ar": "تأكيد الإدخال"},
    "act.release_input": {"zh": "松开输入", "en": "Release input", "fr": "Relâchement de l'entrée",
                          "pt": "Soltar entrada", "es": "Soltar entrada", "ar": "ترك الإدخال"},
    "act.numeric_input": {"zh": "数值输入", "en": "Numeric input", "fr": "Saisie numérique",
                          "pt": "Entrada numérica", "es": "Entrada numérica", "ar": "إدخال رقمي"},
    "act.reset_commit": {"zh": "复位提交", "en": "Reset commit", "fr": "Validation de la réinitialisation",
                         "pt": "Confirmar redefinição", "es": "Confirmar reinicio",
                         "ar": "تأكيد التصفير"},
    "act.group_commit": {"zh": "组提交", "en": "Group commit", "fr": "Validation de groupe",
                         "pt": "Confirmação em grupo", "es": "Confirmación en grupo",
                         "ar": "تأكيد المجموعة"},
    "act.adjust": {"zh": "调整", "en": "Adjust", "fr": "Ajustement", "pt": "Ajuste", "es": "Ajuste",
                   "ar": "تعديل"},
    "act.range_switch": {"zh": "量程切换", "en": "Range switch", "fr": "Changement de plage",
                         "pt": "Trocar faixa", "es": "Cambiar rango", "ar": "تغيير النطاق"},
    "act.switch": {"zh": "切换", "en": "Switch", "fr": "Changement", "pt": "Alterar",
                   "es": "Cambiar", "ar": "تبديل النمط"},
    "act.end_manual": {"zh": "结束手动测试", "en": "End manual test", "fr": "Fin de l'essai manuel",
                       "pt": "Encerrar teste manual", "es": "Terminar prueba manual",
                       "ar": "إنهاء الاختبار اليدوي"},
    "act.send_end_request": {"zh": "发送结束请求", "en": "Send end request",
                             "fr": "Envoi de la demande de fin", "pt": "Enviar solicitação de fim",
                             "es": "Enviar solicitud de fin", "ar": "إرسال طلب الإنهاء"},
    "act.end_confirm": {"zh": "结束确认", "en": "End confirm", "fr": "Confirmation de fin",
                        "pt": "Confirmação de fim", "es": "Confirmación de fin",
                        "ar": "تأكيد الإنهاء"},
    "act.end_cleanup": {"zh": "结束清理", "en": "End cleanup", "fr": "Nettoyage de fin",
                        "pt": "Limpeza de fim", "es": "Limpieza de fin", "ar": "تنظيف الإنهاء"},
    "act.end_request_before_disconnect": {"zh": "断开前结束请求",
                                          "en": "End request before disconnect",
                                          "fr": "Demande de fin avant déconnexion",
                                          "pt": "Solicitação de fim antes de desconectar",
                                          "es": "Solicitud de fin antes de desconectar",
                                          "ar": "طلب إنهاء قبل قطع الاتصال"},
    "act.start_test_script": {"zh": "启动测试脚本", "en": "Start test script",
                              "fr": "Lancement du script de test", "pt": "Iniciar script de teste",
                              "es": "Iniciar script de prueba", "ar": "تشغيل سكربت الاختبار"},
    "act.script_start_failed": {"zh": "脚本启动失败", "en": "Script start failed",
                                "fr": "Échec du lancement du script", "pt": "Falha ao iniciar o script",
                                "es": "Fallo al iniciar el script", "ar": "فشل تشغيل السكربت"},
    "act.script_connect": {"zh": "脚本连接", "en": "Script connect", "fr": "Connexion du script",
                           "pt": "Conexão do script", "es": "Conexión del script",
                           "ar": "اتصال السكربت"},
    "act.script_output": {"zh": "脚本输出", "en": "Script output", "fr": "Sortie du script",
                          "pt": "Saída do script", "es": "Salida del script", "ar": "مخرجات السكربت"},
    "act.raw_serial": {"zh": "原始串口收发", "en": "Raw serial TX/RX", "fr": "Trame série brute",
                       "pt": "Tráfego serial bruto", "es": "Tráfico serial en bruto",
                       "ar": "إرسال/استقبال تسلسلي خام"},
    "act.script_read": {"zh": "脚本读取", "en": "Script read", "fr": "Lecture du script",
                        "pt": "Leitura do script", "es": "Lectura del script", "ar": "قراءة السكربت"},
    "act.script_write": {"zh": "脚本写入", "en": "Script write", "fr": "Écriture du script",
                         "pt": "Escrita do script", "es": "Escritura del script",
                         "ar": "كتابة السكربت"},
    "act.script_test_finished": {"zh": "脚本测试结束", "en": "Script test finished",
                                 "fr": "Fin du test de script", "pt": "Fim do teste de script",
                                 "es": "Fin de la prueba de script", "ar": "انتهاء اختبار السكربت"},
    "act.script_cleanup_failed": {"zh": "脚本清理失败", "en": "Script cleanup failed",
                                  "fr": "Échec du nettoyage du script", "pt": "Falha na limpeza do script",
                                  "es": "Fallo en la limpieza del script", "ar": "فشل تنظيف السكربت"},
    "act.load_test_script": {"zh": "加载测试脚本", "en": "Load test script",
                             "fr": "Chargement du script de test", "pt": "Carregar script de teste",
                             "es": "Cargar script de prueba", "ar": "تحميل سكربت الاختبار"},
    "act.log_export": {"zh": "日志导出", "en": "Log export", "fr": "Export du journal",
                       "pt": "Exportação de registro", "es": "Exportación de registro",
                       "ar": "تصدير السجل"},

    # 日志结果
    "res.success": {"zh": "成功", "en": "Success", "fr": "Succès", "pt": "Sucesso", "es": "Éxito",
                    "ar": "نجاح"},
    "res.failed": {"zh": "失败", "en": "Failed", "fr": "Échec", "pt": "Falha", "es": "Fallo",
                   "ar": "فشل"},
    "res.sent": {"zh": "已发送", "en": "Sent", "fr": "Envoyé", "pt": "Enviado", "es": "Enviado",
                 "ar": "تم الإرسال"},
    "res.sent_no_readback": {"zh": "已发送（不读回）", "en": "Sent (no read-back)",
                             "fr": "Envoyé (sans relecture)", "pt": "Enviado (sem releitura)",
                             "es": "Enviado (sin relectura)", "ar": "تم الإرسال (بدون قراءة رجعية)"},
    "res.effective": {"zh": "已生效", "en": "Effective", "fr": "Effectif", "pt": "Efetivado",
                      "es": "Efectivo", "ar": "مفعّل"},
    "res.read_back": {"zh": "已读回", "en": "Read back", "fr": "Relu", "pt": "Relido",
                      "es": "Releído", "ar": "تمت القراءة الرجعية"},
    # 脚本测试日志：原始收发/读写的单步结果（script_bridge 产生）
    "res.logged": {"zh": "已记录", "en": "Logged", "fr": "Enregistré", "pt": "Registado",
                   "es": "Registrado", "ar": "مُسجَّل"},
    "res.script_read": {"zh": "读回", "en": "Read", "fr": "Lire", "pt": "Ler",
                        "es": "Leer", "ar": "تم القراءة"},
    "res.script_write_response": {"zh": "写入响应", "en": "Write resp.",
                                  "fr": "Rép. écriture", "pt": "Resp. escrita",
                                  "es": "Resp. escritura", "ar": "رد الكتابة"},
    "res.pending_send": {"zh": "待发送", "en": "Pending send", "fr": "En attente d'envoi",
                         "pt": "Aguardando envio", "es": "Pendiente de envío", "ar": "بانتظار الإرسال"},
    "res.pending_apply": {"zh": "待应用", "en": "Pending apply", "fr": "En attente d'application",
                          "pt": "Aguardando aplicação", "es": "Pendiente de aplicación",
                          "ar": "بانتظار التطبيق"},
    "res.not_sent": {"zh": "未发送", "en": "Not sent", "fr": "Non envoyé", "pt": "Não enviado",
                     "es": "No enviado", "ar": "لم يُرسل"},
    "res.unknown": {"zh": "结果未知", "en": "Result unknown", "fr": "Résultat inconnu",
                    "pt": "Resultado desconhecido", "es": "Resultado desconocido",
                    "ar": "نتيجة غير معروفة"},
    "res.write_rejected": {"zh": "写入拒绝", "en": "Write rejected", "fr": "Écriture refusée",
                           "pt": "Escrita recusada", "es": "Escritura rechazada",
                           "ar": "تم رفض الكتابة"},
    "res.clamped": {"zh": "钳位", "en": "Clamped", "fr": "Plafonné", "pt": "Limitado",
                    "es": "Limitado", "ar": "مقيد"},
    "res.running": {"zh": "运行中", "en": "Running", "fr": "En exécution", "pt": "Em execução",
                    "es": "En ejecución", "ar": "قيد التشغيل"},

    # 日志原因与结束原因
    "rsn.not_a_number": {"zh": "不是合法数字", "en": "Not a valid number", "fr": "Nombre invalide",
                         "pt": "Não é um número válido", "es": "No es un número válido",
                         "ar": "ليس رقمًا صالحًا"},
    "rsn.range_boundary": {"zh": "已达量程边界，保持当前值", "en": "Range limit reached; value kept",
                           "fr": "Limite de plage atteinte ; valeur conservée",
                           "pt": "Limite de faixa atingida; valor mantido",
                           "es": "Límite de rango alcanzado; valor mantenido",
                           "ar": "تم بلوغ حد النطاق؛ تم الاحتفاظ بالقيمة"},
    "rsn.manual_write_user_d": {"zh": "手动写入限用户 D 区",
                                "en": "Manual writes are limited to the user D area",
                                "fr": "Écriture manuelle limitée à la zone D utilisateur",
                                "pt": "Escrita manual limitada à área D do usuário",
                                "es": "La escritura manual se limita al área D del usuario",
                                "ar": "الكتابة اليدوية محدودة بمنطقة D للمستخدم"},
    "rsn.reconnect_required": {"zh": "故障/断线状态需先重连",
                               "en": "Fault state; reconnect first",
                               "fr": "État de défaut ; se reconnecter d'abord",
                               "pt": "Estado de falha; reconecte primeiro",
                               "es": "Estado de fallo; reconecte primero",
                               "ar": "حالة العطل؛ أعد الاتصال أولاً"},
    "rsn.unknown_mode": {"zh": "未知模式", "en": "Unknown mode", "fr": "Mode inconnu",
                         "pt": "Modo desconhecido", "es": "Modo desconocido", "ar": "نمط غير معروف"},
    "rsn.unknown_range": {"zh": "未知量程", "en": "Unknown range", "fr": "Plage inconnue",
                          "pt": "Faixa desconhecida", "es": "Rango desconocido",
                          "ar": "نطاق غير معروف"},
    "rsn.step_range": {"zh": "步长必须为 1–10%", "en": "Step must be 1–10%",
                       "fr": "Le pas doit être de 1 à 10 %", "pt": "O passo deve ser de 1–10%",
                       "es": "El paso debe ser de 1–10%", "ar": "يجب أن تكون الخطوة بين 1–10%"},
    "rsn.needs_input_mapping": {"zh": "该点位需要原测试工程的输入映射",
                                "en": "This point needs the input mapping from the original test project",
                                "fr": "Ce point nécessite le mappage d'entrée du projet de test d'origine",
                                "pt": "Este ponto requer o mapeamento de entrada do projeto de teste original",
                                "es": "Este punto requiere el mapeo de entrada del proyecto de prueba original",
                                "ar": "هذه النقطة تحتاج تعيين الإدخال من مشروع الاختبار الأصلي"},
    "rsn.empty_input": {"zh": "输入为空", "en": "Empty input", "fr": "Saisie vide",
                        "pt": "Entrada vazia", "es": "Entrada vacía", "ar": "إدخال فارغ"},
    "rsn.disconnected_by_user": {"zh": "用户断开", "en": "Disconnected by user",
                                 "fr": "Déconnecté par l'utilisateur", "pt": "Desconectado pelo usuário",
                                 "es": "Desconectado por el usuario", "ar": "تم الفصل بواسطة المستخدم"},
    "rsn.ended_by_user": {"zh": "用户结束", "en": "Ended by user", "fr": "Terminé par l'utilisateur",
                          "pt": "Encerrado pelo usuário", "es": "Finalizado por el usuario",
                          "ar": "تم الإنهاء بواسطة المستخدم"},
    "rsn.closed_by_window": {"zh": "关闭窗口结束", "en": "Ended by window close",
                             "fr": "Fermé par la fenêtre", "pt": "Encerrado pelo fechamento da janela",
                             "es": "Finalizado por cierre de ventana", "ar": "انتهى بإغلاق النافذة"},
    "rsn.log_fault": {"zh": "日志故障", "en": "Log failure", "fr": "Défaut de journal",
                      "pt": "Falha de registro", "es": "Fallo de registro", "ar": "عطل في السجل"},
    "rsn.end_not_confirmed": {"zh": "结束未确认", "en": "End not confirmed", "fr": "Fin non confirmée",
                              "pt": "Fim não confirmado", "es": "Fin no confirmado",
                              "ar": "لم يتم تأكيد الإنهاء"},
    "rsn.end_not_confirmed_outputs": {"zh": "结束未确认，不虚构输出已归零",
                                      "en": "End not confirmed; outputs-zeroed not fabricated",
                                      "fr": "Fin non confirmée ; zéro des sorties non affirmé",
                                      "pt": "Fim não confirmado; zeramento das saídas não afirmado",
                                      "es": "Fin no confirmado; no se afirma que las salidas estén en cero",
                                      "ar": "لم يتم تأكيد الإنهاء؛ لا يُدّعى تصفير المخرجات"},

    # 共享词（结果/动作/会话状态多语境复用）
    "word.rejected": {"zh": "拒绝", "en": "Rejected", "fr": "Refusé", "pt": "Recusado",
                      "es": "Rechazado", "ar": "مرفوض"},
    "word.start_failed": {"zh": "启动失败", "en": "Start failed", "fr": "Échec du démarrage",
                          "pt": "Falha ao iniciar", "es": "Fallo al iniciar", "ar": "فشل البدء"},
    "word.normal_end": {"zh": "正常结束", "en": "Normal end", "fr": "Fin normale", "pt": "Fim normal",
                        "es": "Fin normal", "ar": "نهاية طبيعية"},

    # 会话存储状态（正常结束/启动失败与上方原因词共用 key）
    "store.running": {"zh": "进行中", "en": "In progress", "fr": "En cours", "pt": "Em andamento",
                      "es": "En curso", "ar": "قيد التنفيذ"},
    "store.aborted": {"zh": "异常中断", "en": "Aborted", "fr": "Interrompu (anomalie)",
                      "pt": "Interrompido (anomalia)", "es": "Interrumpido (anomalía)",
                      "ar": "انقطاع غير طبيعي"},
    "store.aborted_unclosed": {"zh": "异常中断（程序未正常关闭该会话）",
                               "en": "Aborted (program did not close this session properly)",
                               "fr": "Interrompu (le programme n'a pas fermé correctement la session)",
                               "pt": "Interrompido (o programa não fechou a sessão corretamente)",
                               "es": "Interrumpido (el programa no cerró la sesión correctamente)",
                               "ar": "انقطاع غير طبيعي (لم يغلق البرنامج الجلسة بشكل صحيح)"},

    # X 交互模式（engine 比较值，显示层翻译；词形按 width=10 下拉框控制）
    "xmode.toggle": {"zh": "保持开关", "en": "Toggle", "fr": "Bascule", "pt": "Alternar",
                     "es": "Alternar", "ar": "تبديل"},
    "xmode.hold": {"zh": "按住有效", "en": "Hold", "fr": "Maintenu", "pt": "Segurar",
                   "es": "Mantener", "ar": "ضغط مستمر"},

    # 监控权限（engine 比较值，显示层翻译；缩写按 width=9 下拉框控制）
    "access.read": {"zh": "只读", "en": "RO", "fr": "Lecture", "pt": "Leitura",
                    "es": "Lectura", "ar": "قراءة"},
    "access.write": {"zh": "只写", "en": "WO", "fr": "Écriture", "pt": "Escrita",
                     "es": "Escritura", "ar": "كتابة"},
    "access.rw": {"zh": "读写", "en": "RW", "fr": "Lec/Écr", "pt": "Lei/Esc",
                  "es": "Lec/Esc", "ar": "قراءة/كتابة"},
}

# ---------------------------------------------------------------------------
# 数据词映射：引擎/存储中文原值（持久化权威） → STRINGS key。未收录的原值原样显示。
# ---------------------------------------------------------------------------
DATA_KEYS: dict[str, str] = {
    # State
    "未连接": "state.disconnected",
    "连接中": "state.connecting",
    "已连接·未仿真": "state.connected",
    "仿真启动中": "state.starting",
    "仿真中": "state.simulating",
    "结束中": "state.ending",
    "故障/断线": "state.fault",
    "脚本测试中": "state.script_running",
    "测试完毕·待确认": "state.script_confirm",
    "手动测试": "state.manual",
    # 日志操作对象
    "连接": "obj.connection",
    "通讯": "obj.comms",
    "开始仿真": "obj.start_simulation",
    "结束仿真": "obj.end_simulation",
    "客户寄存器": "obj.customer_registers",
    "应用全部": "obj.apply_all",
    "复位仿真输入": "obj.reset_inputs",
    "步长": "obj.step",
    "X交互模式": "obj.x_mode",
    "会话": "obj.session",
    "初始输入组": "obj.initial_inputs",
    # 日志动作
    "读取程序版本": "act.read_version",
    "连接失败": "act.connect_failed",
    "断开": "act.disconnect",
    "故障": "act.fault",
    "确认后手动接管": "act.manual_takeover",
    "会话启动": "act.session_start",
    "会话申请待发送": "act.session_request_pending",
    "发送会话申请": "act.send_session_request",
    "会话确认": "act.session_confirm",
    "添加或更新寄存器监控": "act.add_watch",
    "移除寄存器监控": "act.remove_watch",
    "导入监控CSV": "act.import_watch_csv",
    "导出监控CSV": "act.export_watch_csv",
    "编辑待应用值": "act.edit_pending",
    "编辑待应用值（松开）": "act.edit_pending_release",
    "提交输入": "act.commit_input",
    "松开输入": "act.release_input",
    "数值输入": "act.numeric_input",
    "复位提交": "act.reset_commit",
    "组提交": "act.group_commit",
    "调整": "act.adjust",
    "量程切换": "act.range_switch",
    "切换": "act.switch",
    "结束手动测试": "act.end_manual",
    "发送结束请求": "act.send_end_request",
    "结束确认": "act.end_confirm",
    "结束清理": "act.end_cleanup",
    "断开前结束请求": "act.end_request_before_disconnect",
    "启动测试脚本": "act.start_test_script",
    "脚本启动失败": "act.script_start_failed",
    "脚本连接": "act.script_connect",
    "脚本输出": "act.script_output",
    "原始串口收发": "act.raw_serial",
    "脚本读取": "act.script_read",
    "脚本写入": "act.script_write",
    "脚本测试结束": "act.script_test_finished",
    "脚本清理失败": "act.script_cleanup_failed",
    "加载测试脚本": "act.load_test_script",
    "日志导出": "act.log_export",
    # 日志结果
    "成功": "res.success",
    "失败": "res.failed",
    "拒绝": "word.rejected",
    "已发送": "res.sent",
    "已发送（不读回）": "res.sent_no_readback",
    "已生效": "res.effective",
    "已读回": "res.read_back",
    "已记录": "res.logged",
    "读回": "res.script_read",
    "写入响应": "res.script_write_response",
    "待发送": "res.pending_send",
    "待应用": "res.pending_apply",
    "未发送": "res.not_sent",
    "结果未知": "res.unknown",
    "写入拒绝": "res.write_rejected",
    "钳位": "res.clamped",
    "运行中": "res.running",
    # 原因 / 结束原因
    "不是合法数字": "rsn.not_a_number",
    "已达量程边界，保持当前值": "rsn.range_boundary",
    "手动写入限用户 D 区": "rsn.manual_write_user_d",
    "故障/断线状态需先重连": "rsn.reconnect_required",
    "未知模式": "rsn.unknown_mode",
    "未知量程": "rsn.unknown_range",
    "步长必须为 1–10%": "rsn.step_range",
    "用户断开": "rsn.disconnected_by_user",
    "结束未确认": "rsn.end_not_confirmed",
    "结束未确认，不虚构输出已归零": "rsn.end_not_confirmed_outputs",
    "该点位需要原测试工程的输入映射": "rsn.needs_input_mapping",
    "输入为空": "rsn.empty_input",
    "用户结束": "rsn.ended_by_user",
    "关闭窗口结束": "rsn.closed_by_window",
    "日志故障": "rsn.log_fault",
    # 会话存储状态（正常结束/启动失败与上方原因词共用 key）
    "进行中": "store.running",
    "正常结束": "word.normal_end",
    "异常中断": "store.aborted",
    "异常中断（程序未正常关闭该会话）": "store.aborted_unclosed",
    "启动失败": "word.start_failed",
    # X 交互模式 / 监控权限
    "保持开关": "xmode.toggle",
    "按住有效": "xmode.hold",
    "只读": "access.read",
    "只写": "access.write",
    "读写": "access.rw",
}

_reverse: dict[str, dict[str, str]] = {}


def _rebuild_reverse() -> None:
    _reverse.clear()
    for code in LANGUAGES:
        table: dict[str, str] = {}
        for canonical, key in DATA_KEYS.items():
            display = STRINGS.get(key, {}).get(code)
            if display:
                table.setdefault(display, canonical)
        _reverse[code] = table


def set_language(code: str) -> None:
    """切换当前界面语言；未知代码回退默认语言。"""
    global _language
    _language = code if code in LANGUAGES else DEFAULT_LANGUAGE
    if not _reverse:
        _rebuild_reverse()


def get_language() -> str:
    return _language


def ui_family() -> str:
    """当前语言的界面字体 family（YaHei 无阿拉伯字形，阿拉伯语切 Segoe UI）。"""
    return UI_FONT_FAMILIES.get(_language, UI_FONT_DEFAULT)


def t(key: str, **kwargs) -> str:
    """按 key 取当前语言文案；缺译文回退中文，缺 key 回退 key 本身。"""
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_language) or entry.get(DEFAULT_LANGUAGE)
    if text is None:
        return key
    return text.format(**kwargs) if kwargs else text


def tr(text: str | None) -> str:
    """把引擎/存储的中文原值映射为当前语言显示；未收录的原值原样返回。"""
    if text is None:
        return ""
    key = DATA_KEYS.get(text)
    return t(key) if key else text


def untr(text: str | None) -> str:
    """把当前语言的显示词映射回中文原值；未收录的原样返回（可能已是原值）。"""
    if text is None:
        return ""
    return _reverse.get(_language, {}).get(text, text)


def validate() -> list[str]:
    """校验字典完整性：每个 key 各语言齐全、非空、格式化占位符一致。"""
    problems: list[str] = []
    for key, entry in STRINGS.items():
        missing = [code for code in LANGUAGES if not entry.get(code)]
        if missing:
            problems.append(f"{key}: 缺少译文 {missing}")
        fields = []
        for code, text in entry.items():
            fields.append((code, {field for _, field, _, _ in string.Formatter().parse(text) if field}))
        if fields and any(f[1] != fields[0][1] for f in fields[1:]):
            problems.append(f"{key}: 各语言占位符不一致 {fields}")
    unknown = {key for key in DATA_KEYS.values() if key not in STRINGS}
    if unknown:
        problems.append(f"DATA_KEYS 指向不存在的 key: {sorted(unknown)}")
    return problems


# ---------------------------------------------------------------------------
# 引擎/存储/脚本抛出的错误与记录文案。
#
# 中文是权威原文：异常里抛的中文、落盘的 end_reason 都不改，只在显示边界用 msg()
# 翻译，所以旧记录、CSV、测试断言全部不受影响。
# 维护中英两套；其余语言回退英文（技术错误文案宁可给英文，也不做半成品直译）。
# ---------------------------------------------------------------------------
MESSAGES: dict[str, str] = {
    # ---- 连接与设置 ----
    "未选择串口": "No serial port selected",
    "从机地址必须为 1..247": "Station must be 1..247",
    "从机地址必须为 1..247（不使用广播 0，不改写 PLC 站号）":
        "Station must be 1..247 (no broadcast 0; the PLC station is never rewritten)",
    "连接期间设置锁定；请先断开再修改": "Settings are locked while connected; disconnect first",
    "版本寄存器必须是 D0–D8511 内的整数编号": "Version register must be an integer D0–D8511",
    "版本寄存器未设置：须填写目标程序实际维护的版本地址":
        "Version register not set: enter the address the target program maintains",
    "实机连接需要安装 pyserial": "pyserial is required for real hardware",
    "串口未打开": "Serial port is not open",
    # ---- 接口档案 ----
    "接口档案必须是 JSON 对象": "Interface profile must be a JSON object",
    "接口档案不完整或校验失败，禁止注入": "Profile is incomplete or invalid; injection is refused",
    "接口档案未经用户确认（confirmed=false），实机禁止写入":
        "Profile not confirmed (confirmed=false); live writes are blocked",
    "接口档案未确认，实机写入被禁止": "Profile not confirmed; live writes are blocked",
    "实机会话地址须在 D0–D7999 用户区": "Live session registers must be in the D0–D7999 user area",
    "版本地址与会话接口重叠": "Version register overlaps the session interface",
    "实机档案须在 build_identity 中提供预期版本及独立构建标识":
        "A live profile must declare the expected version and build id in build_identity",
    "build_identity 须为零基 D 编号和预期整数值的对象":
        "build_identity must map zero-based D numbers to expected integers",
    "confirmed 必须为布尔值": "confirmed must be a boolean",
    "customer_registers 须为列表": "customer_registers must be a list",
    "客户寄存器须填写 address、minimum、maximum，可选 signed":
        "Each customer register needs address, minimum and maximum (signed optional)",
    "客户可写地址须在 D0–D7999": "Writable customer registers must be in D0–D7999",
    "signed 必须为布尔值": "signed must be a boolean",
    "演示模式必须注入回环传输层": "Demo mode needs an injected loopback transport",
    # ---- 仿真会话 ----
    "PLC 存活计数未变化": "PLC liveness counter did not change",
    "PLC 程序版本已变化，请重新连接": "PLC program version changed; reconnect",
    "PLC 仿真会话已变化，请重新连接": "PLC simulation session changed; reconnect",
    "故障/断线状态需先重连": "Fault/disconnected: reconnect first",
    "故障/断线状态需先重连再开始新会话":
        "Fault/disconnected: reconnect before starting a new session",
    "仿真已在进行或启动中，不能重复启动":
        "A simulation is already running or starting; cannot start again",
    "该点位需要原测试工程的输入映射":
        "This point needs the original test project's input mapping",
    "脚本输入地址超出用户区或与版本地址重叠":
        "Script input address is outside the user area or overlaps the version register",
    "手动写入限用户 D 区": "Manual writes are limited to the user D area",
    "手动接管前需释放脚本连接": "Release the script connection before manual takeover",
    "请在当前仿真会话就绪后发送": "Send once the current simulation session is ready",
    "请输入整数寄存器值": "Enter an integer register value",
    "请选择已添加监控的寄存器": "Select a register that is already being watched",
    "该寄存器权限为只读，不能发送": "This register is read-only and cannot be sent",
    "该地址是观察/接口保护寄存器，禁止经客户通道写入":
        "This is an observation/interface register; the customer channel cannot write it",
    "输入为空": "Input is empty",
    "不是合法数字": "Not a valid number",
    "已达量程边界，保持当前值": "Range boundary reached; value unchanged",
    "步长必须为 1–10%": "Step must be 1–10%",
    "步长必须为 1–10 的整数百分比": "Step must be an integer percentage from 1–10",
    "未知量程": "Unknown range",
    "未知模式": "Unknown mode",
    "X 通道编号必须为 0..7": "X channel index must be 0..7",
    "AD 通道编号必须为 0..3": "AD channel index must be 0..3",
    "权限必须为 只读 / 只写 / 读写": "Access must be RO / WO / RW",
    "寄存器名称最多 40 个字符": "Register name is limited to 40 characters",
    "结束未确认": "End not confirmed",
    "结束未确认，不虚构输出已归零": "End not confirmed; outputs are not assumed to be zero",
    "结束未确认：已释放串口，请核对 PLC 状态后重连":
        "End not confirmed: port released; verify the PLC state before reconnecting",
    "通讯故障": "Communication fault",
    "手动连接失败": "Manual connection failed",
    "正常结束": "Normal end",
    # ---- 协议层 ----
    "FC06 回显不符": "FC06 echo mismatch",
    "FC16 回显不符": "FC16 echo mismatch",
    "响应 CRC 校验失败": "Response CRC check failed",
    "响应功能码不符": "Response function code mismatch",
    "异常响应功能码不符": "Exception response function code mismatch",
    "响应字节数不符": "Response byte count mismatch",
    "读位功能码必须为 1 或 2": "Bit read function must be 1 or 2",
    "位读数量必须为 1..2000": "Bit read count must be 1..2000",
    "字读数量必须为 1..125": "Register read count must be 1..125",
    "多字写数量必须为 1..123": "Multi-register write count must be 1..123",
    "写入值必须为 0..65535": "Written value must be 0..65535",
    "虚拟设备无响应（静默丢帧）": "Virtual device did not respond (frame dropped silently)",
    # ---- 绘制内存 / 脚本 ----
    "会话附件需要有效记录和单一文件名":
        "Session attachment needs an active record and one filename",
    "脚本输出线程未退出，禁止手动接管":
        "Script output thread has not exited; manual takeover is refused",
    "脚本及其子进程仍未释放": "Script and its child processes are still running",
    "请选择 Python .py 测试脚本": "Choose a Python .py test script",
    "请先确认本次测试结束": "Confirm that the current test has ended first",
    "脚本执行结束": "Script finished",
    "用户关闭脚本测试": "Script test closed by the user",
    "演示模式禁止打开物理串口": "Demo mode must not open a physical serial port",
    "演示模式请选择内置脚本或使用 LoopbackTransport 的脚本":
        "In demo mode choose a built-in script, or one using LoopbackTransport",
    "演示脚本仅允许回环通讯，请切换实机模式执行硬件脚本":
        "Demo scripts may only use loopback; switch to live mode for hardware scripts",
    "压力工程源文件已变化，请更新脚本接管映射后再运行":
        "Pressure project source changed; update the script mapping before running",
}

def _message_arg(text: str) -> str:
    """模板里的内嵌词（状态、嵌套报错）：统一取英文，避免英文句子里混一个他语状态词。"""
    key = DATA_KEYS.get(text)
    if key:
        return STRINGS[key].get("en") or text
    return MESSAGES.get(text, text)


# 带参数的文案：(正则, 渲染函数)。分组里的内嵌词先经 _message_arg() 统一成英文。
MESSAGE_PATTERNS: tuple = (
    (re.compile(r"当前状态 (.+) 不允许连接"),
     lambda m: f"State {_message_arg(m.group(1))} does not allow connecting"),
    (re.compile(r"当前状态 (.+) 不允许输入"),
     lambda m: f"State {_message_arg(m.group(1))} does not allow input"),
    (re.compile(r"当前状态 (.+) 不允许提交"),
     lambda m: f"State {_message_arg(m.group(1))} does not allow committing"),
    (re.compile(r"当前状态 (.+) 不允许复位"),
     lambda m: f"State {_message_arg(m.group(1))} does not allow resetting"),
    (re.compile(r"当前状态 (.+)，不能重复启动"),
     lambda m: f"State {_message_arg(m.group(1))}: cannot start again"),
    (re.compile(r"当前状态 (.+)，无可结束的仿真"),
     lambda m: f"State {_message_arg(m.group(1))}: no simulation to end"),
    (re.compile(r"当前状态 (.+)，仅本机记录不发送"),
     lambda m: f"State {_message_arg(m.group(1))}: recorded locally only, nothing sent"),
    (re.compile(r"允许范围 (.+)–(.+)"),
     lambda m: f"Allowed range {m.group(1)}–{m.group(2)}"),
    (re.compile(r"组 (\d+) 未收到消费确认"),
     lambda m: f"Group {m.group(1)} was not consumption-confirmed"),
    (re.compile(r"组 (\d+) 生效镜像与目标不一致"),
     lambda m: f"Group {m.group(1)} effective mirror does not match the target"),
    (re.compile(r"上一组（序号 ([^）]+)）尚未确认"),
     lambda m: f"Previous group ({m.group(1)}) is still unconfirmed"),
    (re.compile(r"会话 (.+) 不存在"), lambda m: f"Session {m.group(1)} does not exist"),
    (re.compile(r"(\d+)s 内未收到结束确认"),
     lambda m: f"No end confirmation within {m.group(1)}s"),
    (re.compile(r"最多监控 (\d+) 个寄存器"),
     lambda m: f"At most {m.group(1)} registers can be watched"),
    (re.compile(r"监控地址须在 D0–D(\d+)"), lambda m: f"Watch address must be within D0–D{m.group(1)}"),
    (re.compile(r"版本寄存器: (.+)"), lambda m: f"Version register: {_message_arg(m.group(1))}"),
    (re.compile(r"连接失败: (.+)"), lambda m: f"Connection failed: {_message_arg(m.group(1))}"),
    (re.compile(r"启动失败: (.+)"), lambda m: f"Start failed: {_message_arg(m.group(1))}"),
    (re.compile(r"通讯失败: (.+)"), lambda m: f"Communication failed: {_message_arg(m.group(1))}"),
    (re.compile(r"串口通讯失败: (.+)"), lambda m: f"Serial communication failed: {_message_arg(m.group(1))}"),
    (re.compile(r"心跳发送失败: (.+)"), lambda m: f"Heartbeat send failed: {_message_arg(m.group(1))}"),
    (re.compile(r"组提交失败: (.+)"), lambda m: f"Group commit failed: {_message_arg(m.group(1))}"),
    (re.compile(r"结束过程通讯失败: (.+)"),
     lambda m: f"Communication failed while ending: {_message_arg(m.group(1))}"),
    (re.compile(r"日志故障: (.+)"), lambda m: f"Logging fault: {_message_arg(m.group(1))}"),
    (re.compile(r"断开结束（(.+)）"), lambda m: f"Disconnect: {_message_arg(m.group(1))}"),
    (re.compile(r"PLC 会话已失效（状态码 (\d+)）"),
     lambda m: f"PLC session is invalid (state code {m.group(1)})"),
    (re.compile(r"不支持的数据格式: (.+)（首版 RTU 仅 8 数据位）"),
     lambda m: f"Unsupported data format: {m.group(1)} (RTU is 8 data bits only)"),
    (re.compile(r"不支持的波特率: (.+)"), lambda m: f"Unsupported baud rate: {m.group(1)}"),
    (re.compile(r"未知量程类型: (.+)"), lambda m: f"Unknown range type: {m.group(1)}"),
    (re.compile(r"未知记录类型: (.+)"), lambda m: f"Unknown record type: {m.group(1)}"),
    (re.compile(r"数值 (.+) 超出量程 (.+)"),
     lambda m: f"Value {m.group(1)} is outside {_message_arg(m.group(2))}"),
    (re.compile(r"未知响应功能码 (0x[0-9A-Fa-f]+)"),
     lambda m: f"Unknown response function code {m.group(1)}"),
    (re.compile(r"响应站号 (\d+) 与请求 (\d+) 不符"),
     lambda m: f"Response station {m.group(1)} does not match request {m.group(2)}"),
    (re.compile(r"响应不完整: 期望 (\d+) 字节, 收到 (\d+) 字节"),
     lambda m: f"Incomplete response: expected {m.group(1)} bytes, got {m.group(2)}"),
    (re.compile(r"响应不完整: 期望 (\d+) 字节, 缓冲 (\d+) 字节"),
     lambda m: f"Incomplete response: expected {m.group(1)} bytes, buffered {m.group(2)}"),
    (re.compile(r"数据长度 (\d+) 与请求数 (\d+) 不符"),
     lambda m: f"Data length {m.group(1)} does not match the requested {m.group(2)}"),
    (re.compile(r"D(\d+) 不允许作为仿真写入地址"),
     lambda m: f"D{m.group(1)} cannot be used as a simulation write address"),
    (re.compile(r"D(\d+) 构建标识与接口档案不符"),
     lambda m: f"Build id at D{m.group(1)} does not match the profile"),
    (re.compile(r"D(\d+) 写入范围无效"), lambda m: f"Invalid write range for D{m.group(1)}"),
    (re.compile(r"地址 D(\d+) 不在接口档案写白名单内，拒绝写入"),
     lambda m: f"D{m.group(1)} is not in the profile write whitelist; write refused"),
    (re.compile(r"档案地址 D(\d+) 超出 D0–D(\d+) 范围"),
     lambda m: f"Profile address D{m.group(1)} is outside D0–D{m.group(2)}"),
    (re.compile(r"档案字段 (\S+) 必须为非空字符串"),
     lambda m: f"Profile field {m.group(1)} must be a non-empty string"),
    (re.compile(r"档案字段 (\S+) 必须为整数列表"),
     lambda m: f"Profile field {m.group(1)} must be a list of integers"),
    (re.compile(r"档案字段 (\S+) 必须为整数或 null"),
     lambda m: f"Profile field {m.group(1)} must be an integer or null"),
    (re.compile(r"接口档案不是有效 JSON: (.+)"),
     lambda m: f"Profile is not valid JSON: {_message_arg(m.group(1))}"),
    (re.compile(r"接口档案存在未知字段: (.+)"),
     lambda m: f"Profile has unknown fields: {m.group(1)}"),
    (re.compile(r"无法读取接口档案 (.+): (.+)"),
     lambda m: f"Cannot read profile {m.group(1)}: {_message_arg(m.group(2))}"),
    (re.compile(r"无法为 (.+) 生成不重复文件名"),
     lambda m: f"Cannot generate a unique filename for {m.group(1)}"),
)


def msg(text: str | None) -> str:
    """显示引擎/存储抛出的文案：数据词 → 词条 → 模板 → 原样。

    中文界面直接返回原文（中文即权威）；其他语言无译文时依次回退英文、原文，
    保证技术报错至少可读，不会出现半句翻译。
    """
    if text is None:
        return ""
    if not text or _language == "zh":
        return text
    key = DATA_KEYS.get(text)
    if key:
        return t(key)
    translation = MESSAGES.get(text)
    if translation:
        return translation
    for pattern, render in MESSAGE_PATTERNS:
        match = pattern.fullmatch(text)
        if match:
            return render(match)
    return text


set_language(DEFAULT_LANGUAGE)
