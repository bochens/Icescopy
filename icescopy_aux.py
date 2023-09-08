from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, 
                               QWidget, QGraphicsScene, QGraphicsEllipseItem, QLineEdit, QLabel,
                               QTextEdit, QSizePolicy, QHBoxLayout,QGraphicsView, QSplitter, QSlider, QDialog, QGraphicsProxyWidget)
from PySide6.QtGui import QImage, QPixmap, QPen, QPainter, Qt, QCursor, QTransform, QFont, QMouseEvent
from PySide6.QtCore import QRectF, QThread, Signal
from xml.etree.ElementTree import Element, SubElement, ElementTree, parse
import numpy as np
import cv2
from PIL import Image
import darkdetect
import multiprocessing
import os


from icescopy_selection_Items import Selection_circle

resources_dir = os.path.join(os.path.dirname(__file__), 'resources')

# METADATA FOR COMMAND TYPE FOR UNDO AND REDO
VIEW_NEW_IMAGE   = 0
ADD_SELECTION    = 1
DELETE_SELECTION = 2
EDIT_SELECTION   = 3
TOGGLE_KEYFRAME  = 4
TOGGLE_FLAGFRAME = 5

def create_circular_mask(h, w, center, radius):
    Y, X = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((X - center[0])**2 + (Y-center[1])**2)
    mask = dist_from_center <= radius
    return mask

