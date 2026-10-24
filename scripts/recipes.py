#!/usr/bin/env python3
"""Install and serve the recorded local inference recipes (Python stdlib only)."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / '.venv'
RUNTIME = ROOT / '.runtime'
MODEL_ROOT = Path(os.environ.get('RECIPES_MODEL_DIR', str(Path.home() / '.freetoken/models'))).expanduser()


def read_json(path):
    return json.loads(Path(path).read_text())


def profile(name):
    return read_json(ROOT / 'profiles' / (name + '.json'))


def run(command, **kwargs):
    print('+ ' + shlex.join(map(str, command)), flush=True)
    return subprocess.run(list(map(str, command)), check=True, **kwargs)


def python_bin(required=True):
    result = VENV / 'bin/python'
    if required and not result.exists():
        raise RuntimeError('Primero ejecuta: python3 scripts/recipes.py install')
    return result


def install(with_flint):
    lock = read_json(ROOT / 'runtime.json')
    if not shutil.which('uv'):
        raise RuntimeError('Instala uv siguiendo https://docs.astral.sh/uv/getting-started/installation/')
    if not VENV.exists():
        run(['uv', 'venv', '--python', '3.12', VENV])
    wheels = RUNTIME / 'wheels'
    wheels.mkdir(parents=True, exist_ok=True)
    paths = []
    for item in lock['wheels']:
        path = wheels / item['filename']
        if not path.exists():
            partial = path.with_suffix('.partial')
            urllib.request.urlretrieve(item['url'], partial)
            partial.replace(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item['sha256']:
            raise RuntimeError(f'Checksum incorrecto: {path}; retira ese archivo y repite')
        paths.append(path)
    constraints = ROOT / 'constraints-validated.txt'
    if not constraints.exists():
        constraints = ROOT / 'constraints.txt'
    run(['uv', 'pip', 'install', '--python', python_bin(), '--constraint', constraints,
         str(paths[0]) + '[accel]', paths[1]])
    # FlashInfer's Python package alone falls back to nvcc JIT. The recorded
    # machine used both official binary caches, so install them explicitly.
    acceleration = []
    for item in lock.get('flashinfer_wheels', []):
        path = wheels / item['filename']
        verified_download(item, path)
        acceleration.append(path)
    if acceleration:
        run(['uv', 'pip', 'install', '--python', python_bin(), '--constraint', constraints, *acceleration])
    if with_flint:
        overlay = RUNTIME / 'FreeToken-flint'
        item = lock['flint_overlay']
        if not overlay.exists():
            run(['git', 'init', overlay])
            run(['git', '-C', overlay, 'remote', 'add', 'origin', item['repository']])
        run(['git', '-C', overlay, 'fetch', '--depth', '1', 'origin', item['commit']])
        run(['git', '-C', overlay, 'checkout', '--detach', item['commit']])
        installed = subprocess.check_output([str(python_bin()), '-c',
            'import importlib.util; from pathlib import Path; '
            'print(Path(importlib.util.find_spec("freetoken").origin).parent)'], text=True).strip()
        source = overlay / 'python/freetoken'
        # The reviewed overlay changes Python only; reuse the pinned wheel's native ABI.
        for library in (Path(installed) / 'kernel').rglob('*.so'):
            target = source / library.relative_to(installed)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() and not target.is_symlink():
                target.symlink_to(library)
    with (RUNTIME / 'installed-packages.txt').open('w') as output:
        run(['uv', 'pip', 'freeze', '--python', python_bin()], stdout=output)
    print('Engine preparado. El overlay Flint se aplica solo al servir Flint.' if with_flint else 'Engine preparado.')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verified_download(item, destination, existing=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        partial = destination.with_name(destination.name + '.partial')
        if existing and existing.is_file() and sha256(existing) == item['sha256']:
            shutil.copyfile(existing, partial)
        else:
            urllib.request.urlretrieve(item['url'], partial)
        if sha256(partial) != item['sha256']:
            raise RuntimeError(f'SHA-256 mismatch: {partial}')
        partial.replace(destination)
    if sha256(destination) != item['sha256']:
        raise RuntimeError(f'SHA-256 mismatch: {destination}')


def install_llama():
    lock = read_json(ROOT / 'runtime.json')['llama_cpp']
    directory = RUNTIME / 'llama-cpp'
    for item in lock['archives']:
        archive = directory / 'archives' / item['filename']
        legacy = ('llama-b11828-cuda13.tar.gz' if item['filename'].startswith('llama-')
                  else 'cudart-b11828-cuda13.tar.gz')
        verified_download(item, archive, Path.home() / 'Desktop/AI/bin' / legacy)
        with tarfile.open(archive) as source:
            source.extractall(directory, filter='data')
    print('llama.cpp b11828 CUDA 13.4 installed; archive SHA-256 verified.')


def llama_paths():
    lock = read_json(ROOT / 'runtime.json')['llama_cpp']
    directory = RUNTIME / 'llama-cpp'
    return directory / lock['server_directory'], directory / lock['cuda_directory']


def model_path(p):
    folder = MODEL_ROOT / p['model']['local_directory']
    if p['engine'] == 'llama-cpp' and not (folder / p['model']['filename']).exists():
        existing = Path.home() / 'Desktop/AI/models' / p['model']['filename']
        if existing.is_file():
            return existing
    return folder / p['model']['filename'] if p['model'].get('filename') else folder


def drafter_path(p):
    result = MODEL_ROOT / p['model']['local_directory'] / p['drafter']['filename']
    if not result.exists():
        existing = Path.home() / 'Desktop/AI/models' / p['drafter']['legacy_local_filename']
        if existing.is_file():
            return existing
    return result


def complete_model(p):
    path = model_path(p)
    if p['model'].get('filename'):
        return path.is_file() and path.stat().st_size == p['model']['file_bytes']
    try:
        index = read_json(path / 'model.safetensors.index.json')
        return (path / 'config.json').is_file() and (path / 'tokenizer.json').is_file() and all(
            (path / name).is_file() for name in set(index['weight_map'].values()))
    except (OSError, KeyError, ValueError):
        return False


def download(p):
    if p['engine'] == 'llama-cpp':
        for item, destination in [(p['model'], model_path(p)), (p['drafter'], drafter_path(p))]:
            blob = {**item, 'url': 'https://huggingface.co/' + item['repository'] + '/resolve/'
                    + item['download_revision'] + '/' + item['filename']}
            verified_download(blob, destination)
            print(f'Verified weights: {destination}')
        return
    if complete_model(p):
        print(f'Reutilizando pesos locales: {model_path(p)}')
        print('La existencia de los shards no certifica su revisión; consulta evidence/inventory.json.')
        return
    dest = MODEL_ROOT / p['model']['local_directory']
    data = {'repo_id': p['model']['repository'], 'revision': p['model']['download_revision'],
            'local_dir': str(dest), 'allow_patterns': p['model']['download_patterns']}
    code = 'import json,sys; from huggingface_hub import snapshot_download; snapshot_download(**json.loads(sys.argv[1]))'
    run([python_bin(), '-c', code, json.dumps(data)])
    if not complete_model(p):
        raise RuntimeError('La descarga no contiene todos los archivos esperados')


def select_gpu(explicit):
    if explicit:
        return explicit
    result = subprocess.check_output(['nvidia-smi', '--query-gpu=uuid,name', '--format=csv,noheader'], text=True)
    candidates = [line.split(',', 1)[0].strip() for line in result.splitlines()
                  if 'RTX 3060' in line and '3060 Ti' not in line]
    if len(candidates) != 1:
        raise RuntimeError('No se ha encontrado una única RTX 3060; indica --gpu UUID')
    return candidates[0]


def request_json(base, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.load(response)


def serve(p, args):
    path = model_path(p)
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    is_llama = p['engine'] == 'llama-cpp'
    if is_llama:
        binary, cuda = llama_paths()
        if not args.print_command and not (binary / 'llama-server').is_file():
            raise RuntimeError('Run ./recipes install --llama-cpp first')
        env['LD_LIBRARY_PATH'] = os.pathsep.join(filter(None, [str(cuda), str(binary), env.get('LD_LIBRARY_PATH')]))
        command = [str(binary / 'llama-server'), '-m', str(path), '-md', str(drafter_path(p)),
                   '--host', '127.0.0.1', '--port', str(args.port), '--alias', p['id'], *p['server_arguments']]
    else:
        command = [str(python_bin(required=not args.print_command)), '-m', 'freetoken.cli', 'serve', '--model-path', str(path),
                   '--gpu', '0', '--host', '127.0.0.1', '--port', str(args.port),
                   '--served-model-name', p['id'], *p['server_arguments']]
    if p['engine'] == 'flint-overlay':
        source = RUNTIME / 'FreeToken-flint/python'
        if not (source / 'freetoken/models/flint/model.py').exists():
            raise RuntimeError('Primero ejecuta: python3 scripts/recipes.py install --flint')
        env['PYTHONPATH'] = str(source)
        env.update(p.get('environment', {}))
    if not args.print_command:
        if not complete_model(p):
            raise RuntimeError(f'Faltan pesos en {path}; ejecuta download {p["id"]}')
        if is_llama and (not drafter_path(p).is_file() or sha256(path) != p['model']['sha256']
                         or sha256(drafter_path(p)) != p['drafter']['sha256']):
            raise RuntimeError('Missing or unverified Nemotron weights; run download nemotron')
        env['CUDA_VISIBLE_DEVICES'] = select_gpu(args.gpu)
    else:
        env['CUDA_VISIBLE_DEVICES'] = args.gpu or '<UUID de la RTX 3060>'
        selected = {k: env[k] for k in ['CUDA_VISIBLE_DEVICES', 'PYTHONPATH', 'FLASHINFER_USE_CUDA_NORM', 'LD_LIBRARY_PATH'] if k in env}
        print(' '.join(k + '=' + shlex.quote(v) for k, v in selected.items()), shlex.join(command))
        print('Reconstrucción posterior:', json.dumps(p.get('cache_rebuild')))
        return
    # Check the API and the engine rendezvous before owning any child processes.
    for port in ([args.port] if is_llama else [args.port, args.port + 1]):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    print('+ ' + shlex.join(command), flush=True)
    process = subprocess.Popen(command, env=env, start_new_session=True)
    base = f'http://127.0.0.1:{args.port}'
    try:
        deadline = time.monotonic() + args.startup_timeout
        while time.monotonic() < deadline and process.poll() is None:
            try:
                status = request_json(base, '/health' if is_llama else '/v1/cache/status')
                if (status.get('status') == 'ok' if is_llama else status.get('state') == 'serving'):
                    break
            except (OSError, ValueError):
                pass
            time.sleep(.5)
        else:
            raise RuntimeError('El engine no ha terminado de cargar; consulta su log')
        if p.get('cache_rebuild'):
            result = request_json(base, '/v1/cache/rebuild', p['cache_rebuild'])
            if result.get('status') != 'ok':
                raise RuntimeError(f'No se ha aplicado la geometría: {result}')
        print(f'LISTO: {p["id"]} en {base}/v1 (una generación simultánea)', flush=True)
        process.wait()
        if process.returncode:
            raise RuntimeError(f'Engine terminado con código {process.returncode}')
    except KeyboardInterrupt:
        pass
    finally:
        # Also clean worker descendants if the frontend has already exited.
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def desktop(p, args):
    if p['engine'] == 'llama-cpp':
        raise RuntimeError('Nemotron uses llama.cpp; this recipe has no FreeToken Desktop profile.')
    path = Path(args.config).expanduser()
    original = path.read_bytes()
    data = json.loads(original)
    data.setdefault('cacheProfiles', {})[p['model']['local_directory']] = p['desktop_cache']
    models = data.setdefault('textOnlyModels', [])
    if p['model']['local_directory'] not in models:
        models.append(p['model']['local_directory'])
    if not args.apply:
        print(json.dumps({'cacheProfiles': {p['model']['local_directory']: p['desktop_cache']},
                          'textOnlyModels': [p['model']['local_directory']]}, indent=2))
        print('Para guardar con copia previa: añade --apply. Cierra Desktop antes.')
        return
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = path.with_name(path.name + '.recipes-backup-' + stamp)
    shutil.copy2(path, backup)
    temporary = path.with_name(path.name + '.recipes-tmp-' + stamp)
    with temporary.open('x') as output:
        output.write(json.dumps(data, indent=2) + '\n')
    temporary.chmod(path.stat().st_mode & 0o777)
    if path.read_bytes() != original:
        temporary.unlink()
        raise RuntimeError('Desktop modificó la configuración; ciérralo y repite')
    temporary.replace(path)
    print(f'Perfil guardado; copia previa: {backup}')
    print('Los ajustes globales y el engine de Desktop no se cambian. Consulta docs/desktop.md.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    setup = commands.add_parser('install')
    setup.add_argument('--flint', action='store_true')
    setup.add_argument('--llama-cpp', action='store_true', help='Install the pinned engine for Nemotron')
    for command in ['download', 'show', 'serve', 'desktop']:
        sub = commands.add_parser(command)
        sub.add_argument('model', choices=sorted(p.stem for p in (ROOT / 'profiles').glob('*.json')))
        if command == 'serve':
            sub.add_argument('--port', type=int, default=1919)
            sub.add_argument('--gpu', help='UUID NVIDIA; por defecto detecta la RTX 3060')
            sub.add_argument('--startup-timeout', type=int, default=600)
            sub.add_argument('--print-command', action='store_true')
        if command == 'desktop':
            sub.add_argument('--config', default='~/.config/freetoken/desktop.json')
            sub.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.command == 'install':
        if args.llama_cpp:
            if args.flint:
                raise ValueError('Install FreeToken --flint and --llama-cpp separately')
            install_llama()
        else:
            install(args.flint)
    elif args.command == 'list':
        for path in sorted((ROOT / 'profiles').glob('*.json')):
            p = read_json(path)
            print(f'{p["id"]:16} {p["context"]["total_tokens"]:6} contexto / {p["context"]["output_tokens"]:5} salida - {p["status"]}')
    else:
        p = profile(args.model)
        if args.command == 'show':
            print(json.dumps(p, indent=2, ensure_ascii=False))
        elif args.command == 'download':
            download(p)
        elif args.command == 'serve':
            if not 1024 <= args.port <= 65534:
                raise ValueError('El puerto debe estar entre 1024 y 65534')
            serve(p, args)
        else:
            desktop(p, args)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
