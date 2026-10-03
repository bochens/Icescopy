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
from PySide6.QtCore import Qt, Signal, QTimer, QItemSelectionModel, QAbstractTableModel
from PySide6.QtGui import QAction, QColor, QKeySequence, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QTableView,
    QTextEdit, QVBoxLayout, QWidget, QFrame,
)

from icescopy_inptk_client import InptkClient
from icescopy_inptk_plot import axis_limits
from icescopy_inptk_state import cli_choices, fingerprint, new_settings, number, reconcile_inputs, set_group_inputs
from icescopy_plot import GrayscalePlotWidget
from icescopy_session_io import build_freeze_count_timeseries_csv_text


class InpTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.columns, self.rows = [], []

    def replace(self, columns, rows):
        self.beginResetModel()
        self.columns, self.rows = columns, rows
        self.endResetModel()

    def rowCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.rows)

    def columnCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.columns)

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role in (Qt.DisplayRole, Qt.ToolTipRole):
            value = self.rows[index.row()].get(self.columns[index.column()], "")
            return str(number(value) if isinstance(value, dict) and "$nonfinite" in value else value)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self.columns[section] if orientation == Qt.Horizontal else section + 1


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
        self.setText(selected[0] if len(selected) == 1 else f"{len(selected)} inputs…" if selected else "Choose…")
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
        self.last_error = ""
        self.after_connect = None
        self.plot_context = None
        self.plot_limits = None
        self.source_cache = None
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
        self.source_cache = None
        self.ensure_connected()
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
        self.connection = QLabel()
        self.splitter = splitter = QSplitter(Qt.Horizontal)
        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(8)
        side.addWidget(QLabel("Sample groups"))
        self.curves = QListWidget()
        self.curves.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.curves.setToolTip("Select a group to edit and plot it. Select several to compare. Double-click to rename.")
        self.curves.setMaximumHeight(100)
        self.curves.setMinimumHeight(64)
        self.curves.itemSelectionChanged.connect(self.select_curve)
        self.curves.itemChanged.connect(self.rename_curve)
        side.addWidget(self.curves)
        row = QHBoxLayout()
        self.add_curve_button = QPushButton("New group")
        self.add_curve_button.clicked.connect(self.add_group)
        row.addWidget(self.add_curve_button)
        self.remove_curve_button = QPushButton("Remove group")
        self.remove_curve_button.clicked.connect(self.remove_curve)
        row.addWidget(self.remove_curve_button)
        row.addStretch(1)
        side.addLayout(row)
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(300)
        side.addWidget(self.tabs, 1)
        splitter.addWidget(sidebar)
        splitter.setChildrenCollapsible(False)
        samples = QWidget()
        layout = QVBoxLayout(samples)
        help_text = self.sample_help = QLabel("Check the samples to combine in this group. Use Blank for water controls.")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.inputs = QTableWidget(0, 4)
        self.inputs.setHorizontalHeaderLabels(["Use", "Sample", "Dilution", "Blank"])
        self.inputs.verticalHeader().hide()
        self.inputs.setShowGrid(False)
        self.inputs.setAlternatingRowColors(True)
        self.inputs.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.inputs.setSelectionMode(QAbstractItemView.SingleSelection)
        self.inputs.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.inputs.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.inputs.itemChanged.connect(self.input_changed)
        self.inputs.itemSelectionChanged.connect(self.select_input)
        layout.addWidget(self.inputs, 1)
        cycle_row = QHBoxLayout()
        self.cycle_label = QLabel("Cycle")
        self.input_cycle = QComboBox()
        self.input_cycle.currentIndexChanged.connect(
            lambda: self.change_input_cycle(self.current_input(), self.input_cycle.currentData()))
        cycle_row.addWidget(self.cycle_label)
        cycle_row.addWidget(self.input_cycle, 1)
        layout.addLayout(cycle_row)
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
        layout.addStretch(1)
        self.add_control_tab(samples, "Samples")

        combine = QWidget()
        layout = QVBoxLayout(combine)
        form = QFormLayout()
        self.method = QComboBox()
        self.method.addItem("MLE", "mle")
        self.method.setToolTip("Maximum likelihood estimation: jointly fit the sample and blank freezing counts.")
        self.method.addItem("Average", "average")
        self.method.currentIndexChanged.connect(lambda: self.change_option("method", self.method.currentData()))
        form.addRow("Method", self.method)
        self.fit_step = self.option_edit("fit_step", "Automatic")
        form.addRow("Fit spacing (°C)", self.fit_step)
        self.combine_form = form
        self.basis = QComboBox()
        for text, key in (("Suspension", "suspension"), ("Sampled air", "sampled_air"), ("Dry soil", "dry_soil")):
            self.basis.addItem(text, key)
        self.basis.currentIndexChanged.connect(lambda: self.change_option("basis", self.basis.currentData()))
        form.addRow("Concentration in", self.basis)
        layout.addLayout(form)
        label = QLabel("Drag the colored limits or enter temperatures. Empty fields use the full range.")
        label.setToolTip("Both endpoints are included. Each sample has its own limits.")
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
        self.min_frozen = QSpinBox()
        self.min_unfrozen = QSpinBox()
        for widget, key in ((self.min_frozen, "min_frozen"), (self.min_unfrozen, "min_unfrozen")):
            widget.setRange(0, 100000)
            widget.setValue(3)
            widget.valueChanged.connect(lambda value, key=key: self.change_option(key, value))
        thresholds = QFormLayout()
        thresholds.addRow("Minimum frozen", self.min_frozen)
        thresholds.addRow("Minimum unfrozen", self.min_unfrozen)
        self.thresholds = thresholds
        layout.addLayout(thresholds)
        self.suggest = QPushButton("Auto range")
        self.suggest.setToolTip("Suggest Average limits for the selected sample group.")
        self.suggest.clicked.connect(self.suggest_ranges)
        layout.addWidget(self.suggest)
        self.suggestion_status = QLabel("Automatic limits are available for Average; MLE limits are manual.")
        self.suggestion_status.setWordWrap(True)
        layout.addWidget(self.suggestion_status)
        layout.addStretch(1)
        self.add_control_tab(combine, "Combine")

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
        form.addRow("Count step (°C)", self.grid_step)
        form.addRow("Warm end (°C)", self.grid_start)
        form.addRow("Cold end (°C)", self.grid_end)
        form.addRow("Count selection", self.grid_method)
        form.addRow("Window width (°C)", self.grid_window)
        self.decrease_policy = QComboBox()
        self.decrease_policy.addItem("Stop at first decrease", "stop_at_decrease")
        self.decrease_policy.addItem("Skip decreases", "skip_decreases")
        self.decrease_policy.currentIndexChanged.connect(lambda: self.change_option("decrease_policy", self.decrease_policy.currentData()))
        form.addRow("If concentration falls", self.decrease_policy)
        self.z = self.option_edit("z", "1.96")
        self.z.setToolTip("1.96 gives nominal 95% uncertainty bounds.")
        form.addRow("Uncertainty z", self.z)
        note = QLabel("The optional grid selects counts before calculation. It does not interpolate the final curve. Scientific checks and calculations are performed by INP toolkit.")
        note.setWordWrap(True)
        form.addRow(note)
        self.add_control_tab(advanced, "Advanced")

        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(8, 0, 0, 0)
        controls = QHBoxLayout()
        self.quantity = QComboBox()
        self.quantity.addItems(["Number frozen", "Fraction frozen", "Concentration"])
        self.quantity.setCurrentIndex(1)
        self.quantity.currentIndexChanged.connect(self.draw)
        self.log_y = QCheckBox("Log scale")
        self.log_y.setChecked(True)
        self.log_y.toggled.connect(self.draw)
        self.fit_button = QPushButton("Fit axes")
        self.fit_button.clicked.connect(self.fit_plot)
        controls.addWidget(self.quantity)
        controls.addStretch(1)
        controls.addWidget(self.log_y)
        controls.addWidget(self.fit_button)
        layout.addLayout(controls)
        self.views = QTabWidget()
        self.plot = pg.PlotWidget()
        self.plot.setBackground(None)
        self.plot.showGrid(x=True, y=True, alpha=.2)
        self.plot.setLabel("bottom", "Temperature", units="°C")
        self.plot.addLegend(offset=(8, 8))
        plot_page = QWidget()
        plot_layout = QVBoxLayout(plot_page)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        self.empty_plot = QLabel()
        self.empty_plot.setWordWrap(True)
        self.empty_plot.setAlignment(Qt.AlignCenter)
        self.empty_plot.setMargin(20)
        plot_layout.addWidget(self.empty_plot)
        plot_layout.addWidget(self.plot, 1)
        self.views.addTab(plot_page, "Plot")
        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        self.table_kind = QComboBox()
        self.table_kind.addItems(["Observations", "Concentration", "Excluded", "Range suggestions"])
        self.table_kind.currentIndexChanged.connect(self.draw_table)
        table_layout.addWidget(self.table_kind)
        self.table = QTableView()
        self.table_model = InpTableModel(self.table)
        self.table.setModel(self.table_model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table_layout.addWidget(self.table)
        self.views.addTab(table_page, "Table")
        console = QTextEdit()
        console.setReadOnly(True)
        console.setDocument(self.window.terminal.document())
        self.views.addTab(console, "Console")
        self.views.currentChanged.connect(self.draw_table)
        layout.addWidget(self.views, 1)
        self.plot_note = QLabel()
        self.plot_note.setWordWrap(True)
        layout.addWidget(self.plot_note)
        splitter.addWidget(view)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 800])
        outer.addWidget(splitter, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        bottom = QHBoxLayout()
        self.undo_button = QPushButton("Undo")
        self.redo_button = QPushButton("Redo")
        bottom.addWidget(self.undo_button)
        bottom.addWidget(self.redo_button)
        bottom.addWidget(self.connection)
        bottom.addStretch(1)
        self.calculate = QPushButton("Calculate")
        self.calculate.clicked.connect(self.recalculate)
        self.cancel = QPushButton("Stop")
        self.cancel.clicked.connect(self.cancel_operation)
        self.cancel.hide()
        self.export = QPushButton("Export")
        menu = QMenu(self.export)
        menu.addAction("Save INP toolkit result…", self.export_result)
        for label, kind in (("Frozen counts", "counts"), ("Frozen fractions", "frozen_fraction"),
                            ("Concentrations", "cumulative"), ("Excluded points", "excluded")):
            menu.addAction(f"Export all {label.lower()}…", lambda checked=False, kind=kind: self.export_csv(kind))
        self.export.setMenu(menu)
        for widget in (self.calculate, self.cancel, self.export): bottom.addWidget(widget)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        bottom.addWidget(close)
        # Enter commits a field; it must not accidentally run or close analysis.
        for button in self.findChildren(QPushButton): button.setAutoDefault(False)
        outer.addLayout(bottom)
        self.tabs.currentChanged.connect(self.draw_ranges)
        for form in (self.combine_form, self.thresholds, form):
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for combo in self.tabs.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(9)
        self.restore_choices(self.settings)

    def add_control_tab(self, widget, title):
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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
        # Renaming does not change any measured counts. Avoid rebuilding their
        # potentially long plot or the controls while an inline edit commits.
        def without_group_names(state):
            state = copy.deepcopy(state)
            for curve in state["curves"]: curve.pop("name", None)
            for value in state["inputs"].values(): value.pop("group", None)
            return state
        rename_only = (self.settings["curves"] != choices["curves"]
                       and without_group_names(self.settings) == without_group_names(choices))
        if (rename_only and self.quantity.currentText() != "Concentration"
                and self.plot_context and self.plot_context[3] == self.preview_hash):
            self.settings = copy.deepcopy(choices)
            for i, curve in enumerate(choices["curves"]): self.curves.item(i).setText(curve["name"])
            self.loading = False
            if self.plot_context:
                values = list(self.plot_context); values[2] = tuple(self.selected_curve_names())
                self.plot_context = tuple(values)
            self.update_status()
            return
        self.settings = copy.deepcopy(choices)
        old_input = self.current_input()
        old_curve = self.curves.currentRow()
        selected_names = set(self.selected_curve_names())
        old_range = self.ranges.currentRow()
        for key in ("fit_step", "grid_step", "grid_start", "grid_end", "grid_window", "z"):
            getattr(self, key).setText(str(self.settings[key]))
        for key in ("method", "basis", "grid_method", "decrease_policy"):
            widget = getattr(self, key); widget.setCurrentIndex(widget.findData(self.settings[key]))
        self.blank_enabled.setChecked(self.settings["blank_correction"])
        self.min_frozen.setValue(self.settings["min_frozen"])
        self.min_unfrozen.setValue(self.settings["min_unfrozen"])
        self.combine_form.setRowVisible(self.fit_step, self.settings["method"] == "mle")
        for field in (self.min_frozen, self.min_unfrozen):
            self.thresholds.setRowVisible(field, self.settings["method"] == "average")
        self.grid_window.setEnabled(bool(self.settings["grid_step"]) and self.settings["grid_method"] == "window")
        for widget in (self.grid_start, self.grid_end, self.grid_method): widget.setEnabled(bool(self.settings["grid_step"]))
        self.input_ids = list(self.settings["inputs"])
        self.inputs.setRowCount(0)
        self.inputs.setRowCount(len(self.input_ids))
        for row, key in enumerate(self.input_ids):
            values = self.settings["inputs"][key]
            use = QTableWidgetItem()
            self.inputs.setItem(row, 0, use)
            item = QTableWidgetItem(key); item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setData(Qt.DecorationRole, self.color(key)); self.inputs.setItem(row, 1, item)
            metadata = next((m for m in (self.preview or {}).get("measurement_metadata", []) if m["measurement_id"] == key), {})
            dilution = QTableWidgetItem(str(metadata.get("dilution", "")))
            dilution.setFlags(dilution.flags() & ~Qt.ItemIsEditable)
            self.inputs.setItem(row, 2, dilution)
            blank = QTableWidgetItem(); blank.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            blank.setCheckState(Qt.Checked if values["blank"] else Qt.Unchecked)
            self.inputs.setItem(row, 3, blank)
        self.inputs.setMaximumHeight(min(240, max(110, 36 + 30 * len(self.input_ids))))
        if self.input_ids: self.inputs.selectRow(self.input_ids.index(old_input) if old_input in self.input_ids else 0)
        self.curves.clear()
        for curve in self.settings["curves"]:
            item = QListWidgetItem(curve["name"]); item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.curves.addItem(item)
        for row in range(self.curves.count()):
            self.curves.item(row).setSelected(self.curves.item(row).text() in selected_names)
        if self.curves.count() and not self.curves.selectedItems():
            self.curves.setCurrentRow(max(0, min(old_curve, self.curves.count()-1)), QItemSelectionModel.ClearAndSelect)
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
            self.suggestion_status.setText("Auto range uses these count thresholds." if self.settings["method"] == "average" else "Set each sample's range manually for MLE.")
        self.select_input(); self.select_curve(); self.update_status()

    def current_input(self):
        row = self.inputs.currentRow()
        return self.input_ids[row] if 0 <= row < len(self.input_ids) else None

    def select_input(self):
        if self.loading: return
        key = self.current_input()
        if not key: return
        value = self.settings["inputs"][key]
        self.blank_label.setText(f"Blanks for {key}")
        measurements = {r["measurement_id"]: r for r in (self.preview or {}).get("measurements", [])}
        cycles = measurements.get(key, {}).get("cycle_ids", [value["cycle"]])
        self.input_cycle.blockSignals(True)
        self.input_cycle.clear()
        if len(cycles) != 1: self.input_cycle.addItem("Choose a cycle…", "")
        for cycle in cycles: self.input_cycle.addItem(str(cycle), str(cycle))
        self.input_cycle.setCurrentIndex(max(0, self.input_cycle.findData(value["cycle"])))
        self.input_cycle.blockSignals(False)
        self.cycle_label.setText(f"Cycle for {key}")
        self.cycle_label.setVisible(len(cycles) > 1)
        self.input_cycle.setVisible(len(cycles) > 1)
        self.blank_choice.populate([k for k, v in self.settings["inputs"].items() if v["blank"] and k != key], value["blanks"])
        self.blank_choice.setEnabled(not value["blank"])
        if key in self.range_ids: self.ranges.selectRow(self.range_ids.index(key))

    def input_changed(self, item):
        if self.loading: return
        key = self.input_ids[item.row()]; state = copy.deepcopy(self.settings)
        if item.column() == 0:
            index = self.single_curve_row()
            if index < 0: return
            members = list(state["curves"][index]["inputs"])
            if item.checkState() == Qt.Checked:
                if key not in members: members.append(key)
            else:
                members = [k for k in members if k != key]
            name = state["curves"][index]["name"]
            self.commit(set_group_inputs(state, index, members), f"INP analysis: update samples in {name}")
            return
        if item.column() != 3: return
        state["inputs"][key]["blank"] = item.checkState() == Qt.Checked
        if state["inputs"][key]["blank"]:
            for curve in state["curves"]: curve["inputs"] = [k for k in curve["inputs"] if k != key]
            state["curves"] = [c for c in state["curves"] if c["inputs"]]
        self.commit(state, f"INP analysis: update blank role for {key}")

    def change_input_cycle(self, key, cycle):
        if self.loading or key is None: return
        state = copy.deepcopy(self.settings); state["inputs"][key]["cycle"] = cycle
        self.commit(state, f"INP analysis: select cycle {cycle} for {key}")

    def change_blanks(self, values):
        key = self.current_input()
        if not key: return
        state = copy.deepcopy(self.settings); state["inputs"][key]["blanks"] = values
        self.commit(state, f"INP analysis: assign blanks for {key}")

    def selected_curve_names(self):
        return [item.text() for item in self.curves.selectedItems()]

    def selected_input_ids(self):
        names = set(self.selected_curve_names())
        return list(dict.fromkeys(key for curve in self.settings["curves"]
                                 if curve["name"] in names for key in curve["inputs"]))

    def single_curve_row(self):
        items = self.curves.selectedItems()
        return self.curves.row(items[0]) if len(items) == 1 else -1

    def select_curve(self):
        if self.loading: return
        row = self.single_curve_row()
        self.sample_help.setText("Check the samples to combine in this group. Use Blank for water controls."
                                 if row >= 0 else "Select one group to edit its samples, or several groups to compare their plots.")
        values = set(self.selected_input_ids())
        self.loading = True
        for i, key in enumerate(self.input_ids):
            item = self.inputs.item(i, 0)
            flags = Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
            if row >= 0 and not self.settings["inputs"][key]["blank"]: flags |= Qt.ItemIsEnabled
            item.setFlags(flags)
            item.setCheckState(Qt.Checked if key in values else Qt.Unchecked)
            owner = next((c["name"] for c in self.settings["curves"] if key in c["inputs"]), "ungrouped")
            item.setToolTip(f"Current group: {owner}. Check to move this sample into the selected group.")
        self.loading = False
        self.remove_curve_button.setEnabled(bool(self.selected_curve_names()))
        self.draw()

    def add_group(self):
        state = copy.deepcopy(self.settings)
        names = {c["name"] for c in state["curves"]}
        index = 1
        while f"Group {index}" in names: index += 1
        name = f"Group {index}"
        state["curves"].append({"name": name, "inputs": []})
        self.commit(state, f"INP analysis: add group {name}")
        self.curves.setCurrentRow(self.curves.count()-1, QItemSelectionModel.ClearAndSelect)
        self.tabs.setCurrentIndex(0)
        self.curves.editItem(self.curves.currentItem())

    def remove_curve(self):
        names = set(self.selected_curve_names())
        if not names: return
        state = copy.deepcopy(self.settings)
        state["curves"] = [c for c in state["curves"] if c["name"] not in names]
        self.commit(state, "INP analysis: remove sample group")

    def rename_curve(self, item):
        if self.loading: return
        name = item.text().strip()
        row = self.curves.row(item)
        if not name or any(c["name"] == name for i, c in enumerate(self.settings["curves"]) if i != row):
            self.loading = True; item.setText(self.settings["curves"][row]["name"]); self.loading = False
            self.error("Use a unique, nonempty sample group name."); return
        state = copy.deepcopy(self.settings)
        previous = state["curves"][row]["name"]
        state["curves"][row]["name"] = name
        # Names label the group; physical input identities and memberships stay.
        for values in state["inputs"].values():
            if values["group"] == previous: values["group"] = name
        self.commit(state, f"INP analysis: rename group {previous} to {name}")

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
        keys = self.selected_input_ids()
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
        if self.source_cache is None:
            text = build_freeze_count_timeseries_csv_text(w.freeze_count_timeseries_headers, w.freeze_count_timeseries_rows,
                session_metadata=w.serialize_session_metadata(), summary=w.freeze_count_timeseries_summary)
            self.source_cache = (text, hashlib.sha256(text.encode()).hexdigest())
        return self.source_cache[0]

    def current_hash(self):
        try:
            self.source_text()
            return self.source_cache[1]
        except ValueError: return ""

    def calculation_key(self):
        # Suggested limits affect calculation only once applied. Changing the
        # suggestion thresholds/report alone does not change a fitted result.
        choices = {k: v for k, v in self.settings.items()
                   if k not in {"suggestion", "min_frozen", "min_unfrozen"}}
        return fingerprint([self.current_hash(), choices])

    def ensure_connected(self, after=None):
        path = getattr(self.window, "inptk_executable_path", "")
        normalized = str(Path(path).expanduser()) if path else ""
        if self.client.capabilities and self.client.path == normalized:
            if after: after()
            return
        if after: self.after_connect = after
        if not self.client.busy:
            self.last_error = ""
            self.client.connect_executable(path)

    def connect_toolkit(self):
        self.ensure_connected()

    def connected(self, reply):
        self.last_error = ""
        self.window.log(f"INP toolkit connected: {reply['toolkit_version']} (protocol 2)")
        after, self.after_connect = self.after_connect, None
        self.refresh_preview(after=after)

    def refresh_preview(self, _checked=False, after=None):
        if self.operation or self.client.busy: return
        if not self.client.capabilities:
            self.ensure_connected(after=lambda: self.refresh_preview(after=after)); return
        try: text = self.source_text()
        except ValueError as exc: self.error(str(exc)); return
        source_hash = hashlib.sha256(text.encode()).hexdigest()
        path = Path(self.cache.name) / f"counts-{uuid.uuid4().hex}.csv"
        path.write_text(text)
        self.last_error = ""
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
            if missing: self.update_status()
            self.window.log("INP analysis: counts and fractions updated.")
            if after: after()
        def failed(message):
            path.unlink(missing_ok=True); self.error(message)
        self.client.request(["preview", str(path), "--format", "icescopy"], done, failed)

    def recalculate(self):
        if self.operation or self.client.busy: return
        if not self.client.capabilities:
            self.ensure_connected(after=self.recalculate); return
        if self.preview_hash != self.current_hash() or not self.preview:
            self.refresh_preview(after=self.recalculate); return
        self.run_calculation(False)

    def suggest_ranges(self):
        if self.operation or self.client.busy: return
        if not self.client.capabilities:
            self.ensure_connected(after=self.suggest_ranges); return
        if self.preview_hash != self.current_hash() or not self.preview:
            self.refresh_preview(after=self.suggest_ranges); return
        self.run_calculation(True)

    def run_calculation(self, suggest):
        if suggest and self.settings["method"] != "average": return
        row = self.single_curve_row()
        selected = self.settings["curves"][row]["name"] if suggest and row >= 0 else None
        try:
            if suggest and selected is None: raise ValueError("Select one sample group for Auto range.")
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
        self.last_error = ""
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
        self.calculate.setEnabled(not busy and bool(self.current_hash()))
        self.calculate.setText("Recalculate" if self.result else "Calculate")
        self.cancel.setVisible(busy)
        self.suggest.setEnabled(not busy and self.settings["method"] == "average" and self.single_curve_row() >= 0)
        self.export.setEnabled(bool(self.result) and not busy)
        if connected:
            self.connection.setText(f"INP toolkit {self.client.capabilities['toolkit_version']}")
        else:
            self.connection.setText("Connecting…" if self.client.busy else "Toolkit unavailable")
        missing = (self.preview or {}).get("suspension_metadata", {}).get("error")
        if busy: message = "Calculating…" if self.operation and self.preview else "Loading counts…"
        elif self.last_error: message = self.last_error
        elif self.result and self.result["key"] == self.calculation_key(): message = "Result is up to date."
        elif self.result: message = "Changes not calculated — showing the last successful result."
        elif missing: message = f"Counts available. Concentration needs sample metadata: {missing}"
        elif self.preview: message = "Check samples and blanks, then Calculate."
        else: message = "Import temperatures and freezing counts to begin."
        self.status.setText(message)
        if self.quantity.currentText() == "Concentration":
            self.plot_note.setText("Shading: uncertainty. Crosses: excluded points. Export uses the last calculation.")
        else:
            self.plot_note.setText("Original observations for the selected groups. Colors identify inputs.")
        if self.quantity.currentText() == "Concentration" and self.log_y.isChecked():
            self.plot_note.setText(self.plot_note.text() + " Log scale omits zero values; shading needs two positive bounds.")
        self.update_empty_plot()

    def update_empty_plot(self):
        message = ""
        if not self.selected_curve_names():
            message = "Select a sample group on the left."
        elif self.quantity.currentText() == "Concentration":
            if self.last_error:
                message = self.last_error
            elif not self.result:
                missing = (self.preview or {}).get("suspension_metadata", {}).get("error")
                message = (f"Concentration needs sample metadata. {missing}" if missing else
                           "Choose samples and blanks, then Calculate to show concentration.")
            elif not self.selected_result_tables("cumulative"):
                message = "This sample group has not been calculated. Choose Recalculate."
            elif not getattr(self, "visible_points", 0):
                message = ("No positive concentration values on log scale. Turn off Log scale to see zeros."
                           if self.log_y.isChecked() else
                           "No finite concentration points. Check the selected ranges and excluded-point table.")
        elif not self.preview:
            message = self.last_error or "Loading freezing counts…"
        self.empty_plot.setText(message)
        self.empty_plot.setVisible(bool(message))

    def error(self, message):
        self.operation = False
        self.after_connect = None
        self.last_error = str(message)
        self.update_status()
        self.window.log(f"INP toolkit: {message}")

    def cancel_operation(self):
        self.generation += 1; self.client.stop(); self.operation = False
        for path in Path(self.cache.name).iterdir():
            if path.is_dir(): shutil.rmtree(path)
            else: path.unlink(missing_ok=True)
        self.error("Stopped. The last successful result is retained. Calculate to try again.")

    def source_changed(self):
        self.source_cache = None
        # Source metadata/header edits can still be in progress. Read them on
        # the next event loop turn, once the main window has finished the edit.
        if self.isVisible(): QTimer.singleShot(0, self.refresh_if_needed)

    def refresh_if_needed(self):
        if not self.operation and not self.client.busy and self.preview_hash != self.current_hash():
            self.refresh_preview()
        self.update_status()

    def selected_result_tables(self, kind):
        selected = set(self.selected_curve_names())
        return [(name, tables[kind]) for name, tables in (self.result or {}).get("tables", {}).items()
                if kind in tables and name in selected]

    def fit_plot(self):
        if self.plot_limits:
            xlim, ylim = self.plot_limits
            self.plot.setRange(xRange=xlim, yRange=ylim, padding=0)

    @staticmethod
    def point_tip(x, y, data):
        return "\n".join(f"{k}: {v}" for k, v in data.items() if k in {
            "temperature_C", "measurement_id", "n_total", "n_frozen", "fraction_frozen",
            "concentration", "lower_error", "upper_error", "contributor_count", "unit",
            "selection_status", "final_selection_status", "qc_flag"})

    def observation_rows(self):
        selected = set(self.selected_input_ids())
        rows = []
        for row in (self.preview or {}).get("table", {}).get("rows", []):
            key = row["measurement_id"]
            chosen = self.settings["inputs"].get(key, {}).get("cycle", "")
            if key in selected and (not chosen or str(row["cycle_id"]) == chosen): rows.append(row)
        return rows

    def draw(self, *_):
        if self.loading: return
        quantity = self.quantity.currentText()
        is_concentration = quantity == "Concentration"
        # Counts and fractions always retain their physical linear scale. The
        # concentration scale choice is remembered when switching quantities.
        logarithmic = is_concentration and self.log_y.isChecked()
        self.log_y.setVisible(is_concentration)
        context = (quantity, logarithmic, tuple(self.selected_curve_names()), self.preview_hash,
                   (self.result or {}).get("key"))
        refit = context != self.plot_context
        self.plot_context = context
        self.plot.clear(); self.range_items.clear()
        legend = self.plot.getPlotItem().legend
        if legend: legend.clear()
        self.plot.disableAutoRange()
        if logarithmic != self.plot.getPlotItem().ctrl.logYCheck.isChecked():
            self.plot.setYRange(0, 1, padding=0)
        self.plot.setLogMode(x=False, y=logarithmic)
        foreground = self.palette().color(self.foregroundRole())
        for side in ("left", "bottom"):
            self.plot.getAxis(side).setTextPen(foreground)
            self.plot.getAxis(side).setPen(foreground)
            self.plot.getAxis(side).enableAutoSIPrefix(False)
        if legend: legend.setLabelTextColor(foreground)
        self.plot.setLabel("left", quantity, units="")
        groups = []
        if is_concentration:
            for name, table in self.selected_result_tables("cumulative"):
                groups.append((name, table["rows"], "concentration"))
        else:
            by_input = {}
            for row in self.observation_rows():
                by_input.setdefault(f"{row['measurement_id']} · cycle {row['cycle_id']}", []).append(row)
            for name, rows in by_input.items():
                groups.append((name, rows, "n_frozen" if quantity == "Number frozen" else "fraction_frozen"))
        xs, ys, totals = [], [], []
        self.visible_points = 0
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
                valid = np.isfinite(x) & np.isfinite(y)
                if logarithmic: valid &= y > 0
                self.visible_points += int(valid.sum())
                xs.extend(x[np.isfinite(x)]); ys.extend(y[valid])
                totals.extend(number(row.get("n_total")) for row in chunk)
                y[~valid] = np.nan
                if not valid.any(): continue
                curve = self.plot.plot(x, y, pen=pg.mkPen(color, width=2), symbol="o", symbolSize=5,
                    symbolBrush=color, symbolPen=color, name=name if i == 0 else None, connect="finite", data=chunk)
                # PlotDataItem owns transformed x/y for both line and symbols.
                # Only set hover options here; replacing scatter data breaks log Y.
                curve.scatter.opts.update(hoverable=True, tip=self.point_tip)
                if column == "concentration":
                    unit = str(chunk[0].get("unit", ""))
                    unit = {"INP_per_mL_suspension": "INP/mL suspension", "INP_per_L_air": "INP/L air",
                            "INP_per_g_soil": "INP/g soil"}.get(unit, unit)
                    self.plot.setLabel("left", "Concentration", units=unit)
                    lower = y - np.array([number(row.get("lower_error")) for row in chunk])
                    upper = y + np.array([number(row.get("upper_error")) for row in chunk])
                    for bound in (lower, upper):
                        bound[~np.isfinite(bound)] = np.nan
                        if logarithmic: bound[bound <= 0] = np.nan
                        ys.extend(bound[np.isfinite(x) & np.isfinite(bound)])
                    edge = QColor(color); edge.setAlpha(90)
                    lo = self.plot.plot(x, lower, pen=pg.mkPen(edge, width=1), connect="finite")
                    hi = self.plot.plot(x, upper, pen=pg.mkPen(edge, width=1), connect="finite")
                    fill = QColor(color); fill.setAlpha(35)
                    # The two paths must cover identical temperatures. Pairing
                    # unequal paths closes a diagonal polygon across missing or
                    # zero log bounds, falsely shading outside the interval.
                    paired = np.flatnonzero(np.isfinite(x) & np.isfinite(lower) & np.isfinite(upper))
                    for indices in np.split(paired, np.flatnonzero(np.diff(paired) != 1) + 1):
                        if len(indices) < 2: continue
                        boundary = pg.mkPen(QColor(0, 0, 0, 0))
                        band_lo = self.plot.plot(x[indices], lower[indices], pen=boundary)
                        band_hi = self.plot.plot(x[indices], upper[indices], pen=boundary)
                        self.plot.addItem(pg.FillBetweenItem(band_lo, band_hi, brush=fill), ignoreBounds=True)
        if is_concentration:
            for name, table in self.selected_result_tables("excluded"):
                rows = table["rows"]
                if not rows: continue
                x = np.array([number(r.get("temperature_C")) for r in rows])
                y = np.array([number(r.get("concentration")) for r in rows])
                valid = np.isfinite(x) & np.isfinite(y)
                if logarithmic: valid &= y > 0
                y[~valid] = np.nan
                if not valid.any(): continue
                # Excluded outliers must not flatten the retained concentration.
                points = self.plot.plot(x, y, data=rows, pen=None, symbol="x", symbolSize=6,
                    symbolPen=pg.mkPen(150, 150, 150, 110))
                points.scatter.opts.update(hoverable=True, tip=self.point_tip)
        self.plot_limits = axis_limits(quantity, xs, ys, totals, logarithmic=logarithmic)
        if refit: self.fit_plot()
        self.draw_ranges(); self.draw_table(); self.update_status()

    def draw_table(self, *_):
        if self.loading or self.views.currentIndex() != 1: return
        kind = self.table_kind.currentText()
        if kind == "Observations":
            table = dict((self.preview or {}).get("table", {}))
            table["rows"] = self.observation_rows()
            tables = [("", table)]
        elif kind == "Range suggestions": tables = [("", (self.settings.get("suggestion") or {}).get("table", {}))]
        else: tables = self.selected_result_tables("excluded" if kind == "Excluded" else "cumulative")
        columns = list(dict.fromkeys(c for _, table in tables for c in table.get("columns", [])))
        rows = [r for _, table in tables for r in table.get("rows", [])]
        self.table_model.replace(columns, rows)

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
        if not self.client.capabilities: self.ensure_connected(after=lambda: self.export_csv(kind)); return
        path, _ = QFileDialog.getSaveFileName(self, "Export calculated INP table", "inp_results.csv", "CSV (*.csv)")
        if not path: return
        if Path(path).exists(): self.error("Choose a new filename; existing outputs are preserved."); return
        source = Path(self.cache.name) / f"export-{uuid.uuid4().hex}.inptk"
        source.mkdir()
        (source / "analysis.json").write_text(self.result["saved_result"], encoding="utf-8")
        args = ["export-csv", str(source), "--table", kind, "--out", path]
        # Export the complete saved calculation, as named in the menu. Raw
        # counts/fractions have measurement IDs, not named concentration curves.
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
        self.last_error = ""; self.after_connect = None; self.plot_context = None; self.source_cache = None
        self.undo_stack.clear()
        self.undo_stack.setUndoLimit(self.window.undo_limit)
        state = state or {}
        self.preview = state.get("preview"); self.preview_hash = state.get("preview_hash", "")
        self.result = state.get("result")
        self.restore_choices(state.get("choices") or new_settings())

    def shutdown(self):
        self.client.stop(); self.cache.cleanup()
