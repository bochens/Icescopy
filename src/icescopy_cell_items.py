from dataclasses import dataclass

from PySide6.QtWidgets import QGraphicsEllipseItem
from PySide6.QtGui import QPen, QPainter, Qt, QFont, QColor, QStaticText
from PySide6.QtCore import QPointF
import copy


@dataclass(slots=True)
class CellSnapshot:
    circle_positions: tuple
    circle_sizes: float
    circle_pixel_positions: tuple
    cell_id: int
    edit_chosen: bool = False
    hover: bool = False
    pressed: bool = False


class CellCircle(QGraphicsEllipseItem):
    LABEL_FONT = QFont("Arial", 12, QFont.Bold)
    LABEL_FONT.setHintingPreference(QFont.PreferNoHinting)
    LABEL_OFFSET_X = 6
    LABEL_OFFSET_Y = 6
    Z_VALUE = 1_000

    # This class should be shallow copy friendly. At no point should the attributes gets changed, always create a new one instead of making changes
    def __init__(self, main_window, circle_positions, circle_sizes, circle_pixel_positions, cell_id):
        self.main_window = main_window

        super().__init__(circle_positions[0] - circle_sizes, circle_positions[1] - circle_sizes, 2*circle_sizes, 2*circle_sizes)

        self.circle_positions = circle_positions                # position of the center of the circle for drawing
        self.circle_sizes = circle_sizes                        # circle radius in terms of pixels of the image      
        self.circle_pixel_positions = circle_pixel_positions    # position of the center of the circle on the image
        self.cell_id = cell_id                      # the number assigned to the circle
        self._label_text = QStaticText(str(self.cell_id))
        self.setZValue(self.Z_VALUE)

        self.update_selectable_state()     # enable selection
        self.setAcceptHoverEvents(True)                         # enable hover event

        # state attributes
        self.hover = False
        self.pressed = False
        self.edit_chosen = False

    def sync_from_data(
        self,
        circle_positions,
        circle_sizes,
        circle_pixel_positions,
        cell_id,
        *,
        edit_chosen=None,
        hover=False,
        pressed=False,
    ):
        self.circle_positions = circle_positions
        self.circle_sizes = circle_sizes
        self.circle_pixel_positions = circle_pixel_positions
        if self.cell_id != cell_id:
            self._label_text = QStaticText(str(cell_id))
        self.cell_id = cell_id
        if edit_chosen is not None:
            self.edit_chosen = edit_chosen
        self.hover = hover
        self.pressed = pressed
        self.setRect(
            circle_positions[0] - circle_sizes,
            circle_positions[1] - circle_sizes,
            2 * circle_sizes,
            2 * circle_sizes,
        )
        self.update_selectable_state()
        self.update()

    # paint function is called when:
    #   1. item is added to the scene
    #   2. item's properties changes
    #   3. item is selected or deselected
    #   4. when the view is refreshed
    #   5. manual update by triggering the pain function
    def paint(self, painter, option, widget):
        sample_color = self.main_window.sample_visual_color_for_cell(self.cell_id)
        # Check if the item is selected
        if self.pressed:
            pen = QPen(self.main_window.get_qcolor(self.main_window.circle_pressed_color))
        elif self.edit_chosen:
            pen = QPen(self.main_window.get_qcolor(self.main_window.circle_edit_color))
        elif self.isSelected():
            pen = QPen(self.main_window.get_qcolor(self.main_window.circle_selected_color))
        elif self.hover:
            pen = QPen(self.main_window.get_qcolor(self.main_window.circle_hover_color))
        else:
            pen = QPen(self.main_window.get_qcolor(self.main_window.circle_default_color))

        pen.setWidth(self.main_window.pen_width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Draw the ellipse using the pen settings
        painter.drawEllipse(self.rect())

        # Draw the cell ID near the ellipse.
        label_font = QFont(self.LABEL_FONT)
        label_font_size = float(
            getattr(self.main_window, "circle_label_font_size", self.LABEL_FONT.pointSizeF())
        )
        label_font.setPointSizeF(max(1.0, label_font_size))
        painter.setFont(label_font)
        label_pen = QPen(sample_color if sample_color is not None else pen.color())
        label_pen.setWidth(1)
        painter.setPen(label_pen)
        label_offset_x = float(getattr(self.main_window, "circle_label_offset_x", self.LABEL_OFFSET_X))
        label_offset_y = float(getattr(self.main_window, "circle_label_offset_y", self.LABEL_OFFSET_Y))
        label_x = float(self.circle_positions[0] + self.circle_sizes + label_offset_x)
        baseline_y = float(self.circle_positions[1] + self.circle_sizes + label_offset_y)
        label_y = baseline_y - float(painter.fontMetrics().ascent())
        painter.drawStaticText(QPointF(label_x, label_y), self._label_text)

        # Note: You could also use self.setPen(pen) here, but then you'd need to trigger an update
        # to ensure the item is redrawn. Overriding paint avoids that.
    
    def hoverEnterEvent(self, event):
        # Called when the mouse enters the item
        if self.main_window.tool_mode in ["cursor", "deselect", "edit-choose", "edit-new", "edit-group", "image-edit"]:
            self.hover = True
            self.update()

    def hoverLeaveEvent(self, event):
        if self.main_window.tool_mode in ["cursor", "select", "deselect", "edit-choose", "edit-new", "pan", "edit-group", "image-edit"]:
            # Called when the mouse leaves the item
            self.hover = False
            self.update()  # Schedule a repaint

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.main_window.tool_mode in ["cursor", "deselect", "edit-choose", "edit-group", "image-edit"]:
                self.pressed = True  # Update the pressed state
                self.update()  # Schedule a repaint
            
            # Only Cursor is allowed to mutate Qt's scene selection directly.
            # Edit consumes the already-established selection instead of trying
            # to be a second selection tool.
            if self.main_window.tool_mode in ["cursor", "image-edit"]:
                super().mousePressEvent(event)  # Call parent class method
            
            if self.main_window.tool_mode in ["pan"]:
                event.ignore()


    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.main_window.tool_mode in ["cursor", "select", "deselect", "edit-choose", "pan", "edit-group", "image-edit"]:
                self.pressed = False  # Update the pressed state
                self.update()  # Schedule a repaint

            if self.main_window.tool_mode in ["cursor", "image-edit"]:
                super().mouseReleaseEvent(event)

            if self.main_window.tool_mode == "edit-choose":
                self.main_window.activate_edit_cell_item(self)

            if self.main_window.tool_mode in ["pan"]:
                event.ignore()
        
    def update_selectable_state(self):
        # Restrict Qt's built-in item selection to Cursor mode so group/edit
        # state stays stable when switching tools.
        if self.main_window.tool_mode in {"cursor", "edit-choose", "image-edit"}:
            self.setFlag(QGraphicsEllipseItem.ItemIsSelectable, True)
        else:
            self.setFlag(QGraphicsEllipseItem.ItemIsSelectable, False)
        
    def __deepcopy__(self, memo):
        # Create a new instance of CellCircle with the same attributes as the original
        new_circle = CellCircle(self.main_window, 
                                    copy.deepcopy(self.circle_positions, memo), 
                                    copy.deepcopy(self.circle_sizes, memo), 
                                    copy.deepcopy(self.circle_pixel_positions, memo),
                                    copy.deepcopy(self.cell_id, memo))
        new_circle._label_text = QStaticText(str(new_circle.cell_id))

        # Set state variables
        new_circle.hover = False
        new_circle.pressed = False
        new_circle.edit_chosen = False

        # Add the new instance to the memo dictionary to avoid infinite recursion
        memo[id(self)] = new_circle

        return new_circle
