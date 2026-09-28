"""266차 뮤테이션 — 레드팀 33회차 반영 가드(test_266cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 266
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda k='266cha': subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', k],
                                        capture_output=True).returncode
assert run() == 0 and run('264cha') == 0 and run('265cha') == 0, "원본이 실패한다 — 뮤테이션 무효"
D = '근거_관리동_실재점검_20260915.md'
R = os.path.join('mutations', 'run_all.py')
M = [
 ("M1 완결 주장 되살림", D, "그래서 목록 밖 라인은 **더 있을 수 있다**.", "그래서 목록 밖 라인은 이것뿐이다."),
 ("M2 S4 목록 밖 라인 삭제", D, "  - S4 견적 PDF p.10 「모타 전선(관리동천창) VCTP 2P×2.5C 800m」 **1,120,000** — 146차 7줄 합에 없다.\n", ""),
 ("M3 연동 라인 합 틀림", D, "(합 9,127,814 — 143차", "(합 9,127,000 — 143차"),
 ("M4 S5 포함 단정으로", D, "**150차 측정은 S5를 이관 대상에 넣은 것으로 보인다**", "**150차 측정은 S5를 이관 대상에 넣었다**"),
 ("M5 실행기가 「적용 불가」를 다시 못 셈", R, "head.startswith('적용불가')", "ln.startswith('적용불가')"),
 ("M6 쪽 번호 해석 되돌림", D, "**0부터 센 쪽 번호**로 보인다", "인쇄 쪽과 PDF 쪽의 차로 보인다"),
 # 266차가 KNOWN 사유·A5 문구를 고쳐 mut_264 M1·mut_265 M3가 낡았다 — 같은 검사를 여기서 잇는다
 ("M7 분류 없는 면제(새 사유 문구)", R, "'상태 변화 — D-7이 250차에 닫혀 열린 항목 검사 대상이 아니다'", "'그냥 넘어감'", '265cha'),
 ("M8 A5 측면 보강대 라인 삭제", D, "p.8 「관리동 측면 보강대 118.0m」 **543,304**(두 열 같음) ·", "", '264cha'),
]
for n, f, a, b, *k in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8'); crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a; b2 = b.replace('\n', '\r\n') if crlf else b
    if s.count(a2) < 1: print("적용불가", n); continue
    open(f, 'wb').write(s.replace(a2, b2, 1).encode('utf-8'))
    try: print("잡음" if run(*k) else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
