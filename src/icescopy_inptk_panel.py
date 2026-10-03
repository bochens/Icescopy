"""Modal INP analysis workspace. All calculations run in the external CLI."""
import copy
import hashlib
import json
import math
import shutil
from pathlib import Path
import tempfile
import time
import uuid

import numpy as np
import pyqtgraph as pg
from shiboken6 import isValid
from PySide6.QtCore import Qt, Signal, QTimer, QItemSelectionModel, QAbstractTableModel
from PySide6.QtGui import QAction, QColor, QKeySequence, QPalette, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QTableView,
    QTextEdit, QVBoxLayout, QWidget, QFrame, QGroupBox, QStyledItemDelegate,
)

from icescopy_inptk_client import InptkClient
from icescopy_inptk_plot import ConcentrationAxis, TemperatureRangeItem, axis_limits
from icescopy_inptk_state import cli_choices, concentration_curves, fingerprint, new_settings, number, reconcile_inputs, set_group_inputs
from icescopy_plot import GrayscalePlotWidget
from icescopy_session_io import build_freeze_count_timeseries_csv_text


def concentration_unit(unit):
    return {"INP_per_mL_suspension": "INP/mL suspension", "INP_per_L_air": "INP/L air",
            "INP_per_g_soil": "INP/g soil"}.get(unit, unit)


class InpTableModel(QAbstractTableModel):
    HEADERS = {
        "measurement_id": "Sample", "curve_id": "Group", "sample_id": "Sample group",
        "temperature_C": "Temperature (°C)", "n_frozen": "Frozen", "n_total": "Total",
        "fraction_frozen": "Fraction frozen", "cycle_id": "Cycle", "concentration": "Concentration",
        "lower_error": "Lower error", "upper_error": "Upper error", "unit": "Unit",
        "contributor_count": "Contributors", "qc_flag": "Quality flag",
    }

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
        if index.isValid() and role == Qt.TextAlignmentRole:
            value = self.rows[index.row()].get(self.columns[index.column()])
            if isinstance(value, (int, float, dict)):
                return Qt.AlignRight | Qt.AlignVCenter
        if index.isValid() and role in (Qt.DisplayRole, Qt.ToolTipRole):
            value = self.rows[index.row()].get(self.columns[index.column()], "")
            if isinstance(value, dict) and "$nonfinite" in value: value = number(value)
            if role == Qt.DisplayRole:
                if isinstance(value, float): return f"{value:.6g}"
                if self.columns[index.column()] == "unit": return concentration_unit(str(value))
            return str(value)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                key = self.columns[section]
                return self.HEADERS.get(key, key.replace("_", " ").capitalize())
            return section + 1
        if role == Qt.ToolTipRole and orientation == Qt.Horizontal:
            key = self.columns[section]
            if key in {"lower_error", "upper_error"}:
                return f"{key}: distance from the concentration to its confidence limit, not the limit itself."
            return key


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
        self.setText(selected[0] if len(selected) == 1 else f"{len(selected)} blanks" if selected else "No blank assigned")
        self.setToolTip(", ".join(selected) or "Choose water blanks for this sample. Without an assignment it is not corrected.")

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


