import math

import cv2
import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QBrush,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QGraphicsObject, QWidget


def exposure_gain(exposure_stops):
    return float(2.0 ** float(exposure_stops))


def contrast_gain(contrast_percent):
    contrast_percent = float(contrast_percent)
    return max(0.0, 1.0 + (contrast_percent / 100.0))


def normalize_angle_degrees(angle_degrees):
    angle_degrees = float(angle_degrees)
    while angle_degrees <= -180.0:
        angle_degrees += 360.0
    while angle_degrees > 180.0:
        angle_degrees -= 360.0
    return angle_degrees


def rotated_crop_corners(crop_state):
    center_x = float(crop_state["center_x"])
    center_y = float(crop_state["center_y"])
    crop_width = float(crop_state["width"])
    crop_height = float(crop_state["height"])
    angle_radians = math.radians(float(crop_state["angle"]))
    cos_theta = math.cos(angle_radians)
    sin_theta = math.sin(angle_radians)
    rotation = np.array(
        [
            [cos_theta, -sin_theta],
            [sin_theta, cos_theta],
        ],
        dtype=float,
    )
    local_points = np.array(
        [
            (-crop_width * 0.5, -crop_height * 0.5),
            (crop_width * 0.5, -crop_height * 0.5),
            (crop_width * 0.5, crop_height * 0.5),
            (-crop_width * 0.5, crop_height * 0.5),
        ],
        dtype=float,
    )
    return (local_points @ rotation.T) + np.array([center_x, center_y], dtype=float)


def fit_rotated_crop_state_to_bounds(image_width, image_height, crop_state):
    image_width = float(max(0, image_width))
    image_height = float(max(0, image_height))
    if image_width <= 0 or image_height <= 0:
        return {
            "center_x": 0.0,
            "center_y": 0.0,
            "width": 1.0,
            "height": 1.0,
            "angle": 0.0,
        }

    state = {
        "center_x": float(crop_state["center_x"]),
        "center_y": float(crop_state["center_y"]),
        "width": max(1.0, min(float(crop_state["width"]), image_width)),
        "height": max(1.0, min(float(crop_state["height"]), image_height)),
        "angle": normalize_angle_degrees(crop_state["angle"]),
    }

    for _ in range(3):
        corners = rotated_crop_corners(state)
        min_x = float(np.min(corners[:, 0]))
        max_x = float(np.max(corners[:, 0]))
        min_y = float(np.min(corners[:, 1]))
        max_y = float(np.max(corners[:, 1]))
        span_width = max_x - min_x
        span_height = max_y - min_y

        if span_width > image_width or span_height > image_height:
            scale = min(
                image_width / max(span_width, 1e-9),
                image_height / max(span_height, 1e-9),
                1.0,
            )
            state["width"] = max(1.0, state["width"] * scale)
            state["height"] = max(1.0, state["height"] * scale)
            corners = rotated_crop_corners(state)
            min_x = float(np.min(corners[:, 0]))
            max_x = float(np.max(corners[:, 0]))
            min_y = float(np.min(corners[:, 1]))
            max_y = float(np.max(corners[:, 1]))

        shift_x = 0.0
        shift_y = 0.0
        if min_x < 0.0:
            shift_x = -min_x
        elif max_x > image_width:
            shift_x = image_width - max_x
        if min_y < 0.0:
            shift_y = -min_y
        elif max_y > image_height:
            shift_y = image_height - max_y

        state["center_x"] += shift_x
        state["center_y"] += shift_y

    return state


