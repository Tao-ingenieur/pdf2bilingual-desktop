"""Simple UI contract and language-switch regressions (Tk required)."""
import importlib
import os
import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from pdf2bilingual.gui.app import App, LANGUAGES
from pdf2bilingual.gui.i18n import EN, translate


class LanguageTest(unittest.TestCase):
    def setUp(self):
        self.app = App(language='zh')
        self.app.withdraw()
        preferences = patch.object(self.app, 'save_preferences')
        preferences.start()
        self.addCleanup(preferences.stop)
        self.addCleanup(self.app.destroy)

    def test_switch_preserves_inputs_target_model_and_log(self):
        app = self.app
        app.input_var.set('example.pdf')
        app.output_dir.set('D:/output')
        app.output_language.set('bi')
        app.model.set('vision-model')
        app.token.set('not-a-real-key')
        app.model_enabled.set(True)
        app.append_log('[1/4] 正在读取和解析 PDF。')
        app.ui_language.set('English')
        app.change_language()
        self.assertEqual(app.target(), 'bi')
        self.assertEqual(app.input_var.get(), 'example.pdf')
        self.assertEqual(app.output_dir.get(), 'D:/output')
        self.assertEqual(app.model.get(), 'vision-model')
        self.assertEqual(app.token.get(), 'not-a-real-key')
        self.assertTrue(app.model_enabled.get())
        self.assertIn('Reading and extracting', app.log_box.get('1.0', 'end'))
        app.ui_language.set('中文')
        app.change_language()
        self.assertEqual(app.target(), 'bi')

    def test_four_output_choices_and_one_text_area(self):
        self.assertEqual(set(LANGUAGES.values()), {'zh', 'en', 'bi', 'all'})
        widgets = []
        def walk(parent):
            for child in parent.winfo_children():
                widgets.append(child)
                walk(child)
        walk(self.app)
        self.assertEqual(sum(isinstance(w, tk.Text) for w in widgets), 1)
        self.assertFalse(any(w.winfo_class() in ('Treeview', 'TNotebook', 'Canvas') for w in widgets))
        captions = [str(w.cget('text')) for w in widgets if 'text' in w.keys()]
        for caption in captions:
            self.assertNotIn('Codex', caption)
            self.assertNotIn('原貌', caption)
            self.assertNotIn('PPTX', caption)

    def test_all_option_survives_interface_switch(self):
        self.app.output_language.set('all')
        self.app.ui_language.set('English')
        self.app.change_language()
        self.assertEqual(self.app.target(), 'all')

    def test_english_progress_and_errors(self):
        for zh, en in EN.items():
            self.assertEqual(translate(zh, 'en'), en)
            self.assertEqual(translate(zh, 'zh'), zh)
        self.assertEqual(translate('LLM 已连接，第 2 页处理完成。', 'en'), 'LLM connected. Page 2 completed.')

    def test_frozen_config_uses_executable_directory(self):
        import pdf2bilingual.paths as config
        with patch.dict(os.environ, {'PDFBILINGUAL_HOME': ''}), \
             patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, 'executable', r'D:\Portable\PDFBilingual.exe'):
            importlib.reload(config)
            self.assertEqual(config.PROJECT_ROOT, r'D:\Portable')
        importlib.reload(config)

    def test_release_executable_uses_shared_dist_and_config(self):
        import pdf2bilingual.paths as config
        with patch.dict(os.environ, {'PDFBILINGUAL_HOME': ''}), \
             patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, 'executable', r'D:\Portable\dist\release\PDFBilingual.exe'):
            importlib.reload(config)
            self.assertEqual(config.PROJECT_ROOT, r'D:\Portable')
            self.assertEqual(config.INPUT_ROOT, r'D:\Portable\dist\input')
            self.assertEqual(config.CONFIG_ROOT, r'D:\Portable\dist\config')
        importlib.reload(config)


if __name__ == '__main__':
    unittest.main()
