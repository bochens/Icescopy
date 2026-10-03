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
from icescopy_inptk_state import cli_choices, new_settings, reconcile_inputs
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
        self.panel.commit(state,"Configure INP analysis")
        return keys

    def calculate(self):
        self.panel.recalculate()
        self.wait(lambda: not self.panel.operation and not self.panel.client.busy)
        self.assertIsNotNone(self.panel.result,self.panel.status.text())
        self.assertIn("up to date",self.panel.status.text())

    def test_real_cli_plots_history_ranges_export_and_session(self):
        keys = self.configure(); self.calculate()
        self.assertEqual(set(self.panel.result["tables"]),{"Combined","Neat"})
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
        self.assertLess(first.span[1], second.span[0])
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

    def test_one_selection_controls_plot_table_and_ranges(self):
        keys = self.configure(); self.calculate()
        p = self.panel
        p.tabs.setCurrentIndex(1)
        p.curves.setCurrentRow(1, QItemSelectionModel.ClearAndSelect)
        self.assertEqual(p.selected_curve_names(), ['Neat'])
        self.assertEqual(set(p.range_items), {keys[0]})
        self.assertEqual([name for name, _ in p.selected_result_tables('cumulative')], ['Neat'])
        self.assertEqual({r['measurement_id'] for r in p.observation_rows()}, {keys[0]})
        p.views.setCurrentIndex(1)
        p.table_kind.setCurrentText('Observations')
        self.assertEqual(p.table_model.rowCount(), 4)
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
        rows = p.result['tables']['Combined']['cumulative']['rows']
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

    def test_edit_does_not_reserialize_csv_or_populate_hidden_result_table(self):
        import icescopy_inptk_panel as module
        p = self.panel
        p.source_cache = None
        with patch.object(module, 'build_freeze_count_timeseries_csv_text', wraps=module.build_freeze_count_timeseries_csv_text) as serialize:
            p.current_hash()
            for i in range(3): p.curves.item(0).setText(f'Renamed {i}')
            self.assertEqual(serialize.call_count, 1)
        self.assertEqual(p.table_model.rowCount(), 0)
        p.views.setCurrentIndex(1)
        self.assertEqual(p.table_model.rowCount(), 4)
        p.source_changed()
        with patch.object(module, 'build_freeze_count_timeseries_csv_text', wraps=module.build_freeze_count_timeseries_csv_text) as serialize:
            p.current_hash()
            self.assertEqual(serialize.call_count, 1)


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
