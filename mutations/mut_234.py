"""234차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 234  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
E, R = 'smartfarm_engine.py', '엔진데이터_레지스트리.json'
RSQ = chr(0x2019)
M = [
 ("M1 굽은 따옴표 별칭 제거", E, '    "Manufacturer\\u2019s Specification": "제조업자 시방서",\n', ''),
 ("M2 따옴표 일괄 치환", E, 'unicodedata.normalize("NFKC", str(name)).split()',
  'unicodedata.normalize("NFKC", str(name)).replace(chr(0x2018), chr(0x2019)).split()'),
 ("M3 레지스트리 값 누락", R, '"Manufacturer' + RSQ + 's Specification": "제조업자 시방서",', ''),
 ("M4 ‘ 별칭도 추가", E, '    "Manufacturer\\u2019s Specification": "제조업자 시방서",\n',
  '    "Manufacturer\\u2019s Specification": "제조업자 시방서",\n    "Manufacturer\\u2018s Specification": "제조업자 시방서",\n'),
 ("M5 레지스트리 기록 누락", R, ' 📌234차 — 사용자 지시', ' 📌 — 사용자 지시'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a
    b2 = b.replace('\n', '\r\n') if crlf else b
    if s.count(a2) != 1:
        res.append((name, f"적용 불가({s.count(a2)})")); continue
    open(f, 'wb').write(s.replace(a2, b2).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_registry.py', '-q', '-x',
                            '-k', '234cha or 233cha or 232cha or simple_dict'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
