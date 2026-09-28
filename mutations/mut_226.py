"""226차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 226  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
CP, W = 'consulting_package.py', 'webapp.py'
H = 'webapp_templates/entry_hub.html'
M = [
 ("M1 패키지가 저장 주입을 안 읽음", CP, '    inj = case_injections(case)\n', '    inj = {}\n'),
 ("M2 D23이 제출 문서 무시", CP, '            if inj.get("dd_documents"):\n                d["제출 문서"]', '            if False:\n                d["제출 문서"]'),
 ("M3 문서 저장 근거 검사 제거", W, '    if not block["note"]:\r\n        raise HTTPException(400, detail="근거(note: 문서 출처',
  '    if False:\r\n        raise HTTPException(400, detail="근거(note: 문서 출처'),
 ("M4 발급 저장 엔진 검증 생략", W, '    _preview_with(case, cpkg.KSFID_ISSUE_KEY, block)      # 엔진 검증 통과분만 저장', '    pass'),
 ("M5 발급일 변환 누락", CP, '    if ki.get("ksfid_issued"):\n', '    if False:\n'),
 ("M6 규격 선언 파싱 무시", W, '"quoted_models": _lines(form, "quoted_models_text"), "ks_declared": ks,',
  '"quoted_models": _lines(form, "quoted_models_text"), "ks_declared": {},'),
 ("M7 잘못된 키에 저장", W, '    case[cpkg.DOC_SUBMISSION_KEY] = block\r\n', '    case["docs"] = block\r\n'),
 ("M8 허브 스테퍼 상태 하드코딩", H, '<span class="chip {{ step_cls.get(s.state, \'chip-ref\') }}">{{ s.state }}</span><br>',
  '<span class="chip {{ step_cls.get(s.state, \'chip-ref\') }}">대기</span><br>'),
 ("M9 미리보기가 저장", W, '    pv = _preview_with(case, cpkg.KSFID_ISSUE_KEY, block)\r\n',
  '    pv = _preview_with(case, cpkg.KSFID_ISSUE_KEY, block)\r\n    case[cpkg.KSFID_ISSUE_KEY] = block\r\n    _save_case(case)\r\n'),
 ("M10 발급 폼 재열기 값 누락", 'webapp_templates/entry_issue.html',
  'value="{{ v.ksfid_seq if v.ksfid_seq is not none else \'\' }}"', 'value=""'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-k', '226cha or 224cha or 225cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
