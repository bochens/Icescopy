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

from PySide6.QtWidgets import QApplication, QDialog, QLabel  # noqa: E402
import Icescopy as icescopy_module  # noqa: E402
from icescopy_dialogs import (CSUTemperatureImportDialog, StandardTemperatureImportDialog,
                              UTKTemperatureImportDialog, TAMUTemperatureImportDialog,
                              PKUTemperatureImportDialog, temperature_import_summary_text)  # noqa: E402
from icescopy_temperature_import import (  # noqa: E402
    CSU_COUNT_SOURCE_COMBINED,
    CSU_COUNT_SOURCE_IMAGES,
)


class CSUImportDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def make_dialog(self, **kwargs):
        dialog = CSUTemperatureImportDialog(
            SimpleNamespace(), "", **kwargs
        )
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_all_import_dialogs_have_no_blank_selector_or_remembered_choice(self):
        for cls in (CSUTemperatureImportDialog, StandardTemperatureImportDialog,
                    UTKTemperatureImportDialog, TAMUTemperatureImportDialog, PKUTemperatureImportDialog):
            with self.subTest(dialog=cls.__name__):
                dialog = cls(SimpleNamespace(), "", initial_reset_temperature=0)
                self.addCleanup(dialog.deleteLater)
                dialog.show()
                self.qt_app.processEvents()
                self.assertFalse(hasattr(dialog, "blank_sample_list"))
                self.assertNotIn("blank_sample_names", dialog.get_values())
                self.assertEqual(dialog.get_values()["reset_temperature"], 0)
                self.assertFalse(any("blank" in label.text().lower() for label in dialog.findChildren(QLabel)))
                self.assertEqual(dialog.scroll_area.horizontalScrollBar().maximum(), 0)
                dialog.close()

    def test_existing_combined_method_remains_the_default(self):
        dialog = self.make_dialog()
        self.assertEqual(dialog.get_values()["count_source"], CSU_COUNT_SOURCE_COMBINED)
        self.assertEqual([dialog.count_source_combo.itemText(i)
                          for i in range(dialog.count_source_combo.count())],
                         ["Icescopy only", "Icescopy + .dat"])
        self.assertIn("Run image analysis first", dialog.count_source_help.text())

    def test_source_selection_updates_payload_and_explains_count_provenance(self):
        dialog = self.make_dialog()
        dialog.show()
        for source, help_text in (
            (CSU_COUNT_SOURCE_IMAGES, ".dat count columns are not required"),
            (CSU_COUNT_SOURCE_COMBINED, ".dat counts between images"),
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
        warning = "A recorded count decreased; review the count source."
        summary = {
            "count_source_label": "Icescopy + .dat",
            "count_source": CSU_COUNT_SOURCE_COMBINED,
            "total_cell_count": 5,
            "sample_total_cells": [{"total_cells": 5}],
            "temperature_column": "Sample_Temp",
            "matched_samples": ["Unassigned cells"],
            "total_cell_group_count": 1,
            "total_dat_sample_count": 1,
            "sample_count_matching_used": True,
            "dat_sample_matches": [],
            "matched_image_count": 2,
            "total_image_count": 3,
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
            "reset_temperature": None,
            "count_source": CSU_COUNT_SOURCE_COMBINED,
        }
        with patch.object(icescopy_module, "CSUTemperatureImportDialog", return_value=dialog), \
                patch.object(icescopy_module, "parse_csu_is_dat", return_value=parsed):
            icescopy_module.IceScopy.import_csu_is_dat(window)

        builder.assert_called_once_with(
            parsed, reset_temperature=None,
            count_source=CSU_COUNT_SOURCE_COMBINED,
        )
        details = window.show_detailed_information_dialog.call_args.args[2]
        self.assertIn("Count source: Icescopy + .dat", details)
        self.assertIn("Cell groups: 1 total; 1 included.", details)
        self.assertIn(".dat sample-count columns matched: 0/1.", details)
        self.assertIn("Loaded images matched: 2/3.", details)
        self.assertIn("Included group names: Unassigned cells", details)
        self.assertIn("Temperature column: Sample_Temp", details)
        self.assertIn(warning, details)
        window.log.assert_any_call(f"CSU import warning: {warning}")


class TemperatureImportSummaryTests(unittest.TestCase):
    def timing_summary(self):
        return {
            "matched_samples": ["Unassigned cells"],
            "sample_total_cells": [{"total_cells": 12}],
            "total_cell_count": 12,
            "total_images": 10,
            "parsed_image_count": 8,
            "in_range_image_count": 6,
            "out_of_range_image_count": 2,
            "unparsed_image_count": 2,
            "cycle_count": 1,
        }

    def test_time_matching_shows_partial_coverage_for_images_and_video(self):
        for video_mode, label in ((False, "Images"), (True, "Frames")):
            with self.subTest(video_mode=video_mode):
                message = temperature_import_summary_text(self.timing_summary(), 10, video_mode=video_mode)
                self.assertIn("Cells: 12 total; 12 included.", message)
                self.assertIn(f"{label} with temperatures: 6/10.", message)
                self.assertIn(f"{label} with readable timestamps: 8/10.", message)
                self.assertIn("outside the temperature record", message)
                self.assertIn("no readable timestamp", message)
                self.assertIn("blank temperature fields", message)
                self.assertIn("Output rows: 10.", message)
                self.assertNotIn("synchronized", message)

    def test_pku_describes_record_order_without_claiming_filename_matching(self):
        summary = self.timing_summary()
        summary.update(source_type="pku_linksys32_iml", image_record_count=10,
                       tagged_temperature_count=10, parsed_image_count=10, unparsed_image_count=0)
        message = temperature_import_summary_text(summary, 10)
        self.assertIn("Images paired with .iml records (by order): 10/10.", message)
        self.assertIn("Images with temperatures: 10/10.", message)
        self.assertNotIn("outside", message)
        self.assertNotIn("blank temperature", message)

    def test_excluded_cells_are_visible_without_opening_details(self):
        summary = self.timing_summary()
        summary["total_cell_count"] = 15
        message = temperature_import_summary_text(summary, 10)
        self.assertIn("Cells: 15 total; 12 included.", message)
        self.assertIn("3 cell(s) are not included", message)

    def test_image_only_dat_import_does_not_claim_sample_matching(self):
        summary = self.timing_summary()
        summary.update(count_source=CSU_COUNT_SOURCE_IMAGES, count_source_label="Icescopy only",
                       sample_count_matching_used=False, total_image_count=10, matched_image_count=10)
        message = temperature_import_summary_text(summary, 20)
        self.assertNotIn("sample-count matching", message)
        self.assertIn("Loaded images matched: 10/10.", message)
        self.assertIn("Output rows: 20.", message)
        self.assertNotIn("sample-count columns matched:", message)


if __name__ == "__main__":
    unittest.main()
