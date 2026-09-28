"""260차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 260  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '260cha or 258cha'], capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
R = '릴리스_v1.2_20260928.md'
M = [
 ("M1 다시 경계로", R, '- **사용자 경계로 남긴 것**: 없음(', '- **사용자 경계로 남긴 것**: 옛 기록 실명('),
 ("M2 확정 기록 삭제", R, '**260차에 ★「그대로 둔다」로 확정**', '**나중에 정한다**'),
 ("M3 표시 계층 경계 삭제", 'case_display.py', '내부 데이터는 손대지 않는다', '내부 데이터도 바꾼다'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
