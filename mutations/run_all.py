"""뮤테이션 실행기 — 차수별 가드를 일부러 깨서 잡히는지 다시 잰다(265차 · 266차 보강).

  python mutations/run_all.py            # 전부(오래 걸린다 — 스크립트마다 pytest를 여러 번 돈다)
  python mutations/run_all.py 262 263    # 지정한 차수만(보충 스크립트 mut_NNNb.py도 함께)

한 스크립트마다:
  ① **원본 통과 확인** — 스크립트가 부르는 테스트 파일과 `-k` 선택자를 모아 먼저 돌린다. 실패하면 **무효**,
     선택자를 하나도 못 모으면 **건너뜀**(둘 다 실패로 친다 — 266차: 종전엔 건너뛰고도 「통과」로 적었다).
  ② **안전 복원(git 기준)** — 실행 전 `git status`와 이미 바뀌어 있던 파일의 바이트를 저장하고, 끝나면(시간 초과·예외 포함)
     새로 바뀐 추적 파일은 되돌리고 새로 생긴 파일은 지운다(266차: 종전엔 스크립트가 **이름으로 부른** 파일만 복원해
     glob으로 얻은 경로·새로 만든 파일을 놓쳤다 — 레드팀 33회차 B4).
  ③ **집계** — 「잡음」·「놓침」·「적용불가」(띄어쓰기 무관 — 266차: 223~245차는 「적용 불가」라 **20건이 소리 없이 빠졌다**, 33회차 B1)를
     세고, **스크립트에 선언된 뮤테이션 수와 대조**한다(모자라면 「누락」 — 실패).
     결함이 아닌 놓침은 `KNOWN`에 분류·이유와 함께 둔다. 지금 **살아서 잡는 뮤테이션이 0**인 차수는 경고한다(33회차 B3).
종료 코드: 원본 실패·건너뜀·놓침·누락·스크립트 오류가 하나라도 있으면 1.
"""
import ast, glob, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')

# 265차 재현에서 나온 놓침 가운데 **가드 결함이 아닌 것** — 분류와 이유를 함께 둔다(이유는 항목마다 적는다 — 「〃」 금지).
#   여기 없는 놓침은 새 결함이라 실패로 친다. 가드 결함(무뎌짐)은 여기 올리지 않고 가드를 고친다
#   (265차: 228·234차 레지스트리 기록 단언이 뒤 차수 서술의 같은 차수 번호에 무뎌져 있었다 → 조임).
_V11 = '대상 이동 — v1.1은 257차에 239차 동결 기록이 됐고 같은 검사는 test_207cha가 v1.2에서 한다'
KNOWN = {
    '233': {'M3 굽은 따옴표 추측 치환': '등가 변이 — 234~236차에 따옴표 변형 별칭이 전부 등재돼 추측 치환과 결과가 같다'},
    '234': {'M2 따옴표 일괄 치환': '등가 변이 — 235·236차에 따옴표 변형이 전부 등재돼 일괄 치환과 결과가 같다',
            'M4 ‘ 별칭도 추가': '등가 변이 — 235차에 ‘가 사용자 지시로 등재돼 추가해도 같은 키다'},
    '235': {'M2 백틱 일괄 치환': '등가 변이 — 236차에 백틱이 등재돼 일괄 치환과 결과가 같다',
            'M4 백틱 별칭 추가': '등가 변이 — 236차에 백틱이 사용자 지시로 등재돼 추가해도 같은 키다'},
    '237': {'M1 v1.1 라우트 수 틀림': _V11 + '(라우트 수)',
            'M2 v1.1 보증 한계 문구 삭제': _V11 + '(보증 한계 문구)',
            'M6 v1.1 레지스트리 수 낡음': _V11 + '(레지스트리 수)'},
    '238': {'M8 v1.1 ★ 글자 수로 복귀': _V11 + '(★대기 항목 수)',
            'M9 v1.1 확인요망 과소': _V11 + '(확인요망 항목 수)',
            'M10 v1.1 KB 낡음': _V11 + '(엔진 KB)'},
    '240': {'M5 지역명 부분 매칭이 생김(대장 미갱신)': '상태 변화 — D-5가 241차에 닫혀 가드의 「D-5 대기」 분기가 돌지 않는다'},
    '249': {'M1 D-11 WO의 D 번호 제거': '상태 변화 — D-11이 255차에 닫혀 열린 항목 검사 대상이 아니다',
            'M4 D-7 WO 중복': '상태 변화 — D-7이 250차에 닫혀 열린 항목 검사 대상이 아니다'},
}


def num_of(path):
    return re.search(r'mut_(\d+)', os.path.basename(path)).group(1)


def baseline_args(src):
    files = sorted(set(re.findall(r"'(test_\w+\.py)'", src))) or ['test_engine.py', 'test_webapp.py']
    ks = re.findall(r"'-k',\s*'([^']+)'", src)
    ks += [x for x in re.findall(r"'([^'\n]*\b\d{2,3}cha\b[^'\n]*)'", src) if x not in ks]
    return files, ks


