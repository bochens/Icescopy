"""Client checks; optional real-CLI integration via INPTK_TEST_EXECUTABLE."""
import copy
import json
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
from PySide6.QtGui import QUndoCommand
from icescopy_inptk_state import cli_choices, concentration_curves, new_settings, reconcile_inputs
from icescopy_session_io import build_session_payload, build_restore_state, load_session_bundle, save_session_bundle
from icescopy_temperature_import import CSU_COUNT_SOURCE_IMAGES
from icescopy_inptk_client import InptkClient
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


class InpProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_wrong_version_or_response_id_stops_the_client(self):
        for reply in ({"id": 1, "protocol_version": 1, "saved_format_version": 4},
                      {"id": 2, "protocol_version": 2, "saved_format_version": 4}):
            with self.subTest(reply=reply):
                client = InptkClient(); errors = []; received = []
                client.failed.connect(errors.append)
                client.active = (1, [], received.append, None)
                with patch.object(client.process, 'readAllStandardOutput', return_value=(json.dumps(reply)+'\n').encode()):
                    client._read()
                self.assertTrue(errors)
                self.assertFalse(received)
                self.assertFalse(client.busy)

    def test_partial_response_waits_for_newline(self):
        client = InptkClient(); received = []
        client.active = (1, [], received.append, None)
        payload = json.dumps({"id":1,"status":"ok","protocol_version":2,"saved_format_version":4}).encode()
        for data in (payload[:20], payload[20:]):
            with patch.object(client.process, 'readAllStandardOutput', return_value=data): client._read()
            self.assertFalse(received)
        with patch.object(client.process, 'readAllStandardOutput', return_value=b'\n'): client._read()
        self.assertEqual(len(received),1)


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

    def test_real_cli_plots_history_ranges_export_and_session(self):
        keys = self.configure(); self.calculate()
        self.assertEqual(set(self.panel.result["tables"]),{"Combined","Neat","Combined / Sample_1"})
        self.panel.show_analysis()
        QApplication.processEvents()
        self.assertLess(self.panel.plot.viewRange()[0][1], -4)
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
        self.assertEqual(self.panel.ranges.item(1, 1).text(), "-7.5")
        self.panel.undo_stack.undo()
        self.assertEqual(self.panel.settings["ranges"], {})
        self.panel.ranges.item(0, 1).setText("-7")
        self.assertEqual(self.panel.range_items[keys[0]].getRegion(), (-7, -5))
        self.assertEqual(self.panel.range_items[keys[1]].getRegion(), (-8, -5))
        self.panel.curves.setCurrentRow(1, QItemSelectionModel.ClearAndSelect)
        self.assertEqual(set(self.panel.range_items), {keys[0]})
        self.assertTrue(self.panel.ranges.isRowHidden(1))
        self.panel.curves.setCurrentRow(0, QItemSelectionModel.ClearAndSelect)
        self.assertEqual(set(self.panel.range_items), set(keys[:2]))

    def test_dialog_history_is_independent_and_survives_close(self):
        self.configure(); self.calculate()
        original = self.panel.result
        self.panel.undo_stack.clear()
        self.window.undo_stack.push(QUndoCommand("Source edit"))
        self.window.undo_stack.undo()
        main_index = self.window.undo_stack.index()
        self.panel.show_analysis()
        self.assertEqual(self.panel.windowModality(), Qt.WindowModal)
        self.assertFalse(self.panel.undo_action.isEnabled())
        self.panel.change_option("method", "mle")
        self.assertTrue(self.panel.undo_action.isEnabled())
        self.assertEqual(self.window.undo_stack.index(), main_index)
        self.assertTrue(self.window.undo_stack.canRedo())
        self.panel.undo_action.trigger()
        self.assertEqual(self.panel.settings["method"], "average")
        self.assertFalse(self.panel.undo_action.isEnabled())
        self.panel.reject()
        self.assertIs(self.panel.result, original)
        self.panel.show_analysis()
        self.assertTrue(self.panel.redo_action.isEnabled())
        self.panel.redo_action.trigger()
        self.assertEqual(self.panel.settings["method"], "mle")
        self.assertEqual(self.window.undo_stack.index(), main_index)
        self.assertTrue(self.window.undo_stack.canRedo())
        self.panel.reject()
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
        self.panel.reject()
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

    def test_switching_quantity_refits_axes_including_uncertainty(self):
        import numpy as np
        import pyqtgraph as pg
        self.configure(); self.calculate()
        p = self.panel
        p.show_uncertainty.setChecked(True)
        self.assertTrue(p.log_y.isChecked())
        p.log_y.setChecked(False)
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
        p.log_y.setChecked(True)
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
        self.assertIn('fit step', p.status.text())
        self.assertIn('fit step', p.empty_plot.text())
        self.assertIsNone(p.result)
        p.change_option('fit_step', '1')
        self.calculate()
        self.assertEqual(p.empty_plot.text(), '')

    def test_zero_and_nonfinite_concentrations_have_explicit_display_state(self):
        self.configure(); self.calculate()
        p = self.panel
        p.curves.setCurrentRow(1, QItemSelectionModel.ClearAndSelect)
        p.log_y.setChecked(False)
        rows = p.result['tables']['Neat']['cumulative']['rows']
        for row in rows:
            row.update(concentration=0., lower_error=0., upper_error={'$nonfinite': 'inf'})
        p.draw()
        self.assertEqual(p.visible_points, 4)
        p.log_y.setChecked(True)
        self.assertEqual(p.visible_points, 0)
        self.assertIn('No positive', p.empty_plot.text())
        p.log_y.setChecked(False)
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
        p.source_cache = None
        with patch.object(module, 'build_freeze_count_timeseries_csv_text', wraps=module.build_freeze_count_timeseries_csv_text) as serialize:
            p.current_hash()
            for i in range(3): p.curves.item(0).setText(f'Renamed {i}')
            self.assertEqual(serialize.call_count, 1)
        self.assertFalse(hasattr(p, 'views'))
        with patch.object(p.plot, 'clear', wraps=p.plot.clear) as clear:
            p.draw(); p.draw()
            self.assertEqual(clear.call_count, 0)
        p.source_changed()
        with patch.object(module, 'build_freeze_count_timeseries_csv_text', wraps=module.build_freeze_count_timeseries_csv_text) as serialize:
            p.current_hash()
            self.assertEqual(serialize.call_count, 1)

    def test_full_range_uses_measured_placeholders_and_undo_restores_limits(self):
        p = self.panel
        p.inputs.item(1, 0).setCheckState(Qt.Checked)
        p.tabs.setCurrentIndex(1)
        keys = p.selected_input_ids()
        self.assertEqual(len(keys), 2)
        self.assertFalse(p.settings['ranges'])
        self.assertEqual(p.ranges.item(0, 1).text(), '')
        self.assertEqual(p.ranges.item(0, 1).data(Qt.UserRole), '-8')
        self.assertEqual(p.ranges.item(0, 2).data(Qt.UserRole), '-5')
        p.ranges.item(0, 1).setText('-7')
        p.ranges.item(1, 2).setText('-6')
        before = copy.deepcopy(p.settings['ranges'])
        p.full_range.click()
        self.assertFalse(p.settings['ranges'])
        self.assertEqual(p.range_items[keys[0]].getRegion(), (-8., -5.))
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
        self.assertIn('will not be corrected', p.blank_help.text())
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
        self.assertEqual(p.ranges.item(0, 1).data(Qt.UserRole), '-8')
        p.change_input_cycle(key, 'later')
        self.assertEqual(p.ranges.item(0, 1).data(Qt.UserRole), '-20')
        self.assertFalse(p.settings['ranges'])

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
        for table in p.result['tables'].values():
            self.assertEqual([r['temperature_C'] for r in table['cumulative']['rows']],
                             [-5., -5.5, -6., -6.5, -7., -7.5, -8.])
        p.change_option('grid_step', '')
        saved = p.session_state()
        p.restore_session(saved)
        self.assertEqual(p.settings['grid_step'], '')  # Explicit saved settings survive the new default.

    def test_uncertainty_toggle_changes_only_display(self):
        import pyqtgraph as pg
        self.configure(); self.calculate()
        p = self.panel
        original = copy.deepcopy(p.result)
        key, undo_index = p.calculation_key(), p.undo_stack.index()
        self.assertFalse(p.show_uncertainty.isChecked())
        curve_top = p.plot_limits[1][1]
        self.assertFalse(any(isinstance(item, pg.FillBetweenItem) for item in p.plot.getPlotItem().items))
        p.show_uncertainty.setChecked(True)
        self.assertGreater(p.plot_limits[1][1], curve_top)
        self.assertTrue(any(isinstance(item, pg.FillBetweenItem) for item in p.plot.getPlotItem().items))
        self.assertEqual(p.result, original)
        self.assertEqual(p.calculation_key(), key)
        self.assertEqual(p.undo_stack.index(), undo_index)
        p.show_uncertainty.setChecked(False)
        self.assertEqual(p.plot_limits[1][1], curve_top)

    def test_full_individual_fits_preserve_combined_results_and_reuse_cached_references(self):
        keys = self.configure()
        p = self.panel
        state = copy.deepcopy(p.settings)
        state['ranges'] = {keys[1]: {'min_C': -7, 'max_C': -5}}
        p.commit(state, 'Restrict one dilution')
        # Compare against a real toolkit calculation without extra outputs.
        source = self.fixture.root / 'baseline.csv'
        source.write_text(p.source_text())
        output = self.fixture.root / 'baseline.inptk'
        responses = []
        p.client.request(['analyze', str(source), '--format', 'icescopy', *cli_choices(p.settings),
                          '--out', str(output)], responses.append)
        self.wait(lambda: responses and not p.client.busy)
        baseline = json.loads((output / 'analysis.json').read_text())
        with patch.object(p.client, 'request', wraps=p.client.request) as requests:
            self.calculate()
            self.assertEqual([c.args[0][0] for c in requests.call_args_list], ['analyze', 'analyze'])
            p.recalculate()
            self.assertEqual(requests.call_count, 2)  # No work when nothing changed.
        tables = dict(p.concentration_tables('cumulative'))
        self.assertEqual(set(tables), {'Combined', ('individual', keys[0]), ('individual', keys[1])})
        for name in ('Combined', 'Neat'):
            self.assertEqual(p.result['tables'][name]['cumulative']['rows'], baseline['curves'][name]['tables']['cumulative']['rows'])
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
            p.export_csv(reference_key=keys[1])
        self.wait(lambda:not p.operation and not p.client.busy)
        import csv
        with csv_path.open() as handle: exported = list(csv.DictReader(handle))
        expected = p.result['references']['tables'][keys[1]]['cumulative']['rows']
        self.assertEqual([float(r['concentration']) for r in exported], [r['concentration'] for r in expected])

    def test_range_edits_reuse_full_range_fits_and_report_history_is_lightweight(self):
        keys = self.configure(); self.calculate()
        p = self.panel
        reference = p.result['references']
        with patch.object(p.client, 'request', wraps=p.client.request) as requests:
            p.settings['ranges'][keys[1]] = {'min_C': -7, 'max_C': -6}
            self.calculate()
            self.assertEqual(len(requests.call_args_list), 1)
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
        report_path = self.fixture.root / 'range-suggestions.json'
        with patch('icescopy_inptk_panel.QFileDialog.getSaveFileName', return_value=(str(report_path), '')):
            p.export_range_report()
        self.assertEqual(json.loads(report_path.read_text()), report)

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



class InpAxisTests(unittest.TestCase):
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
