import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from icescopy_session_io import (  # noqa: E402
    FREEZE_CSV_FILENAME,
    GRAYSCALE_CSV_FILENAME,
    SESSION_SCHEMA_VERSION,
    SESSION_STATE_FILENAME,
    TEMPERATURE_SYNC_CSV_FILENAME,
    load_session_bundle,
    save_session_bundle,
)


class SessionIoTests(unittest.TestCase):
    def test_session_bundle_stores_all_three_tables_as_csv(self):
        payload = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "image_paths": ["/tmp/example.png"],
            "image_names": ["example.png"],
            "temperature_sync_summary": {"source_type": "csu"},
        }

        grayscale_headers = ["image_name", "cell_0_grayscale"]
        grayscale_rows = [["frame_0001.png", "123.4"]]
        freeze_headers = ["cell", "image_index", "image_name"]
        freeze_rows = [["cell_0", "4", "frame_0005.png"]]
        temperature_headers = ["timestamp", "temperature_C", "sample_A fraction frozen"]
        temperature_rows = [["2026-04-22 12:00:00", "-12.3", "0.500000"]]

        with tempfile.TemporaryDirectory() as td:
            bundle_path = Path(td) / "session.icescopy"

            save_session_bundle(
                bundle_path,
                payload,
                grayscale_headers,
                grayscale_rows,
                freeze_headers,
                freeze_rows,
                temperature_headers,
                temperature_rows,
            )

            with zipfile.ZipFile(bundle_path, "r") as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    sorted(
                        [
                            SESSION_STATE_FILENAME,
                            GRAYSCALE_CSV_FILENAME,
                            FREEZE_CSV_FILENAME,
                            TEMPERATURE_SYNC_CSV_FILENAME,
                        ]
                    ),
                )
                session_payload = json.loads(
                    archive.read(SESSION_STATE_FILENAME).decode("utf-8")
                )
                self.assertNotIn("grayscale_results_headers", session_payload)
                self.assertNotIn("grayscale_results_rows", session_payload)
                self.assertNotIn("freeze_results_headers", session_payload)
                self.assertNotIn("freeze_results_rows", session_payload)
                self.assertNotIn("temperature_sync_headers", session_payload)
                self.assertNotIn("temperature_sync_rows", session_payload)
                self.assertEqual(
                    session_payload["temperature_sync_summary"],
                    {"source_type": "csu"},
                )

            (
                restored_payload,
                grayscale_table,
                freeze_table,
                temperature_table,
            ) = load_session_bundle(bundle_path)

            self.assertEqual(restored_payload, session_payload)
            self.assertEqual(grayscale_table, (grayscale_headers, grayscale_rows))
            self.assertEqual(freeze_table, (freeze_headers, freeze_rows))
            self.assertEqual(temperature_table, (temperature_headers, temperature_rows))


if __name__ == "__main__":
    unittest.main()
