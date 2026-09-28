"""263차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 263  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')  # 266차: 265차 치환이 이 문장을 주석 속에 넣었다 — 되살림
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '263cha'], capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
D = '근거_관리동_실재점검_20260915.md'
M = [
 ("M1 표 금액 하나 틀림", D, '| 1,406,856 |', '| 1,406,850 |'),
 ("M2 S6·S7 두 번 셈", D, '| S6·S7 | 〃 p.6 |', '| S6·S7 | 시공 견적서 PDF p.5(재) | 콘크리트 양액실/관리실 49㎡ × 130,000 | 6,370,000 |\n| S6·S7 | 〃 p.6 |'),
 ("M3 행 하나 삭제", D, '| A6 | 견적 xls `내역서` 7행 | 작업동바닥콘크리트타설 9m×42m 1식 | 1,150,000 |\n', ''),
 ("M4 온실 전체 금액 유입", D, '| A7 | 〃 167행 |', '| S3 | 최종견적서 PDF p.11 | 농업용스크린(작업장포함) | 12,125,520 |\n| A7 | 〃 167행 |'),
 ("M5 사재를 두 줄로", D, '| A5 | 〃 p.8 | 관리동전후면 샛기둥 108.0m | 851,059 |', '| A5 | 〃 p.8 | 관리동 트러스 사재(재) | 348,840 |\n| A5 | 〃 p.8 | 관리동전후면 샛기둥 108.0m | 851,059 |'),
 ("M6 원문 위치 비움", D, '| S5 | 견적서 PDF p.3 · p.8 소계 |', '| S5 | — |'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8'); crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a; b2 = b.replace('\n', '\r\n') if crlf else b
    if s.count(a2) < 1: print("적용불가", n); continue
    open(f, 'wb').write(s.replace(a2, b2, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
