
from PySide6.QtWidgets import QSlider, QStyle, QStyleOptionSlider
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QPolygonF, QPainterPath
from PySide6.QtCore import Qt, Signal, QPoint, QPointF, QTimer

class FrameSlider(QSlider):
    keyframeClicked = Signal(bool)  # Signal emitted when a keyframe indicator is clicked
    flagframeClicked = Signal(bool)

    def __init__(self, orientation=Qt.Horizontal, main_window=None, parent=None):
        super(FrameSlider, self).__init__(orientation, parent)
        self.keyframes = set()  # List to store positions of keyframes
        self.flaggedframes = set()
        
        self.main_window = main_window
        self.setSingleStep(1)
        self.setMinimum(0)
        self.setMaximum(1)  # Will be updated when images are loaded
        self.setEnabled(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.custom_ticks = [0] # set when loading images
        self.left_ratio = None
        self.raise_()
        self.value_has_changed = False

        self.valueChanged.connect(self.handle_value_change)
        self.sliderReleased.connect(self.handle_slider_release)

    def set_custom_ticks(self):
        original_range = len(self.main_window.imagePaths)
        slider_width = max(1, self.width())
        tick_interval = int(self.main_window.slider_tick_pixel_interval * original_range / slider_width)
        if tick_interval == 0:
            tick_interval = 1
        self.custom_ticks = range(0, original_range, tick_interval)
        self.update()

    def set_left_ratio(self):
        denominator = self.maximum() - self.minimum()
        if denominator <= 0:
            self.left_ratio = 0.0
        else:
            self.left_ratio = (self.value() - self.minimum()) / denominator

    def update_zoomed_level(self, zoom_value):
        """Updates the zoom level of the slider based on zoom_value."""
        original_range = len(self.main_window.imagePaths)
        if original_range <= 0:
            self.setRange(0, 0)
            self.left_ratio = 0.0
            self.update()
            return

        zoom_value = max(1, int(zoom_value))
        center_position = int(self.value())  # Get current handle position
        new_slider_range = max(0, int(round(original_range / zoom_value - 1)))

        if self.left_ratio is not None:
            left_ratio = float(self.left_ratio)
        else:
            left_ratio = self.value() / max(1, original_range - 1)
        left_ratio = max(0.0, min(1.0, left_ratio))

        left_length = int(round(new_slider_range * left_ratio))
        min_value = center_position - left_length
        max_value = min_value + new_slider_range

        if min_value <= 0:
            min_value = 0
            max_value = new_slider_range
        elif max_value >= (original_range - 1):
            max_value = original_range - 1
            min_value = max_value - new_slider_range

        min_value = max(0, int(min_value))
        max_value = min(original_range - 1, int(max_value))
        if max_value < min_value:
            max_value = min_value

        self.setRange(min_value, max_value)
        self.left_ratio = left_ratio # so that the slider hodler can stay at one place roughly
        self.update()

    def toggle_keyframe(self):
        """Toggle a keyframe at the given position."""
        if self.isEnabled():
            before_state = self.main_window.capture_cell_state()
            position = self.main_window.image_index
            if position in self.keyframes:
                self.keyframes.remove(position)
                self.main_window.update_toggle_keyframe_button_icon()
                self.update()  # Trigger repaint
                self.keyframeClicked.emit(False)  # False for remove
                
            else:
                self.keyframes.add(position)
                self.main_window.update_toggle_keyframe_button_icon()
                self.update()  # Trigger repaint
                self.keyframeClicked.emit(True)  # True for add
        
            self.main_window.push_cell_history("Toggle Keyframe", before_state)
            

    def toggle_flagging(self):
        """Toggle a keyframe at the given position."""
        if self.isEnabled():
            before_state = self.main_window.capture_cell_state()
            position = self.main_window.image_index
            if position in self.flaggedframes:
                self.flaggedframes.remove(position)
                self.main_window.update_toggle_flagging_button_icon()
                self.update()  # Trigger repaint
                self.flagframeClicked.emit(False)
                
            else:
                self.flaggedframes.add(position)
                self.main_window.update_toggle_flagging_button_icon()
                self.update()  # Trigger repaint
                self.flagframeClicked.emit(True)
        
            self.main_window.push_cell_history("Toggle Flagged Frame", before_state)


    def paintEvent(self, event):
        """Override the paintEvent to draw keyframe indicators, flag indicators, and tickmarks."""

        super(FrameSlider, self).paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        visible_min = int(self.minimum())
        visible_max = int(self.maximum())

        # keyframe indicator
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(10, 132, 255, 255)))
        for keyframe in self.keyframes:
            if keyframe < visible_min or keyframe > visible_max:
                continue
            x = self.sliderPositionToX(keyframe)
            y = self.height() - 5.5  # Positioning it 5 pixels above the bottom edge

            # Define the points for the diamond shape
            pointsF = [QPointF(x * 1.0, y - 5.0), QPointF(x * 1.0 + 5.0, y), QPointF(x * 1.0, y + 5.0), QPointF(x - 5.0, y * 1.0)]

            polygonF = QPolygonF(pointsF)
            
            # Convert QPolygonF to a list of QPointF
            points_list = [polygonF.at(i) for i in range(polygonF.count())]

            # Draw using QPainterPath
            path = QPainterPath()
            path.moveTo(points_list[0])
            for point in points_list[1:]:
                path.lineTo(point)
            path.lineTo(points_list[0])  # close the shape
            painter.drawPath(path)

        # Flag indicator
        pen = QPen(QColor(255, 69, 58, 255))
        pen.setWidth(1)
        brush = QBrush(QColor(255, 69, 58, 255))
        painter.setPen(pen)
        painter.setBrush(brush)

        for a_flag in self.flaggedframes:
            if a_flag < visible_min or a_flag > visible_max:
                continue
            x = self.sliderPositionToX(a_flag) * 1.0
            y = self.height() - 5.5  # You can adjust this
            radius = 2.5  # Radius of circle
            painter.drawEllipse(QPointF(x, y), radius, radius)

        # Tick Mark
        pen = QPen(QColor(178, 178, 178, 178))
        brush = QBrush(QColor(178, 178, 178, 178))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(brush)

        # Draw tick marks
        for i in self.custom_ticks:
            if i < visible_min or i > visible_max:
                continue
            x = self.sliderPositionToX(i)
            value_x = self.sliderPositionToX(self.value())
            if (x < (value_x)-6) or (x > (value_x+6)):
                y = self.height() - 18  # You can adjust this
                radius = 1  # Radius of circle
                painter.drawEllipse(QPoint(x, y), radius, radius)

        painter.end()

    def _slider_style_option(self, position=None):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        if position is not None:
            try:
                slider_position = int(round(float(position)))
            except (TypeError, ValueError):
                slider_position = int(self.value())
            option.sliderPosition = slider_position
            option.sliderValue = slider_position
        return option

    def _handle_rect_for_position(self, position):
        option = self._slider_style_option(position)
        return self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)

    def _slider_geometry(self):
        option = self._slider_style_option()
        groove_rect = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, self)
        handle_rect = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
        return option, groove_rect, handle_rect
  

    def sliderPositionToX(self, position):
        """Convert a slider position to its corresponding X coordinate."""
        minimum_value = self.minimum()
        maximum_value = self.maximum()
        minimum_handle = self._handle_rect_for_position(minimum_value)
        maximum_handle = self._handle_rect_for_position(maximum_value)
        minimum_center = float(minimum_handle.x()) + (float(minimum_handle.width()) * 0.5)
        maximum_center = float(maximum_handle.x()) + (float(maximum_handle.width()) * 0.5)
        if maximum_value == minimum_value:
            return minimum_center
        ratio = (float(position) - float(minimum_value)) / float(maximum_value - minimum_value)
        ratio = max(0.0, min(1.0, ratio))
        return minimum_center + (ratio * (maximum_center - minimum_center))

    def mousePressEvent(self, event):
        self.setFocus(Qt.MouseFocusReason)
        if self.main_window is not None:
            self.main_window.set_active_image_panel("timeline")
        x = event.x()  # X-coordinate of mouse click
        y = event.y()  # Y-coordinate of mouse click
        if event.button() != Qt.LeftButton:
            super(FrameSlider, self).mousePressEvent(event)
            return

        # Translate x coordinate to slider position
        clicked_position = int(round(self.xToSliderPosition(x)))
        clicked_position = max(self.minimum(), min(self.maximum(), clicked_position))

        # Check if clicked near any keyframe
        for keyframe in self.keyframes:
            keyframe_x = self.sliderPositionToX(keyframe)
            keyframe_y = self.height() - 5.5  # Same as in paintEvent
            if ((keyframe_x - x)**2 + (keyframe_y - y)**2) <= 25:  # Threshold distance to detect click, can adjust
                self.main_window.navigate_to_image(keyframe)
                return  # Don't propagate event further
        
        for flagframe in self.flaggedframes:
            flagframe_x = self.sliderPositionToX(flagframe)
            flagframe_y = self.height() - 5.5  # Same as in paintEvent
            if ((flagframe_x - x)**2 + (flagframe_y - y)**2) <= 9:  # Threshold distance to detect click, can adjust
                self.main_window.navigate_to_image(flagframe)
                return  # Don't propagate event further

        handle_rect = self._handle_rect_for_position(self.value()).adjusted(-2, -2, 2, 2)
        if not handle_rect.contains(QPoint(int(round(x)), int(round(y)))):
            if self.main_window is not None:
                self.main_window.navigate_to_image(clicked_position)
            else:
                self.setValue(clicked_position)
            event.accept()
            return

        super(FrameSlider, self).mousePressEvent(event)  # Call parent's mousePressEvent

    def mouseReleaseEvent(self, event):
        super(FrameSlider, self).mouseReleaseEvent(event)
        QTimer.singleShot(0, self.restore_viewer_focus)

    def xToSliderPosition(self, x):
        """Translate X-coordinate to slider position."""
        minimum_value = self.minimum()
        maximum_value = self.maximum()
        if maximum_value == minimum_value:
            return self.minimum()
        option, groove_rect, handle_rect = self._slider_geometry()
        travel_span = max(0, int(groove_rect.width() - handle_rect.width()))
        if travel_span <= 0:
            return minimum_value
        relative_x = int(round(float(x) - float(groove_rect.x()) - (float(handle_rect.width()) * 0.5)))
        relative_x = max(0, min(travel_span, relative_x))
        return QStyle.sliderValueFromPosition(
            minimum_value,
            maximum_value,
            relative_x,
            travel_span,
            option.upsideDown,
        )
    
    def handle_value_change(self, value):
        self.value_has_changed = True

    def handle_slider_release(self):
        if self.value_has_changed:
            self.value_has_changed = False

    def restore_viewer_focus(self):
        if self.main_window is not None:
            self.main_window.set_active_image_panel("viewer")
            if hasattr(self.main_window, "view") and self.main_window.view is not None:
                self.main_window.view.setFocus(Qt.MouseFocusReason)
                viewport = self.main_window.view.viewport()
                if viewport is not None:
                    viewport.setFocus(Qt.MouseFocusReason)

    def keyPressEvent(self, event):
        if self.main_window is not None:
            if self.main_window.handle_frame_navigation_shortcut(event.key()):
                event.accept()
                return
        super().keyPressEvent(event)
        

    
class SliderZoom_Slider(QSlider):
    def __init__(self, orientation=Qt.Horizontal, main_window=None, parent=None):
        super(SliderZoom_Slider, self).__init__(orientation, parent)
        self.main_window = main_window

        self.setValue(1)  # Initial zoom level
        self.setMinimum(1)
        self.setMaximum(2)
        self.setSingleStep(1)
        self.setFixedWidth(200)
        
    def mousePressEvent(self, event):
        self.main_window.image_slider.set_left_ratio()

        super().mousePressEvent(event)