class RangeLimitDelegate(QStyledItemDelegate):
    """Show measured endpoints as placeholders without setting analysis limits."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if not index.data() and index.data(Qt.UserRole) is not None:
            option.text = index.data(Qt.UserRole)
            option.font.setItalic(True)
            base = option.palette.color(QPalette.Base)
            option.palette.setColor(QPalette.Text, QColor("#686868" if base.lightness() > 128 else "#b8b8b8"))

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setPlaceholderText(index.data(Qt.UserRole) or "Full range")
        return editor


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
        self.calculation_connection = None
        self.loading = False
        self.operation = False
        self.operation_started = None
        self.operation_phase = ""
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self.show_elapsed)
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
        row = QHBoxLayout()
        row.addWidget(self.heading("Sample groups"), 1)
        self.add_curve_button = QPushButton("New…")
        self.add_curve_button.setToolTip("Create a sample group, then check the samples to combine.")
        self.add_curve_button.clicked.connect(self.add_group)
        self.remove_curve_button = QPushButton("Remove")
        self.remove_curve_button.setToolTip("Remove selected groups from the output. Source samples are retained.")
        self.remove_curve_button.clicked.connect(self.remove_curve)
        for button in (self.add_curve_button, self.remove_curve_button):
            button.setAttribute(Qt.WA_MacSmallSize)
            row.addWidget(button)
        side.addLayout(row)
        self.curves = QListWidget()
        self.curves.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.curves.setAccessibleName("Sample groups to edit and display")
        self.curves.setToolTip("Select a group to edit and plot it. Select several to compare. Double-click to rename.")
        self.curves.itemSelectionChanged.connect(self.select_curve)
        self.curves.itemChanged.connect(self.rename_curve)
        side.addWidget(self.curves)
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(300)
        side.addWidget(self.tabs, 1)
        splitter.addWidget(sidebar)
        splitter.setChildrenCollapsible(False)
        samples = QWidget()
        layout = QVBoxLayout(samples)
        help_text = self.sample_help = QLabel()
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.inputs = QTableWidget(0, 4)
        self.inputs.setHorizontalHeaderLabels(["Use", "Sample", "Dilution", "Blank"])
        self.inputs.setAccessibleName("Group membership and water blank roles")
        self.inputs.horizontalHeaderItem(0).setToolTip("Check to move a sample into the selected group.")
        self.inputs.horizontalHeaderItem(3).setToolTip("Mark a water-control sample, then assign it under Blank correction.")
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
        self.blank_box = QGroupBox("Blank correction")
        self.blank_box.setFlat(True)
        blank_layout = QVBoxLayout(self.blank_box)
        self.blank_enabled = QCheckBox("Apply blank correction")
        self.blank_enabled.toggled.connect(lambda value: self.change_option("blank_correction", value))
        blank_layout.addWidget(self.blank_enabled)
        self.blank_label = QLabel()
        self.blank_label.setWordWrap(True)
        blank_layout.addWidget(self.blank_label)
        self.blank_choice = ChoiceMenu()
        self.blank_choice.changed.connect(self.change_blanks)
        blank_layout.addWidget(self.blank_choice)
        self.blank_help = QLabel()
        self.blank_help.setWordWrap(True)
        blank_layout.addWidget(self.blank_help)
        layout.addWidget(self.blank_box)
        layout.addStretch(1)
        catalog = QPushButton("Edit sample metadata…")
        catalog.setToolTip("Close this window to edit physical metadata. Your INP analysis is retained.")
        catalog.clicked.connect(self.edit_metadata)
        layout.addWidget(catalog, alignment=Qt.AlignLeft)
        self.add_control_tab(samples, "Samples")

        combine = QWidget()
        layout = QVBoxLayout(combine)
        layout.addWidget(self.heading("Calculation · all groups"))
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
        layout.addSpacing(8)
        layout.addWidget(self.heading("Temperature limits · selected group"))
        label = QLabel("Select a sample row, then drag its handles on the temperature axis or type its limits.")
        label.setToolTip("Both endpoints are included. Each sample has its own limits.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.ranges = QTableWidget(0, 3)
        self.ranges.setHorizontalHeaderLabels(["Sample", "Cold (°C)", "Warm (°C)"])
        self.ranges.setAccessibleName("Temperature limits for each selected sample")
        for col in (1, 2): self.ranges.setItemDelegateForColumn(col, RangeLimitDelegate(self.ranges))
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
        self.auto_range_options = QWidget()
        self.auto_range_options.setLayout(thresholds)
        layout.addWidget(self.auto_range_options)
        self.suggest = QPushButton("Auto range")
        self.suggest.setToolTip("Suggest Average limits for the selected sample group.")
        self.suggest.clicked.connect(self.suggest_ranges)
        self.full_range = QPushButton("Full range")
        self.full_range.setToolTip("Clear limits for every sample in the selected groups. Available temperatures will be used.")
        self.full_range.clicked.connect(self.reset_ranges)
        range_actions = QHBoxLayout()
        range_actions.addWidget(self.suggest)
        range_actions.addWidget(self.full_range)
        layout.addLayout(range_actions)
        self.suggestion_status = QLabel("Automatic limits are available for Average; MLE limits are manual.")
        self.suggestion_status.setWordWrap(True)
        layout.addWidget(self.suggestion_status)
        layout.addStretch(1)
        self.add_control_tab(combine, "Combine")

        advanced = QWidget()
        layout = QVBoxLayout(advanced)
        layout.addWidget(self.heading("Count selection · all groups"))
        self.grid_enabled = QCheckBox("Use a temperature grid")
        self.grid_enabled.toggled.connect(self.toggle_grid)
        layout.addWidget(self.grid_enabled)
        note = QLabel("New analyses use a 0.5 °C grid. Turn off to use every measured temperature.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.grid_controls = QWidget()
        form = self.grid_form = QFormLayout(self.grid_controls)
        form.setContentsMargins(0, 0, 0, 0)
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
        layout.addWidget(self.grid_controls)
        layout.addSpacing(12)
        layout.addWidget(self.heading("Concentration · all groups"))
        form = QFormLayout()
        self.decrease_policy = QComboBox()
        self.decrease_policy.addItem("Stop at first decrease", "stop_at_decrease")
        self.decrease_policy.addItem("Skip decreases", "skip_decreases")
        self.decrease_policy.currentIndexChanged.connect(lambda: self.change_option("decrease_policy", self.decrease_policy.currentData()))
        form.addRow("If concentration falls", self.decrease_policy)
        self.z = self.option_edit("z", "1.96")
        self.z.setToolTip("1.96 gives nominal 95% uncertainty bounds.")
        form.addRow("Uncertainty z", self.z)
        self.z.setAccessibleName("Uncertainty z score; 1.96 gives nominal 95 percent bounds")
        note = QLabel("z = 1.96 gives nominal 95% uncertainty bounds.")
        note.setWordWrap(True)
        form.addRow(note)
        layout.addLayout(form)
        layout.addStretch(1)
        self.add_control_tab(advanced, "Advanced")

        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(8, 0, 0, 0)
        self.view_heading = self.heading("")
        self.view_heading.setWordWrap(True)
        layout.addWidget(self.view_heading)
        self.views = QTabWidget()
        plot_page = QWidget()
        plot_layout = QVBoxLayout(plot_page)
        plot_layout.setContentsMargins(8, 8, 8, 8)
        controls = QHBoxLayout()
        self.quantity = QComboBox()
        self.quantity.addItems(["Number frozen", "Fraction frozen", "Concentration"])
        self.quantity.setAccessibleName("Plotted quantity")
        self.quantity.setCurrentIndex(1)
        self.quantity.currentIndexChanged.connect(self.draw)
        self.log_y = QCheckBox("Log scale")
        self.log_y.setChecked(True)
        self.log_y.toggled.connect(self.draw)
        self.show_uncertainty = QCheckBox("Uncertainty")
        self.show_uncertainty.setToolTip("Show the group's full confidence limits and fit the axes to them. Values in Table and exports are unchanged.")
        self.show_uncertainty.toggled.connect(self.draw)
        self.fit_button = QPushButton("Fit axes")
        self.fit_button.clicked.connect(self.fit_plot)
        controls.addWidget(self.quantity)
        controls.addStretch(1)
        controls.addWidget(self.show_uncertainty)
        controls.addWidget(self.log_y)
        controls.addWidget(self.fit_button)
        plot_layout.addLayout(controls)
        self.plot = pg.PlotWidget(axisItems={'left': ConcentrationAxis('left')})
        self.plot.setBackground(self.palette().color(QPalette.Base))
        self.plot.showGrid(x=False, y=True, alpha=.12)
        for side in ("left", "bottom"):
            self.plot.getAxis(side).setStyle(maxTickLevel=1)
            self.plot.getAxis(side).setTickDensity(.6)
        self.plot.setLabel("bottom", "Temperature", units="°C")
        self.plot.addLegend(offset=(8, 8))
        self.empty_plot = QLabel()
        self.empty_plot.setWordWrap(True)
        self.empty_plot.setAlignment(Qt.AlignCenter)
        self.empty_plot.setMargin(20)
        plot_layout.addWidget(self.empty_plot)
        plot_layout.addWidget(self.plot, 1)
        self.plot_note = QLabel()
        self.plot_note.setWordWrap(True)
        plot_layout.addWidget(self.plot_note)
        self.views.addTab(plot_page, "Plot")
        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        self.table_kind = QComboBox()
        self.table_kind.addItems(["Observations", "Concentration", "Excluded", "Range suggestions"])
        self.table_kind.currentIndexChanged.connect(self.draw_table)
        table_controls = QHBoxLayout()
        table_controls.addWidget(self.table_kind)
        table_controls.addStretch(1)
        self.table_units = QLabel()
        self.table_units.setToolTip("Numbers are displayed to six significant figures. Hover for full precision; exports retain the original values.")
        table_controls.addWidget(self.table_units)
        table_layout.addLayout(table_controls)
        self.table = QTableView()
        self.table_model = InpTableModel(self.table)
        self.table.setModel(self.table_model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setResizeContentsPrecision(100)
        self.table.setAccessibleName("INP toolkit results for selected groups")
        table_layout.addWidget(self.table)
        self.views.addTab(table_page, "Table")
        console = QTextEdit()
        console.setReadOnly(True)
        console.setDocument(self.window.terminal.document())
        self.views.addTab(console, "Console")
        self.views.currentChanged.connect(self.draw_table)
        layout.addWidget(self.views, 1)
        splitter.addWidget(view)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 800])
        outer.addWidget(splitter, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.connection)
        outer.addLayout(status_row)
        bottom = QHBoxLayout()
        self.undo_button = QPushButton("Undo")
        self.redo_button = QPushButton("Redo")
        bottom.addWidget(self.undo_button)
        bottom.addWidget(self.redo_button)
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
        for form in (self.combine_form, self.thresholds, self.grid_form, form):
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # Longer scientific choices get a full row, consistently, rather than
        # wrapping some labels but not others as the sidebar changes width.
        form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        for combo in self.tabs.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(9)
        self.restore_choices(self.settings)

    @staticmethod
    def heading(text):
        label = QLabel(text)
        label.setTextFormat(Qt.PlainText)
        font = label.font(); font.setBold(True); label.setFont(font)
        return label

    @staticmethod
    def fit_table_height(table, count, maximum_rows=6):
        # Size from the native row metrics; leave scrolling for longer lists.
        rows = min(max(1, count), maximum_rows)
        height = table.horizontalHeader().height() + rows * table.verticalHeader().defaultSectionSize() + 2 * table.frameWidth() + 4
        table.setFixedHeight(height)

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
        # Match the exact exported input to its Icescopy sample ID, including
        # sparse IDs and renamed samples; list order is not a sample identity.
        for sample in self.window.freeze_count_timeseries_summary.get('sample_total_cells', []):
            if sample.get('sample_name') == key:
                color = self.window.sample_visual_color(sample.get('sample_id'))
                if color is not None: return color
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

    def toggle_grid(self, enabled):
        self.change_option("grid_step", (self.grid_step.text().strip() or "0.5") if enabled else "")

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
            self.update_view_heading()
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
        self.auto_range_options.setVisible(self.settings["method"] == "average")
        self.suggest.setVisible(self.settings["method"] == "average")
        self.grid_enabled.setChecked(bool(self.settings["grid_step"]))
        self.grid_controls.setVisible(bool(self.settings["grid_step"]))
        self.grid_form.setRowVisible(self.grid_window, self.settings["grid_method"] == "window")
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
        self.fit_table_height(self.inputs, len(self.input_ids))
        if self.input_ids: self.inputs.selectRow(self.input_ids.index(old_input) if old_input in self.input_ids else 0)
        self.curves.clear()
        for curve in self.settings["curves"]:
            item = QListWidgetItem(curve["name"]); item.setFlags(item.flags() | Qt.ItemIsEditable)
            item.setToolTip("\n".join(curve["inputs"]) or "No samples yet. Check samples below to add them.")
            self.curves.addItem(item)
        row_height = self.curves.sizeHintForRow(0) if self.curves.count() else self.curves.fontMetrics().height() + 4
        self.curves.setFixedHeight(min(4, max(2, self.curves.count())) * row_height + 2 * self.curves.frameWidth() + 4)
        for row in range(self.curves.count()):
            self.curves.item(row).setSelected(self.curves.item(row).text() in selected_names)
        if self.curves.count() and not self.curves.selectedItems():
            self.curves.setCurrentRow(max(0, min(old_curve, self.curves.count()-1)), QItemSelectionModel.ClearAndSelect)
        self.range_ids = [key for key, value in self.settings["inputs"].items() if not value["blank"]]
        self.ranges.setRowCount(len(self.range_ids))
        measured = self.measured_limits()
        for row, key in enumerate(self.range_ids):
            item = QTableWidgetItem(key); item.setFlags(item.flags() & ~Qt.ItemIsEditable); item.setData(Qt.DecorationRole, self.color(key))
            self.ranges.setItem(row, 0, item)
            for col, limit in ((1, "min_C"), (2, "max_C")):
                item = QTableWidgetItem(str(self.settings["ranges"].get(key, {}).get(limit, "")))
                endpoint = measured.get(key, {}).get(limit)
                item.setData(Qt.UserRole, f"{endpoint:g}" if endpoint is not None else "Auto")
                item.setToolTip("Clear this field to follow the measured range. Both endpoints are included.")
                item.setData(Qt.AccessibleTextRole, item.text() or f"Measured limit: {item.data(Qt.UserRole)} °C; unrestricted")
                self.ranges.setItem(row, col, item)
        if self.range_ids: self.ranges.selectRow(max(0, min(old_range, len(self.range_ids)-1)))
        self.loading = False
        if self.settings.get("suggestion"):
            self.show_suggestion(self.settings["suggestion"], log=False)
        else:
            self.suggestion_status.setText("Auto range uses the minimum counts above." if self.settings["method"] == "average" else "MLE uses manual limits, or the full range.")
        self.select_input(); self.select_curve(); self.update_status()

    def current_input(self):
        row = self.inputs.currentRow()
        return self.input_ids[row] if 0 <= row < len(self.input_ids) else None

    def select_input(self):
        if self.loading: return
        key = self.current_input()
        if not key:
            self.blank_label.hide(); self.blank_choice.hide()
            self.cycle_label.hide(); self.input_cycle.hide()
            self.blank_help.setText("Select a sample row to assign its water blanks.")
            self.blank_help.show()
            return
        value = self.settings["inputs"][key]
        self.blank_label.setText(f"Water blanks for {key}")
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
        blanks = [k for k, v in self.settings["inputs"].items() if v["blank"] and k != key]
        self.blank_choice.populate(blanks, value["blanks"])
        available = not value["blank"] and bool(blanks)
        self.blank_label.setVisible(available)
        self.blank_choice.setVisible(available)
        self.blank_choice.setEnabled(self.settings["blank_correction"])
        self.blank_label.setEnabled(self.settings["blank_correction"])
        if value["blank"]:
            message = "This is a water blank. Select a sample row to assign it."
        elif not blanks:
            message = "Mark a water control in the Blank column, then select a sample to assign it."
        elif not self.settings["blank_correction"]:
            message = "Correction is off. Assignments are retained."
        elif not value["blanks"]:
            message = "No blank assigned; this sample will not be corrected."
        else:
            message = ""
        self.blank_help.setText(message)
        self.blank_help.setVisible(bool(message))
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
        else:
            # Removing the blank role also removes its assignments. Undo restores
            # both together, so no hidden invalid blank map reaches the toolkit.
            for value in state["inputs"].values():
                value["blanks"] = [blank for blank in value["blanks"] if blank != key]
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
        self.sample_help.setText("Check samples to move them into this group. Mark water controls as Blank."
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
        self.full_range.setEnabled(bool(values))
        self.update_view_heading()
        self.draw()

    def update_view_heading(self):
        names = self.selected_curve_names()
        text = names[0] if len(names) == 1 else f"Comparing {len(names)} groups" if names else "Select a sample group"
        count = len(self.selected_input_ids())
        if names: text += f" · {count} sample{'s' if count != 1 else ''}"
        self.view_heading.setText(text)
        self.view_heading.setToolTip("\n".join(names))

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

    def reset_ranges(self):
        state = copy.deepcopy(self.settings)
        for key in self.selected_input_ids(): state["ranges"].pop(key, None)
        self.commit(state, "INP analysis: use the full measured range for selected groups")

    def measured_limits(self):
        temperatures = {}
        for row in (self.preview or {}).get("table", {}).get("rows", []):
            key = row["measurement_id"]
            cycle = self.settings["inputs"].get(key, {}).get("cycle", "")
            if cycle and str(row["cycle_id"]) != cycle: continue
            value = number(row.get("temperature_C"))
            if math.isfinite(value): temperatures.setdefault(key, []).append(value)
        return {key: {"min_C": min(values), "max_C": max(values)} for key, values in temperatures.items()}

    def draw_ranges(self):
        if self.loading: return
        for region in self.range_items.values(): self.plot.removeItem(region)
        self.range_items.clear()
        keys = self.selected_input_ids()
        keys = [key for key in keys if key in self.range_ids]
        for row, key in enumerate(self.range_ids): self.ranges.setRowHidden(row, key not in keys)
        self.fit_table_height(self.ranges, len(keys))
        if self.tabs.currentIndex() != 1: return
        measured = self.measured_limits()
        selected = self.ranges.currentRow()
        active = self.range_ids[selected] if 0 <= selected < len(self.range_ids) else None
        if active not in keys: active = keys[0] if keys else None
        # All limits remain visible. Only the selected sample is draggable, so
        # coincident boundaries never silently edit the wrong sample.
        for key in keys:
            values = measured.get(key)
            if not values: continue
            limits = self.settings["ranges"].get(key, {})
            color = self.color(key)
            guide = QColor(color); guide.setAlpha(110 if key == active else 45)
            region = TemperatureRangeItem(
                [limits.get("min_C", values["min_C"]), limits.get("max_C", values["max_C"])],
                brush=pg.mkBrush(0, 0, 0, 0), hoverBrush=pg.mkBrush(0, 0, 0, 0),
                pen=pg.mkPen(guide, width=1, style=Qt.DashLine),
                hoverPen=pg.mkPen(color, width=1.5, style=Qt.DashLine),
                movable=key == active, swapMode="block")
            region.setZValue(12 if key == active else 10)
            for line, boundary in zip(region.lines, ("Cold", "Warm")):
                line.addMarker('^', .012, 12 if key == active else 8)
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
        if (self.result and self.result['key'] == self.calculation_key()
                and self.calculation_connection is self.client.capabilities
                and 'individual_curves' in self.result):
            self.window.log("INP analysis is already up to date; no calculation needed.")
            self.quantity.setCurrentText("Concentration")
            self.draw()
            return
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
            args = cli_choices(self.settings, suggest=suggest, selected=selected, include_individual=not suggest)
            individual = {} if suggest else concentration_curves(self.settings)[1]
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
        self.operation_started = time.perf_counter()
        self.operation_phase = "Suggesting ranges" if suggest else f"Calculating {self.method.currentText()} concentrations"
        self.operation = True; self.elapsed_timer.start(); self.update_status()
        self.window.log("INP toolkit: suggesting Average limits…" if suggest else "INP toolkit: calculating concentrations…")
        def fresh(): return generation == self.generation and key == request_key()
        def cleanup():
            source.unlink(missing_ok=True)
            if output.exists(): shutil.rmtree(output)
        def failed(message): cleanup(); self.error(message)
        def done(reply):
            toolkit_seconds = time.perf_counter() - self.operation_started
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
                       "source_hash": self.current_hash(), "toolkit_version": reply["toolkit_version"],
                       "individual_curves": individual}
            # Format 4 stores exactly the CLI table payloads in analysis.json.
            # Read once: the old table-per-curve requests reloaded and validated
            # the entire experiment repeatedly inside the toolkit.
            started = time.perf_counter()
            self.operation_phase = "Loading concentration plots"; self.show_elapsed()
            try:
                saved = (output / "analysis.json").read_text(encoding="utf-8")
                payload = json.loads(saved)
                if (payload.get('format') != 'inptk' or payload.get('format_version') != 4
                        or payload.get('kind') != 'analysis'):
                    raise ValueError("Expected an INP toolkit format 4 analysis result.")
                pending['tables'] = {name: curve['tables'] for name, curve in payload['curves'].items()}
                for name, info in reply['curves'].items():
                    for kind in info['tables']:
                        table = pending['tables'][name][kind]
                        if not isinstance(table.get('columns'), list) or not isinstance(table.get('rows'), list):
                            raise ValueError(f"Invalid {kind} table for {name}.")
                pending['saved_result'] = saved
            except (OSError, ValueError, KeyError, TypeError) as exc:
                failed(f"Could not read INP toolkit result: {exc}"); return
            self.result = pending; self.operation = False
            self.calculation_connection = self.client.capabilities
            # Select the result view before restoring controls to avoid drawing
            # both the old observations and the new concentration unnecessarily.
            self.quantity.blockSignals(True); self.table_kind.blockSignals(True)
            self.quantity.setCurrentIndex(2); self.table_kind.setCurrentText("Concentration")
            self.quantity.blockSignals(False); self.table_kind.blockSignals(False)
            self.restore_choices(self.settings)
            pending['timings'] = {'toolkit_seconds': toolkit_seconds, 'display_seconds': time.perf_counter()-started}
            self.window.log(f"INP analysis updated. Toolkit: {toolkit_seconds:.2f} s; display: {pending['timings']['display_seconds']:.2f} s.")
            cleanup()
        self.client.request(command, done, failed)

    def show_elapsed(self):
        if not self.operation:
            self.elapsed_timer.stop()
            return
        if self.operation_started is not None:
            seconds = time.perf_counter() - self.operation_started
            self.status.setText(f"{self.operation_phase}… {seconds:.0f} s")

    def show_suggestion(self, reply, *, log=True):
        lines = []
        for name, value in reply.get("inputs", {}).items():
            limits = value.get("range_C")
            lines.append(f"{name}: {limits or value.get('status')}; {value.get('kept_observations', 0)} retained. "
                         + ", ".join(value.get("cold_limit_reason", [])))
        title = "Limits applied. Adjust them in the table or plot." if reply.get("complete") else "Incomplete: no limits applied. See Table → Range suggestions."
        self.suggestion_status.setText(title)
        self.suggestion_status.setToolTip("\n".join(lines))
        if log: self.window.log("INP range suggestions: " + title + "\n" + "\n".join(lines))
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
        self.export.setToolTip("Export the last calculation for all groups. Recalculate first to include any pending changes.")
        self.calculate.setToolTip("Calculate concentrations for all sample groups using the current settings.")
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
        elif self.preview: message = "Group samples → set limits in Combine → Calculate."
        else: message = "Import temperatures and freezing counts to begin."
        self.status.setText(message)
        if busy and self.operation_started is not None: self.show_elapsed()
        if not self.operation: self.elapsed_timer.stop(); self.operation_started = None
        if self.quantity.currentText() == "Concentration":
            overlays = any(name not in self.selected_curve_names() for name, _ in self.concentration_tables('cumulative'))
            note = "Solid: combined · Dashed: individual samples" if overlays else "Concentration"
            if self.show_uncertainty.isChecked(): note += " · Shading: uncertainty"
            if self.result and 'individual_curves' not in self.result:
                note += " · Recalculate to include individual samples."
            self.plot_note.setText(note + " · ×: excluded points")
            self.plot_note.setToolTip("Individual sample curves use the same method, blank assignments, units and temperature limits as the group. Individual error widths are in Table. Log scale omits zeros; uncertainty shading needs finite positive endpoints.")
        else:
            self.plot_note.setText("Measured freezing counts, before blank correction or combining dilutions.")
            self.plot_note.setToolTip("Each line represents one sample and its selected freezing cycle.")
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

    def concentration_tables(self, kind):
        tables = self.selected_result_tables(kind)
        selected = set(self.selected_curve_names())
        # Use the last calculation's membership while edits are pending; these
        # overlays describe that result, not a new fit of the changed controls.
        members = {key for curve in (self.result or {}).get('choices', {}).get('curves', [])
                   if curve['name'] in selected and len(curve['inputs']) > 1 for key in curve['inputs']}
        for name, key in (self.result or {}).get('individual_curves', {}).items():
            if key in members and name not in selected:
                table = self.result.get('tables', {}).get(name, {}).get(kind)
                if table is not None: tables.append((name, table))
        return tables

    def concentration_style(self, name):
        sources = (self.result or {}).get('reply', {}).get('curves', {}).get(name, {}).get('sources', [])
        overlay = name not in self.selected_curve_names()
        key = sources[0]['measurement_id'] if len(sources) == 1 else name
        label = name
        if overlay:
            dilution = sources[0].get('dilution') if sources else None
            label = f"{key} · {float(dilution):g}×" if dilution is not None else key
        elif len(sources) > 1:
            label += " (combined)"
        return label, key, overlay

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
        self.show_uncertainty.setVisible(is_concentration)
        context = (quantity, logarithmic, tuple(self.selected_curve_names()), self.preview_hash,
                   (self.result or {}).get("key"), self.show_uncertainty.isChecked())
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
            for name, table in self.concentration_tables("cumulative"):
                label, color_key, overlay = self.concentration_style(name)
                groups.append((label, table["rows"], "concentration", color_key, overlay))
        else:
            by_input = {}
            for row in self.observation_rows():
                by_input.setdefault(f"{row['measurement_id']} · cycle {row['cycle_id']}", []).append(row)
            for name, rows in by_input.items():
                groups.append((name, rows, "n_frozen" if quantity == "Number frozen" else "fraction_frozen",
                               rows[0]['measurement_id'], False))
        xs, ys, totals = [], [], []
        self.visible_points = 0
        for name, rows, column, color_key, overlay in groups:
            color = self.color(color_key)
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
                curve = self.plot.plot(x, y, pen=pg.mkPen(color, width=1.5 if overlay else 2.5,
                    style=Qt.DashLine if overlay else Qt.SolidLine), symbol="o", symbolSize=4 if overlay else 5,
                    symbolBrush=color, symbolPen=color, name=name if i == 0 else None, connect="finite", data=chunk)
                # PlotDataItem owns transformed x/y for both line and symbols.
                # Only set hover options here; replacing scatter data breaks log Y.
                curve.scatter.opts.update(hoverable=True, tip=self.point_tip)
                if column == "concentration":
                    unit = str(chunk[0].get("unit", ""))
                    unit = concentration_unit(unit)
                    self.plot.setLabel("left", "Concentration", units=unit)
                    if overlay or not self.show_uncertainty.isChecked(): continue
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
            for name, table in self.concentration_tables("excluded"):
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
        else: tables = self.concentration_tables("excluded" if kind == "Excluded" else "cumulative")
        columns = list(dict.fromkeys(c for _, table in tables for c in table.get("columns", [])))
        primary = ("temperature_C", "concentration", "lower_error", "upper_error", "unit", "curve_id") if kind == "Concentration" else (
            "measurement_id", "temperature_C", "n_frozen", "n_total", "fraction_frozen", "cycle_id")
        columns = [key for key in primary if key in columns] + [key for key in columns if key not in primary]
        rows = [r for _, table in tables for r in table.get("rows", [])]
        units = set(str(row["unit"]) for row in rows if row.get("unit"))
        self.table_units.setText(concentration_unit(next(iter(units))) if len(units) == 1 else "Units vary; see Unit column" if units else "")
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