class CustomGraphicsView(QGraphicsView):
    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main_window = main_window
        self.selected_items = []

        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def wheelEvent(self, event):
        if self.main_window.tool_mode == 'pan':
            zoom_factor = 1.15
            if event.angleDelta().y() > 0 and self.transform().m11() < self.main_window.maximum_zoom:  # scroll up and not at max zoom
                self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
                self.scale(zoom_factor, zoom_factor)
            elif event.angleDelta().y() < 0 and self.transform().m11() >0.03:  # scroll down
                self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
                self.scale(1/zoom_factor, 1/zoom_factor)
            self.main_window.updateZoomTextbox()

            event.accept()

        elif self.main_window.tool_mode in ['select','edit-new']:
            # Handle circle size change here for select mode
            if event.angleDelta().y() > 0:  # scroll up
                self.main_window.circle_radius = min(self.main_window.circle_radius + 1, self.main_window.image_width)
            else:  # scroll down
                self.main_window.circle_radius = max(self.main_window.circle_radius - 1, 1)
            self.main_window.updateRadiusTextbox()
            self.main_window.updateSelectCursor()

            event.accept()
        
        elif self.main_window.tool_mode in ['deselect','edit-choose']:
            pass # so no scrolling
        else:
            super().wheelEvent(event)
    
    def mousePressEvent(self, event):
        # Add a cicle upon clicking
        if self.main_window.tool_mode == 'select' and event.button() == Qt.LeftButton:
            # Convert widget coordinates to pixmap coordinates
            pixmap_pos = self.mapToScene(event.pos())
            if hasattr(self.main_window, 'pixmap_item'): 
                pixmap_matrix = self.main_window.pixmap_item.transform()

                # Apply the inverse transformation to get the corresponding pixel position on the pixmap
                inv_pixmap_matrix = pixmap_matrix.inverted()[0]
                image_pixel_pos = inv_pixmap_matrix.map(pixmap_pos)

                # Calculate the pixel position in the displayed image
                x_pixel = int(image_pixel_pos.x())
                y_pixel = int(image_pixel_pos.y())

                # Maintain the circle size in image pixel units
                circle_size = self.main_window.circle_radius
                
                circle_position = (pixmap_pos.x(), pixmap_pos.y())
                circle_pixel_position = (x_pixel, y_pixel)

                selection_number = len(self.main_window.selection_items)
                
                # Append the scene position for drawing
                self.main_window.selection_items.append(Selection_circle(self.main_window, circle_position, circle_size, circle_pixel_position, selection_number))

                self.main_window.log(f"Add selection {selection_number} at ({x_pixel}, {y_pixel}); Circle size: {circle_size}")
                self.main_window.displayMarkedRegions()
                self.main_window.add_selection_item_to_keyframes()
                self.main_window.addToHistory(ADD_SELECTION)

        elif self.main_window.tool_mode == 'edit-new' and event.button() == Qt.LeftButton:
            # Under the selection cursor right now
            pixmap_pos = self.mapToScene(event.pos())
            if hasattr(self.main_window, 'pixmap_item'):
                pixmap_matrix = self.main_window.pixmap_item.transform()
                
                # Apply the inverse transformation to get the corresponding pixel position on the pixmap
                inv_pixmap_matrix = pixmap_matrix.inverted()[0]
                image_pixel_pos = inv_pixmap_matrix.map(pixmap_pos)

                # Calculate the pixel position in the displayed image
                x_pixel = int(image_pixel_pos.x())
                y_pixel = int(image_pixel_pos.y())

                # Maintain the circle size in image pixel units
                circle_size = self.main_window.circle_radius
                
                circle_position = (pixmap_pos.x(), pixmap_pos.y())
                circle_pixel_position = (x_pixel, y_pixel)

                selection_number = None
                for item in self.main_window.scene.items():
                    if isinstance(item, Selection_circle):
                        if item.edit_chosen:
                            selection_number = item.selection_number
                            item.edit_chosen = False
                
                # EDITING THE CURRENT FRAME SELECTION
                self.main_window.selection_items[selection_number] = Selection_circle(self.main_window, circle_position, circle_size, circle_pixel_position, selection_number)

                self.main_window.log(f"Updated selection {selection_number} to ({x_pixel}, {y_pixel}); Circle size: {circle_size}")
                self.main_window.displayMarkedRegions()
                self.main_window.edit_current_keyframe_selection_item() # update the change of edit
                self.main_window.tool_mode = 'edit-done'
                self.main_window.addToHistory(EDIT_SELECTION)

                # proceed to mouseReleaseEvent in icescopy_selection_items.py

        elif self.main_window.tool_mode == 'edit-new' and event.button() == Qt.RightButton:
            # Under the selection cursor right now
            # Cancel edit-new, Go back to edit-choose mode

            # reset edit choosen items
            for item in self.main_window.scene.items():
                if isinstance(item, Selection_circle):
                    if item.edit_chosen:
                        item.edit_chosen = False

            self.main_window.log(f"Cancel Edit")
            self.main_window.displayMarkedRegions()

            # does not go back to other events so has to be handeled here

            self.main_window.editTool(self.main_window.edit_tool_action.isChecked())
            self.main_window.image_slider.setEnabled(True) # Reenable view new image 
            self.main_window.leftButton.setEnabled(True)
            self.main_window.rightButton.setEnabled(True)
            self.main_window.set_undo_status() # Renable redo status
            self.main_window.set_redo_status() # Disable undo status


        
        elif self.main_window.tool_mode == 'pan':
            self.selected_items = self.main_window.scene.selectedItems()

        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        # Delete a circle upon clicking
        if self.main_window.tool_mode == 'deselect' and event.button() == Qt.LeftButton:
            # Find the item at the clicked position
            # Get the scene position
            scene_pos = self.mapToScene(event.pos())
    
            clicked_item = self.scene().itemAt(scene_pos, QTransform())
            if clicked_item and isinstance(clicked_item, Selection_circle):
                self.main_window.selection_items.pop(clicked_item.selection_number)
                clicked_item.pressed = False
                self.main_window.log(f"Delete selection {clicked_item.selection_number} at {clicked_item.circle_pixel_positions}")
                
                self.main_window.displayMarkedRegions() # reset the numbers of the selection items and redraw everything
                self.main_window.delete_selection_item_to_keyframes(clicked_item.selection_number)
                self.main_window.addToHistory(DELETE_SELECTION)

        elif self.main_window.tool_mode == 'edit-choose' and event.button() == Qt.LeftButton:
            # delt with in Selection_circle Class
            pass
        
        super().mouseReleaseEvent(event)

        # Has to be below super event call
        # this is so pan does not affect item selection at all but also keep all the selected item selected
        if self.main_window.tool_mode == 'pan':

            for item in self.main_window.scene.selectedItems():
                item.setSelected(False)

            if self.selected_items: # is not an empty list
                for item in self.main_window.scene.items():
                    if item in self.selected_items:
                        item.setSelected(True)
    

