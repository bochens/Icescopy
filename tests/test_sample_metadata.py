import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from xml.etree.ElementTree import Element

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from icescopy_aux import PreferencesDialog  # noqa: E402
from icescopy_sample_catalog import SampleCatalogTreeModel  # noqa: E402
from icescopy_sample_metadata import (  # noqa: E402
    SampleMetadataSchemaError,
    append_sample_metadata_schema_xml,
    default_sample_metadata_schema,
    dropped_sample_metadata_keys,
    migrate_sample_catalog_for_schema,
    normalize_sample_catalog_record,
    normalize_sample_metadata_schema,
    sample_metadata_schema_from_xml,
    sample_metadata_schema_to_payload,
)
from icescopy_session_io import build_freeze_count_timeseries_csv_text, build_restore_state  # noqa: E402


def schema_with_custom_fields():
    schema = default_sample_metadata_schema()
    schema.append(
        {
            "key": "campaign_id",
            "label": "Campaign ID",
            "type": "text",
            "fixed": False,
            "export": True,
            "same_for_all": True,
            "required_for_sample_types": (),
        }
    )
    schema.append(
        {
            "key": "lab_note",
            "label": "Lab note",
            "type": "text",
            "fixed": False,
            "export": False,
            "required_for_sample_types": (),
        }
    )
    schema.append(
        {
            "key": "collection_temperature_c",
            "label": "Collection temperature (C)",
            "type": "number",
            "fixed": False,
            "export": True,
            "required_for_sample_types": (),
        }
    )
    return normalize_sample_metadata_schema(schema)