def expected_count(src):
    """스크립트에 선언된 뮤테이션 수 — 최상위 `M = [...]`의 원소 + 리터럴 이름을 직접 찍는 줄."""
    n = 0
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'M' and isinstance(node.value, ast.List):
            n += len(node.value.elts)
    n += len(re.findall(r'print\("잡음" if [^,]+,\s*"', src))
    n += len(re.findall(r'res\.append\(\("M\d+', src))   # 243차처럼 목록 밖에서 하나를 따로 찍는 스크립트
    return n


def tally(stdout, known):
    """출력 줄 → 집계. 「적용불가」는 띄어쓰기와 무관하게 센다."""
    r = {'caught': 0, 'missed': 0, 'known': 0, 'stale': 0, 'missed_names': []}
    for ln in stdout.splitlines():
        ln = ln.strip()
        head = ln.replace(' ', '')
        if ln.startswith('잡음'):
            r['caught'] += 1
        elif ln.startswith('놓침'):
            name = ln[len('놓침'):].strip()
            if name in known:
                r['known'] += 1
            else:
                r['missed'] += 1; r['missed_names'].append(ln)
        elif head.startswith('적용불가'):
            r['stale'] += 1
    return r


def git_state():
    out = subprocess.run(['git', 'status', '--porcelain', '-uall'], capture_output=True, text=True,
                         encoding='utf-8', errors='replace').stdout
    st = {}
    for ln in out.splitlines():
        path = ln[3:].strip().strip('"')
        if ' -> ' in path:
            path = path.split(' -> ')[-1]
        st[path] = ln[:2]
    return st


def restore(before, snap):
    """실행 전 상태로 되돌린다 — 되돌린 경로 목록을 돌려준다."""
    after = git_state()
    fixed = []
    for path, code in after.items():
        if before.get(path) == code and path not in snap:
            continue
        if path in snap:                                   # 원래 바뀌어 있던 파일 — 저장한 바이트로
            if not os.path.exists(path) or open(path, 'rb').read() != snap[path]:
                open(path, 'wb').write(snap[path]); fixed.append(path)
        elif code == '??':                                  # 새로 생긴 파일 — 지운다
            os.remove(path); fixed.append(path)
        else:                                               # 깨끗했던 추적 파일 — 커밋 상태로
            subprocess.run(['git', 'checkout', '--', path], capture_output=True); fixed.append(path)
    for path, data in snap.items():                         # 원래 있던 파일이 지워진 경우
        if not os.path.exists(path):
            open(path, 'wb').write(data); fixed.append(path)
    return fixed


def run_one(path):
    src = open(path, encoding='utf-8').read()
    num = num_of(path)
    res = {'baseline': '통과', 'caught': 0, 'missed': 0, 'known': 0, 'stale': 0, 'error': '',
           'restored': [], 'missed_names': [], 'expected': expected_count(src)}
    files, ks = baseline_args(src)
    if not ks:
        res['baseline'] = '건너뜀'
        return res
    expr = ' or '.join(f'({k})' for k in ks)
    b = subprocess.run([sys.executable, '-m', 'pytest', *files, '-q', '-x', '-p', 'no:cacheprovider', '-k', expr],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
    if b.returncode != 0:
        res['baseline'] = '실패'
        return res
    before = git_state()
    snap = {p: open(p, 'rb').read() for p, c in before.items() if os.path.isfile(p)}
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, encoding='utf-8',
                           errors='replace', env=ENV, timeout=1800)
        res.update(tally(r.stdout, KNOWN.get(num, {})))
        if r.returncode != 0:
            res['error'] = (r.stderr.strip().splitlines() or ['?'])[-1][:160]
    except subprocess.TimeoutExpired:
        res['error'] = '시간 초과'
    finally:
        res['restored'] = restore(before, snap)
    return res


def main(argv):
    want = set(argv)
    paths = sorted(glob.glob(os.path.join(ROOT, 'mutations', 'mut_*.py')))
    paths = [p for p in paths if not want or num_of(p) in want]
    bad = False
    print('스크립트 | 원본 | 잡음 | 놓침 | 알려진 놓침(분류) | 적용불가(낡음) | 선언 | 비고')
    for p in paths:
        t0 = time.time()
        r = run_one(p)
        seen = r['caught'] + r['missed'] + r['known'] + r['stale']
        notes = []
        if r['error']:
            notes.append(r['error'])
        if r['missed_names']:
            notes.append('; '.join(r['missed_names']))
        if r['baseline'] == '통과' and seen < r['expected']:
            notes.append(f'🔴누락 {r["expected"] - seen}(선언 {r["expected"]} · 집계 {seen})')
        if r['baseline'] == '통과' and r['caught'] == 0:
            notes.append('⚠️살아서 잡는 뮤테이션 0 — 가드를 지금 상태로 다시 재야 한다')
        if r['restored']:
            notes.append('복원: ' + ', '.join(r['restored']))
        print(f"{os.path.basename(p)[:-3]} | {r['baseline']} | {r['caught']} | {r['missed']} | {r['known']} | {r['stale']} | "
              f"{r['expected']} | {' · '.join(notes)} ({time.time() - t0:.0f}s)", flush=True)
        bad |= (r['baseline'] != '통과' or r['missed'] > 0 or bool(r['error'])
                or (r['baseline'] == '통과' and seen < r['expected']))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
