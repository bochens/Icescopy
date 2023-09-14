from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, 
                               QWidget, QGraphicsScene, QGraphicsEllipseItem, QLineEdit, QLabel,
                               QTextEdit, QSizePolicy, QHBoxLayout,QGraphicsView, QSplitter, QSlider, QStatusBar, QGraphicsTextItem, QGraphicsProxyWidget, QDialog)
from PySide6.QtGui import QImage, QPixmap, QPen, QPainter, Qt, QCursor, QTransform, QFont, QAction, QIcon, QWindowStateChangeEvent, QGuiApplication, QResizeEvent, QTextOption, QTextBlockFormat, QTextCursor
from PySide6.QtCore import QRectF, QSize, QTimer, QEvent, QCoreApplication
import xml.etree.ElementTree as ET
import os
import glob
import darkdetect
import platform
import time
from functools import partial
import copy
import numpy as np

# Custom Python Files
from icescopy_aux import CustomGraphicsView, AboutDialog, Image_analysis_thread, PreferencesDialog
import icescopy_stylesheet
from icescopy_selection_Items import Selection_circle
from icescopy_frameslider import FrameSlider, SliderZoom_Slider
from icescopy_freezfinder import FreezeFinderDialog


resources_dir = os.path.join(os.path.dirname(__file__), 'resources')

# METADATA FOR COMMAND TYPE FOR UNDO AND REDO
VIEW_NEW_IMAGE   = 0
ADD_SELECTION    = 1
DELETE_SELECTION = 2
EDIT_SELECTION   = 3
TOGGLE_KEYFRAME  = 4
TOGGLE_FLAGFRAME = 5

