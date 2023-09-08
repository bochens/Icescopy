from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, 
                               QWidget, QGraphicsScene, QGraphicsEllipseItem, QLineEdit, QLabel,
                               QTextEdit, QSizePolicy, QHBoxLayout,QGraphicsView, QSplitter, QSlider, QDialog, QGraphicsItem)
from PySide6.QtGui import QImage, QPixmap, QPen, QPainter, Qt, QCursor, QTransform, QFont, QColor
from PySide6.QtCore import QRectF, QThread, Signal
import numpy as np
import os
import cv2
from PIL import Image
import warnings
import darkdetect
import copy

class Selection_circle(QGraphicsEllipseItem):
    # This class should be shallow copy friendly. At no point should the attributes gets changed, always create a new one instead of making changes
    def __init__(self, main_window, circle_positions, circle_sizes, circle_pixel_positions, selection_number):
        self.main_window = main_window

        super().__init__(circle_positions[0] - circle_sizes, circle_positions[1] - circle_sizes, 2*circle_sizes, 2*circle_sizes)

        self.circle_positions = circle_positions                # position of the center of the circle for drawing
        self.circle_sizes = circle_sizes                        # circle radius in terms of pixels of the image      
        self.circle_pixel_positions = circle_pixel_positions    # position of the center of the circle on the image
        self.selection_number = selection_number                      # the number assigned to the circle

        self.update_selectable_state()     # enable selection
        self.setAcceptHoverEvents(True)                         # enable hover event

        # state attributes
        self.hover = False
        self.pressed = False
        self.edit_chosen = False

    # paint function is called when:
    #   1. item is added to the scene
    #   2. item's properties changes
    #   3. item is selected or deselected
    #   4. when the view is refreshed
    #   5. manual update by triggering the pain function
    def paint(self, painter, option, widget):
        # Call the superclass paint method to get the default behavior
        super().paint(painter, option, widget)

        # Check if the item is selected
        if self.pressed:
            pen = QPen(Qt.yellow)
        elif self.edit_chosen:
            pen = QPen(QColor(240, 168, 168))
        elif self.hover:
            pen = QPen(Qt.blue)
        else:
            pen = QPen(Qt.red)


        pen.setWidth(self.main_window.pen_width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Draw the ellipse using the pen settings
        painter.drawEllipse(self.rect())

        # Draw the selection number at the center of the ellipse
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.setPen(pen)
        painter.drawText(self.circle_positions[0] + self.circle_sizes +6, self.circle_positions[1] + self.circle_sizes +6, str(self.selection_number))

        # Note: You could also use self.setPen(pen) here, but then you'd need to trigger an update
        # to ensure the item is redrawn. Overriding paint avoids that.
    
    def hoverEnterEvent(self, event):
        # Called when the mouse enters the item
        if self.main_window.tool_mode in ["cursor", "deselect", "edit-choose", "edit-new", "edit-done"]:
            self.hover = True
            self.update()

    def hoverLeaveEvent(self, event):
        if self.main_window.tool_mode in ["cursor", "select", "deselect", "edit-choose", "edit-new", "pan"]:
            # Called when the mouse leaves the item
            self.hover = False
            self.update()  # Schedule a repaint

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.main_window.tool_mode in ["cursor", "deselect", "edit-choose"]:
                self.pressed = True  # Update the pressed state
                self.update()  # Schedule a repaint
            
            # Only the cursor can select a Selection
            if self.main_window.tool_mode in ["cursor"]:
                super().mousePressEvent(event)  # Call parent class method
            
            if self.main_window.tool_mode in ["pan"]:
                event.ignore()


    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.main_window.tool_mode in ["cursor", "select", "deselect", "edit-choose", "edit-done", "pan"]:
                self.pressed = False  # Update the pressed state
                self.update()  # Schedule a repaint

            if self.main_window.tool_mode == "edit-choose":
                self.edit_chosen = True
                self.update()  # Schedule a repaint
                self.main_window.tool_mode = 'edit-new'
                self.main_window.set_undo_status() # Disable redo and undo during "edit-new"
                self.main_window.set_redo_status() # Disable redo and undo during "edit-new"
                self.main_window.updateSelectCursor() # Switch to Add selection cursor
                self.main_window.image_slider.setEnabled(False) # make sure you stay on the same frame while editing 
                self.main_window.leftButton.setEnabled(False) 
                self.main_window.rightButton.setEnabled(False)

            if self.main_window.tool_mode == "edit-done":
                self.main_window.tool_mode = "edit-choose"
                self.main_window.set_undo_status() # Enable redo and undo after going back to "edit-choose"
                self.main_window.set_redo_status() # Enable redo and undo after going back to "edit-choose"
                self.main_window.view.setCursor(Qt.PointingHandCursor)
                self.main_window.image_slider.setEnabled(True)
                self.main_window.leftButton.setEnabled(True)
                self.main_window.rightButton.setEnabled(True)
                self.update()

            if self.main_window.tool_mode in ["cursor"]:
                super().mouseReleaseEvent(event)
            
            if self.main_window.tool_mode in ["pan"]:
                event.ignore()
        
    def update_selectable_state(self):
        if self.main_window.tool_mode in ["cursor", "pan"]:
            self.setFlag(QGraphicsEllipseItem.ItemIsSelectable, True)
        else:
            self.setFlag(QGraphicsEllipseItem.ItemIsSelectable, False)
        
    def __deepcopy__(self, memo):
        # Create a new instance of Selection_circle with the same attributes as the original
        new_circle = Selection_circle(self.main_window, 
                                    copy.deepcopy(self.circle_positions, memo), 
                                    copy.deepcopy(self.circle_sizes, memo), 
                                    copy.deepcopy(self.circle_pixel_positions, memo),
                                    copy.deepcopy(self.selection_number, memo))

        # Set state variables
        new_circle.hover = False
        new_circle.pressed = False
        new_circle.edit_chosen = False

        # Add the new instance to the memo dictionary to avoid infinite recursion
        memo[id(self)] = new_circle

        return new_circle
