from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
from PySide6.QtGui import QUndoCommand


class SessionSnapshotCommand(QUndoCommand):
    def __init__(self, main_window, text, before_state, after_state):
        super().__init__(text)
        self.main_window = main_window
        self.before_state = before_state
        self.after_state = after_state
        self._first_redo = True

    def undo(self):
        self.main_window.restore_session_state(self.before_state, preserve_active_tool=True)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return
        self.main_window.restore_session_state(self.after_state, preserve_active_tool=True)


class SessionCellCommand(QUndoCommand):
    def __init__(self, main_window, text, before_state, after_state):
        super().__init__(text)
        self.main_window = main_window
        self.before_state = before_state
        self.after_state = after_state
        self._first_redo = True

    def undo(self):
        self.main_window.restore_cell_state(self.before_state, preserve_active_tool=True)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return
        self.main_window.restore_cell_state(self.after_state, preserve_active_tool=True)


class SessionTimelineMarkersCommand(QUndoCommand):
    def __init__(self, main_window, text, before_state, after_state):
        super().__init__(text)
        self.main_window = main_window
        self.before_state = before_state
        self.after_state = after_state
        self._first_redo = True

    def undo(self):
        self.main_window.restore_timeline_marker_state(self.before_state, preserve_active_tool=True)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return
        self.main_window.restore_timeline_marker_state(self.after_state, preserve_active_tool=True)


class SessionImageListCommand(QUndoCommand):
    def __init__(self, main_window, text, before_state, after_state):
        super().__init__(text)
        self.main_window = main_window
        self.before_state = before_state
        self.after_state = after_state
        self._first_redo = True

    def undo(self):
        self.main_window.restore_image_session_state(self.before_state, preserve_active_tool=True)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return
        self.main_window.restore_image_session_state(self.after_state, preserve_active_tool=True)


class SessionLoadedImagesCommand(QUndoCommand):
    def __init__(self, main_window, text, before_state, after_state):
        super().__init__(text)
        self.main_window = main_window
        self.before_state = before_state
        self.after_state = after_state
        self._first_redo = True

    def undo(self):
        self.main_window.restore_loaded_images_state(self.before_state, preserve_active_tool=True)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return
        self.main_window.restore_loaded_images_state(self.after_state, preserve_active_tool=True)


class SessionDataCommand(QUndoCommand):
    def __init__(self, main_window, text, before_state, after_state):
        super().__init__(text)
        self.main_window = main_window
        self.before_state = before_state
        self.after_state = after_state
        self._first_redo = True

    def undo(self):
        self.main_window.restore_data_state(self.before_state, preserve_active_tool=True)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return
        self.main_window.restore_data_state(self.after_state, preserve_active_tool=True)


class SessionImageEditCommand(QUndoCommand):
    def __init__(self, main_window, text, before_state, after_state):
        super().__init__(text)
        self.main_window = main_window
        self.before_state = before_state
        self.after_state = after_state
        self._first_redo = True

    def undo(self):
        self.main_window.restore_image_edit_history_state(self.before_state, preserve_active_tool=True)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return
        self.main_window.restore_image_edit_history_state(self.after_state, preserve_active_tool=True)


class FrameNavigationCommand(QUndoCommand):
    def __init__(self, main_window, text, before_index, after_index):
        super().__init__(text)
        self.main_window = main_window
        self.before_index = int(before_index)
        self.after_index = int(after_index)
        self._first_redo = True

    def undo(self):
        self.main_window.restore_navigation_index(self.before_index, preserve_active_tool=True)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return
        self.main_window.restore_navigation_index(self.after_index, preserve_active_tool=True)


class ImageListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []
        self._tooltips = []

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._entries)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        if row < 0 or row >= len(self._entries):
            return None

        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._entries[row]
        if role == Qt.ToolTipRole:
            return self._tooltips[row]
        return None

    def set_items(self, entries, tooltips):
        self.beginResetModel()
        self._entries = list(entries)
        self._tooltips = list(tooltips)
        self.endResetModel()

    def append_items(self, entries, tooltips):
        if not entries:
            return
        start = len(self._entries)
        end = start + len(entries) - 1
        self.beginInsertRows(QModelIndex(), start, end)
        self._entries.extend(entries)
        self._tooltips.extend(tooltips)
        self.endInsertRows()

    def remove_rows(self, rows):
        if not rows:
            return

        sorted_rows = sorted(set(rows))
        ranges = []
        range_start = sorted_rows[0]
        range_end = sorted_rows[0]
        for row in sorted_rows[1:]:
            if row == range_end + 1:
                range_end = row
            else:
                ranges.append((range_start, range_end))
                range_start = row
                range_end = row
        ranges.append((range_start, range_end))

        for start, end in reversed(ranges):
            self.beginRemoveRows(QModelIndex(), start, end)
            del self._entries[start:end + 1]
            del self._tooltips[start:end + 1]
            self.endRemoveRows()

    def update_items(self, row_data):
        for row in sorted(row_data):
            if not (0 <= row < len(self._entries)):
                continue

            entry_text, tooltip = row_data[row]
            entry_changed = self._entries[row] != entry_text
            tooltip_changed = self._tooltips[row] != tooltip
            if not entry_changed and not tooltip_changed:
                continue

            self._entries[row] = entry_text
            self._tooltips[row] = tooltip
            model_index = self.index(row, 0)
            self.dataChanged.emit(model_index, model_index, [Qt.DisplayRole, Qt.ToolTipRole])