class IceScopy(QMainWindow):

    def __init__(self):

        # SETTINGS
        self.circle_radius = 22 #default value
        self.pen_width = 1
        self.maximum_zoom = 10
        self.dot_size = 1
        self.slider_maxzoom_pixel_interval = 10
        self.slider_tick_pixel_interval = 20
        

        super().__init__()
        self.initData()
        self.initUI()
        self.set_preferences()

        # miscellaneous
        self.temporary_event_data = {}
        self.space_held = False             # important for using space to activate an and zoom

    def set_preferences(self):
        preferences = {}
        # use .get() method on a dictionary to specify a default value if a key is not found.
        try:
            preferences = self.load_preferences_from_xml()
        except FileNotFoundError:
            print('No preference file set')
            # If the preferences.xml file is not found, you might want to save the default preferences
            pass

        self.circle_radius = preferences.get('DefaultCircleRadius', self.circle_radius)
        self.maximum_zoom = preferences.get('MaximumZoom', self.maximum_zoom)
        self.pen_width = max(1, preferences.get('PenWidth', self.pen_width))
        self.dot_size = preferences.get('DotSize', self.dot_size)
        self.slider_maxzoom_pixel_interval = preferences.get('SliderMaxZoomPixelInterval', self.slider_maxzoom_pixel_interval)
        self.slider_tick_pixel_interval = preferences.get('SliderTickPixelInterval', self.slider_tick_pixel_interval)


        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()
        self.scene.update()

    def initData(self):
        # Gets called so wiped at loading images
        # All Attributes related to data
        
        self.selection_items = [] # current displayed selection items

        self.command_history_list = []
        self.history_index = -1  # Index to keep track of the current history state

        self.keyframe_list = []
        self.flagframe_list = []
        self.keyframe_selection_items_dict = {} # a dictionary. {frame number: selection_items}
        
        
        self.image_width = None  # Add image_width attribute
        self.imagePaths = []
        self.imageNames = []
        self.image_index = 0  # Index of the currently displayed image

        # miscellaneous
        self.timer = None
        self.output_state = False
        self.circle_cursor = None

        
    def initUI(self):
        # Set main window properties
        self.setWindowTitle('Icescopy')
        self.setGeometry(100, 100, 1000, 700)

        # Create a menu bar
        menubar = self.menuBar()

        # Create the "IceScopy" menu
        icescopy_menu = menubar.addMenu("IceScopy")
        icescopy_menu.setFont(QFont("Arial", 10, QFont.Bold))

        # Add "About" action to "IceScopy" menu
        about_action = QAction("About", self)
        about_action.triggered.connect(self.showAboutDialog)
        icescopy_menu.addAction(about_action)
        icescopy_menu.addSeparator() # Add a separator to the menu

        preferences_action = QAction("Preferences", self)
        preferences_action.triggered.connect(self.showPreferencesDialog)
        icescopy_menu.addAction(preferences_action)

        file_menu = menubar.addMenu("File")
        edit_menu = menubar.addMenu("Edit")

        analysis_menu = menubar.addMenu("Analysis")
        freeze_finder_action = QAction("Convolution freeze finder script", self)
        freeze_finder_action.triggered.connect(self.open_FreezeFinderDialog)
        analysis_menu.addAction(freeze_finder_action)

        # Main Layout
        main_layout = QVBoxLayout()

        # Create actions with icons
        self.load_folder_action = QAction("Load from Folder", self)
        self.load_image_action = QAction("Load Images", self)
        self.save_csv_action = QAction("Save Grayscale Data", self)
        self.undo_action = QAction("Undo", self)
        self.redo_action = QAction("Redo", self)
        self.reset_cursor_action = QAction("Cursor Tool (A)", self)
        self.select_tool_action = QAction("Add Selection (S)", self)
        self.edit_tool_action = QAction("Edit Selection (E)", self)
        self.deselect_tool_action = QAction("Delete Selection (D)", self)
        self.pan_tool_action = QAction("Pan and Zoom (Z)", self) 

        file_menu.addAction(self.load_image_action)
        file_menu.addAction(self.load_folder_action)
        file_menu.addSeparator() # Add a separator to the menu
        file_menu.addAction(self.save_csv_action)

        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator() # Add a separator to the menu
        edit_menu.addAction(self.reset_cursor_action)
        edit_menu.addAction(self.pan_tool_action)
        edit_menu.addSeparator() # Add a separator to the menu
        edit_menu.addAction(self.select_tool_action)
        edit_menu.addAction(self.edit_tool_action)
        edit_menu.addAction(self.deselect_tool_action)
        


        if platform.system() == "Darwin":  # macOS
            self.undo_action.setToolTip("Undo (Cmd+Z)")
            self.redo_action.setToolTip("Redo (Shift+Cmd+Z)")
        else:  # Windows and others
            self.undo_action.setToolTip("Undo (Ctrl+Z)")
            self.redo_action.setToolTip("Redo (Shift+Cmd+Z)")

        self.load_folder_action.triggered.connect(self.loadFolder)
        self.load_image_action.triggered.connect(self.loadImages)
        self.save_csv_action.triggered.connect(self.outputData)
        self.undo_action.triggered.connect(self.undo)
        self.redo_action.triggered.connect(self.redo)
        self.reset_cursor_action.triggered.connect(self.reset_cursor_tool)
        self.reset_cursor_action.setCheckable(True)
        self.select_tool_action.triggered.connect(self.selectTool)
        self.select_tool_action.setCheckable(True)
        self.edit_tool_action.triggered.connect(self.editTool)
        self.edit_tool_action.setCheckable(True)
        self.deselect_tool_action.triggered.connect(self.deselectTool)
        self.deselect_tool_action.setCheckable(True)
        self.pan_tool_action.triggered.connect(self.panTool)
        self.pan_tool_action.setCheckable(True)

        # disable tools before loading data
        self.select_tool_action.setEnabled(False)
        self.deselect_tool_action.setEnabled(False)
        self.edit_tool_action.setEnabled(False)
        self.pan_tool_action.setEnabled(False)

        # Initialize toolbar
        self.toolbar = self.addToolBar("Tools")

        # Add actions to toolbar
        self.toolbar.addAction(self.load_image_action)
        self.toolbar.addAction(self.load_folder_action)
        self.toolbar.addAction(self.save_csv_action)
        self.toolbar.addSeparator()  # Add a separator between groups of actions
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)
        self.toolbar.addAction(self.reset_cursor_action)
        self.toolbar.addAction(self.pan_tool_action)
        self.toolbar.addAction(self.select_tool_action)
        self.toolbar.addAction(self.deselect_tool_action)
        self.toolbar.addAction(self.edit_tool_action)

        self.tool_name_dict = {"pan":self.pan_tool_action, 
                               "cursor":self.reset_cursor_action, 
                               "select":self.select_tool_action,
                               "deselect":self.deselect_tool_action, 
                               "edit-choose":self.edit_tool_action, 
                               "edit-new":self.edit_tool_action, 
                               "edit-done":self.edit_tool_action}
        
        self.toolbar.setIconSize(QSize(32, 32))

        # Slider for navigating through images
        self.image_slider = FrameSlider(Qt.Horizontal, self)
        self.image_slider.valueChanged.connect(self.updateImage)
        self.image_slider.keyframeClicked.connect(self.update_keyframe_list)
        self.image_slider.flagframeClicked.connect(self.update_flaggedframe_list)
        
        # Text box to display slider value
        self.image_textbox = QLineEdit()
        self.image_textbox.returnPressed.connect(self.updateImageFromTextbox)

        view_slider_layout = QVBoxLayout()
        view_slider_layout.setContentsMargins(0, 0, 0, 0)

        # Button for slider manipulating and keyframe editing
        # Create the buttons
        self.leftButton = QPushButton()
        self.rightButton = QPushButton()
        self.keyframe_toggle_button = QPushButton()
        self.flag_toggle_button = QPushButton()

        self.leftButton.clicked.connect(self.decreaseSliderValue)
        self.rightButton.clicked.connect(self.increaseSliderValue)
        self.keyframe_toggle_button.clicked.connect(self.image_slider.toggle_keyframe)
        self.flag_toggle_button.clicked.connect(self.image_slider.toggle_flagging)

        # Zoom slider for changing the granularity of the image_slider
        self.zoom_slider = SliderZoom_Slider(Qt.Horizontal, self)
        self.zoom_slider.valueChanged.connect(self.image_slider.update_zoomed_level)

        slider_buttons_layout = QHBoxLayout()
        slider_buttons_layout.addStretch(1)
        slider_buttons_layout.addWidget(self.keyframe_toggle_button)
        slider_buttons_layout.addWidget(self.flag_toggle_button)
        slider_buttons_layout.addWidget(self.zoom_slider)
        slider_buttons_layout.addWidget(self.leftButton)
        slider_buttons_layout.addWidget(self.rightButton)
        slider_buttons_layout.addStretch(1)
        slider_buttons_layout.setContentsMargins(0, 0, 0, 3)

        slider_buttons_widget = QWidget()
        slider_buttons_widget.setLayout(slider_buttons_layout)

        # Create a QHBoxLayout for image slider and text box
        image_navigation_layout = QVBoxLayout()
        image_navigation_layout.addWidget(self.image_slider)

        # CustomGraphicsView and QGraphicsScene for image display
        self.scene = QGraphicsScene(self)
        self.view = CustomGraphicsView(self.scene, self)
        
        view_slider_layout.addWidget(self.view)
        view_slider_layout.addWidget(slider_buttons_widget)
        view_slider_layout.addLayout(image_navigation_layout)
        view_slider_layout.setSpacing(0)
        view_slider_layout.setContentsMargins(0, 0, 0, 0)

        # Create a splitter for graphics view and terminal
        splitter = QSplitter(Qt.Vertical)

        # Create a QWidget to hold the layout
        view_slider_widget = QWidget()
        view_slider_widget.setLayout(view_slider_layout)
        
        # Add the QWidget to the splitter
        splitter.addWidget(view_slider_widget)

        # Terminal-style status display
        self.terminal = QTextEdit(self)
        self.terminal.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.terminal.setReadOnly(True)
        splitter.addWidget(self.terminal)

        splitter.setSizes([7 * splitter.size().height() // 10, 3 * splitter.size().height() // 10])

        main_layout.addWidget(splitter)

        # Create a QHBoxLayout for circle radius and zoom level
        self.statusBar = QStatusBar()

        # Create labels and text boxes
        radius_label = QLabel("Circle Radius:")
        zoom_label = QLabel("Zoom Level:")
        slider_label = QLabel("Frame Number:")

        self.radius_textbox = QLineEdit() # Status text box showing the radius of the circle size for add circle
        self.zoom_textbox = QLineEdit()   # Level of magnifying for the image
        self.radius_textbox.returnPressed.connect(self.updateCircleRadius_from_textedit)
        self.zoom_textbox.returnPressed.connect(self.updateZoomLevel)

        # Set maximum width for the text boxes
        self.radius_textbox.setFixedWidth(60)
        self.zoom_textbox.setFixedWidth(60)

        # Set image label
        self.image_name_label = QLabel('', self)

        self.tool_status_label = QLabel('', self)

        # Add widgets to the control layout
        self.statusBar.addWidget(radius_label)
        self.statusBar.addWidget(self.radius_textbox)
        self.statusBar.addWidget(zoom_label)
        self.statusBar.addWidget(self.zoom_textbox)
        self.statusBar.addWidget(slider_label)
        self.statusBar.addWidget(self.image_textbox)
        self.statusBar.addWidget(self.image_name_label)
        self.statusBar.addWidget(self.tool_status_label)

        # Set the status bar
        self.setStatusBar(self.statusBar)

        self.setFocusPolicy(Qt.StrongFocus)  # Enable keyboard focus for the main window
        
        # The central_widget in a QMainWindow-based application serves as the primary area on which both fixed and dynamic (resizable) widgets are displayed
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Default initializations
        self.reset_cursor_action.trigger()  # force reset the cursor
        self.resize_image_textbox() # set default size for the frame number textbox. Will get called when updating frames (changing slider value)
        self.reset_status_bar_stylesheet()
        self.updateRadiusTextbox()
        self.updateZoomTextbox()
        self.reset_toolbar_icon()
        self.reset_toolbar_stylesheet()
        self.reset_slider_stylesheet()
        self.reset_button_icon()
        self.reset_button_stylesheet()
        self.set_redo_status()
        self.set_undo_status()
        self.updateButtonStates()

        self.log("Initialized. Waiting for input...") # Initialize message in log terminal
        

    ##### END initUI() #####

    def update_keyframe_list(self, is_adding):
        # function is called when toggling the keyframe button, connected to the keyframe clicked signal
        # grab the current keyframes from image_slider
        self.keyframe_list = list(sorted(self.image_slider.keyframes))
        # add the current frame (the newly added keyframe)

        if is_adding: 
            # adding keyframe
            self.keyframe_selection_items_dict[self.image_index] = copy.deepcopy(self.selection_items)
        else: 
            # deleting keyframe
            self.keyframe_selection_items_dict.pop(self.image_index)

    
    def update_flaggedframe_list(self, is_flagging):
        self.flagframe_list = list(sorted(self.image_slider.flaggedframes))
            
    
    def edit_current_keyframe_selection_item(self):
        # this function will be called if edits are made to the current selection_items
        # if the current frame is a key frame, update the selection_items of that key frame in keyframe_selection_items_dict
        # otherwise do nothing

        # the interlopation function will take care of the case when there is no keyframe at all

        if self.keyframe_list: # if any keyframe exist
            if self.image_index in self.keyframe_list:
                self.keyframe_selection_items_dict[self.image_index] = copy.deepcopy(self.selection_items)
                self.log('Edit registered for this keyframe')
            else:
                self.log('Edit unregistered for non-keyframe')


    def add_selection_item_to_keyframes(self):
        # will work for everyframe. No need to be on a key frame to add
        # called when adding a selection-item which will be at the last position of the selection_items list
        # for each keyframe, the same selection item will be added

        if self.keyframe_list: # if any keyframe exist
            for a_keyframe in self.keyframe_list:
                if  a_keyframe != self.image_index:
                    self.keyframe_selection_items_dict[a_keyframe].append(self.selection_items[-1])
                else:
                    self.keyframe_selection_items_dict[a_keyframe] = copy.deepcopy(self.selection_items)

    def delete_selection_item_to_keyframes(self, selection_number):
        # will work for everyframe. No need to be on a key frame to delete
        # called when deleting a selection item from the currnt selection_items
        # Could be any position so need to pass in
        
        if self.keyframe_list: # if any keyframe exist
            for a_keyframe in self.keyframe_list:
                if  a_keyframe != self.image_index:
                    self.keyframe_selection_items_dict[a_keyframe].pop(selection_number)
                else:
                    self.keyframe_selection_items_dict[a_keyframe] = copy.deepcopy(self.selection_items)

    def keyframe_interpolation(self, frame_number):
        # return the selection_items list of a frame interplated

        # check if the frame_number is already a keyframe, if true then just return the selection_items of that frame
        if frame_number in self.keyframe_list:
            return copy.deepcopy(self.keyframe_selection_items_dict[frame_number])
        else:
            keyframe_array = np.array(self.keyframe_list)

            if np.any(keyframe_array<frame_number) and np.any(keyframe_array>frame_number):
                # check if the frame_number passed in is between two keyframes
                previous_kf_index = np.max(keyframe_array[keyframe_array<frame_number])
                next_kf_index     = np.min(keyframe_array[keyframe_array>frame_number])

                interped_item_lists = []

                # (x-x1)/(x2-x1)
                ratio = (frame_number-previous_kf_index)/(next_kf_index-previous_kf_index)

                for i in range(len(self.keyframe_selection_items_dict[previous_kf_index])):
                    previous_item = self.keyframe_selection_items_dict[previous_kf_index][i]
                    next_item     = self.keyframe_selection_items_dict[next_kf_index][i]

                    # (x-x1)/(x2-x1) * (y2-y1) + y1
                    interp_circle_position_x = ratio * (next_item.circle_positions[0]       -previous_item.circle_positions[0])      + previous_item.circle_positions[0]
                    interp_circle_position_y = ratio * (next_item.circle_positions[1]       -previous_item.circle_positions[1])      + previous_item.circle_positions[1]
                    interp_circle_sizes      = ratio * (next_item.circle_sizes              -previous_item.circle_sizes)             + previous_item.circle_sizes
                    interp_pixel_position_x  = ratio * (next_item.circle_pixel_positions[0] -previous_item.circle_pixel_positions[0])+ previous_item.circle_pixel_positions[0]
                    interp_pixel_position_y  = ratio * (next_item.circle_pixel_positions[1] -previous_item.circle_pixel_positions[1])+ previous_item.circle_pixel_positions[1]
                    interp_selection_number  = i

                    interp_pixel_position_x = int(interp_pixel_position_x) # rounding
                    interp_pixel_position_y = int(interp_pixel_position_y)

                    interp_circle_positions = (interp_circle_position_x, interp_circle_position_y)
                    interp_circle_pixel_positions = (interp_pixel_position_x, interp_pixel_position_y)

                    interp_item = Selection_circle(self, interp_circle_positions, interp_circle_sizes, interp_circle_pixel_positions, interp_selection_number)
                    interped_item_lists.append(interp_item)

                return interped_item_lists
            
            elif np.any(keyframe_array<frame_number) or np.any(keyframe_array>frame_number):
                # left is 0 or right is the right end. then use the closest kf values
                closest_kf = min(keyframe_array, key=lambda x: abs(x - frame_number))
                return copy.deepcopy(self.keyframe_selection_items_dict[closest_kf])
            
            else: # no kf at all, just use the selection_items
                return copy.deepcopy(self.selection_items)
                

    def showAboutDialog(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec()

    def showPreferencesDialog(self):
        dlg = PreferencesDialog(self)
        dlg.exec()

    def updateSelectCursor(self):
        # DRAW THE CIRCLE CURSOR
        if self.circle_radius is None:
            self.circle_radius = self.default_circle_radius
            self.updateRadiusTextbox()

        scale_factor = self.view.transform().m11()  # Current zoom level
        effective_radius = self.circle_radius * scale_factor
        offset = 2  # Size offset to prevent clipping
        pixmap_size = max(2 * effective_radius, 2 * self.dot_size) + offset  # Adjusted pixmap size to prevent clipping

        cursor_pixmap = QPixmap(pixmap_size, pixmap_size)
        cursor_pixmap.fill(Qt.transparent)
        painter = QPainter(cursor_pixmap)
        pen = QPen(Qt.red)
        painter.setPen(pen)

        # Draw the circle at the center of the pixmap with adjusted dimensions
        painter.drawEllipse(offset // 2, offset // 2, pixmap_size - offset, pixmap_size - offset)

        # Calculate the new center coordinates
        center_x = pixmap_size // 2
        center_y = pixmap_size // 2

        # Draw the center dot
        painter.setBrush(Qt.red)
        painter.drawEllipse(center_x - self.dot_size // 2, center_y - self.dot_size // 2, self.dot_size, self.dot_size)

        painter.end()
        cursor = QCursor(cursor_pixmap, center_x, center_y)
        self.circle_cursor = cursor
        self.view.setCursor(cursor)

    def zoom_slider_set_maximum(self):
        #set max zoom value so at max zoom each step is about 10 pixel
        original_range = len(self.imagePaths)
        maximum_zoom_value = int(original_range * self.slider_maxzoom_pixel_interval / self.image_slider.width())
        if maximum_zoom_value <= 1:
            maximum_zoom_value = 2
        self.zoom_slider.setMaximum(maximum_zoom_value)

    def log(self, message):
        # Function to append messages to the terminal
        self.terminal.append(f"> {message}")

    def set_tools_highlight(self, tool_mode):
        for key, value in self.tool_name_dict.items():
            if key == tool_mode:
                value.setChecked(True)
            else:
                if (tool_mode in ["edit-choose", "edit-new", "edit-done"]) and (key in ["edit-choose", "edit-new", "edit-done"]):
                    value.setChecked(True)
                else:
                    value.setChecked(False)
     

    def reset_cursor_tool(self, checked):
        self.tool_mode = "cursor"
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.view.setCursor(Qt.ArrowCursor)
        self.reset_selection_items_edit_chosen()
        self.set_tools_highlight(self.tool_mode)
        self.update_selection_items_selectable_state()
        self.tool_status_label.setText('Default Cursor')

    def panTool(self, checked):
        self.tool_mode = 'pan'
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)  # Enable panning in pan mode
        self.view.setCursor(Qt.OpenHandCursor)
        self.set_tools_highlight(self.tool_mode)
        self.update_selection_items_selectable_state()
        self.tool_status_label.setText('Zoom and Pan')

    def selectTool(self, checked):
        self.tool_mode = 'select'
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.updateSelectCursor()
        self.set_tools_highlight(self.tool_mode)
        self.reset_selection_items_edit_chosen()
        self.update_selection_items_selectable_state()
        self.unselect_all_selection_items()
        self.tool_status_label.setText('Add Selection')
    
    def editTool(self, checked):
        self.view.setDragMode(QGraphicsView.NoDrag)
        if "previous_edit_mode" in self.temporary_event_data:
            edit_mode = self.temporary_event_data["previous_edit_mode"]
            self.temporary_event_data.pop("previous_edit_mode")
        else:
            edit_mode = 'edit-choose'

        if edit_mode == 'edit-choose':
            self.tool_mode = 'edit-choose'
            self.view.setCursor(Qt.PointingHandCursor)
        else:
            self.tool_mode = 'edit-new'
            self.updateSelectCursor()
        self.set_tools_highlight(self.tool_mode)
        self.update_selection_items_selectable_state()
        self.unselect_all_selection_items()
        self.tool_status_label.setText('Edit Selection')
    
    def deselectTool(self, checked):
        self.tool_mode = 'deselect'
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.view.setCursor(Qt.PointingHandCursor)
        self.set_tools_highlight(self.tool_mode)
        self.reset_selection_items_edit_chosen()
        self.update_selection_items_selectable_state()
        self.unselect_all_selection_items()
        self.tool_status_label.setText('Delete Selection')

    
    def loadFolder(self):
        input_dirpath = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if input_dirpath:
            # Define a list of common image extensions
            image_extensions = ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"]
            # Initialize an empty list to store image files
            input_imagePath = []
            # Loop through each image extension and find matching files
            for root, dirs, files in os.walk(input_dirpath):
                for file in files:
                    # If the file extension (case-insensitive) is in the list of image extensions, add it to the list
                    if file.split('.')[-1].lower() in image_extensions:
                        input_imagePath.append(os.path.join(root, file))
            # Sort the image files by their creation time
            #input_imagePath.sort(key=lambda x: os.path.getctime(x))
            input_imagePath.sort()

            self.load_aux(input_imagePath)
        else:
            self.load_aux([])
        

    def loadImages(self):
        input_imagePath, _ = QFileDialog.getOpenFileNames(self, "Open Image(s)", "", "Image Files (*.png *.jpg *.jpeg);;All Files (*)")
        if input_imagePath:
            self.load_aux(input_imagePath)
        else:
            self.load_aux([])

    def load_aux(self, input_imagePath):
        if input_imagePath: # check if the list is empty
            
            self.initData()
            self.imagePaths    = input_imagePath
            self.imageNames    = [os.path.basename(path) for path in self.imagePaths]
            if self.imagePaths:
                self.log(f"Loaded {len(self.imagePaths)} images")

                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(len(self.imagePaths) - 1)
                self.image_slider.setValue(0)  # Display the first image
                self.image_textbox.setText("0")
                
                # Clear previous pixmap_item (if any) before creating a new one
                if hasattr(self, 'pixmap_item'):
                    self.scene.removeItem(self.pixmap_item)
                    del(self.pixmap_item)

                self.updateImage(0)
                # Enable/Disable Status
                self.select_tool_action.setEnabled(True)
                self.pan_tool_action.setEnabled(True)
                self.image_slider.setEnabled(True)
                self.deselect_tool_action.setEnabled(True)
                self.edit_tool_action.setEnabled(True)
                self.updateButtonStates()
                self.set_redo_status()
                self.set_undo_status()
                self.image_slider.set_custom_ticks()
                self.zoom_slider_set_maximum()
        else:
            self.log(f"No image loaded")

            #tool_mode

    def updateImage(self, index):
            # Update displayed image and the red circles (selection region). 
            # This function is called when 1. Successfully loading new images 2. Image Selection slider value is changed (also when Image number is changed, or left and right advanced buttons are pressed)
            # The selection region is updated by the self.displayMarkedRegions() function  
            if self.imagePaths:
                # Save the current view transformation
                current_transform = self.view.transform()
                current_hscroll = self.view.horizontalScrollBar().value()
                current_vscroll = self.view.verticalScrollBar().value()

                self.image_index = index
                self.image_textbox.setText(str(index))
                q_image = QImage(self.imagePaths[index])
                if hasattr(self, 'pixmap_item'):
                    self.pixmap_item.setPixmap(QPixmap.fromImage(q_image))
                else:
                    self.pixmap_item = self.scene.addPixmap(QPixmap.fromImage(q_image))
                
                self.view.setSceneRect(self.pixmap_item.pixmap().rect())
                self.view.fitInView(self.pixmap_item.pixmap().rect(), Qt.KeepAspectRatio)

                # Restore the saved view transformation
                self.view.setTransform(current_transform)
                self.view.horizontalScrollBar().setValue(current_hscroll)
                self.view.verticalScrollBar().setValue(current_vscroll)

                self.image_width = q_image.width()
                self.interpolate_and_displayMarkedRegions(index)
                self.image_name_label.setText(self.imageNames[index])
                self.resize_image_textbox()
                self.updateButtonStates()
                self.update_toggle_keyframe_button_icon()
                self.update_toggle_flagging_button_icon()

                
                    
    def decreaseSliderValue(self):
        current_value = self.image_slider.value()
        if current_value > self.image_slider.minimum():
            self.image_slider.setValue(current_value - 1)

            self.delete_nonkf_changes_history()
            self.addToHistory(VIEW_NEW_IMAGE)

        elif current_value > 0:
            self.image_slider.setMinimum(self.image_slider.minimum()-1)
            self.image_slider.setMaximum(self.image_slider.maximum()-1)
            self.image_slider.setValue(current_value - 1)

            self.delete_nonkf_changes_history()
            self.addToHistory(VIEW_NEW_IMAGE)

    def increaseSliderValue(self):
        current_value = self.image_slider.value()
        if current_value < self.image_slider.maximum():
            self.image_slider.setValue(current_value + 1)

            self.delete_nonkf_changes_history()
            self.addToHistory(VIEW_NEW_IMAGE)
        
        elif current_value < (len(self.imagePaths)-1):
            self.image_slider.setMinimum(self.image_slider.minimum()+1)
            self.image_slider.setMaximum(self.image_slider.maximum()+1)
            self.image_slider.setValue(current_value + 1)
        
            self.delete_nonkf_changes_history()
            self.addToHistory(VIEW_NEW_IMAGE)
            
    def updateImageFromTextbox(self):
        # Update displayed image based on textbox value by changing the slider value
        try:
            index = int(self.image_textbox.text())
            index = max(0, min(index, len(self.imagePaths) - 1))  # Ensure valid index
            self.image_slider.setValue(index)
        except ValueError:
            pass  # Ignore non-integer input
    
    def resize_image_textbox(self):
        font_metrics = self.image_textbox.fontMetrics()
        text_width = font_metrics.horizontalAdvance(self.image_textbox.text())
        padding = 20  # extra padding
        new_width = text_width + padding
        self.image_textbox.setFixedWidth(new_width)

    def displayMarkedRegions(self):
        # draw circles when adding/deleting/editing in same frame
        # Clear previous circles
        for item in self.scene.items():
            if isinstance(item, Selection_circle):
                self.scene.removeItem(item)

        self.update_selection_items_selection_number()

        for item in self.selection_items:
            self.scene.addItem(item)

        print('update MarkedRegions')

    def interpolate_and_displayMarkedRegions(self, index):
        # interpolate for the new frame when sliding image_slider
        # also update the self.selection_items
        # Clear previous circles
        for item in self.scene.items():
            if isinstance(item, Selection_circle):
                self.scene.removeItem(item)

        self.selection_items = self.keyframe_interpolation(index)
        self.update_selection_items_selection_number()

        for item in self.selection_items:
            self.scene.addItem(item)

    def updateRadiusTextbox(self):
        if self.circle_radius is not None:
            self.radius_textbox.setText(str(self.circle_radius))
        else:
            self.radius_textbox.clear()  # Clear the text box if circle radius is None

    def updateCircleRadius_from_textedit(self):
        try:
            radius = int(self.radius_textbox.text())
            if radius != self.circle_radius:
                self.circle_radius = radius
                if self.tool_mode == 'select':
                    self.updateSelectCursor()
        except ValueError:
            pass  # Ignore non-integer input


    def updateZoomTextbox(self):
        zoom_factor = self.view.transform().m11()  # Current zoom level
        self.zoom_textbox.setText(f"{zoom_factor * 100:.0f}")  # Update the zoom level text box

    def updateZoomLevel(self):
        try:
            zoom_percentage = float(self.zoom_textbox.text())
            zoom_factor = zoom_percentage / 100.0
            self.view.setTransform(QTransform().scale(zoom_factor, zoom_factor))
            self.updateZoomTextbox()  # Update the zoom text box after manual change
        except ValueError:
            pass  # Ignore non-numeric input
    
    def updateButtonStates(self):
        # Update left button state
        if (self.image_slider.value() <= 0) or self.output_state or (not self.imagePaths):
            self.leftButton.setEnabled(False)
        else:
            self.leftButton.setEnabled(True)

        # Update right button state
        if (self.image_slider.value() >= len(self.imagePaths)-1) or self.output_state or (not self.imagePaths):
            self.rightButton.setEnabled(False)
        else:
            self.rightButton.setEnabled(True)

        if self.output_state or (not self.imagePaths):
            self.keyframe_toggle_button.setEnabled(False)
            self.flag_toggle_button.setEnabled(False)
            self.zoom_slider.setEnabled(False)
        else:
            self.keyframe_toggle_button.setEnabled(True)
            self.flag_toggle_button.setEnabled(True)
            self.zoom_slider.setEnabled(True)

    def addToHistory(self, command_type):
        # Save the current state to history
        a_history = {}
        a_history['command_type']                   = command_type
        a_history['selection_items']                = copy.deepcopy(self.selection_items)
        a_history['keyframe_list']                  = self.keyframe_list.copy()
        a_history['keyframe_selection_items_dict']  = copy.deepcopy(self.keyframe_selection_items_dict)
        a_history['image_index']                    = self.image_index
        a_history['flagframe_list']                 = self.flagframe_list.copy()

        self.history_index += 1

        if self.history_index < len(self.command_history_list):
            # Discard any "redo" history beyond the current state
            del self.command_history_list[self.history_index:]

        self.command_history_list.append(a_history)

        self.set_undo_status()
        self.set_redo_status()

    def set_undo_status(self):
        if (self.history_index >= 0) and (not (self.tool_mode in ["edit-new"])):
            self.undo_action.setEnabled(True)
        else:
            self.undo_action.setEnabled(False)

    def set_redo_status(self):
        if (self.history_index < len(self.command_history_list)-1) and (not (self.tool_mode in ["edit-new"])):
            self.redo_action.setEnabled(True)
        else:
            self.redo_action.setEnabled(False)

    def delete_nonkf_changes_history(self):
        command_list = [a_history['command_type'] for a_history in self.command_history_list]

        def find_last_index(lst, number):
            for i in reversed(range(len(lst))):
                if lst[i] == number:
                    return i
            return None  # Return -1 if no zero is found

        # find last time a VIEW_NEW_IMAGE command is executed
        last_VIEW_NEW_IMAGE_index = find_last_index(command_list, 0)
        
        if last_VIEW_NEW_IMAGE_index and self.keyframe_list:
            # igore the keyframe requirement is there is no keyframe set at all.
            number_of_4_after_0 = command_list[last_VIEW_NEW_IMAGE_index+1:].count(TOGGLE_KEYFRAME)
            if number_of_4_after_0 % 2 == 0:
                # number of toggle is even
                # find last index of 4
                if command_list[last_VIEW_NEW_IMAGE_index+1:].count(EDIT_SELECTION)>0:
                    self.log('Selection Edits on a non-keyframes are not saved')
                    original_length = len(command_list)

                    mask = []
                    for a_command in command_list[last_VIEW_NEW_IMAGE_index+1:]:
                        if a_command in [EDIT_SELECTION]:
                            mask.append(False)
                        else:
                            mask.append(True)
                    
                    list_to_extend = np.array(self.command_history_list[last_VIEW_NEW_IMAGE_index+1:])[mask].tolist()
                    self.command_history_list = self.command_history_list[:last_VIEW_NEW_IMAGE_index+1]
                    self.command_history_list.extend(list_to_extend)
                    self.history_index = self.history_index - (original_length - len(self.command_history_list))

    def undo(self):
        # Implement the undo functionality

        if self.history_index >= 0:

            self.log("Undo")
            this_action = self.command_history_list[self.history_index]['command_type']
            # ^^^ Important, different action need to be choosed depending on how the latest 
            # frame is generated (depending on which action or command is performed.
            # Its easy to just display the previous state by doing similar action

            # Mostly use displayMarkedRegions() for any edits made on the same frame

            self.history_index -= 1

            if self.history_index == -1: # goes to default state
                # default state, no matter what command type
                self.selection_items = []
                self.keyframe_list   = []
                self.keyframe_selection_items_dict = {}
                self.image_index     = 0
                self.flagframe_list  = []
                
                self.image_slider.setValue(self.image_index)
                self.updateImage(self.image_index)
                self.image_slider.keyframes = set(self.keyframe_list)
                self.image_slider.update()
                self.update_toggle_keyframe_button_icon()

            else:
                a_history_entry = self.command_history_list[self.history_index]

                self.selection_items = copy.deepcopy(a_history_entry['selection_items'])
                self.keyframe_list   = a_history_entry['keyframe_list'].copy()
                self.keyframe_selection_items_dict = copy.deepcopy(a_history_entry['keyframe_selection_items_dict'])
                self.image_index     = a_history_entry['image_index']
                self.flagframe_list  = a_history_entry['flagframe_list'].copy()
                
                if this_action in [VIEW_NEW_IMAGE]:
                    self.image_slider.setValue(self.image_index)
                    self.image_slider.update()
                    self.updateImage(self.image_index)

                elif this_action in [ADD_SELECTION, DELETE_SELECTION, EDIT_SELECTION]:
                    self.displayMarkedRegions()

                elif this_action in [TOGGLE_KEYFRAME]:
                    self.image_slider.keyframes = set(self.keyframe_list)
                    self.image_slider.update()
                    self.update_toggle_keyframe_button_icon()
                
                elif this_action in [TOGGLE_FLAGFRAME]:
                    self.image_slider.flaggedframes = set(self.flagframe_list)
                    self.image_slider.update()
                    self.update_toggle_flagging_button_icon()

            self.set_undo_status()
            self.set_redo_status()

    def redo(self):
        # Implement the redo functionality
        if self.history_index < len(self.command_history_list)-1:
            self.log("Redo")

            self.history_index += 1

            a_history_entry = self.command_history_list[self.history_index]
            self.selection_items = copy.deepcopy(a_history_entry['selection_items'])
            self.keyframe_list   = a_history_entry['keyframe_list'].copy()
            self.keyframe_selection_items_dict = copy.deepcopy(a_history_entry['keyframe_selection_items_dict'])
            self.image_index     = a_history_entry['image_index']
            self.flagframe_list  = a_history_entry['flagframe_list'].copy()
            
            this_action = self.command_history_list[self.history_index]['command_type']

            if this_action in [VIEW_NEW_IMAGE]:
                self.image_slider.setValue(self.image_index)
                self.image_slider.update()
                self.updateImage(self.image_index)

            elif this_action in [ADD_SELECTION, DELETE_SELECTION, EDIT_SELECTION]:
                self.displayMarkedRegions()

            elif this_action in [TOGGLE_KEYFRAME]:
                self.image_slider.keyframes = set(self.keyframe_list)
                self.image_slider.update()
                self.update_toggle_keyframe_button_icon()

            elif this_action in [TOGGLE_FLAGFRAME]:
                self.image_slider.flaggedframes = set(self.flagframe_list)
                self.image_slider.update()
                self.update_toggle_flagging_button_icon()

            self.set_undo_status()
            self.set_redo_status()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Z:
            if (event.modifiers() & Qt.ControlModifier) and (event.modifiers() & Qt.ShiftModifier):
                if self.redo_action.isEnabled():
                    self.redo_action.trigger()  # Shift + Ctrl + Z for redo
                    self.key_press_toolbutton_highlight(self.redo_action) # simulate pressing button highlight for visual cue
            elif (event.modifiers() & Qt.ControlModifier):
                if self.undo_action.isEnabled():
                    self.undo_action.trigger()  # Ctrl + Z for undo
                    self.key_press_toolbutton_highlight(self.undo_action) # simulate pressing button highlight for visual cue
            else:
                if self.pan_tool_action.isEnabled():
                    self.pan_tool_action.trigger()  # Z for Zoom and Pan
                    self.key_press_toolbutton_highlight(self.pan_tool_action)
        elif event.key() == Qt.Key_S:
            # Select Add selection Key
            if self.select_tool_action.isEnabled():
                self.select_tool_action.trigger() # S for Add Selection
                self.key_press_toolbutton_highlight(self.select_tool_action)
        elif event.key() == Qt.Key_D:
            # Select Add selection Key
            if self.deselect_tool_action.isEnabled():
                self.deselect_tool_action.trigger() # D for Delete Selection
                self.key_press_toolbutton_highlight(self.deselect_tool_action)
        elif event.key() == Qt.Key_E:
            # Select Add selection Key
            if self.edit_tool_action.isEnabled():
                self.edit_tool_action.trigger() # E for Delete Selection
                self.key_press_toolbutton_highlight(self.edit_tool_action)
        elif event.key() == Qt.Key_A:
            # Select Default Cursor Key
            if self.reset_cursor_action.isEnabled():
                self.reset_cursor_action.trigger() # A for Delete Selection
                self.key_press_toolbutton_highlight(self.reset_cursor_action)
        elif event.key() == Qt.Key_Comma:
            if self.leftButton.isEnabled():
                self.leftButton.click()
                self.key_press_button_highlight(self.leftButton)
        elif event.key() == Qt.Key_Period:
            if self.rightButton.isEnabled():
                self.rightButton.click()
                self.key_press_button_highlight(self.rightButton)

        elif (event.key() == Qt.Key_Space) and (self.space_held == False):
            # Temporarily switch to zoom and pan

            if self.imagePaths:
                # Store original_tool_mode in temporary data
                self.temporary_event_data["original_tool_mode"] = self.tool_mode

                for key, value in self.tool_name_dict.items():
                    if key in ['pan', self.tool_mode]:
                        value.setEnabled(True)
                    elif (self.tool_mode in ["edit-choose", "edit-new", "edit-done"]) and (key in ["edit-choose", "edit-new", "edit-done"]):
                        value.setEnabled(True)
                    else:
                        value.setEnabled(False)

                if self.pan_tool_action.isEnabled():
                    self.pan_tool_action.trigger()  # Z for Zoom and Pan
                    self.key_press_toolbutton_highlight(self.pan_tool_action)

                self.space_held = True

        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:

            if self.imagePaths:
                # Retrieve the original tool mode from the temporary data dict
                self.space_held = False

                original_tool_mode =  self.temporary_event_data["original_tool_mode"]
                self.temporary_event_data.pop("original_tool_mode")

                if original_tool_mode == "pan":
                    self.pan_tool_action.trigger()
                    self.key_press_toolbutton_highlight(self.pan_tool_action)
                elif original_tool_mode == "cursor":
                    self.reset_cursor_action.trigger()
                    self.key_press_toolbutton_highlight(self.reset_cursor_action)
                elif original_tool_mode == "select":
                    self.select_tool_action.trigger()
                    self.key_press_toolbutton_highlight(self.select_tool_action)
                elif original_tool_mode == "deselect":
                    self.deselect_tool_action.trigger()
                    self.key_press_toolbutton_highlight(self.deselect_tool_action)
                elif original_tool_mode in ["edit-choose", "edit-new", "edit-done"]:
                    self.temporary_event_data["previous_edit_mode"] = original_tool_mode
                    self.editTool(self.edit_tool_action.isChecked())
                    self.key_press_toolbutton_highlight(self.edit_tool_action)
                    

                for key, value in self.tool_name_dict.items():
                    value.setEnabled(True)

        else:
            super().keyReleaseEvent(event)

    def outputData(self):
        filePath, _ = QFileDialog.getSaveFileName(self, "Save CSV File", "", "CSV Files (*.csv);;All Files (*)")
        if filePath:
            self.log("Start analyzing...")

            # circle_pixel_positions = [circle.circle_pixel_positions for circle in self.selection_items]
            # circle_sizes = [circle.circle_sizes for circle in self.selection_items]
            list_of_selection_items = self.out_put_interpolation()

            self.worker = Image_analysis_thread(filePath, self.imagePaths.copy(), self.imageNames.copy(), list_of_selection_items, self.flagframe_list)
            self.worker.analysis_done.connect(self.onAnalysisDone)
            self.updateButtonStates()
            self.zoom_slider.setValue(1)
            
            self.reset_cursor_action.trigger()
            self.select_tool_action.setEnabled(False)
            self.deselect_tool_action.setEnabled(False)
            self.edit_tool_action.setEnabled(False)

            self.image_slider.setEnabled(False)
            self.image_slider.setValue(0)
            self.timer = time.time()
            self.output_state = True
            self.worker.start() #When you call start() on a QThread object, it internally calls the run() method of that object in a new thread
            # the finished signal of QThread doesn't support additional arguments, use Python's closure or functools.partial to create a new function that encapsulates the arguments you want to pass
            self.worker.finished.connect(partial(self.onThreadFinished, filePath)) 

    def out_put_interpolation(self):
        list_of_selection_items = []
        for an_image_index in range(len(self.imagePaths)):
            list_of_selection_items.append(self.keyframe_interpolation(an_image_index))
        
        return list_of_selection_items
            
    def onAnalysisDone(self, index, results):
        # Finish anayzing each image
        # self.log(f"Analyzed image {results['file_name']}")
        self.image_slider.setValue(self.image_slider.value() + 1)
        

    def onThreadFinished(self, filePath):
        # Finish anayzing all images
        endTime = time.time()
        elapsed_time = endTime - self.timer
        self.log(f"Saved output at {filePath}")
        self.log(f"Time used: {elapsed_time:.3f} seconds")
        self.timer = None
        self.output_state = False
        self.image_slider.setEnabled(True)
        self.updateButtonStates()
        self.select_tool_action.setEnabled(True)
        self.deselect_tool_action.setEnabled(True)
        self.edit_tool_action.setEnabled(True)


    def key_press_toolbutton_highlight(self, an_action):
        toolbutton = self.toolbar.widgetForAction(an_action)
        if toolbutton:
            # Set a unique object name for styling
            toolbutton.setObjectName("triggeredButton")
            current_stylesheet = self.toolbar.styleSheet()
            if darkdetect.isDark():
                style_sheet_to_add = "QToolButton#triggeredButton {background-color: rgba(10, 132, 255, 120)}"
            else:
                style_sheet_to_add = "QToolButton#triggeredButton {background-color: rgba(0, 122, 255, 200)}"
            self.toolbar.setStyleSheet(current_stylesheet + style_sheet_to_add)
            QTimer.singleShot(150, lambda: self.reset_toolbar_stylesheet())
    
    def key_press_button_highlight(self, button):
        if button:
            # Set a unique object name for styling
            button.setObjectName("triggeredButton")
            current_stylesheet = button.styleSheet()
            if darkdetect.isDark():
                style_sheet_to_add = "QPushButton#triggeredButton {background-color: rgba(10, 132, 255, 120)}"
            else:
                style_sheet_to_add = "QPushButton#triggeredButton {background-color: rgba(0, 122, 255, 200)}"
            button.setStyleSheet(current_stylesheet + style_sheet_to_add)
            QTimer.singleShot(150, lambda: self.reset_button_stylesheet())
            button.setObjectName(None)

    def reset_toolbar_stylesheet(self, theme=None):
        for action in self.toolbar.actions():
            button = self.toolbar.widgetForAction(action)
            button.setObjectName(None)
        if theme == "Dark" or darkdetect.isDark():
            self.toolbar.setStyleSheet(icescopy_stylesheet.darkmode_toolbar_style_sheet)
        else:
            self.toolbar.setStyleSheet(icescopy_stylesheet.light_mode_toolbar_style_sheet)
    
    def reset_slider_stylesheet(self, theme=None):
        if darkdetect.isDark():
            self.image_slider.setStyleSheet(icescopy_stylesheet.dark_mode_time_line_slider_style)
            self.zoom_slider.setStyleSheet(icescopy_stylesheet.dark_zoom_slider_stylesheet)
        else:
            self.image_slider.setStyleSheet(icescopy_stylesheet.light_mode_time_line_slider_style)
            self.zoom_slider.setStyleSheet(icescopy_stylesheet.light_zoom_slider_stylesheet)
    
    def reset_status_bar_stylesheet(self, theme=None):
        if darkdetect.isDark():
            self.statusBar.setStyleSheet(icescopy_stylesheet.dark_mode_status_bar_stylesheet)
            self.radius_textbox.setStyleSheet(icescopy_stylesheet.dark_mode_line_edit_style_sheet)
            self.zoom_textbox.setStyleSheet(icescopy_stylesheet.dark_mode_line_edit_style_sheet)
            self.image_textbox.setStyleSheet(icescopy_stylesheet.dark_mode_line_edit_style_sheet)
        else:
            self.statusBar.setStyleSheet(icescopy_stylesheet.light_mode_status_bar_stylesheet)
            self.radius_textbox.setStyleSheet(icescopy_stylesheet.light_mode_line_edit_style_sheet)
            self.zoom_textbox.setStyleSheet(icescopy_stylesheet.light_mode_line_edit_style_sheet)
            self.image_textbox.setStyleSheet(icescopy_stylesheet.light_mode_line_edit_style_sheet)
    
    def reset_button_stylesheet(self, theme=None):
        if darkdetect.isDark():
            self.keyframe_toggle_button.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.leftButton.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.rightButton.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.flag_toggle_button.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
        else:
            self.keyframe_toggle_button.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.leftButton.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.rightButton.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.flag_toggle_button.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)


    def reset_toolbar_icon(self, theme=None):
        if darkdetect.isDark():
            self.load_folder_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/image-multiple-folder.png")))
            self.load_image_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/image-multiple.png")))
            self.save_csv_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/save-as.png")))
            self.undo_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/command-undo.png")))
            self.redo_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/command-redo.png")))
            self.reset_cursor_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/pointer.png")))
            self.select_tool_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/add-selection.png")))
            self.edit_tool_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/edit-selection.png")))
            self.deselect_tool_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/delete-selection.png")))
            self.pan_tool_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/zoom_pan.png")))
        else:
            self.load_folder_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/image-multiple-folder_2.png")))
            self.load_image_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/image-multiple_2.png")))
            self.save_csv_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/save-as_2.png")))
            self.undo_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/command-undo_2.png")))
            self.redo_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/command-redo_2.png")))
            self.reset_cursor_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/pointer_2.png")))
            self.select_tool_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/add-selection_2.png")))
            self.edit_tool_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/edit-selection_2.png")))
            self.deselect_tool_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/delete-selection_2.png")))
            self.pan_tool_action.setIcon(QIcon(os.path.join(resources_dir,"tool_bar/png/24px/large/zoom_pan_2.png")))

    def update_toggle_keyframe_button_icon(self, theme=None):
        if darkdetect.isDark():
            if self.image_index in self.image_slider.keyframes:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(resources_dir,'diamond_key.png')))
            else:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(resources_dir,'diamond.png')))
        else:
            if self.image_index in self.image_slider.keyframes:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(resources_dir,'diamond_key_2.png')))
            else:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(resources_dir,'diamond_2.png')))
    
    def update_toggle_flagging_button_icon(self, theme=None):
        if darkdetect.isDark():
            if self.image_index in self.image_slider.flaggedframes:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(resources_dir,'flag_red.png')))
            else:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(resources_dir,'flag.png')))
        else:
            if self.image_index in self.image_slider.flaggedframes:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(resources_dir,'flag_red_2.png')))
            else:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(resources_dir,'flag_2.png')))

    def reset_button_icon(self, theme=None):
        self.update_toggle_keyframe_button_icon()
        self.update_toggle_flagging_button_icon()
        if darkdetect.isDark():
            self.leftButton.setIcon(QIcon(os.path.join(resources_dir,"caret-left.png")))
            self.rightButton.setIcon(QIcon(os.path.join(resources_dir,'caret-right.png')))
        else:
            self.leftButton.setIcon(QIcon(os.path.join(resources_dir,'caret-left_2.png')))
            self.rightButton.setIcon(QIcon(os.path.join(resources_dir,'caret-right_2.png')))

    def update_selection_items_selectable_state(self): # update items in the scenes, called when changing tools.
        for item in self.scene.items():
            if isinstance(item, Selection_circle):
                item.update_selectable_state()

    def unselect_all_selection_items(self):
        for item in self.scene.items(): # update items in the scenes, called when changing tools.
            if isinstance(item, Selection_circle):
                item.setSelected(False)
    
    def update_selection_items_selection_number(self): # update items in the data list, called by the self.displayMarkedRegions()
        for i, item in enumerate(self.selection_items):
            item.selection_number = i
    
    def reset_selection_items_edit_chosen(self): # update items in the data list, called by the self.displayMarkedRegions()
        for i, item in enumerate(self.selection_items):
            item.edit_chosen = False
            item.update()

    def switch_light_dark_mode(self, theme=None):
        self.reset_toolbar_stylesheet(theme)
        self.reset_toolbar_icon(theme)
        self.reset_slider_stylesheet(theme)
        self.reset_button_icon(theme)
        self.reset_status_bar_stylesheet(theme)
        self.reset_button_stylesheet(theme)

    def resizeEvent(self, event):
        super().resizeEvent(event)  # Call the base class resizeEvent
        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()

    def open_FreezeFinderDialog(self):
        dialog = FreezeFinderDialog()
        result = dialog.exec()

        if result == QDialog.Accepted:
            self.log(f'Freezing temperature data saved at {dialog.output_file_edit.text()}')
        else:
            self.log(f'Freezing temperature finding script cancelled')


    def load_preferences_from_xml(self):
        tree = ET.parse(os.path.join(resources_dir,"preferences.xml"))
        root = tree.getroot()
        
        preferences = {}

        circle_radius_element = root.find('DefaultCircleRadius')
        if circle_radius_element is not None and circle_radius_element.text is not None:
            preferences['DefaultCircleRadius'] = float(circle_radius_element.text)

        maximum_zoom_element = root.find('MaximumZoom')
        if maximum_zoom_element is not None and maximum_zoom_element.text is not None:
            preferences['MaximumZoom'] = float(maximum_zoom_element.text)
        
        pen_width_element = root.find('PenWidth')
        if pen_width_element is not None and pen_width_element.text is not None:
            preferences['PenWidth'] = float(pen_width_element.text)

        dot_size_element = root.find('DotSize')
        if dot_size_element is not None and dot_size_element.text is not None:
            preferences['DotSize'] = float(dot_size_element.text)

        slide_maxzoom_element = root.find('SliderMaxZoomPixelInterval')
        if slide_maxzoom_element is not None and slide_maxzoom_element.text is not None:
            preferences['SliderMaxZoomPixelInterval'] = float(slide_maxzoom_element.text)
        
        slide_tickpix_element = root.find('SliderTickPixelInterval')
        if slide_tickpix_element is not None and slide_tickpix_element.text is not None:
            preferences['SliderTickPixelInterval'] = float(slide_tickpix_element.text)
        
        return preferences

if __name__ == '__main__':
    app = QApplication([])
    app.setStyle('macos')
    window = IceScopy()
    window.show()
    
    app.exec()