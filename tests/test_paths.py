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

    @unittest.skipUnless(sys.platform == "win32", "Windows file sharing semantics")
    def test_windows_locked_destination_preserves_file_and_can_retry(self):
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"ICESCOPY_CONFIG_DIR": td}
        ):
            path = user_preferences_path()
            original = b"<Preferences><MaximumZoom>10</MaximumZoom></Preferences>"
            path.write_bytes(original)
            # Hold a real Windows read handle that does not permit replacement.
            handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
            if handle == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            root = Element("Preferences")
            SubElement(root, "MaximumZoom").text = "17"
            tree = ElementTree(root)
            try:
                with self.assertRaises(PermissionError):
                    write_preferences_tree_atomic(tree)
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(list(Path(td).glob("*.tmp")), [])
            finally:
                kernel.CloseHandle(handle)
            write_preferences_tree_atomic(tree)
            self.assertEqual(parse(path).findtext("MaximumZoom"), "17")


if __name__ == "__main__":
    unittest.main()
