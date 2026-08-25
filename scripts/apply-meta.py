#!/usr/bin/env python3
"""새 캔버스 번들을 받아 정적 셸의 메타 태그를 다시 붙인다.

Claude Design 캔버스에서 export할 때마다 index.html 1~25행의 정적 셸이
통째로 재생성되면서 OG/트위터 메타가 사라진다. 이 스크립트가 그걸 되돌린다.
크롤러는 JS를 실행하지 않으므로 메타는 반드시 정적 셸에 있어야 한다.

    python3 scripts/apply-meta.py ~/Desktop/index.html   # 새 export를 복사 후 적용
    python3 scripts/apply-meta.py                        # 현재 index.html에 적용

두 번 실행해도 안전하다(이미 붙어 있으면 건너뜀).
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "index.html"
BASE = "https://chesunrry.github.io/"
THUMB = "cherry-thumb.png"
TITLE = "chesunrry"
DESC = "LEE SUNAH — 웹 · 그래픽 디자이너"

META = f"""  <link rel="icon" type="image/png" href="/{THUMB}">
  <link rel="apple-touch-icon" href="/{THUMB}">
  <meta name="description" content="{DESC}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{BASE}">
  <meta property="og:site_name" content="{TITLE}">
  <meta property="og:title" content="{TITLE}">
  <meta property="og:description" content="{DESC}">
  <meta property="og:image" content="{BASE}{THUMB}">
  <meta property="og:image:width" content="308">
  <meta property="og:image:height" content="310">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{TITLE}">
  <meta name="twitter:description" content="{DESC}">
  <meta name="twitter:image" content="{BASE}{THUMB}">"""

SHELL_LINES = 25  # 정적 셸 범위. 그 뒤는 번들러 런타임이라 건드리지 않는다.


def die(msg):
    sys.exit(f"apply-meta: {msg}")


def template_index(lines):
    """뒤쪽 __bundler/template 스크립트 태그 다음 줄(= JSON 문자열)의 인덱스."""
    hits = [n for n, l in enumerate(lines) if "__bundler/template" in l and n > 300]
    if not hits:
        die("__bundler/template 줄을 찾지 못했습니다. 번들 형식이 바뀌었는지 확인하세요.")
    return hits[-1] + 1


def main():
    if len(sys.argv) > 2:
        die(f"인자가 너무 많습니다.\n{__doc__}")

    if len(sys.argv) == 2:
        src = Path(sys.argv[1]).expanduser()
        if not src.is_file():
            die(f"{src} 파일이 없습니다.")
        if src.resolve() != TARGET.resolve():
            shutil.copyfile(src, TARGET)
            print(f"복사: {src} -> {TARGET}")

    lines = TARGET.read_text(encoding="utf-8").split("\n")

    # 번들 형식 검증: 네 개의 페이로드가 모두 파싱되어야 한다.
    for name in ("manifest", "template", "page_order", "ext_resources"):
        hits = [n for n, l in enumerate(lines) if f"__bundler/{name}" in l and n > 300]
        if not hits:
            die(f"__bundler/{name} 줄이 없습니다.")
        try:
            json.loads(lines[hits[-1] + 1])
        except json.JSONDecodeError as e:
            die(f"__bundler/{name} 페이로드가 깨졌습니다: {e}")

    # 1) 정적 셸에 메타 삽입 (이미 있으면 건너뜀)
    shell = "\n".join(lines[:SHELL_LINES])
    if "og:image" in shell:
        print("건너뜀: 정적 셸에 메타가 이미 있습니다.")
    else:
        ti = next((n for n, l in enumerate(lines[:SHELL_LINES]) if "<title>" in l), None)
        if ti is None:
            die("정적 셸에서 <title>을 찾지 못했습니다.")
        lines[ti] = f"  <title>{TITLE}</title>"
        lines.insert(ti + 1, META)
        print(f"메타 삽입: {ti + 2}행부터")

    # 2) 템플릿 안의 썸네일 경로를 절대 URL로
    i = template_index(lines)
    tmpl = json.loads(lines[i])
    rel = f'content="{THUMB}"'
    n = tmpl.count(rel)
    if n:
        tmpl = tmpl.replace(rel, f'content="{BASE}{THUMB}"')
        # 이 인코딩 조합이어야 왕복이 깨지지 않는다. </ 이스케이프는 필수 —
        # 없으면 문자열이 바깥 <script> 태그를 조기 종료시킨다.
        lines[i] = json.dumps(tmpl, ensure_ascii=False).replace("</", "<\\u002F")
        print(f"템플릿 썸네일 경로 절대화: {n}곳")
    else:
        print("건너뜀: 템플릿에 상대 경로 썸네일 참조가 없습니다.")

    TARGET.write_text("\n".join(lines), encoding="utf-8")

    if not (ROOT / THUMB).is_file():
        print(f"경고: {THUMB} 가 리포에 없습니다. OG 이미지가 404가 됩니다.")

    # 저장 후 재검증
    check = TARGET.read_text(encoding="utf-8").split("\n")
    json.loads(check[template_index(check)])
    missing = [t for t in ("og:image", "og:title", "twitter:card") if t not in "\n".join(check[:SHELL_LINES + 20])]
    if missing:
        die(f"검증 실패, 누락된 태그: {', '.join(missing)}")
    print(f"완료: {TARGET} ({len(check)}행)")


if __name__ == "__main__":
    main()
