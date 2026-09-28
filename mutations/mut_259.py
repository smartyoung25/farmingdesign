"""259차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 259  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '259cha'], capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
H = 'webapp_templates/console_home.html'
M = [
 ("M1 제목 되돌림", H, '<h1>스마트농업을 <em>디자인하다</em></h1>', '<h1>입지부터 사후관리까지, <em>모든 수치에 근거 상태가 붙는</em> 스마트팜 컨설팅</h1>'),
 ("M2 제목 변형(마침표 추가 아닌 다른 말)", H, '스마트농업을 <em>디자인하다</em>', '스마트팜을 <em>디자인하다</em>'),
 ("M3 설명문까지 바꿈", H, '실측인지, 추정인지, 확인이 필요한지', '무엇이든'),
 ("M4 릴리스 기록 삭제", '릴리스_v1.2_20260928.md', '  (홈 소개 문구는 259차에 ★「스마트농업을 디자인하다」로 확정)\n', ''),
 ("M5 과장 문구 복귀(설명문에)", H, '입력되지 않은 것은', '모든 수치에 근거가 붙는다. 입력되지 않은 것은'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8'); crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a; b2 = b.replace('\n', '\r\n') if crlf else b
    if s.count(a2) < 1: print("적용불가", n, s.count(a2)); continue
    open(f, 'wb').write(s.replace(a2, b2, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
