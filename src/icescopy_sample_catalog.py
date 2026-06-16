from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QAbstractItemModel, QModelIndex, QRect, QSize, QTimer, Qt
from PySide6.QtGui import QBrush, QDoubleValidator, QFont, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from icescopy_sample_metadata import (
    ALLOWED_SAMPLE_TYPES,
    default_sample_metadata_schema,
    normalize_sample_catalog_record,
    sample_metadata_field_is_relevant,
    sample_metadata_field_keys,
    sample_metadata_field_label,
    sample_metadata_field_same_for_all,
    sample_metadata_field_type,
)
from icescopy_tool_options import TOOL_OPTIONS_BUTTON_SPACING

SAMPLE_CATALOG_PANEL_MIN_WIDTH = 280
SAMPLE_CATALOG_TREE_HEADERS = ("Sample Number", "Value")
SAMPLE_CATALOG_TREE_ROW_HEIGHT = 30
SAMPLE_CATALOG_TREE_EDITOR_HEIGHT = 26
SAMPLE_CATALOG_TREE_LABEL_COLUMN_WIDTH = 172
SAMPLE_CATALOG_TREE_INDENTATION = 12
SAMPLE_CATALOG_COLOR_SWATCH_SIZE = 12
SAMPLE_CATALOG_TREE_EDITOR_LEFT_MARGIN = 6
SAMPLE_CATALOG_TREE_EDITOR_RIGHT_MARGIN = 24
SAMPLE_CATALOG_DATETIME_INPUT_FORMAT = "%Y-%m-%d %H:%M:%S"
SAMPLE_CATALOG_DATETIME_STORAGE_FORMAT = "%Y-%m-%d %H:%M:%S"
SAMPLE_CATALOG_DATETIME_INPUT_MASK = "0000-00-00 00:00:00;_"
SAMPLE_CATALOG_DATETIME_HINT = "YYYY-MM-DD HH:MM:SS"


class SampleCatalogNode:
    def __init__(self, *, kind, parent=None, sample_id=None, field_key=""):
        self.kind = kind
        self.parent = parent
        self.sample_id = sample_id
        self.field_key = field_key
        self.children = []

    def row(self):
        if self.parent is None:
            return 0
        return self.parent.children.index(self)


