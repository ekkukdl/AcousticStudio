"""Validate T5 syntax/docs/provenance and the offline calibration artifacts."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name('t5_static_result.json')
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio.calibration import Calibration, layout_signature
from acousticstudio.geometry import validate_geometry
from acousticstudio.hardware import HardwareController


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
             'docs/ultraino_t5_result.md', '구상도/START_HERE.md', '구상도/creo_tunnel/README.md',
             '구상도/outputs/pcb/README.md']
    links = 0
    for name in names:
        path = REPO / name; content = path.read_text(encoding='utf-8')
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
    for name, expected in report('t4_numerical_result.json')['hashes'].items():
        assert digest(REPO / name) == expected, name
    pipeline = report('t5_pipeline_result.json')
    for name, expected in pipeline['hashes'].items():
        assert digest(REPO / name) == expected, name
    for name, expected in pipeline['source_hashes'].items():
        assert digest(REPO.parent / name) == expected, name
    assert not pipeline['physical_serial_opened'] and not pipeline['pressure_calibrated'] and not pipeline['hardware_measured']
    assert pipeline['candidate_mapping_csv_matches'] and pipeline['legacy_off_rejected']
    assert pipeline['qt_main_integration'] and pipeline['calibrated_gain_inputs'] and pipeline['project_restore']
    assert len(pipeline['protocol_cases']) == 12 and all(row['send_export_equal'] for row in pipeline['protocol_cases'])
    assert pipeline['force_guard']['gravity_equilibrium_status'] == 'unavailable_uncalibrated_pressure'
    project = report('t5_example_project.json')
    calibration = Calibration.from_dict(project['calibration'])
    assert calibration == Calibration.from_dict(report('t5_example_calibration.json'))
    for geometry in project['geometry_arrays']:
        validate_geometry(geometry)
    calibration.validate_context(len(project['transducers']), project['hardware_settings']['board_profile'],
                                 layout_signature(project['geometry_arrays'], project['transducers']))
    controller = HardwareController(); controller.restore_settings(project['hardware_settings'])
    assert controller.phase_offsets == list(calibration.phase_offsets_rad)
    assert controller.channel_map == list(calibration.channel_map)
    assert controller.active_channels == list(calibration.active)
    frame = Path(__file__).with_name('t5_example_frame.bin').read_bytes()
    assert len(frame) == 258 and frame[0] == 254 and frame[-1] == 253
    assert frame[1 + calibration.channel_map.index(2)] == 32
    suite = ET.parse(Path(__file__).with_name('t5_pytest.xml')).getroot().find('testsuite')
    assert suite is not None and suite.get('failures') == '0' and suite.get('errors') == '0'
    assert suite.get('tests') == '211' and suite.get('skipped') == '3'
    checked = subprocess.run(['git', '-c', 'core.safecrlf=false', 'diff', '--check'],
                             cwd=REPO, capture_output=True, text=True, encoding='utf-8')
    if checked.returncode: raise RuntimeError(checked.stdout + checked.stderr)
    result = dict(python=sys.executable, ast_files=len(python_files), utf8_documents=len(names), local_links=links,
                  native_hash_matches=True, t4_model_hashes_match=True, t5_input_hashes_match=True,
                  original_protocol_hashes_match=True, example_project_and_calibration_match=True,
                  protocol_cases=12, qt_main_verified=True, pytest_cases=211, pytest_passed=208, pytest_skipped=3,
                  pytest_failures=0, pytest_errors=0, git_diff_check=True)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
