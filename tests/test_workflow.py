"""Meaningful workflow regressions; all data is temporary and no paid API is used."""
import copy
import json
import sys
import unittest
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PIL import Image
from pdf2bilingual.pipeline import workspace, assist, exporter


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[2] / 'dist' / 'build' / 'tests'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.root = temp_root / ('workflow_' + uuid.uuid4().hex)
        self.root.mkdir()
        self.patches = [patch.object(workspace, 'WORK_ROOT', str(self.root/'work')),
                        patch.object(exporter, 'OUTPUT_ROOT', str(self.root/'output'))]
        for p in self.patches:
            p.start()
        self.addCleanup(shutil.rmtree, self.root)
        for p in self.patches:
            self.addCleanup(p.stop)
        self.key = 'sample'
        self.doc = {'schema_version': 2, 'key': self.key, 'title': 'Test',
                    'source': {'path': 'input/test.pdf', 'sha256': 'abc'},
                    'pages': [dict(number=1, width=200, height=300, preview='page.png',
                                   native_text='', native_language='en', issues=['无文字层'],
                                   figures=[], resolved=None)]}
        folder = workspace.workdir(self.key)/'figures'
        folder.mkdir(parents=True)
        Image.new('RGB', (400, 600), 'white').save(folder/'page.png')
        workspace.save_doc(self.key, self.doc)

    def result(self, target='bi'):
        return {'key': self.key, 'source_sha256': 'abc', 'target': target, 'pages': [
            {'page': 1, 'title_en': 'Title', 'title_zh': '标题', 'notes': '', 'needs_review': False,
             'blocks': [{'t': 'item', 'en': 'Value $x^2$.', 'zh': '值为 $x^2$。', 'sub': {'en': [], 'zh': []}},
                        {'t': 'fig', 'bbox': [100, 200, 500, 700]}]}]}

    def test_offline_switch_blocks_before_any_network(self):
        with patch('urllib.request.build_opener') as network:
            with self.assertRaisesRegex(ValueError, '未开启'):
                assist.complete_api(self.key, 'bi', 'https://example.com/v1', 'model')
            network.assert_not_called()

    def test_incomplete_document_cannot_be_mislabeled_bilingual(self):
        with self.assertRaises(workspace.NeedsModel):
            exporter.build_v2(self.key, 'bi', ('tex',))
        self.assertFalse((self.root/'output'/self.key).exists())

    def test_import_preserves_raw_data_crops_and_backs_up(self):
        self.assertEqual(assist.import_result(self.key, payload=self.result()), 1)
        doc = workspace.read_doc(self.key)
        self.assertEqual(doc['pages'][0]['native_text'], '')
        self.assertEqual(workspace.pending(doc, 'bi'), [])
        fig = doc['pages'][0]['resolved']['blocks'][1]
        self.assertEqual(fig['source_bbox'], [20, 60, 100, 210])
        with Image.open(workspace.figure_path(self.key, fig['file'])) as image:
            self.assertEqual(image.size, (160, 300))
        self.assertTrue(list((workspace.workdir(self.key)/'backups').glob('*.json')))
        exporter.build_v2(self.key, 'bi', ('tex', 'pptx'), progress=lambda _: None)
        self.assertTrue((self.root/'output'/self.key/'sample_BI.pptx').exists())

    def test_invalid_batch_does_not_partially_replace_content(self):
        before = (workspace.workdir(self.key)/'content.json').read_bytes()
        result = self.result()
        result['pages'].append(copy.deepcopy(result['pages'][0]))
        with self.assertRaisesRegex(ValueError, '重复'):
            assist.import_result(self.key, payload=result)
        self.assertEqual(before, (workspace.workdir(self.key)/'content.json').read_bytes())
        result = self.result()
        result['source_sha256'] = 'different'
        with self.assertRaisesRegex(ValueError, '指纹'):
            assist.import_result(self.key, payload=result)

    def test_alignment_and_page_validation(self):
        result = self.result()
        result['pages'][0]['blocks'][0]['sub']['en'] = ['Only English']
        with self.assertRaisesRegex(ValueError, '数量'):
            assist.import_result(self.key, payload=result)
        result = self.result()
        result['pages'][0]['blocks'][1]['bbox'] = [900, 0, 500, 1000]
        with self.assertRaisesRegex(ValueError, '矩形'):
            assist.import_result(self.key, payload=result)

    def test_mock_api_resumes_and_saves_only_pending_pages(self):
        result = self.result()['pages'][0]
        response = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(result)}}]}
        class Reply:
            def __enter__(self):
                import io
                return io.BytesIO(json.dumps(response).encode())
            def __exit__(self, *args):
                pass
        class Opener:
            def open(self, request, timeout):
                self.request = request
                return Reply()
        opener = Opener()
        with patch('urllib.request.build_opener', return_value=opener) as network:
            count = assist.complete_api(self.key, 'bi', 'http://localhost:9000/v1', 'test', enabled=True, progress=lambda _: None)
            self.assertEqual(count, 1)
            self.assertEqual(assist.complete_api(self.key, 'bi', 'http://localhost:9000/v1', 'test', enabled=True), 0)
            self.assertEqual(network.call_count, 1)
        self.assertEqual(workspace.pending(workspace.read_doc(self.key), 'bi'), [])

    def test_handoff_records_source_and_only_pending_pages(self):
        folder = assist.export_handoff(self.key, 'bi')
        task = json.loads((folder/'task.json').read_text(encoding='utf-8'))
        self.assertEqual(task['source_sha256'], 'abc')
        self.assertEqual([p['page'] for p in task['pages']], [1])
        self.assertTrue(Path(task['pages'][0]['image']).is_file())

    def test_model_tex_cannot_inject_commands(self):
        with self.assertRaisesRegex(ValueError, '不支持'):
            exporter.rich_tex(r'$\input{secret}$')
        self.assertEqual(exporter.rich_tex('A & B'), r'A \& B')
        with self.assertRaises(ValueError):
            workspace.workdir('../escape')
        with self.assertRaises(ValueError):
            workspace.figure_path(self.key, '../../escape.png')
        with self.assertRaisesRegex(ValueError, '环境'):
            exporter.rich_tex(r'$\begin{filecontents}{oops}x\end{filecontents}$')

    def test_offline_extraction_detects_blank_page_and_builds_source(self):
        from pdf2bilingual.pipeline import extract
        inputs = self.root/'input'
        inputs.mkdir()
        pdf = inputs/'native_and_blank.pdf'
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
                   b'<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
                   b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 600] /Resources << /Font << /F1 6 0 R >> >> /Contents 5 0 R >>',
                   b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 600] /Resources << >> /Contents 7 0 R >>',
                   None, b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>', b'<< /Length 0 >>\nstream\n\nendstream']
        stream = b'BT /F1 10 Tf 20 500 Td (This is a native English paragraph with enough text to extract.) Tj ET'
        objects[4] = b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream'
        data = bytearray(b'%PDF-1.4\n')
        offsets = [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(len(data));data.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
        xref = len(data)
        data.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
        for offset in offsets[1:]:
            data.extend(f'{offset:010d} 00000 n \n'.encode())
        data.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode())
        pdf.write_bytes(data)
        with patch.object(extract, 'INPUT_ROOT', str(inputs)), patch.object(workspace, 'INPUT_ROOT', str(inputs)):
            key = extract.extract_pdf(pdf, 'extracted', dpi=72, progress=lambda _: None)
            doc = workspace.read_doc(key)
            self.assertEqual(len(doc['pages']), 2)
            self.assertIn('native English', doc['pages'][0]['native_text'])
            self.assertEqual(doc['pages'][0]['issues'], [])
            self.assertEqual([p['page'] for p in workspace.pending(doc)], [2])
            out = exporter.build_v2(key, 'source', ('pdf', 'tex', 'pptx'), progress=lambda _: None)
            self.assertEqual(workspace.fingerprint(pdf), workspace.fingerprint(out/'extracted_SOURCE.pdf'))


if __name__ == '__main__':
    unittest.main()