class SampleCatalogTreeModel(QAbstractItemModel):
    SAMPLE_ID_ROLE = Qt.UserRole
    FIELD_NAME_ROLE = Qt.UserRole + 1
    EDITABLE_ROLE = Qt.UserRole + 2
    FIELD_TYPE_ROLE = Qt.UserRole + 3
    FIELD_LABEL_ROLE = Qt.UserRole + 4

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.root_node = SampleCatalogNode(kind="root")
        self.refresh()

    def active_schema(self):
        if hasattr(self.main_window, "active_sample_metadata_schema"):
            return self.main_window.active_sample_metadata_schema()
        return default_sample_metadata_schema()

    def refresh(self):
        self.beginResetModel()
        try:
            self.root_node = SampleCatalogNode(kind="root")
            if hasattr(self.main_window, "ordered_sample_catalog_records"):
                ordered_samples = self.main_window.ordered_sample_catalog_records()
            else:
                schema = self.active_schema()
                ordered_samples = [
                    (int(sample_id), normalize_sample_catalog_record(sample_record, schema))
                    for sample_id, sample_record in sorted(
                        getattr(self.main_window, "sample_catalog", {}).items(),
                        key=lambda pair: int(pair[0]),
                    )
                ]
            field_keys = sample_metadata_field_keys(self.active_schema())
            for sample_id, _sample_record in ordered_samples:
                sample_node = SampleCatalogNode(
                    kind="sample",
                    parent=self.root_node,
                    sample_id=int(sample_id),
                )
                self.root_node.children.append(sample_node)
                for field_key in field_keys:
                    sample_node.children.append(
                        SampleCatalogNode(
                            kind="field",
                            parent=sample_node,
                            sample_id=int(sample_id),
                            field_key=str(field_key),
                        )
                    )
        finally:
            self.endResetModel()

    def node_from_index(self, index):
        if index.isValid():
            node = index.internalPointer()
            if isinstance(node, SampleCatalogNode):
                return node
        return self.root_node

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid() and parent.column() > 0:
            return 0
        node = self.node_from_index(parent)
        return len(node.children)

    def columnCount(self, parent=QModelIndex()):
        return 2

    def index(self, row, column, parent=QModelIndex()):
        if row < 0 or column < 0 or column >= self.columnCount(parent):
            return QModelIndex()
        parent_node = self.node_from_index(parent)
        if row >= len(parent_node.children):
            return QModelIndex()
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        node = self.node_from_index(index)
        parent_node = node.parent
        if parent_node is None or parent_node is self.root_node:
            return QModelIndex()
        return self.createIndex(parent_node.row(), 0, parent_node)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= int(section) < len(SAMPLE_CATALOG_TREE_HEADERS):
                return SAMPLE_CATALOG_TREE_HEADERS[int(section)]
        return None

    def sample_record(self, sample_id):
        if hasattr(self.main_window, "sample_record_for_id"):
            return self.main_window.sample_record_for_id(sample_id)
        return normalize_sample_catalog_record(
            getattr(self.main_window, "sample_catalog", {}).get(int(sample_id), {}),
            self.active_schema(),
        )

    def field_is_relevant(self, sample_id, field_key):
        return sample_metadata_field_is_relevant(
            self.active_schema(),
            field_key,
            self.sample_record(sample_id),
        )

    def field_is_same_for_all(self, field_key):
        return sample_metadata_field_same_for_all(self.active_schema(), field_key)

    def field_display_label(self, field_key):
        label = sample_metadata_field_label(self.active_schema(), field_key)
        if self.field_is_same_for_all(field_key):
            return f"{label} [all]"
        return label

    def sample_color_swatch(self, sample_id):
        color_getter = getattr(self.main_window, "sample_visual_color", None)
        if not callable(color_getter):
            return None
        color = color_getter(sample_id)
        if color is None or not color.isValid():
            return None
        pixmap = QPixmap(SAMPLE_CATALOG_COLOR_SWATCH_SIZE, SAMPLE_CATALOG_COLOR_SWATCH_SIZE)
        pixmap.fill(color)
        return pixmap

    def field_index(self, sample_id, field_key, column=1):
        sample_id = int(sample_id)
        for sample_row, sample_node in enumerate(self.root_node.children):
            if sample_node.kind != "sample" or int(sample_node.sample_id) != sample_id:
                continue
            sample_index = self.index(sample_row, 0, QModelIndex())
            for field_row, field_node in enumerate(sample_node.children):
                if field_node.kind == "field" and field_node.field_key == field_key:
                    return self.index(field_row, int(column), sample_index)
        return QModelIndex()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node = self.node_from_index(index)
        column = int(index.column())

        if role == Qt.SizeHintRole:
            return QSize(0, SAMPLE_CATALOG_TREE_ROW_HEIGHT)
        if role == self.SAMPLE_ID_ROLE:
            return node.sample_id if node.kind in {"sample", "field"} else None
        if role == self.FIELD_NAME_ROLE:
            return node.field_key if node.kind == "field" else ""
        if role == self.FIELD_TYPE_ROLE:
            return sample_metadata_field_type(self.active_schema(), node.field_key) if node.kind == "field" else ""
        if role == self.FIELD_LABEL_ROLE:
            return self.field_display_label(node.field_key) if node.kind == "field" else ""
        if role == self.EDITABLE_ROLE:
            return bool(node.kind == "field" and column == 1 and self.field_is_relevant(node.sample_id, node.field_key))

        if node.kind == "sample":
            if role == Qt.DecorationRole and column == 0:
                return self.sample_color_swatch(node.sample_id)
            if role == Qt.FontRole and column == 0:
                font = QFont()
                font.setBold(True)
                return font
            if role in (Qt.DisplayRole, Qt.EditRole):
                return str(node.sample_id) if column == 0 else ""
            return None

        if node.kind != "field":
            return None

        record = self.sample_record(node.sample_id)
        if role == Qt.ToolTipRole and self.field_is_same_for_all(node.field_key):
            return "Same for all samples. Editing this value updates every sample in the catalog."
        if role in (Qt.DisplayRole, Qt.EditRole):
            if column == 0:
                return self.field_display_label(node.field_key)
            return str(record.get(node.field_key, "") or "")
        if role == Qt.ForegroundRole and not self.field_is_relevant(node.sample_id, node.field_key):
            palette = self.main_window.palette() if hasattr(self.main_window, "palette") else None
            if palette is not None:
                return QBrush(palette.color(QPalette.Disabled, QPalette.Text))
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        node = self.node_from_index(index)
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if node.kind == "field" and int(index.column()) == 1:
            flags |= Qt.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or not index.isValid() or int(index.column()) != 1:
            return False
        node = self.node_from_index(index)
        if node.kind != "field" or not self.field_is_relevant(node.sample_id, node.field_key):
            return False

        schema = self.active_schema()
        field_key = node.field_key
        field_type = sample_metadata_field_type(schema, field_key)
        value_text = str(value or "").strip()
        if field_key == "sample_name" and not value_text and hasattr(self.main_window, "default_sample_name"):
            value_text = self.main_window.default_sample_name(node.sample_id)
        elif field_key == "sample_type":
            value_text = value_text.casefold()
            if value_text not in ("",) + ALLOWED_SAMPLE_TYPES:
                QMessageBox.warning(
                    self.main_window,
                    "Sample Catalog",
                    "Sample type must be one of: air, soil, other.",
                )
                return False
        elif field_type == "number" and value_text:
            try:
                float(value_text)
            except ValueError:
                return False
        elif field_type == "datetime" and value_text:
            try:
                datetime.strptime(value_text, SAMPLE_CATALOG_DATETIME_STORAGE_FORMAT)
            except ValueError:
                return False

        target_sample_ids = [int(node.sample_id)]
        if sample_metadata_field_same_for_all(schema, field_key):
            target_sample_ids = sorted(
                int(sample_id)
                for sample_id in getattr(self.main_window, "sample_catalog", {}).keys()
            )
            if int(node.sample_id) not in target_sample_ids:
                target_sample_ids.append(int(node.sample_id))
                target_sample_ids.sort()

        pending_records = {}
        for sample_id in target_sample_ids:
            sample_record = normalize_sample_catalog_record(
                getattr(self.main_window, "sample_catalog", {}).get(
                    int(sample_id),
                    self.sample_record(sample_id),
                ),
                schema,
            )
            old_value = str(sample_record.get(field_key, "") or "")
            if old_value == value_text:
                continue
            sample_record[field_key] = value_text
            pending_records[int(sample_id)] = normalize_sample_catalog_record(sample_record, schema)

        if not pending_records:
            return False

        before_state = self.main_window.capture_data_state() if hasattr(self.main_window, "capture_data_state") else None
        for sample_id, sample_record in pending_records.items():
            self.main_window.sample_catalog[int(sample_id)] = sample_record

        changed_sample_ids = sorted(pending_records)
        for sample_id in changed_sample_ids:
            field_index = self.field_index(sample_id, field_key, 1)
            if field_index.isValid():
                self.dataChanged.emit(field_index, field_index, [Qt.DisplayRole, Qt.EditRole])
        if field_key == "sample_type":
            for sample_id in changed_sample_ids:
                value_index = self.field_index(sample_id, field_key, 1)
                parent_index = value_index.parent()
                if not parent_index.isValid() or self.rowCount(parent_index) <= 0:
                    continue
                top_left = self.index(0, 0, parent_index)
                bottom_right = self.index(self.rowCount(parent_index) - 1, 1, parent_index)
                self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, Qt.EditRole, self.EDITABLE_ROLE, Qt.ForegroundRole])
                if hasattr(self.main_window, "reopen_sample_catalog_persistent_editors_for_sample"):
                    self.main_window.reopen_sample_catalog_persistent_editors_for_sample(sample_id)

        refresh_metadata = getattr(self.main_window, "refresh_freeze_count_timeseries_metadata_from_sample_catalog", None)
        if callable(refresh_metadata):
            refresh_metadata(relabel_headers=(field_key == "sample_name"))
        if before_state is not None and hasattr(self.main_window, "push_data_history"):
            self.main_window.push_data_history("Update Sample Metadata", before_state)
        if field_key == "sample_name":
            for callback_name in ("update_cursor_sample_controls", "refresh_cells_panel"):
                callback = getattr(self.main_window, callback_name, None)
                if callable(callback):
                    callback()
        if hasattr(self.main_window, "log"):
            if len(changed_sample_ids) > 1:
                self.main_window.log(f"Update {field_key} to {value_text} for all samples")
            else:
                self.main_window.log(f"Update sample {node.sample_id} {field_key} to {value_text}")
        return True


class SampleCatalogTreeDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if int(index.column()) == 1 and str(index.data(SampleCatalogTreeModel.FIELD_NAME_ROLE) or ""):
            option_without_text = QStyleOptionViewItem(option)
            self.initStyleOption(option_without_text, index)
            option_without_text.text = ""
            style = (
                option_without_text.widget.style()
                if option_without_text.widget is not None
                else QApplication.style()
            )
            style.drawControl(QStyle.CE_ItemViewItem, option_without_text, painter, option_without_text.widget)
            return
        super().paint(painter, option, index)

    def createEditor(self, parent, option, index):
        if int(index.column()) != 1:
            return None
        field_name = str(index.data(SampleCatalogTreeModel.FIELD_NAME_ROLE) or "")
        if not field_name:
            return None
        field_type = str(index.data(SampleCatalogTreeModel.FIELD_TYPE_ROLE) or "text")
        is_editable = bool(index.data(SampleCatalogTreeModel.EDITABLE_ROLE))
        if field_type == "sample_type":
            editor = QComboBox(parent)
            editor.addItem("", "")
            for sample_type in ALLOWED_SAMPLE_TYPES:
                editor.addItem(sample_type, sample_type)
            editor.setEditable(False)
            editor.setInsertPolicy(QComboBox.NoInsert)
            editor.setFixedHeight(SAMPLE_CATALOG_TREE_EDITOR_HEIGHT)
            editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            editor.setEnabled(is_editable)
            editor.activated.connect(self.commit_combo_data)
            return editor

        editor = QLineEdit(parent)
        editor.setFixedHeight(SAMPLE_CATALOG_TREE_EDITOR_HEIGHT)
        editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        editor.setFocusPolicy(Qt.ClickFocus)
        editor.setEnabled(is_editable)
        editor.setReadOnly(not is_editable)
        if field_type == "number":
            validator = QDoubleValidator(editor)
            validator.setNotation(QDoubleValidator.StandardNotation)
            editor.setValidator(validator)
            editor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            editor.setPlaceholderText("number")
        elif field_type == "datetime":
            editor.setInputMask(SAMPLE_CATALOG_DATETIME_INPUT_MASK)
            editor.setPlaceholderText("")
            editor.setToolTip(SAMPLE_CATALOG_DATETIME_HINT)
        else:
            editor.setPlaceholderText("text")
        editor.editingFinished.connect(self.commit_line_edit_data)
        return editor

    def commit_combo_data(self, *_args):
        editor = self.sender()
        if isinstance(editor, QComboBox):
            self.commitData.emit(editor)

    def commit_line_edit_data(self):
        editor = self.sender()
        if isinstance(editor, QLineEdit):
            self.commitData.emit(editor)

    def setEditorData(self, editor, index):
        field_type = str(index.data(SampleCatalogTreeModel.FIELD_TYPE_ROLE) or "text")
        editor.setEnabled(bool(index.data(SampleCatalogTreeModel.EDITABLE_ROLE)))
        if isinstance(editor, QComboBox):
            value_text = str(index.data(Qt.EditRole) or "")
            combo_index = editor.findData(value_text)
            editor.setCurrentIndex(combo_index if combo_index >= 0 else 0)
            return
        if field_type == "datetime" and isinstance(editor, QLineEdit):
            value_text = str(index.data(Qt.EditRole) or "").strip()
            if not value_text:
                editor.clear()
                return
            try:
                parsed_value = datetime.strptime(value_text, SAMPLE_CATALOG_DATETIME_STORAGE_FORMAT)
            except ValueError:
                editor.clear()
                return
            editor.setText(parsed_value.strftime(SAMPLE_CATALOG_DATETIME_INPUT_FORMAT))
            return
        if isinstance(editor, QLineEdit):
            editor.setText(str(index.data(Qt.EditRole) or ""))
            editor.deselect()
            return
        super().setEditorData(editor, index)

    def updateEditorGeometry(self, editor, option, index):
        if int(index.column()) != 1:
            super().updateEditorGeometry(editor, option, index)
            return
        editor_height = min(SAMPLE_CATALOG_TREE_EDITOR_HEIGHT, max(18, option.rect.height() - 4))
        editor_rect = QRect(
            option.rect.left() + SAMPLE_CATALOG_TREE_EDITOR_LEFT_MARGIN,
            option.rect.top() + max(0, int((option.rect.height() - editor_height) / 2)),
            max(
                40,
                option.rect.width()
                - SAMPLE_CATALOG_TREE_EDITOR_LEFT_MARGIN
                - SAMPLE_CATALOG_TREE_EDITOR_RIGHT_MARGIN,
            ),
            editor_height,
        )
        editor.setGeometry(editor_rect)

    def setModelData(self, editor, model, index):
        field_type = str(index.data(SampleCatalogTreeModel.FIELD_TYPE_ROLE) or "text")
        if isinstance(editor, QComboBox):
            model.setData(index, str(editor.currentData() or ""), Qt.EditRole)
            return
        if field_type == "datetime" and isinstance(editor, QLineEdit):
            raw_text = str(editor.text() or "")
            normalized_input = raw_text.replace("_", "").strip()
            if not normalized_input:
                model.setData(index, "", Qt.EditRole)
                return
            try:
                parsed_value = datetime.strptime(raw_text, SAMPLE_CATALOG_DATETIME_INPUT_FORMAT)
            except ValueError:
                return
            model.setData(index, parsed_value.strftime(SAMPLE_CATALOG_DATETIME_STORAGE_FORMAT), Qt.EditRole)
            return
        if isinstance(editor, QLineEdit):
            model.setData(index, str(editor.text() or "").strip(), Qt.EditRole)
            return
        super().setModelData(editor, model, index)


