"""Capture real application widgets with the current toolbar.

Run with Icescopy's Python environment. Supply the original plate session and
PKU frame directory as arguments; neither input is modified. All outputs must
be new. Preferences and neutral frame-name links live in a temporary directory.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--plate-session', type=Path, required=True)
parser.add_argument('--pku-frames', type=Path, required=True)
parser.add_argument('--destination', type=Path, default=Path(__file__).parent)
args = parser.parse_args()
args.destination.mkdir(parents=True, exist_ok=True)
names = ('grid-annotation.png', 'sample-assignment.png',
         'linked-frame-review.png', 'droplet-selection.png')
for name in names:
    if (args.destination / name).exists():
        raise FileExistsError(args.destination / name)
original_hash = hashlib.sha256(args.plate_session.read_bytes()).hexdigest()
with zipfile.ZipFile(args.plate_session) as archive:
    plate = json.loads(archive.read('session.json'))

with tempfile.TemporaryDirectory(prefix='icescopy-readme-') as temporary:
    temporary = Path(temporary)
    os.environ['ICESCOPY_CONFIG_DIR'] = str(temporary / 'preferences')
    sys.path.insert(0, str(ROOT / 'src'))
    import cv2
    import numpy as np
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from Icescopy import IceScopy
    from icescopy_cell_items import CellSnapshot
    from icescopy_freezfinder import compute_freeze_result_rows

    app = QApplication([])

    def open_view(paths, size=(1550, 800)):
        window = IceScopy()
        window.resize(*size)
        window.switch_light_dark_mode('light')
        window.session_active = True
        window.load_aux([str(path) for path in paths])
        window.set_viewer_image_count(1)
        window.pen_width = 3
        window.circle_label_font_size = 16
        for dock in (window.image_list_dock, window.sample_catalog_dock,
                     window.cells_dock, window.grayscale_plot_dock,
                     window.results_tables_dock, window.console_dock):
            dock.hide()
        window.tool_options_dock.show()
        window.show()
        QTest.qWait(200)
        return window

    def cells(window, records):
        snapshots = []
        for item in records:
            x, y = item['circle_pixel_positions']
            cell_id = item['cell_id']
            snapshots.append(CellSnapshot(
                window.image_pixel_to_scene_coordinates(x, y),
                item['circle_sizes'], (x, y), cell_id))
            window.ensure_cell_record(cell_id)
        window.keyframe_list = [0]
        window.keyframe_cell_items_dict = {0: snapshots}
        window.next_cell_id = max(item.cell_id for item in snapshots) + 1
        window.interpolate_and_displayMarkedRegions(window.image_index)

    def camera(window, zoom, center):
        window.zoom_textbox.setText(str(zoom))
        window.updateZoomLevel()
        window.view.centerOn(QPointF(*center))
        QTest.qWait(150)

    def save(window, name):
        app.processEvents()
        assert window.grab().save(str(args.destination / name))

    def close(window):
        window.mark_session_clean()
        window.close()
        app.processEvents()

    # Read geometry only from the session, avoiding its large results tables.
    window = open_view(plate['image_paths'])
    window.apply_image_edit_state({
        'exposure': 0.8, 'contrast': 22,
        'crop': {'center_x': 640, 'center_y': 610, 'width': 1278,
                 'height': 450, 'angle': 0}})
    cells(window, plate['cell_items'][:32])
    window.resizeDocks([window.tool_options_dock], [365], Qt.Horizontal)
    window.gridTool(True)
    window.grid_rows = 8
    window.grid_columns = 4
    window.circle_radius = 8
    window.grid_horizontal_pitch = 41.4
    window.grid_vertical_pitch = 41.4
    window.grid_rotation_degrees = 0
    origin = window.image_pixel_to_scene_coordinates(235.2, 459.4)
    window.update_grid_preview_from_scene_pos(QPointF(*origin), pin=True)
    window.sync_grid_tool_panel()
    camera(window, 88, (639, 225))
    save(window, 'grid-annotation.png')

    window.apply_cursor_tool_ui()
    window.updateImage(295)
    cells(window, plate['cell_items'])
    for cell_id, record in window.cell_records_by_id.items():
        record.sample_id = str(plate['cell_records_by_id'][str(cell_id)]['sample_id'])
    for sample_id in range(6):
        record = window.default_sample_record(sample_id)
        record.update(sample_name=f'Example {chr(65 + sample_id)}',
                      sample_long_name='Demo sample',
                      sample_type='air', dilution='1', air_volume_L='1000')
        window.sample_catalog[sample_id] = record
    window.tool_options_dock.hide()
    window.show_sample_catalog_manager()
    window.resizeDocks([window.sample_catalog_dock], [385], Qt.Horizontal)
    window.refresh_sample_catalog_tree(select_sample_id=0)
    window.sample_catalog_tree.header().resizeSection(0, 220)
    camera(window, 88, (639, 225))
    save(window, 'sample-assignment.png')
    close(window)

    # Neutral temporary names keep private recording names out of the figure.
    paths = sorted(args.pku_frames.glob('*.jpg'))
    assert paths
    frame_links = temporary / 'frames'
    frame_links.mkdir()
    links = []
    for index, path in enumerate(paths):
        link = frame_links / f'Frame_{index:04d}.jpg'
        link.symlink_to(path.resolve())
        links.append(link)
    with zipfile.ZipFile(ROOT / 'auto_cell_ml/examples/real/train/03-PKU/labels.icescopy') as archive:
        labeled = json.loads(archive.read('session.json'))['cell_items']
    chosen = min(labeled, key=lambda c: sum((a-b)**2 for a, b in
                 zip(c['circle_pixel_positions'], (1188, 258))))
    cell_id = chosen['cell_id']
    x, y = chosen['circle_pixel_positions']
    radius = chosen['circle_sizes']
    # Measure the same circular region in each original frame, then use the
    # application's convolution and raw-signal refinement for the freeze event.
    x0, x1 = int(x-radius), int(x+radius)+1
    y0, y1 = int(y-radius), int(y+radius)+1
    yy, xx = np.mgrid[y0:y1, x0:x1]
    mask = ((xx-x)**2 + (yy-y)**2 <= radius**2).astype(np.uint8)
    values = []
    for path in paths:
        frame = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        values.append(float(cv2.mean(frame[y0:y1, x0:x1], mask)[0]))
    freeze_rows, events = compute_freeze_result_rows(
        [p.name for p in links], None, np.asarray(values)[:, None],
        cell_ids=[cell_id], detect_brightening=True,
        convolution_half_window_points=10, width=5)
    assert 149 in events[0], events
    window = open_view(links, (1400, 850))
    cells(window, labeled)
    window.grayscale_results_headers = ['file_name', f'cell_{cell_id}_grayscale']
    window.grayscale_results_rows = [[path.name, str(value)] for path, value in zip(links, values)]
    window.freeze_results_headers = ['cell_id', 'frame_index', 'file_name']
    window.freeze_results_rows = freeze_rows
    window.sync_cell_analysis_from_results()
    window.updateImage(149)
    window.apply_cursor_tool_ui()
    window.set_viewer_image_count(3)
    window.resizeDocks([window.tool_options_dock], [365], Qt.Horizontal)
    window.grayscale_plot_dock.show()
    window.grayscale_plot_dock.raise_()
    window.resizeDocks([window.grayscale_plot_dock], [260], Qt.Vertical)
    window.timeseries_line_width = 3.5
    window.timeseries_convolution_line_width = 2.8
    window.convolution_half_window_points = 10
    window.freeze_finder_width = 5
    window.freeze_finder_detect_brightening = True
    window.reselect_cell_ids([cell_id])
    camera(window, 110, (x, y))
    window.center_on_cell_selection()
    window.refresh_grayscale_plot()
    window.update_grayscale_plot_current_frame(force=True)
    QTest.qWait(200)
    save(window, 'linked-frame-review.png')
    close(window)

    window = open_view([ROOT / 'auto_cell_ml/examples/real/evaluation/04-TAMU/image.png'], (1400, 850))
    seeds = json.loads((ROOT / 'auto_cell_ml/examples/real/evaluation/examples.json').read_text())['examples']['04-TAMU']
    cells(window, [dict(circle_pixel_positions=(x, y), circle_sizes=r, cell_id=i)
                   for i, (x, y, r) in enumerate(seeds)])
    window.circle_label_font_size = 13
    for cell in window.cell_items:
        cell.setSelected(True)
    window.console_dock.show()
    window.resizeDocks([window.tool_options_dock], [365], Qt.Horizontal)
    window.resizeDocks([window.console_dock], [95], Qt.Vertical)
    window.view.fitInView(window.view.content_rect, Qt.KeepAspectRatio)
    messages = []
    window.show_detailed_information_dialog = lambda title, text, detail_text='': messages.append(text)
    window.droplet_tools.start_detection()
    deadline = time.monotonic() + 30
    while window.droplet_tools.is_running() and time.monotonic() < deadline:
        QTest.qWait(25)
    assert not window.droplet_tools.is_running() and messages
    assert len(window.cell_items) == 16
    window.terminal.verticalScrollBar().setValue(window.terminal.verticalScrollBar().maximum())
    window.view.fitInView(window.view.content_rect, Qt.KeepAspectRatio)
    QTest.qWait(150)
    save(window, 'droplet-selection.png')
    print(messages[0])
    close(window)

assert hashlib.sha256(args.plate_session.read_bytes()).hexdigest() == original_hash
print('Four widget captures saved; original session unchanged.')
