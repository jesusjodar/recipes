"""Offline regression checks for recipe installation and measurement accounting."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


runner = module('profile_validation', ROOT / 'scripts/validate-profiles.py')
recipes = module('recipes', ROOT / 'scripts/recipes.py')
summary = module('validation_summary', ROOT / 'scripts/summarize-validation.py')


class Response:
    def __init__(self, events):
        self.lines = [b'data: ' + json.dumps(e).encode() + b'\n' for e in events] + [b'data: [DONE]\n']

    def __enter__(self):
        return iter(self.lines)

    def __exit__(self, *args):
        return False


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.suite = runner.Suite({'id': 'test', 'engine': 'llama-cpp'}, self.out, 'http://127.0.0.1:1')

    def events(self):
        return [
            {'choices': [{'delta': {'reasoning_content': 'think'}}]},
            {'choices': [{'delta': {'content': 'answer'}, 'finish_reason': 'length'}]},
            {'choices': [], 'usage': {'prompt_tokens': 100, 'completion_tokens': 3,
                                     'prompt_tokens_details': {'cached_tokens': 20}}},
        ]

    def test_reasoning_is_first_event_and_cached_tokens_excluded(self):
        with patch.object(runner.urllib.request, 'urlopen', return_value=Response(self.events())), \
             patch.object(runner.time, 'perf_counter', side_effect=[0, 1, 2, 3, 4, 5]):
            row = self.suite.stream('measured', [{'role': 'user', 'content': 'synthetic'}], 3)
        self.assertEqual(row['ttft_s'], 1)
        self.assertEqual(row['prefill_effective_tok_s'], 80)
        self.assertEqual(row['decode_http_tok_s'], 1)
        self.assertTrue(row['forced_length_passed'])
        self.assertEqual(len((self.out / 'measured-events.jsonl').read_text().splitlines()), 3)

    def test_unknown_cache_count_does_not_infer_uncached_prefill(self):
        events = self.events()
        del events[-1]['usage']['prompt_tokens_details']
        with patch.object(runner.urllib.request, 'urlopen', return_value=Response(events)):
            row = self.suite.stream('cache-unknown', [{'role': 'user', 'content': 'synthetic'}], 3)
        self.assertIsNone(row['prefill_effective_tok_s'])
        self.assertIsNotNone(row['prefill_including_cached_tok_s'])

    def test_enabled_cache_reporting_interprets_omitted_details_as_zero(self):
        events = self.events()
        del events[-1]['usage']['prompt_tokens_details']
        self.suite.p['server_arguments'] = ['--enable-cache-report']
        with patch.object(runner.urllib.request, 'urlopen', return_value=Response(events)), \
             patch.object(runner.time, 'perf_counter', side_effect=[0, 1, 2, 3, 4, 5]):
            row = self.suite.stream('cache-zero', [{'role': 'user', 'content': 'synthetic'}], 3)
        self.assertEqual(row['cached_tokens'], 0)
        self.assertEqual(row['prefill_effective_tok_s'], 100)

    def test_short_forced_output_is_failure_but_evidence_saved(self):
        events = self.events()
        events[-1]['usage']['completion_tokens'] = 2
        with patch.object(runner.urllib.request, 'urlopen', return_value=Response(events)):
            with self.assertRaisesRegex(RuntimeError, 'incomplete forced output'):
                self.suite.stream('short', [{'role': 'user', 'content': 'synthetic'}], 3)
        self.assertFalse(json.loads((self.out / 'results.json').read_text())['runs'][0]['forced_length_passed'])

    def test_tool_arguments_reassemble_across_chunks(self):
        events = [
            {'choices': [{'delta': {'tool_calls': [{'index': 0, 'id': 'call_test', 'function': {'name': 'lookup_codeword', 'arguments': '{"key":'}}]}}]},
            {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': '"recipe"}'}}]}, 'finish_reason': 'tool_calls'}]},
            {'choices': [], 'usage': {'prompt_tokens': 100, 'completion_tokens': 8}},
        ]
        with patch.object(runner.urllib.request, 'urlopen', return_value=Response(events)):
            row = self.suite.stream('tool', [{'role': 'user', 'content': 'synthetic'}], 64, forced=False)
        call = row['message']['tool_calls'][0]
        self.assertEqual(json.loads(call['function']['arguments']), {'key': 'recipe'})
        self.assertEqual(call['function']['name'], 'lookup_codeword')
        self.assertEqual(call['id'], 'call_test')

    def test_exact_prompt_construction(self):
        self.suite.count = lambda messages, tools=None: len(messages[0]['content'])
        messages = self.suite.prompt(1500, 'test')
        self.assertEqual(self.suite.count(messages), 1500)

    def test_padding_handles_token_counts_skipped_by_character_boundaries(self):
        def count(messages, tools=None):
            content = messages[0]['content']
            if '\nToken padding:' in content:
                filler = content.split('\nToken padding:', 1)[1].split('\nPropose', 1)[0]
                return 1000 + filler.count(' x')
            return 2 * len(content)
        self.suite.count = count
        messages = self.suite.prompt(1501, 'odd-target')
        self.assertEqual(count(messages), 1501)
        self.assertIn('Token padding:', messages[0]['content'])

    def test_http_error_keeps_response_body(self):
        import io
        from urllib.error import HTTPError
        error = HTTPError('http://localhost', 400, 'invalid', {}, io.BytesIO(b'bad model'))
        with patch.object(runner.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, 'HTTP 400: bad model'):
                runner.http('http://localhost', '/v1/test', {})


class SummaryTests(unittest.TestCase):
    def test_recomputes_rates_from_archived_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'events.jsonl'
            events = [
                {'elapsed_s': 2, 'event': {'choices': [{'delta': {'reasoning_content': 'a'}}]}},
                {'elapsed_s': 4, 'event': {'choices': [{'delta': {'content': 'b'}}]}},
                {'elapsed_s': 5, 'event': {'usage': {'prompt_tokens': 100, 'completion_tokens': 5,
                                                   'prompt_tokens_details': {'cached_tokens': 20}}}},
            ]
            path.write_text('\n'.join(json.dumps(e) for e in events))
            row = summary.normalize({}, {}, path)
            self.assertEqual(row['prefill_effective_tok_s'], 40)
            self.assertAlmostEqual(row['decode_http_tok_s'], 4 / 3)
            self.assertEqual(row['decode_visible_span_tok_s'], 2)
            self.assertEqual(row['suppressed_output_tail_s'], 1)
            self.assertEqual(row['cached_tokens'], 20)

    def test_structured_tool_tokens_do_not_infer_text_decode_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'events.jsonl'
            path.write_text('\n'.join(json.dumps(e) for e in [
                {'elapsed_s': 2, 'event': {'choices': [{'delta': {'content': 'a'}}]}},
                {'elapsed_s': 4, 'event': {'choices': [{'delta': {'content': 'b'}}]}},
                {'elapsed_s': 5, 'event': {'usage': {'prompt_tokens': 100, 'completion_tokens': 5}}},
            ]))
            row = summary.normalize({'message': {'tool_calls': [{}]}}, {}, path)
            self.assertIsNone(row['decode_http_tok_s'])
            self.assertIn('Structured tool output', row['decode_metric_note'])


class RecipeTests(unittest.TestCase):
    def test_gpu_selection_excludes_3060_ti(self):
        with patch.object(recipes.subprocess, 'check_output', return_value='GPU-a, RTX 3060 Ti\nGPU-b, NVIDIA GeForce RTX 3060\n'):
            self.assertEqual(recipes.select_gpu(None), 'GPU-b')

    def test_gpu_selection_requires_unique_match(self):
        with patch.object(recipes.subprocess, 'check_output', return_value='GPU-a, RTX 2070\n'):
            with self.assertRaises(RuntimeError):
                recipes.select_gpu(None)

    def test_checksum_mismatch_does_not_overwrite_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'weights'
            p.write_bytes(b'original bytes')
            with self.assertRaisesRegex(RuntimeError, 'SHA-256 mismatch'):
                recipes.verified_download({'sha256': 'wrong'}, p)
            self.assertEqual(p.read_bytes(), b'original bytes')

    def test_checksum_match_reuses_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'weights'
            p.write_bytes(b'original bytes')
            with patch.object(recipes.urllib.request, 'urlretrieve') as download:
                recipes.verified_download({'sha256': recipes.sha256(p)}, p)
            download.assert_not_called()


class CatalogTests(unittest.TestCase):
    def test_context_budgets_sum_to_capacity(self):
        for path in (ROOT / 'profiles').glob('*.json'):
            p = json.loads(path.read_text())
            self.assertEqual(p['context']['input_budget_with_reserved_output'] + p['context']['output_tokens'],
                             p['context']['total_tokens'], p['id'])

    def test_dflash_internal_reserve_matches_engine_allocation(self):
        p = json.loads((ROOT / 'profiles/nemotron.json').read_text())
        self.assertEqual(p['context']['engine_allocated_tokens'],
                         p['context']['total_tokens'] + p['context']['reserved_engine_tokens'])
        self.assertEqual(int(p['server_arguments'][p['server_arguments'].index('-c') + 1]),
                         p['context']['engine_allocated_tokens'])
        self.assertIn('--no-context-shift', p['server_arguments'])

    def test_readme_languages_have_same_models_and_working_links(self):
        import re
        for path in ROOT.glob('README*.md'):
            text = path.read_text()
            anchors = set(re.findall(r'<a id="([^"]+)"', text))
            for name in ['qwen3.6', 'gemma4', 'gpt-oss', 'flint', 'nemotron']:
                self.assertIn('profiles/' + name + '.json', text)
            for link in re.findall(r'\]\(([^)]+)\)', text):
                if link.startswith('http'):
                    continue
                if link.startswith('#'):
                    self.assertIn(link[1:], anchors, str(path))
                else:
                    self.assertTrue((ROOT / link.split('#')[0]).exists(), link)


if __name__ == '__main__':
    unittest.main()
