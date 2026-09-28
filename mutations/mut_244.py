"""244차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 244  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
E, R = 'smartfarm_engine.py', '엔진데이터_레지스트리.json'
M = [
 ("M1 한 품목 요율 틀림(턴버클 3→2%)", E, '    "철골공사|턴버클": {"공구손료율": 0.03},', '    "철골공사|턴버클": {"공구손료율": 0.02},'),
 ("M2 선홈통 값 하나 고름(3%)", E, '"알루미늄공사|선홈통공사": {"공구손료율": None, "공구손료율_원문": [0.02, 0.03]}',
  '"알루미늄공사|선홈통공사": {"공구손료율": 0.03, "공구손료율_원문": [0.02, 0.03]}'),
 ("M3 원문에 없는 품목 등재(스틸돌리)", E, '    "철골공사|외부기둥": {"공구손료율": 0.03},', '    "철골공사|스틸돌리": {"공구손료율": 0.03},\n    "철골공사|외부기둥": {"공구손료율": 0.03},'),
 ("M4 두 계열 합침(샌드위치 잡재료 누락)", E, '"온실피복공사|샌드위치판넬": {"공구손료율": 0.03, "잡재료율": 0.05}', '"온실피복공사|샌드위치판넬": {"공구손료율": 0.08}'),
 ("M5 레지스트리 status 추정", R, '"status_note": "실측(원문 [주] 전사', '"status_note": "추정(원문 [주] 전사'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a
    b2 = b.replace('\n', '\r\n') if crlf else b
    if name.startswith("M5"):
        a2 = '"status": "실측",\r\n      "status_note": "실측(원문 [주] 전사'
        b2 = '"status": "추정",\r\n      "status_note": "실측(원문 [주] 전사'
    if s.count(a2) != 1:
        res.append((name, f"적용 불가({s.count(a2)})")); continue
    open(f, 'wb').write(s.replace(a2, b2).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_registry.py', '-q', '-x',
                            '-k', '244cha or simple_dict'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
