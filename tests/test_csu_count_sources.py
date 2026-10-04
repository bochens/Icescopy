import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from icescopy_freeze_count_timeseries import FreezeCountTimeseriesMixin  # noqa: E402
from icescopy_temperature_import import (  # noqa: E402
    CSUISDatRow,
    CSU_COUNT_SOURCE_COMBINED,
    CSU_COUNT_SOURCE_IMAGES,
    CSU_COUNT_SOURCE_INSTRUMENT,
    TemperatureImportError,
)


class CountWindow(FreezeCountTimeseriesMixin):
    """Real count logic with an in-memory cell registry and no GUI or files."""

    def __init__(self, names, samples):
        self.names = list(names)
        self.sample_catalog = {}
        self.cell_records_by_id = {}
        for sample_index, (sample_name, event_lists) in enumerate(samples):
            sample_id = str(sample_index)
            self.sample_catalog[sample_id] = {"sample_name": sample_name}
            for events in event_lists:
                cell_id = len(self.cell_records_by_id)
                self.cell_records_by_id[cell_id] = SimpleNamespace(
                    sample_id=sample_id, freeze_event_indices=list(events)
                )

    def frame_count(self):
        return len(self.names)

    def frame_name(self, index):
        return self.names[index]

    def frame_key(self, index):
        return f"synthetic/{self.names[index]}"

    def ensure_cell_registry_matches_scene_cells(self):
        pass

    def ensure_cell_record(self, cell_id):
        return self.cell_records_by_id.get(cell_id)

    def sample_record_for_id(self, sample_id):
        return self.sample_catalog[str(sample_id)]

    def build_freeze_count_timeseries_sample_column_metadata(self, sample):
        return {key: sample[key] for key in ("sample_id", "sample_name", "total_cells")}


def make_data(temperatures, pictures, counts=None):
    counts = counts or {}
    start = datetime(2026, 1, 1, 12, 0, 0, 360000)
    rows = []
    for index, temperature in enumerate(temperatures):
        timestamp = start + timedelta(seconds=index * 1.25)
        rows.append(CSUISDatRow(
            row_index=index,
            timestamp=timestamp,
            timestamp_text=timestamp.isoformat(sep=" ", timespec="milliseconds"),
            avg_temp=temperature,
            picture_name=pictures.get(index, ""),
            sample_counts={name: values[index] for name, values in counts.items()},
        ))
    return {
        "file_path": "/synthetic/cold-stage.dat",
        "temperature_column": "Sample_Temp",
        "sample_columns": list(counts),
        "rows": rows,
    }


def values(headers, rows, name):
    column = headers.index(name)
    return [int(row[column]) for row in rows]


