import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from pipeline.exporter import rich_tex
from pipeline.tex2plain import tex2plain


class MathExportTest(unittest.TestCase):
    def test_unbraced_tex_arguments_do_not_swallow_following_sentence(self):
        text = tex2plain(r'$\frac1x$ and $\binom nr$, followed by text.')
        self.assertIn('1/x', text)
        self.assertIn('followed by text.', text)
        self.assertIn('C', text)

    def test_matrix_row_separator_is_not_a_command(self):
        value = r'$\begin{pmatrix}p\\q\\r\end{pmatrix}$'
        self.assertEqual(rich_tex(value), value)
        with self.assertRaises(ValueError):
            rich_tex(r'$\input{secret}$')

    def test_native_equations_preserve_fraction_and_matrix(self):
        from pipeline.office_math import converter, equation
        if converter() is None:
            self.skipTest('optional local Office equation backend unavailable')
        from lxml import etree
        from pipeline.office_math import M
        fraction = etree.fromstring(equation(r'\frac{a+b}{c}'))
        self.assertIsNotNone(fraction.find(f'.//{{{M}}}f'))
        matrix = etree.fromstring(equation(r'\begin{pmatrix}p\\q\\r\end{pmatrix}'))
        self.assertIsNotNone(matrix.find(f'.//{{{M}}}sSup'))
        self.assertIn('pqrT', ''.join(matrix.itertext()))
        self.assertEqual(matrix.find(f'.//{{{M}}}sepChr').get(f'{{{M}}}val'), ',')
