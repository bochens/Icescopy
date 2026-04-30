import os

from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QDate, QSignalBlocker
from PySide6.QtGui import QDoubleValidator

from icescopy_temperature_import import (
    IMAGE_TIMESTAMP_SOURCE_CHOICES,
    IMAGE_TIMESTAMP_SOURCE_FILENAME,
    IMAGE_TIMESTAMP_SOURCE_CREATED,
    IMAGE_TIMESTAMP_SOURCE_GENERATED,
    IMAGE_TIMESTAMP_SOURCE_MODIFIED,
    IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS,
    TEMPERATURE_UNIT_CELSIUS,
    TEMPERATURE_UNIT_KELVIN,
    TIMESTAMP_STYLE_AUTO,
    TIMESTAMP_STYLE_CHOICES,
    parse_timestamp_text,
    resolve_image_timestamp,
)


TEMPERATURE_RESET_LABEL = "Reset After Warmed To (°C)"
TEMPERATURE_RESET_DESCRIPTION = (
    "If reset is enabled, a new cycle starts once temperature warms back to the selected threshold."
)
WATER_BLANK_CORRECTION_DESCRIPTION = (
    "If water blank samples are selected, their frozen counts and total counts are subtracted from each non-blank output group."
)


def _setup_fixed_width_scrolling_dialog(dialog, *, width, initial_height, minimum_height):
    dialog.resize(width, initial_height)
    dialog.setMinimumWidth(width)
    dialog.setMaximumWidth(width)
    dialog.setMinimumHeight(minimum_height)
    dialog.setSizeGripEnabled(True)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(14)

    scroll_area = QScrollArea(dialog)
    scroll_area.setFrameShape(QFrame.NoFrame)
    scroll_area.setWidgetResizable(True)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    layout.addWidget(scroll_area, 1)

    scroll_contents = QWidget(scroll_area)
    scroll_layout = QVBoxLayout(scroll_contents)
    scroll_layout.setContentsMargins(0, 0, 0, 0)
    scroll_layout.setSpacing(14)
    scroll_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
    scroll_area.setWidget(scroll_contents)

    return layout, scroll_area, scroll_contents, scroll_layout


class NewSessionMetadataDialog(QDialog):
    def __init__(self, parent=None, metadata=None, *, window_title="New Session"):
        super().__init__(parent)
        self.setWindowTitle(str(window_title or "Session Metadata"))
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
        self.well_volume_edit = QLineEdit(str(metadata.get("well_volume_uL", "") or ""), self)
        self.well_volume_edit.setPlaceholderText("uL")
        well_volume_validator = QDoubleValidator(self.well_volume_edit)
        well_volume_validator.setNotation(QDoubleValidator.StandardNotation)
        well_volume_validator.setBottom(0.0)
        self.well_volume_edit.setValidator(well_volume_validator)

        raw_date_text = str(metadata.get("date", "") or "").strip()
        parsed_date = QDate.fromString(raw_date_text, Qt.ISODate)
        if not parsed_date.isValid():
            for date_format in (
                "yyyy/MM/dd",
                "MM/dd/yyyy",
                "M/d/yyyy",
                "dd/MM/yyyy",
                "d/M/yyyy",
            ):
                parsed_date = QDate.fromString(raw_date_text, date_format)
                if parsed_date.isValid():
                    break
        if not parsed_date.isValid():
            parsed_date = QDate.currentDate()

        self.date_edit = QDateEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(parsed_date)

        form.addRow("Project Name", self.project_name_edit)
        form.addRow("User Name", self.user_name_edit)
        form.addRow("Institution", self.institution_edit)
        form.addRow("Date", self.date_edit)
        form.addRow("Well Volume (uL)", self.well_volume_edit)
        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        well_volume_text = self.well_volume_edit.text().strip()
        if well_volume_text:
            try:
                float(well_volume_text)
            except ValueError:
                QMessageBox.warning(
                    self,
                    self.windowTitle(),
                    "Well Volume (uL) must be a number or left blank.",
                )
                return
        super().accept()

    def get_metadata(self):
        return {
            "project_name": self.project_name_edit.text().strip(),
            "user_name": self.user_name_edit.text().strip(),
            "institution": self.institution_edit.text().strip(),
            "date": self.date_edit.date().toString(Qt.ISODate),
            "well_volume_uL": self.well_volume_edit.text().strip(),
        }


