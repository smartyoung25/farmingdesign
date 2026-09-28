"""257차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 257  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '257cha or 207cha'], capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
R = '릴리스_v1.2_20260928.md'
M = [
 ("M1 결정 표에서 D-13 행 삭제", R, '| D-13 관리동·작업동 금액 | 유지 — 독립 공종만 부대시설 | 0 | 253 |\n', ''),
 ("M2 열린 D-14를 결정 표에", R, '| D-11 크루 구성 |', '| D-14 비닐 7종 | 등재 | 0 | 256 |\n| D-11 크루 구성 |'),
 ("M3 WO 칸 부풀림", R, '**9건**(완료 8 · 자료 대기 1)', '**9건**(완료 9 · 자료 대기 0)'),
 ("M4 실명 유입", R, '회귀 기준인 C2 케이스조차', '회귀 기준인 원채원 케이스조차'),
 ("M5 v1.1 포인터 제거", '릴리스_v1.1_20260927.md', '현행 릴리스는 `릴리스_v1.2_20260928.md`다(257차).', '현행 릴리스는 새 판이다.'),
 ("M6 확인요망 수 틀림", R, '| **확인요망**(대장의 살아 있는 항목) | **22** |', '| **확인요망**(대장의 살아 있는 항목) | **23** |'),
 ("M7 v1.1 동결 해제(현재 수치로)", '릴리스_v1.1_20260927.md', '| 회귀 | 3파일 **377 passed**', '| 회귀 | 3파일 **390 passed**'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8'); crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a; b2 = b.replace('\n', '\r\n') if crlf else b
    if s.count(a2) < 1: print("적용불가", n, s.count(a2)); continue
    open(f, 'wb').write(s.replace(a2, b2, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