class Image_analysis_thread(QThread):
    # Class Variables
    analysis_done = Signal(int, dict)  # Signal emitted when analysis is done

    def __init__(self, filePath, imagePaths, imageNames, list_of_selection_items, list_of_red_flags):
        super().__init__()
        self.filePath   = filePath
        self.imagePaths = imagePaths
        self.imageNames = imageNames
        # self.circle_pixel_positions = circle_pixel_positions
        # self.circle_sizes = circle_sizes

        self.list_of_selection_items = list_of_selection_items
        self.list_of_red_flags = list_of_red_flags

        self.imageFolderPath = os.path.dirname(self.imagePaths[0])

    def run(self):
        file_name_list = []
        date_time_list = []
        gss_table = []
        circle_pixel_positions_table = []
        circle_radius_table = []

        for i in range(len(self.imagePaths)):
            file_name = self.imageNames[i]

            circle_pixel_positions = [circle.circle_pixel_positions for circle in self.list_of_selection_items[i]]
            circle_sizes = [circle.circle_sizes for circle in self.list_of_selection_items[i]]

            exif_datetime = self.get_exif_datetime(self.imagePaths[i])
            if exif_datetime:
                exif_datetime = exif_datetime.replace(" ", "T").replace(":", "-", 2)
            gss_list = self.gray_scale_mean(self.imagePaths[i], circle_pixel_positions, circle_sizes)
            
            file_name_list.append(file_name)
            date_time_list.append(exif_datetime)
            gss_table.append(gss_list)
            circle_pixel_positions_table.append(circle_pixel_positions)
            circle_radius_table.append(circle_sizes)
            
            # Emit a signal to update the UI, if needed
            self.analysis_done.emit(i, {'file_name': file_name, 'exif_datetime': exif_datetime, 'gss_list': gss_list})
        
        # Write to CSV file
        with open(self.filePath, 'w') as the_file:
            the_file.write(self.imageFolderPath)
            the_file.write("\n")
            the_file.write('file_name,exif_datetime,flag_state')
            for i in range(len(gss_table[i])):
                the_file.write(",")
                the_file.write('selection_'+str(i)+'_grayscale')
                the_file.write(",")
                the_file.write('selection_'+str(i)+'_circle_x')
                the_file.write(",")
                the_file.write('selection_'+str(i)+'_circle_y')
                the_file.write(",")
                the_file.write('selection_'+str(i)+'_circle_radius')
            the_file.write("\n")
            for i in range(len(date_time_list)):
                the_file.write(str(file_name_list[i]))
                the_file.write(",")
                the_file.write(str(date_time_list[i]))
                the_file.write(",")
                if i in self.list_of_red_flags:
                    the_file.write('flagged')
                else:
                    the_file.write(' ')
                for j in range(len(gss_table[i])):
                    the_file.write(",")
                    the_file.write(str(gss_table[i][j]))
                    the_file.write(",")
                    the_file.write(str(circle_pixel_positions_table[i][j][0]))
                    the_file.write(",")
                    the_file.write(str(circle_pixel_positions_table[i][j][1]))
                    the_file.write(",")
                    the_file.write(str(circle_radius_table[i][j]))
                the_file.write("\n")

    def gray_scale_mean(self, image_path, circle_pixel_positions, circle_sizes):
        image = cv2.imread(image_path)
        # Check if the image is already grayscale, and read into grayscale with OPENCV
        if len(image.shape) == 2:
            image_gray = image
        elif len(image.shape) == 3:
            image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            raise Exception("Unknown image type")

        gss_list = [] # gray scale sum table
        for i in range(len(circle_pixel_positions)):
            x = circle_pixel_positions[i][0]
            y = circle_pixel_positions[i][1]
            a_mask = create_circular_mask(np.shape(image_gray)[0], np.shape(image_gray)[1], center = [x, y], radius=circle_sizes[i])
            gray_scale_mean = np.sum(image_gray[a_mask]) / np.sum(a_mask)
            gss_list.append(gray_scale_mean)
        
        return gss_list

    def get_exif_datetime(self, image_path):
        try:
            # Read with PIL to get EXIF information
            pil_image = Image.open(image_path)
            image_exif = pil_image.getexif()
            image_datetime = image_exif[306]
            return image_datetime
        except:
            # the return value is None, so the processCSVData will handel the None value and log the information that the EXIF information extration failed
            pass
  

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Icescopy")
        self.setFixedSize(300, 550)  # Set the fixed size of the dialog

        layout = QVBoxLayout()

        logo_label = QLabel()
        logo_image = QImage(os.path.join(resources_dir,"icescopy_icon.png"))  # Load your logo image
        #logo_image = logo_image.scaledToWidth(120)
        logo_label.setPixmap(QPixmap.fromImage(logo_image))
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)

        text_label = QLabel()
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setText("Icescopy Version 1.0\nA powerful image analysis tool for ice freezing array experiments.")
        text_label.setFont(QFont("Arial", 12, QFont.Bold))
        text_label.setWordWrap(True)
        layout.addWidget(text_label)

        rights_label = QLabel()
        rights_label.setAlignment(Qt.AlignCenter)
        rights_label.setText("Copyright \u00A9 2023 Bo Chen, and Sarah Brooks Group at Texas A&M University\n")
        rights_label.setFont(QFont("Arial", 12))
        rights_label.setWordWrap(True)
        layout.addWidget(rights_label)

        licenselabel = QLabel()
        licenselabel.setTextInteractionFlags(Qt.TextBrowserInteraction)  # Makes the label text clickable
        licenselabel.setText('Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.')
        licenselabel.setWordWrap(True)
        licenselabel.setFont(QFont("Arial", 8))
        licenselabel.setStyleSheet("""color: rgba(127, 127, 127, 255);""")
        licenselabel.setAlignment(Qt.AlignCenter)

        layout.addWidget(licenselabel)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)

        self.setLayout(layout)


class PreferencesDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
        self.setWindowTitle("Preferences")
        layout = QVBoxLayout()

        self.default_circle_radius_field = QLineEdit()
        self.pen_width_field = QLineEdit()
        self.maximum_zoom_field = QLineEdit()
        self.dot_size_field = QLineEdit()
        self.slider_maxzoom_pixel_interval_field = QLineEdit()
        self.slider_tick_pixel_interval_field = QLineEdit()

        self.default_circle_radius_field.setText(str(self.main_window.circle_radius))
        self.pen_width_field.setText(str(self.main_window.pen_width))
        self.maximum_zoom_field.setText(str(self.main_window.maximum_zoom))
        self.dot_size_field.setText(str(self.main_window.dot_size))
        self.slider_maxzoom_pixel_interval_field.setText(str(self.main_window.slider_maxzoom_pixel_interval))
        self.slider_tick_pixel_interval_field.setText(str(self.main_window.slider_tick_pixel_interval))

        layout.addWidget(QLabel("Default Circle Radius"))
        layout.addWidget(self.default_circle_radius_field)

        layout.addWidget(QLabel("Pen Width"))
        layout.addWidget(self.pen_width_field)

        layout.addWidget(QLabel("Maximum Zoom"))
        layout.addWidget(self.maximum_zoom_field)

        layout.addWidget(QLabel("Dot Size"))
        layout.addWidget(self.dot_size_field)

        layout.addWidget(QLabel("Slider Max Zoom Pixel Interval"))
        layout.addWidget(self.slider_maxzoom_pixel_interval_field)

        layout.addWidget(QLabel("Slider Tick Pixel Interval"))
        layout.addWidget(self.slider_tick_pixel_interval_field)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_preferences)
        layout.addWidget(save_button)

        self.setLayout(layout)

    def save_preferences(self):
        root = Element('Preferences')

        SubElement(root, "DefaultCircleRadius").text = self.default_circle_radius_field.text()
        SubElement(root, "PenWidth").text = self.pen_width_field.text()
        SubElement(root, "MaximumZoom").text = self.maximum_zoom_field.text()
        SubElement(root, "DotSize").text = self.dot_size_field.text()
        SubElement(root, "SliderMaxZoomPixelInterval").text = self.slider_maxzoom_pixel_interval_field.text()
        SubElement(root, "SliderTickPixelInterval").text = self.slider_tick_pixel_interval_field.text()

        tree = ElementTree(root)
        tree.write(os.path.join(resources_dir,"preferences.xml"))
        self.main_window.set_preferences()
        self.accept()

