#!/usr/bin/env python3
"""Validate installed recipes with long-context throughput, cache and tool round trips.

Run with .venv/bin/python. Servers are started one at a time and cleaned up.
--pause-user-service is optional and restores an initially active service in finally.
All prompts are synthetic or source code from this repository. No agent credentials used.
"""
import argparse
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def backend_watchdog(log):
    """Unblock an SSE read if the owned backend died after sending HTTP 200."""
    if not log.exists() or not hasattr(signal, 'setitimer'):
        yield
        return
    previous = signal.getsignal(signal.SIGALRM)

    def check_backend(*_):
        tail = log.read_text()[-24000:]
        if any(marker in tail for marker in ['torch.OutOfMemoryError:', 'Backend worker is gone',
                                              'ERROR   \x1b[0m Backend supervisor:']):
            raise RuntimeError('Backend failed during streamed response; see server.log')

    signal.signal(signal.SIGALRM, check_backend)
    signal.setitimer(signal.ITIMER_REAL, 2, 2)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def http(base, path, body=None, timeout=120):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'{path}: HTTP {error.code}: {error.read().decode()}') from error


def stop(process):
    if process and process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=45)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


class Suite:
    def __init__(self, profile, out, base):
        self.p, self.out, self.base = profile, out, base
        self.offset = 0
        self.results = {'model': profile['id'], 'date': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'profile_sha256': hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest(),
                        'profile': profile, 'runs': [], 'checks': []}
        self.corpus = '\n'.join((ROOT / p).read_text() for p in ['scripts/recipes.py', 'scripts/benchmark-freetoken.py'])
        self.pool = ''.join(f'\n### Synthetic source snapshot {i}\n{self.corpus}\n' for i in range(80))

    def save(self):
        dump(self.out / 'results.json', self.results)

    def count(self, messages, tools=None):
        body = {'model': self.p['id'], 'messages': messages}
        if tools:
            body['tools'] = tools
        if self.p['engine'] == 'llama-cpp':
            return http(self.base, '/v1/chat/completions/input_tokens', body)['input_tokens'] + self.offset
        if tools:
            body['tools'] = [{'name': t['function']['name'], 'description': t['function']['description'],
                              'input_schema': t['function']['parameters']} for t in tools]
        return http(self.base, '/v1/messages/count_tokens', body)['input_tokens'] + self.offset

    def prompt(self, target, label, tail=None):
        prefix = f'Validation case {label} {time.time_ns()}. The following is synthetic repository background.\n'
        suffix = '\n' + (tail or 'Propose a detailed implementation plan and Python code for persistent prefix caching, including invalidation and concurrent access. Explain the design thoroughly.')
        low, high, best = 0, min(len(self.pool), target * 7), None
        for _ in range(25):
            middle = (low + high) // 2
            messages = [{'role': 'user', 'content': prefix + self.pool[:middle] + suffix}]
            n = self.count(messages)
            if n == target:
                return messages
            if n < target:
                low, best = middle + 1, (middle, n)
            else:
                high = middle - 1
            if low > high:
                break
        # A character boundary can skip a token count. Leave room and add a
        # repeated single-token filler; verify with the server rather than
        # assuming a character-to-token ratio.
        middle = max(0, (best[0] if best else high) - 256)
        stem = prefix + self.pool[:middle] + '\nToken padding:'
        for padding in [' x', ' z', ' _', ' a', 'x']:
            n = max(0, target - self.count([{'role': 'user', 'content': stem + suffix}]))
            for _ in range(12):
                messages = [{'role': 'user', 'content': stem + padding * n + suffix}]
                actual = self.count(messages)
                if actual == target:
                    return messages
                n = max(0, n + target - actual)
        raise RuntimeError(f'Unable to construct exact {target}-token prompt; nearest {best}')

    def stream(self, label, messages, maximum, forced=True, tools=None, **extras):
        body = {'model': self.p['id'], 'messages': messages, 'max_tokens': maximum,
                'temperature': 0 if forced else 1.0, 'stream': True, 'stream_options': {'include_usage': True}}
        if forced:
            body['ignore_eos'] = True
        if tools:
            body['tools'] = tools
        body.update(extras)
        dump(self.out / (label + '-request.json'), body)
        req = urllib.request.Request(self.base + '/v1/chat/completions', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        first = last = generation_end = None
        usage, timings, finish = {}, {}, None
        text, reasoning, calls = [], [], {}
        event_count = 0
        started = time.perf_counter()
        print(f'{self.p["id"]} START {label}: {maximum} output tokens', flush=True)
        with backend_watchdog(self.out / 'server.log'), (self.out / (label + '-events.jsonl')).open('w') as events:
            with urllib.request.urlopen(req, timeout=600) as response:
                for line in response:
                    if not line.startswith(b'data:'):
                        continue
                    data = line[5:].strip()
                    now = time.perf_counter()
                    if data == b'[DONE]':
                        break
                    event = json.loads(data)
                    events.write(json.dumps({'elapsed_s': now - started, 'event': event}, ensure_ascii=False) + '\n')
                    if event.get('error'):
                        raise RuntimeError(event['error'])
                    if event.get('usage'):
                        usage = event['usage']
                        generation_end = now
                    if event.get('timings'):
                        timings = event['timings']
                    for choice in event.get('choices', []):
                        delta = choice.get('delta', {})
                        if choice.get('finish_reason'):
                            finish = choice['finish_reason']
                        if delta.get('content') or delta.get('reasoning_content'):
                            first = now if first is None else first
                            last = now
                            event_count += 1
                            if event_count % 2048 == 0:
                                print(f'{self.p["id"]} {label}: {event_count} text/reasoning events, {now-started:.1f}s', flush=True)
                        if delta.get('content'):
                            text.append(delta['content'])
                        if delta.get('reasoning_content'):
                            reasoning.append(delta['reasoning_content'])
                        for tool in delta.get('tool_calls') or []:
                            call = calls.setdefault(tool.get('index', 0), {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                            if tool.get('id'):
                                call['id'] = tool['id']
                            for field in ['name', 'arguments']:
                                value = tool.get('function', {}).get(field)
                                if value:
                                    call['function'][field] += value
        elapsed = time.perf_counter() - started
        cached = usage.get('prompt_tokens_details', {}).get('cached_tokens')
        if cached is None and '--enable-cache-report' in self.p.get('server_arguments', []):
            # FreeToken omits prompt_tokens_details when the reported count is zero.
            cached = 0
        if cached is None and timings.get('cache_n') is not None:
            cached = timings['cache_n']
        row = {'label': label, 'usage': usage, 'cached_tokens': cached, 'finish_reason': finish, 'forced_ignore_eos': forced,
               'requested_max_tokens': maximum, 'elapsed_s': elapsed,
               'ttft_s': first - started if first else None,
               'prefill_effective_tok_s': ((usage['prompt_tokens'] - cached) / (first-started)) if cached is not None and first else None,
               'prefill_including_cached_tok_s': usage.get('prompt_tokens', 0) / (first-started) if first else None,
               'decode_visible_span_tok_s': (usage['completion_tokens'] - 1) / (last-first) if usage and first and last > first else None,
               'generation_end_s': generation_end-started if generation_end else None,
               'decode_http_tok_s': (usage['completion_tokens'] - 1) / (generation_end-first)
                    if usage and first and generation_end and generation_end > first else None,
               'api_output_tok_s': usage.get('completion_tokens', 0) / elapsed, 'text_events': event_count,
               'timings': timings, 'message': {'role': 'assistant', 'content': ''.join(text)}}
        if reasoning:
            row['message']['reasoning_content'] = ''.join(reasoning)
        if calls:
            row['message']['tool_calls'] = list(calls.values())
        row['forced_length_passed'] = bool(usage and usage.get('completion_tokens') == maximum) if forced else None
        self.results['runs'].append(row)
        self.save()
        print(self.p['id'], {k: v for k, v in row.items() if k not in ['message', 'timings']}, flush=True)
        if not usage or forced and not row['forced_length_passed']:
            raise RuntimeError(f'{label}: missing usage or incomplete forced output: {usage}')
        return row

    def endpoints(self):
        for path, body in [('/v1/responses', {'model': self.p['id'], 'input': 'Reply with READY.', 'max_output_tokens': 256}),
                           ('/v1/messages', {'model': self.p['id'], 'messages': [{'role': 'user', 'content': 'Reply with READY.'}], 'max_tokens': 256})]:
            try:
                response = http(self.base, path, body)
                dump(self.out / (path.rsplit('/', 1)[-1] + '-smoke.json'), {'request': body, 'response': response})
                check = {'name': path, 'passed': response.get('object') == 'response' if path.endswith('responses') else response.get('type') == 'message'}
            except Exception as error:
                check = {'name': path, 'passed': False, 'error': str(error)}
            self.results['checks'].append(check)
            self.save()

    def run(self):
        resume = self.results.get('resumed', False)
        self.results['checks'] = []
        warm_messages = self.prompt(1024, 'resume-warmup' if resume else 'warmup')
        warm = self.stream('resume-warmup' if resume else 'warmup', warm_messages, 64)
        # Calibrate any default-template difference between count adapters and chat.
        self.offset = warm['usage']['prompt_tokens'] - 1024
        self.results['count_adapter_offset_tokens'] = self.offset
        target = self.p['context']['input_budget_with_reserved_output']
        row = next((r for r in self.results['runs'] if r['label'] == 'long-cold' and r.get('forced_length_passed')), None)
        if row is None:
            messages = self.prompt(target, 'long-cold')
            row = self.stream('long-cold', messages, 8192)
        else:
            messages = json.loads((self.out / 'long-cold-request.json').read_text())['messages']
        row['expected_input_tokens'] = target
        row['exact_budget_passed'] = row['usage']['prompt_tokens'] == target and row['forced_length_passed']
        self.results['checks'].append({'name': 'long_context_plus_8192', 'passed': row['exact_budget_passed']})
        self.save()
        if not any(r['label'] == 'long-prefix-reuse' and r.get('forced_length_passed') for r in self.results['runs']):
            # Prefix reuse is meaningful only after this server processed the
            # prefix; a resumed run without it must warm that prompt first.
            if resume and any(r['label'] == 'long-cold' for r in self.results['runs']):
                self.stream('resume-prefix-prime', messages, 32)
            self.stream('long-prefix-reuse', messages, 256)
        tools = [{'type': 'function', 'function': {'name': 'lookup_codeword', 'description': 'Return the codeword for a key.',
                  'parameters': {'type': 'object', 'properties': {'key': {'type': 'string'}}, 'required': ['key']}}}]
        tool_messages = self.prompt(target - 2048, 'long-tool', 'Now call lookup_codeword with key recipe. Do not guess its result. After the tool responds, return the codeword verbatim.')
        try:
            tool = self.stream('long-tool-call', tool_messages, 1024, forced=False, tools=tools, temperature=0)
            call = tool['message']['tool_calls'][0]
            assert call['function']['name'] == 'lookup_codeword' and json.loads(call['function']['arguments']) == {'key': 'recipe'}, call
            follow = self.stream('long-tool-followup', tool_messages + [tool['message'], {'role': 'tool', 'tool_call_id': call['id'], 'content': 'BLUEPRINT-742'}], 1024, forced=False, tools=tools, temperature=0)
            assert 'BLUEPRINT-742' in follow['message']['content'], follow['message']
            check = {'name': 'long_tool_round_trip', 'passed': True, 'call_prompt_tokens': tool['usage']['prompt_tokens'], 'followup_prompt_tokens': follow['usage']['prompt_tokens']}
        except Exception as error:
            check = {'name': 'long_tool_round_trip', 'passed': False, 'error': str(error)}
        self.results['checks'].append(check)
        self.save()
        self.endpoints()
        self.results['completed'] = True
        self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', default=['qwen3.6', 'gemma4', 'gpt-oss', 'flint', 'nemotron'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=1929)
    parser.add_argument('--pause-user-service')
    parser.add_argument('--resume', action='store_true', help='Resume missing phases, preserving successful measurements')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    active = args.pause_user_service and subprocess.run(['systemctl', '--user', 'is-active', '--quiet', args.pause_user_service]).returncode == 0
    if active:
        # Refuse to interrupt an in-flight request to the known local Nemotron service.
        if args.pause_user_service == 'nemotron-e4b.service':
            slots = http('http://127.0.0.1:8000', '/slots')
            if any(s.get('is_processing') for s in slots):
                raise RuntimeError('Nemotron is busy; retry when idle.')
        subprocess.run(['systemctl', '--user', 'stop', args.pause_user_service], check=True)
    try:
        for index, name in enumerate(args.models):
            out = args.output / name
            out.mkdir(parents=True, exist_ok=True)
            if (out / 'results.json').exists() and not args.resume:
                raise RuntimeError(f'Results already exist: {out}; use another output directory.')
            profile = json.loads((ROOT / 'profiles' / (name + '.json')).read_text())
            port = args.port + index * 2
            suite = Suite(profile, out, f'http://127.0.0.1:{port}')
            if (out / 'results.json').exists():
                suite.results = json.loads((out / 'results.json').read_text())
                if suite.results.get('error'):
                    suite.results.setdefault('attempt_errors', []).append(suite.results.pop('error'))
                suite.results['resumed'] = True
                suite.results.setdefault('attempt_profiles', []).append(suite.results['profile'])
                suite.results['profile'] = profile
                suite.results['profile_sha256'] = hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()
                for row in suite.results['runs']:
                    if row['label'] == 'resume-warmup' or (row['label'] in ['long-cold', 'long-prefix-reuse'] and row.get('forced_length_passed') is False):
                        label = row['label']
                        number = len(list(out.glob(label + '-attempt-*-events.jsonl'))) + 1
                        archived = label + '-attempt-' + str(number)
                        for suffix in ['-request.json', '-events.jsonl']:
                            prior = out / (label + suffix)
                            if prior.exists():
                                prior.rename(out / (archived + suffix))
                        row['label'] = archived
                        row['attempt_status'] = 'retained before resume'
                suite.offset = suite.results.get('count_adapter_offset_tokens', 0)
                for stem, suffix in [('server', '.log'), ('gpu', '.csv')]:
                    prior = out / (stem + suffix)
                    if prior.exists():
                        number = len(list(out.glob(stem + '-attempt-*' + suffix))) + 1
                        prior.rename(out / (stem + '-attempt-' + str(number) + suffix))
            process = monitor = None
            with (out / 'server.log').open('w') as log, (out / 'gpu.csv').open('w') as gpu:
                try:
                    monitor = subprocess.Popen(['nvidia-smi', '--query-gpu=timestamp,name,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw', '--format=csv,noheader,nounits', '--loop-ms=1000'], stdout=gpu, stderr=subprocess.DEVNULL)
                    process = subprocess.Popen([str(ROOT / 'recipes'), 'serve', name, '--port', str(port)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    for _ in range(1200):
                        if process.poll() is not None:
                            raise RuntimeError(f'{name} exited during startup; see server.log')
                        if 'LISTO:' in (out / 'server.log').read_text():
                            break
                        time.sleep(.5)
                    else:
                        raise RuntimeError(f'{name} startup timeout')
                    suite.run()
                except BaseException as error:
                    suite.results['error'] = repr(error)
                    suite.save()
                    print(name, 'FAILED', repr(error), flush=True)
                    if isinstance(error, (KeyboardInterrupt, SystemExit)):
                        raise
                finally:
                    stop(process)
                    if monitor:
                        monitor.terminate()
                        monitor.wait(timeout=10)
    finally:
        if active:
            subprocess.run(['systemctl', '--user', 'start', args.pause_user_service], check=True)
            print('Initially active service restored.', flush=True)


if __name__ == '__main__':
    main()
