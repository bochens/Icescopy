"""Pin the exact output of the standard, TAMU and PKU count builders.

Each case builds a small synthetic session, runs one builder and then
prepare_source on its table. The expected results in
characterization/count_builders.json were recorded from the code at main
e8a7b1e. A difference means the output changed.
"""
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from test_csu_count_sources import CountWindow  # adds src/ to sys.path
from icescopy_inptk_data import prepare_source
from icescopy_temperature_import import (
    IMAGE_TIMESTAMP_SOURCE_GENERATED,
    IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS,
    Linksys32IMLImageRecord,
    Linksys32IMLTimeseries,
    StandardTemperatureTimeseries,
    TAMULinkamTimeseries,
)
from icescopy_temperature_refresh import encode_temperature_input


EXPECTED_PATH = Path(__file__).resolve().parent / "characterization" / "count_builders.json"
START = datetime(2026, 1, 1, 12, 0, 0)

# Temperatures for a log sampled every 10 s: cool, warm above 0 C, cool again.
LOG_TEMPERATURES = [-1.0, -6.5, -12.25, -18.0, 2.0, 4.0, -3.5, -9.0, -15.75, -21.0]

# (sample name, freeze frames per cell). The blank name drops its cell from
# the sample groups. "bad" and 99 are ignored frame values.
SAMPLES = [
    ("Sample B", [[2], [3, 8], [], [7]]),
    ("sample a", [[1, 7], ["bad", 4]]),
    ("", [[5]]),
    ("Blank", [[3], [8], [99]]),
]
UNASSIGNED_CELL_EVENTS = [[6], [2, 9]]

# One metadata dict per sample, in the order of the builder's sample columns.
PREPARE_METADATA = [
    {"sample_type": "water blank", "well_volume_uL": "50"},
    {"sample_type": "", "dilution": "1", "well_volume_uL": "50", "air_volume_L": "100"},
    {"sample_type": "aerosol", "dilution": "10", "well_volume_uL": "NA"},
    {},
]


class SyntheticWindow(CountWindow):
    def __init__(self, names, samples=SAMPLES, unassigned=UNASSIGNED_CELL_EVENTS,
                 video_frame_seconds=None):
        super().__init__(names, samples)
        for events in unassigned:
            self.cell_records_by_id[len(self.cell_records_by_id)] = SimpleNamespace(
                sample_id="", freeze_event_indices=list(events))
        self.imageNames = list(names)
        self.imagePaths = [f"/synthetic/{name}" for name in names]
        self.video_frame_seconds = video_frame_seconds
        self.last_temperature_calibration_path = "/synthetic/calibration.csv"

    def is_video_source(self):
        return self.video_frame_seconds is not None

    def active_frame_source(self):
        return SimpleNamespace(frame_time_seconds=lambda index: self.video_frame_seconds[index])


def tamu_name(seconds):
    return (START + timedelta(seconds=seconds)).strftime("%Y-%m-%d-%H-%M-%S-%f") + ".png"


def standard_log(temperatures=LOG_TEMPERATURES):
    times = [START + timedelta(seconds=10 * index) for index in range(len(temperatures))]
    return StandardTemperatureTimeseries(
        "/synthetic/standard.csv", times, [t.isoformat(sep=" ") for t in times],
        list(temperatures), len(temperatures))


def tamu_log():
    return TAMULinkamTimeseries(
        "/synthetic/linkam.xlsx", START, START.isoformat(sep=" "),
        [10.0 * index for index in range(len(LOG_TEMPERATURES))],
        list(LOG_TEMPERATURES), 10.0, len(LOG_TEMPERATURES))


def pku_log(image_seconds):
    times = [START + timedelta(seconds=10 * index) for index in range(len(LOG_TEMPERATURES))]
    records = []
    for index, seconds in enumerate(image_seconds):
        timestamp = None if seconds is None else START + timedelta(seconds=seconds)
        records.append(Linksys32IMLImageRecord(
            index, 1000 * index, 900, timestamp, "" if timestamp is None else timestamp.isoformat(),
            -0.5 - 2.25 * index, "OK", ""))
    return Linksys32IMLTimeseries(
        "/synthetic/run.iml", "3.2", START, START.isoformat(sep=" "), 10.0,
        [10.0 * index for index in range(len(times))], times, [t.isoformat() for t in times],
        list(LOG_TEMPERATURES), ["OK"] * len(times), len(times), records, len(records))


