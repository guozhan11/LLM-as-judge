"""Run with: python -m unittest discover -s tests -v."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.project_paths import normalize_comment_id

ROOT = Path(__file__).resolve().parents[1]


class PortablePathsTest(unittest.TestCase):
    def test_legacy_and_portable_ids_match(self):
        for value in (
            '/Users/old/Desktop/project/comments/example.json',
            r'C:\Users\old\project\comments\example.json',
            'comments/example.json',
            './comments/example.json',
        ):
            self.assertEqual(normalize_comment_id(value), 'comments/example.json')
        self.assertEqual(normalize_comment_id('/old/comments/nested/a.json'),
                         'comments/nested/a.json')

    def test_logical_and_unknown_ids_unchanged(self):
        for value in ('csv:epa_comments.csv:row1', 'csv:C:\\comments\\x.json',
                      'unknown', None, '/unrelated/example.json'):
            self.assertEqual(normalize_comment_id(value), value)
        with self.assertRaises(ValueError):
            normalize_comment_id('comments/../secret.json')

    def test_evaluator_resumes_legacy_results_after_move(self):
        """Execute the real evaluation cell against a relocated legacy checkpoint."""
        book = json.loads((ROOT / 'notebooks/comment_evaluator.ipynb').read_text())
        cell = next(''.join(c['source']) for c in book['cells']
                    if 'processed = set()' in ''.join(c['source']))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comment = root / 'comments/example.json'
            comment.parent.mkdir()
            comment.write_text('{}')
            results = root / 'data/results'
            results.mkdir(parents=True)
            old = {'file': '/Users/previous/project/comments/example.json',
                   'scores': {'overall': 4}, 'rationales': {'overall': 'Keep this.'},
                   'overall_summary': 'Unchanged result.'}
            (results / 'comment_scores.jsonl').write_text(json.dumps(old) + '\n')
            def forbidden(*args, **kwargs):
                self.fail('Resume attempted to evaluate an already scored comment')
            env = dict(BASE_DIR=root, normalize_comment_id=normalize_comment_id,
                       json=json, json_files=[comment], csv_records=[],
                       extract_comment_text=forbidden, evaluate_comment=forbidden)
            exec(compile(cell, 'comment_evaluator.ipynb', 'exec'), env)
            saved = json.loads((results / 'comment_scores.jsonl').read_text())
            self.assertEqual(saved, {**old, 'file': 'comments/example.json'})
            self.assertEqual(env['processed'], {'comments/example.json'})


if __name__ == '__main__':
    unittest.main()
