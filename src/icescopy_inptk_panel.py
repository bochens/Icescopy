"""Modal INP analysis workspace. All calculations run in the external CLI."""
import copy
import hashlib
import json
import math
import shutil
from pathlib import Path
import tempfile
import uuid

import numpy as np
import pyqtgraph as pg
from shiboken6 import isValid
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget,
)

from icescopy_inptk_client import InptkClient
from icescopy_inptk_state import cli_choices, fingerprint, new_settings, number, reconcile_inputs
from icescopy_plot import GrayscalePlotWidget
from icescopy_session_io import build_freeze_count_timeseries_csv_text


class ChoiceMenu(QPushButton):
    changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.choices = QMenu(self)
        self.setMenu(self.choices)

    def populate(self, names, selected):
        self.choices.clear()
        for name in names:
            action = self.choices.addAction(name)
            action.setCheckable(True)
            action.setChecked(name in selected)
            action.triggered.connect(self._changed)
        self.setText(f"{len(selected)} selected — choose…" if selected else "Choose…")
        self.setToolTip(", ".join(selected) or "No inputs selected")

    def _changed(self):
        self.changed.emit([a.text() for a in self.choices.actions() if a.isChecked()])


class InpSettingsCommand(QUndoCommand):
    def __init__(self, panel, text, before, after):
        super().__init__(text)
        self.panel, self.before, self.after = panel, before, after
        self.first = True

    def undo(self):
        self.panel.restore_choices(self.before)

    def redo(self):
        if self.first:
            self.first = False
        else:
            self.panel.restore_choices(self.after)


