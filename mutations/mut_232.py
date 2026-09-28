"""232차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 232  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
E, R = 'smartfarm_engine.py', '엔진데이터_레지스트리.json'
M = [
 ("M1 대소문자 무시 제거", E, '    return "".join(str(name).split()).casefold()', '    return "".join(str(name).split())'),
 ("M2 Invoice→계산서 별칭 추가", E, '    "O&M Manual": "자재유지관리 지침서",\n}', '    "O&M Manual": "자재유지관리 지침서",\n    "Invoice": "계산서",\n}'),
 ("M3 영문 별칭 하나 누락", E, '    "Color Chart": "표준 색상철",\n', ''),
 ("M4 복수형 추측(접두 일치)", E, '        if _approval_doc_key(alias) == k:', '        if k.startswith(_approval_doc_key(alias)[:12]):'),
 ("M5 레지스트리 값 드리프트", R, '"Test Report": "시험성적표"', '"Test report": "시험성적표"'),
 ("M6 정본을 잘못 가리킴", E, '    "Test Report": "시험성적표",', '    "Test Report": "제조업자 시방서",'),
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
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_registry.py', 'test_webapp.py', '-q', '-x',
                            '-k', '232cha or 231cha or simple_dict'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
