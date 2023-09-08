
from PySide6.QtWidgets import QSlider
from PySide6.QtGui import QPainter, QPen, QColor, QPolygon, QBrush, QPolygonF, QPainterPath
from PySide6.QtCore import Qt, Signal, QPoint, QPointF

VIEW_NEW_IMAGE   = 0
ADD_SELECTION    = 1
DELETE_SELECTION = 2
EDIT_SELECTION   = 3
TOGGLE_KEYFRAME  = 4
TOGGLE_FLAGFRAME = 5

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
        self.custom_ticks = [0] # set when loading images
        self.left_ratio = None
        self.raise_()
        self.value_has_changed = False

        self.valueChanged.connect(self.handle_value_change)
        self.sliderReleased.connect(self.handle_slider_release)

    def set_custom_ticks(self):
        original_range = len(self.main_window.imagePaths)
        tick_interval = int(self.main_window.slider_tick_pixel_interval * original_range / self.width())
        if tick_interval == 0:
            tick_interval = 1
        self.custom_ticks = range(0, original_range, tick_interval)
        self.update()

    def set_left_ratio(self):
        self.left_ratio = (self.value() - self.minimum())/(self.maximum() - self.minimum())

    def update_zoomed_level(self, zoom_value):
        """Updates the zoom level of the slider based on zoom_value."""
        original_range = len(self.main_window.imagePaths)
        center_position = self.value()  # Get current handle position
        new_slider_range = original_range/zoom_value - 1

        if self.left_ratio:
            left_ratio = self.left_ratio
        else:
            left_ratio = (self.value() - 0)/original_range

        left_length = int(new_slider_range * left_ratio)
        min_value = center_position - left_length
        max_value = min_value + new_slider_range

        if min_value <= 0:
            min_value = 0
            max_value = new_slider_range
        elif max_value >= (original_range-1):
            max_value = original_range - 1
            min_value = max_value - new_slider_range

        self.setRange(min_value, max_value)
        self.left_ratio = left_ratio # so that the slider hodler can stay at one place roughly
        self.update()

    def toggle_keyframe(self):
        """Toggle a keyframe at the given position."""
        if self.isEnabled():
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
        
            self.main_window.addToHistory(TOGGLE_KEYFRAME)
            

    def toggle_flagging(self):
        """Toggle a keyframe at the given position."""
        if self.isEnabled():
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
        
            self.main_window.addToHistory(TOGGLE_FLAGFRAME)


    def paintEvent(self, event):
        """Override the paintEvent to draw keyframe indicators, flag indicators, and tickmarks."""

        super(FrameSlider, self).paintEvent(event)

        # keyframe indicator

        painter = QPainter(self)
        brush = QBrush(QColor(10, 132, 255, 255))
        painter.setBrush(brush)
        painter.setRenderHint(QPainter.Antialiasing)

        for keyframe in self.keyframes:
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

        painter.end()  # Don't forget to end the painter

        # Flag indicator
        painter = QPainter(self)
        pen = QPen(QColor(255, 69, 58, 255))
        pen.setWidth(1)
        brush = QBrush(QColor(255, 69, 58, 255))
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.setRenderHint(QPainter.Antialiasing)

        for a_flag in self.flaggedframes:
            x = self.sliderPositionToX(a_flag) * 1.0
            y = self.height() - 5.5  # You can adjust this
            radius = 2.5  # Radius of circle
            painter.drawEllipse(QPointF(x, y), radius, radius)
            
        painter.end()

        # Tick Mark
        painter = QPainter(self)
        pen = QPen(QColor(178, 178, 178, 178))
        brush = QBrush(QColor(178, 178, 178, 178))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(brush)

        # Draw tick marks
        for i in self.custom_ticks:
            x = self.sliderPositionToX(i)
            value_x = self.sliderPositionToX(self.value())
            if (x < (value_x)-6) or (x > (value_x+6)):
                y = self.height() - 18  # You can adjust this
                radius = 1  # Radius of circle
                painter.drawEllipse(QPoint(x, y), radius, radius)

        painter.end()
  

    def sliderPositionToX(self, position):
        """Convert a slider position to its corresponding X coordinate."""
        leftoffset = 8  # Offset for each side of the slider
        rightoffset = 8 
        available_width = self.width() - (leftoffset+rightoffset)  # Effective width after accounting for offsets
        return (position - self.minimum()) / (self.maximum() - self.minimum()) * available_width + leftoffset

    def mousePressEvent(self, event):
        x = event.x()  # X-coordinate of mouse click
        y = event.y()  # Y-coordinate of mouse click

        # Translate x coordinate to slider position
        clicked_position = self.xToSliderPosition(x)

        # Check if clicked near any keyframe
        for keyframe in self.keyframes:
            keyframe_x = self.sliderPositionToX(keyframe)
            keyframe_y = self.height() - 5.5  # Same as in paintEvent
            distance = ((keyframe_x - x)**2 + (keyframe_y - y)**2)**0.5  # Euclidean distance

            if distance <= 5:  # Threshold distance to detect click, can adjust
                self.setValue(keyframe)  # Set slider to the clicked keyframe
                return  # Don't propagate event further
        
        for flagframe in self.flaggedframes:
            flagframe_x = self.sliderPositionToX(flagframe)
            flagframe_y = self.height() - 5.5  # Same as in paintEvent
            distance = ((flagframe_x - x)**2 + (flagframe_y - y)**2)**0.5  # Euclidean distance

            if distance <= 3:  # Threshold distance to detect click, can adjust
                self.setValue(flagframe)  # Set slider to the clicked flagframe
                return  # Don't propagate event further
        
        super(FrameSlider, self).mousePressEvent(event)  # Call parent's mousePressEvent

    def xToSliderPosition(self, x):
        """Translate X-coordinate to slider position."""
        leftoffset = 8  # Offset for each side of the slider
        rightoffset = 8
        available_width = self.width() - (leftoffset + rightoffset)
        relative_x = x - leftoffset
        position = self.minimum() + (self.maximum() - self.minimum()) * (relative_x / available_width)
        return position
    
    def handle_value_change(self, value):
        self.value_has_changed = True

    def handle_slider_release(self):
        
        self.main_window.delete_nonkf_changes_history()

        if self.value_has_changed:
            self.value_has_changed = False
            self.main_window.addToHistory(VIEW_NEW_IMAGE)
        

    
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