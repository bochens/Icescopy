"""Client checks; optional real-CLI integration via INPTK_TEST_EXECUTABLE."""
import copy
import json
import math
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import test_freeze_review_cycles as cycle_tests
from test_csu_count_sources import make_data
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtGui import QColor, QUndoCommand
from icescopy_inptk_state import cli_choices, concentration_curves, new_settings, reconcile_inputs
from icescopy_session_io import build_session_payload, build_restore_state, load_session_bundle, save_session_bundle
from icescopy_temperature_import import CSU_COUNT_SOURCE_IMAGES
from icescopy_inptk_client import InptkClient, ToolkitTransport
from icescopy_inptk_data import PLOT_COLUMNS, upload_choices
from icescopy_inptk_export import concentration_csv, frozen_fraction_csv, write_csv
from icescopy_session_io import build_freeze_count_timeseries_csv_text
from icescopy_session import SessionSnapshotCommand


class InpChoiceTests(unittest.TestCase):
    def settings(self):
        state = new_settings()
        state["inputs"] = {
            "A": {"group": "sample", "cycle": "01", "blank": False, "blanks": ["water"]},
            "B": {"group": "sample", "cycle": "01", "blank": False, "blanks": ["water"]},
            "water": {"group": "water", "cycle": "01", "blank": True, "blanks": []},
        }
        state["curves"] = [{"name": "Combined", "inputs": ["A", "B"]}]
        return state

    def test_explicit_group_cycle_blank_and_inclusive_limits(self):
        state = self.settings()
        state["ranges"] = {"A": {"min_C": -20, "max_C": -5}, "B": {"max_C": -15}}
        args = cli_choices(state)
        curves = json.loads(args[args.index("--curves")+1])
        self.assertEqual(curves["Combined"]["inputs"][0], {"measurement_id": "A", "cycle_id": "01"})
        self.assertEqual(json.loads(args[args.index("--water-blank-map")+1]), {"A": ["water"], "B": ["water"]})
        self.assertEqual(json.loads(args[args.index("--temperature-ranges")+1]), state["ranges"])
        state["blank_correction"] = False
        self.assertIn("--no-water-blank-correction", cli_choices(state))
        self.assertEqual(state["inputs"]["A"]["blanks"], ["water"])

    def test_full_freezing_range_ends_at_zero_and_keeps_explicit_limits(self):
        state = self.settings()
        before = copy.deepcopy(state)
        args = cli_choices(state)
        self.assertEqual(json.loads(args[args.index('--temperature-ranges') + 1]),
                         {'A': {'max_C': 0.}, 'B': {'max_C': 0.}})
        self.assertEqual(state, before)
        state['ranges'] = {'A': {'min_C': -20}, 'B': {'max_C': -15}}
        args = cli_choices(state)
        self.assertEqual(json.loads(args[args.index('--temperature-ranges') + 1]),
                         {'A': {'min_C': -20, 'max_C': 0.}, 'B': {'max_C': -15}})

    def test_invalid_choices_are_not_silently_corrected(self):
        edits = [
            lambda s: s["inputs"]["B"].update(group="other"),
            lambda s: s["inputs"]["A"].update(cycle=""),
            lambda s: s["inputs"]["water"].update(blank=False),
            lambda s: s["curves"][0].update(inputs=["A", "A"]),
            lambda s: s["ranges"].update(A={"min_C": -5, "max_C": -20}),
        ]
        for edit in edits:
            with self.subTest(edit=edit):
                state = self.settings(); edit(state)
                with self.assertRaises(ValueError): cli_choices(state)

    def test_grid_and_fit_spacing_are_separate(self):
        state = self.settings()
        state.update(grid_step="0.5", grid_start="-4.7", grid_end="-19.2", fit_step="1", grid_method="window", grid_window="0.5")
        args = cli_choices(state)
        self.assertEqual(args[args.index("--temperature-start-C")+1], "-4.7")
        self.assertEqual(args[args.index("--fit-step-C")+1], "1")
        self.assertEqual(args[args.index("--temperature-window-C")+1], "0.5")
        state["method"] = "average"
        self.assertNotIn("--fit-step-C", cli_choices(state))
        self.assertNotIn("--temperature-ranges", cli_choices(state, suggest=True, selected="Combined"))

    def test_default_grid_endpoints_are_explicit_and_blank_fields_use_them(self):
        state = self.settings()
        for warm, cold in (('0', '-35'), ('', '')):
            state.update(grid_start=warm, grid_end=cold)
            args = cli_choices(state)
            self.assertEqual(args[args.index('--temperature-start-C') + 1], '0')
            self.assertEqual(args[args.index('--temperature-end-C') + 1], '-35')
        state['grid_step'] = ''
        self.assertNotIn('--temperature-start-C', cli_choices(state))

    def test_preview_does_not_infer_blank_or_cycle(self):
        state = reconcile_inputs(new_settings(), {"measurements": [
            {"measurement_id": "Water blank", "cycle_ids": ["01", "02"]}]})
        self.assertFalse(state["inputs"]["Water blank"]["blank"])
        self.assertEqual(state["inputs"]["Water blank"]["cycle"], "")

    def test_individual_outputs_reuse_single_inputs_and_avoid_name_collisions(self):
        state = self.settings()
        state['curves'] += [{'name': 'Neat', 'inputs': ['A']},
                            {'name': 'Combined / B', 'inputs': ['A', 'B']}]
        original = copy.deepcopy(state)
        specs, individual = concentration_curves(state)
        self.assertEqual(individual, {'Neat': 'A', 'Combined / B (2)': 'B'})
        self.assertEqual(len(specs), 4)
        self.assertEqual(specs['Combined']['inputs'], specs['Combined / B']['inputs'])
        self.assertEqual(specs['Combined / B (2)']['inputs'], [{'measurement_id': 'B', 'cycle_id': '01'}])
        args = cli_choices(state, include_individual=True)
        self.assertEqual(json.loads(args[args.index('--curves')+1]), specs)
        self.assertEqual(state, original)

    def test_upload_keeps_counts_metadata_and_blanks_in_the_same_scope(self):
        state = self.settings()
        state['curves'] = [{'name': 'Neat', 'inputs': ['A']}, {'name': 'Diluted', 'inputs': ['B']}]
        state['inputs']['B']['blanks'] = []
        source = {'counts': {'measurement_id': ['A', 'B', 'water', 'A'],
                             'temperature_C': [-5, -5, -5, -6]},
                  'metadata': [{'measurement_id': key} for key in ('A', 'B', 'water')]}
        before = copy.deepcopy(source)
        payload = upload_choices(source, state, selected='Neat')
        self.assertEqual(payload['counts'], {'measurement_id': ['A', 'water', 'A'],
                                             'temperature_C': [-5, -5, -6]})
        self.assertEqual([r['measurement_id'] for r in payload['metadata']], ['A', 'water'])
        self.assertEqual(payload['water_blank_map'], {'A': ['water']})
        self.assertEqual(source, before)


class InpProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_wrong_version_or_response_id_stops_the_client(self):
        for reply in ({"id": 1, "protocol_version": 1, "saved_format_version": 4},
                      {"id": 2, "protocol_version": 2, "saved_format_version": 4}):
            with self.subTest(reply=reply):
                client = InptkClient(); errors = []; received = []
                self.addCleanup(client.shutdown)
                client.failed.connect(errors.append)
                client.active = (1, [], received.append, None)
                client._received(client.epoch, reply)
                self.assertTrue(errors)
                self.assertFalse(received)
                self.assertFalse(client.busy)

    def test_partial_response_waits_for_newline(self):
        worker = ToolkitTransport(); received = []
        worker.response.connect(lambda epoch, reply: received.append(reply))
        payload = json.dumps({"id":1,"status":"ok","protocol_version":2,"saved_format_version":4}).encode()
        for data in (payload[:20], payload[20:]):
            worker.feed(data)
            self.assertFalse(received)
        worker.feed(b'\n')
        self.assertEqual(len(received),1)


class InpCsvLayoutTests(unittest.TestCase):
    def test_wide_export_separates_groups_preserves_zero_and_leaves_missing_empty(self):
        def table(rows):
            return {'cumulative': {'rows': [dict(temperature_C=t, concentration=v,
                lower_error=0, upper_error=9, unit='INP_per_mL_suspension',
                source_measurement_ids=['private'], qc_flag=7) for t, v in rows]}}
        tables = {'Group': table([(0., 0.), (-.5, 2.)]),
                  'Other group': table([(-.5, 4.), (-1., 5.)]),
                  'Group / A': table([(0., 100.)])}
        # Fit observations outside the reporting interval are not CSV values.
        tables['Group']['excluded'] = {'rows': [dict(temperature_C=20., concentration=999.,
            unit='INP_per_mL_suspension')]}
        headers, rows = concentration_csv(tables, [('Group', 'Group'), ('Other group', 'Other group')])
        self.assertEqual(headers, ['temperature_C'] + [f'{name} {field} (INP/mL suspension)'
            for name in ('Group', 'Other group') for field in ('concentration', 'lower bound', 'upper bound')])
        self.assertEqual(rows, [[0., 0., 0., 9., '', '', ''],
                               [-.5, 2., 2., 11., 4., 4., 13.],
                               [-1., '', '', '', 5., 5., 14.]])

    def test_uncertainty_bounds_use_asymmetric_errors_and_preserve_infinity(self):
        tables = {'A': {'cumulative': {'rows': [
            dict(temperature_C=-5., concentration=4., lower_error=1.5, upper_error=7., unit='INP_per_L_air'),
            dict(temperature_C=-6., concentration=0., lower_error=0., upper_error={'$nonfinite': 'inf'}, unit='INP_per_L_air'),
            dict(temperature_C=-7., concentration=8., unit='INP_per_L_air')]}}}
        _, rows = concentration_csv(tables, [('A', 'A')])
        self.assertEqual(rows, [[-5., 4., 2.5, 11.], [-6., 0., 0., float('inf')], [-7., 8., '', '']])

    def test_failed_csv_write_does_not_leave_partial_output_or_overwrite_existing_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.csv'
            def broken_rows():
                yield [0, 1]
                raise OSError('Cannot finish writing')
            with self.assertRaises(OSError): write_csv(path, ['temperature_C', 'A'], broken_rows())
            self.assertFalse(path.exists())
            path.write_text('original')
            with self.assertRaises(FileExistsError): write_csv(path, ['temperature_C', 'A'], [])
            self.assertEqual(path.read_text(), 'original')


