"""233차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 233  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
E, R = 'smartfarm_engine.py', '엔진데이터_레지스트리.json'
M = [
 ("M1 NFKC 제거", E, 'return "".join(unicodedata.normalize("NFKC", str(name)).split()).casefold()',
  'return "".join(str(name).split()).casefold()'),
 ("M2 NFC만(전각 못 옮김)", E, 'unicodedata.normalize("NFKC", str(name))', 'unicodedata.normalize("NFC", str(name))'),
 ("M3 굽은 따옴표 추측 치환", E, 'unicodedata.normalize("NFKC", str(name))', 'unicodedata.normalize("NFKC", str(name)).replace(chr(0x2019), "\'")'),
 ("M4 적힌 이름을 반각으로 덮어씀", E, '                     "attachments_given": given,',
  '                     "attachments_given": [unicodedata.normalize("NFKC", g) for g in given],'),
 ("M5 레지스트리 기록 누락", R, ' 📌233차 — 사용자 지시', ' 📌 — 사용자 지시'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '233cha or 232cha or 231cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
