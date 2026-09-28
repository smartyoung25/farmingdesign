"""뮤테이션 실행기 — 차수별 가드를 일부러 깨서 잡히는지 다시 잰다(265차 · 266차 보강).

  python mutations/run_all.py            # 전부(오래 걸린다 — 스크립트마다 pytest를 여러 번 돈다)
  python mutations/run_all.py 262 263    # 지정한 차수만(보충 스크립트 mut_NNNb.py도 함께)

한 스크립트마다:
  ① **원본 통과 확인** — 스크립트가 부르는 테스트 파일과 `-k` 선택자를 모아 먼저 돌린다. 실패하면 **무효**,
     선택자를 하나도 못 모으면 **건너뜀**(둘 다 실패로 친다 — 266차: 종전엔 건너뛰고도 「통과」로 적었다).
  ② **안전 복원(git 기준 · 스크립트가 손댈 수 있는 범위만)** — 실행 전 `git status`와 이미 바뀌어 있던 파일의 바이트를 저장하고,
     끝나면(시간 초과·예외 포함) 새로 바뀐 추적 파일은 되돌리고 새로 생긴 파일은 지운다(266차: 종전엔 스크립트가 **이름으로 부른**
     파일만 복원해 glob으로 얻은 경로·새로 만든 파일을 놓쳤다 — 레드팀 33회차 B4).
     🔴271차: 되돌리는 것은 **그 스크립트가 손댈 수 있는 경로**(소스의 문자열 리터럴이 가리키는 파일·glob 디렉터리 아래)뿐이다 —
     그 밖의 변경은 **손대지 않고 「외부 변경」으로 보고**한다. 268차 실행 중 **같은 리포에 붙은 다른 세션**이 고치던 파일을
     실행기가 HEAD로 되돌려 그쪽 작업을 지웠다(269차 ⑩). 실행 시작 때 작업 트리가 더럽혀 있으면 그 경로를 미리 알린다.
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


def touchable(src):
    """스크립트가 손댈 수 있는 경로 — 소스의 문자열 리터럴 가운데 **존재하는 파일**(그대로)과 glob 패턴의 **디렉터리**(접두).
    271차: 복원은 이 범위 안에서만 한다. 리터럴 밖에서 경로를 만드는 스크립트는 없다(223~270차 전수 — glob은 249·249b뿐)."""
    files, dirs = set(), set()
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        v = node.value.replace(os.sep, '/').strip('/')
        if not v or '\n' in v:
            continue
        if any(ch in v for ch in '*?[') and '/' in v:          # glob 패턴 — 존재하는 디렉터리 접두만(빈 접두 = 리포 전체라 안 받는다)
            d = v.split('*')[0].split('?')[0].split('[')[0].rsplit('/', 1)[0]
            if d and os.path.isdir(os.path.join(ROOT, d)):
                dirs.add(d + '/')
        elif os.path.isfile(os.path.join(ROOT, v)):
            files.add(v)
    # os.path.join('mutations', 'README.md')처럼 조각으로 부르는 경우 — 조각 둘을 이어 본다
    parts = [n.value for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    for a in parts:
        for b in parts:
            j = a.strip('/') + '/' + b.strip('/')
            if '\n' in j:
                continue
            if os.path.isfile(os.path.join(ROOT, j)):
                files.add(j)
            elif 'glob' in src and os.path.isdir(os.path.join(ROOT, j)):   # 249b: join('docs', 'work-orders', 'WO-008_*.md')
                dirs.add(j + '/')
    return files, dirs


def in_scope(path, scope):
    files, dirs = scope
    p = path.replace(os.sep, '/')
    return p in files or any(p.startswith(d) for d in dirs)


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
    """`git status` 항목 → {경로: 상태}. **`-z`로 읽는다** — 기본 출력은 한글 경로를 8진 이스케이프(`"\\354…"`)로 내서
    존재하지 않는 경로가 키가 됐다(레드팀 34회차 B1 — 뮤테이션 대상 대부분이 한글 파일명이라 복원이 헛돌았다)."""
    r = subprocess.run(['git', 'status', '--porcelain', '-uall', '-z'], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('git status 실패 — 복원 기준을 세울 수 없다: ' + r.stderr.decode('utf-8', 'replace').strip())
    st = {}
    items = r.stdout.decode('utf-8').split('\0')
    i = 0
    while i < len(items):
        ln = items[i]; i += 1
        if not ln:
            continue
        code, path = ln[:2], ln[3:]
        if code[0] in 'RC':                 # 이름 변경·복사: 다음 항목이 원래 경로
            i += 1
        st[path] = code
    return st


def _checkout(path):
    r = subprocess.run(['git', 'checkout', '--', path], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f'{path} 복원 실패: ' + r.stderr.decode('utf-8', 'replace').strip())


def restore(before, snap, scope=None):
    """실행 전 상태로 되돌린다 — (되돌린 경로, 손대지 않은 바깥 변경 경로)를 돌려준다.
    `scope`(touchable 결과)가 있으면 **그 범위 안의 경로만** 되돌린다 — 바깥은 다른 세션·사용자의 작업일 수 있다(271차)."""
    after = git_state()
    fixed, foreign = [], []
    for path, code in after.items():
        if before.get(path) == code and path not in snap:
            continue
        if scope is not None and not in_scope(path, scope):
            if path not in snap or open(path, 'rb').read() != snap[path]:
                foreign.append(path)
            continue
        if path in snap:                                   # 원래 바뀌어 있던 파일 — 저장한 바이트로
            if not os.path.exists(path) or open(path, 'rb').read() != snap[path]:
                open(path, 'wb').write(snap[path]); fixed.append(path)
        elif code == '??':                                  # 새로 생긴 파일 — 지운다
            if os.path.exists(path):
                os.remove(path)
            fixed.append(path)
        else:                                               # 깨끗했던 추적 파일 — 커밋 상태로(실패는 요란하게)
            _checkout(path); fixed.append(path)
    for path, data in snap.items():                         # 원래 있던 파일이 지워진 경우
        if not os.path.exists(path):
            if scope is not None and not in_scope(path, scope):
                foreign.append(path); continue
            open(path, 'wb').write(data); fixed.append(path)
    return fixed, foreign


def run_one(path):
    src = open(path, encoding='utf-8').read()
    num = num_of(path)
    res = {'baseline': '통과', 'caught': 0, 'missed': 0, 'known': 0, 'stale': 0, 'error': '',
           'restored': [], 'foreign': [], 'missed_names': [], 'expected': expected_count(src)}
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
        res['restored'], res['foreign'] = restore(before, snap, touchable(src))
    return res


def main(argv):
    want = set(argv)
    paths = sorted(glob.glob(os.path.join(ROOT, 'mutations', 'mut_*.py')))
    paths = [p for p in paths if not want or num_of(p) in want]
    bad = False
    dirty = git_state()
    if dirty:
        print(f'⚠️작업 트리에 실행 전 변경 {len(dirty)}건 — 실행기는 스크립트 범위 밖의 파일에 손대지 않는다: ' + ', '.join(sorted(dirty)))
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
        if r['baseline'] == '통과' and seen != r['expected']:
            notes.append(f'🔴{"누락" if seen < r["expected"] else "초과 집계"} {abs(r["expected"] - seen)}(선언 {r["expected"]} · 집계 {seen})')
        if r['baseline'] == '통과' and r['caught'] == 0:
            notes.append('⚠️살아서 잡는 뮤테이션 0 — 가드를 지금 상태로 다시 재야 한다')
        if r['restored']:
            notes.append('복원: ' + ', '.join(r['restored']))
        if r['foreign']:
            notes.append('⚠️외부 변경(손대지 않음): ' + ', '.join(r['foreign']))
        print(f"{os.path.basename(p)[:-3]} | {r['baseline']} | {r['caught']} | {r['missed']} | {r['known']} | {r['stale']} | "
              f"{r['expected']} | {' · '.join(notes)} ({time.time() - t0:.0f}s)", flush=True)
        bad |= (r['baseline'] != '통과' or r['missed'] > 0 or bool(r['error'])
                or (r['baseline'] == '통과' and seen != r['expected']))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