# Ten frames, one every 9.5 s from -4 s, so the first and last frames fall
# outside the log and one name has no timestamp.
FRAME_SECONDS = [-4.0 + 9.5 * index for index in range(10)]
TAMU_NAMES = [tamu_name(seconds) for seconds in FRAME_SECONDS]
TAMU_NAMES[5] = "notes.png"


def case_standard_filenames():
    window = SyntheticWindow(TAMU_NAMES)
    return window.build_standard_freeze_count_timeseries_results(standard_log(), reset_temperature=0)


def case_standard_video_pts():
    seconds = [None if index == 3 else 1.5 + 9.5 * index for index in range(10)]
    window = SyntheticWindow([f"frame {index:04d}" for index in range(10)], video_frame_seconds=seconds)
    return window.build_standard_freeze_count_timeseries_results(
        standard_log(), image_timestamp_source=IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS,
        generated_start_text=START.isoformat(sep=" "), reset_temperature=-0.5)


def case_standard_video_generated_no_reset():
    window = SyntheticWindow([f"frame {index:04d}" for index in range(10)], video_frame_seconds=[0.0] * 10)
    return window.build_standard_freeze_count_timeseries_results(
        standard_log(), image_timestamp_source=IMAGE_TIMESTAMP_SOURCE_GENERATED,
        generated_start_text=(START + timedelta(seconds=3)).isoformat(sep=" "),
        frame_interval_seconds="9.25")


def case_tamu_calibrated():
    window = SyntheticWindow(TAMU_NAMES)
    calibration = {0: (1.02, 0.4), 1: (0.97, -0.15), 4: (0, 1.0), 7: (1.1, 0.0), 12: (1.0, 0.25)}
    return window.build_tamu_freeze_count_timeseries_results(
        tamu_log(), calibration_by_well=calibration, reset_temperature=0)


def case_tamu_all_cells():
    window = SyntheticWindow(TAMU_NAMES, samples=[("", [[2], [4, 9], [7]])], unassigned=[])
    return window.build_tamu_freeze_count_timeseries_results(tamu_log())


def case_pku():
    image_seconds = [None if index == 6 else 3.0 + 9.0 * index for index in range(10)]
    window = SyntheticWindow([f"img{index}.bmp" for index in range(10)])
    return window.build_pku_linksys32_freeze_count_timeseries_results(
        pku_log(image_seconds), reset_temperature=0)


CASES = {
    "standard_filenames": case_standard_filenames,
    "standard_video_pts": case_standard_video_pts,
    "standard_video_generated_no_reset": case_standard_video_generated_no_reset,
    "tamu_calibrated": case_tamu_calibrated,
    "tamu_all_cells": case_tamu_all_cells,
    "pku": case_pku,
}


def prepared_source(headers, rows):
    try:
        source = prepare_source(headers, rows, PREPARE_METADATA)
    except ValueError as error:
        return {"error": str(error)}
    # The preview table rows repeat the pinned counts, so keep only its columns.
    source["preview"]["table"]["rows"] = len(source["preview"]["table"]["rows"])
    return source


def current_outputs():
    outputs = {}
    for name, build in CASES.items():
        headers, rows, summary = build()
        outputs[name] = json.loads(json.dumps(encode_temperature_input({
            "headers": headers,
            "rows": rows,
            "summary": summary,
            "prepare_source": prepared_source(headers, rows),
        })))
    return outputs


class CountBuilderCharacterizationTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
        cls.actual = current_outputs()

    def test_cases_match_recorded_cases(self):
        self.assertEqual(sorted(self.actual), sorted(self.expected))

    def check(self, name, part):
        self.assertEqual(self.actual[name][part], self.expected[name][part])

    def test_headers_and_rows(self):
        for name in CASES:
            for part in ("headers", "rows"):
                with self.subTest(case=name, part=part):
                    self.check(name, part)

    def test_summary(self):
        for name in CASES:
            with self.subTest(case=name):
                self.check(name, "summary")

    def test_prepare_source(self):
        for name in CASES:
            with self.subTest(case=name):
                self.check(name, "prepare_source")


if __name__ == "__main__":
    unittest.main()
