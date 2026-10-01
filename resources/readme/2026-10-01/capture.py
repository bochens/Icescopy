"""Capture actual Icescopy widgets; no desktop, pointer, or image compositing.

Run with the app's Python environment on macOS. Outputs must not exist.
The public evaluation frame is read-only; preferences use a temporary folder.
"""
from pathlib import Path
import json
import os
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).parent
DEST.mkdir(parents=True, exist_ok=True)
for name in ('droplet-selection.png', 'ml-model.png'):
    if (DEST / name).exists():
        raise FileExistsError(DEST / name)

with tempfile.TemporaryDirectory(prefix='icescopy-readme-') as config:
    os.environ['ICESCOPY_CONFIG_DIR'] = config
    sys.path.insert(0, str(ROOT / 'src'))
    from PySide6.QtCore import Qt, QRect
    from PySide6.QtWidgets import QApplication, QLabel
    from PySide6.QtTest import QTest
    from Icescopy import IceScopy
    from icescopy_aux import PreferencesDialog
    from icescopy_cell_items import CellSnapshot

    app = QApplication([])
    window = IceScopy()
    window.resize(1280, 850)
    window.switch_light_dark_mode('light')
    window.session_active = True
    image = ROOT / 'auto_cell_ml/examples/real/evaluation/04-TAMU/image.png'
    window.load_aux([str(image)])
    window.set_viewer_image_count(1)
    seeds = json.loads((ROOT / 'auto_cell_ml/examples/real/evaluation/examples.json').read_text())['examples']['04-TAMU']
    window.keyframe_list = [0]
    window.keyframe_cell_items_dict = {0: [CellSnapshot((x, y), r, (x, y), i) for i, (x, y, r) in enumerate(seeds)]}
    for i in range(len(seeds)):
        window.ensure_cell_record(i)
    window.next_cell_id = len(seeds)
    window.interpolate_and_displayMarkedRegions(0)
    window.pen_width = 3
    window.circle_label_font_size = 13
    window.circle_default_color = '18,189,89,255'
    window.circle_selected_color = '0,189,232,255'
    for cell in window.cell_items:
        cell.setSelected(True)
    window.image_list_dock.hide()
    window.sample_catalog_dock.hide()
    window.cells_dock.hide()
    window.grayscale_plot_dock.hide()
    window.results_tables_dock.hide()
    window.tool_options_dock.show()
    window.console_dock.show()
    window.resizeDocks([window.tool_options_dock], [365], Qt.Horizontal)
    window.resizeDocks([window.console_dock], [95], Qt.Vertical)
    window.update_session_actions_state()
    window.show()
    QTest.qWait(350)
    window.resizeDocks([window.tool_options_dock], [365], Qt.Horizontal)
    window.view.fitInView(window.view.content_rect, Qt.KeepAspectRatio)
    window.mark_session_clean()
    messages = []
    # Keep the result visible rather than covering it with the modal summary.
    # The real controller still writes the identical summary to the Console.
    window.show_detailed_information_dialog = lambda title, text, detail_text='': messages.append(text)
    window.droplet_tools.start_detection()
    deadline = time.monotonic() + 30
    while window.droplet_tools.is_running() and time.monotonic() < deadline:
        QTest.qWait(25)
    assert not window.droplet_tools.is_running() and messages, 'Detection did not complete'
    assert len(window.cell_items) == 16, (len(window.cell_items), messages)
    window.terminal.verticalScrollBar().setValue(window.terminal.verticalScrollBar().maximum())
    window.view.fitInView(window.view.content_rect, Qt.KeepAspectRatio)
    QTest.qWait(150)
    assert window.grab().save(str(DEST / 'droplet-selection.png'))

    preferences = PreferencesDialog(window)
    preferences.category_list.setCurrentRow(7)
    preferences.resize(900, 390)
    preferences.show()
    QTest.qWait(250)
    # Crop to the actual ML page's useful content; no title bar or desktop.
    page = preferences.ml_page
    height = max(label.mapTo(page, label.rect().bottomLeft()).y()
                 for label in page.findChildren(QLabel) if label.text())
    assert page.grab(QRect(0, 0, page.width(), min(page.height(), height + 24))).save(str(DEST / 'ml-model.png'))
    print(messages[0])
    print('Saved widget captures to', DEST)
    preferences.reject()
    window.mark_session_clean()
    window.close()
    app.processEvents()
