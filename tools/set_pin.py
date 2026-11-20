#!/usr/bin/env python3
"""index.html 의 잠금 화면 PIN 해시를 심는다.

    python3 tools/set_pin.py 1234          # PIN 4~8자리 숫자로 해시를 새로 심는다
    python3 tools/set_pin.py --check 1234  # 지금 심긴 해시가 그 PIN 과 맞는지 확인만 한다
    python3 tools/set_pin.py --show        # 심긴 해시 앞 12자리만 보여 준다

· PIN 원문은 어디에도 저장하지 않는다 — SHA-256(고정 salt + PIN) 해시만 index.html 에 들어간다.
· salt 는 index.html 의 LOCK_SALT 와 같아야 한다(바꾸면 기존 토큰이 모두 무효가 된다).
"""
import hashlib
import pathlib
import re
import sys

SALT = 'teambusan|lock|v1|'
INDEX = pathlib.Path(__file__).resolve().parent.parent / 'index.html'
PATTERN = re.compile(r"const LOCK_HASH='([0-9a-f]{64})';")


def digest(pin: str) -> str:
    return hashlib.sha256((SALT + pin).encode('utf-8')).hexdigest()


def current() -> str:
    m = PATTERN.search(INDEX.read_text(encoding='utf-8'))
    if not m:
        sys.exit('index.html 에서 LOCK_HASH 를 찾지 못했습니다.')
    return m.group(1)


def main(argv):
    if len(argv) == 2 and argv[1] == '--show':
        h = current()
        print('LOCK_HASH =', h[:12] + '…' + h[-6:], '(placeholder)' if h == '0' * 64 else '')
        return 0
    if len(argv) == 3 and argv[1] == '--check':
        ok = digest(argv[2].strip()) == current()
        print('MATCH' if ok else 'MISMATCH')
        return 0 if ok else 1
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    pin = argv[1].strip()
    if not re.fullmatch(r'\d{4,8}', pin):
        sys.exit('PIN 은 숫자 4~8자리로 정해 주세요.')
    h = digest(pin)
    src = INDEX.read_text(encoding='utf-8')
    new, n = PATTERN.subn("const LOCK_HASH='%s';" % h, src)
    if n != 1:
        sys.exit('LOCK_HASH 를 %d곳에서 찾았습니다 — 1곳이어야 합니다.' % n)
    INDEX.write_text(new, encoding='utf-8')
    print('PIN 해시를 심었습니다 — LOCK_HASH =', h[:12] + '…' + h[-6:])
    print('이제 브라우저에서 PIN %s 로 열리는지 확인하고 sw.js 캐시 버전을 올려 배포하세요.' % ('·' * len(pin)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
