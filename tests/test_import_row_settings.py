"""Stop-at-last-image and leave-out-warming settings for every count importer."""
import json
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_count_builder_characterization import (  # adds src/ to sys.path
    SyntheticWindow,
    TAMU_NAMES,
    pku_log,
    standard_log,
    tamu_log,
)
from test_csu_count_sources import CountWindow, make_data, values
from PySide6.QtWidgets import QApplication

from icescopy_dialogs import (
    CSUTemperatureImportDialog,
    PKUTemperatureImportDialog,
    StandardTemperatureImportDialog,
    TAMUTemperatureImportDialog,
    UTKTemperatureImportDialog,
    row_settings_notes,
)
from icescopy_freeze_count_timeseries import leave_out_warming_rows, warming_row_flags
from icescopy_temperature_import import (
    CSU_COUNT_SOURCE_COMBINED,
    CSU_COUNT_SOURCE_IMAGES,
    CSU_COUNT_SOURCE_INSTRUMENT,
)
from icescopy_temperature_refresh import rebuild_temperature_counts

OFF = {"stop_at_last_image": False, "leave_out_warming": False}
HEADERS = ["timestamp", "temperature_C", "cycle", "picture", "S number total", "S number frozen"]


def table(temperatures, frozen, cycles=None):
    cycles = cycles or [0] * len(temperatures)
    return [["", f"{t:.3f}", str(c), "", "4", str(f)] for t, c, f in zip(temperatures, cycles, frozen)]


class WarmingRowTests(unittest.TestCase):
    def test_jitter_and_drift_before_cooling_are_kept(self):
        # Room-temperature drift, then cooling with 0.06 C sensor jitter.
        rows = table([21.4, 21.5, 21.45, -1.0, -2.0, -1.94, -3.0], [0] * 7)
        self.assertEqual(warming_row_flags(HEADERS, rows, 0.2), [False] * 7)

    def test_warm_up_after_the_coldest_reading_is_left_out_and_counts_stay_cumulative(self):
        rows = table([-5, -10, -8, -12, -20, 14], [0, 1, 2, 3, 4, 4])
        kept, omitted, warnings = leave_out_warming_rows(HEADERS, rows, 0.2)
        self.assertEqual([row[1] for row in kept], ["-5.000", "-10.000", "-12.000", "-20.000"])
        # The event on the left-out -8 C row is included in the next kept row.
        self.assertEqual([row[5] for row in kept], ["0", "1", "3", "4"])
        self.assertEqual(omitted, {"0": 2})
        self.assertEqual(warnings, [])

    def test_events_after_the_last_kept_row_are_warned(self):
        rows = table([-5, -10, -20, 0, 5], [0, 1, 2, 3, 3])
        kept, omitted, warnings = leave_out_warming_rows(HEADERS, rows, 0.2)
        self.assertEqual(len(kept), 3)
        self.assertEqual(omitted, {"0": 2})
        self.assertEqual(warnings, [
            "S: 1 freeze event(s) in cycle 0 fall on warming rows after its last kept row and are not counted."
        ])

    def test_each_cycle_has_its_own_coldest_reading(self):
        rows = table([-5, -20, 3, 6, -2, -8], [0, 2, 2, 0, 1, 3], cycles=[0, 0, 0, 1, 1, 1])
        kept, omitted, _ = leave_out_warming_rows(HEADERS, rows, 0.2)
        self.assertEqual([(row[1], row[2]) for row in kept],
                         [("-5.000", "0"), ("-20.000", "0"), ("6.000", "1"), ("-2.000", "1"), ("-8.000", "1")])
        self.assertEqual(omitted, {"0": 1})

    def test_rows_without_temperature_are_kept(self):
        rows = table([-5, -10, -6], [0, 1, 1])
        rows.insert(2, ["", "", "0", "", "4", "1"])
        self.assertEqual(warming_row_flags(HEADERS, rows, 0.2), [False, False, False, True])