def normalize_rotated_crop_state(image_width, image_height, crop_state=None):
    image_width = float(max(0, image_width))
    image_height = float(max(0, image_height))
    if image_width <= 0 or image_height <= 0:
        return {
            "center_x": 0.0,
            "center_y": 0.0,
            "width": 1.0,
            "height": 1.0,
            "angle": 0.0,
        }

    crop_state = crop_state or {}
    default_state = {
        "center_x": image_width * 0.5,
        "center_y": image_height * 0.5,
        "width": image_width,
        "height": image_height,
        "angle": 0.0,
    }

    try:
        center_x = float(crop_state.get("center_x", default_state["center_x"]))
    except (AttributeError, TypeError, ValueError):
        center_x = default_state["center_x"]
    try:
        center_y = float(crop_state.get("center_y", default_state["center_y"]))
    except (AttributeError, TypeError, ValueError):
        center_y = default_state["center_y"]
    try:
        crop_width = float(crop_state.get("width", default_state["width"]))
    except (AttributeError, TypeError, ValueError):
        crop_width = default_state["width"]
    try:
        crop_height = float(crop_state.get("height", default_state["height"]))
    except (AttributeError, TypeError, ValueError):
        crop_height = default_state["height"]
    try:
        angle = float(crop_state.get("angle", default_state["angle"]))
    except (AttributeError, TypeError, ValueError):
        angle = default_state["angle"]

    return fit_rotated_crop_state_to_bounds(
        image_width,
        image_height,
        {
            "center_x": center_x,
            "center_y": center_y,
            "width": crop_width,
            "height": crop_height,
            "angle": angle,
        },
    )


def crop_state_is_identity(image_width, image_height, crop_state=None, tolerance=1e-6):
    state = normalize_rotated_crop_state(image_width, image_height, crop_state)
    return (
        abs(state["center_x"] - (float(image_width) * 0.5)) <= tolerance
        and abs(state["center_y"] - (float(image_height) * 0.5)) <= tolerance
        and abs(state["width"] - float(image_width)) <= tolerance
        and abs(state["height"] - float(image_height)) <= tolerance
        and abs(normalize_angle_degrees(state["angle"])) <= tolerance
    )


def build_rotated_crop_affine(image_width, image_height, crop_state=None):
    state = normalize_rotated_crop_state(image_width, image_height, crop_state)
    output_width = max(1, int(round(state["width"])))
    output_height = max(1, int(round(state["height"])))
    matrix = cv2.getRotationMatrix2D(
        (float(state["center_x"]), float(state["center_y"])),
        float(state["angle"]),
        1.0,
    )
    matrix[0, 2] += (output_width * 0.5) - float(state["center_x"])
    matrix[1, 2] += (output_height * 0.5) - float(state["center_y"])
    return state, matrix, (output_width, output_height)


def apply_affine_to_point(matrix, x_value, y_value):
    mapped = np.asarray(matrix, dtype=float) @ np.array([float(x_value), float(y_value), 1.0], dtype=float)
    return float(mapped[0]), float(mapped[1])


def invert_affine_matrix(matrix):
    return cv2.invertAffineTransform(np.asarray(matrix, dtype=float))


def normalize_rect_area_state(image_width, image_height, area_state=None, min_size=16.0):
    image_width = float(max(0, image_width))
    image_height = float(max(0, image_height))
    min_size = float(max(1.0, min_size))
    if image_width <= 0 or image_height <= 0:
        return {
            "x": 0.0,
            "y": 0.0,
            "width": min_size,
            "height": min_size,
        }

    area_state = area_state or {}
    default_width = max(min_size, image_width * 0.3)
    default_height = max(min_size, image_height * 0.3)
    try:
        x_value = float(area_state.get("x", (image_width - default_width) * 0.5))
    except (AttributeError, TypeError, ValueError):
        x_value = (image_width - default_width) * 0.5
    try:
        y_value = float(area_state.get("y", (image_height - default_height) * 0.5))
    except (AttributeError, TypeError, ValueError):
        y_value = (image_height - default_height) * 0.5
    try:
        width_value = float(area_state.get("width", default_width))
    except (AttributeError, TypeError, ValueError):
        width_value = default_width
    try:
        height_value = float(area_state.get("height", default_height))
    except (AttributeError, TypeError, ValueError):
        height_value = default_height

    width_value = min(max(width_value, min_size), image_width)
    height_value = min(max(height_value, min_size), image_height)
    x_value = min(max(x_value, 0.0), max(0.0, image_width - width_value))
    y_value = min(max(y_value, 0.0), max(0.0, image_height - height_value))
    return {
        "x": float(x_value),
        "y": float(y_value),
        "width": float(width_value),
        "height": float(height_value),
    }


