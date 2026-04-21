from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QFileDialog, QVBoxLayout,
                               QWidget, QGraphicsScene, QLineEdit, QLabel,
                               QTextEdit, QSizePolicy, QHBoxLayout, QGraphicsView, QSplitter, QSlider,
                               QStatusBar, QDialog, QDoubleSpinBox, QToolButton, QAbstractSpinBox,
                               QListView, QListWidget, QListWidgetItem, QGridLayout, QTreeWidget, QTreeWidgetItem, QTableWidget, QHeaderView, QFormLayout, QStackedWidget, QSpinBox, QComboBox,
                               QTableWidgetItem, QAbstractItemView, QMessageBox, QDialogButtonBox, QFrame, QDockWidget, QTabWidget, QStyle, QCheckBox, QScrollArea, QStyleOptionSlider)
from PySide6.QtGui import QPixmap, QImage, QPen, QBrush, QColor, QPainter, Qt, QCursor, QTransform, QFont, QAction, QIcon, QGuiApplication, QUndoStack, QShortcut, QKeySequence
from PySide6.QtCore import QRectF, QSize, QTimer, QEvent, QModelIndex, QItemSelectionModel, QSignalBlocker, QPointF
import xml.etree.ElementTree as ET
import csv
import os
import math
import tempfile
import darkdetect
import platform
import time
import cv2
from functools import partial
import copy
from collections import OrderedDict
import numpy as np
import shiboken6
import re
from PIL import Image

# Custom Python Files
from icescopy_aux import CustomGraphicsView, AboutDialog, Image_analysis_thread, PreferencesDialog, SortImagesDialog
import icescopy_stylesheet
from icescopy_cell import CellStateManager
from icescopy_cell_items import CellCircle, CellSnapshot
from icescopy_frameslider import FrameSlider, SliderZoom_Slider
from icescopy_image_edit import (
    IMAGE_EDIT_HISTOGRAM_BIN_COUNT,
    ImageCropOverlayItem,
    ImageHistogramWidget,
    ImageRectOverlayItem,
    apply_affine_to_point,
    apply_image_adjustments_to_uint8,
    apply_image_adjustments_to_qimage,
    build_rotated_crop_affine,
    compute_histogram_bins,
    crop_state_is_identity,
    invert_affine_matrix,
    normalize_rect_area_state,
    normalize_rotated_crop_state,
    qimage_to_grayscale_array,
)
from icescopy_plot import GrayscalePlotWidget
from icescopy_cell_controller import CellEditController
from icescopy_temperature_import import (
    TemperatureImportError,
    normalize_sample_name,
    parse_ice_array_calibration_csv,
    parse_csu_is_dat,
    parse_tamu_image_timestamp,
    parse_tamu_linkam_xlsx,
    reconcile_cumulative_counts,
)
from icescopy_session import (
    FrameNavigationCommand,
    ImageListModel,
    SessionDataCommand,
    SessionImageEditCommand,
    SessionImageListCommand,
    SessionLoadedImagesCommand,
    SessionCellCommand,
    SessionSnapshotCommand,
)
from icescopy_session_io import build_restore_state, build_session_payload, load_session_bundle, save_session_bundle


module_dir = os.path.dirname(__file__)
resources_dir = os.path.join(module_dir, 'resources')
if not os.path.isdir(resources_dir):
    resources_dir = os.path.join(os.path.dirname(module_dir), 'resources')
ui_images_dir = os.path.join(resources_dir, 'ui_images')
SIDE_PANEL_DEFAULT_WIDTH = 280
TOOL_OPTIONS_CONTENT_WIDTH = 252
TOOL_OPTIONS_BUTTON_SPACING = 8
TOOL_OPTIONS_LABEL_WIDTH = 84
TOOL_OPTIONS_FIELD_WIDTH = 96
TOOL_OPTIONS_SHORTCUT_WIDTH = 56
TOOL_OPTIONS_PANEL_DEFAULT_WIDTH = TOOL_OPTIONS_CONTENT_WIDTH + 20
TOOL_OPTIONS_SPINBOX_SLOT_HEIGHT = 30
TOOL_OPTIONS_CONTROL_QSS = """
            QSpinBox {
                min-height: 24px;
            }
            QDoubleSpinBox {
                min-height: 24px;
            }
            QWidget#toolOptionsPanel QSlider {
                min-height: 16px;
            }
            QWidget#toolOptionsPanel QSlider::groove:horizontal {
                height: 4px;
                border: 1px solid #bdbdbd;
                background: #d9d9d9;
                border-radius: 2px;
            }
            QWidget#toolOptionsPanel QSlider::sub-page:horizontal {
                background: #0a84ff;
                border-radius: 2px;
            }
            QWidget#toolOptionsPanel QSlider::add-page:horizontal {
                background: #d9d9d9;
                border-radius: 2px;
            }
            QWidget#toolOptionsPanel QSlider::handle:horizontal {
                background: white;
                border: 1px solid #949494;
                width: 8px;
                margin: -6px 0;
                border-radius: 4px;
            }
        """

DEFAULT_VISUAL_COLORS = {
    "CircleDefaultColor": "255,0,0,255",
    "CircleHoverColor": "0,0,255,255",
    "CircleSelectedColor": "64,156,255,255",
    "CircleEditColor": "240,168,168,255",
    "CirclePressedColor": "255,255,0,255",
    "GridPreviewOutlineColor": "0,122,255,200",
    "GridPreviewFillColor": "0,122,255,25",
}

SAMPLE_VISUAL_PALETTE = (
    (52, 199, 89),
    (255, 149, 0),
    (175, 82, 222),
    (48, 176, 199),
    (162, 132, 94),
    (106, 90, 205),
    (153, 153, 0),
    (199, 97, 20),
)


class ToolOptionsInfoPage(QWidget):
    def __init__(self, parent=None, content_width=TOOL_OPTIONS_CONTENT_WIDTH):
        super().__init__(parent)
        self.content_width = content_width
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.scroll_area)

        self.scroll_contents = QWidget(self.scroll_area)
        self.scroll_contents_layout = QVBoxLayout(self.scroll_contents)
        self.scroll_contents_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_contents_layout.setSpacing(0)
        self.scroll_contents_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        self.column_widget = QWidget(self.scroll_contents)
        self.column_widget.setFixedWidth(self.content_width)
        self.column_layout = QVBoxLayout(self.column_widget)
        self.column_layout.setContentsMargins(0, 0, 0, 0)
        self.column_layout.setSpacing(10)
        self.column_layout.setAlignment(Qt.AlignTop)

        self.message_label = QLabel(self.column_widget)
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.column_layout.addWidget(self.message_label)
        self.column_layout.addStretch(1)
        self.scroll_contents_layout.addWidget(self.column_widget)
        self.scroll_contents_layout.addStretch(1)
        self.scroll_area.setWidget(self.scroll_contents)

    def set_message(self, text):
        self.message_label.setText(text)


class ToolOptionsFormPage(QWidget):
    def __init__(
        self,
        parent=None,
        *,
        content_width=TOOL_OPTIONS_CONTENT_WIDTH,
        label_width=TOOL_OPTIONS_LABEL_WIDTH,
        field_width=TOOL_OPTIONS_FIELD_WIDTH,
        shortcut_width=TOOL_OPTIONS_SHORTCUT_WIDTH,
    ):
        super().__init__(parent)
        self.content_width = content_width
        self.label_width = label_width
        self.field_width = field_width
        self.shortcut_width = shortcut_width

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.root_layout.addWidget(self.scroll_area)

        self.scroll_contents = QWidget(self.scroll_area)
        self.scroll_contents_layout = QVBoxLayout(self.scroll_contents)
        self.scroll_contents_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_contents_layout.setSpacing(0)
        self.scroll_contents_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        self.column_widget = QWidget(self.scroll_contents)
        self.column_widget.setFixedWidth(self.content_width)
        self.column_layout = QVBoxLayout(self.column_widget)
        self.column_layout.setContentsMargins(0, 0, 0, 0)
        self.column_layout.setSpacing(10)
        self.column_layout.setAlignment(Qt.AlignTop)
        self.scroll_contents_layout.addWidget(self.column_widget)
        self.scroll_contents_layout.addStretch(1)
        self.scroll_area.setWidget(self.scroll_contents)

        self.hint_label = None
        self.apply_button = None
        self.float_button = None
        self.cancel_button = None
        self.native_combo_height = self._probe_native_combo_height()
        self.native_button_height = self._probe_native_button_height()

    def _probe_native_combo_height(self):
        probe = QComboBox(self.column_widget)
        height = probe.sizeHint().height()
        probe.deleteLater()
        return int(height)

    def _probe_native_button_height(self):
        probe = QPushButton("Apply", self.column_widget)
        height = probe.sizeHint().height()
        probe.deleteLater()
        return int(height)

    def standard_button_width(self):
        return int((self.content_width - (2 * TOOL_OPTIONS_BUTTON_SPACING)) / 3)

    def _configure_control(self, control):
        control.setFixedWidth(self.field_width)
        control_height = control.property("toolOptionsControlHeight")
        if control_height not in (None, 0):
            control.setFixedHeight(int(control_height))
        control.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return control

    def create_combo_box(self, *, index_handler=None):
        combo = QComboBox(self.column_widget)
        combo.setProperty("toolOptionsControlHeight", TOOL_OPTIONS_SPINBOX_SLOT_HEIGHT)
        combo.setEditable(True)
        combo.lineEdit().setReadOnly(True)
        combo.lineEdit().setFocusPolicy(Qt.NoFocus)
        combo.lineEdit().setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._configure_control(combo)
        if index_handler is not None:
            combo.currentIndexChanged.connect(index_handler)
        return combo

    def create_spin_box(self, minimum, maximum, *, step=1, value_handler=None):
        spinbox = QSpinBox(self.column_widget)
        self._configure_control(spinbox)
        spinbox.setRange(minimum, maximum)
        spinbox.setSingleStep(step)
        if value_handler is not None:
            spinbox.valueChanged.connect(value_handler)
        return spinbox

    def create_double_spin_box(
        self,
        minimum,
        maximum,
        *,
        decimals=1,
        step=0.5,
        value_handler=None,
    ):
        spinbox = QDoubleSpinBox(self.column_widget)
        self._configure_control(spinbox)
        spinbox.setRange(minimum, maximum)
        spinbox.setDecimals(decimals)
        spinbox.setSingleStep(step)
        if value_handler is not None:
            spinbox.valueChanged.connect(value_handler)
        return spinbox

    def _create_button(self, text, parent, handler):
        button = QPushButton(text, parent)
        button.setFixedHeight(self.native_button_height)
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        button.clicked.connect(handler)
        return button

    def add_row(self, label_text, editor, shortcut_text=""):
        row_widget = QWidget(self.column_widget)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label = QLabel(label_text, row_widget)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setFixedWidth(self.label_width)
        row_layout.addWidget(label)

        self._configure_control(editor)
        row_layout.addWidget(editor)

        shortcut_label = QLabel(shortcut_text, row_widget)
        shortcut_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        shortcut_label.setStyleSheet("color: #7a7a7a; font-size: 11px;")
        shortcut_label.setFixedWidth(self.shortcut_width)
        row_layout.addWidget(shortcut_label)

        self.column_layout.addWidget(row_widget)
        return row_widget

    def add_row_with_button(self, label_text, editor, button_text, handler):
        row_widget = QWidget(self.column_widget)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label = QLabel(label_text, row_widget)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setFixedWidth(self.label_width)
        row_layout.addWidget(label)

        self._configure_control(editor)
        row_layout.addWidget(editor)

        button = self._create_button(button_text, row_widget, handler)
        button.setFixedWidth(self.shortcut_width if self.shortcut_width > 0 else self.standard_button_width())
        row_layout.addWidget(button)

        self.column_layout.addWidget(row_widget)
        return row_widget, button

    def add_section_label(self, text):
        label = QLabel(text, self.column_widget)
        label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        label.setStyleSheet("font-size: 12px; font-weight: 700; color: #2f2f2f;")
        self.column_layout.addWidget(label)
        return label

    def add_separator(self):
        line = QFrame(self.column_widget)
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet("color: #cfcfcf; background-color: #cfcfcf;")
        line.setFixedHeight(1)
        self.column_layout.addWidget(line)
        return line

    def add_value_row(self, label_text, value_text="-"):
        row_widget = QWidget(self.column_widget)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label = QLabel(label_text, row_widget)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setFixedWidth(self.label_width)
        row_layout.addWidget(label)

        value_label = QLabel(str(value_text), row_widget)
        value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        value_label.setFixedWidth(self.field_width)
        row_layout.addWidget(value_label)

        spacer = QWidget(row_widget)
        spacer.setFixedWidth(self.shortcut_width)
        row_layout.addWidget(spacer)

        self.column_layout.addWidget(row_widget)
        return row_widget, label, value_label

    def add_hint(self, text):
        self.hint_label = QLabel(text, self.column_widget)
        self.hint_label.setWordWrap(True)
        self.hint_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.column_layout.addWidget(self.hint_label)
        return self.hint_label

    def add_action_row(self, apply_handler, float_handler, cancel_handler):
        button_width = self.standard_button_width()
        row_widget = QWidget(self.column_widget)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(TOOL_OPTIONS_BUTTON_SPACING)

        self.apply_button = self._create_button("Apply", row_widget, apply_handler)
        self.float_button = self._create_button("Float", row_widget, float_handler)
        self.cancel_button = self._create_button("Cancel", row_widget, cancel_handler)

        for button in (self.apply_button, self.float_button, self.cancel_button):
            button.setFixedWidth(button_width)
            row_layout.addWidget(button)

        self.column_layout.addWidget(row_widget)
        return row_widget

    def add_centered_button_row(self, button_text, handler):
        row_widget = QWidget(self.column_widget)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(TOOL_OPTIONS_BUTTON_SPACING)

        button = self._create_button(button_text, row_widget, handler)
        button.setFixedWidth(max(self.standard_button_width(), button.sizeHint().width()))
        row_layout.addStretch(1)
        row_layout.addWidget(button)
        row_layout.addStretch(1)

        self.column_layout.addWidget(row_widget)
        return row_widget, button

    def add_bottom_stretch(self):
        self.column_layout.addStretch(1)


class NewSessionMetadataDialog(QDialog):
    def __init__(self, parent=None, metadata=None):
        super().__init__(parent)
        self.setWindowTitle("New Session")
        self.setModal(True)
        self.setMinimumWidth(420)

        metadata = metadata or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        message = QLabel(
            "Enter optional session metadata. Leave fields blank if you do not need them.",
            self,
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.project_name_edit = QLineEdit(str(metadata.get("project_name", "")), self)
        self.user_name_edit = QLineEdit(str(metadata.get("user_name", "")), self)
        self.institution_edit = QLineEdit(str(metadata.get("institution", "")), self)
        self.date_edit = QLineEdit(str(metadata.get("date", "")), self)
        self.date_edit.setPlaceholderText("Optional")

        form.addRow("Project Name", self.project_name_edit)
        form.addRow("User Name", self.user_name_edit)
        form.addRow("Institution", self.institution_edit)
        form.addRow("Date", self.date_edit)
        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_metadata(self):
        return {
            "project_name": self.project_name_edit.text().strip(),
            "user_name": self.user_name_edit.text().strip(),
            "institution": self.institution_edit.text().strip(),
            "date": self.date_edit.text().strip(),
        }


class CSUTemperatureImportDialog(QDialog):
    def __init__(self, main_window, initial_path, sample_names, initial_reset_temperature=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("CSU IS .dat import")
        self.resize(620, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        intro_label = QLabel(
            "Select the CSU .dat file and optionally mark app samples that should be treated as blank controls.",
            self,
        )
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        file_row = QHBoxLayout()
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.setSpacing(8)
        self.file_path_edit = QLineEdit(self)
        self.file_path_edit.setText(str(initial_path or ""))
        self.file_path_edit.setPlaceholderText("Choose a CSU .dat file")
        browse_button = QPushButton("Browse", self)
        browse_button.setAutoDefault(False)
        browse_button.setDefault(False)
        browse_button.setFixedWidth(96)
        browse_button.clicked.connect(self.browse_file)
        file_row.addWidget(self.file_path_edit, 1)
        file_row.addWidget(browse_button, 0, Qt.AlignRight)
        file_row_widget = QWidget(self)
        file_row_widget.setLayout(file_row)
        form.addRow("CSU .dat file", file_row_widget)

        self.blank_sample_list = QListWidget(self)
        self.blank_sample_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.blank_sample_list.setMinimumHeight(132)
        for sample_name in sample_names:
            item = QListWidgetItem(str(sample_name), self.blank_sample_list)
            if "blank" in str(sample_name).casefold():
                item.setSelected(True)
        form.addRow("Blank samples", self.blank_sample_list)

        self.reset_temperature_spinbox = QDoubleSpinBox(self)
        self.reset_temperature_spinbox.setRange(-999.0, 200.0)
        self.reset_temperature_spinbox.setDecimals(1)
        self.reset_temperature_spinbox.setSpecialValueText("Off")
        self.reset_temperature_spinbox.setValue(-999.0 if initial_reset_temperature is None else float(initial_reset_temperature))
        self.reset_temperature_spinbox.setFixedWidth(120)
        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_row.addWidget(self.reset_temperature_spinbox, 0, Qt.AlignLeft)
        reset_row.addStretch(1)
        reset_row_widget = QWidget(self)
        reset_row_widget.setLayout(reset_row)
        form.addRow("Reset After Warmed To (°C)", reset_row_widget)

        layout.addLayout(form, 1)

        hint_label = QLabel(
            "Blank correction is applied within each cycle. If reset is enabled, a new cycle starts once temperature warms back to the selected threshold.",
            self,
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: rgba(96, 96, 96, 255);")
        layout.addWidget(hint_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def browse_file(self):
        initial_dir = ""
        existing_path = self.file_path_edit.text().strip()
        if existing_path:
            initial_dir = os.path.dirname(existing_path)
        elif getattr(self.main_window, "last_temperature_import_path", None):
            initial_dir = os.path.dirname(self.main_window.last_temperature_import_path)
        elif getattr(self.main_window, "imagePaths", None):
            initial_dir = os.path.dirname(self.main_window.imagePaths[0])
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import CSU IS .dat file",
            initial_dir,
            "CSU Data Files (*.dat);;All Files (*)",
            options=self.main_window.file_dialog_options(),
        )
        if file_path:
            self.file_path_edit.setText(file_path)

    def accept(self):
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, "CSU IS .dat import", "Choose a CSU .dat file before importing.")
            return
        if not os.path.isfile(file_path):
            QMessageBox.warning(self, "CSU IS .dat import", "The selected CSU .dat file does not exist.")
            return
        super().accept()

    def get_values(self):
        reset_temperature = float(self.reset_temperature_spinbox.value())
        if reset_temperature <= -999.0:
            reset_temperature = None
        return {
            "file_path": self.file_path_edit.text().strip(),
            "blank_sample_names": [
                str(item.text())
                for item in self.blank_sample_list.selectedItems()
            ],
            "reset_temperature": reset_temperature,
        }


class TAMUTemperatureImportDialog(QDialog):
    def __init__(self, main_window, initial_path, initial_calibration_path="", initial_reset_temperature=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("TAMU Linkam .xlsx import")
        self.resize(640, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        intro_label = QLabel(
            "Select the TAMU Linkam workbook. Image timestamps will be read from the PNG filenames and matched to the Linkam temperature trace by time interpolation.",
            self,
        )
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        file_row = QHBoxLayout()
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.setSpacing(8)
        self.file_path_edit = QLineEdit(self)
        self.file_path_edit.setText(str(initial_path or ""))
        self.file_path_edit.setPlaceholderText("Choose a TAMU Linkam workbook")
        browse_button = QPushButton("Browse", self)
        browse_button.setAutoDefault(False)
        browse_button.setDefault(False)
        browse_button.setFixedWidth(96)
        browse_button.clicked.connect(self.browse_file)
        file_row.addWidget(self.file_path_edit, 1)
        file_row.addWidget(browse_button, 0, Qt.AlignRight)
        file_row_widget = QWidget(self)
        file_row_widget.setLayout(file_row)
        form.addRow("TAMU .xlsx file", file_row_widget)

        calibration_row = QHBoxLayout()
        calibration_row.setContentsMargins(0, 0, 0, 0)
        calibration_row.setSpacing(8)
        self.calibration_path_edit = QLineEdit(self)
        self.calibration_path_edit.setText(str(initial_calibration_path or ""))
        self.calibration_path_edit.setPlaceholderText("Optional")
        calibration_browse_button = QPushButton("Browse", self)
        calibration_browse_button.setAutoDefault(False)
        calibration_browse_button.setDefault(False)
        calibration_browse_button.setFixedWidth(96)
        calibration_browse_button.clicked.connect(self.browse_calibration_file)
        calibration_row.addWidget(self.calibration_path_edit, 1)
        calibration_row.addWidget(calibration_browse_button, 0, Qt.AlignRight)
        calibration_row_widget = QWidget(self)
        calibration_row_widget.setLayout(calibration_row)
        form.addRow("Calibration CSV", calibration_row_widget)

        self.reset_temperature_spinbox = QDoubleSpinBox(self)
        self.reset_temperature_spinbox.setRange(-999.0, 200.0)
        self.reset_temperature_spinbox.setDecimals(1)
        self.reset_temperature_spinbox.setSpecialValueText("Off")
        self.reset_temperature_spinbox.setValue(-999.0 if initial_reset_temperature is None else float(initial_reset_temperature))
        self.reset_temperature_spinbox.setFixedWidth(120)
        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_row.addWidget(self.reset_temperature_spinbox, 0, Qt.AlignLeft)
        reset_row.addStretch(1)
        reset_row_widget = QWidget(self)
        reset_row_widget.setLayout(reset_row)
        form.addRow("Reset After Warmed To (°C)", reset_row_widget)

        layout.addLayout(form)

        hint_label = QLabel(
            "Calibration is applied by cell ID. If no sample setup exists, all cells are treated as one output group. If reset is enabled, counts restart once temperature warms back to the selected threshold.",
            self,
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: rgba(96, 96, 96, 255);")
        hint_label.setContentsMargins(2, 2, 2, 0)
        layout.addWidget(hint_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def browse_file(self):
        initial_dir = ""
        existing_path = self.file_path_edit.text().strip()
        if existing_path:
            initial_dir = os.path.dirname(existing_path)
        elif getattr(self.main_window, "last_temperature_import_path", None):
            initial_dir = os.path.dirname(self.main_window.last_temperature_import_path)
        elif getattr(self.main_window, "imagePaths", None):
            initial_dir = os.path.dirname(self.main_window.imagePaths[0])
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import TAMU Linkam .xlsx file",
            initial_dir,
            "Excel Files (*.xlsx);;All Files (*)",
            options=self.main_window.file_dialog_options(),
        )
        if file_path:
            self.file_path_edit.setText(file_path)

    def browse_calibration_file(self):
        initial_dir = ""
        existing_path = self.calibration_path_edit.text().strip()
        if existing_path:
            initial_dir = os.path.dirname(existing_path)
        elif self.file_path_edit.text().strip():
            initial_dir = os.path.dirname(self.file_path_edit.text().strip())
        elif getattr(self.main_window, "imagePaths", None):
            initial_dir = os.path.dirname(self.main_window.imagePaths[0])
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select calibration CSV",
            initial_dir,
            "CSV Files (*.csv);;All Files (*)",
            options=self.main_window.file_dialog_options(),
        )
        if file_path:
            self.calibration_path_edit.setText(file_path)

    def accept(self):
        file_path = self.file_path_edit.text().strip()
        calibration_path = self.calibration_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, "TAMU Linkam .xlsx import", "Choose a TAMU .xlsx file before importing.")
            return
        if not os.path.isfile(file_path):
            QMessageBox.warning(self, "TAMU Linkam .xlsx import", "The selected TAMU .xlsx file does not exist.")
            return
        if calibration_path and not os.path.isfile(calibration_path):
            QMessageBox.warning(self, "TAMU Linkam .xlsx import", "The selected calibration CSV does not exist.")
            return
        super().accept()

    def get_values(self):
        reset_temperature = float(self.reset_temperature_spinbox.value())
        if reset_temperature <= -999.0:
            reset_temperature = None
        return {
            "file_path": self.file_path_edit.text().strip(),
            "calibration_path": self.calibration_path_edit.text().strip(),
            "reset_temperature": reset_temperature,
        }


class OutputResultsDialog(QDialog):
    def __init__(self, parent=None, *, include_grayscale=False, include_freeze=False, include_temperature=False):
        super().__init__(parent)
        self.setWindowTitle("Output Results")
        self.setModal(True)
        self.resize(360, 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        intro_label = QLabel("Choose which result tables to export as CSV.", self)
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        self.select_all_checkbox = QCheckBox("Select All", self)
        layout.addWidget(self.select_all_checkbox)

        self.grayscale_checkbox = QCheckBox("Grayscale Measurements CSV", self)
        self.freeze_checkbox = QCheckBox("Freeze Events CSV", self)
        self.temperature_checkbox = QCheckBox("Temperature Sync CSV", self)

        self.grayscale_checkbox.setVisible(bool(include_grayscale))
        self.freeze_checkbox.setVisible(bool(include_freeze))
        self.temperature_checkbox.setVisible(bool(include_temperature))

        layout.addWidget(self.grayscale_checkbox)
        layout.addWidget(self.freeze_checkbox)
        layout.addWidget(self.temperature_checkbox)

        self.select_all_checkbox.toggled.connect(self.on_select_all_toggled)
        self.grayscale_checkbox.toggled.connect(self.sync_select_all_checkbox)
        self.freeze_checkbox.toggled.connect(self.sync_select_all_checkbox)
        self.temperature_checkbox.toggled.connect(self.sync_select_all_checkbox)
        self.sync_select_all_checkbox()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        if not any(self.selected_exports().values()):
            QMessageBox.warning(self, "Output Results", "Select at least one CSV to export.")
            return
        super().accept()

    def selected_exports(self):
        return {
            "grayscale": (not self.grayscale_checkbox.isHidden()) and self.grayscale_checkbox.isChecked(),
            "freeze": (not self.freeze_checkbox.isHidden()) and self.freeze_checkbox.isChecked(),
            "temperature": (not self.temperature_checkbox.isHidden()) and self.temperature_checkbox.isChecked(),
        }

    def visible_export_checkboxes(self):
        return [
            checkbox
            for checkbox in (
                self.grayscale_checkbox,
                self.freeze_checkbox,
                self.temperature_checkbox,
            )
            if not checkbox.isHidden()
        ]

    def on_select_all_toggled(self, checked):
        for checkbox in self.visible_export_checkboxes():
            with QSignalBlocker(checkbox):
                checkbox.setChecked(checked)
        self.sync_select_all_checkbox()

    def sync_select_all_checkbox(self):
        visible_checkboxes = self.visible_export_checkboxes()
        all_checked = bool(visible_checkboxes) and all(checkbox.isChecked() for checkbox in visible_checkboxes)
        with QSignalBlocker(self.select_all_checkbox):
            self.select_all_checkbox.setChecked(all_checked)


class DockTitleBar(QWidget):
    def __init__(self, dock_widget, title, parent=None):
        super().__init__(parent or dock_widget)
        self.dock_widget = dock_widget
        self.setFixedHeight(26)
        self.setAutoFillBackground(True)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        header_row = QWidget(self)
        layout = QHBoxLayout(header_row)
        layout.setContentsMargins(8, 1, 8, 3)
        layout.setSpacing(4)

        self.button_row = QWidget(header_row)
        button_layout = QHBoxLayout(self.button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)

        self.close_button = QToolButton(self.button_row)
        self.close_button.setAutoRaise(True)
        self.close_button.setFixedSize(14, 14)
        self.close_button.setIconSize(QSize(10, 10))
        self.close_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.close_button.clicked.connect(self.dock_widget.close)

        self.float_button = QToolButton(self.button_row)
        self.float_button.setAutoRaise(True)
        self.float_button.setFixedSize(14, 14)
        self.float_button.setIconSize(QSize(10, 10))
        self.float_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarNormalButton))
        self.float_button.clicked.connect(self.toggle_floating)

        button_layout.addWidget(self.close_button)
        button_layout.addWidget(self.float_button)

        self.title_label = QLabel(str(title), header_row)
        title_font = QFont(self.title_label.font())
        title_font.setPointSize(max(title_font.pointSize(), 12))
        title_font.setWeight(QFont.Medium)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)

        self.right_spacer = QWidget(header_row)
        self.right_spacer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        layout.addWidget(self.button_row, 0)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.right_spacer, 0)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setStyleSheet("color: rgba(0, 0, 0, 40);")

        outer_layout.addWidget(header_row)
        outer_layout.addWidget(separator)

        self.left_edge_cover = QFrame(self)
        self.left_edge_cover.setFrameShape(QFrame.NoFrame)
        self.left_edge_cover.setStyleSheet("background: palette(window);")
        self.left_edge_cover.hide()

        self.right_edge_cover = QFrame(self)
        self.right_edge_cover.setFrameShape(QFrame.NoFrame)
        self.right_edge_cover.setStyleSheet("background: palette(window);")
        self.right_edge_cover.hide()

        self.dock_widget.featuresChanged.connect(self.refresh_buttons)
        self.dock_widget.topLevelChanged.connect(self.refresh_buttons)
        try:
            self.dock_widget.dockLocationChanged.connect(self.refresh_buttons)
        except Exception:
            pass
        self.refresh_buttons()

    def toggle_floating(self):
        self.dock_widget.setFloating(not self.dock_widget.isFloating())

    def refresh_buttons(self, *args):
        features = self.dock_widget.features()
        self.close_button.setVisible(bool(features & QDockWidget.DockWidgetClosable))
        self.float_button.setVisible(bool(features & QDockWidget.DockWidgetFloatable))
        self.right_spacer.setFixedWidth(self.button_row.sizeHint().width())
        float_icon = (
            QStyle.SP_TitleBarNormalButton
            if self.dock_widget.isFloating()
            else QStyle.SP_TitleBarMaxButton
        )
        self.float_button.setIcon(self.style().standardIcon(float_icon))
        self.update_edge_covers()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_edge_covers()

    def update_edge_covers(self):
        left_visible = False
        right_visible = False
        main_window = self.dock_widget.parentWidget()
        if isinstance(main_window, QMainWindow) and not self.dock_widget.isFloating():
            try:
                dock_area = main_window.dockWidgetArea(self.dock_widget)
            except Exception:
                dock_area = Qt.NoDockWidgetArea
            if dock_area == Qt.LeftDockWidgetArea:
                right_visible = True
            elif dock_area == Qt.RightDockWidgetArea:
                left_visible = True

        cover_width = 2
        self.left_edge_cover.setGeometry(0, 0, cover_width, self.height())
        self.right_edge_cover.setGeometry(max(0, self.width() - cover_width), 0, cover_width, self.height())
        self.left_edge_cover.setVisible(left_visible)
        self.right_edge_cover.setVisible(right_visible)

    def mousePressEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        event.ignore()

    def mouseDoubleClickEvent(self, event):
        event.ignore()


class IceScopy(QMainWindow):

    def __init__(self):

        # SETTINGS
        self.circle_radius = 22 #default value
        self.pen_width = 1
        self.maximum_zoom = 10
        self.dot_size = 1
        self.slider_maxzoom_pixel_interval = 10
        self.slider_tick_pixel_interval = 20
        self.undo_limit = 20
        self.viewer_image_count = 1
        self.viewer_split_orientation = "horizontal"
        self.sort_mode = "natural_filename"
        self.grid_rows = 4
        self.grid_columns = 4
        self.grid_horizontal_pitch = 60
        self.grid_vertical_pitch = 60
        self.grid_rotation_degrees = 0
        self.grid_cell_id_direction = "left_to_right"
        self.radius_wheel_step = 1.0
        self.grid_pitch_wheel_step = 1.0
        self.grid_tilt_wheel_step = 1.0
        self.freeze_finder_width = 10.0
        self.freeze_finder_prominence = 100.0
        self.freeze_finder_tail_extend_points = 5
        self.convolution_half_window_points = 0
        self.convolution_ramp_points = 0
        self.freeze_finder_detect_brightening = False
        self.temperature_cycle_warmup_hysteresis_c = 0.02
        self.timeseries_palette = "bright"
        self.timeseries_trace_line_width = 2.0
        self.timeseries_convolution_line_width = 1.0
        self.timeseries_freeze_line_color = "220,20,60,180"
        self.timeseries_freeze_line_width = 1.0
        self.timeseries_current_frame_color = "255,204,0,220"
        self.timeseries_current_frame_line_width = 2.0
        self.circle_default_color = DEFAULT_VISUAL_COLORS["CircleDefaultColor"]
        self.circle_hover_color = DEFAULT_VISUAL_COLORS["CircleHoverColor"]
        self.circle_selected_color = DEFAULT_VISUAL_COLORS["CircleSelectedColor"]
        self.circle_edit_color = DEFAULT_VISUAL_COLORS["CircleEditColor"]
        self.circle_pressed_color = DEFAULT_VISUAL_COLORS["CirclePressedColor"]
        self.grid_preview_outline_color = DEFAULT_VISUAL_COLORS["GridPreviewOutlineColor"]
        self.grid_preview_fill_color = DEFAULT_VISUAL_COLORS["GridPreviewFillColor"]
        self.preview_handle_size = 12.0
        self.circle_label_offset_x = 6.0
        self.circle_label_offset_y = 6.0
        self.default_circle_radius = self.circle_radius
        self.default_grid_rows = self.grid_rows
        self.default_grid_columns = self.grid_columns
        self.default_grid_horizontal_pitch = self.grid_horizontal_pitch
        self.default_grid_vertical_pitch = self.grid_vertical_pitch
        self.default_grid_rotation_degrees = self.grid_rotation_degrees
        self.default_grid_cell_id_direction = self.grid_cell_id_direction
        self.edit_single_base_radius = None
        self.edit_single_radius_delta = 0.0
        self.edit_group_base_radius = None
        self.edit_group_base_radii_by_number = {}
        self.edit_group_radius_delta = 0.0
        self.edit_group_base_horizontal_pitch = None
        self.edit_group_base_vertical_pitch = None
        self.edit_group_base_rotation_degrees = None
        self.edit_group_horizontal_pitch_delta = 0.0
        self.edit_group_vertical_pitch_delta = 0.0
        self.edit_group_rotation_delta = 0.0
        
        super().__init__()
        self.cell_state = CellStateManager(self)
        self.cell_controller = CellEditController(self)
        self.undo_stack = QUndoStack(self)
        self.undo_redo_enabled = True
        self.image_list_enabled = True
        self.history_restoring = False
        # Tool actions can fire during initUI, so temporary key/mode state has
        # to exist before any default tool is triggered.
        self.temporary_event_data = {}
        self.space_held = False             # important for using space to activate an and zoom
        self.default_dock_state = None
        self.initData()
        self.initUI()
        self.set_preferences()

    def set_preferences(self, preserve_session_tool_state=False):
        preferences = {}
        # use .get() method on a dictionary to specify a default value if a key is not found.
        try:
            preferences = self.load_preferences_from_xml()
        except FileNotFoundError:
            print('No preference file set')
            # If the preferences.xml file is not found, you might want to save the default preferences
            pass

        current_tool_state = None
        if preserve_session_tool_state:
            current_tool_state = {
                "circle_radius": self.circle_radius,
                "grid_rows": self.grid_rows,
                "grid_columns": self.grid_columns,
                "grid_horizontal_pitch": self.grid_horizontal_pitch,
                "grid_vertical_pitch": self.grid_vertical_pitch,
                "grid_rotation_degrees": self.grid_rotation_degrees,
            }

        self.default_circle_radius = preferences.get('DefaultCircleRadius', self.default_circle_radius)
        self.circle_radius = self.default_circle_radius
        self.maximum_zoom = preferences.get('MaximumZoom', self.maximum_zoom)
        self.pen_width = max(1, preferences.get('PenWidth', self.pen_width))
        self.dot_size = preferences.get('DotSize', self.dot_size)
        self.slider_maxzoom_pixel_interval = preferences.get('SliderMaxZoomPixelInterval', self.slider_maxzoom_pixel_interval)
        self.slider_tick_pixel_interval = preferences.get('SliderTickPixelInterval', self.slider_tick_pixel_interval)
        self.undo_limit = int(preferences.get('UndoLimit', self.undo_limit))
        self.sample_name_pattern = str(
            preferences.get('SampleNamePattern', getattr(self, "sample_name_pattern", "Sample_#"))
        )
        self.viewer_image_count = int(preferences.get('ViewerImageCount', self.viewer_image_count))
        self.sort_mode = preferences.get('SortMode', self.sort_mode)
        self.default_grid_rows = int(preferences.get('GridRows', self.default_grid_rows))
        self.default_grid_columns = int(preferences.get('GridColumns', self.default_grid_columns))
        self.default_grid_horizontal_pitch = preferences.get('GridHorizontalPitch', self.default_grid_horizontal_pitch)
        self.default_grid_vertical_pitch = preferences.get('GridVerticalPitch', self.default_grid_vertical_pitch)
        self.default_grid_rotation_degrees = preferences.get('GridRotationDegrees', self.default_grid_rotation_degrees)
        self.default_grid_cell_id_direction = preferences.get('GridCellIdDirection', self.default_grid_cell_id_direction)
        self.grid_rows = self.default_grid_rows
        self.grid_columns = self.default_grid_columns
        self.grid_horizontal_pitch = self.default_grid_horizontal_pitch
        self.grid_vertical_pitch = self.default_grid_vertical_pitch
        self.grid_rotation_degrees = self.default_grid_rotation_degrees
        self.grid_cell_id_direction = self.default_grid_cell_id_direction
        self.radius_wheel_step = preferences.get('RadiusWheelStep', self.radius_wheel_step)
        self.grid_pitch_wheel_step = preferences.get('GridPitchWheelStep', self.grid_pitch_wheel_step)
        self.grid_tilt_wheel_step = preferences.get('GridTiltWheelStep', self.grid_tilt_wheel_step)
        self.freeze_finder_width = preferences.get('FreezeFinderWidth', self.freeze_finder_width)
        self.freeze_finder_prominence = preferences.get('FreezeFinderProminence', self.freeze_finder_prominence)
        self.freeze_finder_tail_extend_points = int(
            preferences.get('FreezeFinderTailExtendPoints', self.freeze_finder_tail_extend_points)
        )
        self.convolution_half_window_points = int(
            preferences.get('ConvolutionHalfWindowPoints', self.convolution_half_window_points)
        )
        self.convolution_ramp_points = int(
            preferences.get('ConvolutionRampPoints', self.convolution_ramp_points)
        )
        self.freeze_finder_detect_brightening = bool(
            preferences.get('FreezeFinderDetectBrightening', self.freeze_finder_detect_brightening)
        )
        self.temperature_cycle_warmup_hysteresis_c = float(
            preferences.get(
                'TemperatureCycleWarmupHysteresisC',
                self.temperature_cycle_warmup_hysteresis_c,
            )
        )
        self.timeseries_palette = preferences.get('TimeseriesPalette', self.timeseries_palette)
        self.timeseries_trace_line_width = float(
            preferences.get('TimeseriesTraceLineWidth', self.timeseries_trace_line_width)
        )
        self.timeseries_convolution_line_width = float(
            preferences.get('TimeseriesConvolutionLineWidth', self.timeseries_convolution_line_width)
        )
        self.timeseries_freeze_line_color = preferences.get(
            'TimeseriesFreezeLineColor',
            self.timeseries_freeze_line_color,
        )
        self.timeseries_freeze_line_width = float(
            preferences.get('TimeseriesFreezeLineWidth', self.timeseries_freeze_line_width)
        )
        self.timeseries_current_frame_color = preferences.get(
            'TimeseriesCurrentFrameColor',
            self.timeseries_current_frame_color,
        )
        self.timeseries_current_frame_line_width = float(
            preferences.get('TimeseriesCurrentFrameLineWidth', self.timeseries_current_frame_line_width)
        )
        self.circle_default_color = preferences.get('CircleDefaultColor', self.circle_default_color)
        self.circle_hover_color = preferences.get('CircleHoverColor', self.circle_hover_color)
        self.circle_selected_color = preferences.get('CircleSelectedColor', self.circle_selected_color)
        self.circle_edit_color = preferences.get('CircleEditColor', self.circle_edit_color)
        self.circle_pressed_color = preferences.get('CirclePressedColor', self.circle_pressed_color)
        self.grid_preview_outline_color = preferences.get('GridPreviewOutlineColor', self.grid_preview_outline_color)
        self.grid_preview_fill_color = preferences.get('GridPreviewFillColor', self.grid_preview_fill_color)
        self.preview_handle_size = float(preferences.get('PreviewHandleSize', self.preview_handle_size))
        self.circle_label_offset_x = float(preferences.get('CircleLabelOffsetX', self.circle_label_offset_x))
        self.circle_label_offset_y = float(preferences.get('CircleLabelOffsetY', self.circle_label_offset_y))

        if current_tool_state is not None:
            self.circle_radius = current_tool_state["circle_radius"]
            self.grid_rows = current_tool_state["grid_rows"]
            self.grid_columns = current_tool_state["grid_columns"]
            self.grid_horizontal_pitch = current_tool_state["grid_horizontal_pitch"]
            self.grid_vertical_pitch = current_tool_state["grid_vertical_pitch"]
            self.grid_rotation_degrees = current_tool_state["grid_rotation_degrees"]

        if self.undo_stack.count() == 0:
            self.undo_stack.setUndoLimit(self.undo_limit)
        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()
        if hasattr(self, "tool_options_stack"):
            self.sync_tool_options_panel()
        if hasattr(self, "radius_textbox"):
            self.updateRadiusTextbox()
        if hasattr(self, "viewer_single_action"):
            self.update_viewer_mode_actions()
        if self.imagePaths and hasattr(self, "view"):
            self.updateImage(self.image_index)
        elif hasattr(self, "view"):
            self.view.viewport().update()
        if hasattr(self, "cell_controller") and self.cell_controller.uses_grid_preview():
            self.update_grid_preview()
        if hasattr(self, "grayscale_plot_widget"):
            self.refresh_grayscale_plot()
        self.scene.update()

    def get_qcolor(self, color_value):
        if isinstance(color_value, QColor):
            return QColor(color_value)
        try:
            red, green, blue, alpha = [int(part.strip()) for part in str(color_value).split(",")]
            return QColor(red, green, blue, alpha)
        except Exception:
            return QColor(255, 0, 0, 255)

    def sample_visual_color(self, sample_id, alpha=255):
        if sample_id in (None, ""):
            return None
        try:
            palette_index = max(0, int(sample_id))
        except (TypeError, ValueError):
            return None
        red, green, blue = SAMPLE_VISUAL_PALETTE[palette_index % len(SAMPLE_VISUAL_PALETTE)]
        return QColor(red, green, blue, alpha)

    def sample_visual_color_for_cell(self, cell_id, alpha=255):
        record = self.ensure_cell_record(cell_id)
        if record is None:
            return None
        return self.sample_visual_color(getattr(record, "sample_id", ""), alpha=alpha)

    def refresh_cell_sample_visuals(self):
        for item in getattr(self, "cell_items", []):
            item.update()
        if hasattr(self, "scene"):
            self.scene.update()

    def extract_cell_id_from_analysis_header(self, header_text):
        return self.cell_state.extract_cell_id_from_analysis_header(header_text)

    def extract_cell_id_from_label(self, label_text):
        return self.cell_state.extract_cell_id_from_label(label_text)

    def serialize_cell_records(self):
        return self.cell_state.serialize_cell_records()

    def deserialize_cell_records(self, payload):
        return self.cell_state.deserialize_cell_records(payload)

    def ensure_cell_record(self, cell_id):
        return self.cell_state.ensure_cell_record(cell_id)

    def ensure_cell_registry_matches_scene_cells(self):
        self.cell_state.ensure_cell_registry_matches_scene_cells()

    def recompute_next_cell_id(self, preserve_if_larger=True):
        return self.cell_state.recompute_next_cell_id(preserve_if_larger=preserve_if_larger)

    def allocate_cell_id(self):
        return self.cell_state.allocate_cell_id()

    def cell_id_exists(self, cell_id, exclude_cell_id=None):
        return self.cell_state.cell_id_exists(cell_id, exclude_cell_id=exclude_cell_id)

    def rename_cell_id(self, old_cell_id, new_cell_id):
        return self.cell_state.rename_cell_id(old_cell_id, new_cell_id)

    def clear_cell_analysis(self):
        self.cell_state.clear_cell_analysis()

    def sync_cell_analysis_from_results(self):
        self.cell_state.sync_cell_analysis_from_results()

    def prune_analysis_results_for_deleted_cells(self, deleted_cell_ids):
        return self.cell_state.prune_analysis_results_for_deleted_cells(deleted_cell_ids)

    def serialize_sample_catalog(self):
        catalog = getattr(self, "sample_catalog", {})
        return {
            str(int(sample_id)): str(sample_name)
            for sample_id, sample_name in sorted(catalog.items(), key=lambda pair: int(pair[0]))
        }

    def deserialize_sample_catalog(self, payload):
        catalog = {}
        if not isinstance(payload, dict):
            return catalog
        for key, value in payload.items():
            try:
                sample_id = int(key)
            except (TypeError, ValueError):
                continue
            catalog[sample_id] = str(value)
        return catalog

    def recompute_next_sample_id(self, preserve_if_larger=True):
        max_sample_id = -1
        for sample_id in getattr(self, "sample_catalog", {}).keys():
            try:
                max_sample_id = max(max_sample_id, int(sample_id))
            except (TypeError, ValueError):
                continue
        derived_next = max_sample_id + 1
        if preserve_if_larger:
            self.next_sample_id = max(int(getattr(self, "next_sample_id", 0)), derived_next)
        else:
            self.next_sample_id = derived_next
        if self.next_sample_id < 0:
            self.next_sample_id = 0
        return self.next_sample_id

    def allocate_sample_id(self):
        self.recompute_next_sample_id(preserve_if_larger=True)
        sample_id = int(self.next_sample_id)
        self.next_sample_id = sample_id + 1
        return sample_id

    def default_sample_name(self, sample_id):
        try:
            sample_id = int(sample_id)
        except (TypeError, ValueError):
            sample_id = 0
        pattern = str(getattr(self, "sample_name_pattern", "Sample_#") or "Sample_#")
        sample_id_text = str(sample_id)
        output = []
        index = 0
        while index < len(pattern):
            char = pattern[index]
            if char == "\\":
                if index + 1 < len(pattern) and pattern[index + 1] in ("#", "\\"):
                    output.append(pattern[index + 1])
                    index += 2
                    continue
                output.append("\\")
                index += 1
                continue
            if char == "#":
                output.append(sample_id_text)
            else:
                output.append(char)
            index += 1
        return "".join(output)

    def sample_name_for_id(self, sample_id):
        if sample_id in (None, ""):
            return ""
        try:
            sample_key = int(sample_id)
        except (TypeError, ValueError):
            return ""
        return str(self.sample_catalog.get(sample_key, ""))

    def ensure_sample_catalog_matches_cell_records(self):
        if not hasattr(self, "sample_catalog") or not isinstance(self.sample_catalog, dict):
            self.sample_catalog = {}
        for record in getattr(self, "cell_records_by_id", {}).values():
            sample_value = str(getattr(record, "sample_id", "")).strip()
            if not sample_value:
                continue
            try:
                sample_id = int(sample_value)
            except (TypeError, ValueError):
                continue
            if sample_id < 0:
                continue
            if sample_id not in self.sample_catalog:
                self.sample_catalog[sample_id] = self.default_sample_name(sample_id)
        self.recompute_next_sample_id(preserve_if_larger=True)

    def cursor_sample_catalog_signature(self):
        return tuple(
            (str(int(sample_id)), str(sample_name))
            for sample_id, sample_name in sorted(self.sample_catalog.items(), key=lambda pair: int(pair[0]))
        )

    def invalidate_cursor_sample_combo_cache(self):
        self.cursor_sample_combo_catalog_signature = None
        self.cursor_sample_combo_has_mixed_item = False

    def set_cursor_sample_combo_mixed_item_visible(self, visible):
        if not hasattr(self, "cursor_sample_combo"):
            return

        mixed_index = self.cursor_sample_combo.findData("__mixed__")
        currently_visible = mixed_index >= 0
        if visible == currently_visible:
            self.cursor_sample_combo_has_mixed_item = visible
            return

        blocker = QSignalBlocker(self.cursor_sample_combo)
        if visible:
            self.cursor_sample_combo.insertItem(0, "Mixed Selection", "__mixed__")
        elif mixed_index >= 0:
            self.cursor_sample_combo.removeItem(mixed_index)
        self.cursor_sample_combo_has_mixed_item = visible

    def refresh_cursor_sample_combo_catalog(self, include_mixed_item=False, force=False):
        if not hasattr(self, "cursor_sample_combo"):
            return

        catalog_signature = self.cursor_sample_catalog_signature()
        cached_signature = getattr(self, "cursor_sample_combo_catalog_signature", None)
        needs_rebuild = force or (catalog_signature != cached_signature) or (self.cursor_sample_combo.count() == 0)

        if needs_rebuild:
            blocker = QSignalBlocker(self.cursor_sample_combo)
            self.cursor_sample_combo.clear()
            self.cursor_sample_combo.addItem("None", "")
            for sample_id_text, sample_name in catalog_signature:
                self.cursor_sample_combo.addItem(sample_id_text, sample_id_text)
            self.cursor_sample_combo_catalog_signature = catalog_signature
            self.cursor_sample_combo_has_mixed_item = False

        self.set_cursor_sample_combo_mixed_item_visible(include_mixed_item)

    def summarize_integer_list(self, values, limit=8):
        normalized_values = []
        for value in values:
            try:
                normalized_values.append(int(value))
            except (TypeError, ValueError):
                continue
        if not normalized_values:
            return "-"

        unique_values = sorted(set(normalized_values))
        preview = ", ".join(str(value) for value in unique_values[:limit])
        if len(unique_values) > limit:
            preview += f", +{len(unique_values) - limit} more"
        return preview

    def format_numeric_display(self, value, decimals=1):
        if value in (None, ""):
            return "-"
        try:
            return f"{float(value):.{decimals}f}"
        except (TypeError, ValueError):
            return "-"

    def set_cursor_display_field_locked(self, field, locked):
        if field is None:
            return
        field.setEnabled(True)
        field.setReadOnly(bool(locked))
        field.setFocusPolicy(Qt.NoFocus if locked else Qt.StrongFocus)

    def format_integer_list_csv(self, values):
        normalized_values = []
        seen_values = set()
        for value in values:
            try:
                normalized = int(value)
            except (TypeError, ValueError):
                continue
            if normalized in seen_values:
                continue
            seen_values.add(normalized)
            normalized_values.append(normalized)
        if not normalized_values:
            return "-"
        return ", ".join(str(value) for value in normalized_values)

    def parse_integer_csv_text(self, text, *, allow_empty=True, minimum=None, maximum=None):
        raw_text = str(text or "").strip()
        if not raw_text:
            return [] if allow_empty else None

        values = []
        seen_values = set()
        for token in raw_text.split(","):
            piece = token.strip()
            if not piece:
                continue
            try:
                value = int(piece)
            except (TypeError, ValueError):
                return None
            if minimum is not None and value < minimum:
                return None
            if maximum is not None and value > maximum:
                return None
            if value in seen_values:
                continue
            seen_values.add(value)
            values.append(value)
        return values

    def parse_freeze_frame_text(self, text):
        raw_text = str(text or "").strip()
        if raw_text.lower() in {"", "none", "-", "clear"}:
            return []
        return self.parse_integer_csv_text(raw_text, allow_empty=True, minimum=0, maximum=100000)

    def rebuild_freeze_rows_for_cell(self, cell_id, freeze_event_indices):
        rebuilt_rows = []
        label = f"cell_{int(cell_id)}"
        for frame_index in freeze_event_indices:
            image_name = ""
            if 0 <= int(frame_index) < len(self.grayscale_results_rows):
                row = self.grayscale_results_rows[int(frame_index)]
                if len(row) > 0:
                    image_name = str(row[0])
            elif 0 <= int(frame_index) < len(self.imageNames):
                image_name = str(self.imageNames[int(frame_index)])
            rebuilt_rows.append([
                label,
                str(int(frame_index)),
                image_name,
            ])
        return rebuilt_rows

    def apply_manual_freeze_event_indices(self, cell_id, freeze_event_indices, refresh_tables=True):
        record = self.ensure_cell_record(cell_id)
        if record is None:
            return

        normalized_indices = [int(value) for value in freeze_event_indices]
        record.freeze_event_indices = list(normalized_indices)
        rebuilt_rows = self.rebuild_freeze_rows_for_cell(cell_id, normalized_indices)
        record.freeze_rows = [list(row) for row in rebuilt_rows]

        target_label = f"cell_{int(cell_id)}"
        kept_rows = [
            list(row)
            for row in self.freeze_results_rows
            if not row or str(row[0]) != target_label
        ]
        kept_rows.extend(rebuilt_rows)
        kept_rows.sort(
            key=lambda row: (
                self.extract_cell_id_from_label(row[0] if row else None) or -1,
                int(row[1]) if len(row) > 1 and str(row[1]).strip().isdigit() else -1,
            )
        )
        self.freeze_results_rows = kept_rows
        if rebuilt_rows and not self.freeze_results_headers:
            self.freeze_results_headers = ["cell", "image_index", "image_name"]
        self.last_freeze_output_path = None
        if hasattr(self, "grayscale_plot_widget"):
            self.grayscale_plot_widget.invalidate_render_cache()
        self.invalidate_temperature_sync_results("freeze frame annotations changed")
        if refresh_tables:
            self.update_results_tables()

    def build_cells_panel_records(self):
        self.ensure_cell_registry_matches_scene_cells()
        records = []
        for cell_id in sorted(self.cell_records_by_id.keys()):
            record = self.ensure_cell_record(cell_id)
            sample_id = str(getattr(record, "sample_id", ""))
            sample_name = self.sample_name_for_id(sample_id)
            freeze_frames = list(getattr(record, "freeze_event_indices", []))
            grayscale_trace = list(getattr(record, "grayscale_trace", []))
            freeze_rows = list(getattr(record, "freeze_rows", []))
            records.append({
                "cell_id": int(cell_id),
                "sample_id": sample_id,
                "sample_name": sample_name,
                "freeze_frames": self.summarize_integer_list(freeze_frames),
            })
        return records

    def refresh_cells_panel(self, changed_columns=None, preserve_selection=False):
        if not hasattr(self, "cells_tree_widget"):
            return
        if (not self.should_refresh_cells_panel_from_redraw()) and not bool(getattr(self, "cells_panel_force_refresh", False)):
            self.cells_panel_dirty = True
            return

        expanded_cell_ids = set()
        for index in range(self.cells_tree_widget.topLevelItemCount()):
            item = self.cells_tree_widget.topLevelItem(index)
            if item.isExpanded():
                cell_id = item.data(0, Qt.UserRole)
                if cell_id is not None:
                    expanded_cell_ids.add(int(cell_id))
        selected_cell_ids = {
            int(item.cell_id)
            for item in self.get_selected_cell_items()
        }

        records = self.build_cells_panel_records()
        tree_snapshot = tuple(
            (
                record["cell_id"],
                record["sample_id"],
                record["sample_name"],
                record["freeze_frames"],
            )
            for record in records
        )
        if tree_snapshot == getattr(self, "cells_panel_last_snapshot", None) and not bool(getattr(self, "cells_panel_force_refresh", False)):
            self.cells_panel_dirty = False
            return

        tree_blocker = QSignalBlocker(self.cells_tree_widget)
        try:
            self.cells_tree_widget.clear()
            for record in records:
                cell_id = int(record["cell_id"])
                sample_id = str(record["sample_id"] or "-")
                sample_name = str(record["sample_name"] or "-")
                freeze_frames = str(record["freeze_frames"] or "-")
                top_item = QTreeWidgetItem([f"Cell {cell_id}", ""])
                top_item.setData(0, Qt.UserRole, cell_id)

                detail_rows = (
                    ("Cell ID", str(cell_id)),
                    ("Sample ID", sample_id),
                    ("Sample Name", sample_name),
                    ("Freeze Frame(s)", freeze_frames),
                )
                for field_name, value_text in detail_rows:
                    child_item = QTreeWidgetItem([field_name, value_text])
                    child_item.setFlags(child_item.flags() & ~Qt.ItemIsSelectable)
                    top_item.addChild(child_item)

                self.cells_tree_widget.addTopLevelItem(top_item)
                if cell_id in expanded_cell_ids:
                    top_item.setExpanded(True)
                if cell_id in selected_cell_ids:
                    top_item.setSelected(True)
        finally:
            del tree_blocker

        self.cells_panel_last_snapshot = tree_snapshot
        self.cells_panel_dirty = False
        self.cells_panel_force_refresh = False

    def sync_cells_panel_selection(self):
        if not hasattr(self, "cells_tree_widget"):
            return
        selected_cell_ids = {
            int(item.cell_id)
            for item in self.get_selected_cell_items()
        }
        blocker = QSignalBlocker(self.cells_tree_widget)
        try:
            for index in range(self.cells_tree_widget.topLevelItemCount()):
                item = self.cells_tree_widget.topLevelItem(index)
                cell_id = item.data(0, Qt.UserRole)
                if cell_id is None:
                    continue
                item.setSelected(int(cell_id) in selected_cell_ids)
        finally:
            del blocker

    def handle_cells_panel_selection_changed(self):
        if not hasattr(self, "cells_tree_widget"):
            return
        selected_cell_ids = []
        for item in self.cells_tree_widget.selectedItems():
            if item.parent() is not None:
                continue
            cell_id = item.data(0, Qt.UserRole)
            if cell_id is None:
                continue
            selected_cell_ids.append(int(cell_id))
        self.reselect_cell_ids(selected_cell_ids, sync_tool_panel=True)

    def should_refresh_cells_panel_from_redraw(self):
        if bool(getattr(self, "preview_frame_update_in_progress", False)):
            return False
        dock = getattr(self, "cells_dock", None)
        if dock is None or (not shiboken6.isValid(dock)):
            return False
        toggle_action = dock.toggleViewAction()
        if toggle_action is None:
            return True
        return bool(toggle_action.isChecked())

    def handle_cells_panel_visibility_changed(self, visible):
        if not visible:
            return
        self.cells_panel_force_refresh = True
        self.refresh_cells_panel()

    def refresh_cursor_selection_info(self, selected_items=None):
        if not hasattr(self, "cursor_info_value_labels"):
            return 0

        if selected_items is None:
            selected_items = sorted(
                self.get_selected_cell_items(),
                key=lambda item: int(getattr(item, "cell_id", 0)),
            )

        selected_ids = []
        selected_sample_names = set()
        for item in selected_items:
            selected_ids.append(int(item.cell_id))
            record = self.ensure_cell_record(item.cell_id)
            sample_id = str(getattr(record, "sample_id", ""))
            selected_sample_names.add(self.sample_name_for_id(sample_id))

        info_values = {
            "cell_id": "-",
            "sample_name": "-",
            "x": "-",
            "y": "-",
            "radius": "-",
            "selected": "0",
        }
        if len(selected_items) == 1:
            item = selected_items[0]
            record = self.ensure_cell_record(item.cell_id)
            pixel_x = None
            pixel_y = None
            radius = None
            try:
                pixel_x = float(item.circle_pixel_positions[0])
                pixel_y = float(item.circle_pixel_positions[1])
                radius = float(item.circle_sizes)
            except (AttributeError, IndexError, TypeError, ValueError):
                pass
            info_values.update({
                "cell_id": str(int(item.cell_id)),
                "sample_name": self.sample_name_for_id(getattr(record, "sample_id", "")) or "-",
                "x": self.format_numeric_display(pixel_x),
                "y": self.format_numeric_display(pixel_y),
                "radius": self.format_numeric_display(radius),
            })
        elif len(selected_items) > 1:
            selected_sample_name_values = {value for value in selected_sample_names}
            if len(selected_sample_name_values) == 1:
                only_sample_name = next(iter(selected_sample_name_values))
                sample_name_text = only_sample_name or "-"
            else:
                sample_name_text = "Mixed"
            info_values.update({
                "selected": str(len(selected_items)),
                "cell_id": self.summarize_integer_list(selected_ids),
                "sample_name": sample_name_text,
                "x": "Multiple",
                "y": "Multiple",
                "radius": "Multiple",
            })

        for field_name, value_label in self.cursor_info_value_labels.items():
            value_label.setText(str(info_values.get(field_name, "-")))

        has_selection = bool(selected_items)
        single_selected = len(selected_items) == 1
        self.cursor_info_section_label.setVisible(has_selection)
        self.cursor_info_row_widgets["selected"].setVisible(len(selected_items) > 1)
        self.cursor_info_row_widgets["cell_id"].setVisible(has_selection)
        self.cursor_info_row_widgets["sample_name"].setVisible(has_selection)
        self.cursor_info_row_widgets["x"].setVisible(single_selected)
        self.cursor_info_row_widgets["y"].setVisible(single_selected)
        self.cursor_info_row_widgets["radius"].setVisible(single_selected)
        self.cursor_info_label_widgets["cell_id"].setText("Cell IDs:" if len(selected_items) > 1 else "Cell ID:")

        return len(selected_ids)

    def update_cursor_record_edit_state(self, selected_items=None):
        if not hasattr(self, "cursor_sample_combo"):
            return

        if selected_items is None:
            selected_items = sorted(
                self.get_selected_cell_items(),
                key=lambda item: int(getattr(item, "cell_id", 0)),
            )

        has_selection = bool(selected_items)
        single_selected = len(selected_items) == 1
        self.cursor_edit_section_label.setVisible(has_selection)
        if hasattr(self, "cursor_info_edit_separator"):
            self.cursor_info_edit_separator.setVisible(has_selection)
        self.cursor_sample_row.setVisible(has_selection)
        self.cursor_sample_button_row.setVisible(has_selection)
        self.cursor_freeze_row.setVisible(single_selected)
        if hasattr(self, "cursor_freeze_lineedit"):
            self.cursor_freeze_lineedit.setEnabled(single_selected)
            if hasattr(self, "cursor_freeze_apply_button"):
                self.cursor_freeze_apply_button.setEnabled(single_selected)
            blocker = QSignalBlocker(self.cursor_freeze_lineedit)
            if single_selected:
                record = self.ensure_cell_record(selected_items[0].cell_id)
                freeze_values = [int(value) for value in getattr(record, "freeze_event_indices", [])]
                self.cursor_freeze_lineedit.setText(
                    "None" if not freeze_values else self.format_integer_list_csv(freeze_values)
                )
                self.cursor_freeze_lineedit.setPlaceholderText("None")
            else:
                self.cursor_freeze_lineedit.clear()
                self.cursor_freeze_lineedit.setPlaceholderText("")

    def apply_cursor_freeze_frames_edit(self):
        selected_items = sorted(
            self.get_selected_cell_items(),
            key=lambda item: int(getattr(item, "cell_id", 0)),
        )
        if len(selected_items) != 1:
            return False

        if not hasattr(self, "cursor_freeze_lineedit"):
            return False

        parsed_values = self.parse_freeze_frame_text(self.cursor_freeze_lineedit.text())
        if parsed_values is None:
            QMessageBox.warning(
                self,
                "Freeze Frame",
                "Enter freeze frames as comma-separated non-negative integers, or use None to clear them.",
            )
            return False

        target_cell_id = int(selected_items[0].cell_id)
        current_values = [
            int(value)
            for value in getattr(self.ensure_cell_record(target_cell_id), "freeze_event_indices", [])
        ]
        if current_values == parsed_values:
            self.cursor_freeze_lineedit.clearFocus()
            if hasattr(self, "view"):
                self.view.setFocus()
                self.view.viewport().setFocus()
            return True

        before_state = self.capture_data_state()
        self.apply_manual_freeze_event_indices(target_cell_id, parsed_values, refresh_tables=False)
        self.update_results_tables()
        self.refresh_cursor_selection_info(selected_items=selected_items)
        self.push_data_history("Edit Freeze Frames", before_state)
        self.log(
            f"Update freeze frames for cell {target_cell_id} to "
            f"{self.format_integer_list_csv(parsed_values)}"
        )
        self.cursor_freeze_lineedit.clearFocus()
        if hasattr(self, "view"):
            self.view.setFocus()
            self.view.viewport().setFocus()
        return True

    def current_single_edit_target_item(self):
        target_items = self.cell_controller.get_edit_chosen_items()
        if len(target_items) == 1:
            return target_items[0]
        target_items = self.get_edit_target_items()
        if len(target_items) == 1:
            return target_items[0]
        return None

    def apply_edit_circle_cell_id_edit(self):
        if self.tool_mode != "edit-new" or not hasattr(self, "edit_circle_cell_id_spinbox"):
            return

        target_item = self.current_single_edit_target_item()
        if target_item is None:
            return

        old_cell_id = int(target_item.cell_id)
        new_cell_id = int(self.edit_circle_cell_id_spinbox.value())
        if new_cell_id == old_cell_id:
            return

        before_state = self.capture_cell_state(include_analysis=True)
        renamed, message = self.rename_cell_id(old_cell_id, new_cell_id)
        if not renamed:
            QMessageBox.warning(self, "Rename Cell ID", message or "Unable to rename the selected cell.")
            self.sync_tool_options_panel()
            return

        self.cell_controller.redraw_current_cells(preserve_selection=False, force_scene_scan=True)
        self.reset_cell_items_edit_chosen()
        for item in self.cell_items:
            if int(getattr(item, "cell_id", -1)) == new_cell_id:
                item.edit_chosen = True
                item.update()
                break
        self.reselect_cell_ids([new_cell_id], sync_tool_panel=False)
        self.refresh_grayscale_plot()
        self.push_cell_history("Rename Cell ID", before_state, include_analysis=True)
        self.log(f"Rename cell {old_cell_id} to {new_cell_id}")
        self.sync_tool_options_panel()

    def restore_add_defaults(self, include_grid=False):
        self.circle_radius = float(self.default_circle_radius)
        if include_grid:
            self.grid_rows = int(self.default_grid_rows)
            self.grid_columns = int(self.default_grid_columns)
            self.grid_horizontal_pitch = float(self.default_grid_horizontal_pitch)
            self.grid_vertical_pitch = float(self.default_grid_vertical_pitch)
            self.grid_rotation_degrees = float(self.default_grid_rotation_degrees)

    def initData(self):
        # Gets called so wiped at loading images
        # All Attributes related to data
        if hasattr(self, 'image_cache'):
            self.image_cache.clear()
        if hasattr(self, 'pixmap_cache'):
            self.pixmap_cache.clear()
        self.cell_items = [] # current displayed cell items
        self.rendered_cell_items = [] # currently drawn QGraphics items for cells
        self.next_cell_id = 0
        self.cell_records_by_id = {}
        self.sample_catalog = {}
        self.invalidate_cursor_sample_combo_cache()
        self.next_sample_id = 0
        self.image_edit_exposure = 0.0
        self.image_edit_contrast = 0.0
        self.image_edit_uniform_exposure_area_x = None
        self.image_edit_uniform_exposure_area_y = None
        self.image_edit_uniform_exposure_area_width = None
        self.image_edit_uniform_exposure_area_height = None
        self.image_edit_uniform_exposure_offsets = {}
        self.image_edit_crop_center_x = None
        self.image_edit_crop_center_y = None
        self.image_edit_crop_width = None
        self.image_edit_crop_height = None
        self.image_edit_crop_angle = 0.0

        self.keyframe_list = []
        self.flagframe_list = []
        self.keyframe_cell_items_dict = {} # a dictionary. {frame number: cell_items}
        
        
        self.image_width = None  # Add image_width attribute
        self.imagePaths = []
        self.imageNames = []
        self.image_index = 0  # Index of the currently displayed image
        self.last_committed_image_index = 0
        self.pending_preview_image_index = None
        self.preview_frame_update_in_progress = False
        self.pending_image_edit_preview_state = None
        self.image_edit_preview_in_progress = False
        self.pending_image_edit_histogram_qimage = None
        if hasattr(self, "image_edit_preview_timer"):
            self.image_edit_preview_timer.stop()
        if hasattr(self, "image_edit_histogram_timer"):
            self.image_edit_histogram_timer.stop()
        self.last_grayscale_output_path = None
        self.last_freeze_output_path = None
        self.grayscale_results_headers = []
        self.grayscale_results_rows = []
        self.freeze_results_headers = []
        self.freeze_results_rows = []
        self.temperature_sync_headers = []
        self.temperature_sync_rows = []
        self.temperature_sync_summary = {}
        self.last_temperature_import_path = None
        self.last_temperature_calibration_path = None
        self.last_temperature_reset_temperature = None
        self.pending_navigation_before_index = None
        self.pending_navigation_history_text = "Change Frame"
        self.slider_drag_start_index = None
        self.analysis_progress_navigation_suppressed = False
        self.analysis_progress_start_index = None
        self.pending_analysis_progress_index = None
        self.pending_analysis_before_state = None
        self.sort_mode = getattr(self, "sort_mode", "natural_filename")
        self.session_project_name = ""
        self.session_user_name = ""
        self.session_institution = ""
        self.session_date = ""

        # miscellaneous
        self.timer = None
        self.output_state = False
        self.raw_image_cache = OrderedDict()
        self.raw_image_cache_size = 4
        self.image_cache = OrderedDict()
        self.image_cache_size = 8
        self.pixmap_cache = OrderedDict()
        self.pixmap_cache_size = 8
        self.raw_image_size_cache = {}
        self.image_edit_histogram_scale_cache = {}
        self.image_edit_uniform_exposure_overlay = None
        self.image_edit_crop_overlay = None
        self.displayed_image_edit_crop_applied = None
        self.context_pixmap_items = []
        self.placeholder_items = []
        self.grid_preview_items = []
        self.grid_preview_handle_item = None
        self.grid_preview_origin_pixels = None
        self.grid_preview_floating = True
        self.preview_offset_x = 0.0
        self.preview_offset_y = 0.0
        self.cell_controller.reset()
        self.image_list_entry_ids = []
        self.next_image_list_entry_id = 0
        self.syncing_image_list_selection = False
        self.active_image_panel = "viewer"
        self.tool_mode = "cursor"
        self.session_active = False
        self.current_session_file_path = None
        self.update_session_metadata_status_label()

    def serialize_session_metadata(self):
        return {
            "project_name": str(getattr(self, "session_project_name", "")).strip(),
            "user_name": str(getattr(self, "session_user_name", "")).strip(),
            "institution": str(getattr(self, "session_institution", "")).strip(),
            "date": str(getattr(self, "session_date", "")).strip(),
        }

    def serialize_image_edit_state(self):
        valid_paths = {str(path) for path in getattr(self, "imagePaths", [])}
        return {
            "exposure": float(getattr(self, "image_edit_exposure", 0.0)),
            "contrast": float(getattr(self, "image_edit_contrast", 0.0)),
            "uniform_exposure": {
                "area": {
                    "x": getattr(self, "image_edit_uniform_exposure_area_x", None),
                    "y": getattr(self, "image_edit_uniform_exposure_area_y", None),
                    "width": getattr(self, "image_edit_uniform_exposure_area_width", None),
                    "height": getattr(self, "image_edit_uniform_exposure_area_height", None),
                },
                "offsets": {
                    str(path): float(value)
                    for path, value in dict(getattr(self, "image_edit_uniform_exposure_offsets", {})).items()
                    if str(path) in valid_paths and abs(float(value)) > 1e-9
                },
            },
            "crop": {
                "center_x": getattr(self, "image_edit_crop_center_x", None),
                "center_y": getattr(self, "image_edit_crop_center_y", None),
                "width": getattr(self, "image_edit_crop_width", None),
                "height": getattr(self, "image_edit_crop_height", None),
                "angle": float(getattr(self, "image_edit_crop_angle", 0.0)),
            },
        }

    def apply_image_edit_state(self, state, *, invalidate_results=False, refresh_display=True, sync_controls=True):
        try:
            exposure_value = float((state or {}).get("exposure", 0.0))
        except (AttributeError, TypeError, ValueError):
            exposure_value = 0.0
        try:
            contrast_value = float((state or {}).get("contrast", 0.0))
        except (AttributeError, TypeError, ValueError):
            contrast_value = 0.0
        uniform_exposure_state = (state or {}).get("uniform_exposure", {})
        raw_uniform_area = (uniform_exposure_state or {}).get("area", {})
        raw_width, raw_height = self.get_current_raw_image_dimensions()
        has_uniform_area = any(
            raw_uniform_area.get(key) is not None
            for key in ("x", "y", "width", "height")
        )
        if has_uniform_area and raw_width > 0 and raw_height > 0:
            uniform_area = self.normalize_image_edit_uniform_exposure_area_state(raw_uniform_area)
        elif has_uniform_area:
            try:
                uniform_area = {
                    "x": float(raw_uniform_area.get("x", 0.0)),
                    "y": float(raw_uniform_area.get("y", 0.0)),
                    "width": float(raw_uniform_area.get("width", 16.0)),
                    "height": float(raw_uniform_area.get("height", 16.0)),
                }
            except (AttributeError, TypeError, ValueError):
                uniform_area = None
        else:
            uniform_area = None
        uniform_offsets = {}
        for image_path, offset_value in dict((uniform_exposure_state or {}).get("offsets", {})).items():
            try:
                offset_float = float(offset_value)
            except (TypeError, ValueError):
                continue
            if abs(offset_float) > 1e-9:
                uniform_offsets[str(image_path)] = offset_float
        raw_crop_state = (state or {}).get("crop", {})
        has_crop_state = any(
            raw_crop_state.get(key) is not None
            for key in ("center_x", "center_y", "width", "height", "angle")
        ) if isinstance(raw_crop_state, dict) else False
        if has_crop_state and raw_width > 0 and raw_height > 0:
            crop_value = self.normalize_image_edit_crop_state(raw_crop_state)
        elif has_crop_state:
            try:
                crop_value = {
                    "center_x": float(raw_crop_state.get("center_x", 0.0)),
                    "center_y": float(raw_crop_state.get("center_y", 0.0)),
                    "width": float(raw_crop_state.get("width", 1.0)),
                    "height": float(raw_crop_state.get("height", 1.0)),
                    "angle": float(raw_crop_state.get("angle", 0.0)),
                }
            except (AttributeError, TypeError, ValueError):
                crop_value = self.normalize_image_edit_crop_state({})
        else:
            crop_value = self.normalize_image_edit_crop_state({})

        previous_value = float(getattr(self, "image_edit_exposure", 0.0))
        previous_contrast = float(getattr(self, "image_edit_contrast", 0.0))
        previous_uniform_area = self.current_image_edit_uniform_exposure_area_state()
        previous_uniform_offsets = {
            str(path): float(value)
            for path, value in dict(getattr(self, "image_edit_uniform_exposure_offsets", {})).items()
            if abs(float(value)) > 1e-9
        }
        previous_crop = self.current_image_edit_crop_state()
        state_changed = abs(previous_value - exposure_value) > 1e-9
        state_changed = state_changed or abs(previous_contrast - contrast_value) > 1e-9
        state_changed = state_changed or previous_uniform_area != uniform_area
        state_changed = state_changed or previous_uniform_offsets != uniform_offsets
        state_changed = state_changed or previous_crop != crop_value
        visual_changed = abs(previous_value - exposure_value) > 1e-9
        visual_changed = visual_changed or abs(previous_contrast - contrast_value) > 1e-9
        visual_changed = visual_changed or previous_uniform_offsets != uniform_offsets
        visual_changed = visual_changed or previous_crop != crop_value
        geometry_changed = previous_crop != crop_value
        self.image_edit_exposure = exposure_value
        self.image_edit_contrast = contrast_value
        if uniform_area is None:
            self.image_edit_uniform_exposure_area_x = None
            self.image_edit_uniform_exposure_area_y = None
            self.image_edit_uniform_exposure_area_width = None
            self.image_edit_uniform_exposure_area_height = None
        else:
            self.image_edit_uniform_exposure_area_x = float(uniform_area["x"])
            self.image_edit_uniform_exposure_area_y = float(uniform_area["y"])
            self.image_edit_uniform_exposure_area_width = float(uniform_area["width"])
            self.image_edit_uniform_exposure_area_height = float(uniform_area["height"])
        self.image_edit_uniform_exposure_offsets = uniform_offsets
        self.image_edit_crop_center_x = float(crop_value["center_x"])
        self.image_edit_crop_center_y = float(crop_value["center_y"])
        self.image_edit_crop_width = float(crop_value["width"])
        self.image_edit_crop_height = float(crop_value["height"])
        self.image_edit_crop_angle = float(crop_value["angle"])

        if visual_changed:
            self.clear_image_caches()

        if sync_controls:
            self.sync_image_edit_controls()

        if refresh_display and visual_changed and self.imagePaths:
            if geometry_changed:
                self.updateImage(self.image_index)
            else:
                self.refresh_current_image_edit_visuals()
        else:
            self.request_image_edit_histogram_refresh()

    def refresh_current_image_edit_visuals(self):
        if not self.imagePaths:
            return
        if not hasattr(self, "pixmap_item"):
            self.updateImage(self.image_index)
            return

        current_transform = self.view.transform()
        current_hscroll = self.view.horizontalScrollBar().value()
        current_vscroll = self.view.verticalScrollBar().value()

        self.view.setUpdatesEnabled(False)
        try:
            q_image = self.update_display_pixmaps(self.image_index)
            self.view.setTransform(current_transform)
            self.view.horizontalScrollBar().setValue(current_hscroll)
            self.view.verticalScrollBar().setValue(current_vscroll)
            self.request_image_edit_histogram_refresh(q_image)
        finally:
            self.view.setUpdatesEnabled(True)

    def prewarm_current_image_edit_render_cache(self):
        if not self.imagePaths:
            return
        if not (0 <= int(self.image_index) < len(self.imagePaths)):
            return
        image_path = self.imagePaths[int(self.image_index)]
        self.get_cached_raw_image(image_path)
        self.get_cached_image(self.image_index)
        self.get_cached_pixmap(self.image_index)

    def get_image_edit_histogram_interval_ms(self):
        return 15

    def request_image_edit_histogram_refresh(self, q_image=None, *, immediate=False):
        if not hasattr(self, "image_edit_histogram_widget"):
            return
        self.pending_image_edit_histogram_qimage = q_image
        if immediate:
            if hasattr(self, "image_edit_histogram_timer"):
                self.image_edit_histogram_timer.stop()
            self.flush_pending_image_edit_histogram()
            return
        self.image_edit_histogram_timer.start(self.get_image_edit_histogram_interval_ms())

    def flush_pending_image_edit_histogram(self):
        q_image = self.pending_image_edit_histogram_qimage
        self.pending_image_edit_histogram_qimage = None
        self.refresh_image_edit_histogram(q_image)

    def normalize_image_edit_uniform_exposure_area_state(self, area_state=None, *, raw_width=None, raw_height=None):
        if raw_width is None or raw_height is None:
            raw_width, raw_height = self.get_current_raw_image_dimensions()
        return normalize_rect_area_state(raw_width, raw_height, area_state or {})

    def current_image_edit_uniform_exposure_area_state(self, *, index=None):
        if not self.has_image_edit_uniform_exposure_area():
            return None
        if index is None:
            raw_width, raw_height = self.get_current_raw_image_dimensions()
        else:
            raw_width, raw_height = self.get_raw_image_dimensions(index)
        return self.normalize_image_edit_uniform_exposure_area_state(
            {
                "x": getattr(self, "image_edit_uniform_exposure_area_x", None),
                "y": getattr(self, "image_edit_uniform_exposure_area_y", None),
                "width": getattr(self, "image_edit_uniform_exposure_area_width", None),
                "height": getattr(self, "image_edit_uniform_exposure_area_height", None),
            },
            raw_width=raw_width,
            raw_height=raw_height,
        )

    def current_image_edit_uniform_exposure_state(self):
        area_state = self.current_image_edit_uniform_exposure_area_state()
        return {
            "area": copy.deepcopy(area_state) if area_state is not None else {},
            "offsets": {
                str(path): float(value)
                for path, value in dict(getattr(self, "image_edit_uniform_exposure_offsets", {})).items()
                if abs(float(value)) > 1e-9
            },
        }

    def compose_image_edit_state(self, *, exposure=None, contrast=None, uniform_exposure=None, crop=None):
        return {
            "exposure": float(getattr(self, "image_edit_exposure", 0.0) if exposure is None else exposure),
            "contrast": float(getattr(self, "image_edit_contrast", 0.0) if contrast is None else contrast),
            "uniform_exposure": self.current_image_edit_uniform_exposure_state() if uniform_exposure is None else copy.deepcopy(uniform_exposure),
            "crop": self.current_image_edit_crop_state() if crop is None else copy.deepcopy(crop),
        }

    def has_image_edit_uniform_exposure_area(self):
        return all(
            getattr(self, attribute_name, None) is not None
            for attribute_name in (
                "image_edit_uniform_exposure_area_x",
                "image_edit_uniform_exposure_area_y",
                "image_edit_uniform_exposure_area_width",
                "image_edit_uniform_exposure_area_height",
            )
        )

    def has_image_edit_uniform_exposure(self):
        return bool(getattr(self, "image_edit_uniform_exposure_offsets", {}))

    def get_image_edit_uniform_exposure_offset(self, *, index=None, image_path=None):
        offsets = getattr(self, "image_edit_uniform_exposure_offsets", {}) or {}
        if image_path is None:
            if index is None:
                index = self.image_index
            if not self.imagePaths or not (0 <= int(index) < len(self.imagePaths)):
                return 0.0
            image_path = self.imagePaths[int(index)]
        try:
            return float(offsets.get(str(image_path), 0.0))
        except (TypeError, ValueError):
            return 0.0

    def current_image_edit_total_exposure(self, *, index=None, image_path=None):
        return float(getattr(self, "image_edit_exposure", 0.0)) + self.get_image_edit_uniform_exposure_offset(
            index=index,
            image_path=image_path,
        )

    def current_image_edit_crop_state(self, *, index=None):
        if index is None:
            raw_width, raw_height = self.get_current_raw_image_dimensions()
        else:
            raw_width, raw_height = self.get_raw_image_dimensions(index)
        return self.normalize_image_edit_crop_state({
            "center_x": getattr(self, "image_edit_crop_center_x", raw_width * 0.5),
            "center_y": getattr(self, "image_edit_crop_center_y", raw_height * 0.5),
            "width": getattr(self, "image_edit_crop_width", raw_width),
            "height": getattr(self, "image_edit_crop_height", raw_height),
            "angle": float(getattr(self, "image_edit_crop_angle", 0.0)),
        }, raw_width=raw_width, raw_height=raw_height)

    def get_raw_image_dimensions(self, index):
        if not self.imagePaths:
            return 0, 0
        try:
            index = int(index)
        except (TypeError, ValueError):
            return 0, 0
        if index < 0 or index >= len(self.imagePaths):
            return 0, 0

        image_path = self.imagePaths[index]
        cached_size = getattr(self, "raw_image_size_cache", {}).get(image_path)
        if cached_size is not None:
            return int(cached_size[0]), int(cached_size[1])

        raw_q_image = self.get_cached_raw_image(image_path)
        width = int(raw_q_image.width())
        height = int(raw_q_image.height())
        if hasattr(self, "raw_image_size_cache"):
            self.raw_image_size_cache[image_path] = (width, height)
        return width, height

    def get_current_raw_image_dimensions(self):
        if not self.imagePaths:
            return 0, 0
        return self.get_raw_image_dimensions(self.image_index)

    def normalize_image_edit_crop_state(self, crop_state=None, *, raw_width=None, raw_height=None):
        if raw_width is None or raw_height is None:
            raw_width, raw_height = self.get_current_raw_image_dimensions()
        return normalize_rotated_crop_state(raw_width, raw_height, crop_state or {})

    def should_apply_crop_in_display(self):
        return not self.is_image_edit_crop_active() and not self.is_image_edit_uniform_exposure_area_active()

    def current_image_edit_crop_transform(self, index=None, *, apply_crop=None):
        if index is None:
            index = self.image_index
        raw_width, raw_height = self.get_raw_image_dimensions(index)
        crop_state = self.current_image_edit_crop_state(index=index)
        if apply_crop is None:
            apply_crop = self.should_apply_crop_in_display()
        if (not apply_crop) or crop_state_is_identity(raw_width, raw_height, crop_state):
            return crop_state, None, None, (max(1, int(raw_width)), max(1, int(raw_height)))
        state, matrix, output_size = build_rotated_crop_affine(
            raw_width,
            raw_height,
            crop_state,
        )
        inverse_matrix = invert_affine_matrix(matrix)
        return state, matrix, inverse_matrix, output_size

    def image_pixel_to_scene_coordinates(self, pixel_x, pixel_y, image_rect=None, *, index=None, apply_crop=None):
        if image_rect is None:
            pixmap_item = getattr(self, "pixmap_item", None)
            if pixmap_item is None:
                return float(pixel_x), float(pixel_y)
            image_rect = pixmap_item.sceneBoundingRect()
        _crop_state, matrix, _inverse_matrix, _output_size = self.current_image_edit_crop_transform(
            index=index,
            apply_crop=apply_crop,
        )
        display_x = float(pixel_x)
        display_y = float(pixel_y)
        if matrix is not None:
            display_x, display_y = apply_affine_to_point(matrix, display_x, display_y)
        return (
            float(image_rect.left()) + display_x,
            float(image_rect.top()) + display_y,
        )

    def scene_to_image_pixel_coordinates(self, scene_pos, image_rect=None, *, index=None, apply_crop=None):
        if image_rect is None:
            pixmap_item = getattr(self, "pixmap_item", None)
            if pixmap_item is None:
                return float(scene_pos.x()), float(scene_pos.y())
            image_rect = pixmap_item.sceneBoundingRect()
        display_x = float(scene_pos.x()) - float(image_rect.left())
        display_y = float(scene_pos.y()) - float(image_rect.top())
        _crop_state, _matrix, inverse_matrix, _output_size = self.current_image_edit_crop_transform(
            index=index,
            apply_crop=apply_crop,
        )
        if inverse_matrix is not None:
            display_x, display_y = apply_affine_to_point(inverse_matrix, display_x, display_y)
        return (float(display_x), float(display_y))

    def sync_image_edit_controls(self):
        if hasattr(self, "image_edit_exposure_slider"):
            slider_value = int(round(float(getattr(self, "image_edit_exposure", 0.0)) * 10.0))
            with QSignalBlocker(self.image_edit_exposure_slider):
                self.image_edit_exposure_slider.setValue(slider_value)
        if hasattr(self, "image_edit_exposure_spinbox"):
            with QSignalBlocker(self.image_edit_exposure_spinbox):
                self.image_edit_exposure_spinbox.setValue(float(getattr(self, "image_edit_exposure", 0.0)))
        if hasattr(self, "image_edit_contrast_slider"):
            slider_value = int(round(float(getattr(self, "image_edit_contrast", 0.0))))
            with QSignalBlocker(self.image_edit_contrast_slider):
                self.image_edit_contrast_slider.setValue(slider_value)
        if hasattr(self, "image_edit_contrast_spinbox"):
            with QSignalBlocker(self.image_edit_contrast_spinbox):
                self.image_edit_contrast_spinbox.setValue(int(round(float(getattr(self, "image_edit_contrast", 0.0)))))
        if hasattr(self, "image_edit_uniform_exposure_area_button"):
            area_active = self.is_image_edit_uniform_exposure_area_active()
            has_area = self.has_image_edit_uniform_exposure_area()
            self.image_edit_uniform_exposure_area_button.setText("Done" if area_active else "Set Area")
            self.image_edit_uniform_exposure_run_button.setEnabled(bool(has_area))
            self.image_edit_uniform_exposure_reset_button.setEnabled(bool(has_area or self.has_image_edit_uniform_exposure()))
        if hasattr(self, "image_edit_crop_start_button"):
            crop_active = self.is_image_edit_crop_active()
            raw_width, raw_height = self.get_current_raw_image_dimensions()
            has_committed_crop = bool(
                raw_width > 0
                and raw_height > 0
                and (not crop_state_is_identity(raw_width, raw_height, self.current_image_edit_crop_state()))
            )
            self.image_edit_crop_start_button.setText("Cancel" if crop_active else "Crop")
            self.image_edit_crop_start_button.setEnabled(True)
            self.image_edit_crop_apply_button.setEnabled(crop_active)
            self.image_edit_crop_reset_button.setEnabled((not crop_active) and has_committed_crop)
        self.sync_image_edit_uniform_exposure_overlay()
        self.sync_image_edit_crop_overlay()

    def refresh_image_edit_histogram(self, q_image=None):
        if not hasattr(self, "image_edit_histogram_widget"):
            return
        if getattr(self, "tool_mode", "") != "image-edit":
            return
        if not self.imagePaths or not (0 <= self.image_index < len(self.imagePaths)):
            self.image_edit_histogram_widget.clear_histogram()
            return

        if q_image is None:
            q_image = self.get_cached_image(self.image_index, apply_crop=False)
        gray_array = qimage_to_grayscale_array(q_image)
        histogram = compute_histogram_bins(gray_array, IMAGE_EDIT_HISTOGRAM_BIN_COUNT)
        overlay_histogram = None
        overlay_scale_max = None
        selected_items = list(self.cell_controller.selected_scene_items()) if hasattr(self, "cell_controller") else []
        if selected_items and gray_array is not None and gray_array.size > 0:
            selected_values = []
            image_height, image_width = gray_array.shape[:2]
            for item in selected_items:
                try:
                    center_x = float(item.circle_pixel_positions[0])
                    center_y = float(item.circle_pixel_positions[1])
                    radius = float(item.circle_sizes)
                except (AttributeError, TypeError, ValueError, IndexError):
                    continue
                if radius <= 0:
                    continue
                left = max(0, int(math.floor(center_x - radius)))
                top = max(0, int(math.floor(center_y - radius)))
                right = min(image_width, int(math.ceil(center_x + radius)) + 1)
                bottom = min(image_height, int(math.ceil(center_y + radius)) + 1)
                if right <= left or bottom <= top:
                    continue
                region = gray_array[top:bottom, left:right]
                yy, xx = np.ogrid[top:bottom, left:right]
                mask = ((xx - center_x) ** 2 + (yy - center_y) ** 2) <= (radius ** 2)
                if np.any(mask):
                    selected_values.append(region[mask])
            if selected_values:
                overlay_histogram = compute_histogram_bins(
                    np.concatenate(selected_values),
                    IMAGE_EDIT_HISTOGRAM_BIN_COUNT,
                )
                overlay_scale_max = max(float(np.max(overlay_histogram)) if overlay_histogram.size else 0.0, 1.0)
        scale_max = max(float(np.max(histogram)) if histogram.size else 0.0, 1.0)
        self.image_edit_histogram_widget.set_histogram(
            histogram,
            overlay_histogram=overlay_histogram,
            scale_max=scale_max,
            overlay_scale_max=overlay_scale_max,
        )

    def begin_image_edit_history(self, text):
        if self.history_restoring:
            return
        if "image_edit_before_state" in self.temporary_event_data:
            return
        self.temporary_event_data["image_edit_before_state"] = self.capture_image_edit_history_state()
        self.temporary_event_data["image_edit_history_text"] = str(text or "Edit Image")

    def commit_image_edit_history(self, text=None):
        before_state = self.temporary_event_data.pop("image_edit_before_state", None)
        history_text = str(text or self.temporary_event_data.pop("image_edit_history_text", "Edit Image"))
        if before_state is None:
            return
        after_state = self.capture_image_edit_history_state()
        if before_state == after_state:
            return
        self.push_image_edit_history(history_text, before_state)
        self.log_image_edit_change(history_text)

    def log_image_edit_change(self, history_text):
        history_text = str(history_text or "Edit Image")
        if history_text == "Adjust Exposure":
            self.log(f"Adjust Exposure: {float(getattr(self, 'image_edit_exposure', 0.0)):.1f}")
            return
        if history_text == "Adjust Contrast":
            self.log(f"Adjust Contrast: {int(round(float(getattr(self, 'image_edit_contrast', 0.0))))}")
            return
        if history_text == "Apply Crop":
            crop_state = self.current_image_edit_crop_state()
            self.log(
                "Apply Crop: "
                f"center=({float(crop_state['center_x']):.1f}, {float(crop_state['center_y']):.1f}), "
                f"size=({float(crop_state['width']):.1f} x {float(crop_state['height']):.1f}), "
                f"angle={float(crop_state['angle']):.1f}"
            )
            return
        if history_text == "Reset Crop":
            self.log("Reset Crop")
            return
        if history_text == "Reset Uniform Exposure":
            self.log("Reset Uniform Exposure")
            return
        self.log(history_text)

    def get_image_edit_preview_interval_ms(self):
        return 15

    def reset_pending_image_edit_preview_state(self, stop_timer=False):
        self.pending_image_edit_preview_state = None
        self.image_edit_preview_in_progress = False
        if stop_timer and hasattr(self, "image_edit_preview_timer"):
            self.image_edit_preview_timer.stop()

    def compose_pending_image_edit_preview_state(self, *, exposure=None, contrast=None):
        base_state = self.pending_image_edit_preview_state
        if base_state is None:
            base_state = self.compose_image_edit_state()
        else:
            base_state = copy.deepcopy(base_state)
        if exposure is not None:
            base_state["exposure"] = float(exposure)
        if contrast is not None:
            base_state["contrast"] = float(contrast)
        return base_state

    def queue_image_edit_preview_state(self, state):
        self.pending_image_edit_preview_state = copy.deepcopy(state)
        if self.image_edit_preview_in_progress:
            return
        self.image_edit_preview_timer.start(self.get_image_edit_preview_interval_ms())

    def flush_pending_image_edit_preview(self):
        if self.pending_image_edit_preview_state is None or self.image_edit_preview_in_progress:
            return
        pending_state = copy.deepcopy(self.pending_image_edit_preview_state)
        self.pending_image_edit_preview_state = None
        self.image_edit_preview_in_progress = True
        try:
            self.apply_image_edit_state(
                pending_state,
                invalidate_results=True,
                refresh_display=True,
                sync_controls=True,
            )
        finally:
            self.image_edit_preview_in_progress = False

        if self.pending_image_edit_preview_state is not None:
            self.image_edit_preview_timer.start(self.get_image_edit_preview_interval_ms())

    def handle_image_edit_exposure_slider_changed(self, slider_value):
        self.begin_image_edit_history("Adjust Exposure")
        exposure_value = float(slider_value) / 10.0
        if getattr(self, "image_edit_exposure_slider", None).isSliderDown():
            self.queue_image_edit_preview_state(
                self.compose_pending_image_edit_preview_state(exposure=exposure_value)
            )
            return
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                exposure=exposure_value,
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Exposure")

    def handle_image_edit_exposure_spinbox_changed(self, exposure_value):
        self.begin_image_edit_history("Adjust Exposure")
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                exposure=float(exposure_value),
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Exposure")

    def handle_image_edit_exposure_slider_released(self):
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                exposure=float(self.image_edit_exposure_slider.value()) / 10.0,
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Exposure")

    def handle_image_edit_contrast_slider_changed(self, contrast_value):
        self.begin_image_edit_history("Adjust Contrast")
        contrast_value = float(contrast_value)
        if getattr(self, "image_edit_contrast_slider", None).isSliderDown():
            self.queue_image_edit_preview_state(
                self.compose_pending_image_edit_preview_state(contrast=contrast_value)
            )
            return
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                contrast=contrast_value,
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Contrast")

    def handle_image_edit_contrast_spinbox_changed(self, contrast_value):
        self.begin_image_edit_history("Adjust Contrast")
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                contrast=float(contrast_value),
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Contrast")

    def handle_image_edit_contrast_slider_released(self):
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                contrast=float(self.image_edit_contrast_slider.value()),
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Contrast")

    def is_image_edit_uniform_exposure_area_active(self):
        return bool(self.temporary_event_data.get("image_edit_uniform_exposure_area_active", False))

    def begin_image_edit_uniform_exposure_area(self):
        raw_width, raw_height = self.get_current_raw_image_dimensions()
        if raw_width <= 0 or raw_height <= 0:
            return
        if self.is_image_edit_crop_active():
            self.cancel_image_edit_crop()
        if self.is_image_edit_uniform_exposure_area_active():
            self.sync_image_edit_controls()
            return
        if getattr(self, "image_edit_uniform_exposure_area_x", None) is None:
            area_state = self.normalize_image_edit_uniform_exposure_area_state({})
            self.image_edit_uniform_exposure_area_x = float(area_state["x"])
            self.image_edit_uniform_exposure_area_y = float(area_state["y"])
            self.image_edit_uniform_exposure_area_width = float(area_state["width"])
            self.image_edit_uniform_exposure_area_height = float(area_state["height"])
        self.temporary_event_data["image_edit_uniform_exposure_area_active"] = True
        if self.imagePaths:
            self.updateImage(self.image_index)
        else:
            self.sync_image_edit_controls()

    def end_image_edit_uniform_exposure_area(self):
        if not self.is_image_edit_uniform_exposure_area_active():
            return
        self.temporary_event_data.pop("image_edit_uniform_exposure_area_active", None)
        if self.imagePaths:
            self.updateImage(self.image_index)
        else:
            self.sync_image_edit_controls()

    def handle_image_edit_uniform_exposure_area_button(self):
        if self.is_image_edit_uniform_exposure_area_active():
            self.end_image_edit_uniform_exposure_area()
        else:
            self.begin_image_edit_uniform_exposure_area()

    def handle_image_edit_uniform_exposure_overlay_changed(self, area_state, finalize=False):
        pixmap_item = getattr(self, "pixmap_item", None)
        if pixmap_item is None:
            return
        image_rect = pixmap_item.sceneBoundingRect()
        top_left_scene = QPointF(float(image_rect.left()) + float(area_state["x"]), float(image_rect.top()) + float(area_state["y"]))
        bottom_right_scene = QPointF(
            float(image_rect.left()) + float(area_state["x"]) + float(area_state["width"]),
            float(image_rect.top()) + float(area_state["y"]) + float(area_state["height"]),
        )
        top_left = self.scene_to_image_pixel_coordinates(top_left_scene, image_rect=image_rect, apply_crop=False)
        bottom_right = self.scene_to_image_pixel_coordinates(bottom_right_scene, image_rect=image_rect, apply_crop=False)
        normalized = self.normalize_image_edit_uniform_exposure_area_state(
            {
                "x": min(float(top_left[0]), float(bottom_right[0])),
                "y": min(float(top_left[1]), float(bottom_right[1])),
                "width": abs(float(bottom_right[0]) - float(top_left[0])),
                "height": abs(float(bottom_right[1]) - float(top_left[1])),
            }
        )
        current = self.current_image_edit_uniform_exposure_area_state()
        if normalized == current:
            return
        self.image_edit_uniform_exposure_area_x = float(normalized["x"])
        self.image_edit_uniform_exposure_area_y = float(normalized["y"])
        self.image_edit_uniform_exposure_area_width = float(normalized["width"])
        self.image_edit_uniform_exposure_area_height = float(normalized["height"])
        self.request_image_edit_histogram_refresh()
        if finalize:
            self.sync_image_edit_controls()

    def ensure_image_edit_uniform_exposure_overlay(self):
        overlay = getattr(self, "image_edit_uniform_exposure_overlay", None)
        if overlay is not None and overlay.scene() is self.scene:
            return overlay
        overlay = ImageRectOverlayItem()
        overlay.areaChanged.connect(self.handle_image_edit_uniform_exposure_overlay_changed)
        overlay.areaChangeFinished.connect(lambda state: self.handle_image_edit_uniform_exposure_overlay_changed(state, finalize=True))
        self.scene.addItem(overlay)
        self.image_edit_uniform_exposure_overlay = overlay
        return overlay

    def sync_image_edit_uniform_exposure_overlay(self):
        overlay = getattr(self, "image_edit_uniform_exposure_overlay", None)
        should_show = (
            getattr(self, "tool_mode", "") == "image-edit"
            and bool(self.imagePaths)
            and getattr(self, "pixmap_item", None) is not None
            and self.is_image_edit_uniform_exposure_area_active()
            and not self.is_image_edit_crop_active()
        )
        if not should_show:
            if overlay is not None:
                overlay.hide()
            return
        overlay = self.ensure_image_edit_uniform_exposure_overlay()
        overlay.set_interactive(True)
        image_rect = self.pixmap_item.sceneBoundingRect()
        area_state = self.current_image_edit_uniform_exposure_area_state()
        if area_state is None:
            overlay.hide()
            return
        top_left = self.image_pixel_to_scene_coordinates(area_state["x"], area_state["y"], image_rect=image_rect, apply_crop=False)
        bottom_right = self.image_pixel_to_scene_coordinates(
            area_state["x"] + area_state["width"],
            area_state["y"] + area_state["height"],
            image_rect=image_rect,
            apply_crop=False,
        )
        scene_rect = QRectF(QPointF(*top_left), QPointF(*bottom_right)).normalized()
        overlay.sync_from_rect(
            image_rect,
            {
                "x": float(scene_rect.left() - image_rect.left()),
                "y": float(scene_rect.top() - image_rect.top()),
                "width": float(scene_rect.width()),
                "height": float(scene_rect.height()),
            },
        )
        overlay.show()

    def show_image_edit_progress_frame(self, index):
        if not self.imagePaths:
            return
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        if index < 0 or index >= len(self.imagePaths):
            return
        self.image_slider.blockSignals(True)
        try:
            self.ensure_slider_window_contains_index(index)
            self.image_slider.setValue(index)
        finally:
            self.image_slider.blockSignals(False)
        self.updateImage(index, preview=False)
        QApplication.processEvents()

    def show_analysis_progress_frame(self, index):
        if not self.imagePaths:
            return
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        if index < 0 or index >= len(self.imagePaths):
            return
        self.image_slider.blockSignals(True)
        try:
            self.ensure_slider_window_contains_index(index)
            self.image_slider.setValue(index)
        finally:
            self.image_slider.blockSignals(False)
        self.updateImage(index, preview=False)

    def get_analysis_progress_interval_ms(self):
        return 16

    def enqueue_analysis_progress_frame(self, index):
        if not self.imagePaths:
            return
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        if index < 0 or index >= len(self.imagePaths):
            return
        self.pending_analysis_progress_index = index
        if not self.analysis_progress_timer.isActive():
            self.analysis_progress_timer.start(self.get_analysis_progress_interval_ms())

    def flush_pending_analysis_progress(self):
        pending_index = self.pending_analysis_progress_index
        self.pending_analysis_progress_index = None
        if pending_index is None:
            return
        self.show_analysis_progress_frame(pending_index)
        if self.pending_analysis_progress_index is not None:
            self.analysis_progress_timer.start(self.get_analysis_progress_interval_ms())

    def compute_image_edit_uniform_exposure_solution(self, area_state, reference_index, progress_callback=None):
        if not self.imagePaths:
            return {}, {}
        try:
            reference_index = max(0, min(int(reference_index), len(self.imagePaths) - 1))
        except (TypeError, ValueError):
            reference_index = self.image_index

        def load_gray(index):
            image_gray = cv2.imread(self.imagePaths[index], cv2.IMREAD_GRAYSCALE)
            if image_gray is None:
                raise ValueError(f"Unable to read image: {self.imagePaths[index]}")
            image_gray = apply_image_adjustments_to_uint8(
                image_gray,
                self.image_edit_exposure,
                self.image_edit_contrast,
                crop_state=None,
                apply_crop=False,
            )
            return image_gray

        def area_mean(image_gray, raw_area_state):
            image_height, image_width = image_gray.shape[:2]
            normalized_area = self.normalize_image_edit_uniform_exposure_area_state(
                raw_area_state,
                raw_width=image_width,
                raw_height=image_height,
            )
            left = int(round(float(normalized_area["x"])))
            top = int(round(float(normalized_area["y"])))
            width = int(round(float(normalized_area["width"])))
            height = int(round(float(normalized_area["height"])))
            right = min(image_width, left + width)
            bottom = min(image_height, top + height)
            if left >= right or top >= bottom:
                raise ValueError("Uniform exposure area is empty.")
            roi = image_gray[top:bottom, left:right]
            if roi.size == 0:
                raise ValueError("Uniform exposure area is empty.")
            return float(np.mean(roi, dtype=np.float64))

        reference_image = load_gray(reference_index)
        reference_mean = area_mean(reference_image, area_state)
        if reference_mean <= 1e-6:
            raise ValueError("Uniform exposure reference area is too dark.")

        offsets = {}
        for index, image_path in enumerate(self.imagePaths):
            if progress_callback is not None:
                progress_callback(index)
            image_gray = reference_image if index == reference_index else load_gray(index)
            current_mean = area_mean(image_gray, area_state)
            if current_mean <= 1e-6:
                raise ValueError(f"Uniform exposure area is too dark on frame {index}.")
            offset = float(np.clip(np.log2(reference_mean / current_mean), -4.0, 4.0))
            if abs(offset) > 1e-9:
                offsets[str(image_path)] = offset
        normalized_area = self.normalize_image_edit_uniform_exposure_area_state(area_state)
        return offsets, normalized_area

    def run_image_edit_uniform_exposure(self):
        if not self.imagePaths:
            return
        if not self.has_image_edit_uniform_exposure_area():
            QMessageBox.information(self, "Uniform Exposure", "Set a control area first.")
            return
        reference_index = int(self.image_index)
        progress_restore_index = int(self.image_index)
        area_state = self.current_image_edit_uniform_exposure_area_state()
        try:
            offsets, normalized_area = self.compute_image_edit_uniform_exposure_solution(
                area_state,
                reference_index,
                progress_callback=self.show_image_edit_progress_frame,
            )
        except Exception as err:
            if self.imagePaths and 0 <= progress_restore_index < len(self.imagePaths):
                self.show_image_edit_progress_frame(progress_restore_index)
            QMessageBox.warning(self, "Uniform Exposure", str(err))
            return
        before_state = self.capture_data_state()
        self.temporary_event_data.pop("image_edit_uniform_exposure_area_active", None)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                uniform_exposure={
                    "area": copy.deepcopy(normalized_area),
                    "offsets": offsets,
                },
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        if self.imagePaths and 0 <= progress_restore_index < len(self.imagePaths) and progress_restore_index != self.image_index:
            self.show_image_edit_progress_frame(progress_restore_index)
        self.log(f"Applied uniform exposure to {len(self.imagePaths)} images")
        self.push_data_history("Run Uniform Exposure", before_state)

    def reset_image_edit_uniform_exposure(self):
        if not self.has_image_edit_uniform_exposure_area() and not self.has_image_edit_uniform_exposure():
            return
        before_state = self.capture_data_state()
        self.temporary_event_data.pop("image_edit_uniform_exposure_area_active", None)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                uniform_exposure={
                    "area": {},
                    "offsets": {},
                },
            ),
            invalidate_results=bool(self.has_image_edit_uniform_exposure()),
            refresh_display=True,
            sync_controls=True,
        )
        self.push_data_history("Reset Uniform Exposure", before_state)
        self.log_image_edit_change("Reset Uniform Exposure")

    def is_image_edit_crop_active(self):
        return bool(self.temporary_event_data.get("image_edit_crop_active", False))

    def get_image_edit_crop_draft_state(self):
        draft_state = self.temporary_event_data.get("image_edit_crop_draft_state")
        if draft_state is None:
            return None
        return self.normalize_image_edit_crop_state(draft_state)

    def discard_image_edit_crop_draft(self):
        self.temporary_event_data.pop("image_edit_crop_active", None)
        self.temporary_event_data.pop("image_edit_crop_draft_state", None)

    def reset_image_edit_crop(self):
        raw_width, raw_height = self.get_current_raw_image_dimensions()
        if raw_width <= 0 or raw_height <= 0:
            return
        reset_state = {
            "center_x": raw_width * 0.5,
            "center_y": raw_height * 0.5,
            "width": raw_width,
            "height": raw_height,
            "angle": 0.0,
        }
        if self.is_image_edit_crop_active():
            self.temporary_event_data["image_edit_crop_draft_state"] = dict(reset_state)
            self.sync_image_edit_controls()
            return

        before_state = self.capture_data_state()
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                crop=reset_state,
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.push_data_history("Reset Crop", before_state)
        self.log_image_edit_change("Reset Crop")

    def begin_image_edit_crop(self):
        raw_width, raw_height = self.get_current_raw_image_dimensions()
        if raw_width <= 0 or raw_height <= 0:
            return
        if self.is_image_edit_uniform_exposure_area_active():
            self.end_image_edit_uniform_exposure_area()
        if self.is_image_edit_crop_active():
            self.sync_image_edit_controls()
            return

        current_state = self.current_image_edit_crop_state()
        if crop_state_is_identity(raw_width, raw_height, current_state):
            draft_state = {
                "center_x": float(raw_width) * 0.5,
                "center_y": float(raw_height) * 0.5,
                "width": float(raw_width),
                "height": float(raw_height),
                "angle": 0.0,
            }
        else:
            draft_state = current_state
        self.temporary_event_data["image_edit_crop_active"] = True
        self.temporary_event_data["image_edit_crop_draft_state"] = dict(draft_state)
        if self.tool_mode == "image-edit":
            self.view.setDragMode(QGraphicsView.NoDrag)
        if self.imagePaths:
            self.updateImage(self.image_index)
        else:
            self.sync_image_edit_controls()

    def handle_image_edit_crop_primary_button(self):
        if self.is_image_edit_crop_active():
            self.cancel_image_edit_crop()
        else:
            self.begin_image_edit_crop()

    def apply_image_edit_crop(self):
        draft_state = self.get_image_edit_crop_draft_state()
        if draft_state is None:
            return
        before_state = self.capture_data_state()
        self.discard_image_edit_crop_draft()
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                crop=draft_state,
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.sync_image_edit_controls()
        if self.tool_mode == "image-edit":
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.push_data_history("Apply Crop", before_state)
        self.log_image_edit_change("Apply Crop")

    def trigger_image_edit_crop_apply_button(self):
        apply_button = getattr(self, "image_edit_crop_apply_button", None)
        if apply_button is not None and apply_button.isEnabled():
            apply_button.animateClick()
            return True
        self.apply_image_edit_crop()
        return True

    def cancel_image_edit_crop(self):
        if not self.is_image_edit_crop_active():
            return
        self.discard_image_edit_crop_draft()
        if self.tool_mode == "image-edit":
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        if self.imagePaths:
            self.updateImage(self.image_index)
        else:
            self.sync_image_edit_controls()

    def handle_image_edit_crop_overlay_changed(self, crop_state, finalize=False):
        crop_state = self.normalize_image_edit_crop_state(crop_state)
        changed = crop_state != self.get_image_edit_crop_draft_state()
        if not changed:
            return
        self.temporary_event_data["image_edit_crop_draft_state"] = dict(crop_state)
        if finalize:
            self.sync_image_edit_controls()

    def ensure_image_edit_crop_overlay(self):
        overlay = getattr(self, "image_edit_crop_overlay", None)
        if overlay is not None and overlay.scene() is self.scene:
            return overlay
        overlay = ImageCropOverlayItem()
        overlay.cropChanged.connect(self.handle_image_edit_crop_overlay_changed)
        overlay.cropChangeFinished.connect(lambda state: self.handle_image_edit_crop_overlay_changed(state, finalize=True))
        self.scene.addItem(overlay)
        self.image_edit_crop_overlay = overlay
        return overlay

    def sync_image_edit_crop_overlay(self):
        overlay = getattr(self, "image_edit_crop_overlay", None)
        should_show = (
            self.tool_mode == "image-edit"
            and bool(self.imagePaths)
            and hasattr(self, "pixmap_item")
            and self.is_image_edit_crop_active()
        )
        if not should_show:
            if overlay is not None:
                overlay.hide()
            return
        overlay = self.ensure_image_edit_crop_overlay()
        overlay.show()
        overlay.sync_from_state(
            self.pixmap_item.sceneBoundingRect(),
            self.normalize_image_edit_crop_state(self.get_image_edit_crop_draft_state()),
        )

    def apply_session_metadata(self, metadata):
        metadata = metadata or {}
        self.session_project_name = str(metadata.get("project_name", "")).strip()
        self.session_user_name = str(metadata.get("user_name", "")).strip()
        self.session_institution = str(metadata.get("institution", "")).strip()
        self.session_date = str(metadata.get("date", "")).strip()
        self.update_session_metadata_status_label()

    def format_session_metadata_status_text(self):
        field_specs = (
            ("project_name", "Project"),
            ("user_name", "User"),
            ("institution", "Institution"),
            ("date", "Date"),
        )
        metadata = self.serialize_session_metadata()
        parts = []
        for key, label in field_specs:
            value = str(metadata.get(key, "")).strip()
            if value:
                parts.append(f"{label}: {value}")
        return " | ".join(parts)

    def update_session_metadata_status_label(self):
        label = getattr(self, "session_metadata_status_label", None)
        if label is None:
            return
        text = self.format_session_metadata_status_text()
        label.setText(text)
        label.setToolTip(text)
        label.setVisible(bool(text))

    def has_session_content(self):
        raw_width, raw_height = self.get_current_raw_image_dimensions()
        crop_is_identity = True
        if raw_width > 0 and raw_height > 0:
            crop_is_identity = crop_state_is_identity(
                raw_width,
                raw_height,
                self.current_image_edit_crop_state(),
            )
        return bool(
            self.imagePaths
            or self.cell_items
            or self.cell_records_by_id
            or self.sample_catalog
            or abs(float(getattr(self, "image_edit_exposure", 0.0))) > 1e-9
            or abs(float(getattr(self, "image_edit_contrast", 0.0))) > 1e-9
            or self.has_image_edit_uniform_exposure_area()
            or self.has_image_edit_uniform_exposure()
            or (not crop_is_identity)
            or self.grayscale_results_headers
            or self.grayscale_results_rows
            or self.freeze_results_headers
            or self.freeze_results_rows
            or self.temperature_sync_headers
            or self.temperature_sync_rows
        )

    def has_session_save_payload(self):
        return self.has_session_content() or any(self.serialize_session_metadata().values())

    def prompt_save_before_replacing_session(self, next_action_label="starting a new session"):
        if (not getattr(self, "session_active", False)) or (not self.has_session_save_payload()):
            return "discard"

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Question)
        dialog.setWindowTitle("Save Session")
        dialog.setText(f"Do you want to save this session before {next_action_label}?")
        dialog.setInformativeText("Undo/redo history will be cleared.")
        save_button = dialog.addButton("Save", QMessageBox.AcceptRole)
        dont_save_button = dialog.addButton("Don't Save", QMessageBox.DestructiveRole)
        cancel_button = dialog.addButton(QMessageBox.Cancel)
        dialog.setDefaultButton(save_button)
        dialog.exec()

        clicked_button = dialog.clickedButton()
        if clicked_button == cancel_button:
            return "cancel"
        if clicked_button == save_button:
            return "saved" if self.saveSession() else "cancel"
        return "discard"

    def prompt_new_session_metadata(self):
        dialog = NewSessionMetadataDialog(self, self.serialize_session_metadata())
        if dialog.exec() != QDialog.Accepted:
            return None
        return dialog.get_metadata()

    def newSession(self, checked=False):
        save_choice = self.prompt_save_before_replacing_session("starting a new session")
        if save_choice == "cancel":
            return

        metadata = self.prompt_new_session_metadata()
        if metadata is None:
            return

        self.clear_session(
            confirm=False,
            log_message="Started new session",
            record_history=False,
            new_metadata=metadata,
            activate_session=True,
        )
        self.undo_stack.clear()
        self.pending_analysis_before_state = None
        self.log("New session ready")

    def initUI(self):
        # Set main window properties
        self.setWindowTitle('Icescopy')
        self.setGeometry(100, 100, 1000, 700)
        if platform.system() == "Darwin":
            self.setWindowFlags(
                (self.windowFlags() | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowSystemMenuHint |
                 Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint) & ~Qt.WindowFullscreenButtonHint
            )

        # Create a menu bar
        menubar = self.menuBar()

        # Create the "IceScopy" menu
        icescopy_menu = menubar.addMenu("IceScopy")
        icescopy_menu.setFont(QFont("Arial", 10, QFont.Bold))

        # Add "About" action to "IceScopy" menu
        about_action = QAction("About", self)
        about_action.triggered.connect(self.showAboutDialog)
        icescopy_menu.addAction(about_action)
        icescopy_menu.addSeparator() # Add a separator to the menu

        self.preferences_action = QAction("Preferences", self)
        self.preferences_action.triggered.connect(self.showPreferencesDialog)
        icescopy_menu.addAction(self.preferences_action)

        file_menu = menubar.addMenu("File")
        edit_menu = menubar.addMenu("Edit")
        analysis_menu = menubar.addMenu("Analysis")
        window_menu = menubar.addMenu("Window")

        # Create actions with icons
        self.add_images_action = QAction("Add Images", self)
        self.add_folder_action = QAction("Add Folder", self)
        self.remove_selected_action = QAction("Remove Selected", self)
        self.clear_images_action = QAction("Clear Images", self)
        self.new_session_action = QAction("New Session", self)
        self.open_session_action = QAction("Open Session", self)
        self.save_session_action = QAction("Save Session", self)
        self.save_session_as_action = QAction("Save Session As...", self)
        self.save_session_action.setShortcuts([QKeySequence.Save, QKeySequence("Ctrl+S")])
        self.save_session_as_action.setShortcuts([QKeySequence.SaveAs])
        self.relink_images_action = QAction("Relink Images Folder...", self)
        self.run_analysis_action = QAction("Run Analysis", self)
        self.output_results_action = QAction("Output Results", self)
        self.import_csu_is_dat_action = QAction("CSU IS .dat import...", self)
        self.import_tamu_linkam_xlsx_action = QAction("TAMU Linkam .xlsx import...", self)
        self.sort_images_action = QAction("Sort Images", self)
        self.sample_manager_action = QAction("Sample Catalog Manager", self)
        self.image_edit_action = QAction("Image Edit", self)
        self.viewer_single_action = QAction("Show One Image", self)
        self.viewer_double_action = QAction("Show Two Images", self)
        self.viewer_triple_action = QAction("Show Three Images", self)
        self.viewer_orientation_toggle_action = QAction("Stack Top to Bottom", self)
        self.undo_action = QAction("Undo", self)
        self.redo_action = QAction("Redo", self)
        self.reset_cursor_action = QAction("Cursor Tool (A)", self)
        self.select_tool_action = QAction("Add Cell (S)", self)
        self.grid_tool_action = QAction("Grid Tool (G)", self)
        self.edit_tool_action = QAction("Edit Cell (E)", self)
        self.deselect_tool_action = QAction("Delete Cells (D)", self)
        self.pan_tool_action = QAction("Pan and Zoom (Z)", self) 

        file_menu.addAction(self.add_images_action)
        file_menu.addAction(self.add_folder_action)
        file_menu.addAction(self.new_session_action)
        file_menu.addAction(self.open_session_action)
        file_menu.addAction(self.save_session_action)
        file_menu.addAction(self.save_session_as_action)
        file_menu.addAction(self.output_results_action)
        file_menu.addSeparator() # Add a separator to the menu
        file_menu.addAction(self.relink_images_action)
        file_menu.addSeparator() # Add a separator to the menu
        file_menu.addAction(self.remove_selected_action)
        file_menu.addAction(self.clear_images_action)
        file_menu.addSeparator() # Add a separator to the menu
        file_menu.addAction(self.sort_images_action)

        analysis_menu.addAction(self.run_analysis_action)
        analysis_menu.addSeparator()
        import_temperature_menu = analysis_menu.addMenu("Import Temperature Data")
        import_temperature_menu.addAction(self.import_csu_is_dat_action)
        import_temperature_menu.addAction(self.import_tamu_linkam_xlsx_action)

        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator() # Add a separator to the menu
        edit_menu.addAction(self.reset_cursor_action)
        edit_menu.addAction(self.pan_tool_action)
        edit_menu.addAction(self.image_edit_action)
        edit_menu.addSeparator() # Add a separator to the menu
        edit_menu.addAction(self.select_tool_action)
        edit_menu.addAction(self.grid_tool_action)
        edit_menu.addAction(self.edit_tool_action)
        edit_menu.addAction(self.deselect_tool_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.sample_manager_action)
        


        if platform.system() == "Darwin":  # macOS
            self.undo_action.setToolTip("Undo (Cmd+Z)")
            self.redo_action.setToolTip("Redo (Shift+Cmd+Z)")
        else:  # Windows and others
            self.undo_action.setToolTip("Undo (Ctrl+Z)")
            self.redo_action.setToolTip("Redo (Shift+Cmd+Z)")
        self.deselect_tool_action.setToolTip(
            "Delete mode. Click cells to remove them. In Cursor mode, Delete or Backspace removes the selected cells."
        )

        self.add_folder_action.triggered.connect(self.loadFolder)
        self.add_images_action.triggered.connect(self.open_add_images_dialog)
        self.new_session_action.triggered.connect(self.newSession)
        self.open_session_action.triggered.connect(self.openSession)
        self.save_session_action.triggered.connect(self.handle_save_session_action)
        self.save_session_as_action.triggered.connect(self.saveSessionAs)
        self.relink_images_action.triggered.connect(self.relink_images_folder)
        self.output_results_action.triggered.connect(self.export_results_csv)
        self.import_csu_is_dat_action.triggered.connect(self.import_csu_is_dat)
        self.import_tamu_linkam_xlsx_action.triggered.connect(self.import_tamu_linkam_xlsx)
        self.remove_selected_action.triggered.connect(self.remove_selected_image)
        self.clear_images_action.triggered.connect(self.clear_loaded_images)
        self.run_analysis_action.triggered.connect(self.outputData)
        self.sort_images_action.triggered.connect(self.openSortImagesDialog)
        self.sample_manager_action.triggered.connect(self.show_sample_catalog_manager)
        self.image_edit_action.triggered.connect(self.imageEditTool)
        self.viewer_single_action.triggered.connect(lambda: self.set_viewer_image_count(1))
        self.viewer_double_action.triggered.connect(lambda: self.set_viewer_image_count(2))
        self.viewer_triple_action.triggered.connect(lambda: self.set_viewer_image_count(3))
        self.viewer_orientation_toggle_action.triggered.connect(self.toggle_viewer_split_orientation)
        self.undo_action.triggered.connect(self.undo)
        self.redo_action.triggered.connect(self.redo)
        self.reset_cursor_action.triggered.connect(self.reset_cursor_tool)
        self.reset_cursor_action.setCheckable(True)
        self.select_tool_action.triggered.connect(self.selectTool)
        self.select_tool_action.setCheckable(True)
        self.grid_tool_action.triggered.connect(self.gridTool)
        self.grid_tool_action.setCheckable(True)
        self.edit_tool_action.triggered.connect(self.editTool)
        self.edit_tool_action.setCheckable(True)
        self.deselect_tool_action.triggered.connect(self.deselectTool)
        self.deselect_tool_action.setCheckable(True)
        self.pan_tool_action.triggered.connect(self.panTool)
        self.pan_tool_action.setCheckable(True)
        self.image_edit_action.setCheckable(True)
        self.viewer_single_action.setCheckable(True)
        self.viewer_double_action.setCheckable(True)
        self.viewer_triple_action.setCheckable(True)
        self.undo_stack.canUndoChanged.connect(lambda _: self.set_undo_status())
        self.undo_stack.canRedoChanged.connect(lambda _: self.set_redo_status())
        self.preview_confirm_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        self.preview_confirm_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.preview_confirm_shortcut.activated.connect(self.handle_preview_confirm_shortcut)
        self.preview_confirm_shortcut_enter = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self.preview_confirm_shortcut_enter.setContext(Qt.WidgetWithChildrenShortcut)
        self.preview_confirm_shortcut_enter.activated.connect(self.handle_preview_confirm_shortcut)
        self.preview_cancel_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.preview_cancel_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.preview_cancel_shortcut.activated.connect(self.handle_preview_cancel_shortcut)
        self.update_preview_shortcut_enabled_state()

        # disable tools before loading data
        self.select_tool_action.setEnabled(False)
        self.grid_tool_action.setEnabled(False)
        self.deselect_tool_action.setEnabled(False)
        self.edit_tool_action.setEnabled(False)
        self.pan_tool_action.setEnabled(False)
        self.image_edit_action.setEnabled(False)
        self.remove_selected_action.setEnabled(False)
        self.clear_images_action.setEnabled(False)
        self.save_session_action.setEnabled(False)
        self.save_session_as_action.setEnabled(False)
        self.relink_images_action.setEnabled(False)
        self.run_analysis_action.setEnabled(False)
        self.output_results_action.setEnabled(False)

        # Initialize toolbar
        self.toolbar = self.addToolBar("Tools")

        # Add actions to toolbar
        self.toolbar.addAction(self.preferences_action)
        self.toolbar.addAction(self.new_session_action)
        self.toolbar.addAction(self.open_session_action)
        self.toolbar.addAction(self.save_session_action)
        self.toolbar.addAction(self.output_results_action)
        self.toolbar.addSeparator()  # Add a separator between groups of actions
        self.toolbar.addAction(self.add_images_action)
        self.toolbar.addAction(self.remove_selected_action)
        self.toolbar.addAction(self.clear_images_action)
        self.toolbar.addAction(self.sort_images_action)
        self.toolbar.addAction(self.image_edit_action)
        self.toolbar.addAction(self.sample_manager_action)
        self.toolbar.addAction(self.run_analysis_action)
        self.toolbar.addSeparator()  # Add a separator between groups of actions
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)
        self.toolbar.addAction(self.reset_cursor_action)
        self.toolbar.addAction(self.pan_tool_action)
        self.toolbar.addAction(self.select_tool_action)
        self.toolbar.addAction(self.grid_tool_action)
        self.toolbar.addAction(self.deselect_tool_action)
        self.toolbar.addAction(self.edit_tool_action)
        self.toolbar.addSeparator()  # Add a separator between groups of actions
        self.toolbar.addAction(self.viewer_single_action)
        self.toolbar.addAction(self.viewer_double_action)
        self.toolbar.addAction(self.viewer_triple_action)
        self.toolbar.addAction(self.viewer_orientation_toggle_action)

        self.tool_name_dict = {"pan":self.pan_tool_action, 
                               "image-edit":self.image_edit_action,
                               "cursor":self.reset_cursor_action, 
                               "select":self.select_tool_action,
                               "grid":self.grid_tool_action,
                               "deselect":self.deselect_tool_action, 
                               "edit-choose":self.edit_tool_action, 
                               "edit-new":self.edit_tool_action}
        
        self.toolbar.setIconSize(QSize(32, 32))

        # Slider for navigating through images
        self.image_slider = FrameSlider(Qt.Horizontal, self)
        self.image_slider.setTracking(False)
        self.image_slider.valueChanged.connect(self.handle_committed_image_slider_value)
        self.image_slider.sliderMoved.connect(self.handle_preview_image_slider_value)
        self.image_slider.sliderPressed.connect(self.handle_image_slider_pressed)
        self.image_slider.sliderReleased.connect(self.handle_image_slider_released)
        self.image_slider.keyframeClicked.connect(self.update_keyframe_list)
        self.image_slider.flagframeClicked.connect(self.update_flaggedframe_list)
        self.image_preview_timer = QTimer(self)
        self.image_preview_timer.setSingleShot(True)
        self.image_preview_timer.timeout.connect(self.flush_pending_preview_image)
        self.image_edit_preview_timer = QTimer(self)
        self.image_edit_preview_timer.setSingleShot(True)
        self.image_edit_preview_timer.setTimerType(Qt.PreciseTimer)
        self.image_edit_preview_timer.timeout.connect(self.flush_pending_image_edit_preview)
        self.image_edit_histogram_timer = QTimer(self)
        self.image_edit_histogram_timer.setSingleShot(True)
        self.image_edit_histogram_timer.setTimerType(Qt.PreciseTimer)
        self.image_edit_histogram_timer.timeout.connect(self.flush_pending_image_edit_histogram)
        self.analysis_progress_timer = QTimer(self)
        self.analysis_progress_timer.setSingleShot(True)
        self.analysis_progress_timer.timeout.connect(self.flush_pending_analysis_progress)
        
        # Text box to display slider value
        self.image_textbox = QLineEdit()
        self.image_textbox.returnPressed.connect(self.updateImageFromTextbox)

        view_slider_layout = QVBoxLayout()
        view_slider_layout.setContentsMargins(0, 0, 0, 0)

        # Button for slider manipulating and keyframe editing
        # Create the buttons
        self.leftButton = QPushButton()
        self.rightButton = QPushButton()
        self.keyframe_toggle_button = QPushButton()
        self.flag_toggle_button = QPushButton()

        self.leftButton.clicked.connect(self.decreaseSliderValue)
        self.rightButton.clicked.connect(self.increaseSliderValue)
        self.keyframe_toggle_button.clicked.connect(self.image_slider.toggle_keyframe)
        self.flag_toggle_button.clicked.connect(self.image_slider.toggle_flagging)

        # Zoom slider for changing the granularity of the image_slider
        self.zoom_slider = SliderZoom_Slider(Qt.Horizontal, self)
        self.zoom_slider.valueChanged.connect(self.image_slider.update_zoomed_level)

        slider_buttons_layout = QHBoxLayout()
        slider_buttons_layout.addStretch(1)
        slider_buttons_layout.addWidget(self.keyframe_toggle_button)
        slider_buttons_layout.addWidget(self.flag_toggle_button)
        slider_buttons_layout.addWidget(self.zoom_slider)
        slider_buttons_layout.addWidget(self.leftButton)
        slider_buttons_layout.addWidget(self.rightButton)
        slider_buttons_layout.addStretch(1)
        slider_buttons_layout.setContentsMargins(0, 0, 0, 3)

        slider_buttons_widget = QWidget()
        slider_buttons_widget.setLayout(slider_buttons_layout)

        # Create a QHBoxLayout for image slider and text box
        image_navigation_layout = QVBoxLayout()
        image_navigation_layout.setContentsMargins(0, 0, 0, 6)
        image_navigation_layout.addWidget(self.image_slider)

        # CustomGraphicsView and QGraphicsScene for image display
        self.scene = QGraphicsScene(self)
        self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.scene.selectionChanged.connect(self.handle_scene_cell_selection_changed)
        self.view = CustomGraphicsView(self.scene, self)
        
        view_slider_layout.addWidget(self.view)
        view_slider_layout.addWidget(slider_buttons_widget)
        view_slider_layout.addLayout(image_navigation_layout)
        view_slider_layout.setSpacing(0)
        view_slider_layout.setContentsMargins(0, 0, 0, 0)

        self.view_slider_widget = QWidget()
        self.view_slider_widget.setLayout(view_slider_layout)

        self.terminal = QTextEdit(self)
        self.terminal.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.terminal.setReadOnly(True)

        self.image_list_model = ImageListModel(self)
        self.image_list_widget = QListView(self)
        self.image_list_widget.setModel(self.image_list_model)
        self.image_list_widget.setAlternatingRowColors(True)
        self.image_list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.image_list_widget.setUniformItemSizes(True)
        self.image_list_widget.setWrapping(False)
        self.image_list_widget.setFocusPolicy(Qt.StrongFocus)
        self.image_list_widget.setMinimumWidth(SIDE_PANEL_DEFAULT_WIDTH)
        self.image_list_widget.clicked.connect(self.handle_image_list_selection)
        self.image_list_widget.selectionModel().currentChanged.connect(self.handle_image_list_current_changed)

        # These tables are retained for internal data/export handling only.
        # They are no longer docked in the UI, so they must not be visible
        # children of the main window.
        self.data_table = QTableWidget()
        self.freeze_table = QTableWidget()
        self.temperature_sync_table = QTableWidget()
        self.grayscale_plot_widget = GrayscalePlotWidget(self)
        self.setup_table_widget(self.data_table)
        self.setup_table_widget(self.freeze_table)
        self.setup_table_widget(self.temperature_sync_table)
        self.results_table_tabs = QTabWidget(self)
        self.results_table_tabs.addTab(self.data_table, "Measurements")
        self.results_table_tabs.addTab(self.freeze_table, "Freeze Events")
        self.results_table_tabs.addTab(self.temperature_sync_table, "Temperature Sync")
        self.results_table_tabs.setTabPosition(QTabWidget.South)
        self.results_table_tabs.tabBar().setExpanding(False)
        self.results_table_tabs.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: right;
            }
        """)
        self.update_results_table_visibility()
        self.tool_options_widget = self.build_tool_options_panel()
        self.sample_catalog_widget = self.build_sample_catalog_panel()
        self.cells_panel_widget = self.build_cells_panel()

        self.setCentralWidget(self.view_slider_widget)
        self.image_list_widget.installEventFilter(self)
        self.image_list_widget.viewport().installEventFilter(self)
        self.image_slider.installEventFilter(self)
        self.zoom_slider.installEventFilter(self)
        self.image_textbox.installEventFilter(self)
        self.grayscale_plot_widget.installEventFilter(self)
        self.grayscale_plot_widget.plot_widget.installEventFilter(self)
        self.setDockNestingEnabled(True)
        self.setDockOptions(
            self.dockOptions()
            | QMainWindow.AllowTabbedDocks
            | QMainWindow.AllowNestedDocks
            | QMainWindow.GroupedDragging
        )
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

        self.image_list_dock = self.create_dock_widget("Images", self.image_list_widget, "imageListDock")
        self.console_dock = self.create_dock_widget("Console", self.terminal, "consoleDock")
        self.tool_options_dock = self.create_dock_widget("Tool Options", self.tool_options_widget, "toolOptionsDock")
        self.sample_catalog_dock = self.create_dock_widget("Sample Catalog", self.sample_catalog_widget, "sampleCatalogDock")
        self.cells_dock = self.create_dock_widget("Cells", self.cells_panel_widget, "cellsDock")
        self.grayscale_dock = None
        self.grayscale_plot_dock = self.create_dock_widget("Grayscale Plot", self.grayscale_plot_widget, "grayscalePlotDock")
        self.results_tables_dock = self.create_dock_widget("Results Tables", self.results_table_tabs, "resultsTablesDock")
        self.freeze_dock = None

        self.addDockWidget(Qt.LeftDockWidgetArea, self.image_list_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.tool_options_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.sample_catalog_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.cells_dock)
        self.tabifyDockWidget(self.tool_options_dock, self.sample_catalog_dock)
        self.tabifyDockWidget(self.sample_catalog_dock, self.cells_dock)
        self.tool_options_dock.raise_()
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.grayscale_plot_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.results_tables_dock)
        self.tabifyDockWidget(self.console_dock, self.grayscale_plot_dock)
        self.tabifyDockWidget(self.grayscale_plot_dock, self.results_tables_dock)
        self.console_dock.raise_()
        self.sample_catalog_dock.hide()
        self.cells_dock.hide()
        self.grayscale_plot_dock.hide()
        self.results_tables_dock.hide()
        self.cells_dock.visibilityChanged.connect(self.handle_cells_panel_visibility_changed)

        reset_layout_action = QAction("Reset Panel Layout", self)
        reset_layout_action.triggered.connect(self.reset_panel_layout)
        self.zoom_window_action = QAction("Zoom Window", self)
        self.zoom_window_action.triggered.connect(self.zoom_window)
        self.restore_window_action = QAction("Restore Window", self)
        self.restore_window_action.triggered.connect(self.restore_window)
        window_menu.addAction(self.zoom_window_action)
        window_menu.addAction(self.restore_window_action)
        window_menu.addSeparator()
        window_menu.addAction(self.viewer_single_action)
        window_menu.addAction(self.viewer_double_action)
        window_menu.addAction(self.viewer_triple_action)
        window_menu.addAction(self.viewer_orientation_toggle_action)
        window_menu.addSeparator()
        window_menu.addAction(reset_layout_action)
        window_menu.addSeparator()
        window_menu.addAction(self.image_list_dock.toggleViewAction())
        window_menu.addAction(self.tool_options_dock.toggleViewAction())
        window_menu.addAction(self.sample_catalog_dock.toggleViewAction())
        window_menu.addAction(self.cells_dock.toggleViewAction())
        window_menu.addAction(self.console_dock.toggleViewAction())
        window_menu.addAction(self.grayscale_plot_dock.toggleViewAction())
        window_menu.addAction(self.results_tables_dock.toggleViewAction())

        # Create a QHBoxLayout for circle radius and zoom level
        self.statusBar = QStatusBar()

        # Create labels and text boxes
        self.session_metadata_status_label = QLabel("", self)
        self.session_metadata_status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.session_metadata_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.session_metadata_status_label.setMinimumWidth(0)
        self.radius_status_label = QLabel("Circle Radius:")
        self.zoom_status_label = QLabel("Zoom Level:")
        self.frame_status_label = QLabel("Frame Number:")

        self.radius_textbox = QLineEdit() # Status text box showing the radius of the circle size for add circle
        self.zoom_textbox = QLineEdit()   # Level of magnifying for the image
        self.radius_textbox.returnPressed.connect(self.updateCircleRadius_from_textedit)
        self.zoom_textbox.returnPressed.connect(self.updateZoomLevel)

        # Set maximum width for the text boxes
        self.radius_textbox.setFixedWidth(60)
        self.zoom_textbox.setFixedWidth(60)
        self.image_textbox.setMinimumWidth(72)

        # Set image label
        self.image_name_label = QLabel('', self)

        self.tool_status_label = QLabel('', self)

        # Metadata stays on the left; the live frame/view controls stay grouped on the right.
        self.statusBar.addWidget(self.session_metadata_status_label, 1)
        self.statusBar.addPermanentWidget(self.radius_status_label)
        self.statusBar.addPermanentWidget(self.radius_textbox)
        self.statusBar.addPermanentWidget(self.zoom_status_label)
        self.statusBar.addPermanentWidget(self.zoom_textbox)
        self.statusBar.addPermanentWidget(self.frame_status_label)
        self.statusBar.addPermanentWidget(self.image_textbox)
        self.statusBar.addPermanentWidget(self.image_name_label)
        self.statusBar.addPermanentWidget(self.tool_status_label)

        # Set the status bar
        self.setStatusBar(self.statusBar)

        self.setFocusPolicy(Qt.StrongFocus)  # Enable keyboard focus for the main window

        # Default initializations
        self.reset_cursor_action.trigger()  # force reset the cursor
        self.resize_image_textbox() # set default size for the frame number textbox. Will get called when updating frames (changing slider value)
        self.reset_status_bar_stylesheet()
        self.update_session_metadata_status_label()
        self.updateRadiusTextbox()
        self.updateZoomTextbox()
        self.reset_toolbar_icon()
        self.reset_toolbar_stylesheet()
        self.reset_slider_stylesheet()
        self.reset_button_icon()
        self.reset_button_stylesheet()
        self.set_redo_status()
        self.set_undo_status()
        self.updateButtonStates()
        self.update_session_actions_state()
        QTimer.singleShot(0, self.finalize_initial_dock_layout)

        self.log("Initialized. Waiting for input...") # Initialize message in log terminal
        

    ##### END initUI() #####

    def finalize_initial_dock_layout(self):
        QTimer.singleShot(0, self.enforce_initial_right_dock_tab)

    def enforce_initial_right_dock_tab(self):
        if hasattr(self, "tool_options_dock") and self.tool_options_dock is not None:
            self.tool_options_dock.show()
            self.tool_options_dock.raise_()
        self.store_default_dock_state()

    def format_numeric_value(self, value):
        return f"{value:g}"

    def current_preview_absolute_coordinates(self):
        origin = getattr(self, "grid_preview_origin_pixels", None)
        if origin is None:
            return None
        try:
            return (
                float(origin[0]) + float(getattr(self, "preview_offset_x", 0.0)),
                float(origin[1]) + float(getattr(self, "preview_offset_y", 0.0)),
            )
        except (TypeError, ValueError, IndexError):
            return None

    def clamp_preview_absolute_coordinates(self, x_value, y_value):
        try:
            clamped_x = float(x_value)
            clamped_y = float(y_value)
        except (TypeError, ValueError):
            return 0.0, 0.0

        raw_width, raw_height = self.get_current_raw_image_dimensions()
        if raw_width <= 0 or raw_height <= 0:
            return clamped_x, clamped_y

        min_x = 0.0
        min_y = 0.0
        max_x = max(min_x, float(raw_width))
        max_y = max(min_y, float(raw_height))
        return (
            min(max(clamped_x, min_x), max_x),
            min(max(clamped_y, min_y), max_y),
        )

    def set_preview_absolute_coordinates(self, x_value, y_value):
        absolute_x, absolute_y = self.clamp_preview_absolute_coordinates(x_value, y_value)
        origin = getattr(self, "grid_preview_origin_pixels", None)
        if origin is None:
            self.grid_preview_origin_pixels = (absolute_x, absolute_y)
            self.preview_offset_x = 0.0
            self.preview_offset_y = 0.0
            return

        try:
            origin_x = float(origin[0])
            origin_y = float(origin[1])
        except (TypeError, ValueError, IndexError):
            self.grid_preview_origin_pixels = (absolute_x, absolute_y)
            self.preview_offset_x = 0.0
            self.preview_offset_y = 0.0
            return

        self.preview_offset_x = float(absolute_x) - origin_x
        self.preview_offset_y = float(absolute_y) - origin_y

    def build_tool_options_panel(self):
        panel = QWidget(self)
        panel.setObjectName("toolOptionsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        panel.setMinimumWidth(SIDE_PANEL_DEFAULT_WIDTH)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.tool_options_mode_label = QLabel("Tool Options")
        self.tool_options_mode_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.tool_options_mode_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #4a4a4a;")
        layout.addWidget(self.tool_options_mode_label)

        self.tool_options_stack = QStackedWidget(panel)
        self.tool_options_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.tool_options_none_page = ToolOptionsInfoPage(panel)
        self.tool_options_none_label = self.tool_options_none_page.message_label
        self.tool_options_none_page.set_message(
            "Choose a cell or image-edit tool. Tool-specific controls will appear here."
        )

        self.cursor_tool_page = ToolOptionsFormPage(panel)
        self.cursor_info_section_label = self.cursor_tool_page.add_section_label("Cell Info")
        self.cursor_info_row_widgets = {}
        self.cursor_info_label_widgets = {}
        self.cursor_info_value_labels = {}
        cursor_info_rows = (
            ("selected", "Selected:"),
            ("cell_id", "Cell ID:"),
            ("sample_name", "Name:"),
            ("x", "X:"),
            ("y", "Y:"),
            ("radius", "Radius:"),
        )
        for field_name, label_text in cursor_info_rows:
            row_widget, label_widget, value_widget = self.cursor_tool_page.add_value_row(label_text)
            self.cursor_info_row_widgets[field_name] = row_widget
            self.cursor_info_label_widgets[field_name] = label_widget
            self.cursor_info_value_labels[field_name] = value_widget

        self.cursor_info_edit_separator = self.cursor_tool_page.add_separator()
        self.cursor_edit_section_label = self.cursor_tool_page.add_section_label("Cell Edit")
        self.cursor_freeze_lineedit = QLineEdit(self.cursor_tool_page.column_widget)
        self.cursor_freeze_lineedit.setPlaceholderText("None")
        self.cursor_tool_page._configure_control(self.cursor_freeze_lineedit)
        self.cursor_freeze_lineedit.installEventFilter(self)
        self.cursor_freeze_lineedit.editingFinished.connect(self.apply_cursor_freeze_frames_edit)
        self.cursor_freeze_row, self.cursor_freeze_apply_button = self.cursor_tool_page.add_row_with_button(
            "Freeze Frame:",
            self.cursor_freeze_lineedit,
            "Set",
            self.apply_cursor_freeze_frames_edit,
        )

        self.cursor_sample_combo = self.cursor_tool_page.create_combo_box(
            index_handler=self.assign_selected_cells_to_current_sample,
        )
        self.cursor_sample_row = self.cursor_tool_page.add_row("Sample ID:", self.cursor_sample_combo)

        self.cursor_sample_button_row, self.cursor_sample_new_button = self.cursor_tool_page.add_centered_button_row(
            "New Sample",
            self.create_sample_from_cursor_controls,
        )
        self.cursor_tool_hint = self.cursor_tool_page.add_hint(
            "Select cells in Cursor mode to inspect them. Edit freeze frames for one cell or assign samples to one or more cells."
        )
        self.cursor_tool_page.add_bottom_stretch()

        self.delete_tool_page = ToolOptionsFormPage(panel)
        self.delete_tool_hint = self.delete_tool_page.add_hint(
            "Click a cell to delete it. In Cursor mode, select one or more cells and press Delete or Backspace to remove them."
        )
        self.delete_tool_page.add_bottom_stretch()

        self.image_edit_tool_page = ToolOptionsFormPage(
            panel,
            content_width=TOOL_OPTIONS_CONTENT_WIDTH,
            label_width=72,
            field_width=180,
            shortcut_width=0,
        )
        self.image_edit_histogram_widget = ImageHistogramWidget(self.image_edit_tool_page.column_widget)
        self.image_edit_histogram_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.image_edit_tool_page.column_layout.addWidget(self.image_edit_histogram_widget)
        self.image_edit_histogram_separator = self.image_edit_tool_page.add_separator()

        self.image_edit_exposure_block = QWidget(self.image_edit_tool_page.column_widget)
        self.image_edit_exposure_block.setFixedWidth(self.image_edit_tool_page.content_width)
        self.image_edit_exposure_block.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        image_edit_exposure_block_layout = QVBoxLayout(self.image_edit_exposure_block)
        image_edit_exposure_block_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_exposure_block_layout.setSpacing(4)

        self.image_edit_exposure_header = QWidget(self.image_edit_exposure_block)
        self.image_edit_exposure_header.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        image_edit_exposure_header_layout = QHBoxLayout(self.image_edit_exposure_header)
        image_edit_exposure_header_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_exposure_header_layout.setSpacing(8)

        self.image_edit_exposure_label = QLabel("Exposure", self.image_edit_exposure_header)
        self.image_edit_exposure_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        image_edit_exposure_header_layout.addWidget(self.image_edit_exposure_label, 1)

        self.image_edit_exposure_spinbox = QDoubleSpinBox(self.image_edit_exposure_header)
        self.image_edit_exposure_spinbox.setRange(-4.0, 4.0)
        self.image_edit_exposure_spinbox.setDecimals(1)
        self.image_edit_exposure_spinbox.setSingleStep(0.1)
        self.image_edit_exposure_spinbox.setFixedWidth(60)
        self.image_edit_exposure_spinbox.valueChanged.connect(self.handle_image_edit_exposure_spinbox_changed)
        image_edit_exposure_header_layout.addWidget(self.image_edit_exposure_spinbox, 0)
        image_edit_exposure_block_layout.addWidget(self.image_edit_exposure_header)

        self.image_edit_exposure_slider = QSlider(Qt.Horizontal, self.image_edit_exposure_block)
        self.image_edit_exposure_slider.setObjectName("imageEditExposureSlider")
        self.image_edit_exposure_slider.setRange(-40, 40)
        self.image_edit_exposure_slider.setSingleStep(1)
        self.image_edit_exposure_slider.setPageStep(5)
        self.image_edit_exposure_slider.installEventFilter(self)
        self.image_edit_exposure_slider.valueChanged.connect(self.handle_image_edit_exposure_slider_changed)
        self.image_edit_exposure_slider.sliderReleased.connect(self.handle_image_edit_exposure_slider_released)
        self.image_edit_exposure_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        image_edit_exposure_block_layout.addWidget(self.image_edit_exposure_slider)
        self.image_edit_exposure_block.setFixedHeight(self.image_edit_exposure_block.sizeHint().height())
        self.image_edit_tool_page.column_layout.addWidget(self.image_edit_exposure_block)
        self.image_edit_exposure_separator = self.image_edit_tool_page.add_separator()

        self.image_edit_contrast_block = QWidget(self.image_edit_tool_page.column_widget)
        self.image_edit_contrast_block.setFixedWidth(self.image_edit_tool_page.content_width)
        self.image_edit_contrast_block.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        image_edit_contrast_block_layout = QVBoxLayout(self.image_edit_contrast_block)
        image_edit_contrast_block_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_contrast_block_layout.setSpacing(4)

        self.image_edit_contrast_header = QWidget(self.image_edit_contrast_block)
        self.image_edit_contrast_header.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        image_edit_contrast_header_layout = QHBoxLayout(self.image_edit_contrast_header)
        image_edit_contrast_header_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_contrast_header_layout.setSpacing(8)

        self.image_edit_contrast_label = QLabel("Contrast", self.image_edit_contrast_header)
        self.image_edit_contrast_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        image_edit_contrast_header_layout.addWidget(self.image_edit_contrast_label, 1)

        self.image_edit_contrast_spinbox = QSpinBox(self.image_edit_contrast_header)
        self.image_edit_contrast_spinbox.setRange(-100, 100)
        self.image_edit_contrast_spinbox.setSingleStep(1)
        self.image_edit_contrast_spinbox.setFixedWidth(60)
        self.image_edit_contrast_spinbox.valueChanged.connect(self.handle_image_edit_contrast_spinbox_changed)
        image_edit_contrast_header_layout.addWidget(self.image_edit_contrast_spinbox, 0)
        image_edit_contrast_block_layout.addWidget(self.image_edit_contrast_header)

        self.image_edit_contrast_slider = QSlider(Qt.Horizontal, self.image_edit_contrast_block)
        self.image_edit_contrast_slider.setObjectName("imageEditContrastSlider")
        self.image_edit_contrast_slider.setRange(-100, 100)
        self.image_edit_contrast_slider.setSingleStep(1)
        self.image_edit_contrast_slider.setPageStep(10)
        self.image_edit_contrast_slider.installEventFilter(self)
        self.image_edit_contrast_slider.valueChanged.connect(self.handle_image_edit_contrast_slider_changed)
        self.image_edit_contrast_slider.sliderReleased.connect(self.handle_image_edit_contrast_slider_released)
        self.image_edit_contrast_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        image_edit_contrast_block_layout.addWidget(self.image_edit_contrast_slider)
        self.image_edit_contrast_block.setFixedHeight(self.image_edit_contrast_block.sizeHint().height())
        self.image_edit_tool_page.column_layout.addWidget(self.image_edit_contrast_block)
        self.image_edit_contrast_separator = self.image_edit_tool_page.add_separator()

        self.image_edit_uniform_exposure_section_label = self.image_edit_tool_page.add_section_label("Uniform Exposure")
        self.image_edit_uniform_exposure_button_row = QWidget(self.image_edit_tool_page.column_widget)
        image_edit_uniform_exposure_button_layout = QHBoxLayout(self.image_edit_uniform_exposure_button_row)
        image_edit_uniform_exposure_button_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_uniform_exposure_button_layout.setSpacing(TOOL_OPTIONS_BUTTON_SPACING)
        self.image_edit_uniform_exposure_area_button = self.image_edit_tool_page._create_button(
            "Set Area",
            self.image_edit_uniform_exposure_button_row,
            self.handle_image_edit_uniform_exposure_area_button,
        )
        self.image_edit_uniform_exposure_run_button = self.image_edit_tool_page._create_button(
            "Run",
            self.image_edit_uniform_exposure_button_row,
            self.run_image_edit_uniform_exposure,
        )
        self.image_edit_uniform_exposure_reset_button = self.image_edit_tool_page._create_button(
            "Reset",
            self.image_edit_uniform_exposure_button_row,
            self.reset_image_edit_uniform_exposure,
        )
        uniform_button_width = int(
            (
                self.image_edit_tool_page.content_width
                - (2 * TOOL_OPTIONS_BUTTON_SPACING)
            ) / 3
        )
        self.image_edit_uniform_exposure_area_button.setFixedWidth(uniform_button_width)
        self.image_edit_uniform_exposure_run_button.setFixedWidth(uniform_button_width)
        self.image_edit_uniform_exposure_reset_button.setFixedWidth(uniform_button_width)
        image_edit_uniform_exposure_button_layout.addWidget(self.image_edit_uniform_exposure_area_button)
        image_edit_uniform_exposure_button_layout.addWidget(self.image_edit_uniform_exposure_run_button)
        image_edit_uniform_exposure_button_layout.addWidget(self.image_edit_uniform_exposure_reset_button)
        self.image_edit_tool_page.column_layout.addWidget(self.image_edit_uniform_exposure_button_row)
        self.image_edit_uniform_exposure_hint = self.image_edit_tool_page.add_hint(
            "Use the current frame as the reference. Set one control area, then Run to match each image's area brightness to that frame."
        )
        self.image_edit_uniform_exposure_separator = self.image_edit_tool_page.add_separator()

        self.image_edit_crop_section_label = self.image_edit_tool_page.add_section_label("Crop")
        self.image_edit_crop_button_row = QWidget(self.image_edit_tool_page.column_widget)
        image_edit_crop_button_layout = QHBoxLayout(self.image_edit_crop_button_row)
        image_edit_crop_button_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_crop_button_layout.setSpacing(TOOL_OPTIONS_BUTTON_SPACING)
        self.image_edit_crop_start_button = self.image_edit_tool_page._create_button(
            "Crop",
            self.image_edit_crop_button_row,
            self.handle_image_edit_crop_primary_button,
        )
        self.image_edit_crop_apply_button = self.image_edit_tool_page._create_button(
            "Apply",
            self.image_edit_crop_button_row,
            self.apply_image_edit_crop,
        )
        self.image_edit_crop_reset_button = self.image_edit_tool_page._create_button(
            "Reset",
            self.image_edit_crop_button_row,
            self.reset_image_edit_crop,
        )
        button_width = int(
            (
                self.image_edit_tool_page.content_width
                - (2 * TOOL_OPTIONS_BUTTON_SPACING)
            ) / 3
        )
        self.image_edit_crop_start_button.setFixedWidth(button_width)
        self.image_edit_crop_apply_button.setFixedWidth(button_width)
        self.image_edit_crop_reset_button.setFixedWidth(button_width)
        image_edit_crop_button_layout.addWidget(self.image_edit_crop_start_button)
        image_edit_crop_button_layout.addWidget(self.image_edit_crop_apply_button)
        image_edit_crop_button_layout.addWidget(self.image_edit_crop_reset_button)
        self.image_edit_tool_page.column_layout.addWidget(self.image_edit_crop_button_row)

        self.image_edit_tool_hint = self.image_edit_tool_page.add_hint(
            "Exposure and contrast apply to all images. Uniform Exposure matches one control area across frames. Press Crop, adjust the box, then Apply. Reset restores the committed crop to the full image."
        )
        self.image_edit_tool_page.add_bottom_stretch()

        self.circle_tool_page = ToolOptionsFormPage(panel)
        self.circle_radius_spinbox = self.circle_tool_page.create_double_spin_box(
            1,
            100000,
            value_handler=self.handle_circle_radius_spinbox_changed,
        )
        self.circle_offset_x_spinbox = self.circle_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.circle_offset_y_spinbox = self.circle_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.circle_tool_page.add_row("Radius", self.circle_radius_spinbox, "scroll")
        self.circle_tool_page.add_row("X", self.circle_offset_x_spinbox)
        self.circle_tool_page.add_row("Y", self.circle_offset_y_spinbox)
        self.circle_tool_page.add_action_row(
            self.handle_circle_apply_action,
            self.handle_circle_float_action,
            self.handle_circle_cancel_action,
        )
        self.circle_tool_hint = self.circle_tool_page.add_hint(
            "Move the preview over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
        )
        self.circle_apply_button = self.circle_tool_page.apply_button
        self.circle_float_button = self.circle_tool_page.float_button
        self.circle_cancel_button = self.circle_tool_page.cancel_button
        self.circle_tool_page.add_bottom_stretch()

        self.edit_circle_tool_page = ToolOptionsFormPage(panel)
        self.edit_circle_cell_id_spinbox = self.edit_circle_tool_page.create_spin_box(0, 100000)
        self.edit_circle_cell_id_spinbox.editingFinished.connect(self.apply_edit_circle_cell_id_edit)
        self.edit_circle_radius_spinbox = self.edit_circle_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_circle_radius_spinbox_changed,
        )
        self.edit_circle_offset_x_spinbox = self.edit_circle_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.edit_circle_offset_y_spinbox = self.edit_circle_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.edit_circle_tool_page.add_row("Cell ID", self.edit_circle_cell_id_spinbox)
        self.edit_circle_tool_page.add_row("Radius Delta", self.edit_circle_radius_spinbox, "scroll")
        self.edit_circle_tool_page.add_row("X Offset", self.edit_circle_offset_x_spinbox)
        self.edit_circle_tool_page.add_row("Y Offset", self.edit_circle_offset_y_spinbox)
        self.edit_circle_tool_page.add_action_row(
            self.handle_circle_apply_action,
            self.handle_circle_float_action,
            self.handle_circle_cancel_action,
        )
        self.edit_circle_tool_hint = self.edit_circle_tool_page.add_hint(
            "Move the lifted circle over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
        )
        self.edit_circle_apply_button = self.edit_circle_tool_page.apply_button
        self.edit_circle_float_button = self.edit_circle_tool_page.float_button
        self.edit_circle_cancel_button = self.edit_circle_tool_page.cancel_button
        self.edit_circle_tool_page.add_bottom_stretch()

        self.grid_tool_page = ToolOptionsFormPage(panel)
        self.grid_rows_spinbox = self.grid_tool_page.create_spin_box(
            1,
            100,
            value_handler=self.handle_grid_parameter_change,
        )
        self.grid_columns_spinbox = self.grid_tool_page.create_spin_box(
            1,
            100,
            value_handler=self.handle_grid_parameter_change,
        )
        self.grid_radius_spinbox = self.grid_tool_page.create_double_spin_box(
            1,
            100000,
            value_handler=self.handle_grid_radius_change,
        )
        self.grid_hpitch_spinbox = self.grid_tool_page.create_double_spin_box(
            1,
            100000,
            value_handler=self.handle_grid_parameter_change,
        )
        self.grid_vpitch_spinbox = self.grid_tool_page.create_double_spin_box(
            1,
            100000,
            value_handler=self.handle_grid_parameter_change,
        )
        self.grid_rotation_spinbox = self.grid_tool_page.create_double_spin_box(
            -180,
            180,
            value_handler=self.handle_grid_parameter_change,
        )
        self.grid_offset_x_spinbox = self.grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.grid_offset_y_spinbox = self.grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.grid_tool_page.add_row("Rows", self.grid_rows_spinbox)
        self.grid_tool_page.add_row("Cols", self.grid_columns_spinbox)
        self.grid_tool_page.add_row("Radius", self.grid_radius_spinbox, "scroll")
        self.grid_tool_page.add_row("H Pitch", self.grid_hpitch_spinbox, "opt+scroll")
        self.grid_tool_page.add_row("V Pitch", self.grid_vpitch_spinbox, "ctrl+scroll")
        self.grid_tool_page.add_row("Tilt", self.grid_rotation_spinbox, "cmd+scroll")
        self.grid_tool_page.add_row("X", self.grid_offset_x_spinbox)
        self.grid_tool_page.add_row("Y", self.grid_offset_y_spinbox)
        self.grid_tool_page.add_action_row(
            self.handle_grid_apply_action,
            self.handle_grid_float_action,
            self.handle_grid_cancel_action,
        )
        self.grid_tool_hint = self.grid_tool_page.add_hint(
            "Move the preview over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
        )
        self.grid_apply_button = self.grid_tool_page.apply_button
        self.grid_float_button = self.grid_tool_page.float_button
        self.grid_cancel_button = self.grid_tool_page.cancel_button
        self.grid_tool_page.add_bottom_stretch()

        self.edit_grid_tool_page = ToolOptionsFormPage(panel)
        self.edit_grid_radius_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_grid_radius_change,
        )
        self.edit_grid_hpitch_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_grid_parameter_change,
        )
        self.edit_grid_vpitch_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_grid_parameter_change,
        )
        self.edit_grid_rotation_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -180,
            180,
            value_handler=self.handle_grid_parameter_change,
        )
        self.edit_grid_offset_x_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.edit_grid_offset_y_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.edit_grid_tool_page.add_row("Radius Delta", self.edit_grid_radius_spinbox, "scroll")
        self.edit_grid_tool_page.add_row("H Pitch Delta", self.edit_grid_hpitch_spinbox, "opt+scroll")
        self.edit_grid_tool_page.add_row("V Pitch Delta", self.edit_grid_vpitch_spinbox, "ctrl+scroll")
        self.edit_grid_tool_page.add_row("Tilt Delta", self.edit_grid_rotation_spinbox, "cmd+scroll")
        self.edit_grid_tool_page.add_row("X Offset", self.edit_grid_offset_x_spinbox)
        self.edit_grid_tool_page.add_row("Y Offset", self.edit_grid_offset_y_spinbox)
        self.edit_grid_tool_page.add_action_row(
            self.handle_grid_apply_action,
            self.handle_grid_float_action,
            self.handle_grid_cancel_action,
        )
        self.edit_grid_tool_hint = self.edit_grid_tool_page.add_hint(
            "Move the group preview over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
        )
        self.edit_grid_apply_button = self.edit_grid_tool_page.apply_button
        self.edit_grid_float_button = self.edit_grid_tool_page.float_button
        self.edit_grid_cancel_button = self.edit_grid_tool_page.cancel_button
        self.edit_grid_tool_page.add_bottom_stretch()

        self.tool_options_stack.addWidget(self.tool_options_none_page)
        self.tool_options_stack.addWidget(self.cursor_tool_page)
        self.tool_options_stack.addWidget(self.delete_tool_page)
        self.tool_options_stack.addWidget(self.image_edit_tool_page)
        self.tool_options_stack.addWidget(self.circle_tool_page)
        self.tool_options_stack.addWidget(self.grid_tool_page)
        self.tool_options_stack.addWidget(self.edit_circle_tool_page)
        self.tool_options_stack.addWidget(self.edit_grid_tool_page)
        layout.addWidget(self.tool_options_stack, 1)

        panel.setStyleSheet(f"""
            QLabel {{ line-height: 1.3; }}
            {TOOL_OPTIONS_CONTROL_QSS}
        """)

        self.sync_tool_options_panel()
        return panel

    def build_cells_panel(self):
        panel = QWidget(self)
        panel.setMinimumWidth(SIDE_PANEL_DEFAULT_WIDTH)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.cells_tree_widget = QTreeWidget(panel)
        self.cells_tree_widget.setColumnCount(2)
        self.cells_tree_widget.setHeaderLabels(["Field", "Value"])
        self.cells_tree_widget.setRootIsDecorated(True)
        self.cells_tree_widget.setUniformRowHeights(True)
        self.cells_tree_widget.setAlternatingRowColors(True)
        self.cells_tree_widget.setAnimated(False)
        self.cells_tree_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cells_tree_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.cells_tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.cells_tree_widget.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.cells_tree_widget.itemSelectionChanged.connect(self.handle_cells_panel_selection_changed)
        layout.addWidget(self.cells_tree_widget, 1)

        hint = QLabel(
            "Shows mostly static cell record data. Sample assignment stays in Cursor mode and Sample Catalog.",
            panel,
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        layout.addWidget(hint)

        self.cells_panel_last_snapshot = None
        self.cells_panel_dirty = False
        self.cells_panel_force_refresh = False
        self.refresh_cells_panel()
        return panel

    def build_sample_catalog_panel(self):
        panel = QWidget(self)
        panel.setMinimumWidth(SIDE_PANEL_DEFAULT_WIDTH)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Sample Catalog", panel)
        title.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        title.setStyleSheet("font-size: 13px; font-weight: 600; color: #4a4a4a;")
        layout.addWidget(title)

        self.sample_catalog_table_syncing = False
        self.sample_catalog_table = QTableWidget(panel)
        self.sample_catalog_table.setColumnCount(2)
        self.sample_catalog_table.setHorizontalHeaderLabels(["Sample ID", "Sample Name"])
        self.sample_catalog_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sample_catalog_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.sample_catalog_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.SelectedClicked
        )
        self.sample_catalog_table.horizontalHeader().setStretchLastSection(True)
        self.sample_catalog_table.verticalHeader().setVisible(False)
        self.sample_catalog_table.itemChanged.connect(self.handle_sample_catalog_item_changed)
        self.sample_catalog_table.itemSelectionChanged.connect(self.update_sample_catalog_buttons)
        layout.addWidget(self.sample_catalog_table, 1)

        button_row = QWidget(panel)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(TOOL_OPTIONS_BUTTON_SPACING)
        self.sample_add_button = QPushButton("Add", button_row)
        self.sample_add_button.clicked.connect(self.add_sample_catalog_entry)
        self.sample_delete_button = QPushButton("Delete", button_row)
        self.sample_delete_button.clicked.connect(self.delete_selected_sample_catalog_entry)
        button_layout.addWidget(self.sample_add_button)
        button_layout.addWidget(self.sample_delete_button)
        button_layout.addStretch(1)
        layout.addWidget(button_row)

        hint = QLabel(
            "Sample IDs are session-level labels. Rename sample names directly in the table.",
            panel,
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        layout.addWidget(hint)

        self.refresh_sample_catalog_table(preserve_selection=False)
        return panel

    def selected_sample_catalog_id(self):
        if not hasattr(self, "sample_catalog_table"):
            return None
        row = self.sample_catalog_table.currentRow()
        if row < 0:
            return None
        id_item = self.sample_catalog_table.item(row, 0)
        if id_item is None:
            return None
        sample_id = id_item.data(Qt.UserRole)
        if sample_id is None:
            try:
                sample_id = int(id_item.text())
            except (TypeError, ValueError):
                return None
        try:
            return int(sample_id)
        except (TypeError, ValueError):
            return None

    def refresh_sample_catalog_table(self, select_sample_id=None, preserve_selection=True):
        if not hasattr(self, "sample_catalog_table"):
            return

        self.ensure_sample_catalog_matches_cell_records()

        if select_sample_id is None and preserve_selection:
            select_sample_id = self.selected_sample_catalog_id()

        self.sample_catalog_table_syncing = True
        self.sample_catalog_table.blockSignals(True)
        try:
            ordered_samples = sorted(
                ((int(sample_id), str(sample_name)) for sample_id, sample_name in self.sample_catalog.items()),
                key=lambda pair: pair[0],
            )
            self.sample_catalog_table.setRowCount(len(ordered_samples))
            for row, (sample_id, sample_name) in enumerate(ordered_samples):
                id_item = QTableWidgetItem(str(sample_id))
                id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
                id_item.setData(Qt.UserRole, int(sample_id))
                self.sample_catalog_table.setItem(row, 0, id_item)

                name_item = QTableWidgetItem(sample_name)
                name_item.setData(Qt.UserRole, int(sample_id))
                self.sample_catalog_table.setItem(row, 1, name_item)
        finally:
            self.sample_catalog_table.blockSignals(False)
            self.sample_catalog_table_syncing = False

        if select_sample_id is not None:
            for row in range(self.sample_catalog_table.rowCount()):
                id_item = self.sample_catalog_table.item(row, 0)
                if id_item is None:
                    continue
                if int(id_item.data(Qt.UserRole)) == int(select_sample_id):
                    self.sample_catalog_table.selectRow(row)
                    self.sample_catalog_table.setCurrentCell(row, 1)
                    break

        self.update_sample_catalog_buttons()
        self.update_cursor_sample_controls()
        self.refresh_cells_panel()

    def update_sample_catalog_buttons(self):
        if not hasattr(self, "sample_delete_button"):
            return
        self.sample_delete_button.setEnabled(self.selected_sample_catalog_id() is not None)

    def add_sample_catalog_entry(self):
        before_state = self.capture_data_state()
        sample_id = self.allocate_sample_id()
        self.sample_catalog[int(sample_id)] = self.default_sample_name(sample_id)
        self.recompute_next_sample_id(preserve_if_larger=True)
        self.refresh_sample_catalog_table(select_sample_id=sample_id, preserve_selection=False)
        self.invalidate_temperature_sync_results("sample catalog changed")
        self.push_data_history("Add Sample", before_state)
        self.log(f"Add sample {sample_id}")

    def delete_selected_sample_catalog_entry(self):
        sample_id = self.selected_sample_catalog_id()
        if sample_id is None:
            return

        used_by_cells = sorted(
            cell_id
            for cell_id, record in self.cell_records_by_id.items()
            if str(getattr(record, "sample_id", "")) == str(sample_id)
        )
        if used_by_cells:
            preview = ", ".join(str(cell_id) for cell_id in used_by_cells[:8])
            if len(used_by_cells) > 8:
                preview += ", ..."
            sample_name = str(self.sample_catalog.get(sample_id, self.default_sample_name(sample_id)))
            QMessageBox.warning(
                self,
                "Delete Sample",
                f"{sample_name} is assigned to cell(s): {preview}. Reassign those cells first.",
            )
            return

        if sample_id not in self.sample_catalog:
            return

        before_state = self.capture_data_state()
        self.sample_catalog.pop(sample_id, None)
        self.recompute_next_sample_id(preserve_if_larger=True)
        self.refresh_sample_catalog_table(preserve_selection=False)
        self.invalidate_temperature_sync_results("sample catalog changed")
        self.push_data_history("Delete Sample", before_state)
        self.log(f"Delete sample {sample_id}")

    def handle_sample_catalog_item_changed(self, item):
        if item is None or self.sample_catalog_table_syncing:
            return
        if item.column() != 1:
            return

        sample_id = item.data(Qt.UserRole)
        try:
            sample_id = int(sample_id)
        except (TypeError, ValueError):
            return

        new_name = str(item.text()).strip()
        if not new_name:
            new_name = self.default_sample_name(sample_id)
            self.sample_catalog_table_syncing = True
            try:
                item.setText(new_name)
            finally:
                self.sample_catalog_table_syncing = False

        old_name = str(self.sample_catalog.get(sample_id, ""))
        if old_name == new_name:
            return

        before_state = self.capture_data_state()
        self.sample_catalog[sample_id] = new_name
        self.invalidate_temperature_sync_results("sample names changed")
        self.push_data_history("Rename Sample", before_state)
        self.log(f"Rename sample {sample_id} to {new_name}")
        self.update_cursor_sample_controls()
        self.refresh_cells_panel()

    def update_cursor_sample_controls(self):
        if not hasattr(self, "cursor_tool_page") or not hasattr(self, "cursor_sample_combo") or not hasattr(self, "cursor_sample_new_button"):
            return

        if self.tool_mode != "cursor":
            return

        self.ensure_sample_catalog_matches_cell_records()

        selected_items = sorted(
            self.get_selected_cell_items(),
            key=lambda item: int(getattr(item, "cell_id", 0)),
        )
        selected_sample_ids = set()
        for item in selected_items:
            record = self.ensure_cell_record(item.cell_id)
            sample_id = str(getattr(record, "sample_id", ""))
            selected_sample_ids.add(sample_id)

        has_mixed_selection = bool(selected_items) and len(selected_sample_ids) > 1
        self.refresh_cursor_sample_combo_catalog(include_mixed_item=has_mixed_selection)

        blocker = QSignalBlocker(self.cursor_sample_combo)
        if not selected_items:
            self.cursor_sample_combo.setCurrentIndex(0)
        elif len(selected_sample_ids) == 1:
            target_sample = next(iter(selected_sample_ids))
            sample_index = self.cursor_sample_combo.findData(target_sample)
            self.cursor_sample_combo.setCurrentIndex(sample_index if sample_index >= 0 else 0)
        else:
            sample_index = self.cursor_sample_combo.findData("__mixed__")
            self.cursor_sample_combo.setCurrentIndex(sample_index if sample_index >= 0 else 0)

        self.refresh_cursor_selection_info(selected_items=selected_items)
        self.update_cursor_record_edit_state(selected_items=selected_items)
        self.update_cursor_sample_assignment_state()

    def update_cursor_sample_assignment_state(self):
        selected_count = len(self.get_selected_cell_items())
        self.cursor_sample_new_button.setEnabled(self.tool_mode == "cursor")
        if hasattr(self, "cursor_sample_combo"):
            self.cursor_sample_combo.setEnabled(self.tool_mode == "cursor" and selected_count > 0)

    def assign_selected_cells_to_current_sample(self):
        selected_items = self.get_selected_cell_items()
        if not selected_items:
            return
        sample_value = self.cursor_sample_combo.currentData() if hasattr(self, "cursor_sample_combo") else None
        if sample_value in (None, "__mixed__"):
            return
        sample_id = str(sample_value)

        before_state = self.capture_data_state()
        changed = False
        for item in selected_items:
            record = self.ensure_cell_record(item.cell_id)
            if record is None:
                continue
            if str(getattr(record, "sample_id", "")) == sample_id:
                continue
            record.sample_id = sample_id
            changed = True

        if not changed:
            return

        self.invalidate_temperature_sync_results("sample assignments changed")
        self.push_data_history("Assign Sample", before_state)
        if sample_id:
            self.log(f"Assign sample {sample_id} to {len(selected_items)} selected cell(s)")
        else:
            self.log(f"Clear sample assignment for {len(selected_items)} selected cell(s)")
        self.refresh_cell_sample_visuals()
        self.update_cursor_sample_controls()
        self.refresh_cells_panel()

    def create_sample_from_cursor_controls(self):
        before_state = self.capture_data_state()
        sample_id = self.allocate_sample_id()
        self.sample_catalog[int(sample_id)] = self.default_sample_name(sample_id)
        selected_items = self.get_selected_cell_items()
        for item in selected_items:
            record = self.ensure_cell_record(item.cell_id)
            if record is not None:
                record.sample_id = str(sample_id)

        self.recompute_next_sample_id(preserve_if_larger=True)
        self.refresh_sample_catalog_table(select_sample_id=sample_id, preserve_selection=False)
        self.invalidate_temperature_sync_results("sample catalog changed")
        if selected_items:
            self.push_data_history("Create and Assign Sample", before_state)
            self.log(f"Create sample {sample_id} and assign to {len(selected_items)} selected cell(s)")
        else:
            self.push_data_history("Add Sample", before_state)
            self.log(f"Add sample {sample_id}")
        self.refresh_cell_sample_visuals()
        self.update_cursor_sample_controls()
        self.refresh_cells_panel()

    def sync_tool_options_panel(self):
        # Keep the panel in sync with the current tool state without letting the
        # spin boxes fire recursive updates while we are just mirroring state.
        #
        # Add and Edit intentionally do not share one population source:
        # Add uses the session's live add parameters; Edit must reflect the
        # item/group being edited.
        if not hasattr(self, "tool_options_stack"):
            return

        if self.tool_mode == "select":
            self.tool_options_mode_label.setText("Single Circle")
            self.tool_options_stack.setCurrentWidget(self.circle_tool_page)
            self.sync_circle_tool_panel(radius=self.circle_radius, is_edit=False)
        elif self.cell_controller.uses_grid_panel():
            if self.cell_controller.is_group_edit_mode():
                self.tool_options_mode_label.setText("Edit Group")
                self.tool_options_stack.setCurrentWidget(self.edit_grid_tool_page)
                self.sync_grid_tool_panel(is_edit=True)
            else:
                self.tool_options_mode_label.setText("Grid Placement")
                self.tool_options_stack.setCurrentWidget(self.grid_tool_page)
                self.sync_grid_tool_panel(is_edit=False)
        elif self.tool_mode == "edit-new":
            self.tool_options_mode_label.setText("Edit Cell")
            self.tool_options_stack.setCurrentWidget(self.edit_circle_tool_page)
            self.sync_circle_tool_panel(radius=0.0, is_edit=True)
        elif self.tool_mode == "edit-choose":
            self.tool_options_mode_label.setText("Edit Cell")
            self.tool_options_none_label.setText("Select one circle to edit it, or select several circles in Cursor mode and then choose Edit.")
            self.tool_options_stack.setCurrentWidget(self.tool_options_none_page)
        elif self.tool_mode == "grid":
            self.tool_options_mode_label.setText("Grid Placement")
            self.tool_options_stack.setCurrentWidget(self.grid_tool_page)
            self.sync_grid_tool_panel(is_edit=False)
        elif self.tool_mode == "cursor":
            self.tool_options_mode_label.setText("Cursor")
            self.tool_options_stack.setCurrentWidget(self.cursor_tool_page)
        elif self.tool_mode == "deselect":
            self.tool_options_mode_label.setText("Delete Cells")
            self.tool_options_stack.setCurrentWidget(self.delete_tool_page)
        elif self.tool_mode == "image-edit":
            self.tool_options_mode_label.setText("Image Edit")
            self.tool_options_stack.setCurrentWidget(self.image_edit_tool_page)
            self.sync_image_edit_controls()
            self.request_image_edit_histogram_refresh()
        else:
            self.tool_options_mode_label.setText("Tool Options")
            self.tool_options_none_label.setText("Choose a cell or image-edit tool. Tool-specific controls will appear here.")
            self.tool_options_stack.setCurrentWidget(self.tool_options_none_page)

        self.sync_image_edit_crop_overlay()
        desired_crop_applied = self.should_apply_crop_in_display()
        if self.imagePaths and self.displayed_image_edit_crop_applied != desired_crop_applied:
            self.updateImage(self.image_index)

        self.update_preview_shortcut_enabled_state()
        self.update_cursor_sample_controls()
        self.update_grid_apply_state()

    def update_preview_shortcut_enabled_state(self):
        preview_shortcuts_enabled = (
            hasattr(self, "cell_controller")
            and self.cell_controller.uses_grid_preview()
        )
        for shortcut_name in (
            "preview_confirm_shortcut",
            "preview_confirm_shortcut_enter",
            "preview_cancel_shortcut",
        ):
            shortcut = getattr(self, shortcut_name, None)
            if shortcut is not None:
                shortcut.setEnabled(preview_shortcuts_enabled)

    def current_circle_controls(self):
        if self.tool_mode == "edit-new":
            return {
                "radius": self.edit_circle_radius_spinbox,
                "offset_x": self.edit_circle_offset_x_spinbox,
                "offset_y": self.edit_circle_offset_y_spinbox,
                "hint": self.edit_circle_tool_hint,
                "apply": self.edit_circle_apply_button,
                "float": self.edit_circle_float_button,
                "cancel": self.edit_circle_cancel_button,
            }
        return {
            "radius": self.circle_radius_spinbox,
            "offset_x": self.circle_offset_x_spinbox,
            "offset_y": self.circle_offset_y_spinbox,
            "hint": self.circle_tool_hint,
            "apply": self.circle_apply_button,
            "float": self.circle_float_button,
            "cancel": self.circle_cancel_button,
        }

    def current_grid_controls(self):
        if self.cell_controller.is_group_edit_mode():
            return {
                "rows": None,
                "cols": None,
                "radius": self.edit_grid_radius_spinbox,
                "hpitch": self.edit_grid_hpitch_spinbox,
                "vpitch": self.edit_grid_vpitch_spinbox,
                "rotation": self.edit_grid_rotation_spinbox,
                "offset_x": self.edit_grid_offset_x_spinbox,
                "offset_y": self.edit_grid_offset_y_spinbox,
                "hint": self.edit_grid_tool_hint,
                "apply": self.edit_grid_apply_button,
                "float": self.edit_grid_float_button,
                "cancel": self.edit_grid_cancel_button,
            }
        return {
            "rows": self.grid_rows_spinbox,
            "cols": self.grid_columns_spinbox,
            "radius": self.grid_radius_spinbox,
            "hpitch": self.grid_hpitch_spinbox,
            "vpitch": self.grid_vpitch_spinbox,
            "rotation": self.grid_rotation_spinbox,
            "offset_x": self.grid_offset_x_spinbox,
            "offset_y": self.grid_offset_y_spinbox,
            "hint": self.grid_tool_hint,
            "apply": self.grid_apply_button,
            "float": self.grid_float_button,
            "cancel": self.grid_cancel_button,
        }

    def sync_circle_tool_panel(self, radius, is_edit=False):
        controls = self.current_circle_controls() if is_edit else {
            "radius": self.circle_radius_spinbox,
            "offset_x": self.circle_offset_x_spinbox,
            "offset_y": self.circle_offset_y_spinbox,
        }
        if is_edit:
            self.edit_circle_cell_id_spinbox.blockSignals(True)
        controls["radius"].blockSignals(True)
        controls["offset_x"].blockSignals(True)
        controls["offset_y"].blockSignals(True)
        if is_edit:
            target_item = self.current_single_edit_target_item()
            if target_item is not None:
                self.edit_circle_cell_id_spinbox.setValue(int(target_item.cell_id))
                self.edit_circle_cell_id_spinbox.setEnabled(True)
            else:
                self.edit_circle_cell_id_spinbox.setValue(0)
                self.edit_circle_cell_id_spinbox.setEnabled(False)
            radius_delta = 0.0 if abs(float(self.edit_single_radius_delta)) < 1e-9 else float(self.edit_single_radius_delta)
            controls["radius"].setValue(radius_delta)
            controls["offset_x"].setValue(float(self.preview_offset_x))
            controls["offset_y"].setValue(float(self.preview_offset_y))
        else:
            controls["radius"].setValue(float(radius))
            absolute_coordinates = self.current_preview_absolute_coordinates()
            if absolute_coordinates is None:
                display_x = float(self.preview_offset_x)
                display_y = float(self.preview_offset_y)
            else:
                display_x, display_y = absolute_coordinates
            controls["offset_x"].setValue(display_x)
            controls["offset_y"].setValue(display_y)
        if is_edit:
            self.edit_circle_cell_id_spinbox.blockSignals(False)
        controls["radius"].blockSignals(False)
        controls["offset_x"].blockSignals(False)
        controls["offset_y"].blockSignals(False)

    def sync_grid_tool_panel(self, is_edit=False):
        controls = self.current_grid_controls() if is_edit else {
            "rows": self.grid_rows_spinbox,
            "cols": self.grid_columns_spinbox,
            "radius": self.grid_radius_spinbox,
            "hpitch": self.grid_hpitch_spinbox,
            "vpitch": self.grid_vpitch_spinbox,
            "rotation": self.grid_rotation_spinbox,
            "offset_x": self.grid_offset_x_spinbox,
            "offset_y": self.grid_offset_y_spinbox,
        }
        if controls["rows"] is not None:
            controls["rows"].blockSignals(True)
        if controls["cols"] is not None:
            controls["cols"].blockSignals(True)
        controls["radius"].blockSignals(True)
        controls["hpitch"].blockSignals(True)
        controls["vpitch"].blockSignals(True)
        controls["rotation"].blockSignals(True)
        controls["offset_x"].blockSignals(True)
        controls["offset_y"].blockSignals(True)
        if controls["rows"] is not None:
            controls["rows"].setValue(int(self.grid_rows))
        if controls["cols"] is not None:
            controls["cols"].setValue(int(self.grid_columns))
        if is_edit:
            radius_delta = 0.0 if abs(float(self.edit_group_radius_delta)) < 1e-9 else float(self.edit_group_radius_delta)
            hpitch_delta = 0.0 if abs(float(self.edit_group_horizontal_pitch_delta)) < 1e-9 else float(self.edit_group_horizontal_pitch_delta)
            vpitch_delta = 0.0 if abs(float(self.edit_group_vertical_pitch_delta)) < 1e-9 else float(self.edit_group_vertical_pitch_delta)
            rotation_delta = 0.0 if abs(float(self.edit_group_rotation_delta)) < 1e-9 else float(self.edit_group_rotation_delta)
            controls["radius"].setValue(radius_delta)
            controls["hpitch"].setValue(hpitch_delta)
            controls["vpitch"].setValue(vpitch_delta)
            controls["rotation"].setValue(rotation_delta)
        else:
            controls["radius"].setValue(float(self.circle_radius))
            controls["hpitch"].setValue(float(self.grid_horizontal_pitch))
            controls["vpitch"].setValue(float(self.grid_vertical_pitch))
            controls["rotation"].setValue(float(self.grid_rotation_degrees))
            absolute_coordinates = self.current_preview_absolute_coordinates()
            if absolute_coordinates is None:
                display_x = float(self.preview_offset_x)
                display_y = float(self.preview_offset_y)
            else:
                display_x, display_y = absolute_coordinates
            controls["offset_x"].setValue(display_x)
            controls["offset_y"].setValue(display_y)
        if is_edit:
            controls["offset_x"].setValue(float(self.preview_offset_x))
            controls["offset_y"].setValue(float(self.preview_offset_y))
        if controls["rows"] is not None:
            controls["rows"].blockSignals(False)
        if controls["cols"] is not None:
            controls["cols"].blockSignals(False)
        controls["radius"].blockSignals(False)
        controls["hpitch"].blockSignals(False)
        controls["vpitch"].blockSignals(False)
        controls["rotation"].blockSignals(False)
        controls["offset_x"].blockSignals(False)
        controls["offset_y"].blockSignals(False)

    def sync_active_preview_coordinate_controls(self):
        if not hasattr(self, "tool_options_stack"):
            return

        if self.cell_controller.is_group_edit_mode():
            self.sync_grid_tool_panel(is_edit=True)
            return

        if self.tool_mode == "select":
            self.sync_circle_tool_panel(radius=self.circle_radius, is_edit=False)
        elif self.tool_mode == "grid":
            self.sync_grid_tool_panel(is_edit=False)
        elif self.tool_mode == "edit-new":
            self.sync_circle_tool_panel(radius=0.0, is_edit=True)

    def handle_circle_radius_spinbox_changed(self, value):
        sender = self.sender()
        if sender is self.edit_circle_radius_spinbox:
            self.edit_single_radius_delta = float(value)
            base_radius = float(self.edit_single_base_radius if self.edit_single_base_radius is not None else self.circle_radius)
            self.circle_radius = max(1.0, base_radius + self.edit_single_radius_delta)
        else:
            self.circle_radius = float(value)
        self.updateRadiusTextbox()
        if self.tool_mode in {'select', 'edit-new'}:
            if self.cell_controller.uses_grid_preview():
                self.update_grid_preview()
        elif self.cell_controller.uses_grid_preview():
            self.update_grid_preview()

    def handle_grid_radius_change(self, value):
        sender = self.sender()
        if sender is self.edit_grid_radius_spinbox:
            self.edit_group_radius_delta = float(value)
            base_radius = float(self.edit_group_base_radius if self.edit_group_base_radius is not None else self.circle_radius)
            self.circle_radius = max(1.0, base_radius + self.edit_group_radius_delta)
        else:
            self.circle_radius = float(value)
        self.updateRadiusTextbox()
        self.handle_grid_parameter_change()

    def handle_preview_offset_change(self, *_args):
        current_widget = self.tool_options_stack.currentWidget()
        if current_widget == self.circle_tool_page:
            self.set_preview_absolute_coordinates(
                float(self.circle_offset_x_spinbox.value()),
                float(self.circle_offset_y_spinbox.value()),
            )
        elif current_widget == self.edit_circle_tool_page:
            self.preview_offset_x = float(self.edit_circle_offset_x_spinbox.value())
            self.preview_offset_y = float(self.edit_circle_offset_y_spinbox.value())
        else:
            controls = self.current_grid_controls()
            if current_widget == self.grid_tool_page:
                self.set_preview_absolute_coordinates(
                    float(controls["offset_x"].value()),
                    float(controls["offset_y"].value()),
                )
            else:
                self.preview_offset_x = float(controls["offset_x"].value())
                self.preview_offset_y = float(controls["offset_y"].value())
        if self.cell_controller.uses_grid_preview():
            self.update_grid_preview()

    def handle_grid_parameter_change(self, *_args):
        controls = self.current_grid_controls()
        if controls["rows"] is not None:
            self.grid_rows = controls["rows"].value()
        if controls["cols"] is not None:
            self.grid_columns = controls["cols"].value()
        if self.cell_controller.is_group_edit_mode():
            self.edit_group_horizontal_pitch_delta = float(controls["hpitch"].value())
            self.edit_group_vertical_pitch_delta = float(controls["vpitch"].value())
            self.edit_group_rotation_delta = float(controls["rotation"].value())
            base_hpitch = float(self.edit_group_base_horizontal_pitch if self.edit_group_base_horizontal_pitch is not None else self.grid_horizontal_pitch)
            base_vpitch = float(self.edit_group_base_vertical_pitch if self.edit_group_base_vertical_pitch is not None else self.grid_vertical_pitch)
            base_rotation = float(self.edit_group_base_rotation_degrees if self.edit_group_base_rotation_degrees is not None else self.grid_rotation_degrees)
            self.grid_horizontal_pitch = max(0.1, base_hpitch + self.edit_group_horizontal_pitch_delta)
            self.grid_vertical_pitch = max(0.1, base_vpitch + self.edit_group_vertical_pitch_delta)
            self.grid_rotation_degrees = max(-180.0, min(180.0, base_rotation + self.edit_group_rotation_delta))
        else:
            self.grid_horizontal_pitch = float(controls["hpitch"].value())
            self.grid_vertical_pitch = float(controls["vpitch"].value())
            self.grid_rotation_degrees = float(controls["rotation"].value())
        if self.cell_controller.uses_grid_preview():
            self.update_grid_preview()

    def clear_grid_preview(self):
        # Thin wrapper kept on the main window because the view/event code
        # already calls this name in several places.
        self.cell_controller.clear_preview()

    def cancel_grid_preview(self):
        self.cell_controller.cancel_preview()

    def float_grid_preview(self):
        self.cell_controller.float_preview()

    def update_grid_preview_from_scene_pos(self, scene_pos, pin=False):
        self.cell_controller.update_preview_from_scene_pos(scene_pos, pin)

    def get_grid_preview_definitions(self):
        return self.cell_controller.get_preview_definitions()

    def update_grid_preview(self):
        self.cell_controller.update_preview()

    def update_grid_apply_state(self):
        self.cell_controller.update_grid_panel_state()

    def handle_grid_apply_action(self):
        self.cell_controller.handle_grid_apply_action()

    def handle_circle_apply_action(self):
        self.cell_controller.handle_circle_apply_action()

    def focus_is_text_entry_widget(self):
        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return False
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QAbstractSpinBox)):
            return True
        if isinstance(focus_widget, QComboBox) and focus_widget.isEditable():
            return True
        parent = focus_widget.parentWidget()
        while parent is not None:
            if isinstance(parent, (QLineEdit, QTextEdit, QAbstractSpinBox)):
                return True
            if isinstance(parent, QComboBox) and parent.isEditable():
                return True
            parent = parent.parentWidget()
        return False

    def focus_is_tool_options_editor(self):
        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return False
        if not self.focus_widget_is_within(
            focus_widget,
            [
                getattr(self, "tool_options_widget", None),
                getattr(self, "tool_options_dock", None),
            ],
        ):
            return False
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QAbstractSpinBox)):
            return True
        if isinstance(focus_widget, QComboBox) and focus_widget.isEditable():
            return True
        parent = focus_widget.parentWidget()
        while parent is not None:
            if isinstance(parent, (QLineEdit, QTextEdit, QAbstractSpinBox)):
                return True
            if isinstance(parent, QComboBox) and parent.isEditable():
                return True
            parent = parent.parentWidget()
        return False

    def focus_widget_is_within(self, focus_widget, roots):
        if focus_widget is None:
            return False
        valid_roots = [root for root in roots if root is not None]
        current = focus_widget
        while current is not None:
            if any(current is root for root in valid_roots):
                return True
            current = current.parentWidget()
        return False

    def focus_allows_preview_shortcut(self):
        if not self.cell_controller.uses_grid_preview():
            return False

        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return True
        if self.focus_is_text_entry_widget() and not self.focus_is_tool_options_editor():
            return False
        return True

    def confirm_active_preview(self):
        if not self.cell_controller.uses_grid_preview():
            return False
        if self.grid_preview_floating and not self.cell_controller.pin_current_preview(log_change=False):
            return False
        if self.cell_controller.is_single_preview_mode():
            self.handle_circle_apply_action()
        else:
            self.handle_grid_apply_action()
        return True

    def handle_preview_confirm_shortcut(self):
        if not self.focus_allows_preview_shortcut():
            return
        self.confirm_active_preview()

    def handle_circle_float_action(self):
        if self.cell_controller.uses_grid_preview():
            self.float_grid_preview()

    def handle_circle_cancel_action(self):
        self.cell_controller.handle_circle_cancel_action()

    def handle_preview_cancel_shortcut(self):
        if not self.focus_allows_preview_shortcut():
            return
        if self.cell_controller.is_single_preview_mode():
            self.handle_circle_cancel_action()
        else:
            self.handle_grid_cancel_action()

    def handle_grid_float_action(self):
        if self.cell_controller.uses_grid_preview():
            self.float_grid_preview()

    def handle_grid_cancel_action(self):
        self.cell_controller.handle_grid_cancel_action()

    def get_selected_cell_items(self):
        return self.cell_controller.selected_scene_items()

    def delete_selected_cells(self):
        cell_ids = self.cell_controller.selected_scene_cell_ids()
        if not cell_ids:
            return False

        before_state = self.capture_cell_state(include_analysis=True)
        removed_cell_ids = sorted(set(cell_ids))
        removed_id_set = set(removed_cell_ids)
        kept_items = [
            item for item in self.cell_items
            if item.cell_id not in removed_id_set
        ]

        if len(kept_items) == len(self.cell_items):
            return False

        self.cell_items = kept_items
        self.cell_controller.redraw_current_cells(preserve_selection=False)
        self.delete_cell_items_to_keyframes(removed_cell_ids)
        self.prune_analysis_results_for_deleted_cells(removed_cell_ids)
        self.ensure_cell_registry_matches_scene_cells()
        self.recompute_next_cell_id(preserve_if_larger=False)
        self.refresh_cells_panel()
        joined_numbers = ", ".join(str(number) for number in removed_cell_ids)
        label = "cell" if len(removed_cell_ids) == 1 else "cells"
        self.log(f"Delete {label} {joined_numbers}")
        self.push_cell_history("Delete Cells", before_state, include_analysis=True)
        self.apply_cursor_tool_ui()
        self.refresh_grayscale_plot()
        return True

    def get_edit_target_items(self):
        return self.cell_controller.get_target_items()

    def infer_grid_parameters_from_cells(self, selected_items):
        self.cell_controller.infer_grid_parameters_from_cells(selected_items)

    def handle_scene_cell_selection_changed(self):
        if hasattr(self, "tool_options_stack"):
            self.sync_tool_options_panel()
        self.sync_cells_panel_selection()
        self.refresh_grayscale_plot()
        self.request_image_edit_histogram_refresh()

    def reselect_cell_ids(self, cell_ids, sync_tool_panel=True):
        # Scene items are rebuilt whenever circles are re-anchored/redrawn, so we
        # restore selection by stable cell_id instead of holding stale
        # item references.
        number_set = set(cell_ids)
        current_selected = {
            item.cell_id
            for item in self.scene.selectedItems()
            if isinstance(item, CellCircle)
        }
        if current_selected == number_set:
            if sync_tool_panel:
                self.sync_tool_options_panel()
            return
        scene_blocker = QSignalBlocker(self.scene)
        try:
            for item in self.scene.items():
                if isinstance(item, CellCircle):
                    item.setSelected(item.cell_id in number_set)
        finally:
            del scene_blocker
        if sync_tool_panel:
            self.handle_scene_cell_selection_changed()

    def apply_grid_preview(self):
        self.cell_controller.apply_grid_add()

    def show_sample_catalog_manager(self):
        if not hasattr(self, "sample_catalog_dock") or self.sample_catalog_dock is None:
            return
        self.refresh_sample_catalog_table(preserve_selection=False)
        self.show_dock_widget(self.sample_catalog_dock)

    def zoom_window(self):
        self.showMaximized()
        self.log("Zoom Window")

    def restore_window(self):
        self.showNormal()
        self.log("Restore Window")

    def create_dock_widget(self, title, widget, object_name):
        dock_widget = QDockWidget(title, self)
        dock_widget.setObjectName(object_name)
        if isinstance(widget, QFrame):
            widget.setFrameShape(QFrame.NoFrame)
            widget.setLineWidth(0)
        content_container = QWidget(dock_widget)
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(widget)
        dock_widget._content_widget = widget
        dock_widget.setWidget(content_container)
        dock_widget.setFeatures(
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
        dock_widget.setStyleSheet("QDockWidget { border: none; }")
        dock_widget.setTitleBarWidget(DockTitleBar(dock_widget, title, dock_widget))
        return dock_widget

    def show_dock_widget(self, dock_widget):
        if dock_widget is None or (not shiboken6.isValid(dock_widget)):
            return
        dock_widget.show()
        dock_widget.raise_()
        child_widget = getattr(dock_widget, "_content_widget", dock_widget.widget())
        if child_widget is not None and shiboken6.isValid(child_widget):
            child_widget.setFocus(Qt.OtherFocusReason)

    def store_default_dock_state(self):
        self.default_dock_state = self.saveState()

    def reset_panel_layout(self):
        if self.default_dock_state is not None:
            self.restoreState(self.default_dock_state)
            if self.tool_options_dock is not None and shiboken6.isValid(self.tool_options_dock):
                self.tool_options_dock.raise_()

    def get_slider_handle_rect(self, slider):
        if slider is None:
            return QRectF()
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        handle_rect = slider.style().subControlRect(
            QStyle.CC_Slider,
            option,
            QStyle.SC_SliderHandle,
            slider,
        )
        return QRectF(handle_rect)

    def reset_image_edit_slider_to_default(self, slider):
        if slider is getattr(self, "image_edit_exposure_slider", None):
            self.begin_image_edit_history("Reset Exposure")
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            self.apply_image_edit_state(
                self.compose_image_edit_state(exposure=0.0),
                invalidate_results=True,
                refresh_display=True,
                sync_controls=True,
            )
            self.commit_image_edit_history("Reset Exposure")
            return True
        if slider is getattr(self, "image_edit_contrast_slider", None):
            self.begin_image_edit_history("Reset Contrast")
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            self.apply_image_edit_state(
                self.compose_image_edit_state(contrast=0.0),
                invalidate_results=True,
                refresh_display=True,
                sync_controls=True,
            )
            self.commit_image_edit_history("Reset Contrast")
            return True
        return False

    def eventFilter(self, watched, event):
        if watched is getattr(self, "cursor_freeze_lineedit", None):
            if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if getattr(self, "cursor_freeze_apply_button", None) is not None:
                    self.cursor_freeze_apply_button.animateClick()
                else:
                    self.apply_cursor_freeze_frames_edit()
                event.accept()
                return True
        elif watched in (self.image_list_widget, self.image_list_widget.viewport()):
            if event.type() in (QEvent.FocusIn, QEvent.MouseButtonPress):
                self.set_active_image_panel("list")
            if event.type() == QEvent.KeyPress:
                if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                    self.remove_selected_list_images()
                    event.accept()
                    return True
                if event.key() == Qt.Key_Space:
                    self.keyPressEvent(event)
                    event.accept()
                    return True
            if event.type() == QEvent.KeyRelease:
                if event.key() == Qt.Key_Space:
                    self.keyReleaseEvent(event)
                    event.accept()
                    return True
        elif watched in (
            self.image_slider,
            self.zoom_slider,
            getattr(self, "image_edit_exposure_slider", None),
            getattr(self, "image_edit_contrast_slider", None),
            self.grayscale_plot_widget,
            self.grayscale_plot_widget.plot_widget,
        ):
            if watched in (
                getattr(self, "image_edit_exposure_slider", None),
                getattr(self, "image_edit_contrast_slider", None),
            ):
                if event.type() == QEvent.Wheel:
                    event.accept()
                    return True
                if (
                    event.type() == QEvent.MouseButtonDblClick
                    and event.button() == Qt.LeftButton
                    and self.get_slider_handle_rect(watched).contains(event.position())
                ):
                    if self.reset_image_edit_slider_to_default(watched):
                        event.accept()
                        return True
            if event.type() == QEvent.KeyPress and self.handle_frame_navigation_shortcut(event.key()):
                event.accept()
                return True

        return super().eventFilter(watched, event)

    def setup_table_widget(self, table_widget):
        table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        table_widget.setAlternatingRowColors(True)
        table_widget.verticalHeader().setVisible(True)
        table_widget.horizontalHeader().setStretchLastSection(False)
        table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

    def set_table_data(self, table_widget, headers, rows):
        table_widget.setUpdatesEnabled(False)
        table_widget.clear()
        table_widget.setRowCount(0)
        table_widget.setColumnCount(0)

        if not headers:
            table_widget.setUpdatesEnabled(True)
            return

        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        table_widget.setRowCount(len(rows))
        table_widget.setVerticalHeaderLabels([str(index) for index in range(len(rows))])

        for row_index, row_values in enumerate(rows):
            for col_index, value in enumerate(row_values):
                item = QTableWidgetItem("" if value is None else str(value))
                table_widget.setItem(row_index, col_index, item)

        if len(headers) <= 12 and len(rows) <= 300:
            table_widget.resizeColumnsToContents()
        else:
            table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table_widget.horizontalHeader().setStretchLastSection(False)
        table_widget.setUpdatesEnabled(True)

    def update_results_tables(self):
        self.sync_cell_analysis_from_results()
        self.set_table_data(self.data_table, self.grayscale_results_headers, self.grayscale_results_rows)
        self.set_table_data(self.freeze_table, self.freeze_results_headers, self.freeze_results_rows)
        self.update_results_table_visibility()
        self.refresh_grayscale_plot()
        self.refresh_cells_panel()

    def update_temperature_sync_table(self):
        if hasattr(self, "temperature_sync_table"):
            self.set_table_data(self.temperature_sync_table, self.temperature_sync_headers, self.temperature_sync_rows)
        self.update_results_table_visibility()

    def update_results_table_visibility(self):
        if hasattr(self, "results_table_tabs"):
            grayscale_visible = bool(self.grayscale_results_headers)
            freeze_visible = bool(self.freeze_results_headers)
            temperature_visible = bool(self.temperature_sync_headers)
            self.results_table_tabs.setTabVisible(0, grayscale_visible)
            self.results_table_tabs.setTabVisible(1, freeze_visible)
            self.results_table_tabs.setTabVisible(2, temperature_visible)
            visible_count = int(grayscale_visible) + int(freeze_visible) + int(temperature_visible)
            current_index = self.results_table_tabs.currentIndex()
            if current_index < 0 or not self.results_table_tabs.isTabVisible(current_index):
                for index in range(self.results_table_tabs.count()):
                    if self.results_table_tabs.isTabVisible(index):
                        self.results_table_tabs.setCurrentIndex(index)
                        break
            if hasattr(self, "results_tables_dock") and self.results_tables_dock is not None:
                if visible_count == 0:
                    self.results_tables_dock.hide()

    def set_temperature_sync_results(self, headers, rows, summary=None):
        self.temperature_sync_headers = [str(value) for value in (headers or [])]
        self.temperature_sync_rows = [
            ["" if value is None else str(value) for value in row]
            for row in (rows or [])
        ]
        self.temperature_sync_summary = dict(summary or {})
        self.update_temperature_sync_table()
        if self.temperature_sync_headers:
            if hasattr(self, "results_table_tabs"):
                self.results_table_tabs.setCurrentIndex(2)
            self.show_dock_widget(self.results_tables_dock)
        self.update_session_actions_state()

    def invalidate_temperature_sync_results(self, reason=None):
        had_results = bool(self.temperature_sync_headers or self.temperature_sync_rows)
        self.temperature_sync_headers = []
        self.temperature_sync_rows = []
        self.temperature_sync_summary = {}
        self.last_temperature_import_path = None
        self.update_temperature_sync_table()
        self.update_session_actions_state()
        if had_results and reason:
            self.log(f"Temperature sync cleared: {reason}. Re-import the temperature data file.")

    def invalidate_analysis_results(self, reason=None):
        had_results = bool(
            self.grayscale_results_headers
            or self.grayscale_results_rows
            or self.freeze_results_headers
            or self.freeze_results_rows
        )
        self.last_grayscale_output_path = None
        self.last_freeze_output_path = None
        self.grayscale_results_headers = []
        self.grayscale_results_rows = []
        self.freeze_results_headers = []
        self.freeze_results_rows = []
        self.clear_cell_analysis()
        self.update_results_tables()
        self.invalidate_temperature_sync_results("analysis results changed")
        if had_results and reason:
            self.log(f"Analysis cleared: {reason}. Run Analysis again.")

    def get_plot_target_cell_ids(self):
        selected_cell_ids = [item.cell_id for item in self.get_selected_cell_items()]
        if selected_cell_ids:
            return sorted(set(selected_cell_ids))

        edit_target_numbers = [item.cell_id for item in self.get_edit_target_items()]
        if edit_target_numbers:
            return sorted(set(edit_target_numbers))

        return []

    def refresh_grayscale_plot(self):
        if not hasattr(self, "grayscale_plot_widget"):
            return
        self.grayscale_plot_widget.update_plot_data(
            self.grayscale_results_headers,
            self.grayscale_results_rows,
            self.freeze_results_rows,
            self.get_plot_target_cell_ids(),
            self.get_plot_current_image_index(),
            self.freeze_finder_tail_extend_points,
            self.convolution_half_window_points,
            self.convolution_ramp_points,
            self.timeseries_palette,
            self.timeseries_trace_line_width,
            self.timeseries_convolution_line_width,
            self.get_qcolor(self.timeseries_freeze_line_color).getRgb(),
            self.timeseries_freeze_line_width,
            self.get_qcolor(self.timeseries_current_frame_color).getRgb(),
            self.timeseries_current_frame_line_width,
        )

    def grayscale_plot_is_visible(self):
        plot_widget = getattr(self, "grayscale_plot_widget", None)
        if plot_widget is None:
            return False
        plot_dock = getattr(self, "grayscale_plot_dock", None)
        if plot_dock is not None:
            try:
                return bool(plot_dock.isVisible())
            except RuntimeError:
                return False
        return bool(plot_widget.isVisible())

    def update_grayscale_plot_current_frame(self):
        if not hasattr(self, "grayscale_plot_widget"):
            return
        if not self.grayscale_plot_is_visible():
            return
        self.grayscale_plot_widget.set_current_image_index(self.get_plot_current_image_index())

    def get_plot_current_image_index(self):
        if self.pending_preview_image_index is not None:
            return self.pending_preview_image_index
        if self.imagePaths and (0 <= self.image_index < len(self.imagePaths)):
            return self.image_index
        return None

    def capture_session_state(self):
        return {
            "session_metadata": copy.deepcopy(self.serialize_session_metadata()),
            "image_edit_state": copy.deepcopy(self.serialize_image_edit_state()),
            "cell_items": copy.deepcopy(self.cell_items),
            "next_cell_id": int(getattr(self, "next_cell_id", 0)),
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "sample_catalog": copy.deepcopy(self.serialize_sample_catalog()),
            "next_sample_id": int(getattr(self, "next_sample_id", 0)),
            "keyframe_list": self.keyframe_list.copy(),
            "flagframe_list": self.flagframe_list.copy(),
            "keyframe_cell_items_dict": copy.deepcopy(self.keyframe_cell_items_dict),
            "image_width": self.image_width,
            "imagePaths": self.imagePaths.copy(),
            "imageNames": self.imageNames.copy(),
            "image_index": self.image_index,
            "image_list_entry_ids": self.image_list_entry_ids.copy(),
            "next_image_list_entry_id": self.next_image_list_entry_id,
            "sort_mode": self.sort_mode,
            "last_grayscale_output_path": self.last_grayscale_output_path,
            "last_freeze_output_path": self.last_freeze_output_path,
            "grayscale_results_headers": self.grayscale_results_headers.copy(),
            "grayscale_results_rows": copy.deepcopy(self.grayscale_results_rows),
            "freeze_results_headers": self.freeze_results_headers.copy(),
            "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def capture_cell_state(self, include_analysis=False):
        state = {
            "cell_items": copy.deepcopy(self.cell_items),
            "next_cell_id": int(getattr(self, "next_cell_id", 0)),
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "sample_catalog": copy.deepcopy(self.serialize_sample_catalog()),
            "next_sample_id": int(getattr(self, "next_sample_id", 0)),
            "keyframe_list": self.keyframe_list.copy(),
            "flagframe_list": self.flagframe_list.copy(),
            "keyframe_cell_items_dict": copy.deepcopy(self.keyframe_cell_items_dict),
            "image_index": self.image_index,
            "tool_mode": getattr(self, "tool_mode", "cursor"),
            "last_temperature_import_path": self.last_temperature_import_path,
            "last_temperature_calibration_path": self.last_temperature_calibration_path,
            "last_temperature_reset_temperature": self.last_temperature_reset_temperature,
            "temperature_sync_headers": self.temperature_sync_headers.copy(),
            "temperature_sync_rows": copy.deepcopy(self.temperature_sync_rows),
            "temperature_sync_summary": dict(self.temperature_sync_summary),
        }
        if include_analysis:
            state.update({
                "last_grayscale_output_path": self.last_grayscale_output_path,
                "last_freeze_output_path": self.last_freeze_output_path,
                "grayscale_results_headers": self.grayscale_results_headers.copy(),
                "grayscale_results_rows": copy.deepcopy(self.grayscale_results_rows),
                "freeze_results_headers": self.freeze_results_headers.copy(),
                "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            })
        return state

    def capture_data_state(self):
        return {
            "image_edit_state": copy.deepcopy(self.serialize_image_edit_state()),
            "next_cell_id": int(getattr(self, "next_cell_id", 0)),
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "sample_catalog": copy.deepcopy(self.serialize_sample_catalog()),
            "next_sample_id": int(getattr(self, "next_sample_id", 0)),
            "last_grayscale_output_path": self.last_grayscale_output_path,
            "last_freeze_output_path": self.last_freeze_output_path,
            "last_temperature_import_path": self.last_temperature_import_path,
            "last_temperature_calibration_path": self.last_temperature_calibration_path,
            "last_temperature_reset_temperature": self.last_temperature_reset_temperature,
            "grayscale_results_headers": self.grayscale_results_headers.copy(),
            "grayscale_results_rows": copy.deepcopy(self.grayscale_results_rows),
            "freeze_results_headers": self.freeze_results_headers.copy(),
            "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            "temperature_sync_headers": self.temperature_sync_headers.copy(),
            "temperature_sync_rows": copy.deepcopy(self.temperature_sync_rows),
            "temperature_sync_summary": dict(self.temperature_sync_summary),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def capture_image_edit_history_state(self):
        return {
            "image_edit_state": copy.deepcopy(self.serialize_image_edit_state()),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def capture_image_session_state(self):
        return {
            "image_edit_state": copy.deepcopy(self.serialize_image_edit_state()),
            "cell_items": copy.deepcopy(self.cell_items),
            "next_cell_id": int(getattr(self, "next_cell_id", 0)),
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "sample_catalog": copy.deepcopy(self.serialize_sample_catalog()),
            "next_sample_id": int(getattr(self, "next_sample_id", 0)),
            "keyframe_list": self.keyframe_list.copy(),
            "flagframe_list": self.flagframe_list.copy(),
            "keyframe_cell_items_dict": copy.deepcopy(self.keyframe_cell_items_dict),
            "imagePaths": self.imagePaths.copy(),
            "imageNames": self.imageNames.copy(),
            "image_index": self.image_index,
            "image_list_entry_ids": self.image_list_entry_ids.copy(),
            "next_image_list_entry_id": self.next_image_list_entry_id,
            "sort_mode": self.sort_mode,
            "last_grayscale_output_path": self.last_grayscale_output_path,
            "last_freeze_output_path": self.last_freeze_output_path,
            "grayscale_results_headers": self.grayscale_results_headers.copy(),
            "grayscale_results_rows": copy.deepcopy(self.grayscale_results_rows),
            "freeze_results_headers": self.freeze_results_headers.copy(),
            "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def capture_loaded_images_state(self):
        return {
            "image_edit_state": copy.deepcopy(self.serialize_image_edit_state()),
            "next_cell_id": int(getattr(self, "next_cell_id", 0)),
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "sample_catalog": copy.deepcopy(self.serialize_sample_catalog()),
            "next_sample_id": int(getattr(self, "next_sample_id", 0)),
            "imagePaths": self.imagePaths.copy(),
            "imageNames": self.imageNames.copy(),
            "image_index": self.image_index,
            "image_list_entry_ids": self.image_list_entry_ids.copy(),
            "next_image_list_entry_id": self.next_image_list_entry_id,
            "sort_mode": self.sort_mode,
            "last_grayscale_output_path": self.last_grayscale_output_path,
            "last_freeze_output_path": self.last_freeze_output_path,
            "grayscale_results_headers": self.grayscale_results_headers.copy(),
            "grayscale_results_rows": copy.deepcopy(self.grayscale_results_rows),
            "freeze_results_headers": self.freeze_results_headers.copy(),
            "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def get_active_tool_for_restore(self):
        """Return the user-facing tool to preserve across undo/redo.

        Undo/redo should revert data changes, not unexpectedly switch the user
        to whatever tool happened to be active when the command was created.
        """
        previous_edit_mode = self.temporary_event_data.get("previous_edit_mode")
        if self.cell_controller.is_any_edit_mode() or previous_edit_mode in ["edit-choose", "edit-new", "edit-group"]:
            # In-progress edit is transient interaction state. Undo/redo should
            # cancel that interaction and act on the last committed command.
            return "cursor"
        return getattr(self, "tool_mode", "cursor")

    def cancel_transient_history_state(self):
        """Clear unfinished interaction state before undo/redo.

        Preview/edit state is not itself an undoable command. If the user hits
        undo/redo mid-edit, we should discard the transient interaction first
        and then apply the history command to committed state only.
        """
        previous_edit_mode = self.temporary_event_data.get("previous_edit_mode")
        if self.cell_controller.uses_grid_preview():
            self.cell_controller.cancel_preview(log_message=False)
        elif self.cell_controller.is_any_edit_mode() or previous_edit_mode in ["edit-choose", "edit-new", "edit-group"]:
            self.cancel_edit_state()
            self.tool_mode = "cursor"
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
            self.set_view_cursor_shape(Qt.ArrowCursor)
            self.set_tools_highlight(self.tool_mode)
            self.update_cell_items_selectable_state()
            self.tool_status_label.setText('Select / Move')
            self.sync_tool_options_panel()

    def restore_tool_mode_ui(self, restored_tool_mode=None):
        """Reapply cursor/drag/action state after undo/redo restores data."""
        restored_tool_mode = restored_tool_mode or getattr(self, "tool_mode", "cursor")

        if not self.imagePaths:
            self.tool_mode = "cursor"
            self.grid_preview_origin_pixels = None
            self.grid_preview_floating = True
            self.cell_controller.clear_preview()
            self.set_tools_highlight(self.tool_mode)
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
            self.set_view_cursor_shape(Qt.ArrowCursor)
            self.tool_status_label.setText('Select / Move')
            self.update_cell_items_selectable_state()
            self.sync_tool_options_panel()
            return

        if restored_tool_mode in ["edit", "edit-choose", "edit-new", "edit-group"]:
            self.temporary_event_data["previous_edit_mode"] = restored_tool_mode
            self.editTool(self.edit_tool_action.isChecked())
        elif restored_tool_mode == "pan":
            self.pan_tool_action.trigger()
        elif restored_tool_mode == "image-edit":
            self.image_edit_action.trigger()
        elif restored_tool_mode == "select":
            self.select_tool_action.trigger()
        elif restored_tool_mode == "grid":
            self.grid_tool_action.trigger()
        elif restored_tool_mode == "deselect":
            self.deselect_tool_action.trigger()
        else:
            self.reset_cursor_action.trigger()

    def restore_image_session_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.invalidate_temperature_sync_results()
            self.clear_image_caches()
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            current_image_paths = self.imagePaths.copy()
            current_current_path = self.imagePaths[self.image_index] if self.imagePaths and 0 <= self.image_index < len(self.imagePaths) else None
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False

            self.cell_items = copy.deepcopy(state["cell_items"])
            self.next_cell_id = int(state.get("next_cell_id", getattr(self, "next_cell_id", 0)))
            self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", {}))
            self.sample_catalog = self.deserialize_sample_catalog(
                state.get("sample_catalog", self.serialize_sample_catalog())
            )
            try:
                self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
            except (TypeError, ValueError):
                self.next_sample_id = int(getattr(self, "next_sample_id", 0))
            self.keyframe_list = state["keyframe_list"].copy()
            self.flagframe_list = state["flagframe_list"].copy()
            self.keyframe_cell_items_dict = copy.deepcopy(state["keyframe_cell_items_dict"])
            self.imagePaths = state["imagePaths"].copy()
            self.imageNames = state["imageNames"].copy()
            self.image_index = state["image_index"]
            self.last_committed_image_index = int(self.image_index)
            self.image_list_entry_ids = state["image_list_entry_ids"].copy()
            self.next_image_list_entry_id = state["next_image_list_entry_id"]
            self.sort_mode = state.get("sort_mode", self.sort_mode)
            self.apply_image_edit_state(
                state.get("image_edit_state", self.serialize_image_edit_state()),
                invalidate_results=False,
                refresh_display=False,
                sync_controls=False,
            )
            self.last_grayscale_output_path = state.get("last_grayscale_output_path")
            self.last_freeze_output_path = state.get("last_freeze_output_path")
            self.grayscale_results_headers = state.get("grayscale_results_headers", []).copy()
            self.grayscale_results_rows = copy.deepcopy(state.get("grayscale_results_rows", []))
            self.freeze_results_headers = state.get("freeze_results_headers", []).copy()
            self.freeze_results_rows = copy.deepcopy(state.get("freeze_results_rows", []))
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()

            self.update_results_tables()
            self.refresh_sample_catalog_table(preserve_selection=False)

            image_set_changed = current_image_paths != self.imagePaths
            new_current_path = self.imagePaths[self.image_index] if self.imagePaths and 0 <= self.image_index < len(self.imagePaths) else None

            if self.imagePaths:
                self.image_slider.blockSignals(True)
                self.image_slider.setEnabled(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(len(self.imagePaths) - 1)
                self.image_slider.setValue(self.image_index)
                self.image_slider.blockSignals(False)
                self.image_slider.keyframes = set(self.keyframe_list)
                self.image_slider.flaggedframes = set(self.flagframe_list)
                self.image_slider.update()
                self.image_textbox.setText(str(self.image_index))

                self.select_tool_action.setEnabled(True)
                self.grid_tool_action.setEnabled(True)
                self.pan_tool_action.setEnabled(True)
                self.deselect_tool_action.setEnabled(True)
                self.edit_tool_action.setEnabled(True)

                if image_set_changed:
                    self.populate_image_list()
                else:
                    self.update_image_list_annotations()
                    self.sync_image_list_selection()

                if current_current_path != new_current_path or not hasattr(self, 'pixmap_item'):
                    self.updateImage(self.image_index)
                    self.finalize_frame_update(self.image_index)
                else:
                    self.cell_controller.redraw_current_cells(preserve_selection=False, force_scene_scan=True)
                    self.image_name_label.setText(self.imageNames[self.image_index])
                    self.resize_image_textbox()
                    self.updateButtonStates()
                    self.update_toggle_keyframe_button_icon()
                    self.update_toggle_flagging_button_icon()
                    self.sync_image_list_selection()
            else:
                self.populate_image_list()
                self.reset_transient_interaction_state()
                self.scene.clear()
                if hasattr(self, 'pixmap_item'):
                    del(self.pixmap_item)
                self.image_name_label.clear()
                self.image_textbox.clear()
                self.image_slider.blockSignals(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(0)
                self.image_slider.setValue(0)
                self.image_slider.blockSignals(False)
                self.image_slider.setEnabled(False)
                self.image_slider.keyframes = set()
                self.image_slider.flaggedframes = set()
                self.image_slider.update()
                self.sync_image_list_selection()
                self.select_tool_action.setEnabled(False)
                self.grid_tool_action.setEnabled(False)
                self.pan_tool_action.setEnabled(False)
                self.deselect_tool_action.setEnabled(False)
                self.edit_tool_action.setEnabled(False)

            self.update_session_actions_state()
            self.updateButtonStates()
            self.image_slider.set_custom_ticks()
            self.zoom_slider_set_maximum()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_loaded_images_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.invalidate_temperature_sync_results()
            self.clear_image_caches()
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            current_image_paths = self.imagePaths.copy()
            current_current_path = self.imagePaths[self.image_index] if self.imagePaths and 0 <= self.image_index < len(self.imagePaths) else None
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False

            self.imagePaths = state["imagePaths"].copy()
            self.imageNames = state["imageNames"].copy()
            self.image_index = state["image_index"]
            self.last_committed_image_index = int(self.image_index)
            self.next_cell_id = int(state.get("next_cell_id", getattr(self, "next_cell_id", 0)))
            self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", self.serialize_cell_records()))
            self.sample_catalog = self.deserialize_sample_catalog(
                state.get("sample_catalog", self.serialize_sample_catalog())
            )
            try:
                self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
            except (TypeError, ValueError):
                self.next_sample_id = int(getattr(self, "next_sample_id", 0))
            self.image_list_entry_ids = state["image_list_entry_ids"].copy()
            self.next_image_list_entry_id = state["next_image_list_entry_id"]
            self.sort_mode = state.get("sort_mode", self.sort_mode)
            self.apply_image_edit_state(
                state.get("image_edit_state", self.serialize_image_edit_state()),
                invalidate_results=False,
                refresh_display=False,
                sync_controls=False,
            )
            self.last_grayscale_output_path = state.get("last_grayscale_output_path")
            self.last_freeze_output_path = state.get("last_freeze_output_path")
            self.grayscale_results_headers = state.get("grayscale_results_headers", []).copy()
            self.grayscale_results_rows = copy.deepcopy(state.get("grayscale_results_rows", []))
            self.freeze_results_headers = state.get("freeze_results_headers", []).copy()
            self.freeze_results_rows = copy.deepcopy(state.get("freeze_results_rows", []))
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()

            self.update_results_tables()
            self.refresh_sample_catalog_table(preserve_selection=False)

            image_set_changed = current_image_paths != self.imagePaths
            new_current_path = self.imagePaths[self.image_index] if self.imagePaths and 0 <= self.image_index < len(self.imagePaths) else None

            if self.imagePaths:
                self.image_slider.blockSignals(True)
                self.image_slider.setEnabled(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(len(self.imagePaths) - 1)
                self.image_slider.setValue(self.image_index)
                self.image_slider.blockSignals(False)
                self.image_slider.keyframes = set(self.keyframe_list)
                self.image_slider.flaggedframes = set(self.flagframe_list)
                self.image_slider.update()
                self.image_textbox.setText(str(self.image_index))

                self.select_tool_action.setEnabled(True)
                self.grid_tool_action.setEnabled(True)
                self.pan_tool_action.setEnabled(True)
                self.deselect_tool_action.setEnabled(True)
                self.edit_tool_action.setEnabled(True)

                if image_set_changed:
                    self.populate_image_list()
                else:
                    self.update_image_list_annotations()
                    self.sync_image_list_selection()

                if current_current_path != new_current_path or not hasattr(self, 'pixmap_item'):
                    self.updateImage(self.image_index)
                    self.finalize_frame_update(self.image_index)
                else:
                    self.image_name_label.setText(self.imageNames[self.image_index])
                    self.resize_image_textbox()
                    self.updateButtonStates()
                    self.update_toggle_keyframe_button_icon()
                    self.update_toggle_flagging_button_icon()
                    self.sync_image_list_selection()
            else:
                self.populate_image_list()
                self.reset_transient_interaction_state()
                self.scene.clear()
                if hasattr(self, 'pixmap_item'):
                    del(self.pixmap_item)
                self.image_name_label.clear()
                self.image_textbox.clear()
                self.image_slider.blockSignals(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(0)
                self.image_slider.setValue(0)
                self.image_slider.blockSignals(False)
                self.image_slider.setEnabled(False)
                self.image_slider.keyframes = set()
                self.image_slider.flaggedframes = set()
                self.image_slider.update()
                self.sync_image_list_selection()
                self.select_tool_action.setEnabled(False)
                self.grid_tool_action.setEnabled(False)
                self.pan_tool_action.setEnabled(False)
                self.deselect_tool_action.setEnabled(False)
                self.edit_tool_action.setEnabled(False)

            self.update_session_actions_state()
            self.updateButtonStates()
            self.image_slider.set_custom_ticks()
            self.zoom_slider_set_maximum()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_session_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.invalidate_temperature_sync_results()
            self.clear_image_caches()
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            self.session_active = True
            if "console_history" in state and hasattr(self, "terminal"):
                self.terminal.setPlainText(state["console_history"])
            self.apply_session_metadata(state.get("session_metadata", self.serialize_session_metadata()))

            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", "cursor")
            current_image_paths = self.imagePaths.copy()
            current_image_names = self.imageNames.copy()
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False
            self.cell_items = copy.deepcopy(state["cell_items"])
            self.next_cell_id = int(state.get("next_cell_id", getattr(self, "next_cell_id", 0)))
            self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", {}))
            self.sample_catalog = self.deserialize_sample_catalog(
                state.get("sample_catalog", self.serialize_sample_catalog())
            )
            try:
                self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
            except (TypeError, ValueError):
                self.next_sample_id = int(getattr(self, "next_sample_id", 0))
            self.keyframe_list = state["keyframe_list"].copy()
            self.flagframe_list = state["flagframe_list"].copy()
            self.keyframe_cell_items_dict = copy.deepcopy(state["keyframe_cell_items_dict"])
            self.image_width = state["image_width"]
            self.imagePaths = state["imagePaths"].copy()
            self.imageNames = state["imageNames"].copy()
            self.image_index = state["image_index"]
            self.last_committed_image_index = int(self.image_index)
            self.image_list_entry_ids = state.get("image_list_entry_ids", list(range(len(self.imagePaths))))
            self.next_image_list_entry_id = state.get("next_image_list_entry_id", len(self.image_list_entry_ids))
            self.sort_mode = state.get("sort_mode", self.sort_mode)
            self.apply_image_edit_state(
                state.get("image_edit_state", self.serialize_image_edit_state()),
                invalidate_results=False,
                refresh_display=False,
                sync_controls=False,
            )
            self.last_grayscale_output_path = state["last_grayscale_output_path"]
            self.last_freeze_output_path = state["last_freeze_output_path"]
            self.last_temperature_import_path = state.get("last_temperature_import_path")
            self.last_temperature_calibration_path = state.get("last_temperature_calibration_path")
            self.last_temperature_reset_temperature = state.get("last_temperature_reset_temperature")
            self.grayscale_results_headers = state["grayscale_results_headers"].copy()
            self.grayscale_results_rows = copy.deepcopy(state["grayscale_results_rows"])
            self.freeze_results_headers = state["freeze_results_headers"].copy()
            self.freeze_results_rows = copy.deepcopy(state["freeze_results_rows"])
            self.temperature_sync_headers = state.get("temperature_sync_headers", []).copy()
            self.temperature_sync_rows = copy.deepcopy(state.get("temperature_sync_rows", []))
            self.temperature_sync_summary = dict(state.get("temperature_sync_summary", {}))
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()

            self.update_results_tables()
            self.update_temperature_sync_table()
            self.refresh_sample_catalog_table(preserve_selection=False)

            image_set_changed = (
                current_image_paths != self.imagePaths or
                current_image_names != self.imageNames
            )

            if self.imagePaths:
                self.image_slider.blockSignals(True)
                self.image_slider.setEnabled(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(len(self.imagePaths) - 1)
                self.image_slider.setValue(self.image_index)
                self.image_slider.blockSignals(False)
                self.image_slider.keyframes = set(self.keyframe_list)
                self.image_slider.flaggedframes = set(self.flagframe_list)
                self.image_slider.update()
                self.image_textbox.setText(str(self.image_index))

                self.select_tool_action.setEnabled(True)
                self.grid_tool_action.setEnabled(True)
                self.pan_tool_action.setEnabled(True)
                self.deselect_tool_action.setEnabled(True)
                self.edit_tool_action.setEnabled(True)

                if image_set_changed:
                    self.populate_image_list()
                else:
                    self.update_image_list_annotations()
                    self.sync_image_list_selection()
                self.updateImage(self.image_index)
                self.finalize_frame_update(self.image_index)
            else:
                self.populate_image_list()
                self.image_slider.blockSignals(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(0)
                self.image_slider.setValue(0)
                self.image_slider.blockSignals(False)
                self.image_slider.setEnabled(False)
                self.image_slider.keyframes = set()
                self.image_slider.flaggedframes = set()
                self.image_slider.update()
                self.image_textbox.clear()
                self.image_name_label.clear()
                self.reset_transient_interaction_state()
                self.scene.clear()
                if hasattr(self, 'pixmap_item'):
                    del(self.pixmap_item)
                self.sync_image_list_selection()

                self.select_tool_action.setEnabled(False)
                self.grid_tool_action.setEnabled(False)
                self.pan_tool_action.setEnabled(False)
                self.deselect_tool_action.setEnabled(False)
                self.edit_tool_action.setEnabled(False)

            self.update_session_actions_state()
            self.updateButtonStates()
            self.image_slider.set_custom_ticks()
            self.zoom_slider_set_maximum()
            self.update_toggle_keyframe_button_icon()
            self.update_toggle_flagging_button_icon()
            if self.temperature_sync_headers:
                if hasattr(self, "results_table_tabs"):
                    self.results_table_tabs.setCurrentIndex(2)
                self.show_dock_widget(self.results_tables_dock)

            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_cell_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False

            if not self.imagePaths:
                self.cell_items = []
                self.rendered_cell_items = []
                self.next_cell_id = int(state.get("next_cell_id", 0))
                self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", {}))
                self.sample_catalog = self.deserialize_sample_catalog(
                    state.get("sample_catalog", self.serialize_sample_catalog())
                )
                try:
                    self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
                except (TypeError, ValueError):
                    self.next_sample_id = int(getattr(self, "next_sample_id", 0))
                self.keyframe_list = []
                self.flagframe_list = []
                self.keyframe_cell_items_dict = {}
                self.recompute_next_cell_id(preserve_if_larger=True)
                self.ensure_sample_catalog_matches_cell_records()
                self.refresh_sample_catalog_table(preserve_selection=False)
                self.restore_tool_mode_ui(restore_tool_mode)
                return

            frame_count = len(self.imagePaths)
            restored_keyframes = sorted(
                frame
                for frame in state.get("keyframe_list", [])
                if isinstance(frame, int) and 0 <= frame < frame_count
            )
            restored_flagframes = sorted(
                frame
                for frame in state.get("flagframe_list", [])
                if isinstance(frame, int) and 0 <= frame < frame_count
            )
            restored_keyframe_dict = {
                frame: copy.deepcopy(items)
                for frame, items in state.get("keyframe_cell_items_dict", {}).items()
                if isinstance(frame, int) and 0 <= frame < frame_count
            }

            self.cell_items = copy.deepcopy(state.get("cell_items", []))
            self.next_cell_id = int(state.get("next_cell_id", getattr(self, "next_cell_id", 0)))
            self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", {}))
            self.sample_catalog = self.deserialize_sample_catalog(
                state.get("sample_catalog", self.serialize_sample_catalog())
            )
            try:
                self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
            except (TypeError, ValueError):
                self.next_sample_id = int(getattr(self, "next_sample_id", 0))
            self.keyframe_list = restored_keyframes
            self.flagframe_list = restored_flagframes
            self.keyframe_cell_items_dict = restored_keyframe_dict
            has_analysis_payload = any(
                key in state
                for key in (
                    "last_grayscale_output_path",
                    "last_freeze_output_path",
                    "grayscale_results_headers",
                    "grayscale_results_rows",
                    "freeze_results_headers",
                    "freeze_results_rows",
                )
            )
            has_temperature_sync_payload = any(
                key in state
                for key in (
                    "last_temperature_import_path",
                    "last_temperature_calibration_path",
                    "last_temperature_reset_temperature",
                    "temperature_sync_headers",
                    "temperature_sync_rows",
                    "temperature_sync_summary",
                )
            )
            if has_analysis_payload:
                self.last_grayscale_output_path = state.get("last_grayscale_output_path", self.last_grayscale_output_path)
                self.last_freeze_output_path = state.get("last_freeze_output_path", self.last_freeze_output_path)
                self.grayscale_results_headers = state.get("grayscale_results_headers", self.grayscale_results_headers).copy()
                self.grayscale_results_rows = copy.deepcopy(state.get("grayscale_results_rows", self.grayscale_results_rows))
                self.freeze_results_headers = state.get("freeze_results_headers", self.freeze_results_headers).copy()
                self.freeze_results_rows = copy.deepcopy(state.get("freeze_results_rows", self.freeze_results_rows))
            if has_temperature_sync_payload:
                self.last_temperature_import_path = state.get("last_temperature_import_path")
                self.last_temperature_calibration_path = state.get("last_temperature_calibration_path")
                self.last_temperature_reset_temperature = state.get("last_temperature_reset_temperature")
                self.temperature_sync_headers = state.get("temperature_sync_headers", []).copy()
                self.temperature_sync_rows = copy.deepcopy(state.get("temperature_sync_rows", []))
                self.temperature_sync_summary = dict(state.get("temperature_sync_summary", {}))
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()
            if has_analysis_payload:
                self.update_results_tables()
            if has_temperature_sync_payload:
                self.update_temperature_sync_table()

            target_index = state.get("image_index", self.image_index)
            if not isinstance(target_index, int):
                target_index = self.image_index
            target_index = max(0, min(target_index, frame_count - 1))

            self.ensure_slider_window_contains_index(target_index)
            self.image_slider.blockSignals(True)
            self.image_slider.setValue(target_index)
            self.image_slider.blockSignals(False)
            self.image_slider.keyframes = set(self.keyframe_list)
            self.image_slider.flaggedframes = set(self.flagframe_list)
            self.image_slider.update()
            self.update_image_list_annotations()

            if target_index != self.image_index:
                self.updateImage(target_index, preview=False)
                self.finalize_frame_update(target_index)
            else:
                self.cell_controller.redraw_current_cells(preserve_selection=False)
                self.finalize_frame_update(target_index)

            if not has_analysis_payload:
                self.refresh_grayscale_plot()
            self.refresh_sample_catalog_table(preserve_selection=False)
            self.update_session_actions_state()
            self.updateButtonStates()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_data_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            self.apply_image_edit_state(state.get("image_edit_state", self.serialize_image_edit_state()), invalidate_results=False, refresh_display=False, sync_controls=False)
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False

            self.last_grayscale_output_path = state.get("last_grayscale_output_path")
            self.last_freeze_output_path = state.get("last_freeze_output_path")
            self.last_temperature_import_path = state.get("last_temperature_import_path")
            self.last_temperature_calibration_path = state.get("last_temperature_calibration_path")
            self.last_temperature_reset_temperature = state.get("last_temperature_reset_temperature")
            self.grayscale_results_headers = state.get("grayscale_results_headers", []).copy()
            self.grayscale_results_rows = copy.deepcopy(state.get("grayscale_results_rows", []))
            self.freeze_results_headers = state.get("freeze_results_headers", []).copy()
            self.freeze_results_rows = copy.deepcopy(state.get("freeze_results_rows", []))
            self.temperature_sync_headers = state.get("temperature_sync_headers", []).copy()
            self.temperature_sync_rows = copy.deepcopy(state.get("temperature_sync_rows", []))
            self.temperature_sync_summary = dict(state.get("temperature_sync_summary", {}))
            self.next_cell_id = int(state.get("next_cell_id", getattr(self, "next_cell_id", 0)))
            self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", self.serialize_cell_records()))
            self.sample_catalog = self.deserialize_sample_catalog(
                state.get("sample_catalog", self.serialize_sample_catalog())
            )
            try:
                self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
            except (TypeError, ValueError):
                self.next_sample_id = int(getattr(self, "next_sample_id", 0))
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()
            self.update_results_tables()
            self.update_temperature_sync_table()
            self.refresh_sample_catalog_table(preserve_selection=False)
            self.update_session_actions_state()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_image_edit_history_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            self.apply_image_edit_state(
                state.get("image_edit_state", self.serialize_image_edit_state()),
                invalidate_results=False,
                refresh_display=True,
                sync_controls=True,
            )
            self.update_session_actions_state()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_navigation_index(self, index, preserve_active_tool=False):
        self.history_restoring = True
        try:
            if not self.imagePaths:
                return

            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else getattr(self, "tool_mode", "cursor")
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False

            target_index = max(0, min(int(index), len(self.imagePaths) - 1))
            if target_index == self.image_index:
                self.finalize_frame_update(target_index)
            else:
                self.updateImage(target_index, preview=False)
                self.finalize_frame_update(target_index)
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def push_snapshot_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_session_state()
        self.undo_stack.push(SessionSnapshotCommand(self, text, before_state, after_state))

    def push_cell_history(self, text, before_state, include_analysis=False):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_cell_state(include_analysis=include_analysis)
        self.undo_stack.push(SessionCellCommand(self, text, before_state, after_state))

    def push_image_session_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_image_session_state()
        self.undo_stack.push(SessionImageListCommand(self, text, before_state, after_state))

    def push_loaded_images_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_loaded_images_state()
        self.undo_stack.push(SessionLoadedImagesCommand(self, text, before_state, after_state))

    def push_data_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_data_state()
        self.undo_stack.push(SessionDataCommand(self, text, before_state, after_state))

    def push_image_edit_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_image_edit_history_state()
        self.undo_stack.push(SessionImageEditCommand(self, text, before_state, after_state))

    def push_navigation_history(self, text, before_index, after_index):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return
        if before_index == after_index:
            return

        history_label = f"{text} ({before_index} -> {after_index})"
        self.undo_stack.push(FrameNavigationCommand(self, history_label, before_index, after_index))

    def format_image_list_entry(self, index):
        markers = []
        if index in self.keyframe_list:
            markers.append("K")
        if index in self.flagframe_list:
            markers.append("F")

        marker_text = f"[{' '.join(markers)}] " if markers else ""
        entry_id = self.image_list_entry_ids[index] if index < len(self.image_list_entry_ids) else index
        return f"{entry_id:06d} {marker_text}{self.imageNames[index]}"

    def populate_image_list(self):
        if not self.image_list_enabled:
            self.image_list_model.set_items([], [])
            return
        entries = [self.format_image_list_entry(index) for index in range(len(self.imagePaths))]
        self.image_list_model.set_items(entries, self.imagePaths)
        self.sync_image_list_selection()

    def update_image_list_annotations(self, rows=None):
        if not self.image_list_enabled:
            return
        if rows is None:
            rows = range(len(self.imageNames))

        row_data = {}
        for row in rows:
            if not (0 <= row < len(self.imageNames)):
                continue
            row_data[row] = (self.format_image_list_entry(row), self.imagePaths[row])

        self.image_list_model.update_items(row_data)

    def sync_image_list_selection(self):
        if not self.image_list_enabled:
            return
        selection_model = self.image_list_widget.selectionModel()
        if selection_model is None:
            return

        if not self.imagePaths or not (0 <= self.image_index < len(self.imagePaths)):
            self.syncing_image_list_selection = True
            try:
                selection_model.clearSelection()
                self.image_list_widget.setCurrentIndex(QModelIndex())
            finally:
                self.syncing_image_list_selection = False
            return

        model_index = self.image_list_model.index(self.image_index, 0)
        if not model_index.isValid():
            return

        self.syncing_image_list_selection = True
        try:
            selected_rows = [
                selected_index.row()
                for selected_index in selection_model.selectedRows(0)
                if selected_index.isValid()
            ]
            if len(selected_rows) <= 1:
                selection_model.setCurrentIndex(
                    model_index,
                    QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
                )
            else:
                selection_model.setCurrentIndex(model_index, QItemSelectionModel.NoUpdate)
            self.image_list_widget.setCurrentIndex(model_index)
        finally:
            self.syncing_image_list_selection = False

        if not self.image_slider.isSliderDown():
            visible_rect = self.image_list_widget.visualRect(model_index)
            if not visible_rect.isValid() or not self.image_list_widget.viewport().rect().contains(visible_rect.center()):
                self.image_list_widget.scrollTo(model_index, QListView.EnsureVisible)

    def handle_image_list_selection(self, index):
        if not self.image_list_enabled:
            return
        if self.syncing_image_list_selection:
            return

        modifiers = QGuiApplication.keyboardModifiers()
        if modifiers & (Qt.ControlModifier | Qt.ShiftModifier | Qt.MetaModifier):
            return

        row = index.row()
        if 0 <= row < len(self.imagePaths) and row != self.image_index:
            self.navigate_to_image(row)

    def handle_image_list_current_changed(self, current, previous):
        if not self.image_list_enabled:
            return
        if self.syncing_image_list_selection or not current.isValid():
            return
        self.handle_image_list_selection(current)

    def update_session_actions_state(self):
        session_active = bool(getattr(self, "session_active", False))
        has_images = session_active and bool(self.imagePaths)
        has_results = session_active and bool(
            self.grayscale_results_headers
            or self.freeze_results_headers
            or self.temperature_sync_headers
        )
        interactive = session_active and (not self.output_state)

        self.add_images_action.setEnabled(interactive)
        self.add_folder_action.setEnabled(interactive)
        self.remove_selected_action.setEnabled(self.image_list_enabled and has_images and not self.output_state)
        self.clear_images_action.setEnabled(has_images and not self.output_state)
        self.sort_images_action.setEnabled(has_images and not self.output_state)
        self.relink_images_action.setEnabled(has_images and not self.output_state)
        self.sample_manager_action.setEnabled(interactive)
        self.new_session_action.setEnabled(not self.output_state)
        self.open_session_action.setEnabled(not self.output_state)
        self.save_session_action.setEnabled(session_active and not self.output_state)
        self.save_session_as_action.setEnabled(session_active and not self.output_state)
        self.run_analysis_action.setEnabled(has_images and not self.output_state)
        self.output_results_action.setEnabled(has_results and not self.output_state)
        self.import_csu_is_dat_action.setEnabled(has_images and not self.output_state)
        self.import_tamu_linkam_xlsx_action.setEnabled(has_images and not self.output_state)
        self.viewer_single_action.setEnabled(interactive)
        self.viewer_double_action.setEnabled(interactive)
        self.viewer_triple_action.setEnabled(interactive)
        self.viewer_orientation_toggle_action.setEnabled(interactive and self.viewer_image_count in (2, 3))
        self.image_edit_action.setEnabled(has_images and not self.output_state)

        if session_active:
            self.set_undo_status()
            self.set_redo_status()
        else:
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)

        self.update_document_interface_state()

    def update_document_interface_state(self):
        session_active = bool(getattr(self, "session_active", False))
        has_images = session_active and bool(self.imagePaths)
        interactive_images = has_images and (not self.output_state)

        viewer_widget = getattr(self, "view_slider_widget", None)
        if viewer_widget is not None and shiboken6.isValid(viewer_widget):
            viewer_widget.setEnabled(session_active)

        for dock_name in (
            "image_list_dock",
            "tool_options_dock",
            "sample_catalog_dock",
            "cells_dock",
            "console_dock",
            "grayscale_plot_dock",
            "results_tables_dock",
        ):
            dock = getattr(self, dock_name, None)
            if dock is None or (not shiboken6.isValid(dock)):
                continue
            if (dock_name == "image_list_dock") and (not self.image_list_enabled):
                dock.setEnabled(False)
                toggle_action = dock.toggleViewAction()
                if toggle_action is not None:
                    toggle_action.setEnabled(False)
                continue
            dock.setEnabled(session_active)
            toggle_action = dock.toggleViewAction()
            if toggle_action is not None:
                toggle_action.setEnabled(session_active)

        for widget_name in (
            "radius_status_label",
            "zoom_status_label",
            "frame_status_label",
            "radius_textbox",
            "zoom_textbox",
            "image_textbox",
            "image_name_label",
            "tool_status_label",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setEnabled(interactive_images)

    def set_active_image_panel(self, panel_name):
        self.active_image_panel = panel_name

    def get_selected_image_rows(self):
        selection_model = self.image_list_widget.selectionModel()
        if selection_model is None:
            return []
        return sorted({
            model_index.row()
            for model_index in selection_model.selectedRows(0)
            if model_index.isValid()
        })

    def navigate_to_image(self, index, history_text="Change Frame"):
        if not self.imagePaths:
            return

        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        index = max(0, min(index, len(self.imagePaths) - 1))
        committed_index = max(
            0,
            min(int(getattr(self, "last_committed_image_index", self.image_index)), len(self.imagePaths) - 1),
        )
        if index == committed_index and not self.image_slider.isSliderDown():
            return

        if (
            not self.history_restoring
            and self.cell_controller.uses_grid_preview()
            and not (
                self.cell_controller.is_any_edit_mode()
                or self.temporary_event_data.get("previous_edit_mode") in ["edit-choose", "edit-new", "edit-group"]
            )
        ):
            self.cancel_unfinished_tool_workflow()

        if not self.history_restoring and self.pending_navigation_before_index is None:
            self.pending_navigation_before_index = committed_index
            self.pending_navigation_history_text = history_text

        self.ensure_slider_window_contains_index(index)
        self.image_slider.setValue(index)

    def commit_slider_release_navigation(self):
        if self.history_restoring or not self.imagePaths:
            return
        before_index = max(
            0,
            min(int(getattr(self, "last_committed_image_index", self.image_index)), len(self.imagePaths) - 1),
        )
        self.finalize_frame_update(self.image_index)
        if self.analysis_progress_navigation_suppressed:
            return
        if before_index != self.image_index:
            self.log(f"Change Frame: {before_index} -> {self.image_index}")
            self.push_navigation_history("Change Frame", before_index, self.image_index)

    def load_grayscale_results(self, file_path):
        try:
            with open(file_path, newline='') as csv_file:
                rows = list(csv.reader(csv_file))
        except OSError as err:
            self.log(f"Unable to load grayscale results table: {err}")
            return

        if len(rows) < 2:
            self.grayscale_results_headers = []
            self.grayscale_results_rows = []
        else:
            self.grayscale_results_headers = rows[1]
            self.grayscale_results_rows = rows[2:]

        self.update_results_tables()

    def set_freeze_results(self, headers, rows):
        self.freeze_results_headers = headers
        self.freeze_results_rows = rows
        self.update_results_tables()
        if self.freeze_results_headers:
            if hasattr(self, "results_table_tabs"):
                self.results_table_tabs.setCurrentIndex(1)
            self.show_dock_widget(self.results_tables_dock)
        self.invalidate_temperature_sync_results("freeze results changed")

    def build_temperature_sync_sample_groups(self, grouping_mode="samples"):
        self.ensure_cell_registry_matches_scene_cells()
        grouping_mode = str(grouping_mode or "samples").strip().casefold()
        if grouping_mode == "all_cells":
            all_cell_ids = []
            for cell_id in sorted(self.cell_records_by_id.keys()):
                if self.ensure_cell_record(cell_id) is None:
                    continue
                all_cell_ids.append(int(cell_id))
            if not all_cell_ids:
                return {}
            return {
                normalize_sample_name("All Cells"): {
                    "sample_name": "All Cells",
                    "cell_ids": all_cell_ids,
                    "total_cells": len(all_cell_ids),
                }
            }

        groups = {}
        for cell_id in sorted(self.cell_records_by_id.keys()):
            record = self.ensure_cell_record(cell_id)
            if record is None:
                continue
            sample_id = str(getattr(record, "sample_id", "")).strip()
            if not sample_id:
                continue
            sample_name = str(self.sample_name_for_id(sample_id)).strip()
            if not sample_name:
                continue
            normalized_name = normalize_sample_name(sample_name)
            if not normalized_name:
                continue
            group = groups.setdefault(
                normalized_name,
                {
                    "sample_name": sample_name,
                    "cell_ids": [],
                    "total_cells": 0,
                },
            )
            group["cell_ids"].append(int(cell_id))
            group["total_cells"] += 1
        return groups

    def build_temperature_sync_image_counts(self, sample_groups, count_mode="cumulative"):
        count_mode = str(count_mode or "cumulative").strip().casefold()
        image_counts_by_sample = {}
        for normalized_name, group in sample_groups.items():
            if count_mode == "state":
                state_counts = {}
                per_cell_events = []
                for cell_id in group["cell_ids"]:
                    record = self.ensure_cell_record(cell_id)
                    if record is None:
                        continue
                    resolved_frames = []
                    for frame_value in getattr(record, "freeze_event_indices", []):
                        try:
                            frame_index = int(frame_value)
                        except (TypeError, ValueError):
                            continue
                        if 0 <= frame_index < len(self.imageNames):
                            resolved_frames.append(frame_index)
                    per_cell_events.append(sorted(set(resolved_frames)))

                event_pointers = [0] * len(per_cell_events)
                cell_states = [0] * len(per_cell_events)
                for image_index in range(len(self.imageNames)):
                    frozen_count = 0
                    for cell_position, event_frames in enumerate(per_cell_events):
                        while event_pointers[cell_position] < len(event_frames) and event_frames[event_pointers[cell_position]] <= image_index:
                            cell_states[cell_position] = 1 - cell_states[cell_position]
                            event_pointers[cell_position] += 1
                        frozen_count += cell_states[cell_position]
                    state_counts[image_index] = int(frozen_count)
                image_counts_by_sample[normalized_name] = state_counts
                continue

            freeze_frames = []
            for cell_id in group["cell_ids"]:
                record = self.ensure_cell_record(cell_id)
                if record is None:
                    continue
                resolved_frames = []
                for frame_value in getattr(record, "freeze_event_indices", []):
                    try:
                        resolved_frames.append(int(frame_value))
                    except (TypeError, ValueError):
                        continue
                if resolved_frames:
                    freeze_frames.append(min(resolved_frames))
            freeze_frames.sort()
            cumulative_counts = {}
            freeze_pointer = 0
            for image_index in range(len(self.imageNames)):
                while freeze_pointer < len(freeze_frames) and freeze_frames[freeze_pointer] <= image_index:
                    freeze_pointer += 1
                cumulative_counts[image_index] = int(freeze_pointer)
            image_counts_by_sample[normalized_name] = cumulative_counts
        return image_counts_by_sample

    def build_tamu_temperature_sync_sample_groups(self):
        sample_groups = self.build_temperature_sync_sample_groups(grouping_mode="samples")
        if sample_groups:
            return sample_groups, "samples"
        sample_groups = self.build_temperature_sync_sample_groups(grouping_mode="all_cells")
        if sample_groups:
            return sample_groups, "all_cells"
        return {}, "samples"

    def normalize_temperature_reset_threshold(self, reset_temperature):
        if reset_temperature in (None, ""):
            return None
        try:
            return float(reset_temperature)
        except (TypeError, ValueError):
            return None

    def detect_cycle_start_indexes_from_temperatures(self, temperatures, reset_temperature):
        temperatures = np.asarray(temperatures, dtype=float)
        if temperatures.size == 0:
            return [0]
        threshold = self.normalize_temperature_reset_threshold(reset_temperature)
        if threshold is None:
            return [0]

        cycle_start_indexes = [0]
        # Require a meaningful warm-up from a below-threshold minimum before
        # starting a new cycle. This avoids tiny threshold jitter during a
        # cooling ramp from creating a false cycle boundary.
        warmup_hysteresis_c = max(
            0.0,
            float(getattr(self, "temperature_cycle_warmup_hysteresis_c", 0.02)),
        )
        previous_above = bool(np.isfinite(temperatures[0]) and temperatures[0] >= threshold)
        cool_segment_min = None
        if np.isfinite(temperatures[0]) and temperatures[0] < threshold:
            cool_segment_min = float(temperatures[0])
        for index in range(1, len(temperatures)):
            current_value = temperatures[index]
            current_finite = bool(np.isfinite(current_value))
            current_above = bool(current_finite and current_value >= threshold)
            if current_finite and (not current_above):
                if cool_segment_min is None:
                    cool_segment_min = float(current_value)
                else:
                    cool_segment_min = min(cool_segment_min, float(current_value))
            if current_above and (not previous_above):
                minimum_below_threshold = cool_segment_min
                if (
                    minimum_below_threshold is not None
                    and (float(current_value) - float(minimum_below_threshold)) >= warmup_hysteresis_c
                ):
                    cycle_start_indexes.append(index)
                cool_segment_min = None
            previous_above = current_above
        return cycle_start_indexes

    def build_cycle_ids_from_start_indexes(self, total_count, cycle_start_indexes):
        cycle_ids = []
        if total_count <= 0:
            return cycle_ids
        normalized_starts = sorted(
            set(
                int(index)
                for index in (cycle_start_indexes or [0])
                if 0 <= int(index) < total_count
            )
        )
        if not normalized_starts or normalized_starts[0] != 0:
            normalized_starts.insert(0, 0)
        current_cycle_id = 0
        next_start_pointer = 1
        for index in range(total_count):
            while next_start_pointer < len(normalized_starts) and index >= normalized_starts[next_start_pointer]:
                current_cycle_id += 1
                next_start_pointer += 1
            cycle_ids.append(int(current_cycle_id))
        return cycle_ids

    def cycle_index_for_position(self, position_value, cycle_start_positions):
        if position_value is None or not cycle_start_positions:
            return None
        index = int(np.searchsorted(np.asarray(cycle_start_positions, dtype=float), float(position_value), side="right") - 1)
        return max(0, index)

    def build_tamu_image_timing_context(self, parsed_trace, reset_temperature=None):
        trace_seconds = np.asarray(getattr(parsed_trace, "trace_seconds", []), dtype=float)
        trace_temperatures = np.asarray(getattr(parsed_trace, "trace_temperatures", []), dtype=float)
        cycle_start_indexes = self.detect_cycle_start_indexes_from_temperatures(
            trace_temperatures,
            reset_temperature,
        )
        cycle_start_seconds = [
            float(trace_seconds[index])
            for index in cycle_start_indexes
            if 0 <= int(index) < len(trace_seconds)
        ] or [0.0]
        start_timestamp = getattr(parsed_trace, "start_timestamp", None)
        image_elapsed_seconds = []
        image_cycle_ids = []
        parsed_image_count = 0
        unparsed_images = []
        for image_name in self.imageNames:
            basename = os.path.basename(str(image_name or ""))
            image_timestamp = parse_tamu_image_timestamp(basename)
            if image_timestamp is None or start_timestamp is None:
                image_elapsed_seconds.append(None)
                image_cycle_ids.append(None)
                if image_timestamp is None:
                    unparsed_images.append(basename)
                continue
            parsed_image_count += 1
            elapsed_seconds = float((image_timestamp - start_timestamp).total_seconds())
            image_elapsed_seconds.append(elapsed_seconds)
            image_cycle_ids.append(self.cycle_index_for_position(elapsed_seconds, cycle_start_seconds))
        return {
            "cycle_start_seconds": cycle_start_seconds,
            "cycle_start_indexes": cycle_start_indexes,
            "image_elapsed_seconds": image_elapsed_seconds,
            "image_cycle_ids": image_cycle_ids,
            "parsed_image_count": int(parsed_image_count),
            "unparsed_images": list(unparsed_images),
        }

    def build_tamu_cycle_reset_image_counts(self, sample_groups, image_cycle_ids):
        image_counts_by_sample = {}
        total_image_count = len(self.imageNames)
        for normalized_name, group in sample_groups.items():
            first_freeze_frame_by_cell_cycle = {}
            for cell_id in group["cell_ids"]:
                record = self.ensure_cell_record(cell_id)
                if record is None:
                    continue
                cycle_first_frames = {}
                resolved_frames = []
                for frame_value in getattr(record, "freeze_event_indices", []):
                    try:
                        frame_index = int(frame_value)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= frame_index < total_image_count:
                        resolved_frames.append(frame_index)
                for frame_index in sorted(set(resolved_frames)):
                    cycle_id = image_cycle_ids[frame_index] if frame_index < len(image_cycle_ids) else None
                    if cycle_id is None or cycle_id in cycle_first_frames:
                        continue
                    cycle_first_frames[cycle_id] = int(frame_index)
                first_freeze_frame_by_cell_cycle[int(cell_id)] = cycle_first_frames

            cycle_counts = {}
            for image_index in range(total_image_count):
                cycle_id = image_cycle_ids[image_index] if image_index < len(image_cycle_ids) else None
                frozen_count = 0
                for cycle_first_frames in first_freeze_frame_by_cell_cycle.values():
                    first_frame = cycle_first_frames.get(cycle_id)
                    if first_frame is not None and first_frame <= image_index:
                        frozen_count += 1
                cycle_counts[image_index] = int(frozen_count)
            image_counts_by_sample[normalized_name] = cycle_counts
        return image_counts_by_sample

    def reconcile_counts_by_cycle(self, raw_counts, anchor_counts, maximum_count, cycle_ids):
        raw_counts = [int(value) for value in raw_counts]
        if not raw_counts:
            return []
        if not cycle_ids or len(cycle_ids) != len(raw_counts):
            return reconcile_cumulative_counts(raw_counts, anchor_counts, maximum_count)

        corrected_counts = [0] * len(raw_counts)
        segment_start = 0
        while segment_start < len(raw_counts):
            cycle_id = cycle_ids[segment_start]
            segment_end = segment_start + 1
            while segment_end < len(raw_counts) and cycle_ids[segment_end] == cycle_id:
                segment_end += 1

            segment_raw = raw_counts[segment_start:segment_end]
            segment_anchors = {}
            for global_index, anchor_value in anchor_counts.items():
                if segment_start <= int(global_index) < segment_end:
                    segment_anchors[int(global_index) - segment_start] = int(anchor_value)

            segment_corrected = reconcile_cumulative_counts(
                segment_raw,
                segment_anchors,
                maximum_count,
            )
            corrected_counts[segment_start:segment_end] = segment_corrected
            segment_start = segment_end

        return corrected_counts

    def corrected_temperature_for_cell(self, measured_temperature, cell_id, calibration_by_well):
        if measured_temperature is None or calibration_by_well is None:
            return None
        try:
            calibration_entry = calibration_by_well.get(int(cell_id))
        except (TypeError, ValueError, AttributeError):
            calibration_entry = None
        if not calibration_entry:
            return None
        slope_value, intercept_value = calibration_entry
        try:
            slope_value = float(slope_value)
            intercept_value = float(intercept_value)
            if slope_value == 0:
                return None
            return (float(measured_temperature) - intercept_value) / slope_value
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    def corrected_temperature_for_group(self, measured_temperature, group, calibration_by_well):
        if measured_temperature is None or not calibration_by_well or not group:
            return None
        corrected_values = []
        for cell_id in group.get("cell_ids", []):
            corrected_value = self.corrected_temperature_for_cell(
                measured_temperature,
                cell_id,
                calibration_by_well,
            )
            if corrected_value is not None:
                corrected_values.append(float(corrected_value))
        if not corrected_values:
            return None
        return float(np.mean(corrected_values))

    def build_csu_temperature_sync_results(self, parsed_data, blank_sample_names=None, reset_temperature=None):
        sample_groups = self.build_temperature_sync_sample_groups()
        dat_sample_columns = list(parsed_data.get("sample_columns", []))
        dat_columns_by_name = {
            normalize_sample_name(column_name): column_name
            for column_name in dat_sample_columns
        }
        blank_name_set = {
            normalize_sample_name(sample_name)
            for sample_name in (blank_sample_names or [])
            if str(sample_name or "").strip()
        }

        matched_samples = []
        for dat_column in dat_sample_columns:
            normalized_name = normalize_sample_name(dat_column)
            group = sample_groups.get(normalized_name)
            if group is None:
                continue
            matched_samples.append({
                "normalized_name": normalized_name,
                "sample_name": group["sample_name"],
                "dat_column": dat_column,
                "total_cells": int(group["total_cells"]),
                "is_blank": normalized_name in blank_name_set,
            })

        unmatched_app_samples = sorted(
            group["sample_name"]
            for normalized_name, group in sample_groups.items()
            if normalized_name not in dat_columns_by_name
        )
        unmatched_dat_samples = sorted(
            column_name
            for normalized_name, column_name in dat_columns_by_name.items()
            if normalized_name not in sample_groups
        )
        unmatched_blank_samples = sorted(
            sample_name
            for sample_name in (blank_sample_names or [])
            if normalize_sample_name(sample_name) not in {
                sample["normalized_name"] for sample in matched_samples
            }
        )

        image_index_by_name = {
            os.path.basename(str(image_name)).casefold(): index
            for index, image_name in enumerate(self.imageNames)
        }
        parsed_rows = list(parsed_data.get("rows", []))
        row_temperatures = [
            np.nan if getattr(row, "avg_temp", None) is None else float(row.avg_temp)
            for row in parsed_rows
        ]
        row_cycle_start_indexes = self.detect_cycle_start_indexes_from_temperatures(
            row_temperatures,
            reset_temperature,
        )
        row_cycle_ids = self.build_cycle_ids_from_start_indexes(len(parsed_rows), row_cycle_start_indexes)
        image_cycle_ids = [None] * len(self.imageNames)
        picture_rows_matched = 0
        for row in parsed_rows:
            picture_name = os.path.basename(str(getattr(row, "picture_name", ""))).casefold()
            if picture_name and picture_name in image_index_by_name:
                picture_rows_matched += 1
                image_index = image_index_by_name[picture_name]
                image_cycle_ids[image_index] = row_cycle_ids[int(row.row_index)]

        image_counts_by_sample = self.build_tamu_cycle_reset_image_counts(sample_groups, image_cycle_ids)

        corrected_counts_by_sample = {}
        for sample in matched_samples:
            normalized_name = sample["normalized_name"]
            dat_column = sample["dat_column"]
            total_cells = int(sample["total_cells"])
            raw_counts = [
                int(getattr(row, "sample_counts", {}).get(dat_column, 0))
                for row in parsed_rows
            ]
            anchor_counts = {}
            image_counts = image_counts_by_sample.get(normalized_name, {})
            for row in parsed_rows:
                picture_name = os.path.basename(str(getattr(row, "picture_name", ""))).casefold()
                if not picture_name:
                    continue
                image_index = image_index_by_name.get(picture_name)
                if image_index is None:
                    continue
                anchor_counts[int(row.row_index)] = int(image_counts.get(image_index, 0))
            corrected_counts_by_sample[normalized_name] = self.reconcile_counts_by_cycle(
                raw_counts,
                anchor_counts,
                total_cells,
                row_cycle_ids,
            )

        blank_samples = [sample for sample in matched_samples if sample["is_blank"]]
        output_samples = [sample for sample in matched_samples if not sample["is_blank"]]
        blank_correction_by_row = []
        for row in parsed_rows:
            row_index = int(row.row_index)
            blank_correction = 0
            for blank_sample in blank_samples:
                counts = corrected_counts_by_sample.get(blank_sample["normalized_name"], [])
                if row_index < len(counts):
                    blank_correction += int(counts[row_index])
            blank_correction_by_row.append(int(blank_correction))

        headers = ["timestamp", "temperature_C", "cycle", "picture", "blank correction count"]
        for sample in output_samples:
            sample_name = str(sample["sample_name"])
            total_cells = int(sample["total_cells"])
            headers.append(f"{sample_name} (n={total_cells}) frozen count")

        rows = []
        for row in parsed_rows:
            row_index = int(row.row_index)
            blank_correction = blank_correction_by_row[row_index] if row_index < len(blank_correction_by_row) else 0
            output_row = [
                str(getattr(row, "timestamp_text", "") or ""),
                "" if getattr(row, "avg_temp", None) is None else f"{float(row.avg_temp):.3f}",
                str(int(row_cycle_ids[row_index])) if row_index < len(row_cycle_ids) else "0",
                str(getattr(row, "picture_name", "") or ""),
                str(int(blank_correction)),
            ]
            for sample in output_samples:
                normalized_name = sample["normalized_name"]
                total_cells = int(sample["total_cells"])
                sample_counts = corrected_counts_by_sample.get(normalized_name, [])
                frozen_value = sample_counts[row_index] if row_index < len(sample_counts) else 0
                adjusted_total = max(0, total_cells - int(blank_correction))
                adjusted_frozen = max(0, int(frozen_value) - int(blank_correction))
                adjusted_frozen = min(adjusted_frozen, adjusted_total)
                output_row.append(str(int(adjusted_frozen)))
            rows.append(output_row)

        summary = {
            "source_path": str(parsed_data.get("file_path", "")),
            "matched_samples": [sample["sample_name"] for sample in output_samples],
            "matched_blank_samples": [sample["sample_name"] for sample in blank_samples],
            "sample_total_cells": [
                {
                    "sample_name": str(sample["sample_name"]),
                    "total_cells": int(sample["total_cells"]),
                    "role": "blank" if bool(sample["is_blank"]) else "sample",
                }
                for sample in matched_samples
            ],
            "unmatched_app_samples": unmatched_app_samples,
            "unmatched_dat_samples": unmatched_dat_samples,
            "unmatched_blank_samples": unmatched_blank_samples,
            "matched_picture_rows": int(picture_rows_matched),
            "matched_sample_count": int(len(output_samples)),
            "total_picture_rows": int(sum(1 for row in parsed_rows if getattr(row, "picture_name", ""))),
            "cycle_count": int(max(row_cycle_ids) + 1) if row_cycle_ids else 1,
            "reset_temperature": self.normalize_temperature_reset_threshold(reset_temperature),
        }
        return headers, rows, summary

    def build_tamu_temperature_sync_results(self, parsed_trace, calibration_by_well=None, reset_temperature=None):
        sample_groups, grouping_mode = self.build_tamu_temperature_sync_sample_groups()
        timing_context = self.build_tamu_image_timing_context(parsed_trace, reset_temperature=reset_temperature)
        cycle_start_seconds = timing_context["cycle_start_seconds"]
        image_elapsed_seconds = timing_context["image_elapsed_seconds"]
        image_cycle_ids = timing_context["image_cycle_ids"]
        image_counts_by_sample = self.build_tamu_cycle_reset_image_counts(sample_groups, image_cycle_ids)
        output_samples = sorted(
            sample_groups.items(),
            key=lambda pair: str(pair[1].get("sample_name", "")).casefold(),
        )

        trace_seconds = np.asarray(list(getattr(parsed_trace, "trace_seconds", [])), dtype=float)
        trace_temperatures = np.asarray(list(getattr(parsed_trace, "trace_temperatures", [])), dtype=float)
        start_timestamp = getattr(parsed_trace, "start_timestamp", None)
        include_corrected_temperature = bool(calibration_by_well)

        calibrated_cell_ids = set()
        if calibration_by_well:
            for _, group in output_samples:
                for cell_id in group.get("cell_ids", []):
                    if int(cell_id) in calibration_by_well:
                        calibrated_cell_ids.add(int(cell_id))

        headers = ["timestamp", "temperature_C", "cycle", "image_name"]
        for _, group in output_samples:
            sample_name = str(group.get("sample_name", ""))
            total_cells = int(group.get("total_cells", 0))
            if include_corrected_temperature:
                headers.append(f"{sample_name} (n={total_cells}) corrected temperature_C")
            headers.append(f"{sample_name} (n={total_cells}) frozen count")

        rows = []
        in_range_image_count = 0
        out_of_range_image_count = 0
        for image_index, image_name in enumerate(self.imageNames):
            basename = os.path.basename(str(image_name or ""))
            image_timestamp = parse_tamu_image_timestamp(basename)
            raw_temperature = None
            elapsed_seconds = image_elapsed_seconds[image_index] if image_index < len(image_elapsed_seconds) else None
            if image_timestamp is not None and elapsed_seconds is not None:
                interpolated_temperature = np.interp(
                    elapsed_seconds,
                    trace_seconds,
                    trace_temperatures,
                    left=np.nan,
                    right=np.nan,
                )
                if np.isnan(interpolated_temperature):
                    out_of_range_image_count += 1
                else:
                    in_range_image_count += 1
                    raw_temperature = float(interpolated_temperature)

            output_row = [
                image_timestamp.isoformat(timespec="milliseconds") if image_timestamp is not None else "",
                "" if raw_temperature is None else f"{raw_temperature:.3f}",
                "" if image_cycle_ids[image_index] is None else str(int(image_cycle_ids[image_index])),
                basename,
            ]
            for normalized_name, group in output_samples:
                if include_corrected_temperature:
                    corrected_temperature = self.corrected_temperature_for_group(
                        raw_temperature,
                        group,
                        calibration_by_well,
                    )
                    output_row.append("" if corrected_temperature is None else f"{corrected_temperature:.3f}")
                frozen_count = image_counts_by_sample.get(normalized_name, {}).get(image_index, 0)
                output_row.append(str(int(frozen_count)))
            rows.append(output_row)

        summary = {
            "source_path": str(getattr(parsed_trace, "file_path", "")),
            "source_type": "tamu",
            "matched_samples": [group["sample_name"] for _, group in output_samples],
            "sample_total_cells": [
                {
                    "sample_name": str(group.get("sample_name", "")),
                    "total_cells": int(group.get("total_cells", 0)),
                    "role": "sample",
                }
                for _, group in output_samples
            ],
            "grouping_mode": str(grouping_mode),
            "count_mode": "cycle_reset",
            "trace_start_timestamp": str(getattr(parsed_trace, "start_timestamp_text", "") or ""),
            "trace_row_count": int(getattr(parsed_trace, "trace_row_count", 0) or 0),
            "sample_period_seconds": getattr(parsed_trace, "sample_period_seconds", None),
            "cycle_count": int(len(cycle_start_seconds)),
            "reset_temperature": self.normalize_temperature_reset_threshold(reset_temperature),
            "total_images": int(len(self.imageNames)),
            "parsed_image_count": int(timing_context["parsed_image_count"]),
            "in_range_image_count": int(in_range_image_count),
            "out_of_range_image_count": int(out_of_range_image_count),
            "unparsed_image_count": int(len(timing_context["unparsed_images"])),
            "unparsed_images_preview": list(timing_context["unparsed_images"][:5]),
            "calibration_path": "" if not calibration_by_well else str(getattr(self, "last_temperature_calibration_path", "") or ""),
            "calibrated_cell_count": int(len(calibrated_cell_ids)),
        }
        return headers, rows, summary

    def import_csu_is_dat(self, checked=False):
        if not self.imagePaths:
            QMessageBox.information(self, "CSU IS .dat import", "Load images before importing a CSU .dat file.")
            return

        available_sample_names = [
            str(sample_name)
            for _, sample_name in sorted(self.sample_catalog.items(), key=lambda pair: int(pair[0]))
            if str(sample_name).strip()
        ]
        dialog = CSUTemperatureImportDialog(
            self,
            self.last_temperature_import_path,
            available_sample_names,
            getattr(self, "last_temperature_reset_temperature", None),
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        dialog_values = dialog.get_values()
        file_path = dialog_values["file_path"]
        blank_sample_names = dialog_values["blank_sample_names"]
        reset_temperature = dialog_values["reset_temperature"]

        try:
            parsed_data = parse_csu_is_dat(file_path)
            headers, rows, summary = self.build_csu_temperature_sync_results(
                parsed_data,
                blank_sample_names=blank_sample_names,
                reset_temperature=reset_temperature,
            )
        except (OSError, TemperatureImportError) as err:
            QMessageBox.critical(self, "CSU IS .dat import", str(err))
            self.log(f"CSU IS .dat import failed: {err}")
            return

        self.last_temperature_import_path = str(file_path)
        self.last_temperature_reset_temperature = self.normalize_temperature_reset_threshold(reset_temperature)
        self.set_temperature_sync_results(headers, rows, summary)

        matched_samples = summary.get("matched_samples", [])
        matched_blank_samples = summary.get("matched_blank_samples", [])
        unmatched_app = summary.get("unmatched_app_samples", [])
        unmatched_dat = summary.get("unmatched_dat_samples", [])
        unmatched_blank = summary.get("unmatched_blank_samples", [])
        matched_picture_rows = int(summary.get("matched_picture_rows", 0))
        total_picture_rows = int(summary.get("total_picture_rows", 0))
        cycle_count = int(summary.get("cycle_count", 1))
        reset_temperature = summary.get("reset_temperature")

        message_lines = [
            f"Matched samples: {len(matched_samples)}",
            f"Matched picture rows: {matched_picture_rows}/{total_picture_rows}",
            f"Detected cycles: {cycle_count}",
        ]
        if reset_temperature is not None:
            message_lines.append(f"Reset threshold: {float(reset_temperature):.1f} °C")
        if matched_samples:
            message_lines.append("Matched sample names: " + ", ".join(matched_samples))
        if matched_blank_samples:
            message_lines.append("Blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_app:
            message_lines.append("No CSU column match for app sample(s): " + ", ".join(unmatched_app))
        if unmatched_dat:
            message_lines.append("No app sample match for CSU column(s): " + ", ".join(unmatched_dat))
        if unmatched_blank:
            message_lines.append("Selected blank sample(s) not matched to CSU columns: " + ", ".join(unmatched_blank))

        QMessageBox.information(self, "CSU IS .dat import", "\n".join(message_lines))
        self.log(f"Imported CSU IS .dat file: {file_path}")
        if matched_samples:
            self.log("CSU matched samples: " + ", ".join(matched_samples))
        if matched_blank_samples:
            self.log("CSU blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_app:
            self.log("CSU unmatched app samples: " + ", ".join(unmatched_app))
        if unmatched_dat:
            self.log("CSU unmatched .dat samples: " + ", ".join(unmatched_dat))
        if unmatched_blank:
            self.log("CSU unmatched selected blank samples: " + ", ".join(unmatched_blank))

    def import_tamu_linkam_xlsx(self, checked=False):
        if not self.imagePaths:
            QMessageBox.information(self, "TAMU Linkam .xlsx import", "Load images before importing a TAMU workbook.")
            return

        dialog = TAMUTemperatureImportDialog(
            self,
            self.last_temperature_import_path,
            getattr(self, "last_temperature_calibration_path", ""),
            getattr(self, "last_temperature_reset_temperature", None),
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        dialog_values = dialog.get_values()
        file_path = dialog_values["file_path"]
        calibration_path = dialog_values["calibration_path"]
        reset_temperature = dialog_values["reset_temperature"]

        try:
            parsed_trace = parse_tamu_linkam_xlsx(file_path)
            if getattr(parsed_trace, "start_timestamp", None) is None:
                raise TemperatureImportError("The selected TAMU workbook does not expose a usable absolute start timestamp.")
            calibration_by_well = None
            if calibration_path:
                calibration_by_well = parse_ice_array_calibration_csv(calibration_path)
            headers, rows, summary = self.build_tamu_temperature_sync_results(
                parsed_trace,
                calibration_by_well=calibration_by_well,
                reset_temperature=reset_temperature,
            )
        except (OSError, TemperatureImportError) as err:
            QMessageBox.critical(self, "TAMU Linkam .xlsx import", str(err))
            self.log(f"TAMU Linkam .xlsx import failed: {err}")
            return

        self.last_temperature_import_path = str(file_path)
        self.last_temperature_calibration_path = str(calibration_path or "")
        self.last_temperature_reset_temperature = self.normalize_temperature_reset_threshold(reset_temperature)
        self.set_temperature_sync_results(headers, rows, summary)

        matched_samples = summary.get("matched_samples", [])
        parsed_image_count = int(summary.get("parsed_image_count", 0))
        total_images = int(summary.get("total_images", 0))
        in_range_image_count = int(summary.get("in_range_image_count", 0))
        out_of_range_image_count = int(summary.get("out_of_range_image_count", 0))
        unparsed_image_count = int(summary.get("unparsed_image_count", 0))
        calibrated_cell_count = int(summary.get("calibrated_cell_count", 0))
        cycle_count = int(summary.get("cycle_count", 1))
        reset_temperature = summary.get("reset_temperature")
        grouping_mode = str(summary.get("grouping_mode", "samples"))
        grouping_label = "Current sample setup" if grouping_mode == "samples" else "No sample (all cells as one sample)"

        message_lines = [
            f"Grouping: {grouping_label}",
            f"Images with parsed timestamps: {parsed_image_count}/{total_images}",
            f"Images inside trace range: {in_range_image_count}/{total_images}",
            f"Trace start: {summary.get('trace_start_timestamp', '')}",
            f"Detected cooling cycles: {cycle_count}",
            "Frozen counts reset at each cycle. Within a cycle, a cell is counted after its first freeze event.",
        ]
        if reset_temperature is not None:
            message_lines.append(f"Reset threshold: {float(reset_temperature):.1f} °C")
        if matched_samples:
            message_lines.append("Output samples: " + ", ".join(matched_samples))
        if calibration_path:
            message_lines.append(f"Calibration applied to {calibrated_cell_count} cell(s).")
        if out_of_range_image_count:
            message_lines.append(f"Images outside the trace range: {out_of_range_image_count}")
        if unparsed_image_count:
            preview = ", ".join(summary.get("unparsed_images_preview", []))
            if preview:
                message_lines.append(f"Images with unparseable timestamps: {unparsed_image_count} ({preview})")
            else:
                message_lines.append(f"Images with unparseable timestamps: {unparsed_image_count}")

        QMessageBox.information(self, "TAMU Linkam .xlsx import", "\n".join(message_lines))
        self.log(f"Imported TAMU Linkam workbook: {file_path}")
        self.log(f"TAMU grouping mode: {grouping_label}")
        if matched_samples:
            self.log("TAMU output samples: " + ", ".join(matched_samples))
        if calibration_path:
            self.log(f"TAMU calibration applied to {calibrated_cell_count} cell(s): {calibration_path}")

    def export_grayscale_results_for_external_tool(self):
        if not self.grayscale_results_headers or not self.grayscale_results_rows:
            raise ValueError("No grayscale results available")

        image_folder = os.path.dirname(self.imagePaths[0]) if self.imagePaths else ""
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            prefix="icescopy_grayscale_",
            delete=False,
            newline="",
        )
        with temp_file as handle:
            handle.write(image_folder)
            handle.write("\n")
            writer = csv.writer(handle)
            writer.writerow(self.grayscale_results_headers)
            writer.writerows(self.grayscale_results_rows)
        return temp_file.name

    def write_csv_table(self, file_path, headers, rows):
        with open(file_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if headers:
                writer.writerow(headers)
            writer.writerows(rows)

    def write_temperature_sync_csv(self, file_path):
        summary = dict(self.temperature_sync_summary or {})
        sample_total_cells = list(summary.get("sample_total_cells", []) or [])

        with open(file_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)

            if sample_total_cells:
                writer.writerow(
                    ["sample_name"]
                    + [
                        str(entry.get("sample_name", "") or "")
                        for entry in sample_total_cells
                    ]
                )
                writer.writerow(
                    ["cell_number"]
                    + [
                        str(int(entry.get("total_cells", 0)))
                        for entry in sample_total_cells
                    ]
                )
                if any(str(entry.get("role", "sample") or "sample") != "sample" for entry in sample_total_cells):
                    writer.writerow(
                        ["sample_type"]
                        + [
                            str(entry.get("role", "sample") or "sample")
                            for entry in sample_total_cells
                        ]
                    )
                writer.writerow([])
            if self.temperature_sync_headers:
                writer.writerow(self.temperature_sync_headers)
            writer.writerows(self.temperature_sync_rows)

    def export_results_csv(self, checked=False):
        has_grayscale = bool(self.grayscale_results_headers)
        has_freeze = bool(self.freeze_results_headers)
        has_temperature_sync = bool(self.temperature_sync_headers)
        if not (has_grayscale or has_freeze or has_temperature_sync):
            QMessageBox.information(self, "Output Results", "No results available to export.")
            return

        dialog = OutputResultsDialog(
            self,
            include_grayscale=has_grayscale,
            include_freeze=has_freeze,
            include_temperature=has_temperature_sync,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        selected_exports = dialog.selected_exports()
        dialog.deleteLater()
        QApplication.processEvents()

        def choose_csv_path(title, default_name):
            file_dialog = QFileDialog(self, title)
            file_dialog.setAcceptMode(QFileDialog.AcceptSave)
            file_dialog.setFileMode(QFileDialog.AnyFile)
            file_dialog.setNameFilters(["CSV Files (*.csv)", "All Files (*)"])
            file_dialog.selectFile(default_name)
            file_dialog.setDefaultSuffix("csv")
            file_dialog.setOptions(self.file_dialog_options())
            if file_dialog.exec() != QDialog.Accepted:
                return ""
            selected_files = file_dialog.selectedFiles()
            path = selected_files[0] if selected_files else ""
            if path and not path.lower().endswith(".csv"):
                path = f"{path}.csv"
            return path

        def choose_output_directory():
            file_dialog = QFileDialog(self, "Choose Output Folder for Selected CSV Files")
            file_dialog.setFileMode(QFileDialog.Directory)
            file_dialog.setOption(QFileDialog.ShowDirsOnly, True)
            file_dialog.setOptions(self.file_dialog_options())
            if file_dialog.exec() != QDialog.Accepted:
                return ""
            selected_files = file_dialog.selectedFiles()
            return selected_files[0] if selected_files else ""

        export_targets = [
            (
                "grayscale",
                "Grayscale Measurements CSV",
                "grayscale_measurements.csv",
                self.grayscale_results_headers,
                self.grayscale_results_rows,
                "table",
            ),
            (
                "freeze",
                "Freeze Events CSV",
                "freeze_events.csv",
                self.freeze_results_headers,
                self.freeze_results_rows,
                "table",
            ),
            (
                "temperature",
                "Temperature Sync CSV",
                "temperature_sync.csv",
                self.temperature_sync_headers,
                self.temperature_sync_rows,
                "temperature",
            ),
        ]

        chosen_targets = [
            target for target in export_targets
            if selected_exports.get(target[0], False)
        ]
        if not chosen_targets:
            return

        try:
            if len(chosen_targets) == 1:
                _, export_title, default_name, headers, rows, writer_kind = chosen_targets[0]
                path = choose_csv_path(f"Save {export_title}", default_name)
                if not path:
                    return
                if writer_kind == "table":
                    self.write_csv_table(path, headers, rows)
                else:
                    self.write_temperature_sync_csv(path)
                self.log(f"Saved {export_title.lower()} at {path}")
                return

            output_directory = choose_output_directory()
            if not output_directory:
                return

            for _, export_title, default_name, headers, rows, writer_kind in chosen_targets:
                path = os.path.join(output_directory, default_name)
                if writer_kind == "table":
                    self.write_csv_table(path, headers, rows)
                else:
                    self.write_temperature_sync_csv(path)
                self.log(f"Saved {export_title.lower()} at {path}")
        except OSError as err:
            QMessageBox.critical(self, "Output Results", f"Failed to save CSV: {err}")

    def update_keyframe_list(self, is_adding):
        # function is called when toggling the keyframe button, connected to the keyframe clicked signal
        # grab the current keyframes from image_slider
        self.keyframe_list = list(sorted(self.image_slider.keyframes))
        # add the current frame (the newly added keyframe)

        if is_adding: 
            # adding keyframe
            self.keyframe_cell_items_dict[self.image_index] = copy.deepcopy(self.cell_items)
        else: 
            # deleting keyframe
            self.keyframe_cell_items_dict.pop(self.image_index, None)

        self.update_image_list_annotations([self.image_index])

    
    def update_flaggedframe_list(self, is_flagging):
        self.flagframe_list = list(sorted(self.image_slider.flaggedframes))
        self.update_image_list_annotations([self.image_index])
            
    
    def edit_current_keyframe_cell_item(self):
        # this function will be called if edits are made to the current cell_items
        # if the current frame is a key frame, update the cell_items of that key frame in keyframe_cell_items_dict
        # otherwise do nothing

        # the interlopation function will take care of the case when there is no keyframe at all

        if self.keyframe_list: # if any keyframe exist
            if self.image_index in self.keyframe_list:
                self.keyframe_cell_items_dict[self.image_index] = copy.deepcopy(self.cell_items)
                self.log('Edit registered for this keyframe')
            else:
                self.log('Edit unregistered for non-keyframe')


    def add_cell_item_to_keyframes(self, added_items=None):
        # Called when adding one or more cells. Cell IDs are persistent, so each
        # keyframe receives only the missing IDs rather than index-based appends.
        if not self.keyframe_list:
            return

        source_items = list(added_items or self.cell_items)
        for a_keyframe in self.keyframe_list:
            if a_keyframe == self.image_index:
                self.keyframe_cell_items_dict[a_keyframe] = copy.deepcopy(self.cell_items)
                continue

            if a_keyframe not in self.keyframe_cell_items_dict:
                self.keyframe_cell_items_dict[a_keyframe] = copy.deepcopy(self.cell_items)
                continue

            keyframe_items = self.keyframe_cell_items_dict[a_keyframe]
            existing_ids = {
                int(item.cell_id)
                for item in keyframe_items
            }
            for item in source_items:
                cell_id = int(item.cell_id)
                if cell_id in existing_ids:
                    continue
                keyframe_items.append(copy.deepcopy(item))
                existing_ids.add(cell_id)

    def delete_cell_item_to_keyframes(self, cell_id):
        self.delete_cell_items_to_keyframes([cell_id])

    def delete_cell_items_to_keyframes(self, cell_ids):
        if not cell_ids or not self.keyframe_list:
            return

        removed_number_set = {int(number) for number in cell_ids}
        for a_keyframe in self.keyframe_list:
            if a_keyframe != self.image_index:
                keyframe_items = self.keyframe_cell_items_dict.get(a_keyframe)
                if keyframe_items is None:
                    continue
                self.keyframe_cell_items_dict[a_keyframe] = [
                    item
                    for item in keyframe_items
                    if int(item.cell_id) not in removed_number_set
                ]
            else:
                self.keyframe_cell_items_dict[a_keyframe] = copy.deepcopy(self.cell_items)

    def keyframe_interpolation(self, frame_number):
        # return the cell_items list of a frame interplated

        # check if the frame_number is already a keyframe, if true then just return the cell_items of that frame
        if frame_number in self.keyframe_list:
            return self.keyframe_cell_items_dict.get(frame_number, self.cell_items)
        else:
            keyframe_array = np.array(self.keyframe_list)

            if np.any(keyframe_array<frame_number) and np.any(keyframe_array>frame_number):
                # check if the frame_number passed in is between two keyframes
                previous_kf_index = np.max(keyframe_array[keyframe_array<frame_number])
                next_kf_index     = np.min(keyframe_array[keyframe_array>frame_number])

                interped_item_lists = []
                previous_items = self.keyframe_cell_items_dict.get(previous_kf_index, [])
                next_items = self.keyframe_cell_items_dict.get(next_kf_index, [])
                previous_items_by_id = {
                    int(item.cell_id): item
                    for item in previous_items
                }
                next_items_by_id = {
                    int(item.cell_id): item
                    for item in next_items
                }
                ordered_ids = [
                    int(item.cell_id)
                    for item in previous_items
                ]
                for item in next_items:
                    cell_id = int(item.cell_id)
                    if cell_id not in previous_items_by_id:
                        ordered_ids.append(cell_id)

                # (x-x1)/(x2-x1)
                ratio = (frame_number-previous_kf_index)/(next_kf_index-previous_kf_index)

                for cell_id in ordered_ids:
                    previous_item = previous_items_by_id.get(cell_id)
                    next_item = next_items_by_id.get(cell_id)

                    if previous_item is None and next_item is None:
                        continue
                    if previous_item is None:
                        interped_item_lists.append(next_item)
                        continue
                    if next_item is None:
                        interped_item_lists.append(previous_item)
                        continue

                    # (x-x1)/(x2-x1) * (y2-y1) + y1
                    interp_circle_position_x = ratio * (next_item.circle_positions[0]       -previous_item.circle_positions[0])      + previous_item.circle_positions[0]
                    interp_circle_position_y = ratio * (next_item.circle_positions[1]       -previous_item.circle_positions[1])      + previous_item.circle_positions[1]
                    interp_circle_sizes      = ratio * (next_item.circle_sizes              -previous_item.circle_sizes)             + previous_item.circle_sizes
                    interp_pixel_position_x  = ratio * (next_item.circle_pixel_positions[0] -previous_item.circle_pixel_positions[0])+ previous_item.circle_pixel_positions[0]
                    interp_pixel_position_y  = ratio * (next_item.circle_pixel_positions[1] -previous_item.circle_pixel_positions[1])+ previous_item.circle_pixel_positions[1]

                    interp_circle_positions = (interp_circle_position_x, interp_circle_position_y)
                    interp_circle_pixel_positions = (interp_pixel_position_x, interp_pixel_position_y)

                    interp_item = CellSnapshot(
                        circle_positions=interp_circle_positions,
                        circle_sizes=interp_circle_sizes,
                        circle_pixel_positions=interp_circle_pixel_positions,
                        cell_id=cell_id,
                    )
                    interped_item_lists.append(interp_item)

                return interped_item_lists
            
            elif np.any(keyframe_array<frame_number) or np.any(keyframe_array>frame_number):
                # left is 0 or right is the right end. then use the closest kf values
                closest_kf = min(keyframe_array, key=lambda x: abs(x - frame_number))
                return self.keyframe_cell_items_dict.get(int(closest_kf), self.cell_items)
            
            else: # no kf at all, just use the cell_items
                return self.cell_items
                

    def showAboutDialog(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec()

    def showPreferencesDialog(self):
        dlg = PreferencesDialog(self)
        dlg.exec()

    def zoom_slider_set_maximum(self):
        #set max zoom value so at max zoom each step is about 10 pixel
        original_range = len(self.imagePaths)
        maximum_zoom_value = int(original_range * self.slider_maxzoom_pixel_interval / self.image_slider.width())
        if maximum_zoom_value <= 1:
            maximum_zoom_value = 2
        self.zoom_slider.setMaximum(maximum_zoom_value)

    def log(self, message):
        # Function to append messages to the terminal
        self.terminal.append(f"> {message}")

    def file_dialog_options(self):
        return QFileDialog.Options()

    def set_tools_highlight(self, tool_mode):
        for key, value in self.tool_name_dict.items():
            if key == tool_mode:
                value.setChecked(True)
            else:
                if (tool_mode in ["edit-choose", "edit-new", "edit-group"]) and (key in ["edit-choose", "edit-new"]):
                    value.setChecked(True)
                else:
                    value.setChecked(False)

    def restore_after_edit_mode(self):
        """Restore controls that are temporarily disabled during single-edit."""
        self.image_slider.setEnabled(bool(self.imagePaths) and (not self.output_state))
        self.updateButtonStates()
        self.set_undo_status()
        self.set_redo_status()

    def reset_transient_interaction_state(self):
        """Hard-clear unfinished preview/edit state without changing the active tool.

        Use this before scene clears, session restores, and other structural UI
        resets so the controller does not keep pointing at deleted preview items
        or remembered edit submodes.
        """
        self.temporary_event_data.pop("previous_edit_mode", None)
        self.temporary_event_data.pop("original_tool_mode", None)
        self.temporary_event_data.pop("image_edit_uniform_exposure_area_active", None)
        self.grid_preview_origin_pixels = None
        self.grid_preview_floating = True
        self.preview_offset_x = 0.0
        self.preview_offset_y = 0.0
        if hasattr(self, "cell_controller"):
            self.cell_controller.clear_preview()
            self.cell_controller.clear_group_cells()
        self.reset_cell_items_edit_chosen()

    def cancel_edit_state(self):
        """Cancel any active or remembered edit workflow before switching tools.

        Pan is the only tool that is allowed to preserve edit state. All other
        tool transitions should clear lifted-edit markers and any group-edit
        preview state so the next tool starts cleanly.
        """
        previous_edit_mode = self.temporary_event_data.get("previous_edit_mode")
        had_edit_state = self.cell_controller.is_any_edit_mode() or previous_edit_mode in ["edit-choose", "edit-new", "edit-group"]
        if not had_edit_state:
            return

        self.reset_transient_interaction_state()
        self.restore_after_edit_mode()

    def cancel_unfinished_tool_workflow(self):
        """Drop any transient add/edit/grid interaction before a real tool switch.

        Tool switches should not reinterpret a live preview as another tool's
        preview. They should always start from a clean interaction state unless
        we are explicitly suspending work for temporary pan.
        """
        if self.is_image_edit_uniform_exposure_area_active():
            self.end_image_edit_uniform_exposure_area()
        if self.is_image_edit_crop_active():
            self.cancel_image_edit_crop()
        if self.cell_controller.uses_grid_preview():
            self.cell_controller.cancel_preview(log_message=False)
        elif self.cell_controller.is_any_edit_mode() or self.temporary_event_data.get("previous_edit_mode") in ["edit-choose", "edit-new", "edit-group"]:
            self.cancel_edit_state()
        else:
            self.reset_transient_interaction_state()

    def preserve_edit_state_for_pan(self):
        """Remember the current edit workflow so pan can return to it."""
        if self.cell_controller.is_any_edit_mode():
            self.temporary_event_data["previous_edit_mode"] = self.tool_mode

    def set_view_cursor_shape(self, cursor_shape):
        self.view.unsetCursor()
        self.view.viewport().unsetCursor()
        self.view.setCursor(cursor_shape)
        self.view.viewport().setCursor(cursor_shape)

    def apply_cursor_tool_ui(self):
        self.tool_mode = "cursor"
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.set_view_cursor_shape(Qt.ArrowCursor)
        self.reset_cell_items_edit_chosen()
        self.set_tools_highlight(self.tool_mode)
        self.update_cell_items_selectable_state()
        self.tool_status_label.setText('Select / Move')
        self.sync_tool_options_panel()

    def apply_image_edit_tool_ui(self):
        self.tool_mode = "image-edit"
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.set_view_cursor_shape(Qt.ArrowCursor)
        self.reset_cell_items_edit_chosen()
        self.set_tools_highlight(self.tool_mode)
        self.update_cell_items_selectable_state()
        self.tool_status_label.setText('Image Edit')
        self.prewarm_current_image_edit_render_cache()
        self.sync_tool_options_panel()

    def finalize_tool_mode_after_commit(self):
        """Clear transient override state without changing the active tool."""
        self.space_held = False
        self.temporary_event_data.pop("original_tool_mode", None)
        self.temporary_event_data.pop("previous_edit_mode", None)

    def apply_select_tool_ui(self, preserve_preview=False):
        self.tool_mode = 'select'
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.set_view_cursor_shape(Qt.CrossCursor)
        self.set_tools_highlight(self.tool_mode)
        self.reset_cell_items_edit_chosen()
        self.update_cell_items_selectable_state()
        if not preserve_preview:
            self.unselect_all_cell_items()
        self.tool_status_label.setText('Add Cell')
        self.sync_tool_options_panel()

    def apply_grid_tool_ui(self, preserve_preview=False):
        self.tool_mode = 'grid'
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.set_view_cursor_shape(Qt.CrossCursor)
        self.set_tools_highlight(self.tool_mode)
        self.reset_cell_items_edit_chosen()
        self.update_cell_items_selectable_state()
        if not preserve_preview:
            self.unselect_all_cell_items()
        self.tool_status_label.setText('Grid Placement')
        self.sync_tool_options_panel()
        if not preserve_preview:
            self.update_grid_preview()
            self.log("Grid tool active. Move to float the grid, click to pin it, then Apply or press Enter.")

    def apply_deselect_tool_ui(self):
        self.tool_mode = 'deselect'
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.set_view_cursor_shape(Qt.PointingHandCursor)
        self.set_tools_highlight(self.tool_mode)
        self.reset_cell_items_edit_chosen()
        self.update_cell_items_selectable_state()
        self.unselect_all_cell_items()
        self.tool_status_label.setText('Delete Cells')
        self.sync_tool_options_panel()

    def reset_cursor_tool(self, checked):
        if self.tool_mode != "cursor":
            self.cancel_unfinished_tool_workflow()
        self.apply_cursor_tool_ui()

    def panTool(self, checked):
        self.preserve_edit_state_for_pan()
        self.tool_mode = 'pan'
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)  # Enable panning in pan mode
        self.set_view_cursor_shape(Qt.OpenHandCursor)
        self.set_tools_highlight(self.tool_mode)
        self.update_cell_items_selectable_state()
        self.tool_status_label.setText('Zoom and Pan')
        self.sync_tool_options_panel()

    def is_pan_interaction_active(self):
        return bool(
            self.tool_mode == 'pan'
            or (self.space_held and (self.temporary_event_data.get("original_tool_mode") is not None))
        )

    def enter_temporary_pan_mode(self):
        self.preserve_edit_state_for_pan()
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.set_view_cursor_shape(Qt.OpenHandCursor)
        self.set_tools_highlight("pan")
        self.update_cell_items_selectable_state()
        self.tool_status_label.setText('Zoom and Pan')

    def imageEditTool(self, checked):
        if self.tool_mode != "image-edit":
            self.cancel_unfinished_tool_workflow()
        self.apply_image_edit_tool_ui()

    def selectTool(self, checked):
        if self.tool_mode != "select":
            self.cancel_unfinished_tool_workflow()
            self.restore_add_defaults(include_grid=False)
        self.apply_select_tool_ui()

    def gridTool(self, checked):
        if self.tool_mode != "grid":
            self.cancel_unfinished_tool_workflow()
            self.restore_add_defaults(include_grid=True)
        self.apply_grid_tool_ui()

    def activate_edit_cell_item(self, cell_item):
        if cell_item is None:
            return
        self.cell_controller.clear_group_cells()
        self.reset_cell_items_edit_chosen()
        cell_item.edit_chosen = True
        cell_item.update()
        self.preview_offset_x = 0.0
        self.preview_offset_y = 0.0
        self.edit_single_base_radius = float(cell_item.circle_sizes)
        self.edit_single_radius_delta = 0.0
        self.circle_radius = float(cell_item.circle_sizes)
        self.tool_mode = 'edit-new'
        self.set_tools_highlight(self.tool_mode)
        self.set_undo_status()
        self.set_redo_status()
        self.set_view_cursor_shape(Qt.CrossCursor)
        self.tool_status_label.setText('Edit Cell')
        self.grid_preview_origin_pixels = (
            float(cell_item.circle_pixel_positions[0]),
            float(cell_item.circle_pixel_positions[1]),
        )
        self.grid_preview_floating = False
        self.update_grid_preview()
        self.updateRadiusTextbox()
        self.sync_tool_options_panel()
        self.refresh_grayscale_plot()
    
    def editTool(self, checked):
        if (not self.cell_controller.is_any_edit_mode()) and ("previous_edit_mode" not in self.temporary_event_data):
            self.cancel_unfinished_tool_workflow()
        if "previous_edit_mode" in self.temporary_event_data:
            edit_mode = self.temporary_event_data["previous_edit_mode"]
            self.temporary_event_data.pop("previous_edit_mode")
        else:
            edit_mode = self.tool_mode if self.cell_controller.is_any_edit_mode() else 'edit-choose'

        self.cell_controller.enter_edit_mode(edit_mode)
        self.set_tools_highlight(self.tool_mode)
        self.update_cell_items_selectable_state()
        self.tool_status_label.setText('Edit Cell')
        self.sync_tool_options_panel()
    
    def deselectTool(self, checked):
        if self.delete_selected_cells():
            return
        if self.tool_mode != "deselect":
            self.cancel_unfinished_tool_workflow()
        self.apply_deselect_tool_ui()

    
    def get_image_paths_from_folder(self, input_dirpath):
        image_extensions = {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"}
        input_imagePath = []
        for root, dirs, files in os.walk(input_dirpath):
            for file in files:
                if file.split('.')[-1].lower() in image_extensions:
                    input_imagePath.append(os.path.join(root, file))
        return self.sort_image_paths(input_imagePath)

    def natural_sort_key(self, file_path):
        filename = os.path.basename(file_path)
        parts = re.split(r'(\d+)', filename.lower())
        key = [int(part) if part.isdigit() else part for part in parts]
        return (key, file_path.lower())

    def get_exif_sort_value(self, file_path):
        try:
            image = Image.open(file_path)
            exif = image.getexif()
            exif_datetime = exif.get(306)
            if not exif_datetime:
                return None
            return exif_datetime
        except Exception:
            return None

    def is_sort_mode_available(self, mode, file_paths=None):
        paths = file_paths if file_paths is not None else self.imagePaths
        if not paths:
            return True
        if mode == "exif_time":
            return all(self.get_exif_sort_value(path) is not None for path in paths)
        if mode == "created_time":
            try:
                return all(os.path.exists(path) and os.stat(path).st_birthtime for path in paths)
            except AttributeError:
                return False
            except OSError:
                return False
        if mode == "modified_time":
            try:
                return all(os.path.exists(path) for path in paths)
            except OSError:
                return False
        return True

    def get_sort_availability(self, file_paths=None):
        return {
            "natural_filename": True,
            "filename_asc": True,
            "filename_desc": True,
            "created_time": self.is_sort_mode_available("created_time", file_paths),
            "modified_time": self.is_sort_mode_available("modified_time", file_paths),
            "exif_time": self.is_sort_mode_available("exif_time", file_paths),
        }

    def sort_image_paths(self, file_paths, mode=None):
        sort_mode = mode or self.sort_mode
        paths = list(file_paths)
        if sort_mode == "natural_filename":
            return sorted(paths, key=self.natural_sort_key)
        if sort_mode == "filename_asc":
            return sorted(paths, key=lambda path: (os.path.basename(path).lower(), path.lower()))
        if sort_mode == "filename_desc":
            return sorted(paths, key=lambda path: (os.path.basename(path).lower(), path.lower()), reverse=True)
        if sort_mode == "created_time":
            return sorted(paths, key=lambda path: (os.stat(path).st_birthtime, os.path.basename(path).lower()))
        if sort_mode == "modified_time":
            return sorted(paths, key=lambda path: (os.path.getmtime(path), os.path.basename(path).lower()))
        if sort_mode == "exif_time":
            return sorted(paths, key=lambda path: (self.get_exif_sort_value(path), os.path.basename(path).lower()))
        return paths

    def openSortImagesDialog(self):
        availability = self.get_sort_availability()
        dialog = SortImagesDialog(self, availability, self.sort_mode, self)
        if dialog.exec() != QDialog.Accepted:
            return

        selected_mode = dialog.selected_mode()
        if not self.is_sort_mode_available(selected_mode):
            QMessageBox.warning(self, "Sort Images", "The selected sort method is not available for the current session.")
            return

        before_state = self.capture_session_state() if self.imagePaths else None
        self.sort_mode = selected_mode
        if self.imagePaths:
            self.resort_current_session()
            if before_state is not None:
                self.push_snapshot_history("Sort Images", before_state)
        self.log(f"Sort mode: {selected_mode.replace('_', ' ')}")

    def resort_current_session(self):
        if not self.imagePaths:
            return

        self.reset_pending_frame_navigation_state(stop_timer=True)
        self.clear_image_caches()
        current_path = self.imagePaths[self.image_index]
        keyed_entries = list(zip(
            self.imagePaths,
            self.imageNames,
            self.image_list_entry_ids,
            range(len(self.imagePaths)),
        ))
        sorted_paths = self.sort_image_paths([entry[0] for entry in keyed_entries])
        sorted_entries = []
        remaining_entries = keyed_entries.copy()
        for path in sorted_paths:
            for idx, entry in enumerate(remaining_entries):
                if entry[0] == path:
                    sorted_entries.append(entry)
                    remaining_entries.pop(idx)
                    break

        old_to_new = {old_index: new_index for new_index, (_, _, _, old_index) in enumerate(sorted_entries)}
        self.imagePaths = [entry[0] for entry in sorted_entries]
        self.imageNames = [entry[1] for entry in sorted_entries]
        self.image_list_entry_ids = [entry[2] for entry in sorted_entries]
        self.keyframe_list = sorted(old_to_new[index] for index in self.keyframe_list if index in old_to_new)
        self.flagframe_list = sorted(old_to_new[index] for index in self.flagframe_list if index in old_to_new)
        self.keyframe_cell_items_dict = {
            old_to_new[index]: circles
            for index, circles in self.keyframe_cell_items_dict.items()
            if index in old_to_new
        }
        self.image_index = self.imagePaths.index(current_path) if current_path in self.imagePaths else 0
        self.populate_image_list()
        self.updateImage(self.image_index)
        self.invalidate_analysis_results("image order changed")

    def open_add_images_dialog(self):
        source_dialog = QMessageBox(self)
        source_dialog.setWindowTitle("Add Images")
        source_dialog.setText("Choose what to add to this session.")
        add_files_button = source_dialog.addButton("Images...", QMessageBox.AcceptRole)
        add_folder_button = source_dialog.addButton("Folder...", QMessageBox.ActionRole)
        source_dialog.addButton(QMessageBox.Cancel)
        source_dialog.exec()

        clicked_button = source_dialog.clickedButton()
        if clicked_button == add_files_button:
            self.loadImages()
        elif clicked_button == add_folder_button:
            self.loadFolder()

    def loadFolder(self):
        input_dirpath = QFileDialog.getExistingDirectory(
            self,
            'Select Folder',
            "",
            options=self.file_dialog_options(),
        )
        if input_dirpath:
            self.load_aux(self.get_image_paths_from_folder(input_dirpath))

    def loadImages(self):
        input_imagePath, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Image(s)",
            "",
            "Image Files (*.png *.jpg *.jpeg);;All Files (*)",
            options=self.file_dialog_options(),
        )
        if input_imagePath:
            self.load_aux(self.sort_image_paths(input_imagePath))

    def openSession(self):
        save_choice = self.prompt_save_before_replacing_session("opening another session")
        if save_choice == "cancel":
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Session",
            "",
            "Icescopy Session (*.icescopy);;All Files (*)",
            options=self.file_dialog_options(),
        )
        if not file_path:
            return

        try:
            payload, grayscale_table, freeze_table = load_session_bundle(file_path)
            state = build_restore_state(self, payload, grayscale_table, freeze_table)
            self.session_active = True
            self.current_session_file_path = file_path
            self.restore_session_state(state)
            self.undo_stack.clear()
            self.pending_analysis_before_state = None
            self.log(f"Opened session {os.path.basename(file_path)}")
            missing_images = self.get_missing_session_image_paths()
            if missing_images:
                QMessageBox.information(
                    self,
                    "Session Images Missing",
                    "Some session image files could not be found.\n\nUse File -> Relink Images Folder... to point the session to the current image folder.",
                )
        except Exception as err:
            QMessageBox.critical(self, "Open Session Failed", str(err))
            self.log(f"Failed to open session: {err}")

    def get_missing_session_image_paths(self):
        missing_paths = []
        for image_path in getattr(self, "imagePaths", []):
            try:
                if not os.path.isfile(image_path):
                    missing_paths.append(str(image_path))
            except OSError:
                missing_paths.append(str(image_path))
        return missing_paths

    def relink_images_folder(self, checked=False):
        if not self.imagePaths:
            QMessageBox.information(self, "Relink Images Folder", "No session images are loaded.")
            return

        initial_dir = ""
        for image_path in self.imagePaths:
            try:
                if os.path.isfile(image_path):
                    initial_dir = os.path.dirname(image_path)
                    break
            except OSError:
                continue
        if not initial_dir:
            first_path = str(self.imagePaths[0])
            if first_path:
                initial_dir = os.path.dirname(first_path)

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Relink Images Folder",
            initial_dir,
            options=self.file_dialog_options(),
        )
        if not selected_dir:
            return

        candidate_paths = self.get_image_paths_from_folder(selected_dir)
        if not candidate_paths:
            QMessageBox.warning(self, "Relink Images Folder", "No image files were found in the selected folder.")
            return

        candidates_by_name = {}
        for candidate_path in candidate_paths:
            basename = os.path.basename(candidate_path).casefold()
            candidates_by_name.setdefault(basename, []).append(candidate_path)

        before_state = self.capture_image_session_state()
        old_image_paths = list(self.imagePaths)
        raw_image_edit_state = self.serialize_image_edit_state()
        all_images_missing_before = True
        for image_path in old_image_paths:
            try:
                if os.path.isfile(image_path):
                    all_images_missing_before = False
                    break
            except OSError:
                continue
        new_image_paths = []
        relinked_count = 0
        ambiguous_names = []
        missing_names = []

        for index, old_path in enumerate(old_image_paths):
            image_name = os.path.basename(str(old_path or "")) or str(self.imageNames[index] if index < len(self.imageNames) else "")
            matches = candidates_by_name.get(image_name.casefold(), [])
            if len(matches) == 1:
                resolved_path = matches[0]
                if os.path.normcase(os.path.normpath(resolved_path)) != os.path.normcase(os.path.normpath(str(old_path))):
                    relinked_count += 1
                new_image_paths.append(resolved_path)
            elif len(matches) > 1:
                ambiguous_names.append(image_name)
                new_image_paths.append(old_path)
            else:
                missing_names.append(image_name)
                new_image_paths.append(old_path)

        if relinked_count == 0 and not ambiguous_names and missing_names:
            QMessageBox.warning(
                self,
                "Relink Images Folder",
                "No matching image filenames were found in the selected folder.",
            )
            return

        offset_map = {
            str(path): float(value)
            for path, value in dict(getattr(self, "image_edit_uniform_exposure_offsets", {})).items()
            if abs(float(value)) > 1e-9
        }
        remapped_offsets = {}
        for old_path, new_path in zip(old_image_paths, new_image_paths):
            if str(old_path) in offset_map:
                remapped_offsets[str(new_path)] = float(offset_map[str(old_path)])

        resolved_indexes = []
        for index, image_path in enumerate(new_image_paths):
            try:
                if os.path.isfile(image_path):
                    resolved_indexes.append(index)
            except OSError:
                continue

        self.imagePaths = list(new_image_paths)
        self.imageNames = [os.path.basename(path) for path in self.imagePaths]
        self.image_edit_uniform_exposure_offsets = remapped_offsets
        self.raw_image_size_cache = {}
        self.clear_image_caches()
        self.clear_context_pixmaps()
        if hasattr(self, "pixmap_item"):
            try:
                self.scene.removeItem(self.pixmap_item)
            except Exception:
                pass
            del self.pixmap_item
        self.view.resetTransform()
        self.view.horizontalScrollBar().setValue(0)
        self.view.verticalScrollBar().setValue(0)

        if resolved_indexes:
            if self.image_index not in resolved_indexes:
                self.image_index = int(resolved_indexes[0])
            self.last_committed_image_index = int(self.image_index)

            raw_width, raw_height = self.get_raw_image_dimensions(self.image_index)
            crop_state = dict((raw_image_edit_state or {}).get("crop", {}) or {})
            try:
                crop_center_x = float(crop_state.get("center_x", 0.0))
                crop_center_y = float(crop_state.get("center_y", 0.0))
                crop_width = float(crop_state.get("width", 1.0))
                crop_height = float(crop_state.get("height", 1.0))
                crop_angle = float(crop_state.get("angle", 0.0))
            except (TypeError, ValueError):
                crop_center_x = 0.0
                crop_center_y = 0.0
                crop_width = 1.0
                crop_height = 1.0
                crop_angle = 0.0

            collapsed_missing_image_crop = (
                all_images_missing_before
                and raw_width > 0
                and raw_height > 0
                and abs(crop_center_x) <= 1e-9
                and abs(crop_center_y) <= 1e-9
                and abs(crop_width - 1.0) <= 1e-9
                and abs(crop_height - 1.0) <= 1e-9
                and abs(crop_angle) <= 1e-9
            )
            if collapsed_missing_image_crop:
                raw_image_edit_state["crop"] = {
                    "center_x": float(raw_width) * 0.5,
                    "center_y": float(raw_height) * 0.5,
                    "width": float(raw_width),
                    "height": float(raw_height),
                    "angle": 0.0,
                }

            self.apply_image_edit_state(
                raw_image_edit_state,
                invalidate_results=False,
                refresh_display=False,
                sync_controls=False,
            )

        self.populate_image_list()
        if resolved_indexes:
            self.updateImage(self.image_index)
            self.finalize_frame_update(self.image_index)
            self.view.fitInView(self.view.sceneRect(), Qt.KeepAspectRatio)
        elif self.imagePaths:
            self.image_name_label.setText(self.imageNames[self.image_index] if 0 <= self.image_index < len(self.imageNames) else "")
            self.image_textbox.setText(str(self.image_index))
        self.push_image_session_history("Relink Images Folder", before_state)

        message_lines = [f"Relinked images: {relinked_count}"]
        if resolved_indexes and self.image_index != before_state.get("image_index", self.image_index):
            message_lines.append(f"Showing first resolved image at index {self.image_index}")
        if missing_names:
            preview = ", ".join(missing_names[:6])
            if len(missing_names) > 6:
                preview += f", +{len(missing_names) - 6} more"
            message_lines.append("Still missing: " + preview)
        if ambiguous_names:
            preview = ", ".join(ambiguous_names[:6])
            if len(ambiguous_names) > 6:
                preview += f", +{len(ambiguous_names) - 6} more"
            message_lines.append("Ambiguous filenames not changed: " + preview)

        persisted_relink = False
        current_session_file_path = str(getattr(self, "current_session_file_path", "") or "").strip()
        if current_session_file_path:
            persisted_relink = self.persist_session_to_current_file(show_errors=False)
            if persisted_relink:
                message_lines.append(f"Session updated: {os.path.basename(current_session_file_path)}")
            else:
                message_lines.append("Session file was not updated. Use Save Session to persist relinked paths.")

        QMessageBox.information(self, "Relink Images Folder", "\n".join(message_lines))
        self.log(f"Relink Images Folder: {relinked_count} image path(s) updated")

    def handle_save_session_action(self):
        self.key_press_toolbutton_highlight(self.save_session_action)
        return self.saveSession()

    def persist_session_to_path(self, file_path, *, show_errors=True):
        try:
            payload = build_session_payload(self)
            save_session_bundle(
                file_path,
                payload,
                self.grayscale_results_headers,
                self.grayscale_results_rows,
                self.freeze_results_headers,
                self.freeze_results_rows,
            )
            self.current_session_file_path = file_path
            self.log(f"Saved session at {file_path}")
            return True
        except Exception as err:
            if show_errors:
                QMessageBox.critical(self, "Save Session Failed", str(err))
            self.log(f"Failed to save session: {err}")
            return False

    def persist_session_to_current_file(self, *, show_errors=True):
        file_path = str(getattr(self, "current_session_file_path", "") or "").strip()
        if not file_path:
            return False
        return self.persist_session_to_path(file_path, show_errors=show_errors)

    def saveSession(self):
        if not getattr(self, "session_active", False):
            self.log("No active session to save")
            return False

        current_session_file_path = str(getattr(self, "current_session_file_path", "") or "").strip()
        if current_session_file_path:
            return self.persist_session_to_current_file(show_errors=True)

        return self.saveSessionAs()

    def saveSessionAs(self):
        if not getattr(self, "session_active", False):
            self.log("No active session to save")
            return False

        initial_path = str(getattr(self, "current_session_file_path", "") or "").strip()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Session As",
            initial_path,
            "Icescopy Session (*.icescopy);;All Files (*)",
            options=self.file_dialog_options(),
        )
        if not file_path:
            return False

        if not file_path.lower().endswith(".icescopy"):
            file_path = f"{file_path}.icescopy"

        return self.persist_session_to_path(file_path, show_errors=True)

    def load_aux(self, input_imagePath):
        if not input_imagePath:
            if not self.imagePaths:
                self.log("No image loaded")
            return

        before_state = self.capture_loaded_images_state()

        normalized_existing_paths = {
            os.path.normcase(os.path.normpath(existing_path))
            for existing_path in self.imagePaths
        }
        unique_new_paths = []
        for image_path in input_imagePath:
            normalized_path = os.path.normcase(os.path.normpath(image_path))
            if normalized_path not in normalized_existing_paths:
                unique_new_paths.append(image_path)
                normalized_existing_paths.add(normalized_path)
        unique_new_paths = self.sort_image_paths(unique_new_paths)

        if not unique_new_paths:
            self.log("No new images added")
            return

        is_first_load = not self.imagePaths
        new_entry_ids = list(range(self.next_image_list_entry_id, self.next_image_list_entry_id + len(unique_new_paths)))
        self.next_image_list_entry_id += len(unique_new_paths)
        self.imagePaths.extend(unique_new_paths)
        self.imageNames.extend([os.path.basename(path) for path in unique_new_paths])
        self.image_list_entry_ids.extend(new_entry_ids)

        if is_first_load:
            self.log(f"Loaded {len(unique_new_paths)} images")
            if hasattr(self, 'pixmap_item'):
                self.scene.removeItem(self.pixmap_item)
                del(self.pixmap_item)
        else:
            self.log(f"Added {len(unique_new_paths)} images to this session")

        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(len(self.imagePaths) - 1)
        if is_first_load:
            self.image_slider.setValue(0)
        self.image_slider.blockSignals(False)

        self.select_tool_action.setEnabled(True)
        self.grid_tool_action.setEnabled(True)
        self.pan_tool_action.setEnabled(True)
        self.image_slider.setEnabled(True)
        self.deselect_tool_action.setEnabled(True)
        self.edit_tool_action.setEnabled(True)
        self.update_session_actions_state()
        self.updateButtonStates()
        self.set_redo_status()
        self.set_undo_status()
        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()
        new_rows = range(len(self.imagePaths) - len(unique_new_paths), len(self.imagePaths))
        new_entries = [self.format_image_list_entry(index) for index in new_rows]
        if is_first_load:
            self.image_list_model.set_items(new_entries, unique_new_paths)
        else:
            self.image_list_model.append_items(new_entries, unique_new_paths)

        if is_first_load:
            self.image_textbox.setText("0")
            self.updateImage(0)
            self.finalize_frame_update(0)
        else:
            self.sync_image_list_selection()

        self.invalidate_analysis_results("image list changed")

        self.push_loaded_images_history("Add Images", before_state)

    def remove_selected_image(self):
        if not self.imagePaths:
            return

        if self.active_image_panel == "list":
            self.remove_selected_list_images()
        else:
            self.remove_current_viewer_image()

    def remove_selected_list_images(self):
        if not self.imagePaths:
            return

        selected_rows = self.get_selected_image_rows()
        if not selected_rows:
            current_index = self.image_list_widget.currentIndex()
            if current_index.isValid():
                selected_rows = [current_index.row()]
            else:
                selected_rows = [self.image_index]

        self.remove_images_from_session(selected_rows)

    def remove_current_viewer_image(self):
        if not self.imagePaths:
            return
        self.remove_images_from_session([self.image_index])

    def remove_images_from_session(self, rows):
        rows_to_remove = sorted({row for row in rows if 0 <= row < len(self.imagePaths)})
        if not rows_to_remove:
            return

        if len(rows_to_remove) >= len(self.imagePaths):
            self.clear_loaded_images(confirm=False, log_message="Cleared all loaded images from this session")
            return

        before_state = self.capture_image_session_state()
        self.reset_pending_frame_navigation_state(stop_timer=True)
        self.clear_image_caches()

        removed_rows = set(rows_to_remove)
        old_image_index = self.image_index
        removed_before_current = sum(1 for row in rows_to_remove if row < old_image_index)
        current_removed = old_image_index in removed_rows

        self.imagePaths = [path for index, path in enumerate(self.imagePaths) if index not in removed_rows]
        self.imageNames = [name for index, name in enumerate(self.imageNames) if index not in removed_rows]
        self.image_list_entry_ids = [entry_id for index, entry_id in enumerate(self.image_list_entry_ids) if index not in removed_rows]

        self.keyframe_cell_items_dict = {
            old_index - sum(1 for removed_row in rows_to_remove if removed_row < old_index): value
            for old_index, value in self.keyframe_cell_items_dict.items()
            if old_index not in removed_rows
        }
        self.keyframe_list = [
            old_index - sum(1 for removed_row in rows_to_remove if removed_row < old_index)
            for old_index in self.keyframe_list
            if old_index not in removed_rows
        ]
        self.flagframe_list = [
            old_index - sum(1 for removed_row in rows_to_remove if removed_row < old_index)
            for old_index in self.flagframe_list
            if old_index not in removed_rows
        ]

        new_image_index = max(0, min(old_image_index - removed_before_current, len(self.imagePaths) - 1))

        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(len(self.imagePaths) - 1)
        self.image_slider.setValue(new_image_index)
        self.image_slider.blockSignals(False)
        self.image_slider.keyframes = set(self.keyframe_list)
        self.image_slider.flaggedframes = set(self.flagframe_list)
        self.image_slider.update()
        self.image_textbox.setText(str(new_image_index))

        self.image_list_model.remove_rows(rows_to_remove)
        if self.imagePaths:
            annotation_start = min(rows_to_remove)
            self.update_image_list_annotations(range(annotation_start, len(self.imagePaths)))
        else:
            self.populate_image_list()
        # Always refresh frame display/interpolation after image removal because
        # shifting frame indices can change keyframe interpolation even when the
        # current image path itself did not change.
        self.updateImage(new_image_index)
        self.finalize_frame_update(new_image_index)
        self.invalidate_analysis_results("image list changed")
        self.update_session_actions_state()
        self.updateButtonStates()
        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()
        self.log(f"Removed {len(rows_to_remove)} image(s) from this session")
        self.push_image_session_history("Remove Images", before_state)

    def clear_loaded_images(self, checked=False, confirm=True, log_message="Cleared all loaded images from this session"):
        if not self.imagePaths:
            return

        if confirm:
            reply = QMessageBox.question(
                self,
                "Clear Images",
                "Remove all loaded images from this session? This also clears cells, keyframes, and analysis results tied to those images, but does not delete files from disk.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        before_state = self.capture_image_session_state()

        self.reset_transient_interaction_state()
        self.reset_pending_frame_navigation_state(stop_timer=True)
        self.clear_image_caches()
        self.cell_items = []
        self.rendered_cell_items = []
        self.next_cell_id = 0
        self.cell_records_by_id = {}
        self.keyframe_list = []
        self.flagframe_list = []
        self.keyframe_cell_items_dict = {}
        self.image_width = None
        self.imagePaths = []
        self.imageNames = []
        self.image_index = 0
        self.last_committed_image_index = 0
        self.image_list_entry_ids = []
        self.next_image_list_entry_id = 0

        self.scene.clear()
        if hasattr(self, 'pixmap_item'):
            del(self.pixmap_item)

        self.image_name_label.clear()
        self.image_textbox.clear()
        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(0)
        self.image_slider.setValue(0)
        self.image_slider.blockSignals(False)
        self.image_slider.setEnabled(False)
        self.image_slider.keyframes = set()
        self.image_slider.flaggedframes = set()
        self.image_slider.update()

        self.select_tool_action.setEnabled(False)
        self.grid_tool_action.setEnabled(False)
        self.pan_tool_action.setEnabled(False)
        self.deselect_tool_action.setEnabled(False)
        self.edit_tool_action.setEnabled(False)
        self.update_session_actions_state()
        self.updateButtonStates()
        self.invalidate_analysis_results("image list changed")
        self.populate_image_list()
        self.reset_cursor_action.trigger()
        self.log(log_message)
        self.push_image_session_history("Clear Images", before_state)

    def clear_session(self, checked=False, confirm=True, log_message="Cleared session", record_history=True, new_metadata=None, activate_session=False):
        has_results = bool(
            self.grayscale_results_headers
            or self.freeze_results_headers
            or self.temperature_sync_headers
        )
        if confirm and (self.imagePaths or has_results):
            reply = QMessageBox.question(
                self,
                "Clear Session",
                "Clear the entire current session? This removes loaded images and in-app analysis data, but does not delete files from disk.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        before_state = self.capture_session_state() if record_history else None

        self.initData()
        self.session_active = bool(activate_session)
        if new_metadata is not None:
            self.apply_session_metadata(new_metadata)

        self.reset_transient_interaction_state()
        self.reset_pending_frame_navigation_state(stop_timer=True)
        self.scene.clear()
        if hasattr(self, 'pixmap_item'):
            del(self.pixmap_item)

        self.image_name_label.clear()
        self.image_textbox.clear()
        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(0)
        self.image_slider.setValue(0)
        self.image_slider.blockSignals(False)
        self.image_slider.setEnabled(False)
        self.image_slider.keyframes = set()
        self.image_slider.flaggedframes = set()
        self.image_slider.update()

        self.select_tool_action.setEnabled(False)
        self.grid_tool_action.setEnabled(False)
        self.pan_tool_action.setEnabled(False)
        self.deselect_tool_action.setEnabled(False)
        self.edit_tool_action.setEnabled(False)
        self.update_session_actions_state()
        self.updateButtonStates()
        self.update_results_tables()
        self.update_temperature_sync_table()
        self.refresh_sample_catalog_table(preserve_selection=False)
        self.populate_image_list()
        self.reset_cursor_action.trigger()
        if hasattr(self, "terminal"):
            self.terminal.clear()
        self.log(log_message)
        if record_history and before_state is not None:
            self.push_snapshot_history("Clear Session", before_state)

    def reset_pending_frame_navigation_state(self, stop_timer=False):
        self.pending_navigation_before_index = None
        self.pending_navigation_history_text = "Change Frame"
        self.slider_drag_start_index = None
        self.pending_preview_image_index = None
        self.preview_frame_update_in_progress = False
        if stop_timer and hasattr(self, "image_preview_timer"):
            self.image_preview_timer.stop()

    def clear_image_caches(self):
        if hasattr(self, "image_cache"):
            self.image_cache.clear()
        if hasattr(self, "pixmap_cache"):
            self.pixmap_cache.clear()
        self.displayed_image_edit_crop_applied = None

    def get_cached_raw_image(self, image_path):
        image_path = str(image_path)
        cached_image = self.raw_image_cache.get(image_path)
        if cached_image is not None:
            self.raw_image_cache.move_to_end(image_path)
            return cached_image

        cached_image = QImage(image_path)
        self.raw_image_cache[image_path] = cached_image
        self.raw_image_cache.move_to_end(image_path)

        if hasattr(self, "raw_image_size_cache"):
            self.raw_image_size_cache[image_path] = (int(cached_image.width()), int(cached_image.height()))

        while len(self.raw_image_cache) > self.raw_image_cache_size:
            evicted_path, _ = self.raw_image_cache.popitem(last=False)
            if hasattr(self, "raw_image_size_cache"):
                self.raw_image_size_cache.pop(evicted_path, None)

        return cached_image

    def handle_preview_image_slider_value(self, index):
        if not self.imagePaths:
            return
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        if index < 0 or index >= len(self.imagePaths):
            return

        self.pending_preview_image_index = index
        if self.preview_frame_update_in_progress:
            return
        if not self.image_preview_timer.isActive():
            self.image_preview_timer.start(self.get_preview_frame_interval_ms())

    def handle_image_slider_pressed(self):
        if not self.imagePaths or self.history_restoring:
            return
        committed_index = max(
            0,
            min(int(getattr(self, "last_committed_image_index", self.image_index)), len(self.imagePaths) - 1),
        )
        self.slider_drag_start_index = committed_index
        self.pending_navigation_before_index = committed_index
        self.pending_navigation_history_text = "Change Frame"

    def handle_image_slider_released(self):
        # Drag-release can occur without a committed value change. In that case,
        # clear pending navigation start so it cannot leak into the next move.
        if self.history_restoring:
            return
        if self.image_slider.isSliderDown():
            return
        if self.slider_drag_start_index is None:
            return
        if self.image_slider.sliderPosition() != self.slider_drag_start_index:
            return
        restore_index = int(self.slider_drag_start_index)
        preview_diverged = (
            self.image_index != restore_index
            or (
                self.pending_preview_image_index is not None
                and int(self.pending_preview_image_index) != restore_index
            )
        )
        self.reset_pending_frame_navigation_state(stop_timer=True)
        if preview_diverged and self.imagePaths:
            self.updateImage(restore_index, preview=False)

    def get_preview_frame_interval_ms(self):
        return 16

    def flush_pending_preview_image(self):
        if self.pending_preview_image_index is None or self.preview_frame_update_in_progress:
            return
        pending_index = int(self.pending_preview_image_index)
        self.pending_preview_image_index = None
        if not self.imagePaths:
            return
        if pending_index < 0 or pending_index >= len(self.imagePaths):
            return
        if pending_index == self.image_index:
            return

        self.preview_frame_update_in_progress = True
        try:
            self.updateImage(pending_index, preview=True)
        finally:
            self.preview_frame_update_in_progress = False

        if (
            self.pending_preview_image_index is not None
            and self.pending_preview_image_index != self.image_index
        ):
            self.image_preview_timer.start(self.get_preview_frame_interval_ms())

    def handle_committed_image_slider_value(self, index):
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        drag_start_index = self.slider_drag_start_index
        before_index = self.pending_navigation_before_index
        history_text = self.pending_navigation_history_text
        self.reset_pending_frame_navigation_state(stop_timer=True)
        if before_index is None and drag_start_index is not None:
            before_index = drag_start_index
        if before_index is None and not self.history_restoring:
            before_index = self.last_committed_image_index
        if self.imagePaths and self.image_index == index:
            self.finalize_frame_update(index)
        else:
            self.updateImage(index, preview=False)
        if self.analysis_progress_navigation_suppressed and not self.history_restoring:
            return
        if before_index is not None and not self.history_restoring and before_index != self.image_index:
            self.log(f"{history_text}: {before_index} -> {self.image_index}")
            self.push_navigation_history(history_text, before_index, self.image_index)

    def finalize_frame_update(self, index):
        if not self.imagePaths or not (0 <= index < len(self.imagePaths)):
            return
        self.last_committed_image_index = int(index)
        if not self.image_slider.isSliderDown():
            self.ensure_slider_window_contains_index(index)
            if self.image_slider.value() != index:
                self.image_slider.blockSignals(True)
                self.image_slider.setValue(index)
                self.image_slider.blockSignals(False)
        self.image_name_label.setText(self.imageNames[index])
        self.resize_image_textbox()
        self.updateButtonStates()
        self.update_toggle_keyframe_button_icon()
        self.update_toggle_flagging_button_icon()
        self.sync_image_list_selection()
        self.update_grayscale_plot_current_frame()

    def ensure_slider_window_contains_index(self, index):
        if not self.imagePaths:
            return

        target_index = max(0, min(int(index), len(self.imagePaths) - 1))
        slider_min = self.image_slider.minimum()
        slider_max = self.image_slider.maximum()
        if slider_min <= target_index <= slider_max:
            return

        window_size = max(0, slider_max - slider_min)
        if target_index < slider_min:
            new_min = target_index
            new_max = target_index + window_size
        else:
            new_max = target_index
            new_min = target_index - window_size

        max_index = len(self.imagePaths) - 1
        new_min = max(0, int(new_min))
        new_max = min(max_index, int(new_max))
        if new_max - new_min < window_size:
            if new_min == 0:
                new_max = min(max_index, new_min + window_size)
            else:
                new_min = max(0, new_max - window_size)

        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(new_min)
        self.image_slider.setMaximum(new_max)
        self.image_slider.blockSignals(False)

    def updateImage(self, index, preview=False):
            if self.imagePaths:
                try:
                    index = int(index)
                except (TypeError, ValueError):
                    index = int(getattr(self, "last_committed_image_index", self.image_index))
                index = max(0, min(index, len(self.imagePaths) - 1))
                current_transform = self.view.transform()
                current_hscroll = self.view.horizontalScrollBar().value()
                current_vscroll = self.view.verticalScrollBar().value()
                had_pixmap_item = hasattr(self, 'pixmap_item')

                self.view.setUpdatesEnabled(False)
                try:
                    self.image_index = index
                    self.image_textbox.setText(str(index))
                    q_image = self.update_display_pixmaps(index)
                    if not had_pixmap_item:
                        self.view.fitInView(self.view.sceneRect(), Qt.KeepAspectRatio)

                    self.view.setTransform(current_transform)
                    self.view.horizontalScrollBar().setValue(current_hscroll)
                    self.view.verticalScrollBar().setValue(current_vscroll)

                    self.image_width = self.get_raw_image_dimensions(index)[0]
                    self.interpolate_and_displayMarkedRegions(index, preview=preview)
                    if self.cell_controller.uses_grid_preview():
                        self.cell_controller.rebase_edit_preview_to_current_frame()
                        self.update_grid_preview()
                    self.update_grayscale_plot_current_frame()
                    self.request_image_edit_histogram_refresh(q_image)
                    if self.tool_mode == "image-edit":
                        self.sync_image_edit_controls()

                    if not preview:
                        self.finalize_frame_update(index)
                finally:
                    self.view.setUpdatesEnabled(True)

                
                    
    def decreaseSliderValue(self):
        current_value = self.image_slider.value()
        if current_value > self.image_slider.minimum():
            self.navigate_to_image(current_value - 1)

        elif current_value > 0:
            self.image_slider.setMinimum(self.image_slider.minimum()-1)
            self.image_slider.setMaximum(self.image_slider.maximum()-1)
            self.navigate_to_image(current_value - 1)

    def increaseSliderValue(self):
        current_value = self.image_slider.value()
        if current_value < self.image_slider.maximum():
            self.navigate_to_image(current_value + 1)
        
        elif current_value < (len(self.imagePaths)-1):
            self.image_slider.setMinimum(self.image_slider.minimum()+1)
            self.image_slider.setMaximum(self.image_slider.maximum()+1)
            self.navigate_to_image(current_value + 1)

    def handle_frame_navigation_shortcut(self, key):
        if key in (Qt.Key_Left, Qt.Key_Comma):
            if self.leftButton.isEnabled():
                self.leftButton.click()
                self.key_press_button_highlight(self.leftButton)
                return True
            return False
        if key in (Qt.Key_Right, Qt.Key_Period):
            if self.rightButton.isEnabled():
                self.rightButton.click()
                self.key_press_button_highlight(self.rightButton)
                return True
            return False
        return False
            
    def updateImageFromTextbox(self):
        # Update displayed image based on textbox value by changing the slider value
        try:
            index = int(self.image_textbox.text())
            index = max(0, min(index, len(self.imagePaths) - 1))  # Ensure valid index
            self.navigate_to_image(index)
        except ValueError:
            pass  # Ignore non-integer input
    
    def resize_image_textbox(self):
        font_metrics = self.image_textbox.fontMetrics()
        current_text = self.image_textbox.text() or "0"
        text_width = font_metrics.horizontalAdvance(current_text)
        if self.imagePaths:
            max_index_text = str(max(0, len(self.imagePaths) - 1))
        else:
            max_index_text = "000"
        range_width = font_metrics.horizontalAdvance(max_index_text)
        minimum_width = font_metrics.horizontalAdvance("000")
        padding = 20  # extra padding
        new_width = max(text_width, range_width, minimum_width) + padding
        self.image_textbox.setFixedWidth(new_width)

    def get_cached_image(self, index, *, apply_crop=None):
        if apply_crop is None:
            apply_crop = self.should_apply_crop_in_display()
        image_path = self.imagePaths[index]
        cache_key = (image_path, bool(apply_crop))
        cached_image = self.image_cache.get(cache_key)
        if cached_image is not None:
            self.image_cache.move_to_end(cache_key)
            return cached_image

        raw_q_image = self.get_cached_raw_image(image_path)
        crop_state = self.current_image_edit_crop_state(index=index)
        cached_image = apply_image_adjustments_to_qimage(
            raw_q_image,
            self.current_image_edit_total_exposure(index=index, image_path=image_path),
            self.image_edit_contrast,
            crop_state,
            apply_crop=bool(apply_crop),
        )
        self.image_cache[cache_key] = cached_image
        self.image_cache.move_to_end(cache_key)

        while len(self.image_cache) > self.image_cache_size:
            self.image_cache.popitem(last=False)

        return cached_image

    def get_cached_pixmap(self, index, *, apply_crop=None):
        if apply_crop is None:
            apply_crop = self.should_apply_crop_in_display()
        image_path = self.imagePaths[index]
        cache_key = (image_path, bool(apply_crop))
        cached_pixmap = self.pixmap_cache.get(cache_key)
        if cached_pixmap is not None:
            self.pixmap_cache.move_to_end(cache_key)
            return cached_pixmap

        cached_pixmap = QPixmap.fromImage(self.get_cached_image(index, apply_crop=apply_crop))
        self.pixmap_cache[cache_key] = cached_pixmap
        self.pixmap_cache.move_to_end(cache_key)

        while len(self.pixmap_cache) > self.pixmap_cache_size:
            self.pixmap_cache.popitem(last=False)

        return cached_pixmap

    def get_display_slots(self, current_index):
        total_images = len(self.imagePaths)
        if total_images <= 0:
            return []

        count = max(1, min(self.viewer_image_count, 3))
        if count == 1:
            return [current_index]
        if count == 2:
            before_index = current_index - 1 if current_index > 0 else None
            return [before_index, current_index]

        before_index = current_index - 1 if current_index > 0 else None
        after_index = current_index + 1 if current_index < total_images - 1 else None
        return [before_index, current_index, after_index]

    def is_viewer_split_vertical(self):
        return int(getattr(self, "viewer_image_count", 1)) in (2, 3) and str(getattr(self, "viewer_split_orientation", "horizontal")) == "vertical"

    def clear_context_pixmaps(self):
        for item in self.context_pixmap_items:
            self.scene.removeItem(item)
        self.context_pixmap_items = []
        for item in self.placeholder_items:
            self.scene.removeItem(item)
        self.placeholder_items = []

    def update_display_pixmaps(self, current_index, *, apply_crop=None):
        if apply_crop is None:
            apply_crop = self.should_apply_crop_in_display()
        display_slots = self.get_display_slots(current_index)
        if not display_slots:
            return None

        spacing = 30
        layout_vertical = self.is_viewer_split_vertical()
        active_image = self.get_cached_image(current_index, apply_crop=apply_crop)
        active_pixmap = self.get_cached_pixmap(current_index, apply_crop=apply_crop)
        slot_width = active_pixmap.width()
        slot_height = active_pixmap.height()

        entries = []
        current_left = 0
        current_top = 0
        for display_index in display_slots:
            if display_index is None:
                entries.append((None, None, None, current_left, current_top))
                if layout_vertical:
                    current_top += slot_height + spacing
                else:
                    current_left += slot_width + spacing
                continue

            q_image = self.get_cached_image(display_index, apply_crop=apply_crop)
            pixmap = self.get_cached_pixmap(display_index, apply_crop=apply_crop)
            entries.append((display_index, pixmap, q_image, current_left, current_top))
            if layout_vertical:
                current_top += slot_height + spacing
            else:
                current_left += slot_width + spacing

        active_entry = next((entry for entry in entries if entry[0] == current_index), entries[-1])
        active_x = active_entry[3]
        active_y = active_entry[4]

        if hasattr(self, 'pixmap_item'):
            self.pixmap_item.setPixmap(active_pixmap)
        else:
            self.pixmap_item = self.scene.addPixmap(active_pixmap)
        self.pixmap_item.setZValue(-100)
        self.pixmap_item.setPos(active_x, active_y)

        self.clear_context_pixmaps()
        for display_index, pixmap, _, x_pos, y_pos in entries:
            if display_index is None:
                border_color = QColor(160, 160, 160, 180) if darkdetect.isDark() else QColor(175, 175, 175, 180)
                fill_color = QColor(255, 255, 255, 18) if darkdetect.isDark() else QColor(0, 0, 0, 10)
                placeholder_item = self.scene.addRect(
                    x_pos,
                    y_pos,
                    slot_width,
                    slot_height,
                    QPen(border_color, 1, Qt.DashLine),
                    QBrush(fill_color),
                )
                placeholder_item.setZValue(-110)
                self.placeholder_items.append(placeholder_item)
                continue
            if display_index == current_index:
                continue
            context_item = self.scene.addPixmap(pixmap)
            context_item.setZValue(-120)
            context_item.setPos(x_pos, y_pos)
            self.context_pixmap_items.append(context_item)

        scene_rect = self.pixmap_item.sceneBoundingRect()
        for item in self.context_pixmap_items:
            scene_rect = scene_rect.united(item.sceneBoundingRect())
        for item in self.placeholder_items:
            scene_rect = scene_rect.united(item.sceneBoundingRect())
        self.view.setSceneRect(scene_rect)
        self.displayed_image_edit_crop_applied = bool(apply_crop)
        self.image_width = self.get_raw_image_dimensions(current_index)[0]
        return active_image

    def displayMarkedRegions(self):
        # Delegate circle redraw to the controller so add/edit/delete and frame
        # redraw all use the same anchoring + cell-preservation path.
        self.cell_controller.redraw_current_cells()

    def interpolate_and_displayMarkedRegions(self, index, preview=False):
        if (not self.cell_items) and (not self.keyframe_list):
            if self.rendered_cell_items:
                for item in list(self.rendered_cell_items):
                    if shiboken6.isValid(item) and item.scene() is self.scene:
                        self.scene.removeItem(item)
                self.rendered_cell_items = []
            return
        self.cell_controller.redraw_interpolated_cells(index, preview=preview)

    def anchor_cell_items_to_current_image(self, cell_items):
        return self.cell_controller.anchor_to_current_image(cell_items)

    def updateRadiusTextbox(self):
        if self.circle_radius is not None:
            self.radius_textbox.setText(self.format_numeric_value(self.circle_radius))
            if hasattr(self, "circle_radius_spinbox"):
                self.circle_radius_spinbox.blockSignals(True)
                self.circle_radius_spinbox.setValue(float(self.circle_radius))
                self.circle_radius_spinbox.blockSignals(False)
            if hasattr(self, "grid_radius_spinbox"):
                self.grid_radius_spinbox.blockSignals(True)
                self.grid_radius_spinbox.setValue(float(self.circle_radius))
                self.grid_radius_spinbox.blockSignals(False)
        else:
            self.radius_textbox.clear()  # Clear the text box if circle radius is None

    def updateCircleRadius_from_textedit(self):
        try:
            radius = float(self.radius_textbox.text())
            if radius != self.circle_radius:
                self.circle_radius = radius
                if self.tool_mode in {'select', 'edit-new', 'grid', 'edit-group'}:
                    self.update_grid_preview()
                self.sync_tool_options_panel()
        except ValueError:
            pass  # Ignore non-integer input


    def updateZoomTextbox(self):
        zoom_factor = self.view.transform().m11()  # Current zoom level
        self.zoom_textbox.setText(f"{zoom_factor * 100:.0f}")  # Update the zoom level text box

    def updateZoomLevel(self):
        try:
            zoom_percentage = float(self.zoom_textbox.text())
            zoom_factor = zoom_percentage / 100.0
            self.view.setTransform(QTransform().scale(zoom_factor, zoom_factor))
            self.updateZoomTextbox()  # Update the zoom text box after manual change
        except ValueError:
            pass  # Ignore non-numeric input
    
    def updateButtonStates(self):
        # Update left button state
        if (self.image_slider.value() <= 0) or self.output_state or (not self.imagePaths):
            self.leftButton.setEnabled(False)
        else:
            self.leftButton.setEnabled(True)

        # Update right button state
        if (self.image_slider.value() >= len(self.imagePaths)-1) or self.output_state or (not self.imagePaths):
            self.rightButton.setEnabled(False)
        else:
            self.rightButton.setEnabled(True)

        if self.output_state or (not self.imagePaths):
            self.keyframe_toggle_button.setEnabled(False)
            self.flag_toggle_button.setEnabled(False)
            self.zoom_slider.setEnabled(False)
        else:
            self.keyframe_toggle_button.setEnabled(True)
            self.flag_toggle_button.setEnabled(True)
            self.zoom_slider.setEnabled(True)

    def set_undo_status(self):
        if not getattr(self, "undo_redo_enabled", True):
            self.undo_action.setEnabled(False)
            return
        if (not hasattr(self, "undo_stack")) or (not shiboken6.isValid(self.undo_stack)):
            return
        if self.undo_stack.canUndo():
            self.undo_action.setEnabled(True)
        else:
            self.undo_action.setEnabled(False)

    def set_redo_status(self):
        if not getattr(self, "undo_redo_enabled", True):
            self.redo_action.setEnabled(False)
            return
        if (not hasattr(self, "undo_stack")) or (not shiboken6.isValid(self.undo_stack)):
            return
        if self.undo_stack.canRedo():
            self.redo_action.setEnabled(True)
        else:
            self.redo_action.setEnabled(False)

    def undo(self):
        if not getattr(self, "undo_redo_enabled", True):
            return
        if (not hasattr(self, "undo_stack")) or (not shiboken6.isValid(self.undo_stack)):
            return
        if self.undo_stack.canUndo():
            self.cancel_transient_history_state()
            action_text = self.undo_stack.undoText() or "Undo"
            self.log(f"Undo: {action_text}")
            self.undo_stack.undo()
            self.set_undo_status()
            self.set_redo_status()

    def redo(self):
        if not getattr(self, "undo_redo_enabled", True):
            return
        if (not hasattr(self, "undo_stack")) or (not shiboken6.isValid(self.undo_stack)):
            return
        if self.undo_stack.canRedo():
            self.cancel_transient_history_state()
            action_text = self.undo_stack.redoText() or "Redo"
            self.log(f"Redo: {action_text}")
            self.undo_stack.redo()
            self.set_undo_status()
            self.set_redo_status()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Z:
            if (event.modifiers() & Qt.ControlModifier) and (event.modifiers() & Qt.ShiftModifier):
                if self.redo_action.isEnabled():
                    self.redo_action.trigger()  # Shift + Ctrl + Z for redo
                    self.key_press_toolbutton_highlight(self.redo_action) # simulate pressing button highlight for visual cue
            elif (event.modifiers() & Qt.ControlModifier):
                if self.undo_action.isEnabled():
                    self.undo_action.trigger()  # Ctrl + Z for undo
                    self.key_press_toolbutton_highlight(self.undo_action) # simulate pressing button highlight for visual cue
            else:
                if self.pan_tool_action.isEnabled():
                    self.pan_tool_action.trigger()  # Z for Zoom and Pan
                    self.key_press_toolbutton_highlight(self.pan_tool_action)
        elif event.key() == Qt.Key_S:
            # Select Add cell key
            if self.select_tool_action.isEnabled():
                self.select_tool_action.trigger() # S for Add Cell
                self.key_press_toolbutton_highlight(self.select_tool_action)
        elif event.key() == Qt.Key_D:
            # Select Add cell key
            if self.deselect_tool_action.isEnabled():
                self.deselect_tool_action.trigger() # D for Delete Cells
                self.key_press_toolbutton_highlight(self.deselect_tool_action)
        elif event.key() == Qt.Key_G:
            if self.grid_tool_action.isEnabled():
                self.grid_tool_action.trigger()
                self.key_press_toolbutton_highlight(self.grid_tool_action)
        elif event.key() == Qt.Key_E:
            # Select Add cell key
            if self.edit_tool_action.isEnabled():
                self.edit_tool_action.trigger() # E for Delete Cells
                self.key_press_toolbutton_highlight(self.edit_tool_action)
        elif event.key() == Qt.Key_A:
            # Select Default Cursor Key
            if self.reset_cursor_action.isEnabled():
                self.reset_cursor_action.trigger() # A for Delete Cells
                self.key_press_toolbutton_highlight(self.reset_cursor_action)
        elif event.key() == Qt.Key_Comma:
            if self.leftButton.isEnabled():
                self.leftButton.click()
                self.key_press_button_highlight(self.leftButton)
        elif event.key() == Qt.Key_Period:
            if self.rightButton.isEnabled():
                self.rightButton.click()
                self.key_press_button_highlight(self.rightButton)

        elif (event.key() == Qt.Key_Space) and (self.space_held == False):
            # Temporarily switch to zoom and pan

            if self.imagePaths:
                # Store original_tool_mode in temporary data
                self.temporary_event_data["original_tool_mode"] = self.tool_mode

                for key, value in self.tool_name_dict.items():
                    if key in ['pan', self.tool_mode]:
                        value.setEnabled(True)
                    elif (self.cell_controller.is_any_edit_mode()) and (key in ["edit-choose", "edit-new"]):
                        value.setEnabled(True)
                    else:
                        value.setEnabled(False)

                if self.pan_tool_action.isEnabled():
                    self.enter_temporary_pan_mode()
                    self.key_press_toolbutton_highlight(self.pan_tool_action)

                self.space_held = True

        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:

            if self.imagePaths:
                # Retrieve the original tool mode from the temporary data dict
                self.space_held = False

                original_tool_mode = self.temporary_event_data.pop("original_tool_mode", None)
                if original_tool_mode is None:
                    for key, value in self.tool_name_dict.items():
                        value.setEnabled(True)
                    return

                if original_tool_mode == "pan":
                    self.pan_tool_action.trigger()
                    self.key_press_toolbutton_highlight(self.pan_tool_action)
                elif original_tool_mode == "cursor":
                    self.apply_cursor_tool_ui()
                    self.key_press_toolbutton_highlight(self.reset_cursor_action)
                elif original_tool_mode == "select":
                    self.apply_select_tool_ui(preserve_preview=True)
                    self.key_press_toolbutton_highlight(self.select_tool_action)
                elif original_tool_mode == "deselect":
                    self.apply_deselect_tool_ui()
                    self.key_press_toolbutton_highlight(self.deselect_tool_action)
                elif original_tool_mode in ["edit-choose", "edit-new", "edit-group"]:
                    self.temporary_event_data["previous_edit_mode"] = original_tool_mode
                    self.editTool(self.edit_tool_action.isChecked())
                    self.key_press_toolbutton_highlight(self.edit_tool_action)
                elif original_tool_mode == "grid":
                    self.apply_grid_tool_ui(preserve_preview=True)
                    self.key_press_toolbutton_highlight(self.grid_tool_action)
                elif original_tool_mode == "image-edit":
                    self.apply_image_edit_tool_ui()
                    self.key_press_toolbutton_highlight(self.image_edit_action)
                    

                for key, value in self.tool_name_dict.items():
                    value.setEnabled(True)

        else:
            super().keyReleaseEvent(event)

    def outputData(self):
        if not self.imagePaths:
            self.log("No images loaded")
            return

        self.pending_analysis_before_state = self.capture_data_state()
        self.analysis_progress_start_index = int(getattr(self, "last_committed_image_index", self.image_index))
        self.analysis_progress_navigation_suppressed = True
        self.log("Start analyzing")

        list_of_cell_items = self.out_put_interpolation()

        self.worker = Image_analysis_thread(
            None,
            self.imagePaths.copy(),
            self.imageNames.copy(),
            list_of_cell_items,
            self.flagframe_list,
            image_edit_exposure=self.image_edit_exposure,
            image_edit_contrast=self.image_edit_contrast,
            image_edit_uniform_exposure_offsets=copy.deepcopy(getattr(self, "image_edit_uniform_exposure_offsets", {})),
            image_edit_crop_state=self.current_image_edit_crop_state(),
            freeze_finder_width=self.freeze_finder_width,
            freeze_finder_prominence=self.freeze_finder_prominence,
            freeze_finder_tail_extend_points=self.freeze_finder_tail_extend_points,
            convolution_half_window_points=self.convolution_half_window_points,
            convolution_ramp_points=self.convolution_ramp_points,
            freeze_finder_detect_brightening=self.freeze_finder_detect_brightening,
        )
        self.worker.analysis_done.connect(self.onAnalysisDone)
        self.updateButtonStates()
        self.zoom_slider.setValue(1)
        
        self.reset_cursor_action.trigger()
        self.select_tool_action.setEnabled(False)
        self.grid_tool_action.setEnabled(False)
        self.deselect_tool_action.setEnabled(False)
        self.edit_tool_action.setEnabled(False)
        self.remove_selected_action.setEnabled(False)
        self.new_session_action.setEnabled(False)

        self.image_slider.setEnabled(False)
        self.image_slider.setValue(0)
        self.timer = time.time()
        self.output_state = True
        self.update_session_actions_state()
        self.worker.start()
        self.worker.finished.connect(self.onThreadFinished)

    def out_put_interpolation(self):
        list_of_cell_items = []
        for an_image_index in range(len(self.imagePaths)):
            list_of_cell_items.append(self.keyframe_interpolation(an_image_index))
        
        return list_of_cell_items
            
    def onAnalysisDone(self, index, results):
        # Finish anayzing each image
        # self.log(f"Analyzed image {results['file_name']}")
        self.enqueue_analysis_progress_frame(index)
        

    def onThreadFinished(self):
        # Finish anayzing all images
        before_state = self.pending_analysis_before_state
        self.pending_analysis_before_state = None
        if hasattr(self, "analysis_progress_timer"):
            self.analysis_progress_timer.stop()
        self.flush_pending_analysis_progress()
        worker = self.worker
        endTime = time.time()
        elapsed_time = endTime - self.timer
        self.log("Analysis complete")
        if getattr(worker, 'freeze_output_path', None):
            self.log(f"Saved freeze detection output at {worker.freeze_output_path}")
        self.log(f"Time used: {elapsed_time:.3f} seconds")
        self.last_grayscale_output_path = getattr(worker, 'filePath', None)
        self.last_freeze_output_path = getattr(worker, 'freeze_output_path', None)
        self.timer = None
        self.output_state = False
        self.image_slider.setEnabled(True)
        self.updateButtonStates()
        self.select_tool_action.setEnabled(True)
        self.grid_tool_action.setEnabled(True)
        self.deselect_tool_action.setEnabled(True)
        self.edit_tool_action.setEnabled(True)
        self.update_session_actions_state()
        self.grayscale_results_headers = getattr(worker, 'grayscale_result_headers', [])
        self.grayscale_results_rows = getattr(worker, 'grayscale_result_rows', [])
        self.freeze_results_headers = getattr(worker, 'freeze_result_headers', [])
        self.freeze_results_rows = getattr(worker, 'freeze_result_rows', [])
        self.invalidate_temperature_sync_results("analysis results changed")
        self.update_results_tables()
        if self.grayscale_results_headers or self.freeze_results_headers:
            if hasattr(self, "results_table_tabs"):
                self.results_table_tabs.setCurrentIndex(0 if self.grayscale_results_headers else 1)
            self.show_dock_widget(self.results_tables_dock)
        if self.grayscale_results_rows:
            self.show_dock_widget(self.grayscale_plot_dock)
        final_frame = int(getattr(self, "last_committed_image_index", self.image_index))
        start_frame = self.analysis_progress_start_index
        self.analysis_progress_navigation_suppressed = False
        self.analysis_progress_start_index = None
        self.pending_analysis_progress_index = None
        if (
            start_frame is not None
            and not self.history_restoring
            and int(start_frame) != final_frame
        ):
            self.log(f"Change Frame: {int(start_frame)} -> {final_frame}")
            self.push_navigation_history("Change Frame", int(start_frame), final_frame)
        if before_state is not None:
            self.push_data_history("Run Analysis", before_state)
        worker.deleteLater()
        self.worker = None


    def key_press_toolbutton_highlight(self, an_action):
        toolbutton = self.toolbar.widgetForAction(an_action)
        if toolbutton:
            # Set a unique object name for styling
            toolbutton.setObjectName("triggeredButton")
            current_stylesheet = self.toolbar.styleSheet()
            if darkdetect.isDark():
                style_sheet_to_add = "QToolButton#triggeredButton {background-color: rgba(10, 132, 255, 120)}"
            else:
                style_sheet_to_add = "QToolButton#triggeredButton {background-color: rgba(0, 122, 255, 200)}"
            self.toolbar.setStyleSheet(current_stylesheet + style_sheet_to_add)
            QTimer.singleShot(150, lambda: self.reset_toolbar_stylesheet())
    
    def key_press_button_highlight(self, button):
        if button:
            # Set a unique object name for styling
            button.setObjectName("triggeredButton")
            current_stylesheet = button.styleSheet()
            if darkdetect.isDark():
                style_sheet_to_add = "QPushButton#triggeredButton {background-color: rgba(10, 132, 255, 120)}"
            else:
                style_sheet_to_add = "QPushButton#triggeredButton {background-color: rgba(0, 122, 255, 200)}"
            button.setStyleSheet(current_stylesheet + style_sheet_to_add)
            QTimer.singleShot(150, lambda: self.reset_button_stylesheet())
            button.setObjectName(None)

    def reset_toolbar_stylesheet(self, theme=None):
        for action in self.toolbar.actions():
            button = self.toolbar.widgetForAction(action)
            button.setObjectName(None)
        if theme == "Dark" or darkdetect.isDark():
            self.toolbar.setStyleSheet(icescopy_stylesheet.darkmode_toolbar_style_sheet)
        else:
            self.toolbar.setStyleSheet(icescopy_stylesheet.light_mode_toolbar_style_sheet)
    
    def reset_slider_stylesheet(self, theme=None):
        if darkdetect.isDark():
            self.image_slider.setStyleSheet(icescopy_stylesheet.dark_mode_time_line_slider_style)
            self.zoom_slider.setStyleSheet(icescopy_stylesheet.dark_zoom_slider_stylesheet)
        else:
            self.image_slider.setStyleSheet(icescopy_stylesheet.light_mode_time_line_slider_style)
            self.zoom_slider.setStyleSheet(icescopy_stylesheet.light_zoom_slider_stylesheet)
        self.image_slider.sync_timeline_geometry()
    
    def reset_status_bar_stylesheet(self, theme=None):
        if darkdetect.isDark():
            self.statusBar.setStyleSheet(icescopy_stylesheet.dark_mode_status_bar_stylesheet)
            self.radius_textbox.setStyleSheet(icescopy_stylesheet.dark_mode_line_edit_style_sheet)
            self.zoom_textbox.setStyleSheet(icescopy_stylesheet.dark_mode_line_edit_style_sheet)
            self.image_textbox.setStyleSheet(icescopy_stylesheet.dark_mode_line_edit_style_sheet)
        else:
            self.statusBar.setStyleSheet(icescopy_stylesheet.light_mode_status_bar_stylesheet)
            self.radius_textbox.setStyleSheet(icescopy_stylesheet.light_mode_line_edit_style_sheet)
            self.zoom_textbox.setStyleSheet(icescopy_stylesheet.light_mode_line_edit_style_sheet)
            self.image_textbox.setStyleSheet(icescopy_stylesheet.light_mode_line_edit_style_sheet)
    
    def reset_button_stylesheet(self, theme=None):
        if darkdetect.isDark():
            self.keyframe_toggle_button.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.leftButton.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.rightButton.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.flag_toggle_button.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
        else:
            self.keyframe_toggle_button.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.leftButton.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.rightButton.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.flag_toggle_button.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)

    def toolbar_icon(self, mode_folder, icon_name):
        return QIcon(os.path.join(resources_dir, "tool_bar", mode_folder, "large", icon_name))

    def reset_toolbar_icon(self, theme=None):
        mode_folder = "dark-mode" if darkdetect.isDark() else "light-mode"
        self.preferences_action.setIcon(self.toolbar_icon(mode_folder, "gear.svg"))
        self.add_images_action.setIcon(self.toolbar_icon(mode_folder, "image-multiple-add.svg"))
        self.new_session_action.setIcon(self.toolbar_icon(mode_folder, "document-new-filled.svg"))
        self.open_session_action.setIcon(self.toolbar_icon(mode_folder, "folder-document.svg"))
        self.remove_selected_action.setIcon(self.toolbar_icon(mode_folder, "image-multiple-remove.svg"))
        self.clear_images_action.setIcon(self.toolbar_icon(mode_folder, "image-multiple-trash.svg"))
        self.save_session_action.setIcon(self.toolbar_icon(mode_folder, "save-document.svg"))
        self.run_analysis_action.setIcon(self.toolbar_icon(mode_folder, "media-play-filled.svg"))
        self.output_results_action.setIcon(self.toolbar_icon(mode_folder, "document-action-arrow-down-filled.svg"))
        self.sort_images_action.setIcon(self.toolbar_icon(mode_folder, "sort.svg"))
        self.sample_manager_action.setIcon(self.toolbar_icon(mode_folder, "menu-hamburger-tag.svg"))
        self.image_edit_action.setIcon(self.toolbar_icon(mode_folder, "image-multiple-edit-filled.svg"))
        self.viewer_single_action.setIcon(self.toolbar_icon(mode_folder, "page-landscape-number-1.svg"))
        self.viewer_double_action.setIcon(self.toolbar_icon(mode_folder, "page-landscape-number-2.svg"))
        self.viewer_triple_action.setIcon(self.toolbar_icon(mode_folder, "page-landscape-number-3.svg"))
        self.update_viewer_orientation_toggle_action(mode_folder=mode_folder)
        self.undo_action.setIcon(self.toolbar_icon(mode_folder, "command-undo.svg"))
        self.redo_action.setIcon(self.toolbar_icon(mode_folder, "command-redo.svg"))
        self.reset_cursor_action.setIcon(self.toolbar_icon(mode_folder, "pointer.svg"))
        self.select_tool_action.setIcon(self.toolbar_icon(mode_folder, "media-record-add-filled.svg"))
        self.grid_tool_action.setIcon(self.toolbar_icon(mode_folder, "media-record-table-filled.svg"))
        self.edit_tool_action.setIcon(self.toolbar_icon(mode_folder, "media-record-edit-filled.svg"))
        self.deselect_tool_action.setIcon(self.toolbar_icon(mode_folder, "media-record-remove-filled.svg"))
        self.pan_tool_action.setIcon(self.toolbar_icon(mode_folder, "hand-left.svg"))

    def update_viewer_mode_actions(self):
        self.viewer_single_action.setChecked(self.viewer_image_count == 1)
        self.viewer_double_action.setChecked(self.viewer_image_count == 2)
        self.viewer_triple_action.setChecked(self.viewer_image_count == 3)
        self.update_viewer_orientation_toggle_action()

    def update_viewer_orientation_toggle_action(self, mode_folder=None):
        if mode_folder is None:
            mode_folder = "dark-mode" if darkdetect.isDark() else "light-mode"

        if self.is_viewer_split_vertical():
            self.viewer_orientation_toggle_action.setText("Stack Left to Right")
            self.viewer_orientation_toggle_action.setToolTip("Switch two- and three-image view to left-right layout")
            self.viewer_orientation_toggle_action.setIcon(self.toolbar_icon(mode_folder, "view-separate-vertical.svg"))
        else:
            self.viewer_orientation_toggle_action.setText("Stack Top to Bottom")
            self.viewer_orientation_toggle_action.setToolTip("Switch two- and three-image view to top-down layout")
            self.viewer_orientation_toggle_action.setIcon(self.toolbar_icon(mode_folder, "view-separate-horizontal.svg"))
        self.viewer_orientation_toggle_action.setEnabled(
            bool(getattr(self, "session_active", False))
            and (not getattr(self, "output_state", False))
            and int(getattr(self, "viewer_image_count", 1)) in (2, 3)
        )

    def set_viewer_image_count(self, count):
        self.viewer_image_count = count
        self.update_viewer_mode_actions()
        self.log(f"Viewer layout: show {count} image(s)")
        if self.imagePaths:
            self.updateImage(self.image_index)

    def toggle_viewer_split_orientation(self):
        self.viewer_split_orientation = "vertical" if not self.is_viewer_split_vertical() else "horizontal"
        self.update_viewer_orientation_toggle_action()
        layout_label = "top-down" if self.is_viewer_split_vertical() else "left-right"
        self.log(f"Viewer split layout: {layout_label}")
        if self.imagePaths and self.viewer_image_count in (2, 3):
            self.updateImage(self.image_index)

    def update_toggle_keyframe_button_icon(self, theme=None):
        if darkdetect.isDark():
            if self.image_index in self.image_slider.keyframes:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'diamond_key.png')))
            else:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'diamond.png')))
        else:
            if self.image_index in self.image_slider.keyframes:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'diamond_key_2.png')))
            else:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'diamond_2.png')))
    
    def update_toggle_flagging_button_icon(self, theme=None):
        if darkdetect.isDark():
            if self.image_index in self.image_slider.flaggedframes:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'flag_red.png')))
            else:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'flag.png')))
        else:
            if self.image_index in self.image_slider.flaggedframes:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'flag_red_2.png')))
            else:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'flag_2.png')))

    def reset_button_icon(self, theme=None):
        self.update_toggle_keyframe_button_icon()
        self.update_toggle_flagging_button_icon()
        if darkdetect.isDark():
            self.leftButton.setIcon(QIcon(os.path.join(ui_images_dir, "caret-left.png")))
            self.rightButton.setIcon(QIcon(os.path.join(ui_images_dir, 'caret-right.png')))
        else:
            self.leftButton.setIcon(QIcon(os.path.join(ui_images_dir, 'caret-left_2.png')))
            self.rightButton.setIcon(QIcon(os.path.join(ui_images_dir, 'caret-right_2.png')))

    def update_cell_items_selectable_state(self): # update items in the scenes, called when changing tools.
        self.cell_controller.update_scene_selectable_state()

    def unselect_all_cell_items(self):
        self.cell_controller.clear_scene_selection()
    
    def update_cell_items_cell_ids(self): # update items in the data list, called by the self.displayMarkedRegions()
        self.cell_controller.renumber_cell_items()
    
    def reset_cell_items_edit_chosen(self): # update items in the data list, called by the self.displayMarkedRegions()
        self.cell_controller.reset_edit_chosen()
        self.refresh_grayscale_plot()

    def switch_light_dark_mode(self, theme=None):
        self.reset_toolbar_stylesheet(theme)
        self.reset_toolbar_icon(theme)
        self.reset_slider_stylesheet(theme)
        self.reset_button_icon(theme)
        self.reset_status_bar_stylesheet(theme)
        self.reset_button_stylesheet(theme)

    def resizeEvent(self, event):
        super().resizeEvent(event)  # Call the base class resizeEvent
        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()

    def closeEvent(self, event):
        super().closeEvent(event)

    def load_preferences_from_xml(self):
        tree = ET.parse(os.path.join(resources_dir,"preferences.xml"))
        root = tree.getroot()
        
        preferences = {}

        circle_radius_element = root.find('DefaultCircleRadius')
        if circle_radius_element is not None and circle_radius_element.text is not None:
            preferences['DefaultCircleRadius'] = float(circle_radius_element.text)

        maximum_zoom_element = root.find('MaximumZoom')
        if maximum_zoom_element is not None and maximum_zoom_element.text is not None:
            preferences['MaximumZoom'] = float(maximum_zoom_element.text)
        
        pen_width_element = root.find('PenWidth')
        if pen_width_element is not None and pen_width_element.text is not None:
            preferences['PenWidth'] = float(pen_width_element.text)

        dot_size_element = root.find('DotSize')
        if dot_size_element is not None and dot_size_element.text is not None:
            preferences['DotSize'] = float(dot_size_element.text)

        slide_maxzoom_element = root.find('SliderMaxZoomPixelInterval')
        if slide_maxzoom_element is not None and slide_maxzoom_element.text is not None:
            preferences['SliderMaxZoomPixelInterval'] = float(slide_maxzoom_element.text)
        
        slide_tickpix_element = root.find('SliderTickPixelInterval')
        if slide_tickpix_element is not None and slide_tickpix_element.text is not None:
            preferences['SliderTickPixelInterval'] = float(slide_tickpix_element.text)

        undo_limit_element = root.find('UndoLimit')
        if undo_limit_element is not None and undo_limit_element.text is not None:
            preferences['UndoLimit'] = int(float(undo_limit_element.text))

        sample_name_pattern_element = root.find('SampleNamePattern')
        if sample_name_pattern_element is not None and sample_name_pattern_element.text is not None:
            preferences['SampleNamePattern'] = sample_name_pattern_element.text

        viewer_image_count_element = root.find('ViewerImageCount')
        if viewer_image_count_element is not None and viewer_image_count_element.text is not None:
            preferences['ViewerImageCount'] = int(float(viewer_image_count_element.text))

        sort_mode_element = root.find('SortMode')
        if sort_mode_element is not None and sort_mode_element.text is not None:
            preferences['SortMode'] = sort_mode_element.text

        grid_rows_element = root.find('GridRows')
        if grid_rows_element is not None and grid_rows_element.text is not None:
            preferences['GridRows'] = int(float(grid_rows_element.text))

        grid_columns_element = root.find('GridColumns')
        if grid_columns_element is not None and grid_columns_element.text is not None:
            preferences['GridColumns'] = int(float(grid_columns_element.text))

        grid_horizontal_pitch_element = root.find('GridHorizontalPitch')
        if grid_horizontal_pitch_element is not None and grid_horizontal_pitch_element.text is not None:
            preferences['GridHorizontalPitch'] = float(grid_horizontal_pitch_element.text)

        grid_vertical_pitch_element = root.find('GridVerticalPitch')
        if grid_vertical_pitch_element is not None and grid_vertical_pitch_element.text is not None:
            preferences['GridVerticalPitch'] = float(grid_vertical_pitch_element.text)

        grid_rotation_degrees_element = root.find('GridRotationDegrees')
        if grid_rotation_degrees_element is not None and grid_rotation_degrees_element.text is not None:
            preferences['GridRotationDegrees'] = float(grid_rotation_degrees_element.text)

        grid_cell_id_direction_element = root.find('GridCellIdDirection')
        if grid_cell_id_direction_element is not None and grid_cell_id_direction_element.text is not None:
            preferences['GridCellIdDirection'] = str(grid_cell_id_direction_element.text)

        radius_wheel_step_element = root.find('RadiusWheelStep')
        if radius_wheel_step_element is not None and radius_wheel_step_element.text is not None:
            preferences['RadiusWheelStep'] = float(radius_wheel_step_element.text)

        grid_pitch_wheel_step_element = root.find('GridPitchWheelStep')
        if grid_pitch_wheel_step_element is not None and grid_pitch_wheel_step_element.text is not None:
            preferences['GridPitchWheelStep'] = float(grid_pitch_wheel_step_element.text)

        grid_tilt_wheel_step_element = root.find('GridTiltWheelStep')
        if grid_tilt_wheel_step_element is not None and grid_tilt_wheel_step_element.text is not None:
            preferences['GridTiltWheelStep'] = float(grid_tilt_wheel_step_element.text)

        freeze_finder_width_element = root.find('FreezeFinderWidth')
        if freeze_finder_width_element is not None and freeze_finder_width_element.text is not None:
            preferences['FreezeFinderWidth'] = float(freeze_finder_width_element.text)

        freeze_finder_prominence_element = root.find('FreezeFinderProminence')
        if freeze_finder_prominence_element is not None and freeze_finder_prominence_element.text is not None:
            preferences['FreezeFinderProminence'] = float(freeze_finder_prominence_element.text)

        freeze_finder_tail_extend_points_element = root.find('FreezeFinderTailExtendPoints')
        if (
            freeze_finder_tail_extend_points_element is not None
            and freeze_finder_tail_extend_points_element.text is not None
        ):
            preferences['FreezeFinderTailExtendPoints'] = int(float(freeze_finder_tail_extend_points_element.text))

        convolution_half_window_points_element = root.find('ConvolutionHalfWindowPoints')
        if (
            convolution_half_window_points_element is not None
            and convolution_half_window_points_element.text is not None
        ):
            preferences['ConvolutionHalfWindowPoints'] = int(float(convolution_half_window_points_element.text))

        convolution_ramp_points_element = root.find('ConvolutionRampPoints')
        if convolution_ramp_points_element is not None and convolution_ramp_points_element.text is not None:
            preferences['ConvolutionRampPoints'] = int(float(convolution_ramp_points_element.text))

        freeze_finder_detect_brightening_element = root.find('FreezeFinderDetectBrightening')
        if (
            freeze_finder_detect_brightening_element is not None
            and freeze_finder_detect_brightening_element.text is not None
        ):
            preferences['FreezeFinderDetectBrightening'] = (
                str(freeze_finder_detect_brightening_element.text).strip().lower() in {"1", "true", "yes", "on"}
            )

        temperature_cycle_warmup_hysteresis_c_element = root.find('TemperatureCycleWarmupHysteresisC')
        if (
            temperature_cycle_warmup_hysteresis_c_element is not None
            and temperature_cycle_warmup_hysteresis_c_element.text is not None
        ):
            preferences['TemperatureCycleWarmupHysteresisC'] = float(
                temperature_cycle_warmup_hysteresis_c_element.text
            )

        timeseries_palette_element = root.find('TimeseriesPalette')
        if timeseries_palette_element is not None and timeseries_palette_element.text is not None:
            preferences['TimeseriesPalette'] = timeseries_palette_element.text

        timeseries_trace_line_width_element = root.find('TimeseriesTraceLineWidth')
        if timeseries_trace_line_width_element is not None and timeseries_trace_line_width_element.text is not None:
            preferences['TimeseriesTraceLineWidth'] = float(timeseries_trace_line_width_element.text)

        timeseries_convolution_line_width_element = root.find('TimeseriesConvolutionLineWidth')
        if (
            timeseries_convolution_line_width_element is not None
            and timeseries_convolution_line_width_element.text is not None
        ):
            preferences['TimeseriesConvolutionLineWidth'] = float(timeseries_convolution_line_width_element.text)

        timeseries_freeze_line_color_element = root.find('TimeseriesFreezeLineColor')
        if timeseries_freeze_line_color_element is not None and timeseries_freeze_line_color_element.text is not None:
            preferences['TimeseriesFreezeLineColor'] = timeseries_freeze_line_color_element.text

        timeseries_freeze_line_width_element = root.find('TimeseriesFreezeLineWidth')
        if timeseries_freeze_line_width_element is not None and timeseries_freeze_line_width_element.text is not None:
            preferences['TimeseriesFreezeLineWidth'] = float(timeseries_freeze_line_width_element.text)

        timeseries_current_frame_color_element = root.find('TimeseriesCurrentFrameColor')
        if (
            timeseries_current_frame_color_element is not None
            and timeseries_current_frame_color_element.text is not None
        ):
            preferences['TimeseriesCurrentFrameColor'] = timeseries_current_frame_color_element.text

        timeseries_current_frame_line_width_element = root.find('TimeseriesCurrentFrameLineWidth')
        if (
            timeseries_current_frame_line_width_element is not None
            and timeseries_current_frame_line_width_element.text is not None
        ):
            preferences['TimeseriesCurrentFrameLineWidth'] = float(timeseries_current_frame_line_width_element.text)

        preview_handle_size_element = root.find('PreviewHandleSize')
        if preview_handle_size_element is not None and preview_handle_size_element.text is not None:
            preferences['PreviewHandleSize'] = float(preview_handle_size_element.text)

        circle_label_offset_x_element = root.find('CircleLabelOffsetX')
        if circle_label_offset_x_element is not None and circle_label_offset_x_element.text is not None:
            preferences['CircleLabelOffsetX'] = float(circle_label_offset_x_element.text)

        circle_label_offset_y_element = root.find('CircleLabelOffsetY')
        if circle_label_offset_y_element is not None and circle_label_offset_y_element.text is not None:
            preferences['CircleLabelOffsetY'] = float(circle_label_offset_y_element.text)

        for key in DEFAULT_VISUAL_COLORS:
            color_element = root.find(key)
            if color_element is not None and color_element.text is not None:
                preferences[key] = color_element.text
        
        return preferences

if __name__ == '__main__':
    app = QApplication([])
    app.setWindowIcon(QIcon(os.path.join(resources_dir, "app_icons", "IcescopyApp.png")))
    window = IceScopy()
    window.show()
    
    app.exec()
