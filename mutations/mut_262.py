"""262차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 262  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '262cha'], capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
L = '근거_결정대기대장_20260915.md'
M = [
 ("M1 재합산 값 틀림", L, '모두 더하면 **36,878,048**이다', '모두 더하면 **36,878,000**이다'),
 ("M2 배율 틀림", L, '→ **76,971,248(1.92배)**', '→ **76,971,248(1.93배)**'),
 ("M3 소계 산식 틀림", L, '**소계 재 22,107,700 + 노 3,000,000 = 25,107,700**', '**소계 재 22,107,700 + 노 3,000,000 = 25,107,000**'),
 ("M4 OCR 확인 삭제", L, '📌**262차 원문 확인(OCR)**', '📌'),
 ("M5 엔진 부대시설 기준 변경", 'smartfarm_engine.py', '"auxiliary_facility": 40093200,', '"auxiliary_facility": 40093000,'),
 ("M6 범위 경고 삭제", L, '⚠️A5 외 라인은 이번에 원문을 다시 열지 않았다(143차 목록 값).', ''),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