def qimage_buffer_array(q_image, dtype=np.uint8):
    bits = q_image.bits()
    return np.frombuffer(bits, dtype=dtype, count=q_image.sizeInBytes())


def apply_exposure_to_uint8(image_array, exposure_stops):
    exposure_stops = float(exposure_stops)
    if abs(exposure_stops) < 1e-9:
        return image_array
    gain = exposure_gain(exposure_stops)
    if image_array.ndim == 3 and image_array.shape[2] == 4:
        adjusted = image_array.copy()
        adjusted_rgb = np.clip(adjusted[:, :, :3].astype(np.float32) * gain, 0, 255).astype(np.uint8)
        adjusted[:, :, :3] = adjusted_rgb
        return adjusted
    return np.clip(image_array.astype(np.float32) * gain, 0, 255).astype(np.uint8)


def apply_contrast_to_uint8(image_array, contrast_percent):
    contrast_percent = float(contrast_percent)
    if abs(contrast_percent) < 1e-9:
        return image_array
    gain = contrast_gain(contrast_percent)
    if image_array.ndim == 3 and image_array.shape[2] == 4:
        adjusted = image_array.copy()
        adjusted_rgb = ((adjusted[:, :, :3].astype(np.float32) - 127.5) * gain) + 127.5
        adjusted[:, :, :3] = np.clip(adjusted_rgb, 0, 255).astype(np.uint8)
        return adjusted
    adjusted = ((image_array.astype(np.float32) - 127.5) * gain) + 127.5
    return np.clip(adjusted, 0, 255).astype(np.uint8)


def _warp_border_value(image_array):
    if image_array.ndim == 3:
        return tuple([0] * image_array.shape[2])
    return 0


def apply_rotated_crop_to_uint8(image_array, crop_state=None):
    if image_array is None or image_array.size == 0:
        return image_array

    image_height, image_width = image_array.shape[:2]
    if crop_state_is_identity(image_width, image_height, crop_state):
        return image_array.copy()

    _state, matrix, output_size = build_rotated_crop_affine(image_width, image_height, crop_state)
    return cv2.warpAffine(
        image_array,
        matrix,
        output_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=_warp_border_value(image_array),
    )


def apply_image_adjustments_to_uint8(
    image_array,
    exposure_stops=0.0,
    contrast_percent=0.0,
    crop_state=None,
    apply_crop=True,
):
    adjusted = image_array.copy()
    if apply_crop:
        adjusted = apply_rotated_crop_to_uint8(adjusted, crop_state)
    if abs(float(exposure_stops)) >= 1e-9:
        adjusted = apply_exposure_to_uint8(adjusted, exposure_stops)
    if abs(float(contrast_percent)) >= 1e-9:
        adjusted = apply_contrast_to_uint8(adjusted, contrast_percent)
    return adjusted


def apply_image_adjustments_to_qimage(
    q_image,
    exposure_stops=0.0,
    contrast_percent=0.0,
    crop_state=None,
    apply_crop=True,
):
    if q_image is None or q_image.isNull():
        return QImage()

    converted = q_image.convertToFormat(QImage.Format_RGBA8888)
    width = converted.width()
    height = converted.height()
    bytes_per_line = converted.bytesPerLine()
    rgba_rows = qimage_buffer_array(converted).reshape((height, bytes_per_line))
    rgba = rgba_rows[:, : width * 4].reshape((height, width, 4)).copy()
    rgba = apply_image_adjustments_to_uint8(
        rgba,
        exposure_stops=exposure_stops,
        contrast_percent=contrast_percent,
        crop_state=crop_state,
        apply_crop=apply_crop,
    )
    output_height, output_width = rgba.shape[:2]
    processed = QImage(rgba.data, output_width, output_height, output_width * 4, QImage.Format_RGBA8888)
    return processed.copy()


def qimage_to_grayscale_array(q_image):
    if q_image is None or q_image.isNull():
        return np.empty((0, 0), dtype=np.uint8)

    converted = q_image.convertToFormat(QImage.Format_Grayscale8)
    width = converted.width()
    height = converted.height()
    bytes_per_line = converted.bytesPerLine()

    gray_rows = qimage_buffer_array(converted).reshape((height, bytes_per_line))
    return gray_rows[:, :width].copy()


