"""Verify active Python syntax, handoff links/encoding, native and audit hashes."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name('t3_static_result.json')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    python_files = [REPO / 'main.py']
    for folder in ('src', 'tests', 'scratch/ultraino_migration'):
        python_files.extend(sorted((REPO / folder).rglob('*.py')))
    for path in python_files:
        ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    names = ['AGENTS.md', 'README.md', 'THIRD_PARTY_NOTICES.md', 'docs/project_status.txt',
             'docs/software_requirements.md', 'docs/ultraino_migration_plan.md',
             'docs/ultraino_t0_result.md', 'docs/ultraino_t1_result.md',
             'docs/ultraino_t2_result.md', 'docs/ultraino_t3_result.md',
             '구상도/START_HERE.md', '구상도/creo_tunnel/README.md', '구상도/outputs/pcb/README.md']
    links = 0
    for name in names:
        path = REPO / name
        content = path.read_text(encoding='utf-8')
        assert '\ufffd' not in content, name
        for match in re.finditer(r'\[[^\]\n]+\]\(([^)\n]+)\)', content):
            target = match.group(1).strip().strip('<>')
            if re.match(r'^[a-z]+://', target) or target.startswith('#'):
                continue
            target = (path.parent / target.split('#', 1)[0]).resolve()
            assert target.exists() or target == OUTPUT.resolve(), f'{name}: {target}'
            links += 1
    native = json.loads(Path(__file__).with_name('t2_native_result.json').read_text(encoding='utf-8'))
    assert digest(REPO / 'src/acousticstudio/sonic_core.cpp') == native['source_sha256']
    assert digest(REPO / 'src/acousticstudio/sonic_core.dll') == native['dll_sha256']
    numerical = json.loads(Path(__file__).with_name('t3_numerical_result.json').read_text(encoding='utf-8'))
    for name, expected in numerical['hashes'].items():
        assert digest(REPO / name) == expected, name
    suite = ET.parse(Path(__file__).with_name('t3_pytest.xml')).getroot().find('testsuite')
    assert suite is not None and suite.get('failures') == '0' and suite.get('errors') == '0'
    checked = subprocess.run(['git', '-c', 'core.safecrlf=false', 'diff', '--check'],
                             cwd=REPO, capture_output=True, text=True, encoding='utf-8')
    if checked.returncode:
        raise RuntimeError(checked.stdout + checked.stderr)
    report = dict(python=sys.executable, ast_files=len(python_files), utf8_documents=len(names),
                  local_links=links, native_hash_matches=True, numerical_input_hashes_match=True,
                  pytest_cases=int(suite.get('tests')), pytest_skipped=int(suite.get('skipped')),
                  pytest_failures=0, pytest_errors=0, git_diff_check=True)
    OUTPUT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
