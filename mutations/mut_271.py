"""271차 뮤테이션 — 실행기 범위 제한 복원 가드(test_271cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 271
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '271cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
R = os.path.join('mutations', 'run_all.py')
M = [
 ("M1 범위 검사 제거(범위 밖도 되돌림)", R, "        if scope is not None and not in_scope(path, scope):\n            if path not in snap",
  "        if False:\n            if path not in snap"),
 ("M2 외부 변경을 보고하지 않음", R, "notes.append('⚠️외부 변경(손대지 않음): '", "notes.append('외부: '"),
 ("M3 실행 전 변경 알림 제거", R, "    if dirty:\n        print(", "    if False:\n        print("),
 ("M4 리터럴 전부를 파일로 침(범위 과대)", R, "elif os.path.isfile(os.path.join(ROOT, v)):", "elif True:"),
 ("M5 glob 빈 접두(리포 전체) 허용", R, "if d and os.path.isdir(os.path.join(ROOT, d)):", "if os.path.isdir(os.path.join(ROOT, d)):"),
 ("M6 foreign을 돌려주지 않음", R, "    return fixed, foreign", "    return fixed, []"),
 ("M7 in_scope가 늘 참", R, "    return p in files or any(p.startswith(d) for d in dirs)", "    return True"),
 ("M8 README 설명 되돌림", os.path.join('mutations', 'README.md'), "스크립트가 손댈 수 있는 경로", "스크립트가 고친 경로"),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