class SampleCatalogTreeView(QTreeView):
    def drawBranches(self, painter, rect, index):
        super().drawBranches(painter, rect, index)
        parent_index = index.parent()
        if not parent_index.isValid():
            return
        model = self.model()
        child_count = model.rowCount(parent_index) if model is not None else 0
        if child_count <= 0:
            return

        child_index = index.row()
        x = rect.left() + max(6, int(self.indentation() * 0.6))
        center_y = rect.center().y()
        top_y = center_y if child_index == 0 else rect.top()
        bottom_y = center_y if child_index == (child_count - 1) else rect.bottom()

        painter.save()
        line_color = self.palette().color(QPalette.Mid)
        line_color.setAlpha(180)
        pen = QPen(line_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(x, top_y, x, bottom_y)
        painter.drawLine(x, center_y, rect.right() - 2, center_y)
        painter.restore()


class SampleCatalogPanelMixin:
    def build_sample_catalog_panel(self):
        panel = QWidget(self)
        panel.setMinimumWidth(SAMPLE_CATALOG_PANEL_MIN_WIDTH)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.sample_catalog_tree = SampleCatalogTreeView(panel)
        self.sample_catalog_tree_model = SampleCatalogTreeModel(self, self.sample_catalog_tree)
        self.sample_catalog_tree.setModel(self.sample_catalog_tree_model)
        self.sample_catalog_tree.setHeaderHidden(True)
        self.sample_catalog_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.sample_catalog_tree.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.SelectedClicked
        )
        self.sample_catalog_tree.setRootIsDecorated(True)
        self.sample_catalog_tree.setUniformRowHeights(True)
        self.sample_catalog_tree.setAlternatingRowColors(False)
        self.sample_catalog_tree.setAllColumnsShowFocus(True)
        self.sample_catalog_tree.setIndentation(SAMPLE_CATALOG_TREE_INDENTATION)
        self.sample_catalog_tree.header().setStretchLastSection(False)
        self.sample_catalog_tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.sample_catalog_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.sample_catalog_tree.header().resizeSection(0, SAMPLE_CATALOG_TREE_LABEL_COLUMN_WIDTH)
        self.sample_catalog_tree.setStyleSheet(
            f"QTreeView::item {{ min-height: {SAMPLE_CATALOG_TREE_ROW_HEIGHT}px; }}"
        )
        self.sample_catalog_tree_delegate = SampleCatalogTreeDelegate(self.sample_catalog_tree)
        self.sample_catalog_tree.setItemDelegate(self.sample_catalog_tree_delegate)
        self.sample_catalog_tree.selectionModel().selectionChanged.connect(self.update_sample_catalog_buttons)
        self.sample_catalog_tree.expanded.connect(self.open_sample_catalog_persistent_editors_for_sample_index)
        layout.addWidget(self.sample_catalog_tree, 1)

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
            "Expand a sample to edit metadata. Fields marked [all] use one shared value for every sample. Cursor mode only assigns selected cells to a sample or creates a new sample.",
            panel,
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        layout.addWidget(hint)

        self.refresh_sample_catalog_tree(preserve_selection=False)
        return panel

    def selected_sample_catalog_id(self):
        if not hasattr(self, "sample_catalog_tree"):
            return None
        current_index = self.sample_catalog_tree.currentIndex()
        if not current_index.isValid():
            return None
        sample_id = current_index.data(SampleCatalogTreeModel.SAMPLE_ID_ROLE)
        if sample_id is None:
            return None
        try:
            return int(sample_id)
        except (TypeError, ValueError):
            return None

    def sample_catalog_field_is_relevant(self, field_name, sample_record):
        return sample_metadata_field_is_relevant(
            self.active_sample_metadata_schema(),
            field_name,
            sample_record,
        )

    def sample_catalog_top_index_by_id(self, sample_id):
        if not hasattr(self, "sample_catalog_tree_model"):
            return QModelIndex()
        for row in range(self.sample_catalog_tree_model.rowCount()):
            index = self.sample_catalog_tree_model.index(row, 0)
            if index.data(SampleCatalogTreeModel.SAMPLE_ID_ROLE) == int(sample_id):
                return index
        return QModelIndex()

    def open_sample_catalog_persistent_editors_for_sample_index(self, sample_index):
        if not sample_index.isValid():
            return
        sample_index = self.sample_catalog_tree_model.index(sample_index.row(), 0, sample_index.parent())
        for row in range(self.sample_catalog_tree_model.rowCount(sample_index)):
            value_index = self.sample_catalog_tree_model.index(row, 1, sample_index)
            self.sample_catalog_tree.openPersistentEditor(value_index)
        QTimer.singleShot(0, self.clear_sample_catalog_editor_text_selection)

    def reopen_sample_catalog_persistent_editors_for_sample(self, sample_id):
        top_index = self.sample_catalog_top_index_by_id(sample_id)
        if not top_index.isValid() or not self.sample_catalog_tree.isExpanded(top_index):
            return
        for row in range(self.sample_catalog_tree_model.rowCount(top_index)):
            value_index = self.sample_catalog_tree_model.index(row, 1, top_index)
            self.sample_catalog_tree.closePersistentEditor(value_index)
            self.sample_catalog_tree.openPersistentEditor(value_index)
        QTimer.singleShot(0, self.clear_sample_catalog_editor_text_selection)

    def clear_sample_catalog_editor_text_selection(self):
        if not hasattr(self, "sample_catalog_tree"):
            return
        for editor in self.sample_catalog_tree.findChildren(QLineEdit):
            editor.deselect()

    def refresh_sample_catalog_tree(self, select_sample_id=None, preserve_selection=True):
        if not hasattr(self, "sample_catalog_tree_model"):
            return

        self.ensure_sample_catalog_matches_cell_records()

        if select_sample_id is None and preserve_selection:
            select_sample_id = self.selected_sample_catalog_id()

        expanded_sample_ids = set()
        for row in range(self.sample_catalog_tree_model.rowCount()):
            top_index = self.sample_catalog_tree_model.index(row, 0)
            if self.sample_catalog_tree.isExpanded(top_index):
                expanded_sample_ids.add(int(top_index.data(SampleCatalogTreeModel.SAMPLE_ID_ROLE)))

        self.sample_catalog_tree_model.refresh()

        for row in range(self.sample_catalog_tree_model.rowCount()):
            top_index = self.sample_catalog_tree_model.index(row, 0)
            sample_id = int(top_index.data(SampleCatalogTreeModel.SAMPLE_ID_ROLE))
            should_expand = sample_id in expanded_sample_ids or (
                select_sample_id is not None and sample_id == int(select_sample_id)
            )
            self.sample_catalog_tree.setExpanded(top_index, should_expand)
            if should_expand:
                self.open_sample_catalog_persistent_editors_for_sample_index(top_index)

        if select_sample_id is not None:
            target_index = self.sample_catalog_top_index_by_id(select_sample_id)
            if target_index.isValid():
                self.sample_catalog_tree.setCurrentIndex(target_index)

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
        self.sample_catalog[int(sample_id)] = self.default_sample_record(sample_id)
        self.recompute_next_sample_id(preserve_if_larger=False)
        self.refresh_sample_catalog_tree(select_sample_id=sample_id, preserve_selection=False)
        self.refresh_freeze_count_timeseries_metadata_from_sample_catalog()
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
            sample_name = self.sample_name_for_id(sample_id) or self.default_sample_name(sample_id)
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
        self.recompute_next_sample_id(preserve_if_larger=False)
        self.refresh_sample_catalog_tree(preserve_selection=False)
        self.refresh_freeze_count_timeseries_metadata_from_sample_catalog()
        self.push_data_history("Delete Sample", before_state)
        self.log(f"Delete sample {sample_id}")