IMAGE_EDIT_HISTOGRAM_BIN_COUNT = 64


def compute_histogram_bins(image_gray, bin_count=IMAGE_EDIT_HISTOGRAM_BIN_COUNT):
    if image_gray is None or image_gray.size == 0:
        return np.zeros(int(bin_count), dtype=float)

    flat_values = np.asarray(image_gray, dtype=np.uint8).ravel()
    histogram, _edges = np.histogram(
        flat_values,
        bins=int(bin_count),
        range=(0.0, 256.0),
    )
    return histogram.astype(float, copy=False)


class ImageHistogramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._histogram = np.zeros(IMAGE_EDIT_HISTOGRAM_BIN_COUNT, dtype=float)
        self._overlay_histogram = np.zeros(IMAGE_EDIT_HISTOGRAM_BIN_COUNT, dtype=float)
        self._scale_max = 0.0
        self._overlay_scale_max = 0.0
        self.setMinimumHeight(92)
        self.setMaximumHeight(92)

    def clear_histogram(self):
        self._histogram = np.zeros(IMAGE_EDIT_HISTOGRAM_BIN_COUNT, dtype=float)
        self._overlay_histogram = np.zeros(IMAGE_EDIT_HISTOGRAM_BIN_COUNT, dtype=float)
        self._scale_max = 0.0
        self._overlay_scale_max = 0.0
        self.update()

    def set_histogram(self, histogram, *, overlay_histogram=None, scale_max=None, overlay_scale_max=None):
        if histogram is None:
            self.clear_histogram()
            return
        self._histogram = np.asarray(histogram, dtype=float)
        if overlay_histogram is None:
            self._overlay_histogram = np.zeros_like(self._histogram)
        else:
            self._overlay_histogram = np.asarray(overlay_histogram, dtype=float)
        if scale_max is None:
            self._scale_max = max(float(np.max(self._histogram)) if self._histogram.size else 0.0, 1.0)
        else:
            self._scale_max = max(float(scale_max), 0.0)
        if overlay_scale_max is None:
            self._overlay_scale_max = self._scale_max
        else:
            self._overlay_scale_max = max(float(overlay_scale_max), 0.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, QColor(255, 255, 255, 230))
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRect(rect)

        histogram = self._histogram
        if histogram.size == 0 or float(np.max(histogram)) <= 0:
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(rect, Qt.AlignCenter, "No Histogram")
            return

        chart_rect = QRectF(rect.adjusted(6, 6, -6, -8))
        max_value = max(float(self._scale_max), 1.0)
        bar_width = chart_rect.width() / float(len(histogram))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(90, 90, 90))

        for index, value in enumerate(histogram):
            normalized = 0.0 if max_value <= 0 else max(float(value), 0.0) / max_value
            normalized = min(max(normalized, 0.0), 1.0)
            bar_height = chart_rect.height() * normalized
            if bar_height <= 0:
                continue
            x_pos = chart_rect.left() + (index * bar_width)
            y_pos = chart_rect.bottom() - bar_height
            painter.drawRect(QRectF(x_pos, y_pos, max(1.0, bar_width), bar_height))

        overlay_histogram = self._overlay_histogram
        if overlay_histogram.size != histogram.size or float(np.max(overlay_histogram)) <= 0:
            return

        painter.setBrush(QColor(220, 70, 70, 110))
        overlay_max_value = max(float(self._overlay_scale_max), 1.0)
        for index, value in enumerate(overlay_histogram):
            normalized = 0.0 if overlay_max_value <= 0 else max(float(value), 0.0) / overlay_max_value
            normalized = min(max(normalized, 0.0), 1.0)
            bar_height = chart_rect.height() * normalized
            if bar_height <= 0:
                continue
            x_pos = chart_rect.left() + (index * bar_width)
            y_pos = chart_rect.bottom() - bar_height
            painter.drawRect(QRectF(x_pos, y_pos, max(1.0, bar_width), bar_height))


