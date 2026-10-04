"""INP analysis window. All calculations run in the external CLI."""
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
from PySide6.QtCore import Qt, Signal, QTimer, QItemSelectionModel, QSize
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPalette, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDockWidget, QFileDialog, QFormLayout, QHBoxLayout, QLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QToolButton, QVBoxLayout, QWidget, QWidgetAction, QFrame, QGroupBox, QStyledItemDelegate,
)

from icescopy_inptk_client import InptkClient
from icescopy_inptk_plot import ConcentrationAxis, PlotLegend, TemperatureRangeItem, TemperatureTags, axis_limits
from icescopy_inptk_state import cli_choices, concentration_curves, copy_choices, individual_choices, fingerprint, new_settings, number, reconcile_inputs, set_group_inputs, temperature_range
from icescopy_plot import GrayscalePlotWidget
from icescopy_inptk_data import prepare_source, upload_choices, upload_scope, PLOT_COLUMNS
from icescopy_inptk_export import concentration_csv, frozen_fraction_csv, write_csv


def concentration_unit(unit):
    return {"INP_per_mL_suspension": "INP/mL suspension", "INP_per_L_air": "INP/L air",
            "INP_per_g_dry_soil": "INP/g dry soil"}.get(unit, unit)


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
        self.setToolTip(", ".join(selected) or "Choose water blanks for this sample. Leave all assignments empty for an analysis without blanks.")

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


