"""Separate frame panels that share their image position and zoom.

The current panel owns annotations. Reference panels have their own image-edit
overlays, but never send cell-editing mouse events to the current panel.
"""

from contextlib import contextmanager

import shiboken6
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap, QTransform
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QFrame,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QSizePolicy,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)
from icescopy_cell_items import CellCircle


class CellSelectionTreeWidget(QTreeWidget):
    """Report finished user selections, separate from model refresh signals."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._selection_navigation_start = None
        self._clicked_cell_id = None
        self.itemClicked.connect(self._record_cell_row_click)

    def _record_cell_row_click(self, item, _column):
        if item.parent() is None:
            self._clicked_cell_id = item.data(0, Qt.UserRole)

    def cancel_pending_selection_center(self):
        self._selection_navigation_start = None

    def moveCursor(self, action, modifiers):
        # Arrow navigation visits cells, not their nonselectable detail rows.
        if action in (QAbstractItemView.MoveUp, QAbstractItemView.MoveDown):
            item = self.currentItem()
            if item is not None:
                while item.parent() is not None:
                    item = item.parent()
                row = self.indexOfTopLevelItem(item)
                step = -1 if action == QAbstractItemView.MoveUp else 1
                row = max(0, min(self.topLevelItemCount() - 1, row + step))
                return self.indexFromItem(self.topLevelItem(row))
        return super().moveCursor(action, modifiers)

    def mousePressEvent(self, event):
        self._selection_navigation_start = (
            self.main_window.cell_list_navigation_state()
            if event.button() == Qt.LeftButton else None
        )
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        before = self._selection_navigation_start
        self._selection_navigation_start = None
        self._clicked_cell_id = None
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.main_window.navigate_after_cell_list_selection(
                before, reapply=self._clicked_cell_id is not None,
            )

    def keyPressEvent(self, event):
        before = (
            self.main_window.cell_list_navigation_state()
            if self._selection_navigation_start is None else None
        )
        super().keyPressEvent(event)
        self.main_window.navigate_after_cell_list_selection(before)

    def focusOutEvent(self, event):
        self._selection_navigation_start = None
        super().focusOutEvent(event)


class LinkedGraphicsView(QGraphicsView):
    """Report camera changes and reserve room to center cells near image edges.

    ``content_rect`` is the actual image area. The native scene rectangle is
    larger so scroll limits cannot give different panels different centers.
    Callers fitting the image should pass ``content_rect`` to ``fitInView``.
    """

    cameraChanged = Signal(object)
    viewportResized = Signal(object)
    interactionChanged = Signal()

    def __init__(self, scene, parent=None):
        self._camera_change_depth = 0
        self.content_rect = QRectF()
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(0, 0)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def scene_center(self):
        # QGraphicsView.centerOn uses integer half-width/height. QRect.center()
        # uses (size - 1) / 2 instead, which would move even-sized views by one
        # pixel on every synchronization.
        return self.mapToScene(self.viewport().width() // 2, self.viewport().height() // 2)

    @contextmanager
    def _camera_change(self):
        self._camera_change_depth += 1
        try:
            yield
        finally:
            self._camera_change_depth -= 1
            if self._camera_change_depth == 0:
                self.cameraChanged.emit(self)

    def _update_navigation_bounds(self):
        if self.content_rect.isEmpty():
            return
        center = self.scene_center()
        scale = max(abs(self.transform().m11()), 1e-6)
        margin = max(
            self.content_rect.width(),
            self.content_rect.height(),
            self.viewport().width() / scale,
            self.viewport().height() / scale,
        )
        QGraphicsView.setSceneRect(
            self, self.content_rect.adjusted(-margin, -margin, margin, margin)
        )
        self._center_on_image_point(center)

    def _center_on_image_point(self, point):
        QGraphicsView.centerOn(self, point)
        # Qt rounds half-pixel negative offsets differently from positive ones.
        # Use one integer viewport origin for both reading and setting centers,
        # so repeated resizing/synchronizing cannot accumulate one-pixel moves.
        mapped = self.transform().map(point)
        self.horizontalScrollBar().setValue(round(mapped.x()) - self.viewport().width() // 2)
        self.verticalScrollBar().setValue(round(mapped.y()) - self.viewport().height() // 2)

    def setSceneRect(self, *args):
        with self._camera_change():
            self.content_rect = QRectF(*args)
            if self.content_rect.isEmpty():
                QGraphicsView.setSceneRect(self, self.content_rect)
            else:
                self._update_navigation_bounds()

    def setTransform(self, matrix, combine=False):
        with self._camera_change():
            QGraphicsView.setTransform(self, matrix, combine)
            self._update_navigation_bounds()

    def resetTransform(self):
        with self._camera_change():
            QGraphicsView.resetTransform(self)
            self._update_navigation_bounds()

    def scale(self, sx, sy):
        with self._camera_change():
            QGraphicsView.scale(self, sx, sy)
            self._update_navigation_bounds()

    def centerOn(self, *args):
        with self._camera_change():
            if len(args) == 1 and isinstance(args[0], QGraphicsItem):
                point = args[0].sceneBoundingRect().center()
            else:
                point = QPointF(*args)
            self._center_on_image_point(point)

    def fitInView(self, *args):
        with self._camera_change():
            QGraphicsView.fitInView(self, *args)
            self._update_navigation_bounds()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        if self._camera_change_depth == 0:
            self.cameraChanged.emit(self)

    def resizeEvent(self, event):
        # A resize must restore the shared center, rather than adopt the center
        # temporarily produced while Qt lays out the neighboring panels.
        self._camera_change_depth += 1
        try:
            super().resizeEvent(event)
            self._update_navigation_bounds()
        finally:
            self._camera_change_depth -= 1
        self.viewportResized.emit(self)

    def setDragMode(self, mode):
        super().setDragMode(mode)
        self.interactionChanged.emit()


class ReferenceGraphicsView(LinkedGraphicsView):
    """Pan/zoom and image-edit interactions without current-frame cell actions."""

    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main_window = main_window

    def focusInEvent(self, event):
        self.main_window.set_active_image_panel("viewer")
        super().focusInEvent(event)

    def mousePressEvent(self, event):
        self.main_window.set_active_image_panel("viewer")
        self.setFocus()
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        if not self.main_window.is_pan_interaction_active():
            event.accept()
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()
        current_scale = self.transform().m11()
        if delta > 0 and current_scale < self.main_window.maximum_zoom:
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            self.scale(1.15, 1.15)
        elif delta < 0 and current_scale > 0.03:
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            self.scale(1 / 1.15, 1 / 1.15)
        self.main_window.updateZoomTextbox()
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Comma, Qt.Key_Period):
            self.main_window.handle_frame_navigation_shortcut(key)
            event.accept()
            return
        if key == Qt.Key_Space:
            self.main_window.keyPressEvent(event)
            event.accept()
            return
        if self.main_window.tool_mode == "image-edit":
            if key in (Qt.Key_Return, Qt.Key_Enter) and self.main_window.is_image_edit_crop_active():
                self.main_window.trigger_image_edit_crop_apply_button()
                event.accept()
                return
            if key == Qt.Key_Escape and self.main_window.is_image_edit_crop_active():
                self.main_window.cancel_image_edit_crop()
                event.accept()
                return
        # Cell shortcuts are handled by the main window, never by a reference
        # scene; Delete/Backspace do not act on an unseen current selection.
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.main_window.keyReleaseEvent(event)
            event.accept()
            return
        super().keyReleaseEvent(event)


class FramePanel(QWidget):
    """A labeled image view and its disposable frame-specific overlays."""

    def __init__(self, role, view, *, current=False):
        super().__init__()
        self.role = role
        self.view = view
        self.scene = view.scene()
        self.is_current = current
        self.pixmap_item = None
        self.frame_index = None
        self.crop_overlay = None
        self.uniform_overlay = None
        self.cell_items = []
        self.header = QLabel(role)
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setMargin(5)
        self.header.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        font = self.header.font()
        font.setBold(current)
        self.header.setFont(font)
        self.header.setFrameStyle(QFrame.Panel | QFrame.Plain)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(view, 1)

    def show_reference(self, frame_index, pixmap, bounds, *, preview=False):
        self.frame_index = frame_index if pixmap is not None else None
        if self.pixmap_item is None:
            self.pixmap_item = self.scene.addPixmap(QPixmap())
            self.pixmap_item.setZValue(-100)
        self.pixmap_item.setPixmap(pixmap if pixmap is not None else QPixmap())
        self.pixmap_item.setPos(0, 0)
        self.view.setSceneRect(
            QRectF(0, 0, pixmap.width(), pixmap.height()) if pixmap is not None else bounds
        )
        if pixmap is not None:
            self.header.setText(f"{self.role} — Frame {frame_index}")
        elif frame_index is not None and preview:
            self.header.setText(f"{self.role} — updates after seeking")
        elif frame_index is not None:
            self.header.setText(f"{self.role} — frame unavailable")
        else:
            edge = "earlier" if self.role == "Previous" else "later"
            self.header.setText(f"{self.role} — no {edge} frame")
        if pixmap is None:
            self.clear_cells()
            for overlay in (self.crop_overlay, self.uniform_overlay):
                if overlay is not None:
                    overlay.hide()

    def clear_cells(self):
        for item in self.cell_items:
            if shiboken6.isValid(item) and item.scene() is self.scene:
                self.scene.removeItem(item)
        self.cell_items = []

    def refresh_cells(self, main_window):
        """Render this frame's layout without moving or editing stored cells."""
        if self.frame_index is None or self.pixmap_item is None:
            self.clear_cells()
            return
        previous = {item.cell_id: item for item in self.cell_items}
        updated = []
        seen_ids = set()
        image_rect = self.pixmap_item.sceneBoundingRect()
        for source in main_window.keyframe_interpolation(self.frame_index):
            cell_id = int(source.cell_id)
            if cell_id in seen_ids:
                continue
            seen_ids.add(cell_id)
            pixel_position = tuple(float(value) for value in source.circle_pixel_positions)
            position = main_window.image_pixel_to_scene_coordinates(
                *pixel_position, image_rect=image_rect, index=self.frame_index,
            )
            item = previous.pop(cell_id, None)
            if item is None:
                item = CellCircle(
                    main_window, position, float(source.circle_sizes),
                    pixel_position, cell_id, read_only=True,
                )
                self.scene.addItem(item)
            else:
                item.sync_from_data(
                    position, float(source.circle_sizes), pixel_position, cell_id,
                    edit_chosen=False, hover=False, pressed=False,
                )
            updated.append(item)
        for item in previous.values():
            self.scene.removeItem(item)
        self.cell_items = updated

    def clear(self):
        if not self.is_current:
            self.scene.clear()
            self.crop_overlay = None
            self.uniform_overlay = None
        self.cell_items = []
        self.pixmap_item = None
        self.frame_index = None
        self.header.setText(f"{self.role} — no frames loaded")