class InptkPreferencesWidget(QWidget):
    def __init__(self, path="", parent=None):
        super().__init__(parent)
        self.client = InptkClient(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.path = QLineEdit(path)
        self.path.setPlaceholderText("Choose the separately installed inptk executable")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.browse)
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        self.test = QPushButton("Test connection")
        self.test.clicked.connect(lambda: self.client.connect_executable(self.path.text().strip()))
        layout.addWidget(self.test, alignment=Qt.AlignLeft)
        self.status = QLabel("INP toolkit runs separately and is not included with Icescopy.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.client.ready.connect(self.connected)
        self.client.failed.connect(self.status.setText)
        self.client.busyChanged.connect(lambda busy: self.test.setEnabled(not busy))

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose INP toolkit executable", self.path.text())
        if path:
            self.path.setText(path)
            self.status.setText("Not tested. Test connection, then Save.")

    def connected(self, reply):
        self.status.setText(f"Connected: INP toolkit {reply['toolkit_version']} · CLI protocol 2 · saved format 4")
        self.client.stop()


class InptkPanel(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.setWindowTitle("INP Analysis")
        self.setWindowModality(Qt.WindowModal)
        self.setSizeGripEnabled(True)
        self.resize(1150, 760)
        self.window = window
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(window.undo_limit)
        self.client = InptkClient(self)
        self.client.ready.connect(self.connected)
        self.client.failed.connect(self.error)
        self.client.diagnostic.connect(lambda text: self.window.log(f"INP toolkit: {text}"))
        self.client.busyChanged.connect(self.update_status)
        self.cache = tempfile.TemporaryDirectory(prefix="icescopy-inptk-")
        self.settings = new_settings()
        self.preview = None
        self.preview_hash = ""
        self.result = None
        self.loading = False
        self.operation = False
        self.generation = 0
        self.range_items = {}
        self.input_ids = []
        self.range_ids = []
        self.make_ui()
        self.undo_action = QAction("Undo", self)
        self.redo_action = QAction("Redo", self)
        for action, key, callback in ((self.undo_action, QKeySequence.Undo, self.undo_stack.undo),
                                      (self.redo_action, QKeySequence.Redo, self.undo_stack.redo)):
            action.setShortcuts(QKeySequence.keyBindings(key))
            action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            action.triggered.connect(callback)
            self.addAction(action)
        for button, action in ((self.undo_button, self.undo_action), (self.redo_button, self.redo_action)):
            button.clicked.connect(action.trigger)
            action.changed.connect(lambda button=button, action=action: button.setEnabled(action.isEnabled()))
        self.undo_stack.indexChanged.connect(self.update_history_actions)
        self.update_history_actions()

    def update_history_actions(self, *_):
        stack = self.undo_stack
        if not isValid(stack): return
        index = stack.index()
        for action, position in ((self.undo_action, index - 1), (self.redo_action, index)):
            command = stack.command(position) if 0 <= position < stack.count() else None
            enabled = command is not None
            action.setEnabled(enabled)
            action.setToolTip(command.text() if enabled else "No INP analysis change available")

    def show_analysis(self):
        self.update_history_actions()
        self.show()
        self.raise_()
        self.activateWindow()
        if self.client.capabilities and self.preview_hash != self.current_hash():
            self.refresh_preview()

    def done(self, result):
        if self.operation or self.client.busy:
            self.cancel_operation()
        super().done(result)

    def edit_metadata(self):
        self.reject()
        self.window.show_dock_widget(self.window.sample_catalog_dock)

    def make_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(12)
        top = QHBoxLayout()
        self.connection = QLabel("INP toolkit not connected")
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_toolkit)
        self.refresh_button = QPushButton("Refresh data")
        self.refresh_button.clicked.connect(self.refresh_preview)
        top.addWidget(self.connection, 1)
        self.undo_button = QPushButton("Undo")
        self.redo_button = QPushButton("Redo")
        top.addWidget(self.undo_button)
        top.addWidget(self.redo_button)
        top.addWidget(self.connect_button)
        top.addWidget(self.refresh_button)
        outer.addLayout(top)
        splitter = QSplitter(Qt.Horizontal)
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(410)
        splitter.addWidget(self.tabs)
        samples = QWidget()
        layout = QVBoxLayout(samples)
        help_text = QLabel("Give dilutions of one sample the same group. Mark blank inputs, then assign them below.")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.inputs = QTableWidget(0, 4)
        self.inputs.setHorizontalHeaderLabels(["Input", "Sample group", "Cycle", "Blank"])
        self.inputs.verticalHeader().hide()
        self.inputs.setShowGrid(False)
        self.inputs.setAlternatingRowColors(True)
        self.inputs.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.inputs.setSelectionMode(QAbstractItemView.SingleSelection)
        self.inputs.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.inputs.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.inputs.itemChanged.connect(self.input_changed)
        self.inputs.itemSelectionChanged.connect(self.select_input)
        layout.addWidget(self.inputs, 2)
        self.blank_label = QLabel("Blanks for selected input")
        layout.addWidget(self.blank_label)
        self.blank_choice = ChoiceMenu()
        self.blank_choice.changed.connect(self.change_blanks)
        layout.addWidget(self.blank_choice)
        self.blank_enabled = QCheckBox("Apply blank correction")
        self.blank_enabled.toggled.connect(lambda value: self.change_option("blank_correction", value))
        layout.addWidget(self.blank_enabled)
        catalog = QPushButton("Edit sample metadata…")
        catalog.setToolTip("Close this window to edit physical metadata. Your INP analysis is retained.")
        catalog.clicked.connect(self.edit_metadata)
        layout.addWidget(catalog)
        layout.addWidget(QLabel("Output curves"))
        self.curves = QListWidget()
        self.curves.setToolTip("Double-click a curve to rename it.")
        self.curves.setMaximumHeight(120)
        self.curves.currentRowChanged.connect(self.select_curve)
        self.curves.itemChanged.connect(self.rename_curve)
        layout.addWidget(self.curves)
        row = QHBoxLayout()
        for label, callback in (("Add input", lambda: self.add_curve(False)),
                                ("Add group", lambda: self.add_curve(True)), ("Remove", self.remove_curve)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.curve_inputs = ChoiceMenu()
        self.curve_inputs.changed.connect(self.change_curve_inputs)
        layout.addWidget(self.curve_inputs)
        layout.addStretch(1)
        self.add_control_tab(samples, "Samples && blanks")

        combine = QWidget()
        layout = QVBoxLayout(combine)
        form = QFormLayout()
        self.limit_curve = QComboBox()
        self.limit_curve.currentIndexChanged.connect(self.curves.setCurrentRow)
        form.addRow("Output curve", self.limit_curve)
        self.method = QComboBox()
        self.method.addItem("MLE", "mle")
        self.method.setToolTip("Maximum likelihood estimation: jointly fit the sample and blank freezing counts.")
        self.method.addItem("Average", "average")
        self.method.currentIndexChanged.connect(lambda: self.change_option("method", self.method.currentData()))
        form.addRow("Method", self.method)
        self.fit_step = self.option_edit("fit_step", "Automatic")
        form.addRow("MLE fit spacing (°C)", self.fit_step)
        self.combine_form = form
        self.basis = QComboBox()
        for text, key in (("Suspension", "suspension"), ("Sampled air", "sampled_air"), ("Dry soil", "dry_soil")):
            self.basis.addItem(text, key)
        self.basis.currentIndexChanged.connect(lambda: self.change_option("basis", self.basis.currentData()))
        form.addRow("Concentration basis", self.basis)
        layout.addLayout(form)
        label = QLabel("Each input has its own colored limits on the plot. Drag a pair or type temperatures below. Empty limits are unrestricted.")
        label.setToolTip("Both endpoints are included. Limits apply to every output curve using this input.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.ranges = QTableWidget(0, 3)
        self.ranges.setHorizontalHeaderLabels(["Input", "Cold (°C)", "Warm (°C)"])
        self.ranges.verticalHeader().hide()
        self.ranges.setShowGrid(False)
        self.ranges.setAlternatingRowColors(True)
        self.ranges.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.ranges.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.ranges.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ranges.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ranges.itemChanged.connect(self.range_changed)
        self.ranges.itemSelectionChanged.connect(self.draw_ranges)
        layout.addWidget(self.ranges, 1)
        row = QHBoxLayout()
        self.min_frozen = QSpinBox()
        self.min_unfrozen = QSpinBox()
        for widget, key in ((self.min_frozen, "min_frozen"), (self.min_unfrozen, "min_unfrozen")):
            widget.setRange(0, 100000)
            widget.setValue(3)
            widget.valueChanged.connect(lambda value, key=key: self.change_option(key, value))
        row.addWidget(QLabel("Min. frozen")); row.addWidget(self.min_frozen)
        row.addWidget(QLabel("Min. unfrozen")); row.addWidget(self.min_unfrozen)
        layout.addLayout(row)
        self.suggest = QPushButton("Suggest limits")
        self.suggest.setToolTip("Suggest Average limits for the selected output curve.")
        self.suggest.clicked.connect(self.suggest_ranges)
        layout.addWidget(self.suggest)
        self.suggestion_status = QLabel("Automatic limits are available for Average; MLE limits are manual.")
        self.suggestion_status.setWordWrap(True)
        layout.addWidget(self.suggestion_status)
        layout.addStretch(1)
        self.add_control_tab(combine, "Combine dilutions")

        advanced = QWidget()
        form = QFormLayout(advanced)
        self.grid_step = self.option_edit("grid_step", "Off")
        self.grid_start = self.option_edit("grid_start", "Measured warm limit")
        self.grid_end = self.option_edit("grid_end", "Measured cold limit")
        self.grid_window = self.option_edit("grid_window", "Required for centered window")
        self.grid_method = QComboBox()
        for name, key in (("Latest warmer", "latest"), ("Maximum warmer fraction", "max"), ("Centered window", "window")):
            self.grid_method.addItem(name, key)
        self.grid_method.currentIndexChanged.connect(lambda: self.change_option("grid_method", self.grid_method.currentData()))
        form.addRow("Count-selection step (°C)", self.grid_step)
        form.addRow("Warm grid endpoint (°C)", self.grid_start)
        form.addRow("Cold grid endpoint (°C)", self.grid_end)
        form.addRow("Count selection", self.grid_method)
        form.addRow("Full window width (°C)", self.grid_window)
        self.decrease_policy = QComboBox()
        self.decrease_policy.addItem("Stop at first decrease", "stop_at_decrease")
        self.decrease_policy.addItem("Skip decreases", "skip_decreases")
        self.decrease_policy.currentIndexChanged.connect(lambda: self.change_option("decrease_policy", self.decrease_policy.currentData()))
        form.addRow("Decreasing concentrations", self.decrease_policy)
        self.z = self.option_edit("z", "1.96")
        form.addRow("Uncertainty z (1.96 ≈ 95%)", self.z)
        note = QLabel("The optional grid selects counts before calculation. It does not interpolate the final curve. Scientific checks and calculations are performed by INP toolkit.")
        note.setWordWrap(True)
        form.addRow(note)
        self.add_control_tab(advanced, "Advanced")

        view = QWidget()
        layout = QVBoxLayout(view)
        controls = QHBoxLayout()
        self.quantity = QComboBox()
        self.quantity.addItems(["Number frozen", "Fraction frozen", "Concentration"])
        self.quantity.setCurrentIndex(1)
        self.quantity.currentIndexChanged.connect(self.draw)
        self.view_curve = QComboBox()
        self.view_curve.addItem("All curves")
        self.view_curve.currentIndexChanged.connect(self.draw)
        self.log_y = QCheckBox("Log Y")
        self.log_y.toggled.connect(self.draw)
        controls.addWidget(self.quantity)
        controls.addWidget(self.view_curve, 1)
        controls.addWidget(self.log_y)
        layout.addLayout(controls)
        self.views = QTabWidget()
        self.plot = pg.PlotWidget()
        self.plot.setBackground(None)
        self.plot.showGrid(x=True, y=True, alpha=.2)
        self.plot.setLabel("bottom", "Temperature", units="°C")
        self.plot.addLegend(offset=(8, 8))
        self.views.addTab(self.plot, "Plot")
        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        self.table_kind = QComboBox()
        self.table_kind.addItems(["Observations", "Concentration", "Excluded", "Range suggestions"])
        self.table_kind.currentIndexChanged.connect(self.draw_table)
        table_layout.addWidget(self.table_kind)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table_layout.addWidget(self.table)
        self.views.addTab(table_page, "Table")
        console = QTextEdit()
        console.setReadOnly(True)
        console.setDocument(self.window.terminal.document())
        self.views.addTab(console, "Console")
        layout.addWidget(self.views, 1)
        self.plot_note = QLabel()
        self.plot_note.setWordWrap(True)
        layout.addWidget(self.plot_note)
        splitter.addWidget(view)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 700])
        outer.addWidget(splitter, 1)
        bottom = QHBoxLayout()
        self.status = QLabel("Import temperatures and freezing counts, then connect INP toolkit.")
        self.status.setWordWrap(True)
        bottom.addWidget(self.status, 1)
        self.calculate = QPushButton("Recalculate")
        self.calculate.clicked.connect(self.recalculate)
        self.cancel = QPushButton("Cancel")
        self.cancel.clicked.connect(self.cancel_operation)
        self.export = QPushButton("Export")
        menu = QMenu(self.export)
        menu.addAction("Save INP toolkit result…", self.export_result)
        for label, kind in (("Frozen counts", "counts"), ("Frozen fractions", "frozen_fraction"),
                            ("Concentrations", "cumulative"), ("Excluded points", "excluded")):
            menu.addAction(f"Export calculated {label.lower()}…", lambda checked=False, kind=kind: self.export_csv(kind))
        self.export.setMenu(menu)
        for widget in (self.calculate, self.cancel, self.export): bottom.addWidget(widget)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        bottom.addWidget(close)
        # Enter commits a field; it must not accidentally run or close analysis.
        for button in self.findChildren(QPushButton): button.setAutoDefault(False)
        outer.addLayout(bottom)
        self.tabs.currentChanged.connect(self.draw_ranges)
        self.restore_choices(self.settings)

    def add_control_tab(self, widget, title):
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(widget)
        self.tabs.addTab(area, title)

    def option_edit(self, key, placeholder):
        widget = QLineEdit()
        widget.setPlaceholderText(placeholder)
        widget.editingFinished.connect(lambda: self.change_option(key, widget.text().strip()))
        return widget

    def color(self, key):
        colors = GrayscalePlotWidget.PALETTES.get(getattr(self.window, "timeseries_palette", "bright"), GrayscalePlotWidget.PALETTES["bright"])
        keys = self.input_ids
        index = keys.index(key) if key in keys else int(hashlib.sha256(key.encode()).hexdigest()[:6], 16)
        return QColor(*colors[index % len(colors)])

    def commit(self, choices, label):
        if self.loading or choices == self.settings:
            return
        before = copy.deepcopy(self.settings)
        self.restore_choices(choices)
        self.undo_stack.push(InpSettingsCommand(self, label, before, copy.deepcopy(choices)))
        self.window.log(label)

    def change_option(self, key, value):
        if self.loading: return
        state = copy.deepcopy(self.settings); state[key] = value
        self.commit(state, f"INP analysis: change {key.replace('_', ' ')} to {value}")

    def restore_choices(self, choices):
        self.loading = True
        self.settings = copy.deepcopy(choices)
        old_input = self.current_input()
        old_curve = self.curves.currentRow()
        old_range = self.ranges.currentRow()
        for key in ("fit_step", "grid_step", "grid_start", "grid_end", "grid_window", "z"):
            getattr(self, key).setText(str(self.settings[key]))
        for key in ("method", "basis", "grid_method", "decrease_policy"):
            widget = getattr(self, key); widget.setCurrentIndex(widget.findData(self.settings[key]))
        self.blank_enabled.setChecked(self.settings["blank_correction"])
        self.min_frozen.setValue(self.settings["min_frozen"])
        self.min_unfrozen.setValue(self.settings["min_unfrozen"])
        self.combine_form.setRowVisible(self.fit_step, self.settings["method"] == "mle")
        self.grid_window.setEnabled(bool(self.settings["grid_step"]) and self.settings["grid_method"] == "window")
        for widget in (self.grid_start, self.grid_end, self.grid_method): widget.setEnabled(bool(self.settings["grid_step"]))
        measurements = {r["measurement_id"]: r for r in (self.preview or {}).get("measurements", [])}
        self.input_ids = list(self.settings["inputs"])
        for row in range(self.inputs.rowCount()):
            previous_cycle = self.inputs.cellWidget(row, 2)
            if previous_cycle: previous_cycle.hide()
        self.inputs.setRowCount(0)
        self.inputs.setRowCount(len(self.input_ids))
        for row, key in enumerate(self.input_ids):
            values = self.settings["inputs"][key]
            item = QTableWidgetItem(key); item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setData(Qt.DecorationRole, self.color(key)); self.inputs.setItem(row, 0, item)
            self.inputs.setItem(row, 1, QTableWidgetItem(values["group"]))
            cycles = measurements.get(key, {}).get("cycle_ids", [values["cycle"]])
            if len(cycles) == 1:
                item = QTableWidgetItem(str(cycles[0])); item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.inputs.setItem(row, 2, item)
            else:
                cycle = QComboBox(); cycle.addItem("Choose…", "")
                for value in cycles:
                    if str(value): cycle.addItem(str(value), str(value))
                cycle.setCurrentIndex(max(0, cycle.findData(values["cycle"])))
                cycle.currentIndexChanged.connect(lambda _i, key=key, widget=cycle: self.change_input_cycle(key, widget.currentData()))
                self.inputs.setCellWidget(row, 2, cycle)
            blank = QTableWidgetItem(); blank.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            blank.setCheckState(Qt.Checked if values["blank"] else Qt.Unchecked)
            self.inputs.setItem(row, 3, blank)
        self.inputs.setMaximumHeight(min(240, max(110, 36 + 30 * len(self.input_ids))))
        if self.input_ids: self.inputs.selectRow(self.input_ids.index(old_input) if old_input in self.input_ids else 0)
        self.curves.clear()
        for curve in self.settings["curves"]:
            item = QListWidgetItem(curve["name"]); item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.curves.addItem(item)
        if self.curves.count(): self.curves.setCurrentRow(max(0, min(old_curve, self.curves.count()-1)))
        self.limit_curve.blockSignals(True)
        self.limit_curve.clear()
        self.limit_curve.addItems([curve["name"] for curve in self.settings["curves"]])
        self.limit_curve.setCurrentIndex(self.curves.currentRow())
        self.limit_curve.blockSignals(False)
        view_name = self.view_curve.currentText()
        self.view_curve.blockSignals(True); self.view_curve.clear(); self.view_curve.addItem("All curves")
        for curve in (self.result or {}).get("reply", {}).get("curves", self.settings_curve_dict()): self.view_curve.addItem(curve)
        self.view_curve.setCurrentIndex(max(0, self.view_curve.findText(view_name))); self.view_curve.blockSignals(False)
        self.range_ids = [key for key, value in self.settings["inputs"].items() if not value["blank"]]
        self.ranges.setRowCount(len(self.range_ids))
        self.ranges.setMaximumHeight(min(240, max(110, 36 + 30 * len(self.range_ids))))
        for row, key in enumerate(self.range_ids):
            item = QTableWidgetItem(key); item.setFlags(item.flags() & ~Qt.ItemIsEditable); item.setData(Qt.DecorationRole, self.color(key))
            self.ranges.setItem(row, 0, item)
            for col, limit in ((1, "min_C"), (2, "max_C")):
                self.ranges.setItem(row, col, QTableWidgetItem(str(self.settings["ranges"].get(key, {}).get(limit, ""))))
        if self.range_ids: self.ranges.selectRow(max(0, min(old_range, len(self.range_ids)-1)))
        self.loading = False
        if self.settings.get("suggestion"):
            self.show_suggestion(self.settings["suggestion"], log=False)
        else:
            self.suggestion_status.setText("Automatic limits are available for Average; MLE limits are manual.")
        self.select_input(); self.select_curve(); self.draw(); self.update_status()

    def settings_curve_dict(self):
        return {curve["name"]: curve for curve in self.settings["curves"]}

    def current_input(self):
        row = self.inputs.currentRow()
        return self.input_ids[row] if 0 <= row < len(self.input_ids) else None

    def select_input(self):
        if self.loading: return
        key = self.current_input()
        if not key: return
        value = self.settings["inputs"][key]
        self.blank_label.setText(f"Blanks for {key}")
        self.blank_choice.populate([k for k, v in self.settings["inputs"].items() if v["blank"] and k != key], value["blanks"])
        self.blank_choice.setEnabled(not value["blank"])
        if key in self.range_ids: self.ranges.selectRow(self.range_ids.index(key))

    def input_changed(self, item):
        if self.loading: return
        key = self.input_ids[item.row()]; state = copy.deepcopy(self.settings)
        if item.column() == 1: state["inputs"][key]["group"] = item.text().strip()
        elif item.column() == 3:
            state["inputs"][key]["blank"] = item.checkState() == Qt.Checked
            if state["inputs"][key]["blank"]:
                for curve in state["curves"]: curve["inputs"] = [k for k in curve["inputs"] if k != key]
                state["curves"] = [c for c in state["curves"] if c["inputs"]]
        else: return
        self.commit(state, f"INP analysis: update input {key}")

    def change_input_cycle(self, key, cycle):
        if self.loading: return
        state = copy.deepcopy(self.settings); state["inputs"][key]["cycle"] = cycle
        self.commit(state, f"INP analysis: select cycle {cycle} for {key}")

    def change_blanks(self, values):
        key = self.current_input()
        if not key: return
        state = copy.deepcopy(self.settings); state["inputs"][key]["blanks"] = values
        self.commit(state, f"INP analysis: assign blanks for {key}")

    def select_curve(self):
        if self.loading: return
        row = self.curves.currentRow()
        self.limit_curve.blockSignals(True)
        self.limit_curve.setCurrentIndex(row)
        self.limit_curve.blockSignals(False)
        values = self.settings["curves"][row]["inputs"] if row >= 0 else []
        self.curve_inputs.populate([k for k, v in self.settings["inputs"].items() if not v["blank"]], values)
        self.curve_inputs.setEnabled(row >= 0)
        self.draw_ranges()

    def add_curve(self, group):
        key = self.current_input()
        if not key or self.settings["inputs"][key]["blank"]: return
        state = copy.deepcopy(self.settings)
        name = state["inputs"][key]["group"] if group else key
        keys = [k for k, v in state["inputs"].items() if not v["blank"] and v["group"] == name] if group else [key]
        existing = {c["name"] for c in state["curves"]}; base = name; suffix = 2
        while name in existing: name = f"{base} ({suffix})"; suffix += 1
        state["curves"].append({"name": name, "inputs": keys})
        self.commit(state, f"INP analysis: add curve {name}")
        self.curves.setCurrentRow(self.curves.count()-1)

    def remove_curve(self):
        row = self.curves.currentRow()
        if row < 0: return
        state = copy.deepcopy(self.settings); state["curves"].pop(row)
        self.commit(state, "INP analysis: remove output curve")

    def rename_curve(self, item):
        if self.loading: return
        state = copy.deepcopy(self.settings); state["curves"][self.curves.row(item)]["name"] = item.text().strip()
        self.commit(state, "INP analysis: rename output curve")

    def change_curve_inputs(self, values):
        row = self.curves.currentRow()
        if row < 0: return
        state = copy.deepcopy(self.settings); state["curves"][row]["inputs"] = values
        self.commit(state, "INP analysis: change curve inputs")

    def range_changed(self, item):
        if self.loading or item.column() == 0: return
        key = self.range_ids[item.row()]; state = copy.deepcopy(self.settings)
        limits = state["ranges"].setdefault(key, {})
        boundary = "min_C" if item.column() == 1 else "max_C"
        try:
            if item.text().strip():
                value = float(item.text())
                if not math.isfinite(value): raise ValueError("Use a finite temperature.")
                limits[boundary] = value
            else: limits.pop(boundary, None)
            if limits.get("min_C", -math.inf) > limits.get("max_C", math.inf):
                raise ValueError("Cold limit must not exceed warm limit.")
        except ValueError as exc:
            self.restore_choices(self.settings); self.error(str(exc)); return
        self.commit(state, f"INP analysis: change temperature limits for {key}")

    def draw_ranges(self):
        if self.loading: return
        for region in self.range_items.values(): self.plot.removeItem(region)
        self.range_items.clear()
        curve_row = self.curves.currentRow()
        keys = self.settings["curves"][curve_row]["inputs"] if curve_row >= 0 else []
        keys = [key for key in keys if key in self.range_ids]
        for row, key in enumerate(self.range_ids): self.ranges.setRowHidden(row, key not in keys)
        if self.tabs.currentIndex() != 1: return
        temperatures = {}
        for observation in (self.preview or {}).get("table", {}).get("rows", []):
            value = number(observation.get("temperature_C"))
            if math.isfinite(value): temperatures.setdefault(observation["measurement_id"], []).append(value)
        # Separate strips keep every pair reachable even when temperatures are
        # identical. Each signal carries its input ID, never the selected row.
        lane_height = min(.065, .4 / max(1, len(keys)))
        for index, key in enumerate(keys):
            values = temperatures.get(key, [])
            if not values: continue
            limits = self.settings["ranges"].get(key, {})
            color = self.color(key)
            brush = QColor(color); brush.setAlpha(40)
            start = .01 + index * lane_height
            region = pg.LinearRegionItem(
                [limits.get("min_C", min(values)), limits.get("max_C", max(values))],
                brush=brush, pen=pg.mkPen(color, width=1.5), swapMode="block",
                span=(start, start + lane_height * .8))
            region.setZValue(10)
            region.setToolTip(f"{key}: drag to move both temperature limits")
            for line, marker, boundary in zip(region.lines, ("|>", "<|"), ("Cold", "Warm")):
                line.addMarker(marker, .5, 12)
                line.setToolTip(f"{key} — {boundary} limit (°C)")
            region.sigRegionChanged.connect(lambda _region, key=key, region=region: self.range_dragged(key, region))
            region.sigRegionChangeFinished.connect(lambda _region, key=key, region=region: self.range_finished(key, region))
            self.range_items[key] = region
            self.plot.addItem(region, ignoreBounds=True)

    def range_dragged(self, key, region):
        if self.range_items.get(key) is not region: return
        self.loading = True
        try:
            cold, warm = region.getRegion()
            row = self.range_ids.index(key)
            self.ranges.selectRow(row)
            self.ranges.item(row, 1).setText(f"{cold:.4f}")
            self.ranges.item(row, 2).setText(f"{warm:.4f}")
        finally: self.loading = False

    def range_finished(self, key, region):
        if self.range_items.get(key) is not region: return
        cold, warm = region.getRegion()
        state = copy.deepcopy(self.settings); state["ranges"][key] = {"min_C": cold, "max_C": warm}
        self.commit(state, f"INP analysis: move temperature limits for {key}")

    def source_text(self):
        w = self.window
        if not w.freeze_count_timeseries_headers or not w.freeze_count_timeseries_rows:
            raise ValueError("Import temperatures and freezing counts before INP analysis.")
        if w.freeze_count_timeseries_summary.get("analysis_required"):
            raise ValueError("Freezing analysis is out of date. Run image analysis first.")
        return build_freeze_count_timeseries_csv_text(w.freeze_count_timeseries_headers, w.freeze_count_timeseries_rows,
            session_metadata=w.serialize_session_metadata(), summary=w.freeze_count_timeseries_summary)

    def current_hash(self):
        try: return hashlib.sha256(self.source_text().encode()).hexdigest()
        except ValueError: return ""

    def calculation_key(self):
        # Suggested limits affect calculation only once applied. Changing the
        # suggestion thresholds/report alone does not change a fitted result.
        choices = {k: v for k, v in self.settings.items()
                   if k not in {"suggestion", "min_frozen", "min_unfrozen"}}
        return fingerprint([self.current_hash(), choices])

    def connect_toolkit(self):
        self.client.connect_executable(getattr(self.window, "inptk_executable_path", ""))

    def connected(self, reply):
        self.connection.setText(f"INP toolkit {reply['toolkit_version']}")
        self.window.log(f"INP toolkit connected: {reply['toolkit_version']} (protocol 2)")
        self.refresh_preview()

    def refresh_preview(self, _checked=False, after=None):
        if self.operation or self.client.busy: return
        if not self.client.capabilities:
            self.error("Connect INP toolkit first. Choose its executable in Settings → INP toolkit."); return
        try: text = self.source_text()
        except ValueError as exc: self.error(str(exc)); return
        source_hash = hashlib.sha256(text.encode()).hexdigest()
        path = Path(self.cache.name) / f"counts-{uuid.uuid4().hex}.csv"
        path.write_text(text)
        self.operation = True; self.update_status()
        generation = self.generation
        def done(reply):
            path.unlink(missing_ok=True)
            self.operation = False
            if generation != self.generation or self.current_hash() != source_hash:
                self.update_status(); return
            self.preview, self.preview_hash = reply, source_hash
            state = reconcile_inputs(self.settings, reply)
            if not self.settings["inputs"] and not state["curves"]:
                state["curves"] = [{"name": key, "inputs": [key]} for key in state["inputs"]]
            self.restore_choices(state)
            missing = reply.get("suspension_metadata", {}).get("error")
            if missing: self.status.setText(f"Counts available. {missing}")
            self.window.log("INP analysis: counts and fractions updated.")
            if after: after()
        def failed(message):
            path.unlink(missing_ok=True); self.error(message)
        self.client.request(["preview", str(path), "--format", "icescopy"], done, failed)

    def recalculate(self):
        if self.operation or self.client.busy: return
        if self.preview_hash != self.current_hash() or not self.preview:
            self.refresh_preview(after=self.recalculate); return
        self.run_calculation(False)

    def suggest_ranges(self):
        if self.operation or self.client.busy: return
        if self.preview_hash != self.current_hash() or not self.preview:
            self.refresh_preview(after=self.suggest_ranges); return
        self.run_calculation(True)

    def run_calculation(self, suggest):
        if suggest and self.settings["method"] != "average": return
        row = self.curves.currentRow()
        selected = self.settings["curves"][row]["name"] if suggest and row >= 0 else None
        try:
            if suggest and selected is None: raise ValueError("Select an output curve for the suggestion.")
            args = cli_choices(self.settings, suggest=suggest, selected=selected)
            text = self.source_text()
        except (ValueError, TypeError) as exc: self.error(str(exc)); return
        def request_key():
            return fingerprint([self.current_hash(), self.settings]) if suggest else self.calculation_key()
        key, generation = request_key(), self.generation
        source = Path(self.cache.name) / f"counts-{uuid.uuid4().hex}.csv"
        output = Path(self.cache.name) / f"result-{uuid.uuid4().hex}.inptk"
        source.write_text(text)
        command = ["suggest-ranges" if suggest else "analyze", str(source), "--format", "icescopy", *args]
        if not suggest: command += ["--out", str(output)]
        self.operation = True; self.update_status()
        self.window.log("INP toolkit: suggesting Average limits…" if suggest else "INP toolkit: calculating concentrations…")
        def fresh(): return generation == self.generation and key == request_key()
        def cleanup():
            source.unlink(missing_ok=True)
            if output.exists(): shutil.rmtree(output)
        def failed(message): cleanup(); self.error(message)
        def done(reply):
            if not fresh():
                cleanup(); self.operation = False; self.update_status()
                self.window.log("INP toolkit: inputs changed; the previous result is retained."); return
            if suggest:
                state = copy.deepcopy(self.settings); state["suggestion"] = reply
                if reply.get("complete") and reply.get("temperature_ranges_C") is not None:
                    state["ranges"].update(reply["temperature_ranges_C"])
                self.operation = False
                self.commit(state, "INP analysis: apply Average range suggestions" if reply.get("complete") else "INP analysis: retain incomplete range suggestions")
                self.show_suggestion(reply); cleanup(); return
            pending = {"key": key, "reply": reply, "tables": {}, "choices": copy.deepcopy(self.settings),
                       "source_hash": self.current_hash(), "toolkit_version": reply["toolkit_version"]}
            names = [(name, kind) for name, curve in reply["curves"].items() for kind in curve["tables"]]
            def get_next():
                if not fresh():
                    cleanup(); self.operation = False; self.update_status(); return
                if not names:
                    # INP toolkit's native saved result is a directory containing
                    # analysis.json. Keep that exact document, without client math.
                    pending["saved_result"] = (output / "analysis.json").read_text(encoding="utf-8")
                    self.result = pending; self.operation = False
                    self.restore_choices(self.settings)
                    self.quantity.setCurrentIndex(2); self.table_kind.setCurrentText("Concentration")
                    self.window.log("INP analysis updated.")
                    cleanup(); return
                name, kind = names.pop(0)
                def table_received(response):
                    pending["tables"].setdefault(name, {})[kind] = response["table"]
                    get_next()
                self.client.request(["table", str(output), "--table", kind, "--curve", name], table_received, failed)
            get_next()
        self.client.request(command, done, failed)

    def show_suggestion(self, reply, *, log=True):
        lines = []
        for name, value in reply.get("inputs", {}).items():
            limits = value.get("range_C")
            lines.append(f"{name}: {limits or value.get('status')}; {value.get('kept_observations', 0)} retained. "
                         + ", ".join(value.get("cold_limit_reason", [])))
        title = "Limits applied; you can edit them." if reply.get("complete") else "Incomplete: no limits applied. Resolve the inputs below or adjust thresholds."
        self.suggestion_status.setText(title + "\n" + "\n".join(lines))
        if log: self.window.log("INP range suggestions: " + title)
        self.draw_table()

    def update_status(self, *_):
        if not hasattr(self, "calculate"): return
        busy = self.operation or self.client.busy
        connected = bool(self.client.capabilities)
        self.calculate.setEnabled(connected and not busy)
        self.refresh_button.setEnabled(connected and not busy)
        self.connect_button.setEnabled(not busy)
        self.cancel.setEnabled(busy)
        self.suggest.setEnabled(connected and not busy and self.settings["method"] == "average")
        self.export.setEnabled(bool(self.result) and not busy)
        if busy: message = "INP toolkit is working… You can cancel."
        elif self.result and self.result["key"] == self.calculation_key(): message = "Result is up to date."
        elif self.result: message = "Changes not calculated — showing the last successful result."
        elif self.preview: message = "Counts loaded. Set groups and blanks, then Recalculate."
        else: message = "Import temperatures and freezing counts, then connect INP toolkit."
        self.status.setText(message)
        if self.result:
            if self.quantity.currentText() == "Concentration":
                note = f"Calculated with INP toolkit {self.result['toolkit_version']}. " + ("" if self.result["key"] == self.calculation_key() else "Changes not calculated. ")
            else:
                note = "Original counts from the latest data refresh. "
                if self.preview_hash != self.current_hash(): note += "Source data changed; refresh required. "
            self.plot_note.setText(note + "Export uses the last calculated result.")

    def error(self, message):
        self.operation = False
        self.update_status()
        self.status.setText(str(message))
        if not self.client.capabilities: self.connection.setText("INP toolkit not connected")
        self.window.log(f"INP toolkit: {message}")

    def cancel_operation(self):
        self.generation += 1; self.client.stop(); self.operation = False
        for path in Path(self.cache.name).iterdir():
            if path.is_dir(): shutil.rmtree(path)
            else: path.unlink(missing_ok=True)
        self.error("Cancelled. The last successful result is retained. Connect to start again.")

    def source_changed(self):
        self.update_status()

    def selected_result_tables(self, kind):
        selected = self.view_curve.currentText()
        return [(name, tables[kind]) for name, tables in (self.result or {}).get("tables", {}).items()
                if kind in tables and (selected == "All curves" or name == selected)]

    def draw(self, *_):
        if self.loading: return
        self.plot.clear(); self.range_items.clear()
        legend = self.plot.getPlotItem().legend
        if legend: legend.clear()
        self.plot.setLogMode(x=False, y=self.log_y.isChecked())
        foreground = self.palette().color(self.foregroundRole())
        for side in ("left", "bottom"):
            self.plot.getAxis(side).setTextPen(foreground)
            self.plot.getAxis(side).setPen(foreground)
        if legend: legend.setLabelTextColor(foreground)
        quantity = self.quantity.currentText()
        self.plot.setLabel("left", quantity)
        groups = []
        if quantity == "Concentration":
            for name, table in self.selected_result_tables("cumulative"):
                groups.append((name, table["rows"], "concentration"))
        elif self.preview:
            by_input = {}
            for row in self.preview["table"]["rows"]:
                key = row["measurement_id"]
                chosen = self.settings["inputs"].get(key, {}).get("cycle", "")
                if chosen and str(row["cycle_id"]) != chosen: continue
                by_input.setdefault(f"{key} · cycle {row['cycle_id']}", []).append(row)
            selected = self.settings_curve_dict().get(self.view_curve.currentText())
            for name, rows in by_input.items():
                if selected and rows[0]["measurement_id"] not in selected["inputs"]: continue
                groups.append((name, rows, "n_frozen" if quantity == "Number frozen" else "fraction_frozen"))
        for name, rows, column in groups:
            color = self.color(rows[0].get("measurement_id", name)) if rows else self.color(name)
            chunks, chunk, previous = [], [], None
            for row in rows:
                segment = row.get("segment_id", "0")
                if chunk and segment != previous: chunks.append(chunk); chunk = []
                chunk.append(row); previous = segment
            if chunk: chunks.append(chunk)
            for i, chunk in enumerate(chunks):
                x = np.array([number(row.get("temperature_C")) for row in chunk])
                y = np.array([number(row.get(column)) for row in chunk])
                y[~np.isfinite(y)] = np.nan
                if self.log_y.isChecked(): y[y <= 0] = np.nan
                curve = self.plot.plot(x, y, pen=pg.mkPen(color, width=2), symbol="o", symbolSize=5,
                                      symbolBrush=color, name=name if i == 0 else None, connect="finite")
                curve.scatter.setData(x=x, y=y, data=chunk, hoverable=True,
                    tip=lambda x, y, data: f"Temperature: {data.get('temperature_C')} °C\n" + "\n".join(f"{k}: {v}" for k, v in data.items() if k in {"measurement_id", "n_total", "n_frozen", "fraction_frozen", "concentration", "lower_error", "upper_error", "contributor_count", "unit"}))
                if column == "concentration" and chunk:
                    unit = str(chunk[0].get("unit", ""))
                    unit = {"INP_per_mL_suspension": "INP/mL suspension", "INP_per_L_air": "INP/L air", "INP_per_g_soil": "INP/g soil"}.get(unit, unit)
                    self.plot.setLabel("left", "Concentration", units=unit)
                    lower = y - np.array([number(row.get("lower_error")) for row in chunk])
                    upper = y + np.array([number(row.get("upper_error")) for row in chunk])
                    lower[~np.isfinite(lower)] = np.nan; upper[~np.isfinite(upper)] = np.nan
                    if self.log_y.isChecked(): lower[lower <= 0] = np.nan
                    lo = self.plot.plot(x, lower, pen=None, connect="finite")
                    hi = self.plot.plot(x, upper, pen=None, connect="finite")
                    fill = QColor(color); fill.setAlpha(35)
                    self.plot.addItem(pg.FillBetweenItem(lo, hi, brush=fill), ignoreBounds=True)
        if quantity == "Concentration":
            for name, table in self.selected_result_tables("excluded"):
                rows = table["rows"]
                if not rows: continue
                points = self.plot.plot([number(r.get("temperature_C")) for r in rows], [number(r.get("concentration")) for r in rows],
                    pen=None, symbol="x", symbolSize=6, symbolPen=pg.mkPen(150, 150, 150, 110))
                points.scatter.setData(x=[number(r.get("temperature_C")) for r in rows],
                    y=[number(r.get("concentration")) for r in rows], data=rows, hoverable=True,
                    tip=lambda x, y, data: "Excluded point\n" + "\n".join(
                        f"{k}: {v}" for k, v in data.items()
                        if k in {"temperature_C", "concentration", "selection_status", "final_selection_status", "qc_flag"}))
        self.draw_ranges(); self.draw_table(); self.update_status()

    def draw_table(self, *_):
        if self.loading: return
        kind = self.table_kind.currentText()
        if kind == "Observations": tables = [("", (self.preview or {}).get("table", {}))]
        elif kind == "Range suggestions": tables = [("", (self.settings.get("suggestion") or {}).get("table", {}))]
        else: tables = self.selected_result_tables("excluded" if kind == "Excluded" else "cumulative")
        columns = list(dict.fromkeys(c for _, table in tables for c in table.get("columns", [])))
        rows = [r for _, table in tables for r in table.get("rows", [])]
        self.table.setColumnCount(len(columns)); self.table.setHorizontalHeaderLabels(columns); self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, col in enumerate(columns):
                value = row.get(col, "")
                self.table.setItem(i, j, QTableWidgetItem(str(number(value) if isinstance(value, dict) and "$nonfinite" in value else value)))

    def export_result(self):
        if not self.result: return
        path, _ = QFileDialog.getSaveFileName(self, "Create INP result folder", "analysis.inptk", "INP result folder (*.inptk)")
        if not path: return
        try:
            Path(path).mkdir(parents=False, exist_ok=False)
            with (Path(path) / "analysis.json").open("x", encoding="utf-8") as handle:
                handle.write(self.result["saved_result"])
        except (OSError, ValueError) as exc: self.error(f"Could not save result: {exc}. Choose a new filename."); return
        self.window.log(f"Saved INP result: {path}")

    def export_csv(self, kind="cumulative"):
        if not self.result: return
        if not self.client.capabilities: self.error("Connect INP toolkit to export CSV."); return
        path, _ = QFileDialog.getSaveFileName(self, "Export calculated INP table", "inp_results.csv", "CSV (*.csv)")
        if not path: return
        if Path(path).exists(): self.error("Choose a new filename; existing outputs are preserved."); return
        source = Path(self.cache.name) / f"export-{uuid.uuid4().hex}.inptk"
        source.mkdir()
        (source / "analysis.json").write_text(self.result["saved_result"], encoding="utf-8")
        args = ["export-csv", str(source), "--table", kind, "--out", path]
        if kind != "counts" and self.view_curve.currentText() != "All curves": args += ["--curve", self.view_curve.currentText()]
        self.operation = True
        def done(_):
            shutil.rmtree(source); self.operation = False; self.update_status(); self.window.log(f"Exported INP CSV: {path}")
        def fail(message): shutil.rmtree(source); self.error(message)
        self.client.request(args, done, fail)

    def session_state(self):
        return {"version": 1, "choices": copy.deepcopy(self.settings), "preview": self.preview,
                "preview_hash": self.preview_hash, "result": self.result}

    def restore_session(self, state):
        self.generation += 1; self.client.stop(); self.operation = False
        self.undo_stack.clear()
        self.undo_stack.setUndoLimit(self.window.undo_limit)
        state = state or {}
        self.preview = state.get("preview"); self.preview_hash = state.get("preview_hash", "")
        self.result = state.get("result")
        self.restore_choices(state.get("choices") or new_settings())

    def shutdown(self):
        self.client.stop(); self.cache.cleanup()