class CSUTemperatureImportDialog(QDialog):
    def __init__(
        self,
        main_window,
        initial_path,
        sample_names,
        initial_reset_temperature=None,
        parent=None,
    ):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("CSU IS .dat import")
        layout, self.scroll_area, self.scroll_contents, scroll_layout = _setup_fixed_width_scrolling_dialog(
            self,
            width=640,
            initial_height=460,
            minimum_height=360,
        )

        intro_label = QLabel(
            "Select the CSU .dat file and optionally mark app samples that should be treated as water blank controls.",
            self,
        )
        intro_label.setWordWrap(True)
        scroll_layout.addWidget(intro_label)

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
        form.addRow("Water blank samples", self.blank_sample_list)

        self.reset_temperature_spinbox = QDoubleSpinBox(self)
        self.reset_temperature_spinbox.setRange(-999.0, 200.0)
        self.reset_temperature_spinbox.setDecimals(1)
        self.reset_temperature_spinbox.setSpecialValueText("Off")
        self.reset_temperature_spinbox.setValue(
            -999.0
            if initial_reset_temperature is None
            else float(initial_reset_temperature)
        )
        self.reset_temperature_spinbox.setFixedWidth(120)
        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_row.addWidget(self.reset_temperature_spinbox, 0, Qt.AlignLeft)
        reset_row.addStretch(1)
        reset_row_widget = QWidget(self)
        reset_row_widget.setLayout(reset_row)
        form.addRow(TEMPERATURE_RESET_LABEL, reset_row_widget)

        scroll_layout.addLayout(form, 1)

        hint_label = QLabel(
            f"Water blank correction is applied within each cycle. {WATER_BLANK_CORRECTION_DESCRIPTION} {TEMPERATURE_RESET_DESCRIPTION}",
            self,
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: rgba(96, 96, 96, 255);")
        scroll_layout.addWidget(hint_label)

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
        elif getattr(self.main_window, "active_frame_source", None):
            source_path = str(self.main_window.active_frame_source().source_path() or "")
            initial_dir = source_path if os.path.isdir(source_path) else os.path.dirname(source_path)
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
            QMessageBox.warning(
                self,
                "CSU IS .dat import",
                "Choose a CSU .dat file before importing.",
            )
            return
        if not os.path.isfile(file_path):
            QMessageBox.warning(
                self,
                "CSU IS .dat import",
                "The selected CSU .dat file does not exist.",
            )
            return
        super().accept()

    def get_values(self):
        reset_temperature = float(self.reset_temperature_spinbox.value())
        if reset_temperature <= -999.0:
            reset_temperature = None
        return {
            "file_path": self.file_path_edit.text().strip(),
            "blank_sample_names": [
                str(item.text()) for item in self.blank_sample_list.selectedItems()
            ],
            "reset_temperature": reset_temperature,
        }


class TAMUTemperatureImportDialog(QDialog):
    def __init__(
        self,
        main_window,
        initial_path,
        sample_names,
        initial_calibration_path="",
        initial_reset_temperature=None,
        initial_blank_sample_names=None,
        parent=None,
    ):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("TAMU Linkam .xlsx import")
        layout, self.scroll_area, self.scroll_contents, scroll_layout = _setup_fixed_width_scrolling_dialog(
            self,
            width=640,
            initial_height=420,
            minimum_height=360,
        )

        intro_label = QLabel(
            "Select the TAMU Linkam workbook. Image timestamps will be read from the PNG filenames and matched to the Linkam temperature timeseries by time interpolation. "
            "You can also mark app samples that should be treated as water blank controls.",
            self,
        )
        intro_label.setWordWrap(True)
        scroll_layout.addWidget(intro_label)

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

        if isinstance(initial_blank_sample_names, (str, bytes)):
            blank_name_values = [initial_blank_sample_names]
        else:
            blank_name_values = list(initial_blank_sample_names or [])
        selected_blank_names = {
            str(sample_name).strip()
            for sample_name in blank_name_values
            if str(sample_name).strip()
        }
        self.blank_sample_list = QListWidget(self)
        self.blank_sample_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.blank_sample_list.setMinimumHeight(132)
        for sample_name in sample_names:
            sample_label = str(sample_name)
            item = QListWidgetItem(sample_label, self.blank_sample_list)
            if sample_label in selected_blank_names or (
                not selected_blank_names and "blank" in sample_label.casefold()
            ):
                item.setSelected(True)
        form.addRow("Water blank samples", self.blank_sample_list)

        self.reset_temperature_spinbox = QDoubleSpinBox(self)
        self.reset_temperature_spinbox.setRange(-999.0, 200.0)
        self.reset_temperature_spinbox.setDecimals(1)
        self.reset_temperature_spinbox.setSpecialValueText("Off")
        self.reset_temperature_spinbox.setValue(
            -999.0
            if initial_reset_temperature is None
            else float(initial_reset_temperature)
        )
        self.reset_temperature_spinbox.setFixedWidth(120)
        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_row.addWidget(self.reset_temperature_spinbox, 0, Qt.AlignLeft)
        reset_row.addStretch(1)
        reset_row_widget = QWidget(self)
        reset_row_widget.setLayout(reset_row)
        form.addRow(TEMPERATURE_RESET_LABEL, reset_row_widget)

        scroll_layout.addLayout(form)

        hint_label = QLabel(
            "Calibration is applied by cell ID. If no sample setup exists, all cells are treated as one output group. "
            f"{WATER_BLANK_CORRECTION_DESCRIPTION} "
            f"{TEMPERATURE_RESET_DESCRIPTION}",
            self,
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: rgba(96, 96, 96, 255);")
        hint_label.setContentsMargins(2, 2, 2, 0)
        scroll_layout.addWidget(hint_label)

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
            QMessageBox.warning(
                self,
                "TAMU Linkam .xlsx import",
                "Choose a TAMU .xlsx file before importing.",
            )
            return
        if not os.path.isfile(file_path):
            QMessageBox.warning(
                self,
                "TAMU Linkam .xlsx import",
                "The selected TAMU .xlsx file does not exist.",
            )
            return
        if calibration_path and not os.path.isfile(calibration_path):
            QMessageBox.warning(
                self,
                "TAMU Linkam .xlsx import",
                "The selected calibration CSV does not exist.",
            )
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
            "blank_sample_names": [
                str(item.text()) for item in self.blank_sample_list.selectedItems()
            ],
        }


class PKUTemperatureImportDialog(QDialog):
    def __init__(
        self,
        main_window,
        initial_path,
        sample_names,
        initial_reset_temperature=None,
        initial_blank_sample_names=None,
        parent=None,
    ):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("PKU Linksys32 .iml import")
        layout, self.scroll_area, self.scroll_contents, scroll_layout = _setup_fixed_width_scrolling_dialog(
            self,
            width=640,
            initial_height=420,
            minimum_height=360,
        )

        intro_label = QLabel(
            "Select the PKU Linksys32 .iml file. Loaded images are matched to the .iml image records by current image order. "
            "You can also mark app samples that should be treated as water blank controls.",
            self,
        )
        intro_label.setWordWrap(True)
        scroll_layout.addWidget(intro_label)

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
        self.file_path_edit.setPlaceholderText("Choose a PKU Linksys32 .iml file")
        browse_button = QPushButton("Browse", self)
        browse_button.setAutoDefault(False)
        browse_button.setDefault(False)
        browse_button.setFixedWidth(96)
        browse_button.clicked.connect(self.browse_file)
        file_row.addWidget(self.file_path_edit, 1)
        file_row.addWidget(browse_button, 0, Qt.AlignRight)
        file_row_widget = QWidget(self)
        file_row_widget.setLayout(file_row)
        form.addRow("PKU .iml file", file_row_widget)

        if isinstance(initial_blank_sample_names, (str, bytes)):
            blank_name_values = [initial_blank_sample_names]
        else:
            blank_name_values = list(initial_blank_sample_names or [])
        selected_blank_names = {
            str(sample_name).strip()
            for sample_name in blank_name_values
            if str(sample_name).strip()
        }
        self.blank_sample_list = QListWidget(self)
        self.blank_sample_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.blank_sample_list.setMinimumHeight(132)
        for sample_name in sample_names:
            sample_label = str(sample_name)
            item = QListWidgetItem(sample_label, self.blank_sample_list)
            if sample_label in selected_blank_names or (
                not selected_blank_names and "blank" in sample_label.casefold()
            ):
                item.setSelected(True)
        form.addRow("Water blank samples", self.blank_sample_list)

        self.reset_temperature_spinbox = QDoubleSpinBox(self)
        self.reset_temperature_spinbox.setRange(-999.0, 200.0)
        self.reset_temperature_spinbox.setDecimals(1)
        self.reset_temperature_spinbox.setSpecialValueText("Off")
        self.reset_temperature_spinbox.setValue(
            -999.0
            if initial_reset_temperature is None
            else float(initial_reset_temperature)
        )
        self.reset_temperature_spinbox.setFixedWidth(120)
        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_row.addWidget(self.reset_temperature_spinbox, 0, Qt.AlignLeft)
        reset_row.addStretch(1)
        reset_row_widget = QWidget(self)
        reset_row_widget.setLayout(reset_row)
        form.addRow(TEMPERATURE_RESET_LABEL, reset_row_widget)

        scroll_layout.addLayout(form)

        hint_label = QLabel(
            "The .iml image record count must match the loaded image count so image order can be used without guessing. "
            f"{WATER_BLANK_CORRECTION_DESCRIPTION} "
            f"{TEMPERATURE_RESET_DESCRIPTION}",
            self,
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: rgba(96, 96, 96, 255);")
        hint_label.setContentsMargins(2, 2, 2, 0)
        scroll_layout.addWidget(hint_label)

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
            "Import PKU Linksys32 .iml file",
            initial_dir,
            "Linksys32 Data Files (*.iml);;All Files (*)",
            options=self.main_window.file_dialog_options(),
        )
        if file_path:
            self.file_path_edit.setText(file_path)

    def accept(self):
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(
                self,
                "PKU Linksys32 .iml import",
                "Choose a PKU Linksys32 .iml file before importing.",
            )
            return
        if not os.path.isfile(file_path):
            QMessageBox.warning(
                self,
                "PKU Linksys32 .iml import",
                "The selected PKU Linksys32 .iml file does not exist.",
            )
            return
        super().accept()

    def get_values(self):
        reset_temperature = float(self.reset_temperature_spinbox.value())
        if reset_temperature <= -999.0:
            reset_temperature = None
        return {
            "file_path": self.file_path_edit.text().strip(),
            "reset_temperature": reset_temperature,
            "blank_sample_names": [
                str(item.text()) for item in self.blank_sample_list.selectedItems()
            ],
        }


class StandardTemperatureImportDialog(QDialog):
    def __init__(
        self,
        main_window,
        initial_path,
        sample_names,
        initial_reset_temperature=None,
        initial_blank_sample_names=None,
        initial_image_timestamp_source=IMAGE_TIMESTAMP_SOURCE_FILENAME,
        initial_image_timestamp_style=TIMESTAMP_STYLE_AUTO,
        initial_temperature_timestamp_style=TIMESTAMP_STYLE_AUTO,
        initial_use_image_timestamp_style=True,
        initial_generated_start_text="",
        initial_frame_interval_seconds=1.0,
        initial_temperature_unit=TEMPERATURE_UNIT_CELSIUS,
        video_mode=False,
        parent=None,
    ):
        super().__init__(parent)
        self.main_window = main_window
        self.video_mode = bool(video_mode)
        self.setWindowTitle("Standard temperature CSV import")
        self.resize(640, 620)
        self.setMinimumWidth(640)
        self.setMaximumWidth(640)
        self.setMinimumHeight(540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.scroll_area, 1)

        self.scroll_contents = QWidget(self.scroll_area)
        self.scroll_contents_layout = QVBoxLayout(self.scroll_contents)
        self.scroll_contents_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_contents_layout.setSpacing(14)
        self.scroll_contents_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        self.scroll_area.setWidget(self.scroll_contents)

        intro_label = QLabel(
            "Import a two-column CSV: timestamp and temperature. Extra columns are ignored.",
            self,
        )
        intro_label.setWordWrap(True)
        self.scroll_contents_layout.addWidget(intro_label)

        def make_form_label(text):
            label = QLabel(text, self)
            label.setMinimumWidth(170)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            return label

        image_section_label = QLabel("Video frame timestamps" if self.video_mode else "Image timestamps", self)
        image_section_label.setStyleSheet("font-weight: 600;")
        self.scroll_contents_layout.addWidget(image_section_label)

        self.image_form = QFormLayout()
        self.image_form.setContentsMargins(0, 0, 0, 0)
        self.image_form.setHorizontalSpacing(14)
        self.image_form.setVerticalSpacing(12)
        self.image_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.image_form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.image_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.image_form.setRowWrapPolicy(QFormLayout.DontWrapRows)

        temperature_separator = QFrame(self)
        temperature_separator.setFrameShape(QFrame.HLine)
        temperature_separator.setFrameShadow(QFrame.Sunken)

        temperature_section_label = QLabel("Temperature file", self)
        temperature_section_label.setStyleSheet("font-weight: 600;")

        self.temperature_form = QFormLayout()
        self.temperature_form.setContentsMargins(0, 0, 0, 0)
        self.temperature_form.setHorizontalSpacing(14)
        self.temperature_form.setVerticalSpacing(12)
        self.temperature_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.temperature_form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.temperature_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.temperature_form.setRowWrapPolicy(QFormLayout.DontWrapRows)

        file_row = QHBoxLayout()
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.setSpacing(8)
        self.file_path_edit = QLineEdit(self)
        self.file_path_edit.setText(str(initial_path or ""))
        self.file_path_edit.setPlaceholderText("Choose a temperature CSV")
        browse_button = QPushButton("Browse", self)
        browse_button.setAutoDefault(False)
        browse_button.setDefault(False)
        browse_button.setFixedWidth(96)
        browse_button.clicked.connect(self.browse_file)
        file_row.addWidget(self.file_path_edit, 1)
        file_row.addWidget(browse_button, 0, Qt.AlignRight)
        file_row_widget = QWidget(self)
        file_row_widget.setLayout(file_row)

        selected_blank_names = {
            str(sample_name).strip()
            for sample_name in (initial_blank_sample_names or [])
            if str(sample_name).strip()
        }

        self.image_timestamp_source_combo = QComboBox(self)
        self.image_timestamp_source_combo.setMinimumContentsLength(18)
        self.image_timestamp_source_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        source_choices = (
            (
                (IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS, "First timestamp + video time"),
                (IMAGE_TIMESTAMP_SOURCE_GENERATED, "First timestamp + fixed interval"),
            )
            if self.video_mode
            else IMAGE_TIMESTAMP_SOURCE_CHOICES
        )
        for source_value, source_label in source_choices:
            self.image_timestamp_source_combo.addItem(source_label, source_value)
        source_index = max(
            0,
            self.image_timestamp_source_combo.findData(
                str(initial_image_timestamp_source or IMAGE_TIMESTAMP_SOURCE_FILENAME)
            ),
        )
        self.image_timestamp_source_combo.setCurrentIndex(source_index)
        self.image_form.addRow(make_form_label("Source"), self.image_timestamp_source_combo)

        self.image_timestamp_style_combo = QComboBox(self)
        self.image_timestamp_style_combo.setMinimumContentsLength(18)
        self.image_timestamp_style_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        for style_value, style_label in TIMESTAMP_STYLE_CHOICES:
            self.image_timestamp_style_combo.addItem(style_label, style_value)
        image_style_index = max(
            0,
            self.image_timestamp_style_combo.findData(
                str(initial_image_timestamp_style or TIMESTAMP_STYLE_AUTO)
            ),
        )
        self.image_timestamp_style_combo.setCurrentIndex(image_style_index)
        self.image_form.addRow(make_form_label("Timestamp style"), self.image_timestamp_style_combo)

        self.generated_start_edit = QLineEdit(self)
        self.generated_start_edit.setText(str(initial_generated_start_text or ""))
        self.generated_start_edit.setPlaceholderText("Example: 2026-04-22 23:15:01")
        self.image_form.addRow(make_form_label("First timestamp"), self.generated_start_edit)

        self.frame_interval_spinbox = QDoubleSpinBox(self)
        self.frame_interval_spinbox.setRange(0.000001, 86400.0)
        self.frame_interval_spinbox.setDecimals(6)
        self.frame_interval_spinbox.setValue(
            max(0.000001, float(initial_frame_interval_seconds or 1.0))
        )
        self.frame_interval_spinbox.setFixedWidth(160)
        frame_interval_row = QHBoxLayout()
        frame_interval_row.setContentsMargins(0, 0, 0, 0)
        frame_interval_row.addWidget(self.frame_interval_spinbox, 0, Qt.AlignLeft)
        frame_interval_row.addStretch(1)
        frame_interval_widget = QWidget(self)
        frame_interval_widget.setLayout(frame_interval_row)
        self.generated_frame_interval_widget = frame_interval_widget
        self.image_form.addRow(make_form_label("Frame interval (s)"), frame_interval_widget)

        self.image_timestamp_test_label = QLabel(self)
        self.image_timestamp_test_label.setWordWrap(True)
        self.image_timestamp_test_label.setStyleSheet("color: rgba(96, 96, 96, 255);")
        self.image_form.addRow(self.image_timestamp_test_label)

        self.scroll_contents_layout.addLayout(self.image_form)
        self.scroll_contents_layout.addWidget(temperature_separator)
        self.scroll_contents_layout.addWidget(temperature_section_label)

        self.temperature_form.addRow(make_form_label("CSV file"), file_row_widget)

        self.use_image_timestamp_style_checkbox = QCheckBox(
            "Use image style for temperature timestamps",
            self,
        )
        self.use_image_timestamp_style_checkbox.setChecked(bool(initial_use_image_timestamp_style))
        self.temperature_form.addRow("", self.use_image_timestamp_style_checkbox)

        self.temperature_timestamp_style_combo = QComboBox(self)
        self.temperature_timestamp_style_combo.setMinimumContentsLength(18)
        self.temperature_timestamp_style_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        for style_value, style_label in TIMESTAMP_STYLE_CHOICES:
            self.temperature_timestamp_style_combo.addItem(style_label, style_value)
        temperature_style_index = max(
            0,
            self.temperature_timestamp_style_combo.findData(
                str(initial_temperature_timestamp_style or TIMESTAMP_STYLE_AUTO)
            ),
        )
        self.temperature_timestamp_style_combo.setCurrentIndex(temperature_style_index)
        self.temperature_form.addRow(make_form_label("Timestamp style"), self.temperature_timestamp_style_combo)

        self.temperature_unit_group = QButtonGroup(self)
        self.temperature_celsius_radio = QRadioButton("Celsius", self)
        self.temperature_kelvin_radio = QRadioButton("Kelvin", self)
        self.temperature_unit_group.addButton(self.temperature_celsius_radio)
        self.temperature_unit_group.addButton(self.temperature_kelvin_radio)
        if str(initial_temperature_unit or TEMPERATURE_UNIT_CELSIUS) == TEMPERATURE_UNIT_KELVIN:
            self.temperature_kelvin_radio.setChecked(True)
        else:
            self.temperature_celsius_radio.setChecked(True)
        unit_row = QHBoxLayout()
        unit_row.setContentsMargins(0, 0, 0, 0)
        unit_row.setSpacing(12)
        unit_row.addWidget(self.temperature_celsius_radio)
        unit_row.addWidget(self.temperature_kelvin_radio)
        unit_row.addStretch(1)
        unit_widget = QWidget(self)
        unit_widget.setLayout(unit_row)
        self.temperature_form.addRow(make_form_label("Unit"), unit_widget)

        blank_separator = QFrame(self)
        blank_separator.setFrameShape(QFrame.HLine)
        blank_separator.setFrameShadow(QFrame.Sunken)
        self.temperature_form.addRow(blank_separator)

        blank_section_label = QLabel("Water blank correction", self)
        blank_section_label.setStyleSheet("font-weight: 600;")
        self.temperature_form.addRow(blank_section_label)

        self.blank_sample_list = QListWidget(self)
        self.blank_sample_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.blank_sample_list.setMinimumHeight(132)
        for sample_name in sample_names:
            sample_label = str(sample_name)
            item = QListWidgetItem(sample_label, self.blank_sample_list)
            if sample_label in selected_blank_names or (
                not selected_blank_names and "blank" in sample_label.casefold()
            ):
                item.setSelected(True)
        self.temperature_form.addRow(make_form_label("Water blank samples"), self.blank_sample_list)

        self.reset_temperature_spinbox = QDoubleSpinBox(self)
        self.reset_temperature_spinbox.setRange(-999.0, 200.0)
        self.reset_temperature_spinbox.setDecimals(1)
        self.reset_temperature_spinbox.setSpecialValueText("Off")
        self.reset_temperature_spinbox.setValue(
            -999.0
            if initial_reset_temperature is None
            else float(initial_reset_temperature)
        )
        self.reset_temperature_spinbox.setFixedWidth(120)
        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_row.addWidget(self.reset_temperature_spinbox, 0, Qt.AlignLeft)
        reset_row.addStretch(1)
        reset_row_widget = QWidget(self)
        reset_row_widget.setLayout(reset_row)
        self.temperature_form.addRow(make_form_label(TEMPERATURE_RESET_LABEL), reset_row_widget)

        self.scroll_contents_layout.addLayout(self.temperature_form)

        hint_label = QLabel(
            "<ul style='margin-top:0px; margin-bottom:0px; padding-left:18px;'>"
            "<li>Accepted text forms include YYYY-MM-DD HH:MM:SS, YYYY-MM-DDTHH:MM:SS, YYYY/MM/DD HH:MM:SS, "
            "YYYYMMDD_HHMMSS, YYYYMMDD HHMMSS, YYMMDD_HHMMSS, YYMMDD HHMMSS, YYMMDD HHMM, YYMMDD-HHMMSS, "
            "YY/MM/DD HH:MM:SS, and EXIF text YYYY:MM:DD HH:MM:SS.</li>"
            "<li>Use the explicit Unix epoch options for 10-digit seconds or 13-digit milliseconds since 1970-01-01 00:00:00 UTC.</li>"
            f"<li>{WATER_BLANK_CORRECTION_DESCRIPTION}</li>"
            f"<li>{TEMPERATURE_RESET_DESCRIPTION}</li>"
            "</ul>",
            self,
        )
        hint_label.setTextFormat(Qt.RichText)
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: rgba(96, 96, 96, 255);")
        hint_label.setContentsMargins(2, 2, 2, 0)
        self.scroll_contents_layout.addWidget(hint_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.button_box = button_box
        self.ok_button = button_box.button(QDialogButtonBox.Ok)
        layout.addWidget(button_box)

        self.image_timestamp_source_combo.currentIndexChanged.connect(self.refresh_dynamic_state)
        self.image_timestamp_style_combo.currentIndexChanged.connect(self.refresh_dynamic_state)
        self.generated_start_edit.textChanged.connect(self.refresh_dynamic_state)
        self.frame_interval_spinbox.valueChanged.connect(self.refresh_dynamic_state)
        self.use_image_timestamp_style_checkbox.toggled.connect(self.refresh_dynamic_state)
        self.refresh_dynamic_state()

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
            "Import temperature CSV",
            initial_dir,
            "CSV Files (*.csv);;All Files (*)",
            options=self.main_window.file_dialog_options(),
        )
        if file_path:
            self.file_path_edit.setText(file_path)

    def selected_image_timestamp_source(self):
        return str(
            self.image_timestamp_source_combo.currentData() or IMAGE_TIMESTAMP_SOURCE_FILENAME
        )

    def selected_image_timestamp_style(self):
        return str(self.image_timestamp_style_combo.currentData() or TIMESTAMP_STYLE_AUTO)

    def selected_temperature_timestamp_style(self):
        if self.use_image_timestamp_style_checkbox.isChecked():
            return self.selected_image_timestamp_style()
        return str(
            self.temperature_timestamp_style_combo.currentData() or TIMESTAMP_STYLE_AUTO
        )

    def selected_temperature_unit(self):
        return (
            TEMPERATURE_UNIT_KELVIN
            if self.temperature_kelvin_radio.isChecked()
            else TEMPERATURE_UNIT_CELSIUS
        )

    def refresh_dynamic_state(self):
        source_value = self.selected_image_timestamp_source()
        image_text_style_available = source_value not in {
            IMAGE_TIMESTAMP_SOURCE_CREATED,
            IMAGE_TIMESTAMP_SOURCE_MODIFIED,
        }
        generated_source = source_value == IMAGE_TIMESTAMP_SOURCE_GENERATED
        video_pts_source = source_value == IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS

        self.image_timestamp_style_combo.setEnabled(image_text_style_available)
        self.generated_start_edit.setEnabled(generated_source or video_pts_source)
        self.generated_frame_interval_widget.setEnabled(generated_source)
        self.image_form.setRowVisible(self.generated_start_edit, generated_source or video_pts_source)
        self.image_form.setRowVisible(self.generated_frame_interval_widget, generated_source)
        if not image_text_style_available and self.use_image_timestamp_style_checkbox.isChecked():
            with QSignalBlocker(self.use_image_timestamp_style_checkbox):
                self.use_image_timestamp_style_checkbox.setChecked(False)
        self.use_image_timestamp_style_checkbox.setEnabled(image_text_style_available)
        self.temperature_timestamp_style_combo.setEnabled(
            (not image_text_style_available)
            or (not self.use_image_timestamp_style_checkbox.isChecked())
        )
        is_valid, message = self.evaluate_image_timestamp_test()
        self.image_timestamp_test_label.setText(message)
        if self.ok_button is not None:
            self.ok_button.setEnabled(bool(is_valid))

    def evaluate_image_timestamp_test(self):
        if self.video_mode:
            display_name = "frame 0"
            first_timestamp = parse_timestamp_text(
                self.generated_start_edit.text().strip(),
                self.selected_image_timestamp_style(),
            )
            if first_timestamp is None:
                return False, f"{display_name}: first timestamp not found"
            if self.selected_image_timestamp_source() == IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS:
                frame_source = self.main_window.active_frame_source()
                first_frame_time = frame_source.frame_time_seconds(0)
                if first_frame_time is None:
                    return False, "frame 0: video timing not found; use fixed interval"
                return True, f"{display_name}: video time -> {first_timestamp.isoformat(timespec='milliseconds')}"
            return True, f"{display_name}: fixed interval -> {first_timestamp.isoformat(timespec='milliseconds')}"

        if not getattr(self.main_window, "imagePaths", None):
            return False, "Not found: no loaded images."

        first_path = self.main_window.imagePaths[0]
        first_name = (
            self.main_window.imageNames[0]
            if getattr(self.main_window, "imageNames", None)
            else os.path.basename(str(first_path or ""))
        )
        display_name = os.path.basename(str(first_name or first_path or ""))
        preview_timestamp = resolve_image_timestamp(
            first_path,
            first_name,
            source=self.selected_image_timestamp_source(),
            timestamp_style=self.selected_image_timestamp_style(),
            generated_start_text=self.generated_start_edit.text().strip(),
            frame_interval_seconds=float(self.frame_interval_spinbox.value()),
            image_index=0,
        )
        if preview_timestamp is None:
            if self.selected_image_timestamp_source() == IMAGE_TIMESTAMP_SOURCE_GENERATED:
                return False, f"{display_name}: custom not found"
            return False, f"{display_name}: not found"

        if self.selected_image_timestamp_source() == IMAGE_TIMESTAMP_SOURCE_GENERATED:
            return (
                True,
                f"{display_name}: custom -> {preview_timestamp.isoformat(timespec='milliseconds')}",
            )
        return (
            True,
            f"{display_name}: {preview_timestamp.isoformat(timespec='milliseconds')}",
        )

    def accept(self):
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(
                self,
                "Standard temperature CSV import",
                "Choose a temperature CSV before importing.",
            )
            return
        if not os.path.isfile(file_path):
            QMessageBox.warning(
                self,
                "Standard temperature CSV import",
                "The selected temperature CSV does not exist.",
            )
            return
        if self.selected_image_timestamp_source() in {
            IMAGE_TIMESTAMP_SOURCE_GENERATED,
            IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS,
        }:
            if not self.generated_start_edit.text().strip():
                QMessageBox.warning(
                    self,
                    "Standard temperature CSV import",
                    "Enter the first frame timestamp.",
                )
                return
        if self.selected_image_timestamp_source() == IMAGE_TIMESTAMP_SOURCE_GENERATED:
            if self.frame_interval_spinbox.value() <= 0:
                QMessageBox.warning(
                    self,
                    "Standard temperature CSV import",
                    "Frame interval must be greater than zero.",
                )
                return
        image_timestamp_valid, image_timestamp_message = self.evaluate_image_timestamp_test()
        if not image_timestamp_valid:
            frame_label = "frame" if self.video_mode else "image"
            QMessageBox.warning(
                self,
                "Standard temperature CSV import",
                f"The selected timestamp source/style does not resolve a valid timestamp for the first {frame_label}.\n\n"
                + image_timestamp_message,
            )
            return
        super().accept()

    def get_values(self):
        reset_temperature = float(self.reset_temperature_spinbox.value())
        if reset_temperature <= -999.0:
            reset_temperature = None
        return {
            "file_path": self.file_path_edit.text().strip(),
            "reset_temperature": reset_temperature,
            "blank_sample_names": [
                str(item.text()) for item in self.blank_sample_list.selectedItems()
            ],
            "image_timestamp_source": self.selected_image_timestamp_source(),
            "image_timestamp_style": self.selected_image_timestamp_style(),
            "temperature_timestamp_style": self.selected_temperature_timestamp_style(),
            "use_image_timestamp_style": bool(self.use_image_timestamp_style_checkbox.isChecked()),
            "generated_start_text": self.generated_start_edit.text().strip(),
            "frame_interval_seconds": float(self.frame_interval_spinbox.value()),
            "temperature_unit": self.selected_temperature_unit(),
        }


class OutputResultsDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        include_grayscale=False,
        include_freeze=False,
        include_freeze_count_timeseries=False,
    ):
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
        self.freeze_count_timeseries_checkbox = QCheckBox("Freeze Count Timeseries CSV", self)

        self.grayscale_checkbox.setVisible(bool(include_grayscale))
        self.freeze_checkbox.setVisible(bool(include_freeze))
        self.freeze_count_timeseries_checkbox.setVisible(bool(include_freeze_count_timeseries))

        layout.addWidget(self.grayscale_checkbox)
        layout.addWidget(self.freeze_checkbox)
        layout.addWidget(self.freeze_count_timeseries_checkbox)

        self.select_all_checkbox.toggled.connect(self.on_select_all_toggled)
        self.grayscale_checkbox.toggled.connect(self.sync_select_all_checkbox)
        self.freeze_checkbox.toggled.connect(self.sync_select_all_checkbox)
        self.freeze_count_timeseries_checkbox.toggled.connect(self.sync_select_all_checkbox)
        self.sync_select_all_checkbox()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        if not any(self.selected_exports().values()):
            QMessageBox.warning(
                self,
                "Output Results",
                "Select at least one CSV to export.",
            )
            return
        super().accept()

    def selected_exports(self):
        return {
            "grayscale": (not self.grayscale_checkbox.isHidden())
            and self.grayscale_checkbox.isChecked(),
            "freeze": (not self.freeze_checkbox.isHidden())
            and self.freeze_checkbox.isChecked(),
            "freeze_count_timeseries": (not self.freeze_count_timeseries_checkbox.isHidden())
            and self.freeze_count_timeseries_checkbox.isChecked(),
        }

    def visible_export_checkboxes(self):
        return [
            checkbox
            for checkbox in (
                self.grayscale_checkbox,
                self.freeze_checkbox,
                self.freeze_count_timeseries_checkbox,
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
        all_checked = bool(visible_checkboxes) and all(
            checkbox.isChecked() for checkbox in visible_checkboxes
        )
        with QSignalBlocker(self.select_all_checkbox):
            self.select_all_checkbox.setChecked(all_checked)
