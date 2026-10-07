"""Exercise process-exit reporting without a toolkit installation."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication, QProcess
from icescopy_inptk_client import ToolkitTransport


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_exit_reports_final_stderr_once_and_limits_its_size(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'failure.py'
            script.write_text("import sys\nsys.stderr.write('x' * 12000 + '\\nCalculation failed: invalid input\\n')\nsys.exit(7)\n")
            worker = ToolkitTransport()
            self.addCleanup(worker.close)
            failures = []
            worker.failure.connect(lambda epoch, message: failures.append((epoch, message)))
            class ScriptProcess(QProcess):
                def start(self, _path, _args):
                    super().start(sys.executable, [str(script)])
            with patch('icescopy_inptk_client.QProcess', ScriptProcess):
                worker.start(9, str(script))
                self.assertTrue(worker.process.waitForFinished(10000))
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0][0], 9)
            self.assertIn('code 7', failures[0][1])
            self.assertIn('Calculation failed: invalid input', failures[0][1])
            self.assertLess(len(failures[0][1]), 8100)
            self.assertEqual(len(worker.stderr_tail), 8000)
