"""264차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 264  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
def run(k, f):
    return subprocess.run([sys.executable, '-m', 'pytest', f, '-q', '-x', '-k', k], capture_output=True).returncode
BASE = [('264cha', 'test_engine.py'), ('258cha or 263cha', 'test_engine.py'), ('261cha', 'test_webapp.py')]
assert all(run(*b) == 0 for b in BASE), "원본이 실패한다 — 뮤테이션 무효"
D = '근거_관리동_실재점검_20260915.md'; A = 'audit_work_orders.py'
M = [
 ("M1 목록 밖 라인 하나로 되돌림", D, "p.8 「관리동 측면 보강대 118.0m」 **543,304** · ", "", BASE[0]),
 ("M2 [추정] 삭제", D, "사재를 두 번 더한 것으로 보인다 [추정]", "사재를 두 번 더한 것이다", BASE[0]),
 ("M3 S5 제외 합 틀림", D, "빼면 **34,060,779**", "빼면 **34,060,000**", BASE[0]),
 ("M4 합계열 합 틀림", D, "합계열로 더하면 **36,878,046**", "합계열로 더하면 **36,878,048**", BASE[0]),
 ("M5 CLAUDE.md 콘솔 한정 풀림", 'CLAUDE.md', "**콘솔(webapp) 앱 계층**에서 ", "", BASE[1]),
 ("M6 S6·S7을 두 표본으로(전제)", 'smartfarm_engine.py', '"백가은·조윤정": {', '"백가은": {', BASE[1]),
 ("M7 webapp 누적 대입", 'webapp.py', '    n_sc = sum(1 for c in cases if c.get("scenarios"))', '    n_sc = 0\n    for c in cases:\n        n_sc = n_sc + c.get("area_m2", 0)', BASE[1]),
 ("M8 「잘릴」 다시 금지", A, "릴|림|", "", BASE[2]),
 ("M9 TBD 허용", A, "|TBD|tbd", "", BASE[2]),
 ("M10 목록 셀 NA 없는 행 표시 틀림", 'webapp_templates/work_orders.html', "{{ r.checked }} / {{ r.applicable }}{% if r.na %}", "{{ r.checked }} / {{ r.total }}{% if r.na %}", BASE[2]),
]
for n, f, a, b, bk in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8'); crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a; b2 = b.replace('\n', '\r\n') if crlf else b
    if s.count(a2) < 1: print("적용불가", n, s.count(a2)); continue
    open(f, 'wb').write(s.replace(a2, b2, 1).encode('utf-8'))
    try: print("잡음" if run(*bk) else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert all(run(*b) == 0 for b in BASE)
