"""243차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 243  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
E = 'smartfarm_engine.py'
L = '근거_결정대기대장_20260915.md'


def run(k):
    r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_registry.py', '-q', '-x', '-k', k],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return "잡음" if r.returncode != 0 else "놓침"


res = []
# M1 옛 순서로 되돌림(알루미늄 블록을 천창 뒤로) — 엔진만 되돌리고 레지스트리는 그대로
raw = open(E, 'rb').read(); s = raw.decode('utf-8'); crlf = '\r\n' in s
Ls = s.replace('\r\n', '\n').split('\n')
a0 = next(i for i, l in enumerate(Ls) if l.startswith('    # 알루미늄공사(6종, 개소당)'))
a1 = next(i for i, l in enumerate(Ls) if l.startswith('    # 온실피복공사(4종, ㎡당)'))
blk = Ls[a0:a1]; rest = Ls[:a0] + Ls[a1:]
h = next(i for i, l in enumerate(rest) if l.startswith('    # 수평스크린공사(13종)'))
mut = rest[:h] + blk + rest[h:]
t = '\n'.join(mut)
open(E, 'wb').write((t.replace('\n', '\r\n') if crlf else t).encode('utf-8'))
try:
    res.append(("M1 엔진 옛 순서 복귀", run('243cha or pumsem_items')))
finally:
    open(E, 'wb').write(raw)

M = [
 ("M2 계수 하나 변경(순서 작업 중 실수)", E, '"철골공": 0.21, "특별인부": 0.07}, {"지게차/5TON": 0.19}', '"철골공": 0.22, "특별인부": 0.07}, {"지게차/5TON": 0.19}'),
 ("M3 원장 D-12 다시 대기", L, '| ~~**D-12**~~ ✅**닫힘(243차)** |', '| **D-12** |'),
]
for name, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        res.append((name, run('243cha')))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
