#!/usr/bin/env python3
"""Recompute long-context metrics from saved SSE timelines and write an audit summary."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalize(row, profile, events_path):
    first = last = generation_end = None
    usage, timings = row.get('usage', {}), row.get('timings', {})
    for line in events_path.read_text().splitlines():
        item = json.loads(line)
        event = item['event']
        if event.get('usage'):
            usage = event['usage']
            generation_end = item['elapsed_s']
        if event.get('timings'):
            timings = event['timings']
        if generation_end is None and any(c.get('finish_reason') for c in event.get('choices', [])):
            generation_end = item['elapsed_s']
        if any(c.get('delta', {}).get('content') or c.get('delta', {}).get('reasoning_content')
               for c in event.get('choices', [])):
            first = item['elapsed_s'] if first is None else first
            last = item['elapsed_s']
    cached = usage.get('prompt_tokens_details', {}).get('cached_tokens')
    source = 'usage.prompt_tokens_details.cached_tokens'
    if cached is None and '--enable-cache-report' in profile.get('server_arguments', []):
        cached, source = 0, 'FreeToken enabled cache report omits details for zero cache hits'
    if cached is None and timings.get('cache_n') is not None:
        cached, source = timings['cache_n'], 'llama.cpp timings.cache_n'
    row.update({'usage': usage, 'timings': timings, 'cached_tokens': cached,
                'cache_count_source': source if cached is not None else None,
                'ttft_s': first,
                'prefill_effective_tok_s': (usage['prompt_tokens'] - cached) / first if first and cached is not None else None,
                'decode_visible_span_tok_s': (usage['completion_tokens'] - 1) / (last-first) if first and last > first else None,
                'generation_end_s': generation_end,
                'suppressed_output_tail_s': max(0, generation_end-last) if generation_end and last else None,
                'decode_http_tok_s': (usage['completion_tokens'] - 1) / (generation_end-first)
                    if first and generation_end and generation_end > first else None})
    if row.get('message', {}).get('tool_calls'):
        # Structured tool tokens do not all appear in text/reasoning events.
        row['decode_http_tok_s'] = None
        row['decode_metric_note'] = 'Structured tool output: text-only timeline does not cover all generated tokens.'
    return row


def summarize(directory, output):
    summary = {'date': '2026-10-24', 'method': 'HTTP streaming, first/last nonempty content or reasoning event; '
               'uncached prompt tokens / TTFT; (completion_tokens - 1) / first-content-to-terminal-usage duration, '
               'including trailing non-rendered tokens. '
               'Forced 8192-token capacity test uses ignore_eos and is not a quality evaluation.', 'models': {}}
    for name in ['qwen3.6', 'gemma4', 'gpt-oss', 'flint', 'nemotron']:
        path = directory / name / 'results.json'
        if not path.exists():
            summary['models'][name] = {'complete': False, 'error': 'No results file'}
            continue
        result = json.loads(path.read_text())
        for row in result['runs']:
            events = path.parent / (row['label'] + '-events.jsonl')
            if events.exists():
                normalize(row, result['profile'], events)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
        cold = next((r for r in result['runs'] if r['label'] == 'long-cold'), {})
        warm = next((r for r in result['runs'] if r['label'] == 'long-prefix-reuse'), {})
        gpu = []
        for gpu_path in path.parent.glob('gpu*.csv'):
            with gpu_path.open() as source:
                for row in csv.reader(source):
                    if len(row) >= 7 and 'RTX 3060' in row[1]:
                        gpu.append(row)
        maximum = lambda i: max(float(x[i]) for x in gpu if x[i].strip() != '[N/A]') if gpu else None
        p = result['profile']
        configuration = {k: p.get(k) for k in ['engine', 'model', 'drafter', 'context', 'server_arguments', 'cache_rebuild', 'environment']}
        summary['models'][name] = {
            'complete': result.get('completed', False), 'error': result.get('error'),
            'context_capacity': p['context']['total_tokens'],
            'configuration_sha256': hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest(),
            'prompt_tokens': cold.get('usage', {}).get('prompt_tokens'),
            'output_tokens': cold.get('usage', {}).get('completion_tokens'),
            'prefill_effective_tok_s': cold.get('prefill_effective_tok_s'),
            'decode_http_tok_s': cold.get('decode_http_tok_s'), 'ttft_s': cold.get('ttft_s'),
            'elapsed_s': cold.get('elapsed_s'), 'cached_tokens_cold': cold.get('cached_tokens'),
            'native_timings': cold.get('timings', {}),
            'engine_allocated_tokens': p['context'].get('engine_allocated_tokens', p['context']['total_tokens']),
            'reserved_engine_tokens': p['context'].get('reserved_engine_tokens', 0),
            'prefix_reuse': {k: warm.get(k) for k in ['cached_tokens', 'ttft_s', 'decode_http_tok_s']},
            'gpu_peak_mib': maximum(2), 'gpu_peak_temperature_c': maximum(5),
            'checks': result.get('checks', []), 'evidence': str(path.relative_to(ROOT)),
        }
    integrity = directory / 'checkpoint-integrity.json'
    if integrity.exists():
        data = json.loads(integrity.read_text())
        summary['checkpoint_weight_hashes_verified'] = {name: value['all_weight_files_match'] for name, value in data['models'].items()}
    summary['all_profiles_complete'] = all(x['complete'] for x in summary['models'].values())
    summary['all_recorded_checks_passed'] = summary['all_profiles_complete'] and all(
        check['passed'] for x in summary['models'].values() for check in x.get('checks', []))
    output.write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'evidence/logs/validation-2026-10-24')
    parser.add_argument('--output', type=Path, default=ROOT / 'evidence/validation-2026-10-24.json')
    args = parser.parse_args()
    print(json.dumps(summarize(args.directory, args.output), indent=2))
