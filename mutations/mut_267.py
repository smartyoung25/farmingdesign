"""267차 뮤테이션 — 「확인하지 못한 것」 원문 확인 기록 가드(test_267cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 267
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '267cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
D = '근거_관리동_실재점검_20260915.md'
M = [
 ("M1 [추정]을 단정으로", D, "**[추정]** 그대로 둔다", "확정한다"),
 ("M2 도면 근거 삭제", D, "p.3·4 「관리동면적 **432㎡(130.68py)**」 · ", ""),
 ("M3 분류 결정 문장 유입", D, "- 요약: 목록 밖 라인 가운데", "- 결정: 이 라인들은 부대시설에 넣는다.\n- 요약: 목록 밖 라인 가운데"),
 ("M4 A4 배수 미상 문구 삭제", D, "**배수(200%)의 뜻을 원문이 설명하지 않는다** — 작업동 단독 몫인지 확정 불가", "작업동 몫이다"),
 ("M5 범위 문구 삭제", D, "- ⚠️범위: 도면은", "- 도면은"),
 ("M6 릴리스 기록 삭제", '릴리스_v1.2_20260928.md', "**넣을지는 판단**이라 D-13(★유지)을 다시 열지 않는다.", "판단은 나중에."),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8'); crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a; b2 = b.replace('\n', '\r\n') if crlf else b
    if s.count(a2) < 1: print("적용불가", n); continue
    open(f, 'wb').write(s.replace(a2, b2, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
