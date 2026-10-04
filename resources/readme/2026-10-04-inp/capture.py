"""Capture the native INP client after a fresh MLE air-concentration calculation.

Supply a real .icescopy session with saved groups, blanks, and air metadata.
The source session and normal application preferences are never written.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import math
import os
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--session', type=Path, required=True)
parser.add_argument('--toolkit', type=Path, required=True)
parser.add_argument('--destination', type=Path, default=Path(__file__).parent)
args = parser.parse_args()
args.destination.mkdir(parents=True, exist_ok=True)
output = args.destination / 'm1-mle-air-concentration.png'
if output.exists():
    raise FileExistsError(output)
source_hash = hashlib.sha256(args.session.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory(prefix='icescopy-inp-demo-') as temporary:
    os.environ['ICESCOPY_CONFIG_DIR'] = str(Path(temporary) / 'preferences')
    sys.path.insert(0, str(ROOT / 'src'))
    from PySide6.QtCore import QItemSelectionModel
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from Icescopy import IceScopy
    from icescopy_inptk_state import new_settings, number
    from icescopy_session_io import load_session_bundle, build_restore_state

    app = QApplication([])
    app.setApplicationName('Icescopy')
    window = IceScopy()
    panel = window.inptk_panel
    errors = []
    panel.client.failed.connect(errors.append)

    def wait(condition, timeout=180):
        deadline = time.monotonic() + timeout
        while not condition():
            if errors or panel.last_error:
                raise RuntimeError(errors or panel.last_error)
            if time.monotonic() >= deadline:
                raise TimeoutError(panel.status.text())
            app.processEvents()
            time.sleep(.01)

    try:
        payload, grayscale, freeze, counts = load_session_bundle(args.session)
        saved = payload.get('inp_analysis', {}).get('choices')
        if not saved or len(saved.get('curves', [])) != 1:
            raise ValueError('Use the saved M1 session with one combined sample group.')
        # A marked water control is undiluted. Normalize its metadata only in
        # this in-memory demonstration; leave counts and the source file intact.
        blanks = {key for key, item in saved['inputs'].items() if item['blank']}
        for item in payload['freeze_count_timeseries_summary']['sample_column_metadata']:
            if item['sample_name'] in blanks:
                item['dilution'] = '1'
                payload['sample_catalog'][str(item['sample_id'])]['dilution'] = '1'
        window.restore_session_state(
            build_restore_state(window, payload, grayscale, freeze, counts),
            restore_inp_analysis=False)
        window.switch_light_dark_mode('light')
        window.inptk_executable_path = str(args.toolkit.resolve())
        panel.connect_toolkit()
        wait(lambda: panel.preview is not None and not panel.client.busy)
        choices = new_settings()
        for key in choices:
            if key in saved:
                choices[key] = copy.deepcopy(saved[key])
        choices.update(method='mle', basis='sampled_air', suggestion=None)
        group = choices['curves'][0]
        group['name'] = 'M1 untreated'
        for key in group['inputs']:
            choices['inputs'][key]['group'] = group['name']
        panel.commit(choices, 'Prepare the M1 air-concentration demonstration')
        panel.curves.setCurrentRow(0, QItemSelectionModel.ClearAndSelect)
        panel.recalculate()
        wait(lambda: panel.result is not None and not panel.operation and not panel.client.busy)
        if panel.result['choices']['basis'] != 'sampled_air':
            raise RuntimeError('The calculated result is not normalized to sampled air.')
        rows = panel.result['tables'][group['name']]['cumulative']['rows']
        finite = [row for row in rows if math.isfinite(number(row['concentration']))]
        if not finite:
            raise RuntimeError('The combined concentration has no finite results.')
        panel.show_analysis()
        panel.tabs.setCurrentIndex(1)
        panel.quantity.setCurrentText('Concentration')
        panel.show_uncertainty.setChecked(True)
        panel.show_combined.setChecked(True)
        panel.resize(1400, 900)
        panel.splitter.setSizes([420, 980])
        QTest.qWait(250)
        panel.fit_plot()
        QTest.qWait(250)
        if not panel.grab().save(str(output)):
            raise RuntimeError('Could not save the Qt widget capture.')
        print('Saved:', output)
        print('Method: MLE; basis: sampled air; blank correction:', choices['blank_correction'])
        print('Group inputs:', ', '.join(group['inputs']))
        print('Calculated units:', sorted({row['unit'] for row in finite}))
        print('Finite combined grid points:', len(finite))
        print('Temperature interval:', min(row['temperature_C'] for row in finite),
              'to', max(row['temperature_C'] for row in finite), 'degrees C')
        print('Timings:', panel.result.get('timings'))
    finally:
        panel.shutdown()
        window.mark_session_clean()
        window.close()
        app.processEvents()
        assert hashlib.sha256(args.session.read_bytes()).hexdigest() == source_hash