class ImageRectOverlayItem(QGraphicsObject):
    areaChanged = Signal(dict)
    areaChangeFinished = Signal(dict)

    HANDLE_RADIUS = 6.0
    MIN_SIZE = 16.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_rect = QRectF(0.0, 0.0, 0.0, 0.0)
        self._rect = QRectF(0.0, 0.0, self.MIN_SIZE, self.MIN_SIZE)
        self._drag_mode = None
        self._drag_corner = None
        self._press_pos = QPointF()
        self._start_rect = QRectF(self._rect)
        self._interactive = True
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setZValue(9990)

    def set_interactive(self, interactive):
        self._interactive = bool(interactive)
        self.setAcceptedMouseButtons(Qt.LeftButton if self._interactive else Qt.NoButton)
        self.setAcceptHoverEvents(self._interactive)
        self.update()

    def sync_from_rect(self, image_rect, rect_state):
        self.prepareGeometryChange()
        self.setPos(image_rect.topLeft())
        self._image_rect = QRectF(0.0, 0.0, image_rect.width(), image_rect.height())
        normalized = normalize_rect_area_state(
            self._image_rect.width(),
            self._image_rect.height(),
            rect_state,
            min_size=self.MIN_SIZE,
        )
        self._rect = QRectF(
            float(normalized["x"]),
            float(normalized["y"]),
            float(normalized["width"]),
            float(normalized["height"]),
        )
        self.update()

    def area_state(self):
        return {
            "x": float(self._rect.left()),
            "y": float(self._rect.top()),
            "width": float(self._rect.width()),
            "height": float(self._rect.height()),
        }

    def boundingRect(self):
        margin = self.HANDLE_RADIUS + 8.0
        return QRectF(self._image_rect).adjusted(-margin, -margin, margin, margin)

    def _handle_points(self):
        return {
            "top_left": self._rect.topLeft(),
            "top_right": self._rect.topRight(),
            "bottom_right": self._rect.bottomRight(),
            "bottom_left": self._rect.bottomLeft(),
        }

    def _corner_at_pos(self, pos):
        for corner_name, point in self._handle_points().items():
            if QLineF(pos, point).length() <= self.HANDLE_RADIUS + 2.0:
                return corner_name
        return None

    def mousePressEvent(self, event):
        if not self._interactive or event.button() != Qt.LeftButton:
            event.ignore()
            return
        pos = event.pos()
        corner_name = self._corner_at_pos(pos)
        if corner_name is not None:
            self._drag_mode = "resize"
            self._drag_corner = corner_name
        elif self._rect.contains(pos):
            self._drag_mode = "move"
            self._drag_corner = None
        else:
            self._drag_mode = None
            self._drag_corner = None
            event.ignore()
            return
        self._press_pos = QPointF(pos)
        self._start_rect = QRectF(self._rect)
        event.accept()

    def mouseMoveEvent(self, event):
        if not self._interactive or self._drag_mode is None:
            event.ignore()
            return

        delta = event.pos() - self._press_pos
        rect = QRectF(self._start_rect)
        if self._drag_mode == "move":
            rect.translate(delta)
            if rect.left() < self._image_rect.left():
                rect.moveLeft(self._image_rect.left())
            if rect.top() < self._image_rect.top():
                rect.moveTop(self._image_rect.top())
            if rect.right() > self._image_rect.right():
                rect.moveRight(self._image_rect.right())
            if rect.bottom() > self._image_rect.bottom():
                rect.moveBottom(self._image_rect.bottom())
        elif self._drag_mode == "resize":
            if self._drag_corner == "top_left":
                rect.setTopLeft(rect.topLeft() + delta)
            elif self._drag_corner == "top_right":
                rect.setTopRight(rect.topRight() + delta)
            elif self._drag_corner == "bottom_right":
                rect.setBottomRight(rect.bottomRight() + delta)
            elif self._drag_corner == "bottom_left":
                rect.setBottomLeft(rect.bottomLeft() + delta)
            rect = rect.normalized()
            rect.setWidth(max(rect.width(), self.MIN_SIZE))
            rect.setHeight(max(rect.height(), self.MIN_SIZE))
            if rect.right() > self._image_rect.right():
                rect.moveRight(self._image_rect.right())
            if rect.bottom() > self._image_rect.bottom():
                rect.moveBottom(self._image_rect.bottom())
            if rect.left() < self._image_rect.left():
                rect.moveLeft(self._image_rect.left())
            if rect.top() < self._image_rect.top():
                rect.moveTop(self._image_rect.top())
            rect.setWidth(min(rect.width(), self._image_rect.width()))
            rect.setHeight(min(rect.height(), self._image_rect.height()))

        normalized = normalize_rect_area_state(
            self._image_rect.width(),
            self._image_rect.height(),
            {
                "x": rect.left(),
                "y": rect.top(),
                "width": rect.width(),
                "height": rect.height(),
            },
            min_size=self.MIN_SIZE,
        )
        self._rect = QRectF(
            float(normalized["x"]),
            float(normalized["y"]),
            float(normalized["width"]),
            float(normalized["height"]),
        )
        self.areaChanged.emit(self.area_state())
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_mode is None:
            event.ignore()
            return
        self._drag_mode = None
        self._drag_corner = None
        self.areaChangeFinished.emit(self.area_state())
        event.accept()

    def paint(self, painter, option, widget=None):
        painter.save()
        outer_fill = QColor(0, 180, 120, 18 if self._interactive else 10)
        outline_color = QColor(0, 160, 110, 220 if self._interactive else 140)
        painter.setBrush(QBrush(outer_fill))
        painter.setPen(QPen(outline_color, 1.5, Qt.DashLine))
        painter.drawRect(self._rect)

        if self._interactive:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 160, 110, 235))
            handle_diameter = self.HANDLE_RADIUS * 2.0
            for point in self._handle_points().values():
                painter.drawEllipse(
                    QRectF(
                        point.x() - self.HANDLE_RADIUS,
                        point.y() - self.HANDLE_RADIUS,
                        handle_diameter,
                        handle_diameter,
                    )
                )
        painter.restore()


