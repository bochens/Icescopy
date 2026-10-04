"""Explicit navigation through one cell's freeze events without changing zoom."""

from PySide6.QtCore import QPointF, QRect, QSignalBlocker, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QSizePolicy, QWidget

import icescopy_stylesheet


class FreezeEventButton(QPushButton):
    """The timeline's chevron and red event dot in its existing button shape."""

    def __init__(self, direction, parent=None, *, timeline=True):
        super().__init__(parent)
        self.direction = -1 if direction < 0 else 1
        self._timeline = timeline
        self.setAutoDefault(False)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setIconSize(QSize(24, 16))

    def update_appearance(self, caret_icon, dark):
        stylesheet = (
            icescopy_stylesheet.dark_mode_button_stylesheet if dark
            else icescopy_stylesheet.light_mode_button_stylesheet
        )
        # Keep the compact width identical in both themes. All other button
        # geometry, hover and pressed styling follows the existing timeline.
        # The timeline offsets its buttons downward. A selector beside a
        # native combo box needs symmetric margins to align their centers.
        selector_margin = "" if self._timeline else "margin-top: 0px;"
        self.setStyleSheet(stylesheet + (
            "QPushButton { width: 40px; min-width: 40px; max-width: 40px; "
            + selector_margin + " }"
        ))
        icon = QIcon()
        for mode in (QIcon.Normal, QIcon.Disabled):
            pixmap = QPixmap(96, 64)
            pixmap.setDevicePixelRatio(4)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            caret_x = 0 if self.direction < 0 else 8
            caret_icon.paint(painter, QRect(caret_x, 0, 16, 16), Qt.AlignCenter, mode)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 69, 58) if mode == QIcon.Normal else QColor(145, 145, 145))
            painter.drawEllipse(QPointF(19 if self.direction < 0 else 5, 8), 2.5, 2.5)
            painter.end()
            icon.addPixmap(pixmap, mode)
        self.setIcon(icon)


class FreezeEventComboBox(QComboBox):
    """Remember the selection that opened a popup or started a key action."""

    def __init__(self, selector):
        super().__init__(selector)
        self.selector = selector
        self.activation_context = None

    def showPopup(self):
        self.selector.refresh()
        self.activation_context = self.selector.action_context()
        super().showPopup()

    def keyPressEvent(self, event):
        if not self.view().isVisible():
            self.selector.refresh()
            self.activation_context = self.selector.action_context()
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        if not self.view().isVisible():
            self.selector.refresh()
            self.activation_context = self.selector.action_context()
        super().wheelEvent(event)


