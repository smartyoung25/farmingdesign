"""256차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 256  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')  # 266차: 265차 치환이 이 문장을 주석 속에 넣었다 — 되살림
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '256cha'], capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = '근거_확인요망대장_20260915.md'; L = '근거_결정대기대장_20260915.md'
M = [
 ("M1 WD1 다시 열기", C, '| ~~**WD1**~~ |', '| **WD1** |'),
 ("M2 D-15 몫 0.87%로 되돌림", L, '= 계수의 0.369%**다', '= 계수의 0.87%**다'),
 ("M3 조건(S-3) 삭제", L, '⚠️**조건**(256차 — 레드팀 30회차 A4): D-3 철회는 **S-3(OPEX 원문)이 들어와', '⚠️(256차): D-3 철회는 **나중에'),
 ("M4 14절 D7 닫힘 표시 제거", '작업지시서.md', '| ~~D7~~ ✅**닫힘(250차 ★D-7 유지 — 2,323)** |', '| D7 |'),
 ("M5 WO 제목을 기각안으로", 'docs/work-orders/WO-006_D11_크루구성.md', 'D-11 크루 구성 결정 — ★도입 안 함', 'D-11 크루 구성 도입 결정 반영'),
 ("M6 「잘」 옛 정규식", 'audit_work_orders.py', 'r"(?<![가-힣])잘(?!못|라|린|려|랐|게)"', 'r"(?<![가-힣])잘(?![가-힣])"'),
 ("M7 빈 (확인: ) 허용", 'audit_work_orders.py', 'if not CONFIRM_OK.search(c["text"]):', 'if "(확인:" not in c["text"]:'),
 ("M8 해당 없음 기준을 세지 않음", 'audit_work_orders.py', '"na": bool(NA_CRIT.match(cm.group(2).strip()))', '"na": False'),
 ("M9 히어로 과장 복귀", 'webapp_templates/console_home.html', '모든 수치에 근거 상태가 붙는', '모든 수치에 근거가 붙는'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용불가", n, s.count(a)); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
