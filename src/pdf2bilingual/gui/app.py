"""Simple Windows frontend: PDF, destination, language, optional LLM, and a log."""
import argparse
import json
import os
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from pdf2bilingual.paths import INPUT_ROOT, OUTPUT_ROOT, WORK_ROOT, CONFIG_ROOT
from pdf2bilingual.pipeline.convert import convert_pdf
from pdf2bilingual.gui.i18n import translate

LANGUAGES = {'中文': 'zh', '英文': 'en', '双语': 'bi', '全部（中文＋英文＋双语）': 'all'}


class App(tk.Tk):
    def __init__(self, language=None):
        super().__init__()
        self.settings_path = Path(CONFIG_ROOT) / 'settings.json'
        try:
            self.preferences = json.loads(self.settings_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.preferences = {}
        stored = self.preferences.get('language', 'zh')
        self.language = language or (stored if stored in ('zh', 'en') else 'zh')
        self.title(self.tr('PDF 转换器'))
        self.geometry('940x660')
        self.minsize(780, 540)
        self.configure(bg='#f4f6fa')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 10))
        style.configure('TFrame', background='#f4f6fa')
        style.configure('TLabel', background='#f4f6fa', foreground='#26354b')
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 20, 'bold'))
        style.configure('TButton', padding=(12, 7))
        style.configure('Accent.TButton', background='#245bc4', foreground='white')
        self.input_var = tk.StringVar()
        self.output_dir = tk.StringVar(value=self.preferences.get('output_dir', OUTPUT_ROOT))
        self.output_language = tk.StringVar(value='zh')
        self.ui_language = tk.StringVar(value='中文' if self.language == 'zh' else 'English')
        self.model_enabled = tk.BooleanVar(value=False)
        self.endpoint = tk.StringVar(value=self.preferences.get('base_url', os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')))
        self.model = tk.StringVar(value=self.preferences.get('model', os.environ.get('OPENAI_MODEL', '')))
        self.token = tk.StringVar(value=os.environ.get('OPENAI_API_KEY', ''))
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = False
        self.log_records = []
        self.controls = []
        self.config_window = None
        self._layout()
        self.append_log('就绪：选择输入 PDF、输出目录和语言，然后点击“生成”。')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.pump_after = self.after(100, self.pump)

    def tr(self, text):
        return translate(text, self.language)

    def button(self, parent, text, command, **kwargs):
        result = ttk.Button(parent, text=self.tr(text), command=command, **kwargs)
        self.controls.append(result)
        return result

    def _layout(self):
        root = ttk.Frame(self, padding=22)
        self.root_frame = root
        root.pack(fill='both', expand=True)
        header = ttk.Frame(root)
        header.pack(fill='x', pady=(0, 20))
        ttk.Label(header, text=self.tr('PDF 转换器'), style='Title.TLabel').pack(side='left')
        self.ui_box = ttk.Combobox(header, textvariable=self.ui_language, values=['中文', 'English'], state='readonly', width=10)
        self.ui_box.pack(side='right')
        self.ui_box.bind('<<ComboboxSelected>>', self.change_language)
        ttk.Label(header, text=self.tr('界面语言')).pack(side='right', padx=8)
        fields = ttk.Frame(root)
        fields.pack(fill='x')
        fields.columnconfigure(1, weight=1)
        for row, label, var, command in [(0, '输入 PDF', self.input_var, self.browse_input),
                                          (1, '输出目录', self.output_dir, self.browse_output)]:
            ttk.Label(fields, text=self.tr(label)).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=6)
            entry = ttk.Entry(fields, textvariable=var)
            entry.grid(row=row, column=1, sticky='ew', pady=6)
            self.controls.append(entry)
            self.button(fields, '浏览…', command).grid(row=row, column=2, padx=(8, 0), pady=6)
        options = ttk.Frame(root)
        options.pack(fill='x', pady=(15, 10))
        ttk.Label(options, text=self.tr('输出语言')).pack(side='left', padx=(0, 12))
        for label, value in LANGUAGES.items():
            radio = ttk.Radiobutton(options, text=self.tr(label), variable=self.output_language, value=value)
            radio.pack(side='left', padx=(0, 14))
            self.controls.append(radio)
        actions = ttk.Frame(root)
        actions.pack(fill='x', pady=(0, 16))
        check = ttk.Checkbutton(actions, text=self.tr('连接 LLM'), variable=self.model_enabled)
        check.pack(side='left')
        self.controls.append(check)
        self.button(actions, '配置 LLM…', self.configure_llm).pack(side='left', padx=12)
        self.start_button = self.button(actions, '生成', self.start, style='Accent.TButton')
        self.start_button.pack(side='right')
        self.cancel_button = ttk.Button(actions, text=self.tr('停止'), command=self.request_stop, state='disabled')
        self.cancel_button.pack(side='right', padx=8)
        self.log_box = ScrolledText(root, wrap='word', font=('Microsoft YaHei UI', 10),
                                   background='white', foreground='#26354b', relief='flat',
                                   padx=12, pady=12, state='disabled')
        self.log_box.pack(fill='both', expand=True)
        self.render_log()

    def save_preferences(self):
        data = {'language': self.language, 'output_dir': self.output_dir.get(),
                'base_url': self.endpoint.get(), 'model': self.model.get()}
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError:
            pass

    def change_language(self, event=None):
        if self.busy:
            self.ui_language.set('中文' if self.language == 'zh' else 'English')
            return
        self.language = 'en' if self.ui_language.get() == 'English' else 'zh'
        self.title(self.tr('PDF 转换器'))
        self.root_frame.destroy()
        self.controls = []
        self._layout()
        self.save_preferences()

    def browse_input(self):
        path = filedialog.askopenfilename(parent=self, title=self.tr('输入 PDF'), initialdir=INPUT_ROOT,
                                          filetypes=[('PDF', '*.pdf')])
        if path:
            self.input_var.set(path)

    def browse_output(self):
        path = filedialog.askdirectory(parent=self, title=self.tr('输出目录'),
                                       initialdir=self.output_dir.get() or OUTPUT_ROOT)
        if path:
            self.output_dir.set(path)

    def configure_llm(self):
        if self.config_window and self.config_window.winfo_exists():
            self.config_window.lift()
            return
        window = tk.Toplevel(self)
        self.config_window = window
        window.title(self.tr('配置 LLM'))
        window.transient(self)
        window.resizable(False, False)
        form = ttk.Frame(window, padding=20)
        form.pack(fill='both', expand=True)
        variables = [tk.StringVar(value=v.get()) for v in (self.endpoint, self.model, self.token)]
        for idx, (label, var) in enumerate(zip(('Base URL', '模型', 'API Key'), variables)):
            ttk.Label(form, text=self.tr(label)).grid(row=idx, column=0, sticky='w', pady=7, padx=(0, 12))
            ttk.Entry(form, textvariable=var, width=54, show='•' if idx == 2 else '').grid(row=idx, column=1, sticky='ew', pady=7)
        ttk.Label(form, text=self.tr('使用支持图片输入的兼容接口。API Key 仅保留在本次运行中。'),
                  wraplength=490).grid(row=3, column=0, columnspan=2, sticky='w', pady=12)
        def save():
            for target, var in zip((self.endpoint, self.model, self.token), variables):
                target.set(var.get().strip())
            self.save_preferences()
            self.append_log('LLM 配置已保存。只有勾选“连接 LLM”且处理需要时，才会发送请求。')
            window.destroy()
        ttk.Button(form, text=self.tr('保存'), command=save).grid(row=4, column=1, sticky='e')
        window.grab_set()

    def target(self):
        return self.output_language.get()

    def append_log(self, message):
        self.log_records.append((datetime.now().strftime('%H:%M:%S'), message))
        self.render_log()

    def render_log(self):
        self.log_box.configure(state='normal')
        self.log_box.delete('1.0', 'end')
        for stamp, message in self.log_records:
            self.log_box.insert('end', f'[{stamp}] {self.tr(message)}\n')
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def log(self, message):
        self.events.put(('log', message))

    def set_busy(self, busy):
        self.busy = busy
        for control in self.controls:
            control.configure(state='disabled' if busy else 'normal')
        self.ui_box.configure(state='disabled' if busy else 'readonly')
        self.cancel_button.configure(state='normal' if busy else 'disabled')

    def start(self):
        if self.busy:
            return
        source, output, target = self.input_var.get().strip(), self.output_dir.get().strip(), self.target()
        enabled, endpoint, model, token = self.model_enabled.get(), self.endpoint.get(), self.model.get(), self.token.get()
        if not source or not output:
            self.append_log('请先选择输入 PDF 和输出目录。')
            return
        self.save_preferences()
        self.stop.clear()
        self.set_busy(True)
        self.append_log('开始生成。三种格式将自动一起生成。')
        self.append_log('已启用 LLM，将在需要时自动连接。' if enabled else 'LLM 未启用，先尝试本地处理。')
        def worker():
            try:
                result = convert_pdf(source, output, target, enabled, endpoint, model, token,
                                     progress=self.log, cancelled=self.stop.is_set)
                self.events.put(('done', result))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def pump(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self.append_log(value)
                else:
                    self.set_busy(False)
                    if kind == 'error':
                        self.append_log('处理已停止。')
                        self.append_log(value)
        except queue.Empty:
            pass
        self.pump_after = self.after(100, self.pump)

    def request_stop(self):
        self.stop.set()
        self.append_log('正在停止；当前页结束后保存进度。')

    def close(self):
        if self.busy:
            self.request_stop()
            return
        self.destroy()

    def destroy(self):
        if getattr(self, 'pump_after', None):
            self.after_cancel(self.pump_after)
        super().destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description='PDF Converter GUI')
    parser.add_argument('--language', choices=['zh', 'en'])
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    app = App(language=args.language)
    if args.self_test:
        from unittest.mock import patch
        from pdf2bilingual.paths import PROJECT_ROOT
        app.update()
        original = app.language
        app.output_language.set('bi')
        app.ui_language.set('English' if original == 'zh' else '中文')
        with patch.object(app, 'save_preferences'):
            app.change_language()
            app.update()
        assert app.target() == 'bi'
        assert not app.model_enabled.get()
        assert isinstance(app.log_box, ScrolledText)
        text = app.log_box.get('1.0', 'end')
        assert 'Codex' not in text and '原貌' not in text
        import pdfplumber
        import pypdfium2
        import pptx
        stats = next(iter(Path(INPUT_ROOT).glob('*tat*.pdf')), None)
        result = {'ok': True, 'frozen': bool(getattr(sys, 'frozen', False)), 'workspace': PROJECT_ROOT,
                  'initial_language': original, 'switched_language': app.language, 'single_log': True,
                  'output_choices': list(LANGUAGES.values()), 'model_enabled': False}
        if stats:
            from pdf2bilingual.pipeline.workspace import NeedsModel
            destination = Path(WORK_ROOT).parent / 'qa' / 'simplified-exe-output'
            logs = []
            try:
                convert_pdf(stats, destination, 'bi', progress=logs.append)
            except NeedsModel:
                result['incomplete_blocked'] = True
            else:
                raise AssertionError('Incomplete bilingual input must stop without LLM')
            result['final_files'] = list(str(p) for p in destination.glob('*'))
            assert not result['final_files']
            result['log_steps'] = logs
        app.destroy()
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    app.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        if '--self-test' in sys.argv and '--report' in sys.argv:
            import traceback
            report = Path(sys.argv[sys.argv.index('--report')+1])
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps({'ok': False, 'error': traceback.format_exc()}), encoding='utf-8')
            raise SystemExit(1)
        raise
