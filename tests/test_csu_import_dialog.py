import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402
import Icescopy as icescopy_module  # noqa: E402
from icescopy_dialogs import CSUTemperatureImportDialog  # noqa: E402
from icescopy_temperature_import import (  # noqa: E402
    CSU_COUNT_SOURCE_COMBINED,
    CSU_COUNT_SOURCE_IMAGES,
    CSU_COUNT_SOURCE_INSTRUMENT,
)


class CSUImportDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def make_dialog(self, **kwargs):
        dialog = CSUTemperatureImportDialog(
            SimpleNamespace(), "", ["Sample_0"], **kwargs
        )
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_existing_combined_method_remains_the_default(self):
        dialog = self.make_dialog()
        self.assertEqual(dialog.get_values()["count_source"], CSU_COUNT_SOURCE_COMBINED)
        self.assertIn("Run image analysis first", dialog.count_source_help.text())

    def test_source_selection_updates_payload_and_explains_count_provenance(self):
        dialog = self.make_dialog()
        dialog.show()
        for source, help_text in (
            (CSU_COUNT_SOURCE_IMAGES, "CSU count columns are not required"),
            (CSU_COUNT_SOURCE_INSTRUMENT, "including any decreases"),
            (CSU_COUNT_SOURCE_COMBINED, "CSU counts between pictures"),
        ):
            with self.subTest(source=source):
                dialog.count_source_combo.setCurrentIndex(dialog.count_source_combo.findData(source))
                self.qt_app.processEvents()
                self.assertEqual(dialog.get_values()["count_source"], source)
                self.assertIn(help_text, dialog.count_source_help.text())
                self.assertTrue(dialog.count_source_help.wordWrap())
                self.assertEqual(dialog.scroll_area.horizontalScrollBar().maximum(), 0)
        dialog.close()

    def test_controller_passes_count_source_and_displays_import_warnings(self):
        warning = "A recorded count decreased; the original values were preserved."
        summary = {
            "count_source_label": "CSU recorded counts",
            "temperature_column": "Sample_Temp",
            "matched_samples": ["Sample_0"],
            "matched_picture_rows": 2,
            "total_picture_rows": 2,
            "warnings": [warning],
        }
        parsed = {"temperature_column": "Sample_Temp"}
        builder = Mock(return_value=(["timestamp"], [["2026-01-01"]], summary))
        window = SimpleNamespace(
            has_frames=lambda: True,
            is_video_source=lambda: False,
            available_sample_choices=lambda: ["Sample_0"],
            last_temperature_import_path="",
            build_csu_freeze_count_timeseries_results=builder,
            normalize_temperature_reset_threshold=lambda value: value,
            set_freeze_count_timeseries_results=Mock(),
            show_detailed_information_dialog=Mock(),
            log=Mock(),
        )
        dialog = Mock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.get_values.return_value = {
            "file_path": "/synthetic/cold-stage.dat",
            "blank_sample_names": [],
            "reset_temperature": None,
            "count_source": CSU_COUNT_SOURCE_INSTRUMENT,
        }
        with patch.object(icescopy_module, "CSUTemperatureImportDialog", return_value=dialog), \
                patch.object(icescopy_module, "parse_csu_is_dat", return_value=parsed):
            icescopy_module.IceScopy.import_csu_is_dat(window)

        builder.assert_called_once_with(
            parsed, blank_sample_names=[], reset_temperature=None,
            count_source=CSU_COUNT_SOURCE_INSTRUMENT,
        )
        details = window.show_detailed_information_dialog.call_args.args[2]
        self.assertIn("Count source: CSU recorded counts", details)
        self.assertIn("Temperature column: Sample_Temp", details)
        self.assertIn(warning, details)
        window.log.assert_any_call(f"CSU import warning: {warning}")


if __name__ == "__main__":
    unittest.main()
