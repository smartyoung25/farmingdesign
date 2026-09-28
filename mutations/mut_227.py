"""227차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 227  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
CP, W, T = 'consulting_package.py', 'webapp.py', 'webapp_templates/entry_docs.html'
M = [
 ("M1 D19에 첨부 미전달", CP, '                                                         inj.get("attachments_by_model")), [],',
  '                                                         None), [],'),
 ("M2 저장 첨부 변환 누락", CP, '    if ds.get("attachments_by_model"):                      # 227차', '    if False:                      # 227차'),
 ("M3 안내 목록 직접 적기", CP, 'APPROVAL_ATTACHMENTS: tuple = tuple(e.MATERIAL_APPROVAL_ATTACHMENTS)',
  'APPROVAL_ATTACHMENTS: tuple = ("시험성적표", "카탈로그")'),
 ("M4 견적에 없는 모델 허용", W, '        if m not in models:\r\n', '        if False:\r\n'),
 ("M5 빈 서류 허용", W, '        if not names:\r\n            raise HTTPException(400, detail=f"「{m}」의 첨부', '        if False:\r\n            raise HTTPException(400, detail=f"「{m}」의 첨부'),
 ("M6 첨부 파싱 무시", W, '"ks_declared": ks, "attachments_by_model": att,', '"ks_declared": ks, "attachments_by_model": {},'),
 ("M7 재열기 값 누락", W, '            "attachments_text": "\\n".join(', '            "attachments_text": "" and "\\n".join('),
 ("M8 미리보기 누락 열 제거", T, '{% if r.attachments_missing %}{{ r.attachments_missing | join(", ") }}{% else %}없음{% endif %}', '—'),
 ("M9 형식 검사 제거", W, '        if "=" not in ln:\r\n            raise HTTPException(400, detail=f"재료승인', '        if False:\r\n            raise HTTPException(400, detail=f"재료승인'),
 ("M10 첨부가 등급을 바꿈(규칙 무단 변경)", CP, '"equipment_ks": (None if not inj.get("quoted_models") else',
  '"equipment_ks": (None if not inj.get("attachments_by_model") else'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-k', '227cha or 226cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