@unittest.skipUnless(os.environ.get("INPTK_TEST_EXECUTABLE"), "Set INPTK_TEST_EXECUTABLE to run real CLI integration")
class InpIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cycle_tests.CycleMetadataLifecycleTests.setUpClass()

    def setUp(self):
        self.fixture = cycle_tests.CycleMetadataLifecycleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.window = w = self.fixture.window
        self.panel = w.inptk_panel
        self.addCleanup(self.panel.shutdown)
        w.inptk_executable_path = os.environ["INPTK_TEST_EXECUTABLE"]
        # Independent physical well sets, each with first-freezing observations.
        for sample_id in range(3):
            w.sample_catalog[sample_id] = w.default_sample_record(sample_id)
            w.sample_catalog[sample_id].update(sample_type="air", dilution=str(10**sample_id if sample_id < 2 else 1),
                well_volume_uL="50", air_volume_L="100", suspension_volume_mL="10", filter_fraction_used="1")
            for cell_index in range(10):
                cell_id = self.fixture.cell_id if sample_id == 0 and cell_index == 0 else w.cell_controller.add_single_cell((15,15),(15,15),3)
                record = w.ensure_cell_record(cell_id)
                record.sample_id = str(sample_id)
                record.freeze_event_indices = ([1] if cell_index < 2 else [2] if cell_index < 5 else [3] if cell_index < 8 else []) if sample_id < 2 else ([3] if cell_index == 0 else [])
        w.refresh_sample_catalog_tree(preserve_selection=False)
        data = make_data([-5,-6,-7,-8], {i:w.frame_name(i) for i in range(4)})
        w.set_freeze_count_timeseries_results(*w.build_csu_freeze_count_timeseries_results(data,count_source=CSU_COUNT_SOURCE_IMAGES))
        self.errors = []
        self.panel.client.failed.connect(self.errors.append)
        self.panel.connect_toolkit()
        self.wait(lambda: self.panel.preview is not None or self.errors)
        self.assertFalse(self.errors)

    def wait(self, condition, timeout=20):
        deadline = time.monotonic()+timeout
        while not condition() and time.monotonic()<deadline:
            QApplication.processEvents()
            time.sleep(.01)
        self.assertTrue(condition(), self.panel.status.text())

    def configure(self):
        state = copy.deepcopy(self.panel.settings)
        keys = list(state["inputs"])
        self.assertEqual(len(keys),3)
        for key in keys[:2]: state["inputs"][key].update(group="Sample",blanks=[keys[2]])
        state["inputs"][keys[2]]["blank"] = True
        state["curves"] = [{"name":"Combined","inputs":keys[:2]}, {"name":"Neat","inputs":[keys[0]]}]
        state["method"] = "average"
        state["grid_step"] = ""  # Keep native-temperature checks separate from the default-grid check.
        self.panel.commit(state,"Configure INP analysis")
        return keys

    def calculate(self):
        self.panel.recalculate()
        self.wait(lambda: not self.panel.operation and not self.panel.client.busy)
        self.assertIsNotNone(self.panel.result,self.panel.status.text())
        self.assertIn("up to date",self.panel.status.text())

    def test_export_scope_and_units_follow_the_saved_calculation(self):
        self.configure(); self.calculate()
        p = self.panel
        p.curves.setCurrentRow(0)
        p.change_option('basis', 'sampled_air')  # Pending edit, not yet calculated.
        p.export.menu().aboutToShow.emit()
        self.assertEqual(p.export_scope_action.text(), 'All 2 groups: Combined, Neat')
        self.assertIs(p.export.menu().actions()[0], p.export_scope_action)
        self.assertEqual(p.export.menu().actions()[1].text(), 'Save .inptk session…')
        self.assertIn('INP/mL suspension', p.concentration_export_action.text())
        self.assertIn('INP/mL suspension', p.individual_export_action.text())
        with patch.object(p, 'export_csv') as export:
            p.concentration_export_action.trigger()
        export.assert_called_once_with()
        with patch.object(p, 'export_csv') as export:
            p.individual_export_action.trigger()
        export.assert_called_once_with('individual')
        actions = [action.text() for action in p.export.menu().actions()]
        self.assertIn('Save .inptk session…', actions)
        self.assertIn('Export frozen fraction CSV…', actions)
        self.assertNotIn('Export frozen count CSV…', actions)
        self.assertFalse(any('JSON' in label or 'excluded' in label or 'Diagnostics' in label for label in actions))

    def test_both_concentration_exports_use_the_default_grid_and_only_requested_columns(self):
        import csv
        keys = self.configure(); p = self.panel
        # A positive warm-up reading must not shift the grid to .155/.655 °C.
        extra = list(self.window.freeze_count_timeseries_rows[0])
        extra[self.window.freeze_count_timeseries_headers.index('temperature_C')] = 20.655
        self.window.freeze_count_timeseries_rows.insert(0, extra)
        p.source_changed()
        p.change_option('grid_step', '0.5')
        self.calculate()
        for kind, names in (('cumulative', ['Combined', 'Neat']), ('individual', keys[:2]),
                            ('frozen_fraction', keys)):
            with self.subTest(kind=kind):
                target = self.fixture.root / f'{kind}.csv'
                with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName', return_value=(str(target), '')):
                    p.export_csv(kind)
                self.wait(lambda:not p.operation and not p.client.busy)
                self.assertFalse(p.last_error, p.last_error)
                with target.open() as handle:
                    reader = csv.DictReader(handle); rows = list(reader)
                suffix = ' fraction_frozen' if kind == 'frozen_fraction' else ' concentration (INP/mL suspension)'
                fields = ([name + suffix for name in names] if kind == 'frozen_fraction' else
                          [f'{name} {field} (INP/mL suspension)' for name in names
                           for field in ('concentration', 'lower bound', 'upper bound')])
                self.assertEqual(reader.fieldnames, ['temperature_C'] + fields)
                if kind != 'frozen_fraction':
                    tables = p.result['tables'] if kind == 'cumulative' else p.result['references']['tables']
                    by_temperature = {float(row['temperature_C']): row for row in rows}
                    for name in names:
                        curve = name if kind == 'cumulative' else p.result['references']['by_input'][name]
                        for point in tables[curve]['cumulative']['rows']:
                            row = by_temperature[point['temperature_C']]
                            self.assertAlmostEqual(float(row[f'{name} lower bound (INP/mL suspension)']),
                                                   point['concentration'] - point['lower_error'])
                            self.assertAlmostEqual(float(row[f'{name} upper bound (INP/mL suspension)']),
                                                   point['concentration'] + point['upper_error'])
                temperatures = [float(r['temperature_C']) for r in rows]
                self.assertTrue(all(-35 <= t <= 0 and t * 2 == round(t * 2) for t in temperatures))
                self.assertEqual(temperatures, sorted(temperatures, reverse=True))
                self.assertEqual(len(rows), 7 if kind == 'frozen_fraction' else 5)
                self.assertIn('Exported', p.status.text())
                if kind == 'frozen_fraction':
                    self.assertEqual([float(r[keys[0] + suffix]) for r in rows], [0., 0., .2, .2, .5, .5, .8])
                    self.assertEqual(float(rows[-1][keys[2] + suffix]), .1)
        before = (self.fixture.root / 'cumulative.csv').read_bytes()
        with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName', return_value=(str(self.fixture.root / 'cumulative.csv'), '')):
            p.export_csv()
        self.assertIn('existing outputs are preserved', p.last_error)
        self.assertEqual((self.fixture.root / 'cumulative.csv').read_bytes(), before)

    def test_pending_calculation_changes_do_not_export_old_results(self):
        self.configure(); self.calculate(); p = self.panel
        p.change_option('grid_step', '1')
        with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName') as chooser:
            p.export_csv()
        chooser.assert_not_called()
        self.assertIn('Calculate before exporting', p.status.text())

    def test_missing_individual_fits_are_disabled_and_reported(self):
        self.configure(); self.calculate(); p = self.panel
        p.result.pop('references')
        p.update_export_menu()
        self.assertFalse(p.individual_export_action.isEnabled())
        with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName') as chooser:
            p.export_csv('individual')
        chooser.assert_not_called()
        self.assertIn('Individual sample fits are unavailable', p.last_error)

    def test_native_save_failure_removes_only_the_new_partial_folder(self):
        self.configure(); self.calculate(); p = self.panel
        target = self.fixture.root / 'failed.inptk'
        with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName', return_value=(str(target), '')):
            with patch.object(Path, 'write_text', side_effect=OSError('Disk full')):
                p.export_result()
        self.assertFalse(target.exists())
        self.assertIn('Could not save result', p.last_error)

    def test_real_cli_plots_history_ranges_export_and_session(self):
        keys = self.configure(); self.calculate()
        self.assertEqual(set(self.panel.result["tables"]),{"Combined","Neat","Combined / Sample_1"})
        self.panel.show_analysis()
        QApplication.processEvents()
        self.assertEqual(self.panel.plot.viewRange()[0][1], 0.)
        original = copy.deepcopy(self.panel.result)
        self.panel.tabs.setCurrentIndex(1)
        self.panel.ranges.selectRow(0)
        self.assertEqual(set(self.panel.range_items), set(keys[:2]))
        self.panel.range_items[keys[0]].setRegion((-7,-5))
        self.assertEqual(self.panel.settings["ranges"][keys[0]], {"min_C":-7,"max_C":-5})
        self.assertIn("Changes not calculated",self.panel.status.text())
        self.panel.undo_stack.undo()
        self.assertEqual(self.panel.result,original)
        self.assertIn("up to date",self.panel.status.text())
        path = self.fixture.root/'result.inptk'
        with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName',return_value=(str(path),'')):
            self.panel.export_result()
        self.assertTrue((path/'analysis.json').is_file())
        self.assertFalse((path/'range-suggestions.json').exists())
        original = copy.deepcopy(self.panel.result)
        session = self.fixture.root/'with_inp.icescopy'
        save_session_bundle(session, build_session_payload(self.window),
            self.window.grayscale_results_headers, self.window.grayscale_results_rows,
            self.window.freeze_results_headers, self.window.freeze_results_rows,
            self.window.freeze_count_timeseries_headers, self.window.freeze_count_timeseries_rows)
        payload, gray, freeze, counts = load_session_bundle(session)
        state = build_restore_state(self.window,payload,gray,freeze,counts)
        self.panel.restore_session(None)
        self.window.restore_session_state(state)
        self.assertEqual(self.panel.result,original)
        self.assertEqual(self.panel.settings["inputs"][keys[0]]["blanks"],[keys[2]])

    def test_source_edit_during_calculation_cannot_install_stale_result(self):
        self.configure(); self.calculate()
        original = self.panel.result
        self.panel.change_option("basis","sampled_air")
        self.panel.recalculate()
        self.window.sample_catalog[0]["air_volume_L"] = "200"
        self.window.refresh_freeze_count_timeseries_metadata_from_sample_catalog()
        self.wait(lambda: not self.panel.operation and not self.panel.client.busy)
        self.assertIs(self.panel.result,original)
        self.assertIn("Changes not calculated",self.panel.status.text())

    def test_incomplete_suggestions_preserve_manual_limits(self):
        keys = self.configure()
        self.panel.settings["ranges"] = {keys[0]:{"min_C":-7,"max_C":-5}}
        before = copy.deepcopy(self.panel.settings["ranges"])
        self.panel.change_option("min_unfrozen",100)
        self.panel.curves.setCurrentRow(0, QItemSelectionModel.ClearAndSelect)
        self.panel.suggest_ranges()
        self.wait(lambda:not self.panel.operation and not self.panel.client.busy)
        self.assertFalse(self.panel.settings["suggestion"]["complete"])
        self.assertEqual(self.panel.settings["ranges"],before)
        self.assertIn("Incomplete",self.panel.suggestion_status.text())

    def test_each_group_input_has_independent_handles_and_numeric_limits(self):
        keys = self.configure()
        self.panel.tabs.setCurrentIndex(1)
        self.assertEqual(set(self.panel.range_items), set(keys[:2]))
        first, second = [self.panel.range_items[key] for key in keys[:2]]
        self.assertEqual(first.span, (0, 1))
        self.assertEqual(first.brush.color().alpha(), 0)
        self.assertEqual(first.lines[0].pen.style(), Qt.DashLine)
        self.panel.ranges.selectRow(1)
        first, second = [self.panel.range_items[key] for key in keys[:2]]
        self.assertFalse(first.lines[0].movable)
        self.assertTrue(second.lines[0].movable)
        self.assertGreater(second.zValue(), first.zValue())
        self.assertEqual([entry[0] for entry in self.panel.range_tags.entries], [keys[1]])
        self.assertEqual(self.panel.range_tags.height(), 34)
        curve = next(item for item in self.panel.plot.listDataItems() if item.property('inp_sample') == keys[0])
        curve.sigClicked.emit(curve, None)
        self.assertEqual([entry[0] for entry in self.panel.range_tags.entries], [keys[0]])
        self.panel.activate_range(keys[1])
        second = self.panel.range_items[keys[1]]
        before = self.panel.undo_stack.index()
        second.setRegion((-7.5, -5.5))
        self.assertEqual(self.panel.undo_stack.index(), before + 1)
        self.assertNotIn(keys[0], self.panel.settings["ranges"])
        self.assertEqual(self.panel.settings["ranges"][keys[1]], {"min_C":-7.5,"max_C":-5.5})
        self.assertEqual(self.panel.ranges.item(1, 1).text(), "-7.50")
        self.panel.undo_stack.undo()
        self.assertEqual(self.panel.settings["ranges"], {})
        self.panel.ranges.item(0, 1).setText("-7")
        self.assertEqual(self.panel.range_items[keys[0]].getRegion(), (-7, 0))
        self.assertEqual(self.panel.range_items[keys[1]].getRegion(), (-8, 0))
        self.panel.curves.setCurrentRow(1, QItemSelectionModel.ClearAndSelect)
        self.assertEqual(set(self.panel.range_items), {keys[0]})
        self.assertTrue(self.panel.ranges.isRowHidden(1))
        self.assertEqual(self.panel.range_ids[self.panel.ranges.currentRow()], keys[0])
        self.panel.curves.setCurrentRow(0, QItemSelectionModel.ClearAndSelect)
        self.assertEqual(set(self.panel.range_items), set(keys[:2]))

    def test_enter_commits_field_without_triggering_window_buttons(self):
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QPushButton
        self.configure()
        p = self.panel
        p.change_option('grid_step', '0.5')
        p.show(); p.tabs.setCurrentIndex(2)
        QTest.qWait(50)
        clicked = []
        for button in p.findChildren(QPushButton):
            button.clicked.connect(lambda checked=False, b=button: clicked.append(b.text()))
            self.assertFalse(button.isDefault())
            self.assertFalse(button.autoDefault())
        for key, value in ((Qt.Key_Return, '-33'), (Qt.Key_Enter, '-34')):
            p.grid_end.setFocus()
            p.grid_end.selectAll()
            QTest.keyClicks(p.grid_end, value)
            QTest.keyClick(p.grid_end, key)
            self.assertEqual(p.settings['grid_end'], value)
            self.assertTrue(p.isVisible())
        self.assertEqual(clicked, [])
        self.assertTrue(p.isWindow())
        self.assertEqual(p.windowModality(), Qt.ApplicationModal)

    def test_analysis_blocks_main_window_and_restores_input_on_close(self):
        from PySide6.QtCore import QObject, QEvent
        from PySide6.QtTest import QTest
        events = []
        class Watcher(QObject):
            def eventFilter(self, watched, event):
                if event.type() in (QEvent.WindowBlocked, QEvent.WindowUnblocked):
                    events.append(event.type())
                return False
        watcher = Watcher(self.window)
        self.window.installEventFilter(watcher)
        self.window.show()
        self.panel.show_analysis()
        QTest.qWait(50)
        self.assertIn(QEvent.WindowBlocked, events)
        self.assertIs(QApplication.activeModalWidget(), self.panel)
        self.assertTrue(self.panel.isEnabled())
        self.panel.close()
        QTest.qWait(50)
        self.assertIn(QEvent.WindowUnblocked, events)
        self.assertIsNone(QApplication.activeModalWidget())
        self.window.hide()

    def test_window_history_is_independent_and_survives_close(self):
        self.configure(); self.calculate()
        original = self.panel.result
        self.panel.undo_stack.clear()
        self.window.undo_stack.push(QUndoCommand("Source edit"))
        self.window.undo_stack.undo()
        main_index = self.window.undo_stack.index()
        self.panel.show_analysis()
        self.assertEqual(self.panel.windowModality(), Qt.ApplicationModal)
        self.assertTrue(self.panel.windowFlags() & Qt.WindowTitleHint)
        self.assertFalse(self.panel.windowFlags() & Qt.FramelessWindowHint)
        self.assertFalse(self.panel.undo_action.isEnabled())
        self.panel.change_option("method", "mle")
        self.assertTrue(self.panel.undo_action.isEnabled())
        self.assertEqual(self.window.undo_stack.index(), main_index)
        self.assertTrue(self.window.undo_stack.canRedo())
        self.panel.undo_action.trigger()
        self.assertEqual(self.panel.settings["method"], "average")
        self.assertFalse(self.panel.undo_action.isEnabled())
        self.panel.close()
        self.assertIs(self.panel.result, original)
        self.panel.show_analysis()
        self.assertTrue(self.panel.redo_action.isEnabled())
        self.panel.redo_action.trigger()
        self.assertEqual(self.panel.settings["method"], "mle")
        self.assertEqual(self.window.undo_stack.index(), main_index)
        self.assertTrue(self.window.undo_stack.canRedo())
        self.panel.close()
        saved = self.panel.session_state()
        self.panel.restore_session(saved)
        self.assertEqual(self.panel.settings["method"], "mle")
        self.assertEqual(self.panel.undo_stack.count(), 0)
        self.assertFalse(self.panel.undo_action.isEnabled())

    def test_main_snapshot_history_does_not_restore_dialog_choices(self):
        self.configure()
        before = self.window.capture_session_state()
        after = copy.deepcopy(before)
        after["image_index"] = 1
        self.window.restore_session_state(after, restore_inp_analysis=False)
        self.window.undo_stack.push(SessionSnapshotCommand(self.window, "Change source", before, after))
        self.panel.change_option("method", "mle")
        dialog_index = self.panel.undo_stack.index()
        self.window.undo_stack.undo()
        self.assertEqual(self.window.image_index, 0)
        self.assertEqual(self.panel.settings["method"], "mle")
        self.assertEqual(self.panel.undo_stack.index(), dialog_index)
        self.window.undo_stack.redo()
        self.assertEqual(self.window.image_index, 1)
        self.assertEqual(self.panel.settings["method"], "mle")
        self.panel.undo_action.trigger()
        self.assertEqual(self.panel.settings["method"], "average")
        self.assertEqual(self.window.image_index, 1)

    def test_mle_air_conversion_and_fraction_csv(self):
        self.configure()
        self.panel.change_option("method", "mle")
        self.calculate()
        suspension = self.panel.result["tables"]["Combined"]["cumulative"]["rows"]
        self.panel.change_option("basis", "sampled_air")
        self.calculate()
        air = self.panel.result["tables"]["Combined"]["cumulative"]["rows"]
        self.assertEqual(len(air), len(suspension))
        for a, s in zip(air, suspension):
            self.assertAlmostEqual(a["concentration"], s["concentration"] * .1)
        path = self.fixture.root/'fractions.csv'
        with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName',return_value=(str(path),'')):
            self.panel.export_csv("frozen_fraction")
        self.wait(lambda:not self.panel.operation and not self.panel.client.busy)
        self.assertIn("fraction_frozen", path.read_text())
        original = self.panel.result
        self.panel.change_option("method", "average")
        self.panel.recalculate()
        self.panel.close()
        self.assertFalse(self.panel.client.busy)
        self.assertIs(self.panel.result, original)

    def test_one_selection_controls_plot_ranges_and_assigned_blank_visibility(self):
        keys = self.configure(); self.calculate()
        p = self.panel
        p.tabs.setCurrentIndex(1)
        p.curves.setCurrentRow(1, QItemSelectionModel.ClearAndSelect)
        self.assertEqual(p.selected_curve_names(), ['Neat'])
        self.assertEqual(set(p.range_items), {keys[0]})
        self.assertEqual([name for name, _ in p.selected_result_tables('cumulative')], ['Neat'])
        self.assertEqual({r['measurement_id'] for r in p.observation_rows()}, {keys[0], keys[2]})
        # Standard multiple selection uses the same list, not another plot picker.
        p.curves.item(0).setSelected(True)
        self.assertEqual(set(p.range_items), set(keys[:2]))
        self.assertEqual(len(p.selected_result_tables('cumulative')), 2)
        self.assertFalse(p.inputs.item(0, 0).flags() & Qt.ItemIsEnabled)
        self.assertFalse(p.suggest.isEnabled())

    def test_new_group_membership_refreshes_raw_plots_without_calculation(self):
        p = self.panel
        keys = list(p.settings['inputs'])
        p.quantity.setCurrentText('Number frozen')
        with patch.object(p.client, 'request') as request:
            p.add_group()
            self.assertEqual(p.visible_points, 0)
            for index, key in enumerate(keys[:2], 1):
                p.inputs.item(p.input_ids.index(key), 0).setCheckState(Qt.Checked)
                self.assertEqual(p.visible_points, 4 * index)
                self.assertGreaterEqual(p.plot_limits[1][1], 10)
            p.quantity.setCurrentText('Fraction frozen')
            self.assertEqual(p.visible_points, 8)
            p.inputs.item(p.input_ids.index(keys[0]), 0).setCheckState(Qt.Unchecked)
            self.assertEqual(p.visible_points, 4)
            p.undo_stack.undo()
            self.assertEqual(p.visible_points, 8)
            request.assert_not_called()

    def test_marked_unassigned_blank_is_drawn_in_both_raw_plots(self):
        p = self.panel
        blank = p.input_ids[2]
        p.quantity.setCurrentText('Number frozen')
        p.inputs.item(2, 3).setCheckState(Qt.Checked)
        original = copy.deepcopy(p.settings)
        with patch.object(p.client, 'request') as request:
            for quantity in ('Number frozen', 'Fraction frozen'):
                p.quantity.setCurrentText(quantity)
                names = [line.opts.get('name', '') or '' for line in p.plot.listDataItems()]
                self.assertTrue(any(blank + ' (water blank)' in name for name in names))
                self.assertEqual(p.visible_points, 8)
            self.assertEqual(p.settings, original)
            self.assertFalse(any(value['blanks'] for value in p.settings['inputs'].values()))
            p.change_option('blank_correction', False)
            self.assertEqual(p.visible_points, 8)
            p.inputs.item(p.input_ids.index(blank), 3).setCheckState(Qt.Unchecked)
            self.assertEqual(p.visible_points, 4)
            p.undo_stack.undo()
            self.assertEqual(p.visible_points, 8)
            request.assert_not_called()

    def test_drag_keeps_active_sample_independent_of_sample_table_selection(self):
        keys = self.configure(); p = self.panel
        p.tabs.setCurrentIndex(1)
        # The last sample clicked in Samples differs from the active range row.
        p.inputs.selectRow(p.input_ids.index(keys[1]))
        p.activate_range(keys[0])
        before = copy.deepcopy(p.settings['ranges'])
        undo_index = p.undo_stack.index()
        for value in (-7.8, -7.6):
            p.tag_moved(keys[0], 0, value, False)
            self.assertEqual(p.range_ids[p.ranges.currentRow()], keys[0])
        p.tag_moved(keys[0], 0, -7.5, True)
        self.assertEqual(p.range_ids[p.ranges.currentRow()], keys[0])
        self.assertEqual([entry[0] for entry in p.range_tags.entries], [keys[0]])
        self.assertEqual(p.settings['ranges'], {keys[0]: {'min_C': -7.5, 'max_C': 0}})
        self.assertEqual(p.current_input(), keys[1])
        self.assertEqual(p.undo_stack.index(), undo_index + 1)
        p.undo_stack.undo()
        self.assertEqual(p.settings['ranges'], before)
        self.assertEqual(p.range_ids[p.ranges.currentRow()], keys[0])
        p.undo_stack.redo()
        self.assertEqual(p.range_ids[p.ranges.currentRow()], keys[0])

    def test_switching_quantity_refits_axes_including_uncertainty(self):
        import numpy as np
        import pyqtgraph as pg
        self.configure(); self.calculate()
        p = self.panel
        p.show_uncertainty.setChecked(True)
        self.assertTrue(self.window.inptk_log_concentration)
        self.window.inptk_log_concentration = False; p.draw()
        p.quantity.setCurrentText('Fraction frozen')
        self.assertLess(p.plot.viewRange()[1][0], 0)
        self.assertGreater(p.plot.viewRange()[1][1], 1)
        p.plot.setYRange(.4, .5, padding=0)
        p.quantity.setCurrentText('Concentration')
        rows = p.result['tables']['Combined']['cumulative']['rows']
        upper = max(r['concentration'] + r['upper_error'] for r in rows)
        self.assertGreater(p.plot.viewRange()[1][1], upper)
        self.assertTrue(p.visible_points)
        self.assertTrue(any(isinstance(item, pg.FillBetweenItem) and not item.path().isEmpty()
                            for item in p.plot.getPlotItem().items))
        self.window.inptk_log_concentration = True; p.draw()
        for item in p.plot.listDataItems():
            if item.opts.get('data'):
                np.testing.assert_allclose(item.scatter.getData()[1], item.getData()[1], equal_nan=True)
        p.quantity.setCurrentText('Number frozen')
        self.assertFalse(p.plot.getPlotItem().ctrl.logYCheck.isChecked())
        self.assertGreater(p.plot.viewRange()[1][1], 10)
        self.assertLess(p.plot.viewRange()[1][1], 11)
        p.plot.setYRange(4, 5, padding=0)
        p.fit_button.click()
        self.assertLess(p.plot.viewRange()[1][0], 0)

    def test_open_connects_automatically_and_calculate_restarts_after_stop(self):
        self.configure()
        p = self.panel
        p.client.stop(); p.preview = None
        p.show_analysis()
        self.wait(lambda: p.preview is not None and not p.client.busy)
        self.assertTrue(p.client.capabilities)
        p.cancel_operation()
        self.assertFalse(p.client.capabilities)
        self.assertTrue(p.calculate.isEnabled())
        self.calculate()
        self.assertEqual(p.last_error, '')
        self.assertTrue(p.cancel.isHidden())

    def test_error_survives_idle_notification_and_is_visible_on_blank_plot(self):
        self.configure()
        p = self.panel
        p.quantity.setCurrentText('Concentration')
        p.change_option('fit_step', '-1')
        p.change_option('method', 'mle')
        p.recalculate()
        p.client.busyChanged.emit(False)
        self.assertIn('Fit spacing', p.status.text())
        self.assertIn('Fit spacing', p.empty_plot.text())
        self.assertIsNone(p.result)
        p.change_option('fit_step', '1')
        self.calculate()
        self.assertEqual(p.empty_plot.text(), '')

    def test_zero_and_nonfinite_concentrations_have_explicit_display_state(self):
        self.configure(); self.calculate()
        p = self.panel
        p.curves.setCurrentRow(1, QItemSelectionModel.ClearAndSelect)
        self.window.inptk_log_concentration = False; p.draw()
        rows = p.result['tables']['Neat']['cumulative']['rows']
        for row in rows:
            row.update(concentration=0., lower_error=0., upper_error={'$nonfinite': 'inf'})
        p.draw()
        self.assertEqual(p.visible_points, len(rows))
        self.window.inptk_log_concentration = True; p.draw()
        self.assertEqual(p.visible_points, 0)
        self.assertIn('No positive', p.empty_plot.text())
        self.window.inptk_log_concentration = False; p.draw()
        self.assertEqual(p.empty_plot.text(), '')
        for row in rows: row['concentration'] = {'$nonfinite': 'inf'}
        p.render_key = None  # Production results are immutable between completed runs.
        p.draw()
        self.assertIn('No finite', p.empty_plot.text())

    def test_group_membership_moves_samples_without_duplicate_group_field(self):
        p = self.panel
        p.curves.setCurrentRow(0, QItemSelectionModel.ClearAndSelect)
        original_names = [c['name'] for c in p.settings['curves']]
        p.inputs.item(1, 0).setCheckState(Qt.Checked)
        self.assertEqual(p.settings['curves'][0]['inputs'], list(p.input_ids[:2]))
        self.assertNotIn(original_names[1], [c['name'] for c in p.settings['curves']])
        self.assertEqual(p.settings['inputs'][p.input_ids[1]]['group'], original_names[0])
        p.undo_stack.undo()
        self.assertEqual([c['name'] for c in p.settings['curves']], original_names)
        p.inputs.item(1, 0).setCheckState(Qt.Checked)
        p.inputs.item(1, 0).setCheckState(Qt.Unchecked)
        self.assertEqual({key for c in p.settings['curves'] for key in c['inputs']}, set(p.input_ids))
        p.inputs.item(2, 3).setCheckState(Qt.Checked)
        self.assertTrue(p.settings['inputs'][p.input_ids[2]]['blank'])
        self.assertNotIn(p.input_ids[2], {key for c in p.settings['curves'] for key in c['inputs']})

    def test_edits_reuse_source_and_unchanged_plot_without_result_tabs(self):
        import icescopy_inptk_panel as module
        p = self.panel
        with patch.object(module, 'prepare_source', wraps=module.prepare_source) as prepare:
            p.current_hash()
            for i in range(3): p.curves.item(0).setText(f'Renamed {i}')
            self.assertEqual(prepare.call_count, 0)
        self.assertFalse(hasattr(p, 'views'))
        with patch.object(p.plot, 'clear', wraps=p.plot.clear) as clear:
            p.draw(); p.draw()
            self.assertEqual(clear.call_count, 0)
        p.source_changed()
        with patch.object(module, 'prepare_source', wraps=module.prepare_source) as prepare:
            p.refresh_preview()
            self.wait(lambda:not p.operation and not p.client.busy)
            self.assertEqual(prepare.call_count, 1)

    def test_full_range_uses_measured_placeholders_and_undo_restores_limits(self):
        p = self.panel
        p.inputs.item(1, 0).setCheckState(Qt.Checked)
        p.tabs.setCurrentIndex(1)
        keys = p.selected_input_ids()
        self.assertEqual(len(keys), 2)
        self.assertFalse(p.settings['ranges'])
        self.assertEqual(p.ranges.item(0, 1).text(), '')
        self.assertEqual(p.ranges.item(0, 1).data(Qt.UserRole), '-8.00')
        self.assertEqual(p.ranges.item(0, 2).data(Qt.UserRole), '0.00')
        p.ranges.item(0, 1).setText('-7')
        p.ranges.item(1, 2).setText('-6')
        before = copy.deepcopy(p.settings['ranges'])
        p.full_range.click()
        self.assertFalse(p.settings['ranges'])
        self.assertEqual(p.range_items[keys[0]].getRegion(), (-8., 0.))
        p.undo_stack.undo()
        self.assertEqual(p.settings['ranges'], before)
        self.assertEqual(p.range_items[keys[1]].getRegion(), (-8., -6.))

    def test_blank_role_assignment_and_removal_are_visible_and_undoable(self):
        p = self.panel
        self.assertTrue(p.blank_choice.isHidden())
        self.assertIn('Mark a water control', p.blank_help.text())
        p.inputs.item(2, 3).setCheckState(Qt.Checked)
        p.inputs.selectRow(0)
        self.assertFalse(p.blank_choice.isHidden())
        self.assertIn('leave all assignments empty', p.blank_help.text())
        blank = p.input_ids[2]
        p.change_blanks([blank])
        self.assertTrue(p.blank_help.isHidden())
        p.blank_enabled.setChecked(False)
        self.assertFalse(p.blank_choice.isEnabled())
        self.assertEqual(p.settings['inputs'][p.input_ids[0]]['blanks'], [blank])
        p.blank_enabled.setChecked(True)
        p.inputs.item(2, 3).setCheckState(Qt.Unchecked)
        self.assertEqual(p.settings['inputs'][p.input_ids[0]]['blanks'], [])
        p.undo_stack.undo()
        self.assertTrue(p.settings['inputs'][blank]['blank'])
        self.assertEqual(p.settings['inputs'][p.input_ids[0]]['blanks'], [blank])

    def test_range_placeholders_follow_selected_cycle_without_changing_settings(self):
        p = self.panel
        key = p.input_ids[0]
        other = dict(p.preview['table']['rows'][0], measurement_id=key, cycle_id='later', temperature_C=-20.)
        p.preview['table']['rows'].append(other)
        p.restore_choices(p.settings)
        self.assertEqual(p.ranges.item(0, 1).data(Qt.UserRole), '-8.00')
        p.change_input_cycle(key, 'later')
        self.assertEqual(p.ranges.item(0, 1).data(Qt.UserRole), '-20.00')
        self.assertFalse(p.settings['ranges'])

    def test_range_display_rounding_preserves_drag_and_saved_precision(self):
        keys = self.configure(); p = self.panel
        p.tabs.setCurrentIndex(1)
        exact = -7.670121751025988
        p.tag_moved(keys[0], 0, exact, True)
        self.assertEqual(p.settings['ranges'][keys[0]]['min_C'], exact)
        self.assertEqual(p.ranges.item(0, 1).text(), '-7.67')
        saved = p.session_state()
        self.assertEqual(saved['choices']['ranges'][keys[0]]['min_C'], exact)
        p.restore_session(saved)
        self.assertEqual(p.settings['ranges'][keys[0]]['min_C'], exact)
        self.assertEqual(p.ranges.item(0, 1).text(), '-7.67')

    def test_previous_unrestricted_saved_fit_is_stale_after_zero_degree_default(self):
        from icescopy_inptk_state import fingerprint
        self.configure(); self.calculate()
        p = self.panel
        old_choices = {k: v for k, v in p.settings.items()
                       if k not in {'suggestion', 'min_frozen', 'min_unfrozen'}}
        p.result['key'] = fingerprint([p.current_hash(), old_choices])
        p.draw()
        self.assertIn('Changes not calculated', p.status.text())

    def test_optional_grid_and_plot_changes_preserve_export_data(self):
        p = self.panel
        self.assertTrue(p.grid_enabled.isChecked())
        p.grid_enabled.setChecked(False)
        self.assertEqual(p.settings['grid_step'], '')
        p.undo_stack.undo()
        self.assertEqual(p.settings['grid_step'], '0.5')
        self.configure(); self.calculate()
        original = copy.deepcopy(p.result)
        p.quantity.setCurrentText('Fraction frozen')
        p.quantity.setCurrentText('Concentration')
        self.assertEqual(p.result, original)

    def test_default_grid_and_sample_colors_match_icescopy(self):
        p = self.panel
        self.assertEqual(p.settings['grid_step'], '0.5')
        for entry in self.window.freeze_count_timeseries_summary['sample_total_cells']:
            self.assertEqual(p.color(entry['sample_name']), self.window.sample_visual_color(entry['sample_id']))
        # Reordered or sparse identities must not take a palette color by list position.
        entry = self.window.freeze_count_timeseries_summary['sample_total_cells'][0]
        entry['sample_id'] = '8'
        self.assertEqual(p.color(entry['sample_name']), self.window.sample_visual_color(8))
        self.calculate()
        for name, table in p.result['tables'].items():
            sources = {source['measurement_id'] for source in p.result['reply']['curves'][name]['sources']}
            # The third fixture sample freezes only at -8 C; the others start at -6 C.
            expected = [-8.] if sources == {p.input_ids[2]} else [-6., -6.5, -7., -7.5, -8.]
            self.assertEqual([r['temperature_C'] for r in table['cumulative']['rows']], expected)
        p.change_option('grid_step', '')
        saved = p.session_state()
        p.restore_session(saved)
        self.assertEqual(p.settings['grid_step'], '')  # Explicit saved settings survive the new default.

    def test_grid_endpoint_fields_show_values_after_reopening_and_clearing(self):
        p = self.panel
        saved = p.session_state()
        saved['choices'].update(grid_start='', grid_end='')
        p.restore_session(saved)
        self.assertEqual((p.grid_start.text(), p.grid_end.text()), ('0', '-35'))
        self.assertEqual((p.settings['grid_start'], p.settings['grid_end']), ('0', '-35'))
        for key, default in (('grid_start', '0'), ('grid_end', '-35')):
            widget = getattr(p, key)
            widget.clear(); widget.editingFinished.emit()
            self.assertEqual(widget.text(), default)
            self.assertEqual(p.settings[key], default)
        p.change_option('grid_start', '-5')
        p.grid_start.clear(); p.grid_start.editingFinished.emit()
        self.assertEqual(p.grid_start.text(), '0')
        p.undo_stack.undo()
        self.assertEqual(p.grid_start.text(), '-5')
        p.undo_stack.redo()
        self.assertEqual(p.grid_start.text(), '0')
        saved = p.session_state()
        saved['choices'].update(grid_start='-2', grid_end='-35')
        p.restore_session(saved)
        self.assertEqual((p.grid_start.text(), p.grid_end.text()), ('-2', '-35'))

    def test_catalog_columns_include_nonexported_custom_fields_and_scroll(self):
        from PySide6.QtTest import QTest
        keys = self.configure(); p = self.panel; w = self.window
        before = copy.deepcopy(p.settings)
        custom = dict(w.active_sample_metadata_schema()[-1], key='instrument', label='Instrument', type='text', fixed=False, export=False)
        w.sample_metadata_schema.append(custom)
        w.sample_catalog[0]['instrument'] = 'Cold stage A'
        w.sample_catalog[0]['sampling_site'] = 'Lab'
        w.inptk_sample_columns = [f['key'] for f in w.active_sample_metadata_schema() if f['key'] != 'sample_name']
        p.refresh_sample_table_columns()
        p.show(); p.tabs.setCurrentIndex(0); QTest.qWait(100)
        headers = [p.inputs.horizontalHeaderItem(i).text() for i in range(p.inputs.columnCount())]
        self.assertIn('Instrument', headers)
        self.assertEqual(p.inputs.item(p.input_ids.index(keys[0]), headers.index('Instrument')).text(), 'Cold stage A')
        range_headers = [p.ranges.horizontalHeaderItem(i).text() for i in range(p.ranges.columnCount())]
        self.assertIn('Instrument', range_headers)
        self.assertEqual(p.ranges.item(p.range_ids.index(keys[0]), range_headers.index('Instrument')).text(), 'Cold stage A')
        self.assertEqual(p.inputs.horizontalScrollBarPolicy(), Qt.ScrollBarAsNeeded)
        self.assertGreater(p.inputs.horizontalScrollBar().maximum(), 0)
        w.inptk_sample_columns = []
        p.refresh_sample_table_columns()
        self.assertTrue(p.inputs.isColumnHidden(2))
        self.assertEqual(p.inputs.columnCount(), 5)
        self.assertEqual(p.settings, before)

    def test_sample_visibility_changes_only_plot_and_survives_session_restore(self):
        keys = self.configure(); self.calculate(); p = self.panel
        p.curves.setCurrentRow(0, QItemSelectionModel.ClearAndSelect)
        choices = copy.deepcopy(p.settings)
        result = p.result
        calculation_key = p.calculation_key()
        original_csv = concentration_csv(result['tables'], [(c['name'], c['name']) for c in result['choices']['curves']])
        p.tabs.setCurrentIndex(1)
        row = p.input_ids.index(keys[0])
        self.assertEqual(p.inputs.item(row, 2).text(), '1×')
        self.assertEqual(p.inputs.item(p.input_ids.index(keys[1]), 2).text(), '10×')
        with patch.object(p.client, 'request', wraps=p.client.request) as requests:
            p.inputs.item(row, 4).setCheckState(Qt.Unchecked)
            self.assertNotIn(keys[0], p.range_items)
            self.assertTrue(all(keys[0] not in label.text for _, label in p.legend.items))
            self.assertTrue(any('(combined)' in label.text for _, label in p.legend.items))
            p.show_combined.setChecked(False)
            self.assertTrue(all('(combined)' not in label.text for _, label in p.legend.items))
            p.inputs.item(p.input_ids.index(keys[1]), 4).setCheckState(Qt.Unchecked)
            self.assertIn('All curves are hidden', p.empty_plot.text())
            for quantity in ('Number frozen', 'Fraction frozen'):
                p.quantity.setCurrentText(quantity)
                self.assertEqual([label.text for _, label in p.legend.items], [f'{keys[2]} (water blank)'])
            p.inputs.item(p.input_ids.index(keys[2]), 4).setCheckState(Qt.Unchecked)
            self.assertIn('All curves are hidden', p.empty_plot.text())
            self.assertEqual(requests.call_count, 0)
        self.assertEqual(p.settings, choices)
        self.assertIs(p.result, result)
        self.assertEqual(p.calculation_key(), calculation_key)
        self.assertEqual(concentration_csv(result['tables'], [(c['name'], c['name']) for c in result['choices']['curves']]), original_csv)
        saved = p.session_state()
        p.restore_session(saved)
        self.assertEqual(p.hidden_plot_inputs, set(keys))
        self.assertFalse(p.show_combined.isChecked())
        self.assertEqual(p.inputs.item(row, 4).checkState(), Qt.Unchecked)
        p.inputs.item(row, 4).setCheckState(Qt.Checked)
        self.assertTrue(any(keys[0] in label.text for _, label in p.legend.items))
        # Older sessions default to displaying every curve.
        saved.pop('display')
        p.restore_session(saved)
        self.assertEqual(p.hidden_plot_inputs, set())
        self.assertTrue(p.show_combined.isChecked())

    def test_uncertainty_toggle_changes_only_display(self):
        import pyqtgraph as pg
        self.configure(); self.calculate()
        p = self.panel
        original = copy.deepcopy(p.result)
        key, undo_index = p.calculation_key(), p.undo_stack.index()
        self.assertTrue(p.show_uncertainty.isChecked())
        uncertainty_top = p.plot_limits[1][1]
        self.assertTrue(any(isinstance(item, pg.FillBetweenItem) for item in p.plot.getPlotItem().items))
        p.show_uncertainty.setChecked(False)
        curve_top = p.plot_limits[1][1]
        self.assertLess(curve_top, uncertainty_top)
        self.assertFalse(any(isinstance(item, pg.FillBetweenItem) for item in p.plot.getPlotItem().items))
        p.show_uncertainty.setChecked(True)
        self.assertEqual(p.plot_limits[1][1], uncertainty_top)
        self.assertEqual(p.result, original)
        self.assertEqual(p.calculation_key(), key)
        self.assertEqual(p.undo_stack.index(), undo_index)
        p.show_uncertainty.setChecked(False)
        self.assertEqual(p.plot_limits[1][1], curve_top)

    def test_individual_uncertainty_uses_sample_colors_and_outside_muting(self):
        import pyqtgraph as pg
        keys = self.configure(); p = self.panel
        p.change_option('grid_step', '0.5'); self.calculate()
        state = copy.deepcopy(p.settings)
        state['ranges'][keys[0]] = {'min_C': -7, 'max_C': -5}
        p.commit(state, 'Restrict first dilution')
        # Linear display allows bounds equal to zero; the toolkit values remain unchanged.
        self.window.inptk_log_concentration = False; p.draw()
        bands = [item for item in p.plot.getPlotItem().items if isinstance(item, pg.FillBetweenItem)]
        colors = [item.brush().color() for item in bands if not item.path().isEmpty()]
        for key in keys[:2]:
            matching = [color for color in colors if color.rgb() == p.color(key).rgb()]
            self.assertTrue(matching, f'Missing uncertainty for {key}')
            self.assertTrue(any(abs(color.alphaF() - .14) < .01 for color in matching))
        first = [color for color in colors if color.rgb() == p.color(keys[0]).rgb()]
        self.assertTrue(any(color.alphaF() < .1 for color in first))
        self.assertTrue(any(color.rgb() == QColor(Qt.black).rgb() for color in colors))
        self.assertEqual(p.plot_limits[0][1], 0.)

    def test_excluded_individual_point_inside_limits_is_faded_without_changing_saved_tables(self):
        keys = self.configure(); self.calculate(); p = self.panel
        self.window.inptk_log_concentration = False
        reference = p.result['references']
        table = reference['tables'][reference['by_input'][keys[0]]]
        point = dict(table['cumulative']['rows'].pop(0))
        point.update(concentration=3., lower_error=1., upper_error=2.)
        table['excluded']['rows'].append(point)
        before = copy.deepcopy(table)
        p.reference_plot_tables.clear(); p.render_key = None; p.draw()
        curves = p.plot.listDataItems()
        full = [c for c in curves if c.opts.get('name') and c.opts.get('data')
                and any(r.get('_display_excluded') for r in c.opts['data'])]
        self.assertTrue(full)
        for curve in full:
            for row, y in zip(curve.opts['data'], curve.yData):
                if row.get('_display_excluded'): self.assertTrue(math.isnan(y))
        faded = [c for c in curves if c.opts['pen'].color().rgb() == p.color(keys[0]).rgb()
                 and abs(c.opts['pen'].color().alphaF() - self.window.inptk_outside_opacity / 100.) < .01]
        self.assertTrue(any(any(x == point['temperature_C'] and y == 3.
                               for x, y in zip(c.xData, c.yData)) for c in faded))
        self.assertEqual(table, before)

    def test_full_individual_fits_preserve_combined_results_and_reuse_cached_references(self):
        keys = self.configure()
        p = self.panel
        state = copy.deepcopy(p.settings)
        state['ranges'] = {keys[1]: {'min_C': -7, 'max_C': -5}}
        p.commit(state, 'Restrict one dilution')
        # Compare against a real toolkit calculation without extra outputs.
        source = self.fixture.root / 'baseline.csv'
        source.write_text(build_freeze_count_timeseries_csv_text(self.window.freeze_count_timeseries_headers,
            self.window.freeze_count_timeseries_rows, summary=self.window.freeze_count_timeseries_summary))
        output = self.fixture.root / 'baseline.inptk'
        responses = []
        p.client.request(['analyze', str(source), '--format', 'icescopy', *cli_choices(p.settings),
                          '--out', str(output)], responses.append)
        self.wait(lambda: responses and not p.client.busy)
        baseline = json.loads((output / 'analysis.json').read_text())
        with patch.object(p.client, 'request', wraps=p.client.request) as requests:
            self.calculate()
            self.assertEqual([c.args[0][0] for c in requests.call_args_list if c.args[0][0] == 'analyze'], ['analyze', 'analyze'])
            old_reference = p.result['reference']
            self.assertEqual(p.calculate.text(), 'Calculate')
            p.calculate.click()
            self.wait(lambda:not p.operation and not p.client.busy)
            self.assertEqual([c.args[0][0] for c in requests.call_args_list if c.args[0][0] == 'analyze'],
                             ['analyze', 'analyze', 'analyze'])
            self.assertNotEqual(p.result['reference'], old_reference)
            self.assertEqual(p.calculate.text(), 'Calculate')
        tables = dict(p.concentration_tables('cumulative'))
        self.assertEqual(set(tables), {'Combined', ('individual', keys[0]), ('individual', keys[1])})
        for name in ('Combined', 'Neat'):
            expected_rows = [{key: row[key] for key in PLOT_COLUMNS} for row in baseline['curves'][name]['tables']['cumulative']['rows']]
            self.assertEqual(p.result['tables'][name]['cumulative']['rows'], expected_rows)
        individual = p.result['references']['reply']['curves'][keys[1]]
        self.assertEqual(individual['sources'][0]['water_blank_ids'], [keys[2]])
        self.assertEqual([r['temperature_C'] for r in tables[('individual', keys[1])]['rows']], [-5., -6., -7., -8.])
        curves = [item for item in p.plot.listDataItems() if item.opts.get('data') and item.opts.get('name')]
        self.assertEqual(len(curves), 3)
        self.assertEqual(sum(item.opts['pen'].style() == Qt.DashLine for item in curves), 2)
        for key in p.result['references']['by_input']:
            label, color_key, overlay = p.concentration_style(('individual', key))
            self.assertEqual(color_key, key)
            self.assertTrue(overlay)
        # The table payload read directly is the same data exposed by the CLI.
        responses.clear()
        p.client.request(['table', str(output), '--curve', 'Combined', '--table', 'cumulative'], responses.append)
        self.wait(lambda: responses and not p.client.busy)
        self.assertEqual(responses[0]['table'], baseline['curves']['Combined']['tables']['cumulative'])
        path = self.fixture.root / 'full-range.inptk'
        with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName', return_value=(str(path), '')):
            p.export_result()
        self.assertEqual((path / 'individual-samples.inptk' / 'analysis.json').read_text(),
                         p.result['references']['saved_result'])
        csv_path = self.fixture.root / 'individual.csv'
        with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName', return_value=(str(csv_path), '')):
            p.export_csv('individual')
        self.wait(lambda:not p.operation and not p.client.busy)
        import csv
        with csv_path.open() as handle: exported = list(csv.DictReader(handle))
        expected = p.result['references']['tables'][keys[1]]['cumulative']['rows']
        column = f'{keys[1]} concentration (INP/mL suspension)'
        self.assertEqual([float(r[column]) for r in exported if r[column]], [r['concentration'] for r in expected])

    def test_range_edits_reuse_full_range_fits_and_report_history_is_lightweight(self):
        keys = self.configure(); self.calculate()
        p = self.panel
        reference = p.result['references']
        with patch.object(p.client, 'request', wraps=p.client.request) as requests:
            p.settings['ranges'][keys[1]] = {'min_C': -7, 'max_C': -6}
            self.calculate()
            self.assertEqual(sum(call.args[0][0] == 'analyze' for call in requests.call_args_list), 1)
            self.assertIs(p.result['references'], reference)
        p.suggest_ranges()
        self.wait(lambda:not p.operation and not p.client.busy)
        report = p.settings['suggestion']
        self.assertTrue(report)
        with patch.object(p.client, 'request', wraps=p.client.request) as requests:
            p.suggest_ranges()
            self.assertEqual(requests.call_count, 0)
        p.change_option('grid_step', '1')
        self.assertIs(p.settings['suggestion'], report)
        self.assertIs(p.undo_stack.command(p.undo_stack.index()-1).before['suggestion'], report)
        # Undo can restore a different report; cache the matching report itself.
        p.settings['suggestion'] = {'complete': False}
        p.change_option('grid_step', '')
        with patch.object(p.client, 'request', wraps=p.client.request) as requests:
            p.suggest_ranges()
            self.assertEqual(requests.call_count, 0)
        self.assertIs(p.settings['suggestion'], report)

    def test_cycle_selector_and_legend_only_show_multiple_cycles(self):
        keys = self.configure(); p = self.panel
        for quantity in ('Number frozen', 'Fraction frozen'):
            p.quantity.setCurrentText(quantity)
            self.assertTrue(p.input_cycle.isHidden())
            self.assertTrue(all(' · cycle ' not in label.text for _, label in p.legend.items))
            self.assertTrue(any('(water blank)' in label.text for _, label in p.legend.items))
        # Add a second actual count-table cycle, then reload through the client.
        headers = self.window.freeze_count_timeseries_headers
        rows = self.window.freeze_count_timeseries_rows
        cycle_col = headers.index('cycle')
        temperature_col = headers.index('temperature_C')
        later = copy.deepcopy(rows)
        for row in later:
            row[cycle_col] = 1
            row[temperature_col] = float(row[temperature_col]) - 10
        rows.extend(later)
        p.source_changed(); p.refresh_preview()
        self.wait(lambda:not p.operation and not p.client.busy)
        p.inputs.selectRow(p.input_ids.index(keys[0]))
        self.assertFalse(p.input_cycle.isHidden())
        self.assertIn('below the table', p.sample_help.text())
        p.input_cycle.setCurrentIndex(p.input_cycle.findData('1'))
        self.assertEqual(p.settings['inputs'][keys[0]]['cycle'], '1')
        for quantity in ('Number frozen', 'Fraction frozen'):
            p.quantity.setCurrentText(quantity)
            names = [label.text for _, label in p.legend.items]
            self.assertIn(f'{keys[0]} · cycle 1', names)
            self.assertIn(f'{keys[2]} (water blank) · cycle 1', names)
        args = cli_choices(p.settings)
        curves = json.loads(args[args.index('--curves') + 1])
        self.assertEqual(curves['Combined']['inputs'][0]['cycle_id'], '1')

    def test_assigned_blank_uses_the_selected_sample_cycle(self):
        keys = self.configure(); p = self.panel
        original = p.preview['table']['rows']
        later = [dict(row, cycle_id='later', temperature_C=row['temperature_C']-10) for row in original]
        p.preview = dict(p.preview, table=dict(p.preview['table'], rows=original+later))
        state = copy.deepcopy(p.settings)
        for key in keys[:2]: state['inputs'][key]['cycle']='later'
        p.commit(state, 'Use later sample cycle')
        rows = p.observation_rows()
        self.assertEqual({r['cycle_id'] for r in rows}, {'later'})
        self.assertEqual({r['measurement_id'] for r in rows}, set(keys))

    def test_memory_upload_reuse_release_and_no_calculation_files(self):
        keys = self.configure(); p = self.panel
        with patch.object(p.client, 'request_body', wraps=p.client.request_body) as requests:
            self.calculate()
            first_reference = p.result['reference']
            self.assertEqual(sum('import' in call.args[0] for call in requests.call_args_list), 1)
            state = copy.deepcopy(p.settings)
            state['ranges'][keys[1]] = {'min_C': -7, 'max_C': -5}
            p.commit(state, 'Restrict sample'); self.calculate()
            self.assertEqual(sum('import' in call.args[0] for call in requests.call_args_list), 1)
            state = copy.deepcopy(p.settings)
            for key in keys[:2]:
                state['inputs'][key]['blanks'] = []
            p.commit(state, 'Change blank mapping'); self.calculate()
            self.assertEqual(sum('import' in call.args[0] for call in requests.call_args_list), 2)
            self.assertNotIn(first_reference, p.live_refs)
            self.assertLessEqual(len(p.live_refs), 3)
            p.suggest_ranges(); self.wait(lambda:not p.operation and not p.client.busy)
            self.assertNotIn('table', p.settings['suggestion'])
        self.assertEqual(list(Path(p.cache.name).iterdir()), [])
        self.assertNotIn('saved_result', p.result)

    def test_native_source_mapping_matches_csv_and_retains_rows_without_pictures(self):
        p = self.panel; w = self.window
        w.freeze_count_timeseries_rows[1][w.freeze_count_timeseries_headers.index('picture')] = ''
        p.source_changed(); p.refresh_preview(); self.wait(lambda:not p.operation and not p.client.busy)
        source = self.fixture.root / 'reader-comparison.csv'
        source.write_text(build_freeze_count_timeseries_csv_text(w.freeze_count_timeseries_headers,
                          w.freeze_count_timeseries_rows, summary=w.freeze_count_timeseries_summary))
        replies = []
        p.client.request(['preview', str(source), '--format', 'icescopy'], replies.append)
        self.wait(lambda:bool(replies) and not p.client.busy)
        fields = ['measurement_id', 'cycle_id', 'time_s', 'temperature_C', 'n_total', 'n_frozen', 'fraction_frozen', 'picture_id']
        def project(rows):
            # The CSV reader represents an absent picture as tagged NaN; the
            # native upload retains an empty ID. Neither drops the observation.
            return [[('' if key == 'picture_id' and isinstance(row[key], dict)
                      and row[key].get('$nonfinite') == 'nan' else row[key])
                     for key in fields] for row in rows]
        self.assertEqual(project(p.preview['table']['rows']), project(replies[0]['table']['rows']))
        self.assertEqual(p.preview['measurement_metadata'], replies[0]['measurement_metadata'])
        self.assertTrue(any(not row['picture_id'] for row in p.preview['table']['rows']))

    def test_session_save_captures_native_results_and_reopened_export_does_not_refit(self):
        self.configure(); self.calculate(); p = self.panel; w = self.window
        self.assertNotIn('saved_result', p.result)
        path = self.fixture.root / 'memory-result.icescopy'
        self.assertTrue(w.persist_session_to_path(str(path), show_errors=False))
        native = p.result['saved_result']
        payload, gray, freeze, counts = load_session_bundle(path)
        restored = build_restore_state(w, payload, gray, freeze, counts)
        w.restore_session_state(restored)
        self.assertEqual(p.result['saved_result'], native)
        p.ensure_connected(); self.wait(lambda:not p.operation and not p.client.busy)
        target = self.fixture.root / 'restored.csv'
        with patch.object(p.client, 'request', wraps=p.client.request) as requests:
            with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName', return_value=(str(target), '')):
                p.export_csv()
            self.wait(lambda:not p.operation and not p.client.busy)
            self.assertFalse(any(call.args[0][0] == 'analyze' for call in requests.call_args_list))
        self.assertIn('concentration', target.read_text())
        self.assertEqual(list(Path(p.cache.name).iterdir()), [])

    def test_unused_sample_does_not_block_calculation_or_reuse_the_wrong_upload(self):
        keys = self.configure(); p = self.panel
        state = copy.deepcopy(p.settings)
        state['curves'] = [{'name': 'Neat', 'inputs': [keys[0]]}]
        state['inputs'][keys[1]].update(group='Unused', blanks=[])
        p.commit(state, 'Calculate only the neat sample')
        with patch.object(p.client, 'request_body', wraps=p.client.request_body) as requests:
            self.calculate()
            uploads = [call.args[0]['import'] for call in requests.call_args_list if 'import' in call.args[0]]
            self.assertEqual(len(uploads), 1)
            self.assertEqual(set(uploads[0]['counts']['measurement_id']), {keys[0], keys[2]})
            self.assertEqual({r['measurement_id'] for r in uploads[0]['metadata']}, {keys[0], keys[2]})
            self.assertEqual(uploads[0]['water_blank_map'], {keys[0]: [keys[2]]})
            # Raw plots retain the complete source, including unused samples.
            self.assertEqual({r['measurement_id'] for r in p.preview['table']['rows']}, set(keys))
            state = copy.deepcopy(p.settings)
            state['curves'] = [{'name': 'Combined', 'inputs': keys[:2]}]
            state['inputs'][keys[1]].update(group=state['inputs'][keys[0]]['group'], blanks=[keys[2]])
            p.commit(state, 'Include the diluted sample'); self.calculate()
            uploads = [call.args[0]['import'] for call in requests.call_args_list if 'import' in call.args[0]]
            self.assertEqual(len(uploads), 2)
            self.assertEqual(set(uploads[1]['counts']['measurement_id']), set(keys))

    def test_auto_range_uploads_only_the_selected_group_and_its_blank(self):
        keys = self.configure(); p = self.panel
        state = copy.deepcopy(p.settings)
        state['curves'] = [{'name': 'Neat', 'inputs': [keys[0]]}, {'name': 'Other', 'inputs': [keys[1]]}]
        state['inputs'][keys[1]].update(group='Other', blanks=[])
        p.commit(state, 'Separate groups')
        with patch.object(p.client, 'request_body', wraps=p.client.request_body) as requests:
            for row, expected in ((0, {keys[0], keys[2]}), (1, {keys[1]})):
                p.curves.setCurrentRow(row, QItemSelectionModel.ClearAndSelect)
                p.suggest_ranges()
                self.wait(lambda:not p.operation and not p.client.busy)
                self.assertFalse(p.last_error, p.last_error)
                uploads = [call.args[0]['import'] for call in requests.call_args_list if 'import' in call.args[0]]
                self.assertEqual(len(uploads), row+1)
                self.assertEqual(set(uploads[-1]['counts']['measurement_id']), expected)

    def test_limited_result_survives_failed_full_range_comparison_and_can_retry(self):
        keys = self.configure(); p = self.panel; w = self.window
        frozen_col = w.freeze_count_timeseries_headers.index(keys[0] + ' number frozen')
        for row, frozen in zip(w.freeze_count_timeseries_rows, [0, 3, 2, 1]):
            row[frozen_col] = frozen
        p.source_changed()
        state = copy.deepcopy(p.settings)
        state['curves'] = [{'name': 'Neat', 'inputs': [keys[0]]}]
        state['inputs'][keys[0]]['blanks'] = []
        state['method'] = 'mle'
        state['ranges'] = {keys[0]: {'min_C': -6, 'max_C': -5}}
        p.commit(state, 'Use the valid cooling interval')
        self.calculate()
        self.assertIn('cumulative first-freezing counts', p.result['comparison_error'])
        self.assertNotIn('references', p.result)
        self.assertFalse(p.last_error)
        self.assertIn('Full-range individual samples unavailable', p.status.text())
        self.assertEqual({r['temperature_C'] for r in p.result['tables']['Neat']['cumulative']['rows']}, {-6.})
        p.prepare_session_save(require_native=True)
        self.assertTrue(p.result['saved_result'])
        self.assertLessEqual(len(p.live_refs), 2)
        # Retry after correcting the source also restores comparison overlays.
        for row, frozen in zip(w.freeze_count_timeseries_rows, [0, 3, 5, 8]):
            row[frozen_col] = frozen
        p.source_changed(); self.calculate()
        self.assertIn('references', p.result)
        self.assertNotIn('comparison_error', p.result)

    def test_saved_csv_export_reconnects_without_current_counts_or_refitting(self):
        keys = self.configure(); self.calculate(); p = self.panel; w = self.window
        p.prepare_session_save(require_native=True)
        saved = copy.deepcopy(p.session_state())
        for kind in ('cumulative', 'individual'):
            with self.subTest(kind=kind):
                p.restore_session(copy.deepcopy(saved))
                if kind == 'cumulative':
                    w.freeze_count_timeseries_summary['analysis_required'] = True
                else:
                    w.freeze_count_timeseries_headers = []
                    w.freeze_count_timeseries_rows = []
                target = self.fixture.root / ('saved-group.csv' if kind == 'cumulative' else 'saved-individual.csv')
                with patch.object(p.client, 'request', wraps=p.client.request) as requests:
                    with patch.object(p, 'refresh_preview', wraps=p.refresh_preview) as refresh:
                        with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName', return_value=(str(target), '')) as chooser:
                            p.export_csv(kind)
                            self.wait(lambda:not p.operation and not p.client.busy)
                    self.assertFalse(refresh.called)
                    chooser.assert_called_once()
                    self.assertFalse(any(call.args[0][0] == 'analyze' for call in requests.call_args_list))
                self.assertFalse(p.last_error, p.last_error)
                self.assertIn('concentration', target.read_text())
                self.assertEqual(list(Path(p.cache.name).iterdir()), [])

    def test_auto_range_validation_is_reported_without_stopping_the_client(self):
        keys = self.configure(); p = self.panel
        good = copy.deepcopy(p.settings)
        for field, invalid, message in (('cycle', '', 'Select a cycle'),
                                        ('grid_step', 'abc', 'Enter a valid number for Count step (°C).')):
            with self.subTest(field=field):
                state = copy.deepcopy(good)
                if field == 'cycle': state['inputs'][keys[0]][field] = invalid
                else: state[field] = invalid
                p.commit(state, 'Invalid analysis choice')
                p.curves.setCurrentRow(0, QItemSelectionModel.ClearAndSelect)
                with patch.object(p.client, 'request_body', wraps=p.client.request_body) as requests:
                    with patch.object(self.window, 'log') as log:
                        p.suggest_ranges()
                self.assertIn(message, p.last_error)
                self.assertIn(message, p.status.text())
                self.assertTrue(log.called)
                self.assertFalse(requests.called)
                self.assertFalse(p.operation)
                self.assertIsNotNone(p.client.capabilities)

    def test_worker_keeps_ui_responsive_and_shutdown_cannot_restart_it(self):
        from PySide6.QtCore import QTimer, QThread
        p = self.panel; ticks = []; answers = []
        timer = QTimer(); timer.setInterval(10); timer.timeout.connect(lambda:ticks.append(1)); timer.start()
        def work():
            time.sleep(.1)
            return QThread.currentThread() is QApplication.instance().thread()
        p.client.compute(work, answers.append)
        self.wait(lambda:bool(answers))
        timer.stop()
        self.assertFalse(answers[0]); self.assertGreaterEqual(len(ticks), 3)
        p.shutdown()
        p.client.connect_executable(self.window.inptk_executable_path)
        QApplication.processEvents()
        self.assertFalse(p.client.thread.isRunning())

    def test_process_loss_preserves_display_and_core_session_save(self):
        self.configure(); self.calculate(); p = self.panel
        displayed = copy.deepcopy(p.result['tables'])
        p.cancel_operation()
        self.assertEqual(p.result['tables'], displayed)
        path = self.fixture.root / 'after-process-loss.icescopy'
        self.assertTrue(self.window.persist_session_to_path(str(path), show_errors=False))
        payload, *_ = load_session_bundle(path)
        self.assertTrue(payload['inp_analysis']['result']['native_result_unavailable'])
        self.assertEqual(payload['inp_analysis']['result']['tables'], displayed)



class InpLegendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_plot(self):
        import pyqtgraph as pg
        from PySide6.QtWidgets import QWidget, QVBoxLayout
        from icescopy_inptk_plot import PlotLegend
        widget = QWidget(); layout = QVBoxLayout(widget)
        plot = pg.PlotWidget(); layout.addWidget(plot, 1)
        legend = PlotLegend(plot, '10pt')
        plot.getPlotItem().legend = legend.legend
        widget.resize(800, 500); widget.show()
        self.addCleanup(widget.close)
        return plot, legend

    def settle(self, legend):
        from PySide6.QtTest import QTest
        legend.schedule(); QTest.qWait(160)

    def assert_top_right(self, plot, legend):
        area = plot.mapFromScene(plot.getViewBox().sceneBoundingRect()).boundingRect()
        self.assertAlmostEqual(legend.x() + legend.width(), area.right() - 9, delta=2)
        self.assertAlmostEqual(legend.y(), area.top() + 10, delta=1)
        self.assertIs(legend.parentWidget(), plot.viewport())
        self.assertTrue(legend.isVisible())

    def test_legend_stays_top_right_through_zoom_resize_and_uncertainty(self):
        import pyqtgraph as pg
        plot, legend = self.make_plot()
        lo = plot.plot([-10, 10], [1, 1], name='Combined')
        hi = plot.plot([-10, 10], [100, 100])
        plot.addItem(pg.FillBetweenItem(lo, hi, brush=(0, 0, 0, 30)))
        plot.setLogMode(y=True)
        plot.setRange(xRange=(-10, 10), yRange=(0, 2), padding=0)
        self.settle(legend); self.assert_top_right(plot, legend)
        plot.setRange(xRange=(20, 40), yRange=(1, 2), padding=0)
        self.settle(legend); self.assert_top_right(plot, legend)
        plot.window().resize(600, 400)
        self.settle(legend); self.assert_top_right(plot, legend)
        for i in range(30): plot.plot([0, 1], [i, i], name=f'Sample {i}')
        self.settle(legend); self.assert_top_right(plot, legend)
        self.assertLess(legend.height(), plot.height())
        plot.clear(); self.settle(legend)
        self.assertTrue(legend.isHidden())


class InpAxisTests(unittest.TestCase):
    def test_fit_axes_stops_at_zero_even_with_warm_recording_frames(self):
        from icescopy_inptk_plot import axis_limits
        for quantity in ('Number frozen', 'Fraction frozen', 'Concentration'):
            x, _ = axis_limits(quantity, [-30., -15., 0., 20.], [0., 1.])
            self.assertLess(x[0], -30.)
            self.assertEqual(x[1], 0.)

    def test_limits_are_finite_for_zero_single_point_and_unbounded_data(self):
        import math
        from icescopy_inptk_plot import axis_limits
        for quantity in ('Number frozen', 'Fraction frozen', 'Concentration'):
            for log in (False, True):
                for values in ([0.], [float('inf'), float('nan')], [1e-12, 1e12]):
                    with self.subTest(quantity=quantity, log=log, values=values):
                        x, y = axis_limits(quantity, [-10.], values, [96.], logarithmic=log)
                        self.assertTrue(all(math.isfinite(v) for v in (*x, *y)))
                        self.assertLess(x[0], -10); self.assertGreater(x[1], -10)
                        self.assertLess(y[0], y[1])
