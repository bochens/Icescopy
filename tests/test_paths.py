import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree.ElementTree import Element, ElementTree, SubElement, parse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from icescopy_paths import (  # noqa: E402
    preferences_read_path,
    user_preferences_path,
    write_preferences_tree_atomic,
)


class PreferencePathTests(unittest.TestCase):
    def test_bundled_preferences_are_the_read_only_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config_dir = root / "config"
            resources_dir = root / "resources"
            resources_dir.mkdir()
            bundled_path = resources_dir / "preferences.xml"
            bundled_path.write_text("<Preferences />", encoding="utf-8")

            with patch.dict(os.environ, {"ICESCOPY_CONFIG_DIR": str(config_dir)}):
                self.assertEqual(preferences_read_path(resources_dir), bundled_path)

    def test_preferences_are_written_atomically_to_user_config(self):
        with tempfile.TemporaryDirectory() as td:
            config_dir = Path(td) / "config"
            root = Element("Preferences")
            SubElement(root, "DefaultCircleRadius").text = "42"

            with patch.dict(os.environ, {"ICESCOPY_CONFIG_DIR": str(config_dir)}):
                written_path = write_preferences_tree_atomic(ElementTree(root))
                self.assertEqual(written_path, user_preferences_path())
                self.assertEqual(preferences_read_path(Path(td) / "resources"), written_path)

            parsed_root = parse(written_path).getroot()
            self.assertEqual(parsed_root.findtext("DefaultCircleRadius"), "42")


if __name__ == "__main__":
    unittest.main()
