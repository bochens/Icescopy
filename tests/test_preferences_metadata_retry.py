import copy
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from Icescopy import IceScopy
from icescopy_sample_metadata import default_sample_metadata_schema, sample_metadata_schema_from_payload


class SampleMetadataRetryTests(unittest.TestCase):
    def test_failed_apply_restores_data_before_retrying_a_field_swap(self):
        for record_history in (True, False):
            for failed_stage in (
                "refresh_freeze_count_timeseries_metadata_from_sample_catalog",
                "refresh_sample_catalog_tree", "update_cursor_sample_controls", "refresh_cells_panel",
            ):
                with self.subTest(record_history=record_history, stage=failed_stage):
                    old_schema = sample_metadata_schema_from_payload(default_sample_metadata_schema() + [
                        {"key": "custom_a", "label": "A", "type": "text"},
                        {"key": "custom_b", "label": "B", "type": "text"},
                    ])
                    new_schema = sample_metadata_schema_from_payload(default_sample_metadata_schema() + [
                        {"key": "custom_b", "label": "A", "type": "text"},
                        {"key": "custom_a", "label": "B", "type": "text"},
                    ])
                    original_catalog = {0: {"custom_a": "first", "custom_b": "second"}}
                    window = SimpleNamespace(
                        sample_metadata_schema=copy.deepcopy(old_schema),
                        sample_catalog=copy.deepcopy(original_catalog),
                        next_sample_id=1,
                        freeze_count_timeseries_headers=["Original header"],
                        freeze_count_timeseries_summary={"sample_column_metadata": [{"custom_a": "first"}]},
                        capture_data_state=Mock(return_value={"before": True}),
                        push_data_history=Mock(),
                        update_freeze_count_timeseries_table=Mock(side_effect=RuntimeError("repair also failed")),
                    )
                    window.active_sample_metadata_schema = lambda: window.sample_metadata_schema
                    window.refresh_sample_catalog_tree = Mock()
                    window.update_cursor_sample_controls = Mock()
                    window.refresh_cells_panel = Mock()
                    def refresh_timeseries(**kwargs):
                        window.freeze_count_timeseries_headers = ["Changed header"]
                        window.freeze_count_timeseries_summary["sample_column_metadata"][0]["custom_a"] = "changed"
                        window.next_sample_id = 9
                    window.refresh_freeze_count_timeseries_metadata_from_sample_catalog = Mock(side_effect=refresh_timeseries)
                    failing = getattr(window, failed_stage)
                    previous_side_effect = failing.side_effect
                    failing.side_effect = RuntimeError("original apply failure")
                    with patch("Icescopy.traceback.print_exc"):
                        with self.assertRaisesRegex(RuntimeError, "original apply failure"):
                            IceScopy.apply_sample_metadata_schema(
                                window, new_schema, {"custom_a": "custom_b", "custom_b": "custom_a"},
                                record_history=record_history,
                            )
                    self.assertEqual(window.sample_catalog, original_catalog)
                    self.assertEqual(window.sample_metadata_schema, old_schema)
                    self.assertEqual(window.next_sample_id, 1)
                    self.assertEqual(window.freeze_count_timeseries_headers, ["Original header"])
                    self.assertEqual(window.freeze_count_timeseries_summary,
                                     {"sample_column_metadata": [{"custom_a": "first"}]})
                    window.push_data_history.assert_not_called()
                    failing.side_effect = previous_side_effect
                    IceScopy.apply_sample_metadata_schema(
                        window, new_schema, {"custom_a": "custom_b", "custom_b": "custom_a"},
                        record_history=record_history,
                    )
                    self.assertEqual(window.sample_catalog[0]["custom_b"], "first")
                    self.assertEqual(window.sample_catalog[0]["custom_a"], "second")
                    self.assertEqual(window.sample_metadata_schema, new_schema)
                    self.assertEqual(window.push_data_history.call_count, int(record_history))


if __name__ == "__main__":
    unittest.main()
