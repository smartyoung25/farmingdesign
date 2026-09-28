"""245차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 245  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
H, B, W = 'webapp_templates/console_home.html', 'webapp_templates/_base.html', 'webapp.py'
M = [
 ("M1 숫자 부풀림(케이스 350+)", W, '        "stats": [("케이스", len(cs),', '        "stats": [("케이스", 350,'),
 ("M2 섹션 순서 뒤바꿈(서비스를 히어로 위로)", H, '  <div class="hero">', '  <section class="blk"><h2 id="svc">x</h2></section>\n  <div class="hero">'),
 ("M3 추천사 섹션 추가", H, '  <section class="blk" aria-labelledby="ev">', '  <section class="blk"><h2>고객 후기</h2><p>“최고의 컨설팅”</p></section>\n  <section class="blk" aria-labelledby="ev">'),
 ("M4 3단계 순서 역전", W, '                 for k, n, st, d, b in cpkg.PLATFORM_STAGES],', '                 for k, n, st, d, b in reversed(cpkg.PLATFORM_STAGES)],'),
 ("M5 행동 버튼 제거", B, '  <a class="cta" href="/entry/newcase">새 케이스 시작</a>\n', ''),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8'); crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a
    b2 = b.replace('\n', '\r\n') if crlf else b
    if s.count(a2) != 1:
        res.append((name, f"적용 불가({s.count(a2)})")); continue
    open(f, 'wb').write(s.replace(a2, b2).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '245cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