class ImageCropOverlayItem(QGraphicsObject):
    cropChanged = Signal(dict)
    cropChangeFinished = Signal(dict)

    HANDLE_RADIUS = 6.0
    EDGE_HIT_WIDTH = 12.0
    ROTATE_HANDLE_RADIUS = 7.0
    ROTATE_HANDLE_DISTANCE = 28.0
    MIN_SIZE = 16.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_rect = QRectF(0.0, 0.0, 0.0, 0.0)
        self._crop_state = {
            "center_x": 0.0,
            "center_y": 0.0,
            "width": 1.0,
            "height": 1.0,
            "angle": 0.0,
        }
        self._drag_mode = None
        self._drag_corner_index = None
        self._press_pos = QPointF()
        self._start_state = dict(self._crop_state)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setZValue(10000)

    def sync_from_state(self, image_rect, crop_state):
        self.prepareGeometryChange()
        self.setPos(image_rect.topLeft())
        self._image_rect = QRectF(0.0, 0.0, image_rect.width(), image_rect.height())
        self._crop_state = dict(crop_state)
        self.update()

    def boundingRect(self):
        margin = self.ROTATE_HANDLE_DISTANCE + self.ROTATE_HANDLE_RADIUS + 8.0
        return QRectF(self._image_rect).adjusted(-margin, -margin, margin, margin)

    def _crop_polygon(self):
        return QPolygonF([QPointF(float(x), float(y)) for x, y in rotated_crop_corners(self._crop_state)])

    def _corner_points_for_state(self, state):
        return [QPointF(float(x), float(y)) for x, y in rotated_crop_corners(state)]

    def _basis_vectors(self):
        angle_radians = math.radians(float(self._crop_state["angle"]))
        cos_theta = math.cos(angle_radians)
        sin_theta = math.sin(angle_radians)
        return QPointF(cos_theta, sin_theta), QPointF(-sin_theta, cos_theta)

    def _corner_points(self):
        return self._corner_points_for_state(self._crop_state)

    def _edge_midpoints_for_state(self, state):
        corners = self._corner_points_for_state(state)
        return [
            QPointF((corners[0].x() + corners[1].x()) * 0.5, (corners[0].y() + corners[1].y()) * 0.5),
            QPointF((corners[1].x() + corners[2].x()) * 0.5, (corners[1].y() + corners[2].y()) * 0.5),
            QPointF((corners[2].x() + corners[3].x()) * 0.5, (corners[2].y() + corners[3].y()) * 0.5),
            QPointF((corners[3].x() + corners[0].x()) * 0.5, (corners[3].y() + corners[0].y()) * 0.5),
        ]

    def _edge_segments_for_state(self, state):
        corners = self._corner_points_for_state(state)
        return [
            (corners[0], corners[1]),
            (corners[1], corners[2]),
            (corners[2], corners[3]),
            (corners[3], corners[0]),
        ]

    def _point_to_segment_distance(self, point, segment_start, segment_end):
        start = np.array([segment_start.x(), segment_start.y()], dtype=float)
        end = np.array([segment_end.x(), segment_end.y()], dtype=float)
        p = np.array([point.x(), point.y()], dtype=float)
        segment = end - start
        length_sq = float(np.dot(segment, segment))
        if length_sq <= 1e-9:
            return float(np.linalg.norm(p - start))
        t = float(np.dot(p - start, segment) / length_sq)
        t = max(0.0, min(1.0, t))
        projection = start + (t * segment)
        return float(np.linalg.norm(p - projection))

    def _rotation_handle_point(self):
        center = QPointF(float(self._crop_state["center_x"]), float(self._crop_state["center_y"]))
        _u_axis, v_axis = self._basis_vectors()
        top_center = center - (v_axis * (float(self._crop_state["height"]) * 0.5))
        return top_center - (v_axis * self.ROTATE_HANDLE_DISTANCE)

    def _interaction_for_pos(self, local_pos):
        rotation_handle = self._rotation_handle_point()
        if QLineF(local_pos, rotation_handle).length() <= (self.ROTATE_HANDLE_RADIUS + 3.0):
            return ("rotate", None)
        for index, (start, end) in enumerate(self._edge_segments_for_state(self._crop_state)):
            if self._point_to_segment_distance(local_pos, start, end) <= self.EDGE_HIT_WIDTH:
                return ("edge", index)
        if self._crop_polygon().containsPoint(local_pos, Qt.OddEvenFill):
            return ("move", None)
        return (None, None)

    def _set_cursor_for_interaction(self, interaction):
        mode, handle_index = interaction
        if mode == "rotate":
            self.setCursor(Qt.CrossCursor)
        elif mode == "edge":
            if handle_index in (1, 3):
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.setCursor(Qt.SizeVerCursor)
        elif mode == "move":
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.unsetCursor()

    def hoverMoveEvent(self, event):
        self._set_cursor_for_interaction(self._interaction_for_pos(event.pos()))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            event.ignore()
            return
        interaction = self._interaction_for_pos(event.pos())
        mode, corner_index = interaction
        if mode is None:
            event.ignore()
            return
        self._drag_mode = mode
        self._drag_corner_index = corner_index
        self._press_pos = QPointF(event.pos())
        self._start_state = dict(self._crop_state)
        if mode == "move":
            self.setCursor(Qt.ClosedHandCursor)
        else:
            self._set_cursor_for_interaction(interaction)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_mode is None:
            event.ignore()
            return

        local_pos = QPointF(event.pos())
        image_width = float(self._image_rect.width())
        image_height = float(self._image_rect.height())
        new_state = dict(self._start_state)

        if self._drag_mode == "move":
            delta = local_pos - self._press_pos
            new_state["center_x"] = float(self._start_state["center_x"]) + float(delta.x())
            new_state["center_y"] = float(self._start_state["center_y"]) + float(delta.y())
        elif self._drag_mode == "rotate":
            center = QPointF(float(self._start_state["center_x"]), float(self._start_state["center_y"]))
            start_angle = math.degrees(math.atan2(self._press_pos.y() - center.y(), self._press_pos.x() - center.x()))
            current_angle = math.degrees(math.atan2(local_pos.y() - center.y(), local_pos.x() - center.x()))
            new_state["angle"] = normalize_angle_degrees(float(self._start_state["angle"]) + (current_angle - start_angle))
        elif self._drag_mode == "edge":
            angle_radians = math.radians(float(self._start_state["angle"]))
            u_axis = np.array([math.cos(angle_radians), math.sin(angle_radians)], dtype=float)
            v_axis = np.array([-math.sin(angle_radians), math.cos(angle_radians)], dtype=float)
            edge_midpoints = self._edge_midpoints_for_state(self._start_state)
            if self._drag_corner_index in (1, 3):
                sign_u = 1.0 if self._drag_corner_index == 1 else -1.0
                opposite_point = edge_midpoints[(self._drag_corner_index + 2) % 4]
                vector = np.array([local_pos.x() - opposite_point.x(), local_pos.y() - opposite_point.y()], dtype=float)
                projected_u = float(np.dot(vector, u_axis))
                projected_u = sign_u * max(self.MIN_SIZE, sign_u * projected_u)
                adjusted_edge_center = np.array(
                    [
                        opposite_point.x() + (projected_u * u_axis[0]),
                        opposite_point.y() + (projected_u * u_axis[1]),
                    ],
                    dtype=float,
                )
                new_state["center_x"] = float((opposite_point.x() + adjusted_edge_center[0]) * 0.5)
                new_state["center_y"] = float((opposite_point.y() + adjusted_edge_center[1]) * 0.5)
                new_state["width"] = abs(projected_u)
                new_state["height"] = float(self._start_state["height"])
            else:
                sign_v = 1.0 if self._drag_corner_index == 2 else -1.0
                opposite_point = edge_midpoints[(self._drag_corner_index + 2) % 4]
                vector = np.array([local_pos.x() - opposite_point.x(), local_pos.y() - opposite_point.y()], dtype=float)
                projected_v = float(np.dot(vector, v_axis))
                projected_v = sign_v * max(self.MIN_SIZE, sign_v * projected_v)
                adjusted_edge_center = np.array(
                    [
                        opposite_point.x() + (projected_v * v_axis[0]),
                        opposite_point.y() + (projected_v * v_axis[1]),
                    ],
                    dtype=float,
                )
                new_state["center_x"] = float((opposite_point.x() + adjusted_edge_center[0]) * 0.5)
                new_state["center_y"] = float((opposite_point.y() + adjusted_edge_center[1]) * 0.5)
                new_state["width"] = float(self._start_state["width"])
                new_state["height"] = abs(projected_v)
        new_state = fit_rotated_crop_state_to_bounds(image_width, image_height, new_state)
        self._crop_state = dict(new_state)
        self.update()
        self.cropChanged.emit(dict(new_state))
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_mode is not None:
            self.cropChangeFinished.emit(dict(self._crop_state))
        self._drag_mode = None
        self._drag_corner_index = None
        self.unsetCursor()
        event.accept()

    def paint(self, painter, option, widget):
        if self._image_rect.width() <= 0 or self._image_rect.height() <= 0:
            return

        painter.setRenderHint(QPainter.Antialiasing, True)
        crop_polygon = self._crop_polygon()

        outside_path = QPainterPath()
        outside_path.addRect(self.boundingRect())
        crop_path = QPainterPath()
        crop_path.addPolygon(crop_polygon)
        outside_path = outside_path.subtracted(crop_path)
        painter.fillPath(outside_path, QColor(0, 0, 0, 96))

        line_pen = QPen(QColor(255, 255, 255, 230), 1.5)
        painter.setPen(line_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPolygon(crop_polygon)

        painter.setPen(QPen(QColor(255, 255, 255, 180), 1.0, Qt.DashLine))
        rotation_handle = self._rotation_handle_point()
        top_center = QPointF(
            (crop_polygon[0].x() + crop_polygon[1].x()) * 0.5,
            (crop_polygon[0].y() + crop_polygon[1].y()) * 0.5,
        )
        painter.drawLine(top_center, rotation_handle)

        painter.setPen(QPen(QColor(255, 255, 255, 230), 1.0))
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        for point in self._edge_midpoints_for_state(self._crop_state):
            painter.drawEllipse(point, self.HANDLE_RADIUS - 1.5, self.HANDLE_RADIUS - 1.5)
        painter.drawEllipse(rotation_handle, self.ROTATE_HANDLE_RADIUS, self.ROTATE_HANDLE_RADIUS)
