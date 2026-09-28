"""261차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 261  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')  # 266차: 265차 치환이 이 문장을 주석 속에 넣었다 — 되살림
def run(k='261cha', f='test_webapp.py'):
    return subprocess.run([sys.executable, '-m', 'pytest', f, '-q', '-x', '-k', k], capture_output=True).returncode
assert run() == 0 and run('257cha or 258cha', 'test_engine.py') == 0, "원본이 실패한다 — 뮤테이션 무효"
T = 'webapp_templates/work_orders.html'; D = 'webapp_templates/work_order_detail.html'; A = 'audit_work_orders.py'
M = [
 ("M1 목록 분모를 전체로(256 이전)", T, '{{ r.checked }} / {{ r.applicable }}', '{{ r.checked }} / {{ r.total }}', None),
 ("M2 상세 NA 칩 제거(256 이전)", D, "{% if c.na %}<span class=\"chip chip-ref\">해당 없음</span>{% else %}", "{% if False %}{% else %}", None),
 ("M3 NA 판정 다시 넓게", A, 'NA_CRIT = re.compile(r"^\\([ⓐ-ⓩ](?:·[ⓐ-ⓩ])*\\s*해당\\s*없음\\s*[—–-]\\s*[ⓐ-ⓩ](?:·[ⓐ-ⓩ])*\\s*선택\\)")', 'NA_CRIT = re.compile(r"^\\([^)]*해당\\s*없음\\s*—[^)]*\\)")', None),
 ("M4 체크된 NA 허용", A, '        if c["na"] and c["checked"]:', '        if False:', None),
 ("M5 「잘」 256 정규식", A, 'r"잘(?!못|라|린|려|랐|리|립|게)"', 'r"(?<![가-힣])잘(?!못|라|린|려|랐|게)"', None),
 ("M6 자리표시자 허용", A, ' or CONFIRM_PLACEHOLDER.search(c["text"])', '', None),
 ("M7 단가대비표 오독 복귀", '근거_확인요망대장_20260915.md', '표지 2,323과도 다르다(레드팀 30회차 A7)', '표지·단가대비표 2,323과도 다르다(레드팀 30회차 A7)', None),
 ("M8 인용 오기 복귀", '근거_결정대기대장_20260915.md', '유리닦기 등의 공정등이 없는 것으로 조사', '유리닦기 등의 공정이 없는 것으로 조사', None),
 ("M9 webapp에 += 누적(258 가드)", 'webapp.py', '    n_sc = sum(1 for c in cases if c.get("scenarios"))', '    n_sc = 0\n    for c in cases:\n        n_sc += c.get("area_m2", 0)', ('258cha', 'test_engine.py')),
 ("M10 결정 표에서 D-9 행 삭제(257 가드)", '릴리스_v1.2_20260928.md', '| D-9 동절기 개월 |', '| 동절기 개월 |', ('257cha', 'test_engine.py')),
]
for n, f, a, b, alt in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8'); crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a; b2 = b.replace('\n', '\r\n') if crlf else b
    if s.count(a2) < 1: print("적용불가", n, s.count(a2)); continue
    open(f, 'wb').write(s.replace(a2, b2, 1).encode('utf-8'))
    try: print("잡음" if (run(*alt) if alt else run()) else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
