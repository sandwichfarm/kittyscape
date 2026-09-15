"""Assemble verified runtime evidence without changing archived source inputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import time

ROOT = Path('/home/sandwich/Develop/kittyscape')
OUT = ROOT / 'evidence/4d304c7c23dc'
ARCHIVE = ROOT / 'dist/kittyscape-0.1.0.dev1.tar.gz'
SHA = '4d304c7c23dc343addd42500a05ca7c7607b3b5641ff60bae9324b99eb3a251a'
BUNDLE = Path('/tmp/kittyscape-final-source-z3w7nldt/kittyscape-0.1.0.dev1')


def read(path):
    return json.loads(Path(path).read_text())


def advanced(source, name):
    report = read(source / 'result.json')
    assert report['artifact']['sha256'] == SHA and report['error'] is None
    assert len(report['cases']) == 16 and all(c['status'] == 'passed' for c in report['cases'])
    assert sum(len(c['scenarios']) for c in report['cases']) == 37
    replacements = {source: '$ADVANCED', BUNDLE: '$BUNDLE', ARCHIVE: '$ARCHIVE'}
    for case in report['cases']:
        replacements[Path(case['evidence'])] = '$FIXTURE/' + case['case']
    spec = importlib.util.spec_from_file_location('matrix', ROOT / 'scripts/qualify_release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.preserve(source, OUT / name, replacements)
    for case in report['cases']:
        module.preserve(Path(case['evidence']), OUT / name / case['case'], replacements)
    return {'backend': report['backend'], 'cases': 16, 'scenarios': 37, 'status': 'passed',
            'evidence': 'qualification/' + name + '/result.json'}


def matrix():
    rows = []
    for backend in ('x11', 'wayland'):
        metadata = read(OUT / backend / 'matrix.json')
        assert metadata['sha256'] == SHA and len(metadata['rows']) == 48
        for row in metadata['rows']:
            assert row['result'] == 'pass'
            result = read(OUT / backend / row['evidence'])
            assert result['artifact']['sha256'] == SHA and result['error'] is None
            folder = (OUT / backend / row['evidence']).parent
            shots = ['qualification/' + str(p.relative_to(OUT)) for p in sorted(folder.glob('*.png'))
                     if p.name not in ('A.png', 'B.png', 'baseline.png')]
            rows.append({'id': row['id'], 'status': 'passed',
                         'evidence': 'qualification/' + backend + '/' + row['evidence'], 'screenshots': shots})
    assert len({row['id'] for row in rows}) == 96
    return rows


def sanitize(text):
    text = text.replace(str(ROOT), '$PROJECT').replace(str(BUNDLE), '$BUNDLE')
    text = text.replace('/home/sandwich', '$USER_HOME')
    return re.sub(r'(Unknown OSC escape code: 3008;)[^\n]*', r'\1[profile metadata redacted]', text)


def public_copy():
    target = ROOT / 'docs/public/evidence/qualification'
    selected = ('x11', 'wayland', 'advanced-x11', 'advanced-wayland', 'performance', 'arch-kitty',
                'tool-provenance', 'isolation', 'old-reload', 'checks.json', 'environment.json',
                'resolver-performance.json')
    for name in selected:
        source = OUT / name
        if not source.exists():
            continue
        files = [source] if source.is_file() else [p for p in source.rglob('*') if p.is_file()]
        for path in files:
            dest = target / path.relative_to(OUT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == '.png':
                shutil.copy2(path, dest)
            else:
                dest.write_text(sanitize(path.read_text()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--advanced-wayland', type=Path, required=True)
    args = parser.parse_args()
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == SHA
    rows = matrix()
    extra = [advanced(Path('/tmp/kittyscape-extended-xa58yez1'), 'advanced-x11'),
             advanced(args.advanced_wayland, 'advanced-wayland')]
    performance = read(OUT / 'performance/result.json')
    assert performance['artifact']['sha256'] == SHA and performance['error'] is None
    timing = next(r['detail'] for r in performance['scenarios'] if r['scenario'] == 'performance-100-transitions')
    idle = next(r['detail'] for r in performance['scenarios'] if r['scenario'] == 'T14-idle-60-seconds')
    assert timing['count'] == 100 and timing['p95_ms'] < 250 and idle == {'scheduled_timers': 0, 'image_writes': 0}
    profile = read('/tmp/kittyscape-private-wayland-27ldgord/renderer-profile.json')
    record = {
        'schema': 1, 'version': '0.1.0.dev1', 'status': 'linux-qualified-macos-open',
        'checked_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'artifact': {'name': ARCHIVE.name, 'sha256': SHA,
                     'manifest_sha256': hashlib.sha256((BUNDLE / 'manifest.json').read_bytes()).hexdigest()},
        'matrix': rows, 'advanced': extra, 'checks': read(OUT / 'checks.json'),
        'performance': {'transitions': timing['count'], 'display_p95_ms': timing['p95_ms'],
                        'idle_seconds': 60, **idle, 'resolver': read(OUT / 'resolver-performance.json')},
        'wayland_profile': profile,
        'additional_profiles': [
            {'profile': 'Old kitty native config reload retains original PNG and adopts new layout',
             'evidence': 'qualification/old-reload/' + backend + '/result.json'} for backend in ('x11', 'wayland')
        ],
        'scope': [
            'Linux x86_64; exact named kitty and shell builds, interactive and login startup, no-image and single-PNG baselines.',
            'Wayland uses a private Hyprland compositor, tiled visible windows on workspace15, Mesa software rendering and the explicitly identified host Wayland client preload.',
            'Advanced unsupported-context cases use local command/environment/OSC fixtures; they do not qualify real SSH, containers or multiplexers.',
            'Use a fresh matrix output directory when graphics libraries or compositor settings change; cached rows bind the archive and executable builds.',
            'Browser verification receipts are delivered separately; no live screen-reader session is claimed.'
        ],
        'open_gates': [{'target': 'macOS arm64', 'status': 'open',
                        'reason': 'No Mac is available; the user explicitly left this qualification gate open.'}],
        'publication': 'Local artifacts only. No deployment, publication, repository initialization or project-license selection.',
    }
    (OUT / 'release.json').write_text(json.dumps(record, indent=2) + '\n')
    public_copy()
    (ROOT / 'docs/public/evidence/release.json').write_text(sanitize(json.dumps(record, indent=2)) + '\n')
    for row in rows + extra:
        assert (ROOT / 'docs/public/evidence' / row['evidence']).is_file(), row
        for shot in row.get('screenshots', []):
            assert (ROOT / 'docs/public/evidence' / shot).is_file(), shot
    print(json.dumps({'rows': len(rows), 'advanced_scenarios': sum(e['scenarios'] for e in extra), 'sha256': SHA}))


if __name__ == '__main__':
    main()
