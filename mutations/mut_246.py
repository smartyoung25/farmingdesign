"""246차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다.
246차 당시에는 셸에서 바로 돌려 스크립트가 없었다 — 265차에 차수로그 기록(M1 본문 수정 · M2 HANDOFF 생성 · M3 색인 행 삭제)대로 복원했다.
실행: python mutations/run_all.py 246  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '246cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
SK = os.path.join('.claude', 'skills', 'dev-work-order-writer', 'SKILL.md')
RD = os.path.join('docs', 'work-orders', 'README.md')
HO = os.path.join('docs', 'HANDOFF.md')

raw = open(SK, 'rb').read()
open(SK, 'wb').write(raw.replace('Iron Laws'.encode(), 'Iron Law'.encode(), 1))
try: print("잡음" if run() else "놓침", "M1 스킬 본문 한 글자 수정")
finally: open(SK, 'wb').write(raw)

assert not os.path.exists(HO)
open(HO, 'w', encoding='utf-8').write('')
try: print("잡음" if run() else "놓침", "M2 HANDOFF.md 생성")
finally: os.remove(HO)

raw = open(RD, 'rb').read(); s = raw.decode('utf-8')
row = next(l for l in s.splitlines(True) if l.startswith('| [WO-003]'))
open(RD, 'wb').write(s.replace(row, '', 1).encode('utf-8'))
try: print("잡음" if run() else "놓침", "M3 색인 행 삭제")
finally: open(RD, 'wb').write(raw)
assert run() == 0
