import os
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PIL import Image  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from icescopy_frame_source import (  # noqa: E402
    ImageSequenceFrameSource,
    SOURCE_KIND_IMAGE_SEQUENCE,
    VideoFrameMetadata,
    VideoFrameSource,
    VideoSequenceFrameSource,
    format_seconds_for_frame_list,
)
from icescopy_session import ImageListModel  # noqa: E402


class FrameSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_image_sequence_frame_source_reads_pixels_and_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            first_path = Path(td) / "frame_0001.png"
            second_path = Path(td) / "frame_0002.png"
            Image.new("L", (3, 2), color=17).save(first_path)
            Image.new("L", (4, 5), color=23).save(second_path)

            source = ImageSequenceFrameSource([first_path, second_path])

            self.assertEqual(source.source_kind(), SOURCE_KIND_IMAGE_SEQUENCE)
            self.assertTrue(source.supports_image_file_operations())
            self.assertEqual(source.frame_count(), 2)
            self.assertEqual(source.frame_name(0), "frame_0001.png")
            self.assertEqual(source.frame_tooltip(1), str(second_path))
            self.assertEqual(source.source_path(), td)
            self.assertEqual(source.get_size(0), (3, 2))
            self.assertEqual(source.get_qimage(1).size().width(), 4)
            self.assertEqual(int(source.get_gray_array(0)[0, 0]), 17)
            iterated = list(source.iter_gray_arrays())
            self.assertEqual([index for index, _gray in iterated], [0, 1])
            self.assertEqual([gray.shape for _index, gray in iterated], [(2, 3), (5, 4)])
            self.assertEqual(
                source.to_session_payload(),
                {
                    "kind": SOURCE_KIND_IMAGE_SEQUENCE,
                    "image_paths": [str(first_path), str(second_path)],
                },
            )

    def test_source_backed_image_list_model_formats_requested_rows_only(self):
        calls = []

        fake_window = SimpleNamespace(
            frame_count=lambda: 3,
            format_frame_list_entry=lambda row: calls.append(row) or f"{row:06d} frame {row}",
            frame_tooltip=lambda row: f"tooltip {row}",
        )
        model = ImageListModel()
        model.main_window = fake_window
        model.set_items(["stale"], ["stale tooltip"])

        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(model.data(model.index(1, 0), Qt.DisplayRole), "000001 frame 1")
        self.assertEqual(model.data(model.index(1, 0), Qt.ToolTipRole), "tooltip 1")
        self.assertEqual(calls, [1])

    def test_video_frame_list_time_formatting(self):
        self.assertEqual(format_seconds_for_frame_list(4.967), "00:04.967")
        self.assertEqual(format_seconds_for_frame_list(65.25), "01:05.250")
        self.assertEqual(format_seconds_for_frame_list(3661.5), "01:01:01.500")

    def test_video_sequence_frame_source_concatenates_clip_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            first_path = str(Path(td) / "2026_0507_093532_002.MP4")
            second_path = str(Path(td) / "2026_0507_095032_003.MP4")
            source = VideoSequenceFrameSource(
                [first_path, second_path],
                segment_payloads=[
                    {
                        "frame_metadata": [
                            {"index": 0, "pts": 0, "time_seconds": 0.0},
                            {"index": 1, "pts": 1, "time_seconds": 0.5},
                        ],
                        "frame_size": [32, 24],
                    },
                    {
                        "frame_metadata": [
                            {"index": 0, "pts": 0, "time_seconds": 0.0},
                            {"index": 1, "pts": 1, "time_seconds": 1.0},
                        ],
                        "frame_size": [32, 24],
                    },
                ],
            )

            self.addCleanup(source.close)
            self.assertEqual(source.frame_count(), 4)
            self.assertEqual(source.source_paths(), [first_path, second_path])
            self.assertEqual(source.frame_reference(2), (second_path, 0))
            self.assertEqual(source.global_index_for_reference(second_path, 1), 3)
            self.assertEqual(source.frame_time_seconds(2), 1.0)
            self.assertEqual(source.frame_name(3), "000003  00:02.000")
            self.assertIn("clip frame: 0", source.frame_tooltip(2))
            self.assertEqual(
                source.to_session_payload(),
                {
                    "kind": "video_sequence",
                    "video_paths": [first_path, second_path],
                    "frame_count": 4,
                },
            )

    def test_video_preview_qimage_writes_disk_cache_when_pyav_is_available(self):
        try:
            import av
            import numpy as np
        except Exception as exc:
            self.skipTest(f"PyAV video preview test skipped: {exc}")

        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "tiny.mp4"
            cache_dir = Path(td) / "preview-cache"
            container = av.open(str(video_path), mode="w")
            stream = container.add_stream("mpeg4", rate=10)
            stream.width = 32
            stream.height = 24
            stream.pix_fmt = "yuv420p"
            for frame_index in range(3):
                pixels = np.full((24, 32, 3), frame_index * 40, dtype=np.uint8)
                frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
            container.close()

            source = VideoFrameSource(str(video_path), preview_cache_dir=cache_dir)
            qimage = source.get_preview_qimage(1)
            gray_frames = list(source.iter_gray_arrays())

            self.assertFalse(qimage.isNull())
            self.assertTrue((cache_dir / "frame_00000001.jpg").is_file())
            self.assertEqual([index for index, _gray in gray_frames], [0, 1, 2])
            self.assertEqual([gray.shape for _index, gray in gray_frames], [(24, 32), (24, 32), (24, 32)])
            source.close()

    def test_video_decoder_maps_pts_to_frame_index_while_decoding_forward(self):
        source = object.__new__(VideoFrameSource)
        source._decode_lock = threading.RLock()
        source._decode_container = None
        source._decode_stream = None
        source._metadata = [
            VideoFrameMetadata(index=0, pts=100, time_seconds=0.0),
            VideoFrameMetadata(index=1, pts=140, time_seconds=0.04),
            VideoFrameMetadata(index=2, pts=180, time_seconds=0.08),
        ]
        source._index_by_pts = {metadata.pts: metadata.index for metadata in source._metadata}
        source._decode_next_index = None
        source._decode_iterator = iter([
            SimpleNamespace(pts=100),
            SimpleNamespace(pts=140),
            SimpleNamespace(pts=180),
        ])

        frame = source._decode_until_frame_locked(1)

        self.assertEqual(frame.pts, 140)
        self.assertEqual(source._decode_next_index, 2)

    def test_frame_pixels_are_loaded_through_frame_source(self):
        allowed_cv2_files = {SRC_DIR / "icescopy_frame_source.py"}
        allowed_qimage_frame_files = {SRC_DIR / "icescopy_frame_source.py"}
        qimage_frame_pattern = re.compile(r"QImage\(\s*(?:self\._path_at|image_path|file_path|path\b)")

        for path in SRC_DIR.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "cv2.imread" in text:
                self.assertIn(path, allowed_cv2_files, f"cv2.imread is not frame-source-local: {path}")
            if qimage_frame_pattern.search(text):
                self.assertIn(
                    path,
                    allowed_qimage_frame_files,
                    f"QImage(path) is not frame-source-local: {path}",
                )


if __name__ == "__main__":
    unittest.main()