class FreezeEventSelector(QWidget):
    """Keep a chosen cycle across cells; refreshes only update the controls."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._source = None
        self._cycles = ()
        self._cycle_starts = {}
        self._preferred_cycle = None
        self._chosen_cell_id = None
        self._chosen_frame = None
        self._cell_id = None
        self._frames = ()
        self._target = None
        self._previous = None
        self._next = None
        self._display_snapshot = None
        self._button_context = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.previous_button = FreezeEventButton(-1, self, timeline=False)
        self.previous_button.setAccessibleName("Previous freeze event")
        self.previous_button.setToolTip("Previous freeze event for the selected cell")
        self.combo = FreezeEventComboBox(self)
        self.combo.setAccessibleName("Freeze event")
        self.combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo.setMinimumContentsLength(0)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.next_button = FreezeEventButton(1, self, timeline=False)
        self.next_button.setAccessibleName("Next freeze event")
        self.next_button.setToolTip("Next freeze event for the selected cell")
        layout.addWidget(self.previous_button)
        layout.addWidget(self.combo, 1)
        layout.addWidget(self.next_button)
        self.previous_button.pressed.connect(self.remember_button_context)
        self.next_button.pressed.connect(self.remember_button_context)
        self.previous_button.clicked.connect(lambda: self.step_from_button(-1))
        self.next_button.clicked.connect(lambda: self.step_from_button(1))
        self.combo.activated.connect(self.activate_from_combo)

    def cycle_at(self, frame):
        return self._cycles[frame] if 0 <= frame < len(self._cycles) else None

    def refresh(self):
        window = self.main_window
        source = getattr(window, "frame_source", None)
        cycles = window.freeze_review_cycle_ids()
        if source is not self._source or cycles != self._cycles:
            self._preferred_cycle = None
            self._chosen_cell_id = None
            self._chosen_frame = None
            self._cycle_starts = {}
            for index, cycle in enumerate(cycles):
                if cycle is not None:
                    self._cycle_starts.setdefault(cycle, index)
        self._source, self._cycles = source, cycles
        selected = window.get_selected_cell_items() if hasattr(window, "cell_controller") else []
        self._cell_id = selected[0].cell_id if len(selected) == 1 else None
        self._frames = tuple(window.selected_cell_freeze_frames(selected)) if len(selected) == 1 else ()
        self._target = None
        if self._cell_id is not None:
            candidates = [frame for frame in self._frames if (
                self._preferred_cycle is None or self.cycle_at(frame) == self._preferred_cycle
            )]
            if self._chosen_cell_id == self._cell_id and self._chosen_frame in candidates:
                self._target = self._chosen_frame
            elif candidates:
                self._target = candidates[0]

        self._previous = self._next = None
        if self._target is not None:
            index = self._frames.index(self._target)
            if index > 0:
                self._previous = self._frames[index - 1]
            if index + 1 < len(self._frames):
                self._next = self._frames[index + 1]
        elif self._preferred_cycle is not None:
            # With no event in the chosen cycle, arrows still reach events on
            # either side of its start, including events without a cycle label.
            anchor = self._cycle_starts.get(self._preferred_cycle)
            if anchor is not None:
                earlier = [frame for frame in self._frames if frame < anchor]
                later = [frame for frame in self._frames if frame >= anchor]
                self._previous = earlier[-1] if earlier else None
                self._next = later[0] if later else None

        entries = []
        if self._cell_id is None:
            entries.append(("Select one cell", None))
        elif self._target is None:
            text = "No freeze events" if self._preferred_cycle is None else (
                f"Cycle {self._preferred_cycle + 1}, no event"
            )
            entries.append((text, None))
        for index, frame in enumerate(self._frames):
            cycle = self.cycle_at(frame)
            label = f"Event {index + 1}" if cycle is None else f"Cycle {cycle + 1}"
            entries.append((f"{label}, frame {frame}", frame))

        snapshot = (tuple(entries), self._target)
        if snapshot != self._display_snapshot:
            if self.combo.view().isVisible():
                self.combo.hidePopup()
            blocker = QSignalBlocker(self.combo)
            self.combo.clear()
            for label, frame in entries:
                self.combo.addItem(label, frame)
                if frame is None:
                    self.combo.model().item(self.combo.count() - 1).setEnabled(False)
            del blocker
            self._display_snapshot = snapshot
        # Qt changes the displayed index before emitting activated. If that
        # action is rejected as stale, restore the retained choice even when
        # neither the event list nor our target changed.
        target_index = next((i for i, (_, frame) in enumerate(entries) if frame == self._target), 0)
        if self.combo.currentIndex() != target_index:
            blocker = QSignalBlocker(self.combo)
            self.combo.setCurrentIndex(target_index)
            del blocker
        allowed = window.cell_list_navigation_state() is not None and self._cell_id is not None
        self.combo.setEnabled(allowed and bool(self._frames))
        self.previous_button.setEnabled(allowed and self._previous is not None)
        self.next_button.setEnabled(allowed and self._next is not None)
        self.combo.setToolTip(
            self.combo.currentText() + "\nChoose a freeze event. Cycle choice stays the same when selecting another cell."
        )

    def selected_frame(self):
        self.refresh()
        return self._target

    def remember_target(self):
        """Remember a choice only for a deliberate list or event action."""
        if self._target is not None:
            self._chosen_cell_id = self._cell_id
            self._chosen_frame = self._target
            self._preferred_cycle = self.cycle_at(self._target)

    def action_context(self):
        window = self.main_window
        state = window.cell_list_navigation_state()
        if state is None or len(state[-1]) != 1:
            return None
        frames = tuple(window.selected_cell_freeze_frames(window.get_selected_cell_items()))
        return state, frames, window.freeze_review_cycle_ids()

    def remember_button_context(self):
        self.refresh()
        self._button_context = self.action_context()

    def step_from_button(self, direction):
        before, self._button_context = self._button_context, None
        if before is not None and before == self.action_context():
            self.step_event(direction)

    def activate_from_combo(self, index):
        before = self.combo.activation_context
        if before is not None and before != self.action_context():
            self.refresh()
            return
        self.activate_event(index)

    def activate_event(self, index):
        frame = self.combo.itemData(index)
        cell_id = self._cell_id
        source = self._source
        self.refresh()
        if cell_id == self._cell_id and source is self._source:
            self.navigate(frame)

    def step_event(self, direction):
        self.refresh()
        self.navigate(self._previous if direction < 0 else self._next)

    def navigate(self, frame):
        window = self.main_window
        if self.action_context() is None or frame is None or frame not in self._frames:
            return
        self._target = frame
        self.remember_target()
        window.navigate_to_image(frame, history_text="Show Cell Freeze Frame")
        if window.cells_auto_center_checkbox.isChecked():
            window.center_on_cell_selection()
        self.refresh()
