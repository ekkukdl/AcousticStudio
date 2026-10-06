"""Reorganize project artifacts without deleting files or moving local runtimes."""
from pathlib import Path
import ast
import hashlib
import json
import re

BASE = Path(__file__).resolve().parents[2]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def tracked_files():
    for folder in ('creo_tunnel', 'outputs', 'scratch'):
        for p in (BASE / folder).rglob('*'):
            if 'node_modules' in p.parts or 'creo_cad_env' in p.parts:
                continue
            if p.is_file():
                yield p

def main():
    before = {p.relative_to(BASE).as_posix(): digest(p) for p in tracked_files()}
    moves = {
        'outputs/pcb/polygon_panels': 'outputs/pcb/polygon_panels',
        'outputs/cad_generation/creo_tunnel_models': 'outputs/cad_generation/creo_tunnel_models',
        'outputs/cad_generation/creo_tunnel_reused_v2': 'outputs/cad_generation/creo_tunnel_reused_v2',
        'outputs/reference_analysis/sonicsurface_analysis': 'outputs/reference_analysis/sonicsurface_analysis',
        'outputs/concepts/tunnel_128_concept': 'outputs/concepts/tunnel_128_concept',
        'outputs/budgets/levitation_128': 'outputs/budgets/levitation_128',
        'outputs/vendor_templates/DOILLABS_BOM_Template.xlsx': 'outputs/vendor_templates/DOILLABS_BOM_Template.xlsx',
        'outputs/vendor_templates/DOILLABS_PnP_Template.xlsx': 'outputs/vendor_templates/DOILLABS_PnP_Template.xlsx',
        'scratch/pcba_inputs/pcba_parts_8f.json': 'scratch/pcba_inputs/pcba_parts_8f.json',
        'scratch/pcba_inputs/pcba_native_smt.csv': 'scratch/pcba_inputs/pcba_native_smt.csv',
    }
    for p in (BASE / 'outputs').glob('*.zip'):
        moves[p.relative_to(BASE).as_posix()] = 'outputs/pcb/' + p.name
    for p in (BASE / 'outputs').glob('*.md'):
        moves[p.relative_to(BASE).as_posix()] = 'outputs/docs/' + p.name
    for p in (BASE / 'scratch').glob('*.js'):
        moves[p.relative_to(BASE).as_posix()] = 'scratch/vendor_research/' + p.name
    for p in (BASE / 'scratch').glob('*.py'):
        if p.name in {'extract_pcba_parts.py', 'prepare_pcba_package.py', 'verify_package_pcba.py', 'package_gerber_quotes.py'}:
            group = 'pcba_scripts'
        elif p.name in {'move_project_artifacts.py', 'organize_creo_in_acousticstudio.py', 'check_organized_creo.py', 'check_git_model_index.py'}:
            group = 'organization/history'
        elif p.name == 'inspect_doillabs_public_page.py':
            group = 'vendor_research'
        else:
            group = 'creo_scripts'
        moves[p.relative_to(BASE).as_posix()] = 'scratch/' + group + '/' + p.name
    for old, new in moves.items():
        source, dest = BASE / old, BASE / new
        assert source.resolve().is_relative_to(BASE) and dest.resolve().is_relative_to(BASE)
        assert source.exists() and not dest.exists(), (old, new)
    for old, new in moves.items():
        source, dest = BASE / old, BASE / new
        dest.parent.mkdir(parents=True, exist_ok=True)
        source.rename(dest)

    def relocated(old):
        for src, dst in sorted(moves.items(), key=lambda x: -len(x[0])):
            if old == src or old.startswith(src + '/'):
                return dst + old[len(src):]
        return old

    edits = []
    for old in before:
        p = BASE / relocated(old)
        if p.suffix not in {'.py', '.mjs', '.ps1', '.md', '.txt'}:
            continue
        raw = p.read_bytes()
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        updated = content
        # Relocate explicit path literals in scripts and guidance, leaving native
        # models, spreadsheets, ZIPs, JSON and historical hash records untouched.
        for src, dst in sorted(moves.items(), key=lambda x: -len(x[0])):
            updated = updated.replace(src, dst)
            updated = updated.replace(src.replace('/', '\\\\'), dst.replace('/', '\\\\'))
        if old in moves and p.suffix == '.py':
            extra = len(Path(moves[old]).parts) - len(Path(old).parts)
            updated = re.sub(r'(Path\(__file__\)\.resolve\(\)\.parents\[)(\d+)(\])',
                             lambda m: m[1] + str(int(m[2]) + extra) + m[3], updated)
        if updated != content:
            p.write_bytes(updated.encode('utf-8'))
            edits.append(relocated(old))
    results = []
    for old, sha in before.items():
        new = relocated(old)
        p = BASE / new
        assert p.is_file(), new
        current = digest(p)
        assert current == sha or new in edits, new
        results.append({'before': old, 'after': new, 'sha256_before': sha,
                        'sha256_after': current, 'path_text_updated': new in edits})
    for p in tracked_files():
        if p.suffix == '.py':
            ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p))
    report = {'date': '2026-10-06', 'files_checked': len(results),
              'moves': moves, 'text_updates': edits, 'files': results,
              'runtime_folders_unchanged': ['scratch/creo_cad_env', 'scratch/pcba_artifact/node_modules'],
              'verification': 'All original files exist; SHA-256 unchanged except listed path-text updates. Python syntax checked. No CAD or manufacturing generation run.'}
    (BASE / 'scratch/organization/organization_verification_20261006.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'checked': len(results), 'moved_items': len(moves), 'text_updates': edits}, ensure_ascii=False))

if __name__ == '__main__':
    main()