class ImporterRowSettingTests(unittest.TestCase):
    """Each importer honors both settings, defaults them on, and refreshes with them."""

    def check_settings(self, build, expected_warming_rows, refresh_window=None):
        headers, off_rows, off_summary = build(**OFF)
        self.assertFalse(off_summary["leave_out_warming"])
        self.assertEqual(off_summary["warming_rows_omitted"], 0)
        headers, on_rows, summary = build()
        self.assertTrue(summary["stop_at_last_image"])
        self.assertTrue(summary["leave_out_warming"])
        self.assertEqual(summary["warming_tolerance_c"], 0.2)
        self.assertEqual(summary["warming_rows_omitted"], expected_warming_rows)
        self.assertEqual(len(off_rows) - len(on_rows), expected_warming_rows)
        # Kept rows are unchanged, so counts and cycles do not move.
        self.assertTrue(all(row in off_rows for row in on_rows))
        if refresh_window is not None:
            context = json.loads(json.dumps(summary["refresh_context"]))
            self.assertEqual(rebuild_temperature_counts(refresh_window, context)[1], on_rows)
            off_context = json.loads(json.dumps(off_summary["refresh_context"]))
            self.assertEqual(rebuild_temperature_counts(refresh_window, off_context)[1], off_rows)
        return summary

    def test_standard(self):
        window = SyntheticWindow(TAMU_NAMES)
        self.check_settings(
            lambda **settings: window.build_standard_freeze_count_timeseries_results(
                standard_log(), reset_temperature=0, **settings),
            1, window)

    def test_standard_without_reset_treats_a_second_cooling_as_warming(self):
        window = SyntheticWindow(TAMU_NAMES)
        summary = self.check_settings(
            lambda **settings: window.build_standard_freeze_count_timeseries_results(
                standard_log(), **settings),
            4)
        self.assertEqual(summary["warming_rows_omitted_by_cycle"], {"0": 4})

    def test_tamu(self):
        window = SyntheticWindow(TAMU_NAMES)
        self.check_settings(
            lambda **settings: window.build_tamu_freeze_count_timeseries_results(
                tamu_log(), reset_temperature=0, **settings),
            1, window)

    def test_pku(self):
        names = [f"img{index}.bmp" for index in range(10)]
        seconds = [3.0 + 9.0 * index for index in range(10)]
        window = SyntheticWindow(names)
        log = pku_log(seconds)
        log.image_records[4].temperature_value = 5.0  # a warm reading after -7.25 C
        self.check_settings(
            lambda **settings: window.build_pku_linksys32_freeze_count_timeseries_results(
                log, **settings),
            1, window)

    def test_csu_in_every_count_source(self):
        window = CountWindow(["Image_0.png", "Image_1.png", "Image_2.png"],
                             [("Sample_0", [[1], [2], [2]])])
        # Cooling, a warm excursion with no image, the last image, then a warm-up record.
        data = make_data([2, -10, -20, -15, -25, 14, 14],
                         {1: "Image_0.png", 2: "Image_1.png", 4: "Image_2.png", 5: "Image_3.png"},
                         {"Sample_0": [0, 0, 1, 1, 3, 3, 3]})
        for source in (CSU_COUNT_SOURCE_COMBINED, CSU_COUNT_SOURCE_IMAGES, CSU_COUNT_SOURCE_INSTRUMENT):
            with self.subTest(source=source):
                build = lambda **settings: window.build_csu_freeze_count_timeseries_results(
                    data, count_source=source, **settings)
                headers, rows, summary = build()
                self.assertEqual([row[1] for row in rows], ["2.000", "-10.000", "-20.000", "-25.000"])
                self.assertEqual(values(headers, rows, "Sample_0 number frozen")[-1], 3)
                self.assertEqual(summary["trailing_rows_omitted"], 2)
                self.assertEqual(summary["warming_rows_omitted_by_cycle"], {"0": 1})
                headers, rows, summary = build(stop_at_last_image=False)
                self.assertEqual(summary["trailing_rows_omitted"], 0)
                self.assertEqual(summary["warming_rows_omitted_by_cycle"], {"0": 3})
                headers, rows, summary = build(leave_out_warming=False)
                self.assertEqual(len(rows), 5)
                headers, rows, summary = build(**OFF)
                self.assertEqual(len(rows), 7)

    def test_summary_text_reports_left_out_rows_per_cycle(self):
        summary = {"trailing_rows_omitted": 13, "warming_tolerance_c": 0.2,
                   "warming_rows_omitted_by_cycle": {"0": 2, "1": 5}}
        self.assertEqual(row_settings_notes(summary), [
            "Left out 13 record(s) after the last loaded image.",
            "Left out 7 warming row(s) (cycle 0: 2, cycle 1: 5; tolerance 0.2 °C).",
        ])
        self.assertEqual(row_settings_notes({}), [])


class ImportDialogRowSettingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_every_import_dialog_offers_both_settings(self):
        for cls, rows_are_images in ((CSUTemperatureImportDialog, False),
                                     (StandardTemperatureImportDialog, True),
                                     (UTKTemperatureImportDialog, True),
                                     (TAMUTemperatureImportDialog, True),
                                     (PKUTemperatureImportDialog, True)):
            with self.subTest(dialog=cls.__name__):
                dialog = cls(SimpleNamespace(), "")
                self.addCleanup(dialog.deleteLater)
                self.assertEqual(
                    {key: dialog.get_values()[key] for key in ("stop_at_last_image", "leave_out_warming")},
                    {"stop_at_last_image": True, "leave_out_warming": True})
                self.assertEqual(dialog.stop_at_last_image_checkbox.isEnabled(), not rows_are_images)
                dialog = cls(SimpleNamespace(), "", initial_row_settings=OFF)
                self.addCleanup(dialog.deleteLater)
                values = dialog.get_values()
                self.assertFalse(values["leave_out_warming"])
                self.assertEqual(values["stop_at_last_image"], rows_are_images)
                dialog.show()
                self.qt_app.processEvents()
                self.assertEqual(dialog.scroll_area.horizontalScrollBar().maximum(), 0)
                dialog.close()


if __name__ == "__main__":
    unittest.main()
