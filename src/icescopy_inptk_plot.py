"""Display limits for INP plots; calculations remain in the external toolkit."""
import math
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QWidget, QToolTip, QGraphicsView, QFrame


def curve_intersects_rect(x, y, rect):
    """Include both points and line segments, even when no point is in the box."""
    x, y = np.asarray(x), np.asarray(y)
    valid = np.isfinite(x) & np.isfinite(y)
    left, right, bottom, top = rect.left(), rect.right(), rect.top(), rect.bottom()
    if np.any(valid & (x >= left) & (x <= right) & (y >= bottom) & (y <= top)):
        return True
    pairs = valid[:-1] & valid[1:]
    if not pairs.any(): return False
    x0, y0 = x[:-1][pairs], y[:-1][pairs]
    dx, dy = x[1:][pairs] - x0, y[1:][pairs] - y0
    # Clip each segment against the four rectangle edges (Liang–Barsky).
    start, end = np.zeros(len(x0)), np.ones(len(x0))
    possible = np.ones(len(x0), dtype=bool)
    for direction, distance in ((-dx, x0-left), (dx, right-x0),
                                (-dy, y0-bottom), (dy, top-y0)):
        parallel = direction == 0
        possible &= ~(parallel & (distance < 0))
        ratio = np.divide(distance, direction, out=np.zeros_like(distance, dtype=float), where=~parallel)
        start = np.maximum(start, np.where(direction < 0, ratio, 0))
        end = np.minimum(end, np.where(direction > 0, ratio, 1))
    return bool(np.any(possible & (start <= end)))


class _FixedLegend(pg.LegendItem):
    def mouseDragEvent(self, event):
        event.ignore()


