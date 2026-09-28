"""229차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 229  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
CP = 'consulting_package.py'
M = [
 ("M1 연도 2026으로 되돌림", CP, 'int(d["유효기간"]["issued"][:4]), seq)', '2026, seq)'),
 ("M2 발급일 없어도 번호(현재 연도 지어냄)", CP, '            elif issued:\n                d["식별번호"]',
  '            else:\n                d["식별번호"]'),
 ("M3 발급일 needs 누락", CP, '            if not issued:\n                need25 = need25 + _need("ksfid_issued")',
  '            if False:\n                need25 = need25 + _need("ksfid_issued")'),
 ("M4 스테퍼가 옛 문구", CP, '"{} 미주입 — 번호는 일련번호와 발급일(연도)이 모두 있어야 선다".format(',
  '"ksfid_seq 미주입{}".format(" " and '),
 ("M5 월을 연도로", CP, 'int(d["유효기간"]["issued"][:4]), seq)', 'int(d["유효기간"]["issued"][5:7]), seq)'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '229cha or 226cha or 225cha or 224cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
