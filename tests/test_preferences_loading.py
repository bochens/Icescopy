import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree.ElementTree import Element, ElementTree, ParseError, SubElement

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from Icescopy import IceScopy
from icescopy_paths import user_preferences_path, write_preferences_tree_atomic


class PreferenceLoadingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "preferences.xml"
        selected_path = patch("Icescopy.preferences_read_path", return_value=self.path)
        selected_path.start()
        self.addCleanup(selected_path.stop)

    def load(self, body):
        original = f"<Preferences>{body}</Preferences>".encode("utf-8")
        self.path.write_bytes(original)
        result = IceScopy.load_preferences_from_xml(None)
        self.assertEqual(self.path.read_bytes(), original)
        return result

    def test_invalid_number_does_not_discard_other_settings(self):
        result = self.load(
            "<MaximumZoom>17</MaximumZoom><PenWidth>invalid</PenWidth>"
            "<SampleNamePattern>Ice_#</SampleNamePattern>"
        )
        self.assertEqual(result["MaximumZoom"], 17)
        self.assertEqual(result["SampleNamePattern"], "Ice_#")
        self.assertNotIn("PenWidth", result)
        self.assertIn("PenWidth", result["_load_warnings"][0])

    def test_nonfinite_values_are_rejected_for_float_and_integer_controls(self):
        for key in ("MaximumZoom", "UndoLimit", "SliderTickPixelInterval"):
            for value in ("nan", "inf", "-inf", "1e999"):
                with self.subTest(key=key, value=value):
                    result = self.load(f"<{key}>{value}</{key}>")
                    self.assertNotIn(key, result)
                    self.assertEqual(len(result["_load_warnings"]), 1)

    def test_out_of_range_values_are_rejected(self):
        for key, value in (
            ("DefaultCircleRadius", "0"), ("MaximumZoom", "1001"),
            ("GridRows", "0"), ("GridColumns", "101"),
            ("ViewerImageCount", "4"), ("GridRotationDegrees", "181"),
            ("CircleLabelOffsetX", "-501"), ("TimeseriesLineWidth", "21"),
            ("TemperatureCycleWarmupHysteresisC", "-0.1"),
        ):
            with self.subTest(key=key, value=value):
                result = self.load(f"<{key}>{value}</{key}>")
                self.assertNotIn(key, result)
                self.assertIn(key, result["_load_warnings"][0])

    def test_integer_settings_accept_historical_float_text(self):
        result = self.load("<UndoLimit>20.0</UndoLimit><GridRows>4.0</GridRows>")
        self.assertEqual(result["UndoLimit"], 20)
        self.assertIsInstance(result["UndoLimit"], int)
        self.assertEqual(result["GridRows"], 4)
        self.assertNotIn("_load_warnings", result)

    def test_empty_tags_are_compatible_and_zero_bounds_are_valid(self):
        result = self.load(
            "<MaximumZoom/><PenWidth/><UndoLimit/>"
            "<ConvolutionHalfWindowPoints>0</ConvolutionHalfWindowPoints>"
            "<GridRotationDegrees>-180</GridRotationDegrees>"
        )
        self.assertNotIn("MaximumZoom", result)
        self.assertNotIn("UndoLimit", result)
        self.assertEqual(result["ConvolutionHalfWindowPoints"], 0)
        self.assertEqual(result["GridRotationDegrees"], -180)
        self.assertNotIn("_load_warnings", result)

    def test_bad_sample_schema_preserves_valid_numeric_values(self):
        result = self.load("<MaximumZoom>17</MaximumZoom><SampleMetadataFields><Field key='Invalid Key'/></SampleMetadataFields>")
        self.assertEqual(result["MaximumZoom"], 17)
        self.assertTrue(result["SampleMetadataSchema"])
        self.assertIn("SampleMetadataSchema", result["_load_warnings"][0])

    def test_wrong_root_is_reported_without_changing_file(self):
        original = b"<Unrelated><MaximumZoom>17</MaximumZoom></Unrelated>"
        self.path.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "Preferences element"):
            IceScopy.load_preferences_from_xml(None)
        self.assertEqual(self.path.read_bytes(), original)

    def test_bundled_preferences_pass_validation(self):
        with patch("Icescopy.preferences_read_path", return_value=PROJECT_ROOT / "resources/preferences.xml"):
            result = IceScopy.load_preferences_from_xml(None)
        self.assertNotIn("_load_warnings", result)


class PreferenceWriteValidationTests(unittest.TestCase):
    def test_xml_control_character_preserves_previous_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"ICESCOPY_CONFIG_DIR": folder}):
                path = user_preferences_path()
                original = b"<Preferences><MaximumZoom>17</MaximumZoom></Preferences>"
                path.write_bytes(original)
                root = Element("Preferences")
                SubElement(root, "SampleNamePattern").text = "Sample_" + chr(11) + "#"
                with self.assertRaises(ParseError):
                    write_preferences_tree_atomic(ElementTree(root))
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(list(path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