class CSUCountSourceTests(unittest.TestCase):
    def test_summary_distinguishes_included_groups_from_dat_matches(self):
        window = CountWindow(["a.png", "b.png", "unmatched.png"],
                             [("Sample_0", [[1]]), ("Dust", [[]]), ("temporary", [[]])])
        window.cell_records_by_id[2].sample_id = ""
        data = make_data([-1, -2, -3], {0: "a.png", 1: "b.png", 2: "other.png"},
                         {"Sample_0": [0, 1, 1], "Sample_9": [0, 0, 0]})
        for source, included, matches in (
            (CSU_COUNT_SOURCE_COMBINED, 2, [{"sample_name": "Sample_0", "dat_column": "Sample_0"}]),
            (CSU_COUNT_SOURCE_IMAGES, 3, []),
        ):
            with self.subTest(source=source):
                _, _, summary = window.build_csu_freeze_count_timeseries_results(data, count_source=source)
                self.assertEqual(summary["total_cell_group_count"], 3)
                self.assertEqual(len(summary["matched_samples"]), included)
                self.assertEqual(summary["dat_sample_matches"], matches)
                self.assertEqual(summary["total_dat_sample_count"], 2)
                self.assertEqual(summary["matched_image_count"], 2)
                self.assertEqual(summary["total_image_count"], 3)
                self.assertEqual(summary["sample_count_matching_used"], source == CSU_COUNT_SOURCE_COMBINED)
                self.assertEqual(summary["unmatched_app_samples"],
                                 ["Dust"] if source == CSU_COUNT_SOURCE_COMBINED else [])

    def test_unassigned_cells_are_not_a_dat_sample_match(self):
        window = CountWindow(["a.png", "b.png"], [("temporary", [[1]])])
        window.cell_records_by_id[0].sample_id = ""
        data = make_data([-1, -2], {0: "a.png", 1: "b.png"}, {"Sample_0": [0, 1]})
        _, _, summary = window.build_csu_freeze_count_timeseries_results(data)
        self.assertEqual(summary["matched_samples"], ["Unassigned cells"])
        self.assertEqual(summary["total_cell_group_count"], 1)
        self.assertEqual(summary["dat_sample_matches"], [])
        self.assertEqual(summary["total_dat_sample_count"], 1)

    def test_images_allow_arbitrary_names_without_count_columns_and_hold_until_picture(self):
        window = CountWindow(["Image_0.png", "Image_1.png", "Image_2.png"],
                             [("Dust suspension", [[1], [2]])])
        data = make_data([-1, -2, -3, -4, -5],
                         {0: "Image_0.png", 2: "Image_1.png", 4: "Image_2.png"})
        headers, rows, summary = window.build_csu_freeze_count_timeseries_results(
            data, count_source=CSU_COUNT_SOURCE_IMAGES
        )
        self.assertEqual(values(headers, rows, "Dust suspension number frozen"), [0, 0, 1, 1, 2])
        self.assertEqual(summary["unmatched_app_samples"], [])
        self.assertEqual(summary["temperature_column"], "Sample_Temp")
        self.assertEqual(rows[2][0], "2026-01-01 12:00:02.860")
        self.assertEqual(rows[2][1], "-3.000")

    def test_each_count_source_has_its_own_event_timing_and_default_stays_combined(self):
        window = CountWindow(["a.png", "b.png"], [("Sample_0", [[1], [1], []])])
        data = make_data([-1, -2, -3, -4, -5], {0: "a.png", 4: "b.png"},
                         {"Sample_0": [0, 1, 2, 2, 3]})
        before_cells, before_data = deepcopy(window.cell_records_by_id), deepcopy(data)
        for source, expected in (
            (CSU_COUNT_SOURCE_IMAGES, [0, 0, 0, 0, 2]),
            (CSU_COUNT_SOURCE_INSTRUMENT, [0, 1, 2, 2, 3]),
            (CSU_COUNT_SOURCE_COMBINED, [0, 1, 2, 2, 2]),
        ):
            with self.subTest(source=source):
                headers, rows, summary = window.build_csu_freeze_count_timeseries_results(
                    data, count_source=source
                )
                self.assertEqual(values(headers, rows, "Sample_0 number frozen"), expected)
                self.assertEqual(summary["count_source"], source)
                self.assertEqual(window.cell_records_by_id, before_cells)
                self.assertEqual(data, before_data)
        headers, rows, _ = window.build_csu_freeze_count_timeseries_results(data)
        self.assertEqual(values(headers, rows, "Sample_0 number frozen"), [0, 1, 2, 2, 2])

    def test_instrument_preserves_cold_decrease_without_creating_a_cycle(self):
        window = CountWindow(["a.png", "b.png"], [("Sample_0", [[], []])])
        data = make_data([-12, -14, -15, -16], {0: "a.png", 3: "b.png"},
                         {"Sample_0": [0, 1, 2, 0]})
        headers, rows, summary = window.build_csu_freeze_count_timeseries_results(
            data, reset_temperature=0, count_source=CSU_COUNT_SOURCE_INSTRUMENT
        )
        self.assertEqual(values(headers, rows, "Sample_0 number frozen"), [0, 1, 2, 0])
        self.assertEqual(values(headers, rows, "cycle"), [0, 0, 0, 0])
        self.assertEqual(summary["cycle_count"], 1)
        self.assertTrue(any("decreases are preserved" in warning for warning in summary["warnings"]))
        self.assertEqual([record.freeze_event_indices for record in window.cell_records_by_id.values()], [[], []])

    def test_zero_instrument_counts_do_not_select_image_detections_automatically(self):
        window = CountWindow(["a.png", "b.png"], [("Sample_0", [[1]])])
        data = make_data([-1, -2], {0: "a.png", 1: "b.png"}, {"Sample_0": [0, 0]})
        headers, rows, _ = window.build_csu_freeze_count_timeseries_results(
            data, count_source=CSU_COUNT_SOURCE_INSTRUMENT
        )
        self.assertEqual(values(headers, rows, "Sample_0 number frozen"), [0, 0])

    def test_instrument_rejects_counts_above_assigned_cell_total(self):
        window = CountWindow(["a.png", "b.png"], [("Sample_0", [[], []])])
        data = make_data([-1, -2], {0: "a.png", 1: "b.png"}, {"Sample_0": [0, 3]})
        with self.assertRaisesRegex(TemperatureImportError, "will not clip"):
            window.build_csu_freeze_count_timeseries_results(data, count_source=CSU_COUNT_SOURCE_INSTRUMENT)

    def test_missing_counts_are_rejected_only_when_using_instrument_values(self):
        window = CountWindow(["a.png", "b.png"], [("Sample_0", [[1]])])
        data = make_data([-1, -2], {0: "a.png", 1: "b.png"}, {"Sample_0": [0, None]})
        for source in (CSU_COUNT_SOURCE_INSTRUMENT, CSU_COUNT_SOURCE_COMBINED):
            with self.subTest(source=source), self.assertRaisesRegex(TemperatureImportError, "missing or invalid"):
                window.build_csu_freeze_count_timeseries_results(data, count_source=source)
        headers, rows, _ = window.build_csu_freeze_count_timeseries_results(data, count_source=CSU_COUNT_SOURCE_IMAGES)
        self.assertEqual(values(headers, rows, "Sample_0 number frozen"), [0, 1])

    def test_instrument_requires_drawn_cells_and_a_matching_named_sample(self):
        data = make_data([-1, -2], {0: "a.png", 1: "b.png"}, {"Sample_0": [0, 1]})
        for samples in ([], [("Dust", [[1]])], [("Sample_0", [])]):
            with self.subTest(samples=samples), self.assertRaisesRegex(TemperatureImportError, "draw the cells"):
                CountWindow(["a.png", "b.png"], samples).build_csu_freeze_count_timeseries_results(
                    data, count_source=CSU_COUNT_SOURCE_INSTRUMENT
                )
        no_counts = make_data([-1, -2], {0: "a.png", 1: "b.png"})
        with self.assertRaisesRegex(TemperatureImportError, "draw the cells"):
            CountWindow(["a.png", "b.png"], [("Sample_0", [[1]])]).build_csu_freeze_count_timeseries_results(
                no_counts, count_source=CSU_COUNT_SOURCE_INSTRUMENT
            )

    def test_image_counts_use_first_event_per_cell_in_each_temperature_cycle(self):
        names = [f"Image_{index}.png" for index in range(6)]
        window = CountWindow(names, [("Dust", [[1, 2, 4, 5], [2, 5]])])
        data = make_data([-1, -2, -3, 0.1, -1, -2], dict(enumerate(names)))
        headers, rows, summary = window.build_csu_freeze_count_timeseries_results(
            data, reset_temperature=0, count_source=CSU_COUNT_SOURCE_IMAGES
        )
        self.assertEqual(values(headers, rows, "Dust number frozen"), [0, 1, 2, 0, 1, 2])
        self.assertEqual(values(headers, rows, "cycle"), [0, 0, 0, 1, 1, 1])
        self.assertEqual(summary["freeze_review_cycle_metadata"]["cycle_ids"], [0, 0, 0, 1, 1, 1])
        self.assertEqual(window.cell_records_by_id[0].freeze_event_indices, [1, 2, 4, 5])

    def test_blank_samples_keep_their_own_uncorrected_counts_in_all_sources(self):
        window = CountWindow(["a.png", "b.png", "c.png"],
                             [("Sample_0", [[0], [1], [2]]), ("Sample_blank", [[1]])])
        data = make_data([-1, -2, -3], {0: "a.png", 1: "b.png", 2: "c.png"},
                         {"Sample_0": [1, 2, 3], "Sample_blank": [0, 0, 1]})
        for source, blank_frozen in (
            (CSU_COUNT_SOURCE_IMAGES, [0, 1, 1]),
            (CSU_COUNT_SOURCE_INSTRUMENT, [0, 0, 1]),
            (CSU_COUNT_SOURCE_COMBINED, [0, 1, 1]),
        ):
            with self.subTest(source=source):
                headers, rows, summary = window.build_csu_freeze_count_timeseries_results(
                    data, count_source=source
                )
                self.assertNotIn("water blank correction count", headers)
                self.assertEqual(values(headers, rows, "Sample_0 number total"), [3, 3, 3])
                self.assertEqual(values(headers, rows, "Sample_0 number frozen"), [1, 2, 3])
                self.assertEqual(values(headers, rows, "Sample_blank number total"), [1, 1, 1])
                self.assertEqual(values(headers, rows, "Sample_blank number frozen"), blank_frozen)
                self.assertEqual(summary["matched_samples"], ["Sample_0", "Sample_blank"])
                self.assertTrue(all(item["role"] == "sample" for item in summary["sample_total_cells"]))

    def test_frame_imports_keep_blank_counts_and_reset_each_sample_independently(self):
        start = datetime(2026, 1, 1, 12)
        times = [start + timedelta(seconds=index) for index in range(4)]
        temperatures = [-1, -2, 0.5, -2]
        names = [time.strftime("%Y-%m-%d-%H-%M-%S-%f.png") for time in times]
        window = CountWindow(names, [("Dust", [[1, 3], [3]]), ("Water blank", [[0, 3]])])
        window.is_video_source = lambda: False
        window.imagePaths = names
        window.imageNames = names
        # An old session's remembered choice must have no effect on new counts.
        window.last_temperature_blank_sample_names = ["1"]
        parsed = SimpleNamespace(
            start_timestamp=start, timeseries_datetimes=times,
            timeseries_seconds=[0, 1, 2, 3], temperature_values=temperatures,
            image_records=[SimpleNamespace(timestamp=t, temperature_value=v)
                           for t, v in zip(times, temperatures)],
        )
        for builder in (window.build_standard_freeze_count_timeseries_results,
                        window.build_tamu_freeze_count_timeseries_results,
                        window.build_pku_linksys32_freeze_count_timeseries_results):
            with self.subTest(builder=builder.__name__):
                headers, rows, summary = builder(parsed, reset_temperature=0)
                self.assertNotIn("water blank correction count", headers)
                self.assertEqual(values(headers, rows, "Dust number total"), [2, 2, 2, 2])
                self.assertEqual(values(headers, rows, "Dust number frozen"), [0, 1, 0, 2])
                self.assertEqual(values(headers, rows, "Water blank number total"), [1, 1, 1, 1])
                self.assertEqual(values(headers, rows, "Water blank number frozen"), [1, 1, 0, 1])
                self.assertEqual(summary["matched_samples"], ["Dust", "Water blank"])

    def test_out_of_order_images_are_rejected_in_all_modes(self):
        data = make_data([-1, -2], {0: "a.png", 1: "b.png"}, {"Sample_0": [0, 1]})
        for source in (CSU_COUNT_SOURCE_IMAGES, CSU_COUNT_SOURCE_INSTRUMENT, CSU_COUNT_SOURCE_COMBINED):
            with self.subTest(source=source), self.assertRaisesRegex(TemperatureImportError, "out of order"):
                CountWindow(["b.png", "a.png"], [("Sample_0", [[1]])]).build_csu_freeze_count_timeseries_results(
                    data, count_source=source
                )

    def test_unmatched_event_rejects_image_counts_but_does_not_change_instrument_counts(self):
        window = CountWindow(["a.png", "unknown.png", "b.png"], [("Sample_0", [[1]])])
        data = make_data([-1, -2], {0: "a.png", 1: "b.png"}, {"Sample_0": [0, 1]})
        for source in (CSU_COUNT_SOURCE_IMAGES, CSU_COUNT_SOURCE_COMBINED):
            with self.subTest(source=source), self.assertRaisesRegex(TemperatureImportError, "no matching CSU Picture"):
                window.build_csu_freeze_count_timeseries_results(data, count_source=source)
        headers, rows, summary = window.build_csu_freeze_count_timeseries_results(
            data, count_source=CSU_COUNT_SOURCE_INSTRUMENT
        )
        self.assertEqual(values(headers, rows, "Sample_0 number frozen"), [0, 1])
        self.assertEqual(summary["unmatched_image_count"], 1)
        self.assertTrue(any("no Picture record" in warning for warning in summary["warnings"]))
        self.assertEqual(window.cell_records_by_id[0].freeze_event_indices, [1])


if __name__ == "__main__":
    unittest.main()
