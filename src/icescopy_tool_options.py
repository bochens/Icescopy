from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt


TOOL_OPTIONS_CONTENT_WIDTH = 300
TOOL_OPTIONS_BUTTON_SPACING = 8
TOOL_OPTIONS_LABEL_WIDTH = 84
TOOL_OPTIONS_FIELD_WIDTH = 96
TOOL_OPTIONS_SHORTCUT_WIDTH = 96
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
        self.scroll_contents_layout.setAlignment(Qt.AlignTop)

        self.column_widget = QWidget(self.scroll_contents)
        self.column_widget.setMinimumWidth(self.content_width)
        self.column_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
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
        self.scroll_contents_layout.setAlignment(Qt.AlignTop)

        self.column_widget = QWidget(self.scroll_contents)
        self.column_widget.setMinimumWidth(self.content_width)
        self.column_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
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

        if shortcut_text:
            shortcut_label = QLabel(shortcut_text, row_widget)
            shortcut_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            shortcut_label.setStyleSheet("color: #7a7a7a; font-size: 11px;")
            shortcut_label.setWordWrap(False)
            shortcut_label.setMinimumWidth(max(self.shortcut_width, shortcut_label.sizeHint().width()))
            shortcut_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            row_layout.addWidget(shortcut_label)
        else:
            row_layout.addStretch(1)

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
        button.setFixedWidth(
            self.shortcut_width
            if self.shortcut_width > 0
            else self.standard_button_width()
        )
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
