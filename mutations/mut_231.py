"""231차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 231  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
E, R, T = 'smartfarm_engine.py', '엔진데이터_레지스트리.json', 'webapp_templates/entry_docs.html'
M = [
 ("M1 정규화 없이 문자열 대조", E, '        missing_att = [a for a in MATERIAL_APPROVAL_ATTACHMENTS if a not in seen]',
  '        missing_att = [a for a in MATERIAL_APPROVAL_ATTACHMENTS if a not in given]'),
 ("M2 공백 무시 제거", E, '    return "".join(str(name).split())', '    return str(name).strip()'),
 ("M3 부분 일치로 추측", E, '        if _approval_doc_key(canon) == k:', '        if _approval_doc_key(canon)[:2] == k[:2]:'),
 ("M4 계산서 계열 별칭 추가", E, '    "카다로그": "카탈로그",\n}', '    "카다로그": "카탈로그",\n    "세금계산서": "계산서",\n}'),
 ("M5 적힌 이름을 정본으로 덮어씀", E, '                     "attachments_given": given,', '                     "attachments_given": [norm[g] or g for g in given],'),
 ("M6 인식 안 됨 목록 비움", E, '"attachments_unrecognized": [g for g, c in norm.items() if not c],', '"attachments_unrecognized": [],'),
 ("M7 레지스트리 status 추정", R, '"status_note": "결정(사용자 지시 2026-09-27) — 정본은 실측, 별칭만 결정"', '"status_note": "추정(사용자 지시 2026-09-27) — 정본은 실측, 별칭만 결정"'),
 ("M8 미리보기 표기 정리 열 제거", T, '{% for g, c in (r.attachments_normalized or {}).items() %}<span class="nm">{{ g }}→{{ c }}</span> {% endfor %}', ''),
 ("M9 레지스트리 값 드리프트", R, '"카다로그": "카탈로그"', '"카다록": "카탈로그"'),
 ("M10 양식이 저장값을 정본으로", 'webapp.py', '        att[m] = names\r\n', '        att[m] = [__import__("smartfarm_engine")._normalize_approval_doc(x) or x for x in names]\r\n'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf and '\r\n' not in a else a
    b2 = b.replace('\n', '\r\n') if crlf and '\r\n' not in b else b
    if name.startswith("M7"):
        a2 = '"status": "결정",\r\n      "status_note": "결정(사용자 지시 2026-09-27)'
        b2 = '"status": "추정",\r\n      "status_note": "결정(사용자 지시 2026-09-27)'
    if s.count(a2) != 1:
        res.append((name, f"적용 불가({s.count(a2)})")); continue
    open(f, 'wb').write(s.replace(a2, b2).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_registry.py', 'test_webapp.py', '-q', '-x',
                            '-k', '231cha or simple_dict or 227cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
