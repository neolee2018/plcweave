"""Generate the offline copy page from the documented prompt; no customer assets."""
from pathlib import Path
import html
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = (ROOT / "docs/DVP-CONVERSION.md").read_text(encoding="utf-8")
    prompts = re.findall(r"^```text\n(.*?)\n```", source, re.M | re.S)
    if len(prompts) != 1:
        raise ValueError("Expected exactly one prompt block")
    page = '''<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>指令表转 DVP · AI 转换提示词</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#172b40;font:16px/1.7 'Segoe UI','Microsoft YaHei',sans-serif}
main{max-width:1000px;margin:40px auto;padding:32px;background:white;border:1px solid #dbe4ed;border-radius:16px}
.brand{font-size:14px;color:#005ca1;font-weight:700;letter-spacing:1px}h1{font-size:30px;line-height:1.35;margin:12px 0}
.intro{color:#40566b}.steps{padding-left:24px}.note{background:#edf4fa;padding:16px;border-left:4px solid #005ca1}
.toolbar{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:24px 0 12px}
button{border:0;border-radius:7px;padding:12px 22px;background:#005ca1;color:white;cursor:pointer;font:inherit;font-weight:600}
button:hover{background:#004879}button:focus-visible,textarea:focus-visible{outline:3px solid #f26520;outline-offset:3px}
textarea{display:block;width:100%;height:440px;resize:vertical;border:1px solid #aebfce;border-radius:8px;padding:18px;font:14px/1.8 Consolas,'Microsoft YaHei',monospace;color:#172b40;background:#fcfdff}
label{display:block;font-weight:600;margin-bottom:8px}#status{color:#314c64}a{color:#005ca1}.footer{font-size:14px;color:#536a7d}
@media(max-width:640px){main{margin:0;padding:24px 18px;border-radius:0}h1{font-size:25px}textarea{height:400px}.toolbar{align-items:flex-start;flex-direction:column}}
</style>
<main>
<div class="brand">PLCWeave · 控程工坊</div>
<h1>把指令表交给 AI，转换为 DVP 工程</h1>
<p class="intro">复制下面的提示词，与指令表一起发给已打开本仓库的 Codex 或类似 AI Agent。提示词要求 AI 先查看已有 DVP 模板，再检查并转换程序。</p>
<ol class="steps"><li>点击“复制转换提示词”。</li><li>粘贴给 AI，附上指令表、PLC 完整型号、厂家软件版本和客户项目路径。</li><li>取得工程候选后，在匹配机型的 WPLSoft 中打开、编译并核对。</li></ol>
<p class="note">请让 AI 能够读取本机项目。已有模板属于本机项目资料，公开克隆可能不包含。现有 ES2 转换器仅覆盖成对 LD X / OUT Y 与末尾 END；其他程序需要另行核实支持。生成文件与厂家编译、实机验证分别记录。</p>
<div class="toolbar"><button id="copy" type="button">复制转换提示词</button><span id="status" role="status" aria-live="polite">复制后，再附上你的指令表程序。</span></div>
<label for="prompt">完整提示词（可查看、全选复制）</label>
<textarea id="prompt" readonly spellcheck="false">__PROMPT__</textarea>
<p class="footer">本页离线运行，不上传内容，不连接 PLC。<a href="../../docs/DVP-CONVERSION.md">查看转换说明与模板路径</a> · <a href="../../README.zh-CN.md">返回项目说明</a></p>
</main>
<script>
const prompt = document.getElementById('prompt');
const button = document.getElementById('copy');
const status = document.getElementById('status');
button.addEventListener('click', async () => {
  let copied = false;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(prompt.value);
      copied = true;
    }
  } catch (_) { /* Local browser policies may require the selection fallback. */ }
  if (!copied) {
    prompt.focus(); prompt.select();
    try { copied = document.execCommand('copy'); } catch (_) {}
  }
  button.textContent = copied ? '已复制提示词' : '重新复制提示词';
  status.textContent = copied
    ? '已复制。请粘贴给 AI，并附上指令表、PLC 型号和软件版本。'
    : '自动复制未成功。提示词已选中，请按 Ctrl+C（Mac：⌘C）复制。';
});
</script>
</html>
'''
    target = ROOT / "hmi/prototype/dvp-prompt.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page.replace("__PROMPT__", html.escape(prompts[0])), encoding="utf-8", newline="\n")
    print(target)


if __name__ == "__main__":
    main()
