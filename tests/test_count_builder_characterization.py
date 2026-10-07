"""Pin the exact output of the standard, TAMU and PKU count builders.

Each case builds a small synthetic session, runs one builder and then
prepare_source on its table. EXPECTED_SHA256 holds a hash of each part,
recorded from the code at main e8a7b1e. A different hash means the output
changed; the failure message prints the new output.
"""
import hashlib
import json
import unittest
from datetime import datetime, timedelta
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
            # Sessions save the summary with json.dumps and no key sorting.
            "summary_keys": list(summary),
            "prepare_source": prepared_source(headers, rows),
        })))
    return outputs


EXPECTED_SHA256 = {
    "pku": {
        "headers": "ffc561fec07ad0d367315aa8d7f68210e9e071fbacf91ef0f384ce6354eb6290",
        "rows": "fb76deaf0befc09344deaf892c733d56235b6fca64afcbbcd8d83a9f6e037c21",
        "summary": "1351f819b74e7b206e6ca828e347fc63c6b322f4bf0966b5f5d24dd85f7af4c4",
        "summary_keys": "48cfac5e42a9b602fa9fdc0f1ab781c278779c5f24bd00513bce226953224ac2",
        "prepare_source": "8c9abbee283d9e6552c689aa3b18e756b9402646ca5c3c77c391af9be6c53fc9",
    },
    "standard_filenames": {
        "headers": "ffc561fec07ad0d367315aa8d7f68210e9e071fbacf91ef0f384ce6354eb6290",
        "rows": "3086a6c6920f439d00309ae27d8529171f95e0fedd0bf5473ebde63bcabe5d42",
        "summary": "8f9463450d6ecd30ec5c6ab0285093e469dd1b024cda0603f73a10ed9d2164c6",
        "summary_keys": "5ee8db475aa73b89bf9bf1bf9c66bbdff0283a7aa6110d65a38d1186f6dcb4c4",
        "prepare_source": "ecd0024f4f2a118caae89a8196428f486b2bd5277f6f82cebba0bc77338028bd",
    },
    "standard_video_generated_no_reset": {
        "headers": "ffc561fec07ad0d367315aa8d7f68210e9e071fbacf91ef0f384ce6354eb6290",
        "rows": "85fc2cbb264c8fa386f3fd8984c5a0a91f8d4c214e470317773a8a1e765dc726",
        "summary": "fde0db025a91a53ba70154b128e84b721651e3dd6221d257ef639d5cc30e442b",
        "summary_keys": "5ee8db475aa73b89bf9bf1bf9c66bbdff0283a7aa6110d65a38d1186f6dcb4c4",
        "prepare_source": "4faad5eba1e1b3c92199eb2302b2f15ea94dd91e48e38f23e3a8a1a72436b03c",
    },
    "standard_video_pts": {
        "headers": "ffc561fec07ad0d367315aa8d7f68210e9e071fbacf91ef0f384ce6354eb6290",
        "rows": "4800cd730dde92fe920200feb8c9a0c315d7a12c0843f7dde451afef98f4d103",
        "summary": "dac363b4d966612b3180f805c10b21084845e8c93c529fc24e874a39f21bec94",
        "summary_keys": "5ee8db475aa73b89bf9bf1bf9c66bbdff0283a7aa6110d65a38d1186f6dcb4c4",
        "prepare_source": "641840d30fd15f5be5f67f2c831d9df3acfc473dab8caf3c3b30447e83d54dcf",
    },
    "tamu_all_cells": {
        "headers": "2c04af2c6d06884098723e098303c3c177cc907b392c2fecb49204c2495f41f7",
        "rows": "b72a11e6c388b651ad1ac2102afa5f3eeb4670359d0460e63b41c5849f9cd3ef",
        "summary": "b0750646db9ab4be52dd46603ee098fbbee4a60830baefdd0937636ef6577fe8",
        "summary_keys": "809ec139c2d37c93bddbf04e867133b45522e3c8ea9789ec6f85b7c89d1fd5b0",
        "prepare_source": "e2e7bc8356a40920c7b63c8af88f3a331579a12dcc6061de58a879cf21a26f39",
    },
    "tamu_calibrated": {
        "headers": "2ed0203f2882ba0553bc1fc139c1577608967cbba2590945756adb35e539001f",
        "rows": "6802ab3d49816922c838235717f06cbb2d868f05bb45501a0bbe21ccb7ee0012",
        "summary": "95605d37e0379c73a4d6d49e30478be603f507ea29acb8dc04e056ab06a1f8b8",
        "summary_keys": "809ec139c2d37c93bddbf04e867133b45522e3c8ea9789ec6f85b7c89d1fd5b0",
        "prepare_source": "8d232aecd1a6bb14a5664b609670f168f2f3da78c577a556e3463da31c54872c",
    },
}


def output_text(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class CountBuilderCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = current_outputs()

    def test_cases_match_recorded_cases(self):
        self.assertEqual(sorted(self.actual), sorted(EXPECTED_SHA256))

    def check(self, name, part):
        text = output_text(self.actual[name][part])
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.assertEqual(digest, EXPECTED_SHA256[name][part], f"{name} {part} changed:\n{text}")

    def test_headers_and_rows(self):
        for name in CASES:
            for part in ("headers", "rows"):
                with self.subTest(case=name, part=part):
                    self.check(name, part)

    def test_summary(self):
        for name in CASES:
            for part in ("summary", "summary_keys"):
                with self.subTest(case=name, part=part):
                    self.check(name, part)

    def test_prepare_source(self):
        for name in CASES:
            with self.subTest(case=name):
                self.check(name, "prepare_source")


if __name__ == "__main__":
    unittest.main()