class ComparisonViewer(QWidget):
    """One, two, or three equal image panels with a shared camera."""

    def __init__(self, current_view, main_window):
        super().__init__()
        self.main_window = main_window
        self._sync_depth = 0
        self._camera_transform = QTransform(current_view.transform())
        self._camera_center = QPointF(current_view.scene_center())
        self.current = FramePanel("Current", current_view, current=True)
        self.previous = FramePanel(
            "Previous", ReferenceGraphicsView(QGraphicsScene(self), main_window)
        )
        self.next = FramePanel(
            "Next", ReferenceGraphicsView(QGraphicsScene(self), main_window)
        )
        self.reference_panels = [self.previous, self.next]
        self.panels = [self.previous, self.current, self.next]
        self.views = [panel.view for panel in self.panels]
        self._layout = QBoxLayout(QBoxLayout.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(3)
        for panel in self.panels:
            self._layout.addWidget(panel, 1)
            panel.view.cameraChanged.connect(self.sync_from)
            panel.view.viewportResized.connect(self._restore_camera_after_resize)
        current_view.interactionChanged.connect(self.sync_interaction)
        self.set_layout(1, "horizontal")
        self.sync_interaction()

    @contextmanager
    def suspend_sync(self):
        """Batch view changes; the caller chooses the authoritative view after."""
        self._sync_depth += 1
        try:
            yield
        finally:
            self._sync_depth -= 1

    def _apply_camera(self):
        with self.suspend_sync():
            for view in self.views:
                view.setTransform(self._camera_transform)
                view.centerOn(self._camera_center)

    def sync_from(self, view):
        if self._sync_depth:
            return
        self._camera_transform = QTransform(view.transform())
        self._camera_center = QPointF(view.scene_center())
        self._apply_camera()
        if hasattr(self.main_window, "zoom_textbox"):
            self.main_window.updateZoomTextbox()

    def _restore_camera_after_resize(self, _view):
        if not self._sync_depth:
            self._apply_camera()

    def set_layout(self, count, orientation):
        with self.suspend_sync():
            self._layout.setDirection(
                QBoxLayout.TopToBottom if orientation == "vertical" else QBoxLayout.LeftToRight
            )
            self.previous.setVisible(count >= 2)
            self.next.setVisible(count >= 3)
            self.current.show()
            self._layout.activate()
        self._apply_camera()

    def show_frames(self, slots, current_index, pixmaps, preview=False):
        """Update references from already-rendered pixmaps, without decoding."""
        current_pixmap = pixmaps.get(current_index)
        bounds = (
            QRectF(0, 0, current_pixmap.width(), current_pixmap.height())
            if current_pixmap is not None
            else QRectF(self.current.view.content_rect)
        )
        with self.suspend_sync():
            self.current.frame_index = current_index
            self.current.pixmap_item = self.main_window.pixmap_item
            self.current.view.setSceneRect(bounds)
            self.current.header.setText(f"Current — Frame {current_index}")
            previous_index = slots[0] if len(slots) >= 2 else None
            next_index = slots[2] if len(slots) >= 3 else None
            for panel, index in ((self.previous, previous_index), (self.next, next_index)):
                panel.show_reference(index, pixmaps.get(index), bounds, preview=preview)
        self.refresh_reference_cells()

    def refresh_reference_cells(self):
        for panel in self.reference_panels:
            panel.refresh_cells(self.main_window)

    def sync_interaction(self):
        pan = self.main_window.is_pan_interaction_active() or self.current.view.dragMode() == QGraphicsView.ScrollHandDrag
        editing_image = self.main_window.tool_mode == "image-edit"
        for panel in self.reference_panels:
            view = panel.view
            view.setInteractive(editing_image and not pan)
            view.setDragMode(QGraphicsView.ScrollHandDrag if pan else QGraphicsView.NoDrag)
            cursor = Qt.OpenHandCursor if pan else Qt.ArrowCursor
            view.setCursor(cursor)
            view.viewport().setCursor(cursor)

    def clear(self):
        with self.suspend_sync():
            for panel in self.panels:
                panel.clear()
