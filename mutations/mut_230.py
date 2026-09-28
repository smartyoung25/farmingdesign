"""230차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 230  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
E, R = 'smartfarm_engine.py', '엔진데이터_레지스트리.json'
M = [
 ("M1 해시 계수 변경(값+레지스트리 동시)", E, '    "hash_mul": 131,', '    "hash_mul": 137,'),
 ("M2 본문에 리터럴 복귀", E, 'h = (h * S["hash_mul"] + ord(ch)) % S["hash_mod"]', 'h = (h * 131 + ord(ch)) % S["hash_mod"]'),
 ("M3 레지스트리 status 추정", R, '"status_note": "결정(★사용자 187차 체계 · 229차 연도)', '"status_note": "추정(★사용자 187차 체계 · 229차 연도)'),
 ("M4 레지스트리 값 드리프트", R, '"check_mod": 37,', '"check_mod": 41,'),
 ("M5 준거 GGN 삭제", R, '13자리 GGN(추적 식별자이지 등급이 아니다)', '13자리 번호(추적 식별자이지 등급이 아니다)'),
 ("M6 형식 문구만 바꿈", E, '    "format": "KSF-<연도 4>-<지역 2>-<작목 2>-<피복 1>-<일련 4>-<검증문자 1>",',
  '    "format": "KSF-<연도 4>-<지역 2>-<작목 2>-<피복 1>-<일련 4>",'),
 ("M7 검증문자 모듈러 본문 리터럴", E, '% S["check_mod"]\n', '% 37\n'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    a2 = a.replace('\n', '\r\n') if '\r\n' in s else a
    b2 = b.replace('\n', '\r\n') if '\r\n' in s else b
    if name.startswith("M3"):
        a2 = '"status": "결정",\r\n      "status_note": "결정(★사용자 187차 체계'
        b2 = '"status": "추정",\r\n      "status_note": "결정(★사용자 187차 체계'
    if s.count(a2) != 1:
        res.append((name, f"적용 불가({s.count(a2)})")); continue
    open(f, 'wb').write(s.replace(a2, b2).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_registry.py', 'test_webapp.py', '-q', '-x',
                            '-k', '230cha or simple_dict or 225cha or status_vocabulary'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
