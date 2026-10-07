"""Check T4 syntax, handoff links, audit provenance and completed verification."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name('t4_static_result.json')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(name):
    return json.loads(Path(__file__).with_name(name).read_text(encoding='utf-8'))


def main():
    python_files = [REPO / 'main.py']
    for folder in ('src', 'tests', 'scratch/ultraino_migration'):
        python_files.extend(sorted((REPO / folder).rglob('*.py')))
    for path in python_files:
        content = path.read_text(encoding='utf-8-sig')
        assert '\ufffd' not in content, path
        ast.parse(content, filename=str(path))
    names = ['AGENTS.md', 'README.md', 'THIRD_PARTY_NOTICES.md', 'docs/project_status.txt',
             'docs/software_requirements.md', 'docs/ultraino_migration_plan.md',
             'docs/ultraino_t0_result.md', 'docs/ultraino_t1_result.md',
             'docs/ultraino_t2_result.md', 'docs/ultraino_t3_result.md', 'docs/ultraino_t4_result.md',
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
    native = report('t2_native_result.json')
    assert digest(REPO / 'src/acousticstudio/sonic_core.cpp') == native['source_sha256']
    assert digest(REPO / 'src/acousticstudio/sonic_core.dll') == native['dll_sha256']
    numerical = report('t4_numerical_result.json')
    for name, expected in numerical['hashes'].items():
        assert digest(REPO / name) == expected, name
    assert not numerical['pressure_calibrated'] and not numerical['hardware_used']
    comparisons, diagnoses = numerical['comparisons'], numerical['signed_force_diagnoses']
    assert len(comparisons) == 36 and len(diagnoses) == 18
    assert all(row['phase_phasor_error_after_common_phase'] < 1e-8
               and row['relative_field_error'] < 1e-8 for row in comparisons)
    assert all(row['converged'] and not row['pressure_calibrated']
               and row['gravity_equilibrium_status'] == 'unavailable_uncalibrated_pressure'
               for row in diagnoses)
    original = REPO.parent / 'simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/algorithms/Kinoforms.java'
    java = report('t4_java_result.json')
    assert java['original_source_unchanged'] and digest(original) == java['original_kinoforms_sha256']
    assert len(java['comparisons']) == 3
    assert all(row['phase_phasor_error_after_common_phase'] < 1e-5 for row in java['comparisons'])
    ui = report('t4_ui_result.json')
    assert ui['channels'] == 256 and not ui['serial_connected'] and not ui['pressure_calibrated']
    assert all(ui[name] for name in ('qt_main_integration', 'mixed_target_apply', 'live_worker',
                                    'latest_input_stale_rejected', 'settings_and_target_save_restore',
                                    'inactive_target_save_restore', 'main_close_during_job',
                                    'warm_cache', 'qt_dialog_capture'))
    assert len(ui['candidate_force_checks']) == 3
    assert not ui['qt_viewport_capture']
    suite = ET.parse(Path(__file__).with_name('t4_pytest.xml')).getroot().find('testsuite')
    assert suite is not None and suite.get('failures') == '0' and suite.get('errors') == '0'
    assert suite.get('tests') == '174' and suite.get('skipped') == '3'
    checked = subprocess.run(['git', '-c', 'core.safecrlf=false', 'diff', '--check'],
                             cwd=REPO, capture_output=True, text=True, encoding='utf-8')
    if checked.returncode:
        raise RuntimeError(checked.stdout + checked.stderr)
    result = dict(python=sys.executable, ast_files=len(python_files), utf8_documents=len(names),
                  local_links=links, native_hash_matches=True, numerical_input_hashes_match=True,
                  original_java_hash_matches=True, backend_cases=len(comparisons),
                  signed_force_diagnoses=len(diagnoses), qt_verification_matches=True,
                  pytest_cases=int(suite.get('tests')), pytest_passed=171, pytest_skipped=3,
                  pytest_failures=0, pytest_errors=0, git_diff_check=True)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
