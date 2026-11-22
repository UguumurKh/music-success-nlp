"""Packaging regression checks, independent of private data or model fitting."""
import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from music_success_nlp.analysis_delivery import inventory, reproduction_document


class DeliveryTests(unittest.TestCase):
    def test_inventory_separates_private_and_includes_itself(self):
        with tempfile.TemporaryDirectory() as folder:
            pack = Path(folder)
            (pack/'private').mkdir()
            (pack/'private/predictions.csv').write_text('private')
            (pack/'report.md').write_text('report')
            data = inventory(pack)
            self.assertEqual(data['included_files'], ['report.md', 'submission_manifest.json'])
            self.assertEqual(data['deliberately_excluded_private_files'], ['private/predictions.csv'])
            self.assertEqual(set(data['included_sha256']), {'report.md'})

    def test_generated_code_list_contains_readme_and_helper(self):
        source = Path(__file__).resolve().parents[1]/'src/17_analysis_1.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        values = [ast.literal_eval(node.value) for node in ast.walk(tree)
                  if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'code_files' for t in node.targets)]
        self.assertEqual(len(values), 1)
        for name in ['README.md', 'src/music_success_nlp/analysis_delivery.py', 'tests/test_analysis_delivery.py']:
            self.assertIn(name, values[0])

    def test_bundle_links_and_private_requirements(self):
        text = reproduction_document(Path('/example/run'), dict(base='v2', pca='v3', source='source.parquet'))
        self.assertIn('(run_manifest.json)', text)
        self.assertNotIn('../run_manifest.json', text)
        self.assertIn('ZIP alone cannot run full saved-data verification', text)
        self.assertIn('complete existing', text)
        self.assertIn('execution_output_hashes.json', text)
        self.assertIn('billboard_lyrics_corrected_2000_2022.parquet', text)


if __name__ == '__main__':
    unittest.main()
