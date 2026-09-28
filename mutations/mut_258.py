"""258차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 258  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '258cha'], capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
M = [
 ("M1 엔진 값을 합산", 'webapp.py', '    n_sc = sum(1 for c in cases if c.get("scenarios"))', '    n_sc = sum(c.get("area_m2", 0) for c in cases if c.get("scenarios"))'),
 ("M2 CLAUDE.md 결정 삭제", 'CLAUDE.md', '단서(★사용자 결정 2026-09-28, 258차): **항목 건수 집계는 허용**', '단서: 건수 집계'),
 ("M3 릴리스가 여전히 경계로 적음", '릴리스_v1.2_20260928.md', '- **사용자 경계로 남긴 것**: 홈 소개 문구 선택', '- **사용자 경계로 남긴 것**: `len()` 건수 집계가 1절 「앱 계층 산술」에 드는지 · 홈 소개 문구 선택'),
 ("M4 작업지시서 금지 단서 삭제", '작업지시서.md', ', 엔진 계산값의 재계산·합산·비율은 여전히 금지(레드팀', '(레드팀'),
 ("M5 푸터 구분 제거", 'webapp_templates/_base.html', '계산 수치는 엔진 호출 결과의 표시다 — 건수는', '수치는 엔진 호출 결과의 표시다 — 건수는'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용불가", n, s.count(a)); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
