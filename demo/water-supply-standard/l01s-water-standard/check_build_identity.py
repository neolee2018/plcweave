"""Bind the source file to its canonical, non-self-referential identity words.

This S2 build tool stores fingerprint words with vendor-tool-safe constants:
K decimal constants must stay within ±32767, so a word whose unsigned form
exceeds 32767 is delivered as MUL K<a> K<b> with a*b == word and a,b within
range (found by small-factor search). Prime words without such a split fail
closed with a clear error. Independent S3 must recompute without importing
this module.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

PROGRAM_VERSION = 6
EDITION = 31
SUITE_VERSION_WORD = 6
import struct

ROOT = Path(__file__).resolve().parent


def canonicalize(source):
    lines = source.splitlines()
    if lines.count('#instructions') != 1 or lines.count('#comments') != 1:
        raise ValueError('Exactly one instructions/comments section required')
    start, stop = lines.index('#instructions'), lines.index('#comments')
    if start >= stop:
        raise ValueError('Invalid section order')
    region = lines[start + 1:stop]
    begin, end = '// BEGIN_IDENTITY', '// END_IDENTITY'
    if region.count(begin) != 1 or region.count(end) != 1:
        raise ValueError('Exactly one identity marker pair required')
    a, b = region.index(begin), region.index(end)
    if a >= b:
        raise ValueError('Invalid identity marker order')
    identity = [' '.join(line.split('//', 1)[0].upper().split())
                for line in region[a + 1:b] if line.split('//', 1)[0].strip()]
    expected = ['LD M8002', f'MOV K{PROGRAM_VERSION} D300', f'MOV K{EDITION} D301',
                r'(MOV K\d+|MUL K\d+ K\d+) D302',
                r'(MOV K\d+|MUL K\d+ K\d+) D303',
                f'MOV K{SUITE_VERSION_WORD} D304']
    if len(identity) != 6 or any(not re.fullmatch(p, x) for p, x in zip(expected, identity)):
        raise ValueError('Excluded block must contain only the six identity initialization instructions')
    canonical = []
    for line in region[:a] + region[b + 1:]:
        code = line.split('//', 1)[0]
        if code.strip():
            if code.lstrip().startswith('#'):
                raise ValueError('Unexpected section/comment syntax in instructions')
            canonical.append(' '.join(code.upper().split()))
    return ('\n'.join(canonical) + '\n').encode('utf-8')


def calculate(path):
    raw = path.read_bytes()
    canonical = canonicalize(raw.decode('utf-8-sig'))
    digest = hashlib.sha256(canonical).digest()
    return dict(source_sha256=hashlib.sha256(raw).hexdigest(),
                program_version=PROGRAM_VERSION, edition=EDITION,
                suite_version_word=SUITE_VERSION_WORD,
                fingerprint_words=list(struct.unpack('<hh', digest[:4])),
                canonical_sha256=digest.hex())


def split_word(word):
    """word(0..65535) → (a, b) with a*b == word and a,b ≤ 32767, else None."""
    if word <= 32767:
        return word, 1
    k = max(2, (word + 32766) // 32767)
    while k * k <= word:
        if word % k == 0 and word // k <= 32767:
            return k, word // k
        k += 1
    return None


def word_row(word, address):
    """指纹字 → 厂家工具可导入的指令行（K 十进制在 ±32767 内，超范围用 MUL 拆分）。"""
    split = split_word(word & 0xFFFF)
    if split is None:
        raise ValueError(f'D{address} 指纹字 {word & 0xFFFF} 无可用小因子拆分（素数或因子超范围），请调整规范后重建')
    a, b = split
    if b == 1:
        return f'MOV K{a} D{address}'
    return f'MUL K{a} K{b} D{address}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Refresh identity constants and manifest')
    args = parser.parse_args()
    path = ROOT / 'source.fxil'
    if args.write:
        result = calculate(path)
        source = path.read_text(encoding='utf-8-sig')
        rows = [word_row(result['fingerprint_words'][0], 302),
                word_row(result['fingerprint_words'][1], 303)]
        source, c1 = re.subn(rf'(?m)^(MOV K\d+|MUL K\d+ K\d+) D302$', rows[0], source)
        source, c2 = re.subn(rf'(?m)^(MOV K\d+|MUL K\d+ K\d+) D303$', rows[1], source)
        if c1 != 1 or c2 != 1:
            raise ValueError('Identity fingerprint instructions not found for update')
        path.write_text(source, encoding='utf-8', newline='\n')
        result = calculate(path)
        manifest = json.dumps(result, indent=2) + '\n'
        (ROOT / 'build_identity.json').write_text(manifest, encoding='utf-8')
    else:
        result = calculate(path)
        expected = json.loads((ROOT / 'build_identity.json').read_text(encoding='utf-8'))
        if result != expected:
            raise ValueError('Build manifest differs from current source')
        source = path.read_text(encoding='utf-8-sig')
        for address, word in zip((302, 303), result['fingerprint_words']):
            row = word_row(word, address)
            if len(re.findall(rf'(?m)^{re.escape(row)}$', source)) != 1:
                raise ValueError(f'Identity instruction differs for D{address}: {row}')
    print(json.dumps(dict(status='PASS', **result), indent=2))


if __name__ == '__main__':
    main()