class SampleMetadataTests(unittest.TestCase):
    def test_preferences_initial_button_state_matches_empty_selection(self):
        QApplication.instance() or QApplication([])
        fake_window = SimpleNamespace(
            load_preferences_from_xml=lambda: {
                "SampleMetadataSchema": default_sample_metadata_schema()
            }
        )

        dialog = PreferencesDialog(fake_window)

        self.assertTrue(dialog.sample_add_field_button.isEnabled())
        self.assertFalse(dialog.sample_delete_field_button.isEnabled())
        self.assertFalse(dialog.sample_move_field_up_button.isEnabled())
        self.assertFalse(dialog.sample_move_field_down_button.isEnabled())

    def test_xml_round_trip_preserves_order_types_fixed_and_export_flags(self):
        schema = schema_with_custom_fields()
        root = Element("Preferences")

        append_sample_metadata_schema_xml(root, schema)
        restored = sample_metadata_schema_from_xml(root)

        self.assertEqual([field["key"] for field in restored], [field["key"] for field in schema])
        self.assertTrue(restored[0]["fixed"])
        self.assertEqual(restored[-3]["key"], "campaign_id")
        self.assertEqual(restored[-3]["type"], "text")
        self.assertTrue(restored[-3]["export"])
        self.assertTrue(restored[-3]["same_for_all"])
        self.assertEqual(restored[-2]["key"], "lab_note")
        self.assertFalse(restored[-2]["export"])
        self.assertEqual(restored[-1]["type"], "number")

    def test_default_schema_includes_shared_well_volume_field(self):
        schema = default_sample_metadata_schema()
        fields_by_key = {field["key"]: field for field in schema}

        self.assertIn("well_volume_uL", fields_by_key)
        self.assertEqual(fields_by_key["well_volume_uL"]["label"], "Well volume (uL)")
        self.assertEqual(fields_by_key["well_volume_uL"]["type"], "number")
        self.assertFalse(fields_by_key["well_volume_uL"]["fixed"])
        self.assertTrue(fields_by_key["well_volume_uL"]["export"])
        self.assertTrue(fields_by_key["well_volume_uL"]["same_for_all"])

    def test_schema_validation_protects_fixed_and_reserved_fields(self):
        schema = [
            field
            for field in default_sample_metadata_schema()
            if field["key"] != "sample_type"
        ]
        with self.assertRaises(SampleMetadataSchemaError):
            normalize_sample_metadata_schema(schema)

        schema = default_sample_metadata_schema()
        schema.append(
            {
                "key": "sample_id",
                "label": "Sample ID",
                "type": "text",
                "fixed": False,
                "export": True,
                "required_for_sample_types": (),
            }
        )
        with self.assertRaises(SampleMetadataSchemaError):
            normalize_sample_metadata_schema(schema)

    def test_key_rename_migrates_values_and_deleted_fields_are_dropped(self):
        old_schema = schema_with_custom_fields()
        new_schema = [
            field
            for field in old_schema
            if field["key"] not in {"lab_note", "campaign_id"}
        ]
        new_schema.append(
            {
                "key": "campaign_code",
                "label": "Campaign code",
                "type": "text",
                "fixed": False,
                "export": True,
                "required_for_sample_types": (),
            }
        )
        sample_catalog = {
            0: {
                "sample_name": "Sample_0",
                "campaign_id": "MOSAiC",
                "lab_note": "operator note",
            }
        }

        migrated = migrate_sample_catalog_for_schema(
            sample_catalog,
            old_schema,
            new_schema,
            rename_map={"campaign_id": "campaign_code"},
        )

        self.assertEqual(migrated[0]["campaign_code"], "MOSAiC")
        self.assertNotIn("campaign_id", migrated[0])
        self.assertNotIn("lab_note", migrated[0])
        self.assertEqual(
            dropped_sample_metadata_keys(
                old_schema,
                new_schema,
                rename_map={"campaign_id": "campaign_code"},
            ),
            ["lab_note"],
        )

    def test_model_displays_custom_fields_and_persists_edits(self):
        QApplication.instance() or QApplication([])
        schema = schema_with_custom_fields()
        fake_window = SimpleNamespace(
            sample_metadata_schema=schema,
            sample_catalog={
                0: normalize_sample_catalog_record(
                    {
                        "sample_name": "Sample_0",
                        "campaign_id": "old",
                        "collection_temperature_c": "1.5",
                    },
                    schema,
                )
            },
            history=[],
            refresh_calls=0,
        )
        fake_window.active_sample_metadata_schema = lambda: fake_window.sample_metadata_schema
        fake_window.ordered_sample_catalog_records = lambda: [
            (0, normalize_sample_catalog_record(fake_window.sample_catalog[0], schema))
        ]
        fake_window.sample_record_for_id = lambda sample_id: normalize_sample_catalog_record(
            fake_window.sample_catalog[int(sample_id)],
            schema,
        )
        fake_window.default_sample_name = lambda sample_id: f"Sample_{sample_id}"
        fake_window.capture_data_state = lambda: {"sample_catalog": dict(fake_window.sample_catalog)}
        fake_window.push_data_history = lambda label, before_state: fake_window.history.append(label)
        fake_window.refresh_freeze_count_timeseries_metadata_from_sample_catalog = (
            lambda relabel_headers=False: setattr(fake_window, "refresh_calls", fake_window.refresh_calls + 1)
        )

        model = SampleCatalogTreeModel(fake_window)
        top_index = model.index(0, 0)
        keys = [
            model.index(row, 0, top_index).data(SampleCatalogTreeModel.FIELD_NAME_ROLE)
            for row in range(model.rowCount(top_index))
        ]
        campaign_row = keys.index("campaign_id")
        number_row = keys.index("collection_temperature_c")

        self.assertIn("campaign_id", keys)
        self.assertTrue(model.setData(model.index(campaign_row, 1, top_index), "new", Qt.EditRole))
        self.assertEqual(fake_window.sample_catalog[0]["campaign_id"], "new")
        self.assertFalse(model.setData(model.index(number_row, 1, top_index), "not-a-number", Qt.EditRole))
        self.assertEqual(fake_window.sample_catalog[0]["collection_temperature_c"], "1.5")
        self.assertEqual(fake_window.history, ["Update Sample Metadata"])
        self.assertEqual(fake_window.refresh_calls, 1)

    def test_model_propagates_same_for_all_field_edits(self):
        QApplication.instance() or QApplication([])
        schema = default_sample_metadata_schema()
        fake_window = SimpleNamespace(
            sample_metadata_schema=schema,
            sample_catalog={
                0: normalize_sample_catalog_record({"sample_name": "Sample_0"}, schema),
                1: normalize_sample_catalog_record({"sample_name": "Sample_1"}, schema),
            },
            history=[],
            refresh_calls=0,
        )
        fake_window.active_sample_metadata_schema = lambda: fake_window.sample_metadata_schema
        fake_window.ordered_sample_catalog_records = lambda: [
            (sample_id, normalize_sample_catalog_record(sample_record, schema))
            for sample_id, sample_record in sorted(fake_window.sample_catalog.items())
        ]
        fake_window.sample_record_for_id = lambda sample_id: normalize_sample_catalog_record(
            fake_window.sample_catalog[int(sample_id)],
            schema,
        )
        fake_window.default_sample_name = lambda sample_id: f"Sample_{sample_id}"
        fake_window.capture_data_state = lambda: {"sample_catalog": dict(fake_window.sample_catalog)}
        fake_window.push_data_history = lambda label, before_state: fake_window.history.append(label)
        fake_window.refresh_freeze_count_timeseries_metadata_from_sample_catalog = (
            lambda relabel_headers=False: setattr(fake_window, "refresh_calls", fake_window.refresh_calls + 1)
        )

        model = SampleCatalogTreeModel(fake_window)
        top_index = model.index(0, 0)
        keys = [
            model.index(row, 0, top_index).data(SampleCatalogTreeModel.FIELD_NAME_ROLE)
            for row in range(model.rowCount(top_index))
        ]
        well_volume_row = keys.index("well_volume_uL")

        self.assertEqual(
            model.index(well_volume_row, 0, top_index).data(Qt.DisplayRole),
            "Well volume (uL) [all]",
        )
        self.assertTrue(model.setData(model.index(well_volume_row, 1, top_index), "50", Qt.EditRole))
        self.assertEqual(fake_window.sample_catalog[0]["well_volume_uL"], "50")
        self.assertEqual(fake_window.sample_catalog[1]["well_volume_uL"], "50")
        self.assertEqual(fake_window.history, ["Update Sample Metadata"])
        self.assertEqual(fake_window.refresh_calls, 1)

    def test_model_sample_rows_show_color_swatch_and_bold_number(self):
        QApplication.instance() or QApplication([])
        schema = default_sample_metadata_schema()
        fake_window = SimpleNamespace(
            sample_metadata_schema=schema,
            sample_catalog={
                2: normalize_sample_catalog_record({"sample_name": "Sample_2"}, schema),
            },
        )
        fake_window.active_sample_metadata_schema = lambda: fake_window.sample_metadata_schema
        fake_window.ordered_sample_catalog_records = lambda: [
            (2, normalize_sample_catalog_record(fake_window.sample_catalog[2], schema))
        ]
        fake_window.sample_record_for_id = lambda sample_id: normalize_sample_catalog_record(
            fake_window.sample_catalog[int(sample_id)],
            schema,
        )
        fake_window.sample_visual_color = lambda sample_id, alpha=255: QColor(12, 34, 56, alpha)

        model = SampleCatalogTreeModel(fake_window)
        top_index = model.index(0, 0)
        swatch = top_index.data(Qt.DecorationRole)
        font = top_index.data(Qt.FontRole)

        self.assertIsInstance(swatch, QPixmap)
        self.assertFalse(swatch.isNull())
        swatch_color = swatch.toImage().pixelColor(0, 0)
        self.assertEqual((swatch_color.red(), swatch_color.green(), swatch_color.blue()), (12, 34, 56))
        self.assertIsInstance(font, QFont)
        self.assertTrue(font.bold())

    def test_export_uses_active_schema_and_excludes_non_export_custom_fields(self):
        schema = schema_with_custom_fields()
        headers = ["timestamp", "temperature_C", "Sample A number total", "Sample A number frozen"]
        rows = [["2026-04-22T12:00:00.000", "-12.3", "2", "1"]]

        csv_text = build_freeze_count_timeseries_csv_text(
            headers,
            rows,
            session_metadata={"project_name": "Proj"},
            summary={
                "sample_metadata_schema": sample_metadata_schema_to_payload(schema),
                "sample_column_metadata": [
                    {
                        "sample_id": "1",
                        "cell_number": "2",
                        "sample_name": "Sample A",
                        "campaign_id": "MOSAiC",
                        "lab_note": "not exported",
                        "collection_temperature_c": "-12.5",
                    }
                ],
            },
        )

        self.assertIn("# sample_id,1\n", csv_text)
        self.assertIn("# cell_number,2\n", csv_text)
        self.assertIn("# campaign_id,MOSAiC\n", csv_text)
        self.assertIn("# collection_temperature_c,-12.5\n", csv_text)
        self.assertNotIn("# lab_note,", csv_text)
        self.assertIn("timestamp,temperature_C,Sample A number total,Sample A number frozen\n", csv_text)

    def test_restore_state_uses_saved_session_schema(self):
        schema = schema_with_custom_fields()
        payload = {
            "session_metadata": {},
            "image_edit_state": {},
            "cell_items": [],
            "next_cell_id": 0,
            "cell_records_by_id": {},
            "sample_metadata_schema": sample_metadata_schema_to_payload(schema),
            "sample_catalog": {
                "0": {
                    "sample_name": "Sample_0",
                    "campaign_id": "MOSAiC",
                }
            },
            "next_sample_id": 1,
            "keyframe_list": [],
            "flagframe_list": [],
            "keyframe_cell_items_dict": {},
            "image_width": 100,
            "image_paths": ["/tmp/example.png"],
            "image_names": ["example.png"],
            "image_index": 0,
            "image_list_entry_ids": [0],
            "next_image_list_entry_id": 1,
            "sort_mode": "natural_filename",
            "last_grayscale_output_path": "",
            "last_freeze_output_path": "",
            "last_temperature_import_path": "",
            "last_temperature_calibration_path": "",
            "last_temperature_reset_temperature": None,
            "last_temperature_blank_sample_names": [],
            "last_standard_temperature_image_timestamp_source": "filename",
            "last_standard_temperature_image_timestamp_style": "auto",
            "last_standard_temperature_temperature_timestamp_style": "auto",
            "last_standard_temperature_use_image_timestamp_style": True,
            "last_standard_temperature_generated_start_text": "",
            "last_standard_temperature_frame_interval_seconds": 1.0,
            "last_standard_temperature_temperature_unit": "celsius",
            "freeze_count_timeseries_summary": {},
            "tool_mode": "cursor",
            "console_history": "",
        }
        fake_window = SimpleNamespace(default_tool_settings=lambda: {})

        state = build_restore_state(fake_window, payload, ([], []), ([], []), ([], []))

        self.assertEqual(
            [field["key"] for field in state["sample_metadata_schema"]],
            [field["key"] for field in schema],
        )
        self.assertEqual(state["sample_catalog"]["0"]["campaign_id"], "MOSAiC")


if __name__ == "__main__":
    unittest.main()