class InptkPanel(QWidget):
    def __init__(self, window):
        super().__init__(window, Qt.Window)
        self.setWindowTitle("INP Analysis")
        # Block source edits while retaining a regular, movable QWidget window.
        # QDialog is deliberately avoided so Enter never activates a default button.
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(1080, 740)
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
        self.hidden_plot_inputs = set()
        self.preview = None
        self.preview_hash = ""
        self.result = None
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
        self.source_revision = 0
        self.input_ref = None
        self.input_key = None
        self.live_refs = set()
        self.restored_refs = {}
        self.observations_cache = None
        self.limits_cache = None
        self.render_key = None
        self.reference_cache = None
        self.reference_plot_tables = {}
        self.suggestion_cache = None
        self.console_layout = None
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
        self.draw()
        self.show()
        self.raise_()
        self.activateWindow()
        self.ensure_connected()
        if self.client.capabilities and self.preview_hash != self.current_hash():
            self.refresh_preview()

    def closeEvent(self, event):
        if self.operation or self.client.busy:
            self.cancel_operation()
        self.restore_console()
        super().closeEvent(event)

    def show_console(self):
        """Temporarily float the existing read-only console alongside the analysis window."""
        dock = self.window.console_dock
        if self.console_layout is None:
            self.console_layout = (self.window.saveState(), self.window.dockWidgetArea(dock), dock.features())
            dock.setFeatures(QDockWidget.DockWidgetClosable)
            self.window.removeDockWidget(dock)
            dock.setParent(self, Qt.Tool)
            dock.setWindowTitle("Icescopy Console")
            dock.resize(760, 260)
            dock.move(self.geometry().center() - dock.rect().center())
        dock.show(); dock.raise_(); dock.activateWindow()

    def restore_console(self):
        if self.console_layout is None: return
        state, area, features = self.console_layout
        self.console_layout = None
        dock = self.window.console_dock
        dock.hide(); dock.setParent(self.window)
        dock.setFeatures(features)
        dock.setWindowTitle("Console")
        self.window.addDockWidget(area, dock)
        self.window.restoreState(state)

    def edit_metadata(self):
        self.close()
        self.window.show_dock_widget(self.window.sample_catalog_dock)

    def make_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)
        self.connection = QLabel()
        self.splitter = splitter = QSplitter(Qt.Horizontal)
        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(8)
        group_card = self.section()
        group_layout = QVBoxLayout(group_card)
        group_layout.setContentsMargins(10, 8, 10, 8)
        group_layout.setSpacing(6)
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
        group_layout.addLayout(row)
        self.curves = QListWidget()
        self.curves.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.curves.setAccessibleName("Sample groups to edit and display")
        self.curves.setToolTip("Select a group to edit and plot it. Select several to compare. Double-click to rename.")
        self.curves.itemSelectionChanged.connect(self.select_curve)
        self.curves.itemChanged.connect(self.rename_curve)
        group_layout.addWidget(self.curves)
        side.addWidget(group_card)
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(300)
        controls_card = self.section()
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(6, 8, 6, 6)
        controls_layout.addWidget(self.tabs)
        self.tabs.setStyleSheet("QTabWidget::pane { border: none; }")
        side.addWidget(controls_card, 1)
        splitter.addWidget(sidebar)
        splitter.setChildrenCollapsible(False)
        samples = QWidget()
        layout = QVBoxLayout(samples)
        help_text = self.sample_help = QLabel()
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.inputs = QTableWidget(0, 5)
        self.inputs.setHorizontalHeaderLabels(["Use", "Sample", "Dilution", "Blank", "Show"])
        self.inputs.setAccessibleName("Sample membership, dilution, blank roles and plot visibility")
        self.inputs.horizontalHeaderItem(4).setToolTip("Show this sample in the plot. Does not change calculation membership or exports.")
        self.inputs.horizontalHeaderItem(0).setToolTip("Check to move a sample into the selected group.")
        self.inputs.horizontalHeaderItem(3).setToolTip("Mark a water-control sample, then assign it under Blank correction.")
        self.inputs.verticalHeader().hide()
        self.inputs.setShowGrid(False)
        self.inputs.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.inputs.setAlternatingRowColors(True)
        self.inputs.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.inputs.setSelectionMode(QAbstractItemView.SingleSelection)
        self.inputs.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.inputs.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.inputs.setColumnWidth(1, 130)
        self.inputs.itemChanged.connect(self.input_changed)
        self.inputs.itemSelectionChanged.connect(self.select_input)
        layout.addWidget(self.inputs, 1)
        self.show_combined = QCheckBox("Show combined curve")
        self.show_combined.setChecked(True)
        self.show_combined.setToolTip("Show the combined concentration for the selected groups. Calculations and exports are unchanged.")
        self.show_combined.toggled.connect(self.draw)
        layout.addWidget(self.show_combined)
        cycle_row = QHBoxLayout()
        self.cycle_label = QLabel("Cycle")
        self.input_cycle = QComboBox()
        self.input_cycle.setAccessibleName("Freezing cycle for the selected sample")
        self.input_cycle.setToolTip("Choose the freezing cycle used for this sample. Repeated cycles are not pooled.")
        self.input_cycle.currentIndexChanged.connect(
            lambda: self.change_input_cycle(self.current_input(), self.input_cycle.currentData()))
        cycle_row.addWidget(self.cycle_label)
        cycle_row.addWidget(self.input_cycle, 1)
        layout.addLayout(cycle_row)
        self.blank_box = QGroupBox("Blank correction")
        self.blank_box.setFlat(False)
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
        layout.addWidget(self.heading("Calculation"))
        form = QFormLayout()
        self.method = QComboBox()
        self.method.addItem("MLE", "mle")
        self.method.setToolTip("MLE maximizes the likelihood of the measured freezing counts, fitting samples and assigned water blanks together.")
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
        label = QLabel("Select a sample row or curve. Drag its tags below the plot, or enter limits here.")
        label.setToolTip("Both endpoints are included. Each sample has its own limits.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.ranges = QTableWidget(0, 3)
        self.ranges.setHorizontalHeaderLabels(["Sample", "Cold (°C)", "Warm (°C)"])
        self.ranges.setAccessibleName("Temperature limits for each selected sample")
        self.ranges.setToolTip("Select a sample row or click its curve to show its two drag tags below the plot. You can also type limits here.")
        for col in (1, 2): self.ranges.setItemDelegateForColumn(col, RangeLimitDelegate(self.ranges))
        self.ranges.verticalHeader().hide()
        self.ranges.setShowGrid(False)
        self.ranges.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ranges.setAlternatingRowColors(True)
        self.ranges.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.ranges.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.ranges.setColumnWidth(0, 130)
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
        self.full_range.setToolTip("Use each sample's measured cold limit and a warm limit of 0 °C.")
        self.full_range.clicked.connect(self.reset_ranges)
        range_actions = QHBoxLayout()
        range_actions.addWidget(self.suggest)
        range_actions.addWidget(self.full_range)
        layout.addLayout(range_actions)
        self.suggestion_status = QLabel("Automatic limits are available for Average; MLE limits are manual.")
        self.suggestion_status.setWordWrap(True)
        help_font = QFont(self.font())
        if help_font.pointSizeF() > 0:
            help_font.setPointSizeF(max(10, help_font.pointSizeF() - 1))
        self.suggestion_status.setFont(help_font)
        layout.addWidget(self.suggestion_status)
        layout.addSpacing(6)
        self.method_help = QLabel()
        self.method_help.setFont(help_font)
        self.method_help.setWordWrap(True)
        self.method_help.setTextFormat(Qt.RichText)
        self.method_help.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.method_help)
        self.method_details_button = QToolButton()
        self.method_details_button.setFont(help_font)
        self.method_details_button.setAutoRaise(True)
        self.method_details_button.setText("Equations and uncertainty")
        self.method_details_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.method_details_button.setIconSize(QSize(10, 10))
        self.method_details_button.setArrowType(Qt.RightArrow)
        self.method_details_button.setCheckable(True)
        self.method_details_button.setAccessibleName("Equations and uncertainty")
        self.method_details_button.setToolTip("Show equations and confidence-limit details")
        # macOS ignores autoRaise outside a toolbar. Remove just this control's
        # button chrome while retaining Qt's keyboard and checked-state behavior.
        self.method_details_button.setStyleSheet("""
            QToolButton { background: transparent; border: none;
                          border-bottom: 1px solid transparent; padding: 4px 0; }
            QToolButton:hover { color: palette(link); }
            QToolButton:focus { color: palette(link);
                                border-bottom: 1px dotted palette(link); }
        """)
        layout.addWidget(self.method_details_button, alignment=Qt.AlignLeft)
        self.method_details = QLabel()
        self.method_details.setFont(help_font)
        self.method_details.setTextFormat(Qt.RichText)
        self.method_details.setWordWrap(True)
        self.method_details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.method_details.hide()
        self.method_details_button.toggled.connect(self.toggle_method_details)
        layout.addWidget(self.method_details)
        layout.addStretch(1)
        self.add_control_tab(combine, "Combine")

        advanced = QWidget()
        layout = QVBoxLayout(advanced)
        layout.addWidget(self.heading("Count selection"))
        self.grid_enabled = QCheckBox("Use a temperature grid")
        self.grid_enabled.toggled.connect(self.toggle_grid)
        layout.addWidget(self.grid_enabled)
        note = QLabel("Default grid: 0 to −35 °C in 0.5 °C steps. Turn off to use measured temperatures.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.grid_controls = QWidget()
        form = self.grid_form = QFormLayout(self.grid_controls)
        form.setContentsMargins(0, 0, 0, 0)
        self.grid_step = self.option_edit("grid_step", "Off")
        self.grid_start = self.option_edit("grid_start", "")
        self.grid_end = self.option_edit("grid_end", "")
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
        layout.addWidget(self.heading("Concentration"))
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

        view = self.section()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        self.view_heading = self.heading("")
        self.view_heading.setWordWrap(True)
        layout.addWidget(self.view_heading)
        plot_page = QWidget()
        plot_layout = QVBoxLayout(plot_page)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(6)
        controls = QHBoxLayout()
        self.quantity = QComboBox()
        self.quantity.addItems(["Number frozen", "Fraction frozen", "Concentration"])
        self.quantity.setAccessibleName("Plotted quantity")
        self.quantity.setCurrentIndex(1)
        self.quantity.currentIndexChanged.connect(self.draw)
        self.show_uncertainty = QCheckBox("Uncertainty")
        self.show_uncertainty.setChecked(True)
        self.show_uncertainty.setToolTip("Show confidence limits for the combined result and individual samples, and fit the axes to them. Exported values are unchanged.")
        self.show_uncertainty.toggled.connect(self.draw)
        self.fit_button = QPushButton("Fit axes")
        self.fit_button.clicked.connect(self.fit_plot)
        controls.setSpacing(16)
        controls.addWidget(self.quantity)
        controls.addWidget(self.show_uncertainty)
        controls.addStretch(1)
        controls.addWidget(self.fit_button)
        plot_layout.addLayout(controls)
        self.plot = pg.PlotWidget(axisItems={'left': ConcentrationAxis('left')})
        self.plot.setBackground(self.palette().color(QPalette.Base))
        self.plot.getAxis('left').setWidth(100)
        for side in ("left", "bottom"):
            self.plot.getAxis(side).setStyle(maxTickLevel=1)
            self.plot.getAxis(side).setTickDensity(.6)
        self.plot.setLabel("bottom", "Temperature", units="°C")
        self.legend_view = PlotLegend(self.plot, f"{max(10, help_font.pointSizeF()):g}pt")
        self.legend = self.legend_view.legend
        self.plot.getPlotItem().legend = self.legend
        self.empty_plot = QLabel()
        self.empty_plot.setWordWrap(True)
        self.empty_plot.setAlignment(Qt.AlignCenter)
        self.empty_plot.setMargin(20)
        plot_layout.addWidget(self.empty_plot)
        chart_column = QVBoxLayout()
        chart_column.setSpacing(0)
        chart_column.addWidget(self.plot, 1)
        self.range_tags = TemperatureTags(self.plot)
        self.range_tags.activated.connect(self.activate_range)
        self.range_tags.moved.connect(self.tag_moved)
        chart_column.addWidget(self.range_tags)
        plot_layout.addLayout(chart_column, 1)
        self.plot_note = QLabel()
        self.plot_note.setWordWrap(True)
        plot_layout.addWidget(self.plot_note)
        layout.addWidget(plot_page, 1)
        splitter.addWidget(view)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 720])
        outer.addWidget(splitter, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.connection)
        outer.addLayout(status_row)
        bottom = QHBoxLayout()
        self.console_button = QPushButton("Show console")
        self.console_button.clicked.connect(self.show_console)
        bottom.addWidget(self.console_button)
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
        self.export = QPushButton("Export results")
        menu = QMenu(self.export)
        menu.setToolTipsVisible(True)
        self.export_scope_label = QLabel("All groups")
        self.export_scope_label.setTextFormat(Qt.PlainText)
        self.export_scope_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.export_scope_label.setContentsMargins(12, 4, 12, 4)
        self.export_scope_action = QWidgetAction(menu)
        self.export_scope_action.setDefaultWidget(self.export_scope_label)
        self.export_scope_action.setEnabled(False)
        menu.addAction(self.export_scope_action)
        native = menu.addAction("Save .inptk session…", self.export_result)
        native.setToolTip("Save the complete toolkit result as an .inptk folder. Save the .icescopy session to retain the Icescopy controls as well.")
        menu.addSeparator()
        fractions = menu.addAction("Export frozen fraction CSV…", lambda: self.export_csv('frozen_fraction'))
        fractions.setToolTip("Sample columns on the calculation grid, including selected water blanks. Selecting a plot group does not limit this export.")
        self.concentration_export_action = menu.addAction("Export combined concentration CSV…", lambda: self.export_csv())
        self.concentration_export_action.setToolTip("Temperature rows with concentration and lower/upper uncertainty bounds per combined group. Includes all calculated groups, using their saved units.")
        self.individual_export_action = menu.addAction("Export individual sample concentrations CSV…", lambda: self.export_csv('individual'))
        self.individual_export_action.setToolTip("Temperature rows with concentration and lower/upper uncertainty bounds per individual sample/dilution. Uses full-range fits in the saved units.")
        menu.aboutToShow.connect(self.update_export_menu)
        self.export.setMenu(menu)
        for widget in (self.calculate, self.cancel, self.export): bottom.addWidget(widget)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        # Enter commits a field; it must not accidentally run or close analysis.
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
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
    def section():
        card = QFrame()
        card.setObjectName("inpSection")
        palette = card.palette()
        palette.setColor(QPalette.Window, palette.color(QPalette.Base))
        card.setPalette(palette)
        card.setAutoFillBackground(True)
        card.setStyleSheet("QFrame#inpSection { background: palette(base); border: 1px solid palette(midlight); border-radius: 6px; }")
        return card

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
        widget.layout().setSizeConstraint(QLayout.SetMinimumSize)
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

    def toggle_method_details(self, visible):
        self.method_details.setVisible(visible)
        self.method_details_button.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)
        self.method_details_button.setToolTip(
            "Hide equations and confidence-limit details" if visible else
            "Show equations and confidence-limit details")

    def update_method_help(self):
        text_size = self.method_details.font().pointSizeF()
        if text_size <= 0: text_size = 12
        paragraph = 'margin-top:0; margin-bottom:8px; line-height:130%;'
        def prose(text):
            return f'<p style="{paragraph}">{text}</p>'
        def section(title, formula):
            return (f'<p style="margin-top:12px; margin-bottom:4px;"><b>{title}</b></p>'
                    f'<p align="center" style="margin-top:6px; margin-bottom:10px; '
                    f'font-size:{text_size + 1.5:g}pt;">{formula}</p>')
        common = (
            section('Freezing model', '<i>S</i> = e<sup>−<i>v</i>(<i>K</i>/<i>D</i> + <i>B</i>)</sup>') +
            '<table width="100%" cellspacing="0" cellpadding="2">' +
            ''.join(f'<tr><td width="24" valign="top"><i>{symbol}</i></td><td>{meaning}</td></tr>'
                    for symbol, meaning in (
                        ('S', 'Fraction of droplets still liquid'),
                        ('v', 'Well volume (mL)'),
                        ('D', 'Dilution factor'),
                        ('K', 'Original suspension concentration <nobr>(INP/mL)</nobr>'),
                        ('B', 'Assigned blank concentration <nobr>(INP/mL)</nobr>'))) +
            '</table>' +
            prose('A water blank uses <i>S</i> = e<sup>−<i>vB</i></sup>. '
                  'Without blank correction, <i>B</i> = 0.')
        )
        if self.settings['method'] == 'mle':
            self.method_help.setText(
                prose('<b>Maximum likelihood (MLE)</b>') +
                prose('Maximizes the probability of the measured freezing counts, fitting samples and '
                      'assigned water blanks together. Uses additional droplets frozen between '
                      'temperature readings and the final liquid count.'))
            detail = (
                section('Additional frozen droplets at each step',
                        '<i>n</i><sub>new</sub> = <i>F</i><sub>now</sub> − <i>F</i><sub>previous</sub>'
                        '<br><i>p</i><sub>new</sub> = <i>S</i><sub>previous</sub> − <i>S</i><sub>now</sub>') +
                prose('<i>F</i> is the measured number already frozen. <i>S</i> is the predicted liquid '
                      'fraction. <i>n</i><sub>new</sub> counts the additional frozen droplets; '
                      '<i>p</i><sub>new</sub> is the model probability of freezing in that interval.') +
                section('What MLE maximizes',
                        'ℓ = Σ[<i>n</i><sub>new</sub> ln(<i>p</i><sub>new</sub>)]'
                        '<br>+ Σ[<i>n</i><sub>liquid</sub> ln(<i>S</i><sub>end</sub>)]') +
                prose('ℓ is the log likelihood; ln is the natural logarithm. The first sum covers all '
                      'temperature intervals. The second uses the number still liquid at the end of '
                      'each sample or blank. Counts that are zero contribute zero. Terms constant '
                      'during fitting are omitted.') +
                prose('For the first reading, <i>F</i><sub>previous</sub> = 0 and '
                      '<i>S</i><sub>previous</sub> = 1, so droplets already frozen are included. '
                      'Within each cycle, each droplet contributes once: to one freezing interval or '
                      'to the final liquid count. <i>K</i> and <i>B</i> cannot decrease during cooling; '
                      'each shared blank history is counted once.') +
                section('Confidence limits', 'ℓ<sub>best</sub> − ℓ<sub>test</sub> '
                        '= <i>z</i><sup>2</sup>/2') +
                prose('ℓ<sub>best</sub> is the best-fit log likelihood. To test a concentration '
                      '<i>K</i> at one temperature, the toolkit refits all other curve values and '
                      'blank background to obtain ℓ<sub>test</sub>. The confidence boundaries are where '
                      'the log likelihood drops by 1.92 with the default <i>z</i> = 1.96 '
                      '(approximate 95% limits).')
            )
        else:
            self.method_help.setText(
                prose('<b>Average</b>') +
                prose('Fits each sample with its assigned blanks, then takes an equal-weight mean where '
                      'ranges overlap. A single eligible sample contributes its own estimate.'))
            detail = (
                section('Equal-weight mean', '<i>K</i><sub>mean</sub> = (<i>K</i><sub>1</sub> + … + '
                        '<i>K</i><sub>m</sub>)/<i>m</i>') +
                prose('<i>m</i> is the number of eligible samples at that temperature. Each estimate uses '
                      'the sample’s frozen and total counts, well volume, dilution and assigned blanks.') +
                section('Individual estimate without blanks',
                        '<i>K</i><sub>i</sub> = −<i>D</i><sub>i</sub> ln(1 − <i>f</i><sub>i</sub>)/<i>v</i><sub>i</sub>') +
                prose('<i>f</i> is fraction frozen. This expression applies below 100% frozen.') +
                section('Confidence limits', 'α = 2[1 − Φ(<i>z</i>)]; &nbsp; α<sub>i</sub> = α/<i>m</i>') +
                prose('Φ is the standard normal cumulative probability. Dividing the error probability '
                      'α among the samples widens their likelihood intervals (the Bonferroni adjustment). '
                      'The toolkit then averages the lower and upper endpoints:') +
                section('Combined interval', '<i>L</i> = (<i>L</i><sub>1</sub> + … + <i>L</i><sub>m</sub>)/<i>m</i>'
                        '<br><i>U</i> = (<i>U</i><sub>1</sub> + … + <i>U</i><sub>m</sub>)/<i>m</i>') +
                prose('These conservative limits allow for shared blanks. Adding samples may not narrow them.')
            )
        self.method_details.setText(common + detail +
            f'<p style="{paragraph} font-size:{max(10, text_size - 1):g}pt;">'
            'Limits are approximate and apply at each temperature. They depend on the chosen ranges '
            'and do not include uncertainty from automatic range selection. Air or soil conversion '
            'scales concentrations and both limits using the sample metadata.</p>')

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
        before = copy_choices(self.settings)
        self.restore_choices(choices)
        self.undo_stack.push(InpSettingsCommand(self, label, before, copy_choices(choices)))
        self.window.log(label)

    def change_option(self, key, value):
        if self.loading: return
        if key in {'grid_start', 'grid_end'} and not value.strip():
            value = {'grid_start': '0', 'grid_end': '-35'}[key]
            # Restore the actual text even when the setting was already the
            # default, so the no-change path cannot leave an empty field.
            getattr(self, key).setText(value)
        state = copy_choices(self.settings); state[key] = value
        self.commit(state, f"INP analysis: change {key.replace('_', ' ')} to {value}")

    def toggle_grid(self, enabled):
        self.change_option("grid_step", (self.grid_step.text().strip() or "0.5") if enabled else "")

    def restore_choices(self, choices):
        self.loading = True
        choices = dict(choices)
        for key, default in (('grid_start', '0'), ('grid_end', '-35')):
            if not choices.get(key, '').strip(): choices[key] = default
        # Renaming does not change any measured counts. Avoid rebuilding their
        # potentially long plot or the controls while an inline edit commits.
        def without_group_names(state):
            state = copy_choices(state)
            for curve in state["curves"]: curve.pop("name", None)
            for value in state["inputs"].values(): value.pop("group", None)
            return state
        rename_only = (self.settings["curves"] != choices["curves"]
                       and without_group_names(self.settings) == without_group_names(choices))
        if (rename_only and self.quantity.currentText() != "Concentration"
                and self.plot_context and self.plot_context[3] == self.preview_hash):
            self.settings = copy_choices(choices)
            for i, curve in enumerate(choices["curves"]): self.curves.item(i).setText(curve["name"])
            self.loading = False
            if self.plot_context:
                values = list(self.plot_context); values[2] = tuple(self.selected_curve_names())
                self.plot_context = tuple(values)
                if self.render_key:
                    self.render_key = (self.plot_context, *self.render_key[1:])
            self.update_view_heading()
            self.update_status()
            return
        self.settings = copy_choices(choices)
        self.update_method_help()
        old_input = self.current_input()
        old_curve = self.curves.currentRow()
        selected_names = set(self.selected_curve_names())
        range_row = self.ranges.currentRow()
        old_range = self.range_ids[range_row] if 0 <= range_row < len(self.range_ids) else None
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
            factor = number(metadata.get("dilution"))
            dilution = QTableWidgetItem(f"{factor:g}×" if math.isfinite(factor) else "")
            dilution.setFlags(dilution.flags() & ~Qt.ItemIsEditable)
            self.inputs.setItem(row, 2, dilution)
            blank = QTableWidgetItem(); blank.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            blank.setCheckState(Qt.Checked if values["blank"] else Qt.Unchecked)
            self.inputs.setItem(row, 3, blank)
            shown = QTableWidgetItem()
            shown.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            shown.setCheckState(Qt.Unchecked if key in self.hidden_plot_inputs else Qt.Checked)
            shown.setToolTip(f"Show {key} in plots only; calculation membership and exports are unchanged.")
            self.inputs.setItem(row, 4, shown)
        self.refresh_sample_table_columns()
        self.fit_table_height(self.inputs, len(self.input_ids))
        # Reserve a scrollbar row so wide metadata does not obscure sample rows.
        self.inputs.setFixedHeight(self.inputs.height() + self.inputs.horizontalScrollBar().sizeHint().height())
        if self.input_ids: self.inputs.selectRow(self.input_ids.index(old_input) if old_input in self.input_ids else 0)
        self.curves.clear()
        for curve in self.settings["curves"]:
            item = QListWidgetItem(curve["name"]); item.setFlags(item.flags() | Qt.ItemIsEditable)
            item.setToolTip("\n".join(curve["inputs"]) or "No samples yet. Check samples below to add them.")
            self.curves.addItem(item)
        row_height = self.curves.sizeHintForRow(0) if self.curves.count() else self.curves.fontMetrics().height() + 4
        self.curves.setFixedHeight(min(4, max(1, self.curves.count())) * row_height + 2 * self.curves.frameWidth() + 4)
        for row in range(self.curves.count()):
            self.curves.item(row).setSelected(self.curves.item(row).text() in selected_names)
        if self.curves.count() and not self.curves.selectedItems():
            self.curves.setCurrentRow(max(0, min(old_curve, self.curves.count()-1)), QItemSelectionModel.ClearAndSelect)
        self.range_ids = [key for key, value in self.settings["inputs"].items() if not value["blank"]]
        self.ranges.setRowCount(len(self.range_ids))
        measured = self.full_range_limits()
        for row, key in enumerate(self.range_ids):
            item = QTableWidgetItem(key); item.setFlags(item.flags() & ~Qt.ItemIsEditable); item.setData(Qt.DecorationRole, self.color(key))
            self.ranges.setItem(row, 0, item)
            for col, limit in ((1, "min_C"), (2, "max_C")):
                value = self.settings["ranges"].get(key, {}).get(limit)
                # Only the display is rounded. Choices and drag positions retain
                # their original values until the user explicitly edits a limit.
                item = QTableWidgetItem(f"{number(value):.2f}" if value is not None else "")
                endpoint = measured.get(key, {}).get(limit)
                item.setData(Qt.UserRole, f"{endpoint:.2f}" if endpoint is not None else "Auto")
                item.setToolTip("Displayed to two decimal places; stored limits retain their original precision. Clear this field to use the measured cold limit or a warm limit of 0 °C. Both endpoints are included.")
                item.setData(Qt.AccessibleTextRole, item.text() or f"Full-range limit: {item.data(Qt.UserRole)} °C")
                self.ranges.setItem(row, col, item)
        if self.range_ids:
            self.ranges.selectRow(self.range_ids.index(old_range) if old_range in self.range_ids else 0)
        self.refresh_sample_table_columns()
        self.loading = False
        if self.settings.get("suggestion"):
            self.show_suggestion(self.settings["suggestion"], log=False)
        else:
            self.suggestion_status.setText("Auto range uses the minimum counts above." if self.settings["method"] == "average" else "MLE uses manual limits, or the full range.")
        # Refreshing controls after a range edit must not reselect the last row
        # clicked in the separate Samples table. Preserve the active range by ID.
        self.select_input(sync_range=False); self.select_curve(); self.update_status()

    def refresh_sample_table_columns(self):
        """Read catalog fields by saved sample ID, without changing toolkit input."""
        selected = set(self.window.inptk_sample_columns)
        schema = self.window.active_sample_metadata_schema()
        records = self.window.freeze_count_timeseries_summary.get('sample_column_metadata', [])
        identifiers = [name[:-len(' number total')] for name in self.window.freeze_count_timeseries_headers
                       if name.endswith(' number total')]
        metadata = dict(zip(identifiers, records))
        self.inputs.setColumnHidden(2, 'dilution' not in selected)
        for table, keys, first_column, fixed_fields in (
            (self.inputs, self.input_ids, 5, {'sample_name', 'dilution'}),
            (self.ranges, self.range_ids, 3, {'sample_name'}),
        ):
            extra = [field for field in schema if field['key'] in selected and field['key'] not in fixed_fields]
            blocked = table.blockSignals(True)
            table.setColumnCount(first_column + len(extra))
            for column, field in enumerate(extra, first_column):
                header = QTableWidgetItem(field['label']); header.setToolTip(field['label'])
                table.setHorizontalHeaderItem(column, header)
                table.horizontalHeader().setSectionResizeMode(column, QHeaderView.Interactive)
                table.setColumnWidth(column, min(200, max(110, table.fontMetrics().horizontalAdvance(field['label']) + 24)))
                for row, key in enumerate(keys):
                    values = dict(metadata.get(key, {}))
                    sample_id = str(values.get('sample_id', '')).strip()
                    if sample_id:
                        values.update(self.window.sample_record_for_id(sample_id))
                    value = str(values.get(field['key'], '') or '')
                    if field['key'] == 'dilution' and math.isfinite(number(value)):
                        value = f"{number(value):g}×"
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setToolTip(value)
                    table.setItem(row, column, item)
            table.blockSignals(blocked)

    def current_input(self):
        row = self.inputs.currentRow()
        return self.input_ids[row] if 0 <= row < len(self.input_ids) else None

    def select_input(self, *, sync_range=True):
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
            message = "Choose a blank for this sample, or leave all assignments empty for analysis without blanks."
        else:
            message = ""
        self.blank_help.setText(message)
        self.blank_help.setVisible(bool(message))
        if sync_range and key in self.range_ids: self.ranges.selectRow(self.range_ids.index(key))

    def input_changed(self, item):
        if self.loading: return
        key = self.input_ids[item.row()]
        if item.column() == 4:
            if item.checkState() == Qt.Checked: self.hidden_plot_inputs.discard(key)
            else: self.hidden_plot_inputs.add(key)
            self.draw()
            return
        state = copy_choices(self.settings)
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
        state = copy_choices(self.settings); state["inputs"][key]["cycle"] = cycle
        self.commit(state, f"INP analysis: select cycle {cycle} for {key}")

    def change_blanks(self, values):
        key = self.current_input()
        if not key: return
        state = copy_choices(self.settings); state["inputs"][key]["blanks"] = values
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
        help_text = ("Check samples to move them into this group. Mark water controls as Blank."
                     if row >= 0 else "Select one group to edit its samples, or several groups to compare their plots.")
        if any(len(m.get("cycle_ids", [])) > 1 for m in (self.preview or {}).get("measurements", [])):
            help_text += " Select a sample row to choose its freezing cycle below the table."
        help_text += " Show controls plot visibility only."
        self.sample_help.setText(help_text)
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
        state = copy_choices(self.settings)
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
        state = copy_choices(self.settings)
        state["curves"] = [c for c in state["curves"] if c["name"] not in names]
        self.commit(state, "INP analysis: remove sample group")

    def rename_curve(self, item):
        if self.loading: return
        name = item.text().strip()
        row = self.curves.row(item)
        if not name or any(c["name"] == name for i, c in enumerate(self.settings["curves"]) if i != row):
            self.loading = True; item.setText(self.settings["curves"][row]["name"]); self.loading = False
            self.error("Use a unique, nonempty sample group name."); return
        state = copy_choices(self.settings)
        previous = state["curves"][row]["name"]
        state["curves"][row]["name"] = name
        # Names label the group; physical input identities and memberships stay.
        for values in state["inputs"].values():
            if values["group"] == previous: values["group"] = name
        self.commit(state, f"INP analysis: rename group {previous} to {name}")

    def range_changed(self, item):
        if self.loading or item.column() not in (1, 2): return
        key = self.range_ids[item.row()]; state = copy_choices(self.settings)
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
        state = copy_choices(self.settings)
        for key in self.selected_input_ids(): state["ranges"].pop(key, None)
        self.commit(state, "INP analysis: use the full freezing range through 0 °C for selected groups")

    def full_range_limits(self):
        cache_key = (id(self.preview), self.preview_hash, tuple((k, v['cycle']) for k, v in self.settings['inputs'].items()))
        if self.limits_cache and self.limits_cache[0] == cache_key:
            return self.limits_cache[1]
        temperatures = {}
        for row in (self.preview or {}).get("table", {}).get("rows", []):
            key = row["measurement_id"]
            cycle = self.settings["inputs"].get(key, {}).get("cycle", "")
            if cycle and str(row["cycle_id"]) != cycle: continue
            value = number(row.get("temperature_C"))
            if math.isfinite(value):
                lo, hi = temperatures.get(key, (value, value))
                temperatures[key] = (min(lo, value), max(hi, value))
        result = {key: {"min_C": min(values[0], 0.), "max_C": 0.} for key, values in temperatures.items()}
        self.limits_cache = (cache_key, result)
        return result

    def draw_ranges(self):
        if self.loading: return
        for region in self.range_items.values(): self.plot.removeItem(region)
        self.range_items.clear()
        keys = self.selected_input_ids()
        keys = [key for key in keys if key in self.range_ids]
        for row, key in enumerate(self.range_ids): self.ranges.setRowHidden(row, key not in keys)
        self.fit_table_height(self.ranges, len(keys))
        if self.ranges.columnCount() > 3:
            self.ranges.setFixedHeight(self.ranges.height() + self.ranges.horizontalScrollBar().sizeHint().height())
        if self.tabs.currentIndex() != 1:
            self.range_tags.set_entries([])
            return
        measured = self.full_range_limits()
        selected = self.ranges.currentRow()
        active = self.range_ids[selected] if 0 <= selected < len(self.range_ids) else None
        if active not in keys:
            active = keys[0] if keys else None
            if active is not None:
                blocked = self.ranges.blockSignals(True)
                self.ranges.selectRow(self.range_ids.index(active))
                self.ranges.blockSignals(blocked)
        # All limits remain visible. Only the selected sample is draggable, so
        # coincident boundaries never silently edit the wrong sample.
        tags = []
        for key in keys:
            if key in self.hidden_plot_inputs: continue
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
                line.setToolTip(f"{key} — {boundary} limit (°C)")
            region.sigRegionChanged.connect(lambda _region, key=key, region=region: self.range_dragged(key, region))
            region.sigRegionChangeFinished.connect(lambda _region, key=key, region=region: self.range_finished(key, region))
            self.range_items[key] = region
            self.plot.addItem(region, ignoreBounds=True)
            tags.append((key, region.getRegion(), color, key == active))
        self.range_tags.set_entries(tags)

    def activate_range(self, key):
        if key in self.range_ids:
            self.ranges.selectRow(self.range_ids.index(key))

    def make_sample_clickable(self, curve, key):
        if key not in self.range_ids or self.settings['inputs'].get(key, {}).get('blank'):
            return
        curve.setCurveClickable(True, width=10)
        curve.setProperty('inp_sample', key)
        curve.sigClicked.connect(lambda *_args, key=key: self.activate_range(key))

    def tag_moved(self, key, boundary, value, finished):
        region = self.range_items.get(key)
        if region is None: return
        limits = list(region.getRegion())
        limits[boundary] = min(value, limits[1]) if boundary == 0 else max(value, limits[0])
        region.blockSignals(True)
        region.setRegion(limits)
        region.blockSignals(False)
        self.range_dragged(key, region)
        if finished:
            self.range_finished(key, region)

    def range_dragged(self, key, region):
        if self.range_items.get(key) is not region: return
        self.loading = True
        try:
            cold, warm = region.getRegion()
            row = self.range_ids.index(key)
            self.ranges.selectRow(row)
            self.ranges.item(row, 1).setText(f"{cold:.2f}")
            self.ranges.item(row, 2).setText(f"{warm:.2f}")
        finally: self.loading = False
        self.range_tags.set_entries([
            (k, self.range_items[k].getRegion() if k in self.range_items else limits, color, k == key)
            for k, limits, color, _active in self.range_tags.entries])

    def range_finished(self, key, region):
        if self.range_items.get(key) is not region: return
        cold, warm = region.getRegion()
        state = copy_choices(self.settings); state["ranges"][key] = {"min_C": cold, "max_C": warm}
        self.commit(state, f"INP analysis: move temperature limits for {key}")

    def current_hash(self):
        w = self.window
        if (not w.freeze_count_timeseries_headers or not w.freeze_count_timeseries_rows
                or w.freeze_count_timeseries_summary.get('analysis_required')):
            return ''
        return self.source_cache['hash'] if self.source_cache else f'pending:{self.source_revision}'

    def calculation_key(self):
        # Suggested limits affect calculation only once applied. Changing the
        # suggestion thresholds/report alone does not change a fitted result.
        choices = {k: v for k, v in self.settings.items()
                   if k not in {"suggestion", "min_frozen", "min_unfrozen"}}
        # Include effective defaults so a saved fit made before the 0 °C
        # freezing limit is marked stale, rather than silently reused.
        choices['ranges'] = {key: temperature_range(self.settings, key)
                             for key, value in self.settings['inputs'].items() if not value['blank']}
        if self.settings['grid_step'].strip():
            choices['grid_start'] = self.settings['grid_start'].strip() or '0'
            choices['grid_end'] = self.settings['grid_end'].strip() or '-35'
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
        self.reference_cache = None
        self.suggestion_cache = None
        self.input_ref = self.input_key = None
        self.live_refs.clear(); self.restored_refs.clear()
        self.window.log(f"INP toolkit connected: {reply['toolkit_version']} (protocol 2)")
        after, self.after_connect = self.after_connect, None
        # Calculation callbacks validate/refresh their own source. A saved
        # result can be exported even when current counts are missing or stale.
        if after: after()
        else: self.refresh_preview()

    def refresh_preview(self, _checked=False, after=None):
        if self.operation or self.client.busy: return
        if not self.client.capabilities:
            self.ensure_connected(after=lambda: self.refresh_preview(after=after)); return
        if not self.current_hash():
            self.error('Import temperatures and run freezing analysis before INP analysis.'); return
        # Copy the current table once. Preparation and hashing run on the worker;
        # no CSV is serialized, parsed or written for analysis.
        headers = tuple(self.window.freeze_count_timeseries_headers)
        rows = tuple(tuple(row) for row in self.window.freeze_count_timeseries_rows)
        metadata = [dict(row) for row in self.window.freeze_count_timeseries_summary.get('sample_column_metadata', [])]
        revision, generation = self.source_revision, self.generation
        self.last_error = ''; self.operation = True; self.update_status()
        def done(source):
            self.operation = False
            if generation != self.generation or revision != self.source_revision:
                self.update_status(); return
            self.source_cache = source
            self.preview, self.preview_hash = source['preview'], source['hash']
            self.observations_cache = self.limits_cache = None
            state = reconcile_inputs(self.settings, self.preview)
            if not self.settings['inputs'] and not state['curves']:
                state['curves'] = [{'name': key, 'inputs': [key]} for key in state['inputs']]
            self.restore_choices(state)
            self.window.log('INP analysis: counts and fractions updated.')
            if after: after()
        self.client.compute(lambda: prepare_source(headers, rows, metadata), done, self.error)

    def ensure_input(self, settings, callback, failed, *, selected=None):
        mapping = upload_scope(settings, selected=selected)
        key = fingerprint([self.current_hash(), mapping])
        if self.input_key == key and self.input_ref in self.live_refs:
            callback(self.input_ref); return
        reference = '@input-' + uuid.uuid4().hex
        source = self.source_cache
        def uploaded(reply):
            self.live_refs.add(reference)
            self.input_ref, self.input_key = reference, key
            callback(reference)
        def prepared(payload):
            self.client.request_body({'import': dict(payload, out=reference)}, uploaded, failed)
        self.client.compute(lambda: upload_choices(source, settings, selected=selected), prepared, failed)

    def release_unused(self, *, keep=()):
        retained = {self.input_ref, *keep}
        if self.result:
            retained.add(self.result_reference(self.result))
            retained.add(self.result_reference(self.result.get('references') or {}))
        unused = sorted(self.live_refs - retained)
        if not unused or not self.client.capabilities: return
        def released(_reply): self.live_refs.difference_update(unused)
        self.client.request_body({'release': unused}, released, self.error)

    def read_plot_tables(self, reference, reply, callback, failed):
        tasks = [(name, kind) for name, info in reply['curves'].items()
                 for kind in ('cumulative', 'excluded') if kind in info['tables']]
        tables = {name: {} for name in reply['curves']}
        def next_table():
            if not tasks: callback(tables); return
            name, kind = tasks.pop(0)
            def received(value):
                tables[name][kind] = value['table']; next_table()
            self.client.request(['table', reference, '--curve', name, '--table', kind,
                '--no-history', '--columns', *PLOT_COLUMNS], received, failed)
        next_table()

    def recalculate(self):
        if self.operation or self.client.busy: return
        self.export_notice = None
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
        try:
            key = self.range_suggestion_key()
        except (ValueError, TypeError) as exc:
            self.error(str(exc)); return
        if self.suggestion_cache and self.suggestion_cache[0] == key:
            report = self.suggestion_cache[1]
            state = copy_choices(self.settings)
            state['suggestion'] = report
            if report.get('complete'): state['ranges'].update(report['temperature_ranges_C'])
            self.commit(state, "INP analysis: reapply unchanged range suggestions")
            self.show_suggestion(report)
            return
        self.run_calculation(True)

    def range_suggestion_key(self):
        row = self.single_curve_row()
        if row < 0: raise ValueError('Select one sample group for Auto range.')
        selected = self.settings['curves'][row]['name']
        return fingerprint([self.current_hash(), cli_choices(self.settings, suggest=True, selected=selected)])

    def run_calculation(self, suggest):
        if suggest and self.settings['method'] != 'average': return
        row = self.single_curve_row()
        selected = self.settings['curves'][row]['name'] if suggest and row >= 0 else None
        try:
            if suggest and selected is None: raise ValueError('Select one sample group for Auto range.')
            choices = copy_choices(self.settings)
            unrestricted = not any(choices['ranges'].values())
            args = cli_choices(choices, suggest=suggest, selected=selected,
                               include_individual=not suggest and unrestricted, saved=True)
            reference_choices = individual_choices(choices) if not suggest else None
            reference_key = (fingerprint([self.current_hash(), cli_choices(reference_choices)])
                             if reference_choices else None)
            request_key = self.range_suggestion_key if suggest else self.calculation_key
            key, generation = request_key(), self.generation
        except (ValueError, TypeError) as exc: self.error(str(exc)); return
        source_hash = self.current_hash()
        self.last_error = ''; self.operation = True
        self.operation_started = time.perf_counter()
        self.operation_phase = 'Suggesting ranges' if suggest else f'Calculating {self.method.currentText()} concentrations'
        self.elapsed_timer.start(); self.update_status()
        self.window.log('INP toolkit: suggesting Average limits…' if suggest else 'INP toolkit: calculating concentrations…')
        def fresh():
            try: return generation == self.generation and key == request_key()
            except (ValueError, TypeError): return False
        def failed(message): self.release_unused(); self.error(message)
        def stale():
            self.operation = False; self.release_unused(); self.update_status()
            self.window.log('INP toolkit: inputs changed; the previous result is retained.')
        def finish(pending, references, comparison_error=None):
            if not fresh(): stale(); return
            toolkit_seconds = time.perf_counter() - self.operation_started
            started = time.perf_counter()
            if references:
                pending['references'] = references
                pending['individual_curves'] = {name: key for key, name in references['by_input'].items()}
            if comparison_error: pending['comparison_error'] = comparison_error
            self.reference_cache = references
            self.reference_plot_tables.clear()
            self.result = pending; self.operation = False
            self.quantity.blockSignals(True); self.quantity.setCurrentIndex(2); self.quantity.blockSignals(False)
            self.draw()
            pending['timings'] = dict(toolkit_seconds=toolkit_seconds, display_seconds=time.perf_counter()-started)
            self.window.log(f"INP analysis updated. Toolkit and transport: {toolkit_seconds:.2f} s; display: {pending['timings']['display_seconds']:.2f} s.")
            if comparison_error:
                self.window.log('INP analysis: the selected-limit result is retained. '
                    f'Full-range individual samples could not be calculated: {comparison_error} '
                    'Calculate to retry the comparison.')
            self.release_unused()
        def references_from(result):
            return dict(result, key=reference_key, by_input={info['sources'][0]['measurement_id']: name
                for name, info in result['reply']['curves'].items() if len(info['sources']) == 1})
        def analyze(reference, options, received, on_error=failed):
            output = '@result-' + uuid.uuid4().hex
            def done(reply):
                self.live_refs.add(output)
                if not fresh(): stale(); return
                def tables_done(tables):
                    received(dict(reference=output, reply=reply, tables=tables))
                self.read_plot_tables(output, reply, tables_done, on_error)
            self.client.request(['analyze', reference, '--format', 'saved', *options, '--out', output], done, on_error)
        def uploaded(reference):
            if not fresh(): stale(); return
            if suggest:
                def suggested(reply):
                    if not fresh(): stale(); return
                    state = copy_choices(self.settings); state['suggestion'] = reply
                    if reply.get('complete') and reply.get('temperature_ranges_C') is not None:
                        state['ranges'].update(reply['temperature_ranges_C'])
                    self.operation = False; self.suggestion_cache = (key, reply)
                    self.commit(state, 'INP analysis: apply Average range suggestions' if reply.get('complete') else 'INP analysis: retain incomplete range suggestions')
                    self.show_suggestion(reply); self.release_unused()
                self.client.request(['suggest-ranges', reference, '--format', 'saved', *args, '--summary'], suggested, failed)
                return
            def main_done(result):
                pending = dict(result, key=key, choices=choices, source_hash=source_hash,
                               toolkit_version=result['reply']['toolkit_version'])
                if unrestricted:
                    finish(pending, references_from(result))
                elif self.reference_cache and self.reference_cache['key'] == reference_key:
                    finish(pending, self.reference_cache)
                else:
                    self.operation_phase = 'Calculating full-range individual samples'; self.show_elapsed()
                    analyze(reference, cli_choices(reference_choices, saved=True),
                            lambda result: finish(pending, references_from(result)),
                            lambda message: finish(pending, None, comparison_error=message))
            analyze(reference, args, main_done)
        self.ensure_input(choices, uploaded, failed, selected=selected)

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
        title = "Limits applied. Adjust them in the table or plot." if reply.get("complete") else "Incomplete: no limits applied. See the Console for details."
        self.suggestion_status.setText(title)
        self.suggestion_status.setToolTip("\n".join(lines))
        if log: self.window.log("INP range suggestions: " + title + "\n" + "\n".join(lines))

    def update_status(self, *_):
        if not hasattr(self, "calculate"): return
        busy = self.operation or self.client.busy
        connected = bool(self.client.capabilities)
        self.calculate.setEnabled(not busy and bool(self.current_hash()))
        self.calculate.setText("Calculate")
        self.cancel.setVisible(busy)
        self.suggest.setEnabled(not busy and self.settings["method"] == "average" and self.single_curve_row() >= 0)
        self.export.setEnabled(bool(self.result) and not busy)
        self.export.setToolTip("Export combined groups or individual samples as separate CSVs. Calculate first if analysis inputs or settings changed.")
        self.calculate.setToolTip("Calculate concentrations for all sample groups using the current settings.")
        if connected:
            self.connection.setText(f"INP toolkit {self.client.capabilities['toolkit_version']}")
        else:
            self.connection.setText("Connecting…" if self.client.busy else "Toolkit unavailable")
        missing = (self.preview or {}).get("suspension_metadata", {}).get("error")
        if busy: message = "Calculating…" if self.operation and self.preview else "Loading counts…"
        elif self.last_error: message = self.last_error
        elif self.result and self.result["key"] == self.calculation_key():
            message = "Result is up to date."
            notice = getattr(self, 'export_notice', None)
            if notice and notice[0] == self.result['key']: message += ' ' + notice[1]
            if self.result.get('comparison_error'):
                message += " Full-range individual samples unavailable; see Console."
        elif self.result:
            message = ("Counts are current. Calculate to update concentration."
                       if self.quantity.currentText() != 'Concentration' and self.preview_hash == self.current_hash()
                       else "Changes not calculated — showing the last successful result.")
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
            if self.result and 'references' not in self.result:
                note += (" · Full-range comparison failed; Calculate to retry."
                         if self.result.get('comparison_error') else
                         " · Calculate for full-range individual samples.")
            self.plot_note.setText(note + " · Muted: excluded or outside selected limits")
            self.plot_note.setToolTip("Individual curves are independent full-range fits using the same method, blanks and units. Excluded points and points outside the current limits are muted; the combined curve changes after Calculate. Log scale omits zeros. Saved sessions retain confidence limits; concentration CSVs contain temperatures, concentrations and lower/upper uncertainty bounds.")
        else:
            self.plot_note.setText("Measured freezing counts, before blank correction or combining dilutions.")
            self.plot_note.setToolTip("Each line represents one sample or marked water blank. Showing a blank does not assign it for correction.")
        self.update_empty_plot()

    def update_empty_plot(self):
        message = ""
        if not self.selected_curve_names() and not (self.quantity.currentText() != 'Concentration'
                                                    and getattr(self, 'visible_points', 0)):
            message = "Select a sample group on the left."
        elif getattr(self, 'hidden_curve_count', 0) and not getattr(self, 'shown_curve_count', 0):
            message = "All curves are hidden. Use Show in the Samples table or enable Show combined curve."
        elif self.quantity.currentText() == "Concentration":
            if self.last_error:
                message = self.last_error
            elif not self.result:
                missing = (self.preview or {}).get("suspension_metadata", {}).get("error")
                message = (f"Concentration needs sample metadata. {missing}" if missing else
                           "Choose samples and blanks, then Calculate to show concentration.")
            elif not self.selected_result_tables("cumulative"):
                message = "This sample group has not been calculated. Choose Calculate."
            elif not getattr(self, "visible_points", 0):
                message = ("No positive concentration values on log scale. Choose Linear concentration scale in Settings → INP toolkit client to see zeros."
                           if self.window.inptk_log_concentration else
                           "No finite concentration points. Check the selected ranges and calculation settings.")
        elif not self.preview:
            message = self.last_error or "Loading freezing counts…"
        elif not getattr(self, 'visible_points', 0):
            message = ("Check Use beside the samples to show their freezing counts."
                       if not self.selected_input_ids() else
                       "No freezing observations for the selected samples and cycles.")
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
        self.source_revision += 1
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
        members = {key for curve in (self.result or {}).get('choices', {}).get('curves', [])
                   if curve['name'] in selected and len(curve['inputs']) > 1 for key in curve['inputs']}
        references = (self.result or {}).get('references')
        if references:
            single_keys = {info['sources'][0]['measurement_id']
                          for name, info in self.result['reply']['curves'].items()
                          if name in selected and len(info['sources']) == 1}
            for key, name in references['by_input'].items():
                if key not in members or key in single_keys: continue
                original = references['tables'][name]
                if kind == 'cumulative':
                    # Display every individual estimate, including values omitted
                    # by the toolkit's final monotonic selection. Do not alter the fit.
                    cache = self.reference_plot_tables
                    if name not in cache:
                        rows = sorted(original['cumulative']['rows'] +
                                      [dict(row, _display_excluded=True) for row in original['excluded']['rows']],
                                      key=lambda r: r.get('point_order', 0))
                        cache[name] = {'columns': original['cumulative']['columns'], 'rows': rows}
                    tables.append((('individual', key), cache[name]))
            return tables
        # Older sessions can display their saved limited curves until recalculated.
        for name, key in (self.result or {}).get('individual_curves', {}).items():
            if key in members and name not in selected:
                table = self.result.get('tables', {}).get(name, {}).get(kind)
                if table is not None: tables.append((name, table))
        return tables

    def concentration_style(self, name):
        if isinstance(name, tuple):
            key = name[1]
            references = self.result['references']
            original = references['by_input'][key]
            source = references['reply']['curves'][original]['sources'][0]
            dilution = source.get('dilution')
            label = f"{key} · {float(dilution):g}×" if dilution is not None else key
            return label, key, True
        sources = (self.result or {}).get('reply', {}).get('curves', {}).get(name, {}).get('sources', [])
        overlay = name not in self.selected_curve_names()
        key = sources[0]['measurement_id'] if len(sources) == 1 else name
        label = name
        if overlay:
            dilution = sources[0].get('dilution') if sources else None
            label = f"{key} · {float(dilution):g}×" if dilution is not None else key
        elif len(sources) > 1:
            label += " (combined)"
            key = None  # Combined curves are black; colors identify physical samples.
        return label, key, overlay

    def update_legend_geometry(self):
        self.legend_view.schedule()

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

    def observation_cycles(self):
        selected = set(self.selected_input_ids())
        # Displaying a marked blank is independent of assigning it for correction.
        # Assigned blanks follow their samples' cycles; other marked blanks use
        # their own cycle choice. Never infer or change a correction assignment.
        cycles = {}
        for key in selected:
            cycle = self.settings['inputs'][key]['cycle']
            cycles.setdefault(key, set()).add(cycle)
            for blank in self.settings['inputs'][key]['blanks']:
                cycles.setdefault(blank, set()).add(cycle)
        for key, values in self.settings['inputs'].items():
            if values['blank'] and key not in cycles:
                cycles[key] = {values['cycle']}
        return cycles

    def observation_rows(self):
        cycles = self.observation_cycles()
        cache_key = (id(self.preview), self.preview_hash,
                     tuple((key, tuple(sorted(values))) for key, values in sorted(cycles.items())))
        if self.observations_cache and self.observations_cache[0] == cache_key:
            return self.observations_cache[1]
        rows = []
        for row in (self.preview or {}).get("table", {}).get("rows", []):
            key = row["measurement_id"]
            wanted = cycles.get(key, set())
            if '' in wanted or str(row['cycle_id']) in wanted: rows.append(row)
        self.observations_cache = (cache_key, rows)
        return rows

    def draw(self, *_):
        if self.loading: return
        quantity = self.quantity.currentText()
        is_concentration = quantity == "Concentration"
        # Counts and fractions are linear; the concentration scale is a global
        # display preference, separate from the saved calculation choices.
        logarithmic = is_concentration and self.window.inptk_log_concentration
        self.show_uncertainty.setVisible(is_concentration)
        self.show_combined.setVisible(is_concentration and any(
            len(c['inputs']) > 1 for c in self.settings['curves'] if c['name'] in self.selected_curve_names()))
        observed = (tuple((key, tuple(sorted(cycles))) for key, cycles in sorted(self.observation_cycles().items()))
                    if not is_concentration else ())
        context = (quantity, logarithmic, tuple(self.selected_curve_names()), self.preview_hash,
                   (self.result or {}).get("key"), self.show_uncertainty.isChecked(), observed)
        refit = context != self.plot_context
        self.plot_context = context
        widths = (self.window.inptk_sample_line_width, self.window.inptk_combined_line_width,
                  self.window.inptk_marker_size, self.window.inptk_outside_opacity)
        visibility = (tuple(sorted(self.hidden_plot_inputs)), self.show_combined.isChecked())
        appearance = (visibility, widths, self.window.inptk_uncertainty_opacity,
                      self.window.inptk_grid_opacity, self.window.inptk_legend_font_size)
        render_key = (context, id(self.result), tuple((k, v['cycle'], v['blank'], tuple(v['blanks']))
                      for k, v in self.settings['inputs'].items()),
                      fingerprint(self.settings['ranges']) if is_concentration else '', appearance)
        if self.render_key == render_key:
            self.draw_ranges(); self.update_status(); return
        self.render_key = render_key
        self.plot.clear(); self.range_items.clear()
        legend = self.plot.getPlotItem().legend
        if legend: legend.clear()
        self.plot.disableAutoRange()
        if logarithmic != self.plot.getPlotItem().ctrl.logYCheck.isChecked():
            self.plot.setYRange(0, 1, padding=0)
        self.plot.setLogMode(x=False, y=logarithmic)
        self.plot.showGrid(x=False, y=self.window.inptk_grid_opacity > 0,
                           alpha=self.window.inptk_grid_opacity / 100.)
        foreground = self.palette().color(self.foregroundRole())
        for side in ("left", "bottom"):
            self.plot.getAxis(side).setTextPen(foreground)
            self.plot.getAxis(side).setPen(foreground)
            self.plot.getAxis(side).enableAutoSIPrefix(False)
        if legend:
            legend.setLabelTextColor(foreground)
            legend.setLabelTextSize(f"{self.window.inptk_legend_font_size:g}pt")
        self.plot.setLabel("left", quantity, units="")
        groups = []
        if is_concentration:
            for name, table in self.concentration_tables("cumulative"):
                label, color_key, overlay = self.concentration_style(name)
                groups.append((label, table["rows"], "concentration", color_key, overlay))
        else:
            by_input = {}
            multiple_cycles = {m["measurement_id"] for m in (self.preview or {}).get("measurements", [])
                               if len(m.get("cycle_ids", [])) > 1}
            for row in self.observation_rows():
                by_input.setdefault((row['measurement_id'], str(row['cycle_id'])), []).append(row)
            for (key, cycle), rows in by_input.items():
                label = key
                if self.settings['inputs'].get(key, {}).get('blank'): label += " (water blank)"
                if key in multiple_cycles: label += f" · cycle {cycle}"
                groups.append((label, rows, "n_frozen" if quantity == "Number frozen" else "fraction_frozen",
                               key, False))
        xs, ys, totals = [], [], []
        self.visible_points = 0
        self.hidden_curve_count = 0
        self.shown_curve_count = 0
        for name, rows, column, color_key, overlay in groups:
            if (color_key in self.hidden_plot_inputs
                    or (color_key is None and not self.show_combined.isChecked())):
                self.hidden_curve_count += 1
                continue
            self.shown_curve_count += 1
            color = QColor(Qt.black) if color_key is None else self.color(color_key)
            chunks, chunk, previous = [], [], None
            for row in rows:
                segment = "0" if overlay else row.get("segment_id", "0")
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
                blank = self.settings['inputs'].get(color_key, {}).get('blank', False)
                width = widths[0] if overlay or not is_concentration else widths[1]
                symbol = "o" if len(chunk) <= 500 and widths[2] > 0 else None
                shown = y
                if overlay:
                    limits = temperature_range(self.settings, color_key)
                    active = (x >= limits.get('min_C', -math.inf)) & (x <= limits.get('max_C', math.inf))
                    active &= np.array([not row.get('_display_excluded', False) for row in chunk])
                    if not active.all():
                        dull = QColor(color); dull.setAlphaF(widths[3] / 100.)
                        muted = self.plot.plot(x, y, pen=pg.mkPen(dull, width=width, style=Qt.DashLine),
                            symbol=symbol, symbolSize=widths[2], symbolBrush=dull, symbolPen=dull, connect='finite')
                        self.make_sample_clickable(muted, color_key)
                        shown = y.copy(); shown[~active] = np.nan
                curve = self.plot.plot(x, shown, pen=pg.mkPen(color, width=width,
                    style=Qt.DotLine if blank else Qt.DashLine if overlay else Qt.SolidLine),
                    symbol=symbol, symbolSize=widths[2], symbolBrush=color, symbolPen=color,
                    name=name if i == 0 else None, connect="finite", data=chunk if symbol else None)
                self.make_sample_clickable(curve, color_key)
                if symbol:
                    curve.scatter.opts.update(hoverable=True, tip=self.point_tip)
                if column == "concentration":
                    unit = str(chunk[0].get("unit", ""))
                    unit = concentration_unit(unit)
                    self.plot.setLabel("left", "Concentration", units=unit)
                    if not self.show_uncertainty.isChecked(): continue
                    lower = y - np.array([number(row.get("lower_error")) for row in chunk])
                    upper = y + np.array([number(row.get("upper_error")) for row in chunk])
                    for bound in (lower, upper):
                        bound[~np.isfinite(bound)] = np.nan
                        if logarithmic: bound[bound <= 0] = np.nan
                        ys.extend(bound[np.isfinite(x) & np.isfinite(bound)])
                    # Individual uncertainty uses its sample color and the same
                    # outside-range muting as its curve. Combined bounds are black.
                    if overlay:
                        self.draw_uncertainty(x, lower, upper, color, active, 1.)
                        if not active.all():
                            self.draw_uncertainty(x, lower, upper, color, ~active, widths[3] / 100.)
                    else:
                        self.draw_uncertainty(x, lower, upper, color, np.ones(len(x), dtype=bool), 1.)
        self.plot_limits = axis_limits(quantity, xs, ys, totals, logarithmic=logarithmic)
        self.update_legend_geometry()
        if refit: self.fit_plot()
        self.draw_ranges(); self.update_status()

    def draw_uncertainty(self, x, lower, upper, color, mask, opacity):
        lower, upper = lower.copy(), upper.copy()
        lower[~mask] = np.nan; upper[~mask] = np.nan
        fill = QColor(color)
        fill.setAlphaF(self.window.inptk_uncertainty_opacity / 100. * opacity)
        edge = QColor(color)
        edge.setAlphaF(min(1., self.window.inptk_uncertainty_opacity / 100. * 2.5) * opacity)
        for bound in (lower, upper):
            self.plot.plot(x, bound, pen=pg.mkPen(edge, width=1), connect="finite").setZValue(-1)
        # Pair identical temperatures and split at gaps. Unequal or nonpositive
        # log bounds must never close a diagonal polygon across missing values.
        paired = np.flatnonzero(np.isfinite(x) & np.isfinite(lower) & np.isfinite(upper))
        for indices in np.split(paired, np.flatnonzero(np.diff(paired) != 1) + 1):
            if len(indices) < 2: continue
            boundary = pg.mkPen(QColor(0, 0, 0, 0))
            band_lo = self.plot.plot(x[indices], lower[indices], pen=boundary)
            band_hi = self.plot.plot(x[indices], upper[indices], pen=boundary)
            band = pg.FillBetweenItem(band_lo, band_hi, brush=fill)
            band.setZValue(-2)
            self.plot.addItem(band, ignoreBounds=True)

    def result_reference(self, result):
        reference = self.restored_refs.get(id(result), result.get('reference'))
        return reference if reference in self.live_refs and self.client.capabilities else None

    def prepare_session_save(self, *, require_native=False):
        """Preserve full native results only at a user save/export boundary."""
        if not self.result: return
        saved = {}
        for result in (self.result, self.result.get('references')):
            if not result or result.get('saved_result'): continue
            reference = self.result_reference(result)
            if not reference:
                message = 'The toolkit process no longer holds this unsaved result. The plot and choices are retained; calculate to export native INP results.'
                if require_native: raise ValueError(message)
                result['native_result_unavailable'] = True
                self.window.log(message)
                continue
            if reference not in saved:
                folder = Path(self.cache.name) / ('save-' + uuid.uuid4().hex + '.inptk')
                try:
                    self.client.request_wait(['save', reference, '--out', str(folder)])
                    saved[reference] = self.client.compute_wait(lambda: (folder / 'analysis.json').read_text(encoding='utf-8'))
                finally:
                    if folder.exists(): shutil.rmtree(folder)
            result['saved_result'] = saved[reference]

    def ensure_result_reference(self, result, callback):
        reference = self.result_reference(result)
        if reference: callback(reference); return
        native = result.get('saved_result')
        if not native:
            self.error('The toolkit process no longer holds this result. Calculate before exporting.'); return
        # A reopened session already contains its exact native result. Restore it
        # on explicit export, without fitting it again using a different version.
        reference = '@restored-' + uuid.uuid4().hex
        folder = Path(self.cache.name) / (uuid.uuid4().hex + '.inptk')
        self.operation = True; self.update_status()
        def write_native():
            folder.mkdir(); (folder / 'analysis.json').write_text(native, encoding='utf-8')
        def prepared(_value):
            def loaded(_reply):
                shutil.rmtree(folder)
                self.live_refs.add(reference); self.restored_refs[id(result)] = reference
                callback(reference)
            def failed(message):
                shutil.rmtree(folder); self.error(message)
            self.client.request(['save', str(folder), '--out', reference], loaded, failed)
        self.client.compute(write_native, prepared, self.error)

    def export_result(self):
        if not self.result: return
        # Native export is a user save, so capturing the full JSON is appropriate.
        path, _ = QFileDialog.getSaveFileName(self, 'Save .inptk session folder', 'analysis.inptk', 'INP toolkit session folder (*.inptk)')
        if not path: return
        if Path(path).exists(): self.error('Choose a new result folder; existing outputs are preserved.'); return
        target = Path(path)
        if target.suffix.lower() != '.inptk': target = target.with_name(target.name + '.inptk')
        created, written = False, []
        try:
            self.prepare_session_save(require_native=True)
            target.mkdir(parents=False, exist_ok=False)
            created = True
            written.append(target / 'analysis.json')
            written[-1].write_text(self.result['saved_result'], encoding='utf-8')
            references = self.result.get('references')
            if references and references['saved_result'] != self.result['saved_result']:
                folder = target / 'individual-samples.inptk'; folder.mkdir()
                written.append(folder / 'analysis.json')
                written[-1].write_text(references['saved_result'], encoding='utf-8')
        except (OSError, ValueError) as exc:
            if created:
                # Remove only files we created, never unrelated contents.
                for file in reversed(written):
                    try: file.unlink(missing_ok=True)
                    except OSError: pass
                for folder in (target / 'individual-samples.inptk', target):
                    try: folder.rmdir()
                    except OSError: pass
            self.error(f'Could not save result: {exc}'); return
        self.window.log(f'Saved INP result: {target}')
        self.status.setText(f'Saved .inptk session: {target.name}')

    def export_concentration_unit(self):
        # Pending edits must not relabel the last successful result's units.
        basis = (self.result or {}).get('choices', {}).get('basis')
        return {'suspension': 'INP/mL suspension', 'sampled_air': 'INP/L air',
                'dry_soil': 'INP/g dry soil'}.get(basis, '')

    def update_export_menu(self):
        names = [curve['name'] for curve in (self.result or {}).get('choices', {}).get('curves', [])]
        text = ', '.join(names)
        text = text if len(text) <= 60 else text[:57] + '…'
        self.export_scope_action.setText(f"All {len(names)} {'group' if len(names) == 1 else 'groups'}: {text}")
        self.export_scope_action.setToolTip('\n'.join(names))
        self.export_scope_label.setText(self.export_scope_action.text())
        self.export_scope_label.setToolTip('\n'.join(names))
        unit = self.export_concentration_unit()
        suffix = f" ({unit})" if unit else ''
        self.concentration_export_action.setText(f"Export combined concentration CSV{suffix}…")
        self.individual_export_action.setText(f"Export individual sample concentrations CSV{suffix}…")
        references = (self.result or {}).get('references') or {}
        available = bool(references.get('by_input'))
        self.individual_export_action.setEnabled(available)
        if not available:
            self.individual_export_action.setToolTip('Individual sample fits are unavailable. Calculate to generate them; see Console if that calculation fails.')

    def export_csv(self, kind='cumulative'):
        if not self.result:
            self.error('Calculate INP results before exporting.'); return
        if self.operation or self.client.busy:
            self.window.log('Wait for the current INP operation to finish before exporting.'); return
        if self.current_hash() and not self.source_cache:
            self.refresh_preview(after=lambda: self.export_csv(kind)); return
        if self.current_hash() and self.result['key'] != self.calculation_key():
            self.error('Analysis inputs or settings changed. Calculate before exporting CSV results.'); return
        if kind == 'individual' and not self.result.get('references', {}).get('by_input'):
            self.error('Individual sample fits are unavailable. Calculate before exporting.'); return
        if kind == 'frozen_fraction' and not self.client.capabilities:
            self.ensure_connected(after=lambda: self.export_csv(kind)); return
        labels = {'frozen_fraction': 'frozen fractions', 'cumulative': 'combined concentrations',
                  'individual': 'individual sample concentrations'}
        label = labels[kind]
        unit = self.export_concentration_unit() if kind != 'frozen_fraction' else ''
        title = f"Export {label} CSV" + (f" ({unit})" if unit else '')
        if not self.current_hash(): title += ' — saved calculation'
        filename = f"inp_{label.replace(' ', '_')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, title, filename, 'CSV (*.csv)')
        if not path: return
        if Path(path).suffix.lower() != '.csv': path += '.csv'
        if Path(path).exists(): self.error('Choose a new filename; existing outputs are preserved.'); return
        result = self.result
        self.last_error = ''; self.operation = True; self.update_status()
        def done(row_count):
            self.operation = False; self.update_status()
            message = f'Exported {label}: {row_count} rows · {Path(path).name}'
            self.export_notice = (result['key'], message)
            self.update_status()
            self.window.log(message + f' ({path})')
            self.release_unused()
        def save(layout):
            headers, rows = layout
            write_csv(path, headers, rows)
            return len(rows)
        if kind == 'frozen_fraction':
            def ready(reference):
                def received(reply):
                    if not result['choices']['grid_step'].strip():
                        self.client.compute(lambda: save(frozen_fraction_csv(reply['table'], result['choices'])), done, self.error)
                        return
                    # The toolkit retains the exact selected observation IDs.
                    # Join those to its fractions; never repeat count selection
                    # in the client or round recording temperatures onto a grid.
                    selected = []
                    tasks = ['cumulative']
                    if any(info['tables'].get('excluded', {}).get('row_count', 0)
                           for info in result['reply']['curves'].values()): tasks.append('excluded')
                    def next_table():
                        if not tasks:
                            self.client.compute(lambda: save(frozen_fraction_csv(reply['table'], result['choices'], selected)), done, self.error)
                            return
                        def received_selection(selection):
                            selected.extend(selection['table']['rows']); next_table()
                        self.client.request(['table', reference, '--table', tasks.pop(0), '--no-history',
                            '--columns', 'temperature_C', 'source_observations'], received_selection, self.error)
                    next_table()
                self.client.request(['table', reference, '--table', 'frozen_fraction', '--no-history',
                    '--columns', 'temperature_C', 'measurement_id', 'run_id', 'cycle_id', 'observation_id', 'fraction_frozen'], received, self.error)
            self.ensure_result_reference(result, ready)
        else:
            if kind == 'individual':
                references = result['references']
                tables = references['tables']
                curves = list(references['by_input'].items())
            else:
                tables = result['tables']
                curves = [(curve['name'], curve['name']) for curve in result['choices']['curves']]
            self.client.compute(lambda: save(concentration_csv(tables, curves)), done, self.error)

    def session_state(self):
        return {"version": 1, "choices": copy_choices(self.settings), "preview": self.preview,
                "preview_hash": self.preview_hash, "result": self.result,
                "display": {"hidden_samples": sorted(self.hidden_plot_inputs),
                            "show_combined": self.show_combined.isChecked()}}

    def restore_session(self, state):
        self.generation += 1; self.client.stop(); self.operation = False
        self.live_refs.clear(); self.restored_refs.clear(); self.input_ref = self.input_key = None
        self.source_revision += 1
        self.last_error = ""; self.after_connect = None; self.plot_context = None; self.source_cache = None
        self.export_notice = None
        self.undo_stack.clear()
        self.undo_stack.setUndoLimit(self.window.undo_limit)
        state = state or {}
        display = state.get("display") or {}
        self.hidden_plot_inputs = set(display.get("hidden_samples", []))
        self.show_combined.blockSignals(True)
        self.show_combined.setChecked(display.get("show_combined", True))
        self.show_combined.blockSignals(False)
        self.preview = state.get("preview"); self.preview_hash = state.get("preview_hash", "")
        self.result = state.get("result")
        self.reference_cache = (self.result or {}).get('references')
        self.reference_plot_tables.clear()
        self.render_key = None; self.limits_cache = None; self.observations_cache = None
        self.suggestion_cache = None
        self.restore_choices(state.get("choices") or new_settings())

    def shutdown(self):
        self.close()
        self.restore_console()
        self.client.shutdown(); self.cache.cleanup()
