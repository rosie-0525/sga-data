import importlib.util
import pathlib
import unittest


CONVERT_PATH = pathlib.Path(__file__).with_name('convert.py')
SPEC = importlib.util.spec_from_file_location('sga45_convert', CONVERT_PATH)
convert = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(convert)


class RegisterAndStripDefsTests(unittest.TestCase):
    def test_strips_bibtex_providecommand_preamble(self):
        source = r'''\providecommand{\MRhref}[2]{
  \href{http://www.ams.org/mathscinet-getitem?mr=#1}{#2}
}
\providecommand{\href}[2]{#2}
\begin{thebibliography}{10}
'''

        cleaned = convert.register_and_strip_defs(source)

        self.assertNotIn('mathscinet-getitem', cleaned)
        self.assertNotIn('#1', cleaned)
        self.assertIn(r'\begin{thebibliography}{10}', cleaned)


if __name__ == '__main__':
    unittest.main()
