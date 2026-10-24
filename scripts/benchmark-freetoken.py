#!/usr/bin/env python3
"""Measure synthetic short requests against an already running FreeToken recipe."""
import argparse
import datetime
import json
import os
from pathlib import Path
import statistics
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', choices=['qwen3.6', 'gemma4', 'gpt-oss'])
    parser.add_argument('--url', default='http://127.0.0.1:1919')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Output already exists; choose a new filename.')
    from transformers import AutoTokenizer
    p = json.loads((ROOT / 'profiles' / (args.model + '.json')).read_text())
    directory = Path(os.environ.get('RECIPES_MODEL_DIR', str(Path.home() / '.freetoken/models')))
    tokenizer = AutoTokenizer.from_pretrained(directory / p['model']['local_directory'], local_files_only=True)
    records = []
    result = {'date': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'model': args.model, 'context': p['context'], 'server_arguments_expected': p['server_arguments'],
              'cache_rebuild_expected': p.get('cache_rebuild'),
              'method': 'HTTP stream; first nonempty content OR reasoning event; one warmup excluded. '
                        'Synthetic content truncated before chat template. Record server logs separately '
                        'to confirm arguments, actual cache counts and complete shutdown.', 'runs': records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        target = 256 if i == 0 else 4096
        prefix = f'Benchmark case {chr(65 + i)} {time.time_ns()}. '
        ids = tokenizer.encode(prefix + 'Read these synthetic records. ' +
                               ('The subsystem handles jobs and returns results. ' * 1500),
                               add_special_tokens=False)[:target]
        body = {'model': args.model, 'messages': [{'role': 'user', 'content': tokenizer.decode(ids)}],
                'max_tokens': 32 if i == 0 else 200, 'temperature': 0, 'ignore_eos': True,
                'stream': True, 'stream_options': {'include_usage': True}}
        request = urllib.request.Request(args.url.rstrip('/') + '/v1/chat/completions',
                                         data=json.dumps(body).encode(),
                                         headers={'Content-Type': 'application/json'})
        first = last = generation_end = None
        usage = {}
        events = []
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=300) as response:
            for line in response:
                if not line.startswith(b'data: '):
                    continue
                data = line[6:].strip()
                if data == b'[DONE]':
                    break
                event = json.loads(data)
                events.append(event)
                if event.get('usage'):
                    usage = event['usage']
                    generation_end = time.perf_counter()
                if any(c.get('delta', {}).get('content') or c.get('delta', {}).get('reasoning_content')
                       for c in event.get('choices', [])):
                    now = time.perf_counter()
                    first = now if first is None else first
                    last = now
        if not usage or first is None or last <= first or generation_end is None:
            raise RuntimeError('Missing usage or insufficient streamed tokens; no throughput inferred.')
        record = {'run': i, 'warmup': i == 0, 'requested_raw_content_tokens': target,
                  'request': body, 'usage': usage, 'elapsed_s': time.perf_counter() - started,
                  'ttft_s': first - started,
                  'prefill_effective_tok_s': usage['prompt_tokens'] / (first - started),
                  'decode_visible_span_tok_s': (usage['completion_tokens'] - 1) / (last - first),
                  'decode_http_tok_s': (usage['completion_tokens'] - 1) / (generation_end - first),
                  'generation_end_s': generation_end-started, 'events': events}
        records.append(record)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print({k: v for k, v in record.items() if k not in ['request', 'events']}, flush=True)
    measured = records[1:]
    result['mean_prefill_effective_tok_s'] = statistics.mean(x['prefill_effective_tok_s'] for x in measured)
    result['mean_decode_http_tok_s'] = statistics.mean(x['decode_http_tok_s'] for x in measured)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