class PlotLegend(QGraphicsView):
    """Place a small legend in clear plot space, or in a compact footer.

    The separate scene allows the same legend to move between an overlay and
    a layout without changing plotted data, pan/zoom or the legend entries.
    """

    def __init__(self, plot, footer, text_size):
        self.legend = _FixedLegend(frame=False, labelTextSize=text_size, verSpacing=2)
        scene = pg.GraphicsScene()
        scene.addItem(self.legend)
        super().__init__(scene, plot.viewport())
        scene.setParent(self)
        self.plot, self.footer = plot, footer
        self.in_footer = False
        self.setFrameShape(QFrame.NoFrame)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setAccessibleName("Plot legend")
        self.setStyleSheet("QGraphicsView { border: 1px solid palette(midlight); border-radius: 4px; }")
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.place)
        self.retry_overlay = False
        plot.getViewBox().sigRangeChanged.connect(lambda *_: self.schedule(True))
        plot.getViewBox().sigResized.connect(lambda *_: self.schedule(False))

    def schedule(self, retry_overlay):
        self.retry_overlay |= retry_overlay
        # While a pan or zoom is in progress, an old overlay position may
        # cross the moved curves. Show it again only after finding clear space.
        if retry_overlay and not self.in_footer: self.hide()
        self.timer.start()

    def size_legend(self, columns=1):
        self.legend.setColumnCount(columns)
        for _sample, label in self.legend.items:
            label.item.setTextWidth(min(170, label.item.boundingRect().width()))
            label.updateMin()
            label.setToolTip(label.text)
        self.legend.layout.activate()
        self.legend.updateSize()
        rect = self.legend.boundingRect()
        self.setSceneRect(rect.adjusted(-2, -2, 2, 2))
        return math.ceil(rect.width()) + 12, math.ceil(rect.height()) + 12

    def clear_position(self, pixel_rect):
        view = self.plot.getViewBox()
        scene_rect = QRectF(self.plot.mapToScene(pixel_rect.toRect()).boundingRect())
        # Leave extra clearance for line thickness and point symbols.
        data_rect = view.mapSceneToView(scene_rect.topLeft())
        opposite = view.mapSceneToView(scene_rect.bottomRight())
        data_rect = QRectF(data_rect, opposite).normalized()
        for item in self.plot.listDataItems():
            x, y = item.getData()  # Includes the actual log display transform.
            if x is not None and curve_intersects_rect(x, y, data_rect): return False
        for item in self.plot.getPlotItem().items:
            if isinstance(item, pg.FillBetweenItem) and item.path().intersects(data_rect): return False
        return True

    def place(self):
        retry, self.retry_overlay = self.retry_overlay, False
        if not self.legend.items:
            self.hide(); self.footer.hide(); return
        self.setBackgroundBrush(self.plot.backgroundBrush())
        width, height = self.size_legend()
        area = QRectF(self.plot.mapFromScene(self.plot.getViewBox().sceneBoundingRect()).boundingRect())
        area.adjust(10, 10, -10, -10)
        position = None
        if (retry or not self.in_footer) and width <= area.width() and height <= area.height():
            clearance = 6.
            for item in self.plot.listDataItems():
                pen = item.opts.get('pen')
                stroke = pg.mkPen(pen).widthF() / 2 if pen is not None else 0
                marker = float(item.opts.get('symbolSize', 0)) / 2 if item.opts.get('symbol') else 0
                clearance = max(clearance, stroke + 3, marker + 3)
            # Prefer the upper-right corner; try other corners and then the
            # interior. Never settle for a position crossing a displayed curve.
            fractions = [(1, 0), (0, 0), (1, 1), (0, 1)]
            fractions += [(x, y) for y in (.25, .5, .75) for x in (1, .75, .5, .25, 0)]
            for fx, fy in fractions:
                candidate = QRectF(area.left()+fx*(area.width()-width),
                                   area.top()+fy*(area.height()-height), width, height)
                if self.clear_position(candidate.adjusted(-clearance, -clearance, clearance, clearance)):
                    position = candidate.topLeft(); break
        if position is not None:
            self.footer.layout().removeWidget(self)
            self.setParent(self.plot.viewport())
            self.footer.hide()
            self.in_footer = False
            self.setFixedSize(width, height)
            self.move(position.toPoint())
        else:
            available = max(1, self.plot.width()-20)
            columns = max(1, min(3, available // max(1, width)))
            width, height = self.size_legend(columns)
            self.setParent(self.footer)
            if self.footer.layout().indexOf(self) < 0: self.footer.layout().addWidget(self)
            self.in_footer = True
            self.setFixedSize(min(width, available), min(height, 110))
            self.footer.show()
        self.show()


class TemperatureTags(QWidget):
    """One compact lane of pixel-sized drag targets for the active sample.

    Temperatures map through the actual ViewBox, so tags follow pan, zoom and
    axis-width changes without moving data or consuming concentration-axis space.
    """
    activated = Signal(str)
    moved = Signal(str, int, float, bool)
    row_height = 30

    def __init__(self, plot, parent=None):
        super().__init__(parent)
        self.plot = plot
        self.entries = []
        self.targets = []
        self.drag = None
        self.setMouseTracking(True)
        self.setAccessibleName("Sample temperature limits. Drag a colored tag or edit the limits table.")
        plot.getViewBox().sigRangeChanged.connect(self.update)
        plot.getViewBox().sigResized.connect(self.update)

    def set_entries(self, entries):
        self.entries = [entry for entry in entries if entry[3]]
        self.setFixedHeight(self.row_height + 4 if entries else 0)
        self.setVisible(bool(entries))
        self.update()

    def plot_x(self, temperature):
        view = self.plot.getViewBox()
        point = self.plot.mapFromScene(view.mapViewToScene(QPointF(temperature, 0)))
        return self.mapFromGlobal(self.plot.mapToGlobal(point)).x()

    def temperature_at(self, x):
        point = self.plot.mapFromGlobal(self.mapToGlobal(QPoint(round(x), 0)))
        return self.plot.getViewBox().mapSceneToView(self.plot.mapToScene(point)).x()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.targets = []
        left, right = self.plot.getViewBox().viewRange()[0]
        xmin, xmax = self.plot_x(left), self.plot_x(right)
        for row, (key, limits, color, active) in enumerate(self.entries):
            top = row * self.row_height + 2
            font = self.font(); font.setPointSizeF(max(9, font.pointSizeF() - 1))
            painter.setFont(font)
            painter.setPen(self.palette().color(QPalette.Text))
            label = painter.fontMetrics().elidedText(key, Qt.ElideRight, max(0, xmin - 9))
            painter.drawText(QRectF(0, top + 5, max(0, xmin - 7), 23), Qt.AlignRight | Qt.AlignVCenter, label)
            positions = [max(xmin, min(xmax, self.plot_x(value))) for value in limits]
            for boundary, (value, x) in enumerate(zip(limits, positions)):
                text = f"{value:g}" if abs(value) >= 100 else f"{value:.1f}"
                width = max(48, painter.fontMetrics().horizontalAdvance(text) + 18)
                center = x
                # Separate handles when both temperatures occupy the same few pixels.
                if abs(positions[1] - positions[0]) < width + 4:
                    center += (-1 if boundary == 0 else 1) * (width / 2 + 3)
                center = max(width / 2 + 1, min(self.width() - width / 2 - 1, center))
                rect = QRectF(center - width / 2, top + 7, width, 21)
                shape = QPainterPath(); shape.addRoundedRect(rect, 6, 6)
                tip = QPainterPath(); tip.moveTo(x, top)
                tip.lineTo(center - 7, top + 9); tip.lineTo(center + 7, top + 9); tip.closeSubpath()
                shape = shape.united(tip)
                fill = QColor(color); fill.setAlpha(215 if active else 145)
                painter.setPen(QPen(color, 1.5 if active else 1))
                painter.setBrush(fill); painter.drawPath(shape)
                painter.setPen(Qt.black if color.lightnessF() > .45 else Qt.white)
                painter.drawText(rect, Qt.AlignCenter, text)
                self.targets.append((shape, key, boundary, value))

    def target_at(self, position):
        return next((target for target in reversed(self.targets) if target[0].contains(position)), None)

    def mousePressEvent(self, event):
        target = self.target_at(event.position())
        if event.button() != Qt.LeftButton or target is None:
            event.ignore(); return
        _, key, boundary, value = target
        self.drag = (key, boundary, value, self.temperature_at(event.position().x()))
        self.activated.emit(key)
        self.setCursor(Qt.SizeHorCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag:
            key, boundary, value, start = self.drag
            self.moved.emit(key, boundary, value + self.temperature_at(event.position().x()) - start, False)
        else:
            target = self.target_at(event.position())
            self.setCursor(Qt.SizeHorCursor if target else Qt.ArrowCursor)
            if target:
                _, key, boundary, value = target
                QToolTip.showText(event.globalPosition().toPoint(),
                    f"{key}: {'cold' if boundary == 0 else 'warm'} limit {value:g} °C", self)
            else:
                row = int(event.position().y() // self.row_height)
                if 0 <= row < len(self.entries):
                    QToolTip.showText(event.globalPosition().toPoint(), self.entries[row][0], self)

    def mouseReleaseEvent(self, event):
        if self.drag and event.button() == Qt.LeftButton:
            key, boundary, value, start = self.drag
            self.drag = None
            self.moved.emit(key, boundary, value + self.temperature_at(event.position().x()) - start, True)
            event.accept()
        else:
            event.ignore()


class ConcentrationAxis(pg.AxisItem):
    """Use readable decade ticks; add 2 and 5 only when there is room."""

    def logTickValues(self, minVal, maxVal, size, stdTicks):
        span = maxVal - minVal
        if span < .5:
            return super().logTickValues(minVal, maxVal, size, stdTicks)
        step = max(1, math.ceil(span / max(1, size / 70)))
        major = list(range(math.ceil(minVal / step) * step, math.floor(maxVal) + 1, step))
        minor = []
        if step == 1 and size / span >= 110:
            minor = [power + math.log10(m) for power in range(math.floor(minVal), math.ceil(maxVal))
                     for m in (2, 5) if minVal < power + math.log10(m) < maxVal]
        return [(float(step), major), (None, minor)]


class TemperatureRangeItem(pg.LinearRegionItem):
    """Boundary handles only: the transparent interior must allow plot panning."""

    def mouseDragEvent(self, event):
        event.ignore()

    def mouseClickEvent(self, event):
        event.ignore()

    def hoverEvent(self, event):
        pass


def axis_limits(quantity, x_values, y_values, totals=(), *, logarithmic=False):
    """Return padded plot coordinates, including finite uncertainty endpoints.

    Log coordinates belong to the view only: observations and exports stay in
    their original units. No arbitrary epsilon is substituted for zero data.
    """
    xs = [v for v in x_values if math.isfinite(v)]
    ys = [v for v in y_values if math.isfinite(v)]
    # Fit axes shows the freezing region through 0 °C. Warmer observations
    # remain plotted and are still accessible by panning or zooming out.
    xmin = min((v for v in xs if v < 0), default=-30.)
    pad = max(abs(xmin) * .04, .1)
    xlim = (xmin - pad, 0.)
    if logarithmic:
        positive = [math.log10(v) for v in ys if v > 0]
        if not positive:
            return xlim, (-1., 1.)
        low, high = min(positive), max(positive)
        pad = max((high - low) * .06, .15)
        return xlim, (low - pad, high + pad)
    if quantity == "Fraction frozen":
        return xlim, (-.03, 1.03)
    if quantity == "Number frozen":
        ys += [v for v in totals if math.isfinite(v)]
    maximum = max([v for v in ys if v >= 0], default=1.)
    if maximum == 0:
        maximum = 1.
    # A small margin keeps zero and fully frozen endpoint symbols visible.
    return xlim, (-.03 * maximum, 1.07 * maximum)
