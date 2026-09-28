"""228차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 228  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
CP = 'consulting_package.py'
R = '엔진데이터_레지스트리.json'
M = [
 ("M1 옛 규칙(선언만)으로 되돌림", CP, 'not _eq["needs_ks_declaration"] and not _att_short),', 'not _eq["needs_ks_declaration"]),'),
 ("M2 첨부를 엔진에 안 넘김", CP, '                                         inj.get("attachments_by_model")))\n            _att_short',
  '                                         None))\n            _att_short'),
 ("M3 누락 판단을 all로(하나만 채우면 통과)", CP, 'any(r["attachments_missing"] for r in _eq["rows"])', 'all(r["attachments_missing"] for r in _eq["rows"])'),
 ("M4 needs에 첨부 슬롯 미표시", CP, '                need25 = need25 + _need("attachments_by_model")\n', '                pass\n'),
 ("M5 선언 검사 제거", CP, 'not _eq["needs_ks_declaration"] and not _att_short),', 'not _att_short),'),
 ("M6 레지스트리 결정 기록 누락", R, ' 📌228차 — ★**사용자 결정(2026-09-27, B10 ⓑ)**', ' 📌 — ★**사용자 결정(2026-09-27)**'),
 ("M7 미주입인데 통과", CP, '"equipment_ks": (None if _eq is None else', '"equipment_ks": (True if _eq is None else'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', 'test_engine.py', '-q', '-x',
                            '-k', '227cha or 187cha or ksfid or 226cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
