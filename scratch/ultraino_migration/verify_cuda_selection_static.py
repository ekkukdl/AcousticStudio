"""Audit optional CUDA selection without installing packages or opening hardware."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name('cuda_selection_result.json')
SOURCE_NAMES = [
    'src/acousticstudio/cuda_protocol.py', 'src/acousticstudio/cuda_runtime.py',
    'src/acousticstudio/cuda_worker.py', 'src/acousticstudio/compute_devices.py',
    'src/acousticstudio/field_backends.py', 'src/acousticstudio/sonic_wrapper.py',
    'src/acousticstudio/installer_ui.py', 'src/acousticstudio/app.py',
    'tests/test_compute_devices.py', 'tests/test_cuda_selection.py',
]
DOCUMENT_NAMES = [
    'AGENTS.md', 'README.md', 'docs/project_status.txt',
    'docs/cuda_optional_selection.md', 'docs/multitrap_cuda_diagnosis.md',
    'docs/ultraino_migration_plan.md', 'docs/ultraino_t5_result.md',
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_report(name):
    return json.loads(Path(__file__).with_name(name).read_text(encoding='utf-8'))


def run(command):
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                            encoding='utf-8', errors='strict', timeout=30)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip()


def main():
    syntax_names = SOURCE_NAMES + [str(Path(__file__).relative_to(REPO)).replace('\\', '/')]
    for name in syntax_names:
        content = (REPO / name).read_text(encoding='utf-8-sig')
        assert '\ufffd' not in content, name
        ast.parse(content, filename=name)
    links = 0
    for name in DOCUMENT_NAMES:
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
    native = read_report('t2_native_result.json')
    assert digest(REPO / 'src/acousticstudio/sonic_core.cpp') == native['source_sha256']
    assert digest(REPO / 'src/acousticstudio/sonic_core.dll') == native['dll_sha256']
    preserved = {}
    for name, expected in read_report('t4_numerical_result.json')['hashes'].items():
        assert digest(REPO / name) == expected, name
        preserved[name] = expected
    t5 = read_report('t5_pipeline_result.json')
    for name, expected in t5['hashes'].items():
        if name == 'src/acousticstudio/app.py':
            continue  # The selection UI deliberately changed since T5.
        assert digest(REPO / name) == expected, name
        preserved[name] = expected
    for name, expected in t5['source_hashes'].items():
        assert digest(REPO.parent / name) == expected, name
    junit_path = Path(__file__).with_name('cuda_selection_pytest.xml')
    suite = ET.parse(junit_path).getroot().find('testsuite')
    assert suite is not None
    cases = len(suite.findall('testcase'))
    assert cases == int(suite.get('tests')) == 230
    assert int(suite.get('skipped')) == 3
    assert int(suite.get('failures')) == int(suite.get('errors')) == 0
    selection_cases = [case for case in suite.findall('testcase')
                       if case.get('classname') == 'tests.test_cuda_selection']
    assert len(selection_cases) == 10
    environment = json.loads(run([sys.executable, '-c',
        'import json, sys, torch; print(json.dumps(dict(python=sys.executable, '
        'python_version=sys.version.split()[0], torch_version=str(torch.__version__), '
        'torch_cuda_build=torch.version.cuda, cuda_available=bool(torch.cuda.is_available()))))']))
    runtime_path = REPO / 'runtime' / 'torch_cuda'
    environment['isolated_runtime_directory_exists'] = runtime_path.exists()
    smi = shutil.which('nvidia-smi')
    environment['nvidia_smi'] = (run([smi, '--query-gpu=name,driver_version', '--format=csv,noheader'])
                                 if smi is not None else None)
    run(['git', '-c', 'core.safecrlf=false', 'diff', '--check'])
    historic_names = [
        'multitrap_compute_result.json', 'multitrap_compute_pytest.xml',
        't5_pipeline_result.json', 't5_static_result.json', 't5_pytest.xml',
    ]
    result = dict(
        audited_at_utc=datetime.now(timezone.utc).isoformat(),
        environment=environment,
        ast_files=len(syntax_names), utf8_documents=len(DOCUMENT_NAMES), local_links=links,
        source_hashes={name: digest(REPO / name) for name in syntax_names},
        preserved_model_calibration_native_hashes=preserved,
        original_protocol_hashes_match=True,
        historic_artifact_hashes={name: digest(Path(__file__).with_name(name)) for name in historic_names},
        pytest=dict(cases=cases, passed=227, skipped=3, failures=0, errors=0,
                    cuda_selection_cases=len(selection_cases), timestamp=suite.get('timestamp'),
                    seconds=float(suite.get('time')), junit_sha256=digest(junit_path),
                    cuda_and_pip_test_implementation='fake; real Qt/QThread and Python pipes'),
        actual_cuda_package_install_performed=False,
        actual_pytorch_cuda_kernel_verified=False, physical_serial_opened=False,
        t6_complete=False, git_diff_check=True, git_head=run(['git', 'rev-parse', 'HEAD']),
    )
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(report=str(OUTPUT.relative_to(REPO)), ast_files=len(syntax_names),
                         local_links=links, pytest_passed=227, pytest_skipped=3,
                         preserved_hashes=len(preserved), environment=environment,
                         git_diff_check=True), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
