"""238차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 238  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
E, R, CP = 'smartfarm_engine.py', '엔진데이터_레지스트리.json', 'consulting_package.py'
V = '릴리스_v1.1_20260927.md'
M = [
 ("M1 O&M 별칭 복귀", E, '    "Colour Chart": "표준 색상철",\n', '    "Colour Chart": "표준 색상철",\n    "O&M Manual": "자재유지관리 지침서",\n'),
 ("M2 첨부 미제출=불합격 복귀", CP, 'None if not _att_given else not _att_short),', 'not _att_short),'),
 ("M3 비식별 과장 복귀", E, '"값의 종류가 적어 **표 한 장으로 되찾을 수 있다**(비식별 장치가 아니다 — "', '"번호만으로 농가를 식별하지 못하게 한다(비식별 — "'),
 ("M4 書類提出 복귀", CP, '("docs", "문서 제출", "사람", "JAS 대응 없음(콘솔 단계)"),', '("docs", "문서 제출", "사람", "書類提出(서류 제출)"),'),
 ("M5 TÜV 복귀", CP, '"DNV Owner\'s Engineer(전주기 개념 참고)"),', '"DNV Owner\'s Engineer · TÜV Design Review"),'),
 ("M6 ④ 진행 복귀", CP, '"evidence": (("경로 없음", f"원문 대조 전', '"evidence": (("진행", f"원문 대조 전'),
 ("M7 needs 과잉 복귀", CP, '            if _eq is None:\n                need25 = need25 + _need("quoted_models")\n',
  '            if not gr["complete"]:\n                need25 = need25 + _need("quoted_models")\n'),
 ("M8 v1.1 ★ 글자 수로 복귀", V, '| **★사용자 결정 대기**(대장의 D- 항목) | **15** |', '| **★사용자 결정 대기**(대장의 D- 항목) | **19** |'),
 ("M9 v1.1 확인요망 과소", V, '| **확인요망**(대장의 살아 있는 항목) | **24** |', '| **확인요망**(대장의 살아 있는 항목) | **8** |'),
 ("M10 v1.1 KB 낡음", V, '6,931줄 · 544KB', '6,931줄 · 543KB'),
 ("M11 v1.1 끝까지 과장 복귀", V, '콘솔이 기입·문서 제출·발급을 받아', '콘솔이 이 절차를 끝까지 끌고 기입·문서 제출·발급을 받아'),
 ("M12 레지스트리 226차 복귀", R, '**228차까지** 호출부가', '226차까지 호출부가'),
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
                            '-k', '238cha or 207cha or 227cha or 232cha or simple_dict'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
