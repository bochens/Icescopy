from PySide6.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QWidget,
    QLabel,
    QSizePolicy,
    QGraphicsView,
    QDialog,
    QLineEdit,
    QPushButton,
    QComboBox,
    QDialogButtonBox,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QFrame,
    QColorDialog,
    QScrollArea,
)
from PySide6.QtGui import QPainter, Qt, QTransform, QFont, QImage, QPixmap, QColor
from PySide6.QtCore import QRectF, QThread, Signal, QTimer
from xml.etree.ElementTree import Element, SubElement, ElementTree, parse
import numpy as np
import cv2
import darkdetect
import multiprocessing
import os


from icescopy_cell_items import CellCircle
from icescopy_freezfinder import (
    DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
    DEFAULT_CONVOLUTION_RAMP_POINTS,
    DEFAULT_FREEZE_FINDER_PROMINENCE,
    DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS,
    DEFAULT_FREEZE_FINDER_WIDTH,
    DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING,
    DEFAULT_FREEZE_RESULT_HEADERS,
    build_freeze_output_path,
    compute_freeze_result_rows,
    write_freeze_results_csv,
)
from icescopy_image_edit import (
    apply_affine_to_point,
    apply_image_adjustments_to_uint8,
    build_rotated_crop_affine,
    crop_state_is_identity,
)
from icescopy_session_io import SORT_MODE_LABELS

DEFAULT_VISUAL_COLORS = {
    "CircleDefaultColor": "255,0,0,255",
    "CircleHoverColor": "0,0,255,255",
    "CircleSelectedColor": "64,156,255,255",
    "CircleEditColor": "240,168,168,255",
    "CirclePressedColor": "255,255,0,255",
    "GridPreviewOutlineColor": "0,122,255,200",
    "GridPreviewFillColor": "0,122,255,25",
}

PLOT_PALETTE_LABELS = {
    "bright": "Bright",
    "okabe_ito": "Colorblind Safe",
    "muted": "Muted",
    "warm_cool": "Warm / Cool",
}

GRID_CELL_ID_DIRECTION_LABELS = {
    "left_to_right": "Left to Right",
    "top_to_bottom": "Top to Bottom",
}

DEFAULT_PREFERENCE_VALUES = {
    "DefaultCircleRadius": 22.0,
    "PenWidth": 1.0,
    "MaximumZoom": 10.0,
    "DotSize": 1.0,
    "SliderMaxZoomPixelInterval": 10.0,
    "SliderTickPixelInterval": 20.0,
    "UndoLimit": 20,
    "SampleNamePattern": "Sample_#",
    "ViewerImageCount": 1,
    "SortMode": "natural_filename",
    "GridRows": 4,
    "GridColumns": 4,
    "GridHorizontalPitch": 60.0,
    "GridVerticalPitch": 60.0,
    "GridRotationDegrees": 0.0,
    "GridCellIdDirection": "left_to_right",
    "RadiusWheelStep": 1.0,
    "GridPitchWheelStep": 1.0,
    "GridTiltWheelStep": 1.0,
    "FreezeFinderWidth": DEFAULT_FREEZE_FINDER_WIDTH,
    "FreezeFinderProminence": DEFAULT_FREEZE_FINDER_PROMINENCE,
    "FreezeFinderTailExtendPoints": DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS,
    "ConvolutionHalfWindowPoints": DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
    "ConvolutionRampPoints": DEFAULT_CONVOLUTION_RAMP_POINTS,
    "FreezeFinderDetectBrightening": DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING,
    "TemperatureCycleWarmupHysteresisC": 0.02,
    "TimeseriesPalette": "bright",
    "TimeseriesTraceLineWidth": 2.0,
    "TimeseriesConvolutionLineWidth": 1.0,
    "TimeseriesFreezeLineColor": "220,20,60,180",
    "TimeseriesFreezeLineWidth": 1.0,
    "TimeseriesCurrentFrameColor": "255,204,0,220",
    "TimeseriesCurrentFrameLineWidth": 2.0,
    "PreviewHandleSize": 12.0,
    "CircleLabelOffsetX": 6.0,
    "CircleLabelOffsetY": 6.0,
    **DEFAULT_VISUAL_COLORS,
}

module_dir = os.path.dirname(__file__)
resources_dir = os.path.join(module_dir, 'resources')
if not os.path.isdir(resources_dir):
    resources_dir = os.path.join(os.path.dirname(module_dir), 'resources')


class ColorPreferenceButton(QPushButton):
    def __init__(self, color_value, parent=None):
        super().__init__(parent)
        self._color = self._parse_color(color_value)
        self.clicked.connect(self.choose_color)
        self.setMinimumWidth(220)
        self.setFixedHeight(24)
        self.refresh()

    def _parse_color(self, color_value):
        if isinstance(color_value, QColor):
            return QColor(color_value)
        try:
            red, green, blue, alpha = [int(part.strip()) for part in str(color_value).split(",")]
            return QColor(red, green, blue, alpha)
        except Exception:
            return QColor(255, 0, 0, 255)

    def refresh(self):
        color = self._color
        label = f"{color.red()}, {color.green()}, {color.blue()}, {color.alpha()}"
        self.setText(label)
        text_color = "#111111" if color.lightness() > 140 else "#ffffff"
        self.setStyleSheet(
            "QPushButton {"
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
            f"color: {text_color};"
            "border: 1px solid rgba(0, 0, 0, 0.18);"
            "border-radius: 6px;"
            "padding: 2px 10px;"
            "min-height: 24px;"
            "max-height: 24px;"
            "text-align: left;"
            "}"
        )

    def choose_color(self):
        chosen = QColorDialog.getColor(self._color, self.parentWidget(), "Choose Color", QColorDialog.ShowAlphaChannel)
        if chosen.isValid():
            self._color = chosen
            self.refresh()

    def set_color_value(self, color_value):
        self._color = self._parse_color(color_value)
        self.refresh()

    def color_value(self):
        color = self._color
        return f"{color.red()},{color.green()},{color.blue()},{color.alpha()}"

def create_circular_mask(h, w, center, radius):
    Y, X = np.ogrid[:h, :w]
    mask = ((X - center[0]) ** 2 + (Y - center[1]) ** 2) <= (radius ** 2)
    return mask

class CustomGraphicsView(QGraphicsView):
    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main_window = main_window
        self.selected_items = []
        self.preview_double_click_armed = False
        self.preview_double_click_timer = QTimer(self)
        self.preview_double_click_timer.setSingleShot(True)
        self.preview_double_click_timer.timeout.connect(self._clear_preview_double_click_arm)

        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def _clear_preview_double_click_arm(self):
        self.preview_double_click_armed = False

    def wheelEvent(self, event):
        wheel_delta = event.angleDelta().y()
        if wheel_delta == 0:
            wheel_delta = event.pixelDelta().y()

        if self.main_window.is_pan_interaction_active():
            zoom_factor = 1.15
            if wheel_delta > 0 and self.transform().m11() < self.main_window.maximum_zoom:  # scroll up and not at max zoom
                self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
                self.scale(zoom_factor, zoom_factor)
            elif wheel_delta < 0 and self.transform().m11() >0.03:  # scroll down
                self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
                self.scale(1/zoom_factor, 1/zoom_factor)
            self.main_window.updateZoomTextbox()

            event.accept()

        elif self.main_window.tool_mode in ['select', 'edit-new']:
            # Handle circle size change here for select mode
            radius_step = float(getattr(self.main_window, "radius_wheel_step", 1.0))
            if wheel_delta > 0:  # scroll up
                self.main_window.circle_radius = min(self.main_window.circle_radius + radius_step, self.main_window.image_width)
            else:  # scroll down
                self.main_window.circle_radius = max(self.main_window.circle_radius - radius_step, 1)
            self.main_window.updateRadiusTextbox()
            if self.main_window.cell_controller.uses_grid_preview():
                self.main_window.update_grid_preview()
            self.main_window.sync_tool_options_panel()

            event.accept()
        elif self.main_window.cell_controller.uses_grid_preview():
            # Grid add and group edit share the same wheel vocabulary so users
            # do not have to learn two parameter-adjustment systems.
            if self.main_window.cell_controller.handle_wheel_adjustment(event, wheel_delta):
                return
        
        elif self.main_window.tool_mode in ['deselect','edit-choose']:
            pass # so no scrolling
        else:
            super().wheelEvent(event)
    
    def mousePressEvent(self, event):
        self.main_window.set_active_image_panel("viewer")
        self.setFocus()
        if self.main_window.is_pan_interaction_active():
            self.preview_double_click_armed = False
            self.selected_items = self.main_window.scene.selectedItems()
            super().mousePressEvent(event)
            return
        if (
            self.main_window.cell_controller.uses_grid_preview()
            and event.button() == Qt.RightButton
        ):
            if self.main_window.cell_controller.is_single_preview_mode():
                self.main_window.handle_circle_cancel_action()
            else:
                self.main_window.handle_grid_cancel_action()
            event.accept()
            return

        elif (
            self.main_window.cell_controller.uses_grid_preview()
            and self.main_window.grid_preview_floating
            and event.button() == Qt.LeftButton
        ):
            self.preview_double_click_armed = True
            self.preview_double_click_timer.start(QApplication.doubleClickInterval())
            self.main_window.update_grid_preview_from_scene_pos(self.mapToScene(event.pos()), pin=True)

        super().mousePressEvent(event)

    def focusInEvent(self, event):
        self.main_window.set_active_image_panel("viewer")
        super().focusInEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self.main_window.cell_controller.uses_grid_preview()
            and not self.main_window.is_pan_interaction_active()
        ):
            self.main_window.update_grid_preview_from_scene_pos(self.mapToScene(event.pos()))
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.main_window.set_active_image_panel("viewer")
        self.setFocus()
        if self.main_window.is_pan_interaction_active():
            self.preview_double_click_armed = False
            super().mouseDoubleClickEvent(event)
            return
        if (
            self.main_window.cell_controller.uses_grid_preview()
            and self.preview_double_click_armed
            and event.button() == Qt.LeftButton
        ):
            self.preview_double_click_timer.stop()
            self.main_window.update_grid_preview_from_scene_pos(self.mapToScene(event.pos()), pin=True)
            if self.main_window.cell_controller.is_single_preview_mode():
                self.main_window.handle_circle_apply_action()
            else:
                self.main_window.handle_grid_apply_action()
            self.preview_double_click_armed = False
            event.accept()
            return
        self.preview_double_click_armed = False
        super().mouseDoubleClickEvent(event)
        
    def mouseReleaseEvent(self, event):
        # Delete a circle upon clicking
        if self.main_window.tool_mode == 'deselect' and event.button() == Qt.LeftButton:
            before_state = self.main_window.capture_cell_state(include_analysis=True)
            # Find the item at the clicked position
            # Get the scene position
            scene_pos = self.mapToScene(event.pos())
    
            clicked_item = self.scene().itemAt(scene_pos, QTransform())
            if clicked_item and isinstance(clicked_item, CellCircle):
                removed_item = self.main_window.cell_controller.delete_cell_by_id(clicked_item.cell_id)
                clicked_item.pressed = False
                if removed_item is not None:
                    self.main_window.log(f"Delete cell {clicked_item.cell_id} at {clicked_item.circle_pixel_positions}")
                    self.main_window.push_cell_history("Delete Cells", before_state, include_analysis=True)

        elif self.main_window.tool_mode == 'edit-choose' and event.button() == Qt.LeftButton:
            selected_items = self.main_window.cell_controller.selected_scene_items()
            if selected_items:
                # Edit rubber-band selection should immediately behave like
                # "Cursor select, then click Edit".
                self.main_window.cell_controller.enter_edit_mode("edit-choose")

        super().mouseReleaseEvent(event)

        # Has to be below super event call
        # this is so pan does not affect item selection at all but also keep all the selected item selected
        if self.main_window.is_pan_interaction_active():

            for item in self.main_window.scene.selectedItems():
                item.setSelected(False)

            if self.selected_items: # is not an empty list
                for item in self.main_window.scene.items():
                    if item in self.selected_items:
                        item.setSelected(True)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.main_window.tool_mode == "cursor":
                self.main_window.delete_selected_cells()
            event.accept()
            return
        if (
            self.main_window.tool_mode == "image-edit"
            and self.main_window.is_image_edit_crop_active()
            and event.key() in (Qt.Key_Return, Qt.Key_Enter)
        ):
            self.main_window.trigger_image_edit_crop_apply_button()
            event.accept()
            return
        if self.main_window.cell_controller.uses_grid_preview() and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.main_window.confirm_active_preview()
            event.accept()
            return
        if self.main_window.cell_controller.uses_grid_preview() and event.key() == Qt.Key_Escape:
            self.main_window.handle_grid_cancel_action()
            event.accept()
            return
        if event.key() == Qt.Key_Left:
            if self.main_window.leftButton.isEnabled():
                self.main_window.decreaseSliderValue()
                self.main_window.key_press_button_highlight(self.main_window.leftButton)
            event.accept()
            return
        if event.key() == Qt.Key_Right:
            if self.main_window.rightButton.isEnabled():
                self.main_window.increaseSliderValue()
                self.main_window.key_press_button_highlight(self.main_window.rightButton)
            event.accept()
            return

        super().keyPressEvent(event)
    

class Image_analysis_thread(QThread):
    # Class Variables
    analysis_done = Signal(int, dict)  # Signal emitted when analysis is done

    def __init__(
        self,
        filePath,
        imagePaths,
        imageNames,
        list_of_cell_items,
        list_of_red_flags,
        image_edit_exposure=0.0,
        image_edit_contrast=0.0,
        image_edit_uniform_exposure_offsets=None,
        image_edit_crop_state=None,
        freeze_finder_width=DEFAULT_FREEZE_FINDER_WIDTH,
        freeze_finder_prominence=DEFAULT_FREEZE_FINDER_PROMINENCE,
        freeze_finder_tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS,
        convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
        convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS,
        freeze_finder_detect_brightening=DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING,
    ):
        super().__init__()
        self.filePath   = filePath
        self.imagePaths = imagePaths
        self.imageNames = imageNames
        # self.circle_pixel_positions = circle_pixel_positions
        # self.circle_sizes = circle_sizes

        self.list_of_cell_items = list_of_cell_items
        self.list_of_red_flags = list_of_red_flags
        self.image_edit_exposure = float(image_edit_exposure)
        self.image_edit_contrast = float(image_edit_contrast)
        self.image_edit_uniform_exposure_offsets = dict(image_edit_uniform_exposure_offsets or {})
        self.image_edit_crop_state = dict(image_edit_crop_state or {})

        self.imageFolderPath = os.path.dirname(self.imagePaths[0])
        self.freeze_finder_width = freeze_finder_width
        self.freeze_finder_prominence = freeze_finder_prominence
        self.freeze_finder_tail_extend_points = freeze_finder_tail_extend_points
        self.convolution_half_window_points = convolution_half_window_points
        self.convolution_ramp_points = convolution_ramp_points
        self.freeze_finder_detect_brightening = bool(freeze_finder_detect_brightening)
        self.grayscale_result_headers = []
        self.grayscale_result_rows = []
        self.freeze_result_headers = list(DEFAULT_FREEZE_RESULT_HEADERS)
        self.freeze_result_rows = []
        self.freeze_output_path = build_freeze_output_path(self.filePath) if self.filePath else None
        self._circular_mask_cache = {}
        self._circular_grid_cache = {}

    def run(self):
        file_name_list = []
        gss_table = []
        circle_pixel_positions_table = []
        circle_radius_table = []
        ordered_cell_ids = []
        seen_cell_ids = set()

        for frame_items in self.list_of_cell_items:
            for circle in frame_items:
                try:
                    cell_id = int(circle.cell_id)
                except (TypeError, ValueError):
                    continue
                if cell_id in seen_cell_ids:
                    continue
                seen_cell_ids.add(cell_id)
                ordered_cell_ids.append(cell_id)

        for i in range(len(self.imagePaths)):
            file_name = self.imageNames[i]
            frame_items = self.list_of_cell_items[i] if i < len(self.list_of_cell_items) else []
            frame_item_by_id = {}
            for circle in frame_items:
                try:
                    cell_id = int(circle.cell_id)
                except (TypeError, ValueError):
                    continue
                frame_item_by_id[cell_id] = circle
            ordered_frame_items = [frame_item_by_id.get(cell_id) for cell_id in ordered_cell_ids]
            circle_pixel_positions = [
                item.circle_pixel_positions if item is not None else (float("nan"), float("nan"))
                for item in ordered_frame_items
            ]
            circle_sizes = [
                float(item.circle_sizes) if item is not None else float("nan")
                for item in ordered_frame_items
            ]

            gss_list = self.gray_scale_mean(self.imagePaths[i], circle_pixel_positions, circle_sizes)
            
            file_name_list.append(file_name)
            gss_table.append(gss_list)
            circle_pixel_positions_table.append(circle_pixel_positions)
            circle_radius_table.append(circle_sizes)
            
            # Emit a signal to update the UI, if needed
            self.analysis_done.emit(i, {'file_name': file_name, 'gss_list': gss_list})
        
        # Auto analysis keeps its outputs in memory. A real CSV is only written
        # when an explicit path is supplied for an external workflow.
        if self.filePath:
            with open(self.filePath, 'w') as the_file:
                the_file.write(self.imageFolderPath)
                the_file.write("\n")
                the_file.write('file_name,flag_state')
                for cell_id in ordered_cell_ids:
                    the_file.write(",")
                    the_file.write(f'cell_{cell_id}_grayscale')
                    the_file.write(",")
                    the_file.write(f'cell_{cell_id}_circle_x')
                    the_file.write(",")
                    the_file.write(f'cell_{cell_id}_circle_y')
                    the_file.write(",")
                    the_file.write(f'cell_{cell_id}_circle_radius')
                the_file.write("\n")
                for i in range(len(file_name_list)):
                    the_file.write(str(file_name_list[i]))
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

        self.grayscale_result_headers = ['file_name', 'flag_state']
        for cell_id in ordered_cell_ids:
            self.grayscale_result_headers.extend([
                f'cell_{cell_id}_grayscale',
                f'cell_{cell_id}_circle_x',
                f'cell_{cell_id}_circle_y',
                f'cell_{cell_id}_circle_radius',
            ])

        self.grayscale_result_rows = []
        for i in range(len(file_name_list)):
            row = [
                str(file_name_list[i]),
                'flagged' if i in self.list_of_red_flags else ' ',
            ]
            for j in range(len(gss_table[i])):
                row.extend([
                    str(gss_table[i][j]),
                    str(circle_pixel_positions_table[i][j][0]),
                    str(circle_pixel_positions_table[i][j][1]),
                    str(circle_radius_table[i][j]),
                ])
            self.grayscale_result_rows.append(row)

        image_datetime_array = np.array([""] * len(file_name_list), dtype=object)
        image_grayscale_data = np.array(gss_table, dtype=float)
        self.freeze_result_rows, _ = compute_freeze_result_rows(
            file_name_list,
            image_datetime_array,
            image_grayscale_data,
            width=self.freeze_finder_width,
            prominence=self.freeze_finder_prominence,
            tail_extend_points=self.freeze_finder_tail_extend_points,
            convolution_half_window_points=self.convolution_half_window_points,
            convolution_ramp_points=self.convolution_ramp_points,
            detect_brightening=self.freeze_finder_detect_brightening,
            cell_ids=ordered_cell_ids,
        )
        if self.freeze_output_path:
            write_freeze_results_csv(self.freeze_output_path, self.freeze_result_headers, self.freeze_result_rows)

    def gray_scale_mean(self, image_path, circle_pixel_positions, circle_sizes):
        # Read directly as grayscale so we avoid an extra color conversion on every frame.
        image_gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image_gray is None:
            raise Exception(f"Unable to read image: {image_path}")
        raw_height, raw_width = image_gray.shape[:2]
        crop_is_identity = crop_state_is_identity(raw_width, raw_height, self.image_edit_crop_state)
        _crop_state, crop_matrix, _output_size = build_rotated_crop_affine(
            raw_width,
            raw_height,
            self.image_edit_crop_state or {},
        )
        try:
            effective_exposure = float(self.image_edit_exposure) + float(self.image_edit_uniform_exposure_offsets.get(str(image_path), 0.0))
        except (TypeError, ValueError):
            effective_exposure = float(self.image_edit_exposure)
        image_gray = apply_image_adjustments_to_uint8(
            image_gray,
            effective_exposure,
            self.image_edit_contrast,
            crop_state=self.image_edit_crop_state or {},
            apply_crop=True,
        )

        gss_list = [] # gray scale sum table
        image_height, image_width = image_gray.shape[:2]
        for i in range(len(circle_pixel_positions)):
            x = float(circle_pixel_positions[i][0])
            y = float(circle_pixel_positions[i][1])
            if not crop_is_identity:
                x, y = apply_affine_to_point(crop_matrix, x, y)
            radius = float(circle_sizes[i])
            if np.isnan(x) or np.isnan(y) or np.isnan(radius) or radius <= 0:
                gss_list.append(float("nan"))
                continue

            # Restrict work to the local circular bounding box instead of creating
            # a full-image mask for every circle on every frame.
            left = max(0, int(np.floor(x - radius)))
            right = min(image_width, int(np.ceil(x + radius)) + 1)
            top = max(0, int(np.floor(y - radius)))
            bottom = min(image_height, int(np.ceil(y + radius)) + 1)

            if (left >= right) or (top >= bottom):
                gss_list.append(float("nan"))
                continue

            image_patch = image_gray[top:bottom, left:right]
            patch_mask, mask_count = self.get_cached_circular_mask(
                bottom - top,
                right - left,
                x - left,
                y - top,
                radius,
            )
            if mask_count == 0:
                gss_list.append(float("nan"))
                continue

            gray_scale_mean = float(np.sum(image_patch[patch_mask]) / mask_count)
            gss_list.append(gray_scale_mean)
        
        return gss_list

    def get_cached_circular_mask(self, height, width, center_x, center_y, radius):
        mask_key = (
            int(height),
            int(width),
            round(float(center_x), 6),
            round(float(center_y), 6),
            round(float(radius), 6),
        )
        cached = self._circular_mask_cache.get(mask_key)
        if cached is not None:
            return cached

        grid_key = (int(height), int(width))
        cached_grid = self._circular_grid_cache.get(grid_key)
        if cached_grid is None:
            cached_grid = np.ogrid[:height, :width]
            self._circular_grid_cache[grid_key] = cached_grid
        y_grid, x_grid = cached_grid
        patch_mask = ((x_grid - center_x) ** 2 + (y_grid - center_y) ** 2) <= (radius ** 2)
        cached = (patch_mask, int(np.count_nonzero(patch_mask)))
        self._circular_mask_cache[mask_key] = cached
        return cached

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Icescopy")
        self.setFixedSize(420, 540)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        logo_label = QLabel()
        logo_image = QImage(os.path.join(resources_dir, "app_icons", "IcescopyApp.png"))
        logo_label.setPixmap(QPixmap.fromImage(logo_image).scaledToWidth(132, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout.addWidget(logo_label)

        text_label = QLabel()
        text_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        text_label.setText("Icescopy\nA tool for ice freezing array image analysis.")
        text_label.setFont(QFont("Arial", 12, QFont.Bold))
        text_label.setWordWrap(True)
        text_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout.addWidget(text_label)

        affiliation_label = QLabel()
        affiliation_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        affiliation_label.setText(
            "Developed by Bo Chen during research appointments at\n"
            "Texas A&M University (Ph.D.) and\n"
            "Colorado State University (Postdoctoral Researcher)."
        )
        affiliation_label.setFont(QFont("Arial", 10))
        affiliation_label.setWordWrap(True)
        affiliation_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout.addWidget(affiliation_label)

        disclaimer_label = QLabel()
        disclaimer_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        disclaimer_label.setText(
            "Institutional affiliations are listed for attribution only\n"
            "and do not imply institutional endorsement."
        )
        disclaimer_label.setFont(QFont("Arial", 9))
        disclaimer_label.setWordWrap(True)
        disclaimer_label.setStyleSheet("color: rgba(96, 96, 96, 255);")
        disclaimer_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout.addWidget(disclaimer_label)

        rights_label = QLabel()
        rights_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        rights_label.setText("Copyright \u00A9 2023-2026 Bo Chen")
        rights_label.setFont(QFont("Arial", 12))
        rights_label.setWordWrap(True)
        rights_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout.addWidget(rights_label)

        licenselabel = QLabel()
        licenselabel.setTextInteractionFlags(Qt.TextBrowserInteraction)  # Makes the label text clickable
        licenselabel.setText('Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.')
        licenselabel.setWordWrap(True)
        licenselabel.setFont(QFont("Arial", 8))
        licenselabel.setStyleSheet("""color: rgba(127, 127, 127, 255);""")
        licenselabel.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        licenselabel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        layout.addWidget(licenselabel)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)

        self.setLayout(layout)


class PreferencesDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.saved_preferences = self.load_saved_preferences()
        
        self.setWindowTitle("Preferences")
        self.resize(760, 420)
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(16, 16, 16, 16)
        outer_layout.setSpacing(12)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        self.preference_label_width = 190
        self.preference_field_width = 220
        self.preference_page_width = 560
        self.preference_help_width = self.preference_page_width - self.preference_label_width - 72

        self.default_circle_radius_field = self.make_double_spinbox(0.1, 100000.0, self.pref_value("DefaultCircleRadius"), 1)
        self.pen_width_field = self.make_double_spinbox(0.1, 100.0, self.pref_value("PenWidth"), 1)
        self.maximum_zoom_field = self.make_double_spinbox(0.1, 1000.0, self.pref_value("MaximumZoom"), 1)
        self.dot_size_field = self.make_double_spinbox(0.1, 100.0, self.pref_value("DotSize"), 1)
        self.slider_maxzoom_pixel_interval_field = self.make_double_spinbox(1.0, 1000.0, self.pref_value("SliderMaxZoomPixelInterval"), 1)
        self.slider_tick_pixel_interval_field = self.make_double_spinbox(1.0, 1000.0, self.pref_value("SliderTickPixelInterval"), 1)
        self.undo_limit_field = self.make_spinbox(1, 1000, self.pref_value("UndoLimit"))
        self.sample_name_pattern_field = QLineEdit(str(self.pref_value("SampleNamePattern")))
        self.viewer_image_count_field = QComboBox()
        self.viewer_image_count_field.addItems(["1", "2", "3"])
        self.viewer_image_count_field.setMinimumContentsLength(10)
        self.viewer_image_count_field.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)
        self.viewer_image_count_field.setCurrentText(str(self.pref_value("ViewerImageCount")))
        self.sort_mode_field = QComboBox()
        for value, label in SORT_MODE_LABELS.items():
            self.sort_mode_field.addItem(label, value)
        self.sort_mode_field.setCurrentIndex(max(0, self.sort_mode_field.findData(self.pref_value("SortMode"))))
        self.sort_mode_field.setMinimumContentsLength(20)
        self.sort_mode_field.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)

        self.grid_rows_field = self.make_spinbox(1, 100, self.pref_value("GridRows"))
        self.grid_columns_field = self.make_spinbox(1, 100, self.pref_value("GridColumns"))
        self.grid_horizontal_pitch_field = self.make_double_spinbox(0.1, 100000.0, self.pref_value("GridHorizontalPitch"), 1)
        self.grid_vertical_pitch_field = self.make_double_spinbox(0.1, 100000.0, self.pref_value("GridVerticalPitch"), 1)
        self.grid_rotation_field = self.make_double_spinbox(-180.0, 180.0, self.pref_value("GridRotationDegrees"), 1)
        self.grid_cell_id_direction_field = QComboBox()
        for value, label in GRID_CELL_ID_DIRECTION_LABELS.items():
            self.grid_cell_id_direction_field.addItem(label, value)
        self.grid_cell_id_direction_field.setCurrentIndex(
            max(0, self.grid_cell_id_direction_field.findData(self.pref_value("GridCellIdDirection")))
        )
        self.radius_wheel_step_field = self.make_double_spinbox(0.1, 1000.0, self.pref_value("RadiusWheelStep"), 1)
        self.grid_pitch_wheel_step_field = self.make_double_spinbox(0.1, 1000.0, self.pref_value("GridPitchWheelStep"), 1)
        self.grid_tilt_wheel_step_field = self.make_double_spinbox(0.1, 90.0, self.pref_value("GridTiltWheelStep"), 1)
        self.freeze_finder_width_field = self.make_double_spinbox(0.1, 100000.0, self.pref_value("FreezeFinderWidth"), 1)
        self.freeze_finder_prominence_field = self.make_double_spinbox(0.1, 1000000.0, self.pref_value("FreezeFinderProminence"), 1)
        self.freeze_finder_tail_extend_points_field = self.make_spinbox(0, 1000, self.pref_value("FreezeFinderTailExtendPoints"))
        self.convolution_half_window_points_field = self.make_spinbox(0, 100000, self.pref_value("ConvolutionHalfWindowPoints"))
        self.convolution_ramp_points_field = self.make_spinbox(0, 1000, self.pref_value("ConvolutionRampPoints"))
        self.freeze_finder_detect_brightening_field = QCheckBox("Detect freezing from brightening")
        self.freeze_finder_detect_brightening_field.setChecked(bool(self.pref_value("FreezeFinderDetectBrightening")))
        self.temperature_cycle_warmup_hysteresis_c_field = self.make_double_spinbox(
            0.0,
            10.0,
            self.pref_value("TemperatureCycleWarmupHysteresisC"),
            2,
        )
        self.temperature_cycle_warmup_hysteresis_c_field.setSingleStep(0.01)
        self.timeseries_palette_field = QComboBox()
        for value, label in PLOT_PALETTE_LABELS.items():
            self.timeseries_palette_field.addItem(label, value)
        self.timeseries_palette_field.setCurrentIndex(
            max(0, self.timeseries_palette_field.findData(self.pref_value("TimeseriesPalette")))
        )
        self.timeseries_trace_line_width_field = self.make_double_spinbox(0.1, 20.0, self.pref_value("TimeseriesTraceLineWidth"), 1)
        self.timeseries_convolution_line_width_field = self.make_double_spinbox(0.1, 20.0, self.pref_value("TimeseriesConvolutionLineWidth"), 1)
        self.timeseries_freeze_line_color_field = ColorPreferenceButton(self.pref_value("TimeseriesFreezeLineColor"), self)
        self.timeseries_freeze_line_width_field = self.make_double_spinbox(0.1, 20.0, self.pref_value("TimeseriesFreezeLineWidth"), 1)
        self.timeseries_current_frame_color_field = ColorPreferenceButton(self.pref_value("TimeseriesCurrentFrameColor"), self)
        self.timeseries_current_frame_line_width_field = self.make_double_spinbox(0.1, 20.0, self.pref_value("TimeseriesCurrentFrameLineWidth"), 1)
        self.preview_handle_size_field = self.make_double_spinbox(2.0, 100.0, self.pref_value("PreviewHandleSize"), 1)
        self.circle_label_offset_x_field = self.make_double_spinbox(-500.0, 500.0, self.pref_value("CircleLabelOffsetX"), 1)
        self.circle_label_offset_y_field = self.make_double_spinbox(-500.0, 500.0, self.pref_value("CircleLabelOffsetY"), 1)
        self.circle_default_color_field = ColorPreferenceButton(self.pref_value("CircleDefaultColor"), self)
        self.circle_hover_color_field = ColorPreferenceButton(self.pref_value("CircleHoverColor"), self)
        self.circle_selected_color_field = ColorPreferenceButton(self.pref_value("CircleSelectedColor"), self)
        self.circle_edit_color_field = ColorPreferenceButton(self.pref_value("CircleEditColor"), self)
        self.circle_pressed_color_field = ColorPreferenceButton(self.pref_value("CirclePressedColor"), self)
        self.grid_preview_outline_color_field = ColorPreferenceButton(self.pref_value("GridPreviewOutlineColor"), self)
        self.grid_preview_fill_color_field = ColorPreferenceButton(self.pref_value("GridPreviewFillColor"), self)

        for widget in [
            self.default_circle_radius_field,
            self.pen_width_field,
            self.maximum_zoom_field,
            self.dot_size_field,
            self.slider_maxzoom_pixel_interval_field,
            self.slider_tick_pixel_interval_field,
            self.undo_limit_field,
            self.sample_name_pattern_field,
            self.sort_mode_field,
            self.grid_rows_field,
            self.grid_columns_field,
            self.grid_horizontal_pitch_field,
            self.grid_vertical_pitch_field,
            self.grid_rotation_field,
            self.grid_cell_id_direction_field,
            self.radius_wheel_step_field,
            self.grid_pitch_wheel_step_field,
            self.grid_tilt_wheel_step_field,
            self.freeze_finder_width_field,
            self.freeze_finder_prominence_field,
            self.freeze_finder_tail_extend_points_field,
            self.convolution_half_window_points_field,
            self.convolution_ramp_points_field,
            self.freeze_finder_detect_brightening_field,
            self.temperature_cycle_warmup_hysteresis_c_field,
            self.timeseries_palette_field,
            self.timeseries_trace_line_width_field,
            self.timeseries_convolution_line_width_field,
            self.timeseries_freeze_line_color_field,
            self.timeseries_freeze_line_width_field,
            self.timeseries_current_frame_color_field,
            self.timeseries_current_frame_line_width_field,
            self.preview_handle_size_field,
            self.circle_label_offset_x_field,
            self.circle_label_offset_y_field,
            self.circle_default_color_field,
            self.circle_hover_color_field,
            self.circle_selected_color_field,
            self.circle_edit_color_field,
            self.circle_pressed_color_field,
            self.grid_preview_outline_color_field,
            self.grid_preview_fill_color_field,
        ]:
            widget.setFixedWidth(self.preference_field_width)

        self.category_list = QListWidget()
        self.category_list.setFixedWidth(160)
        self.category_list.addItems(["General", "Viewer", "Drawing", "Analysis", "Timeseries", "Timeline"])
        self.category_list.setCurrentRow(0)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.build_general_page())
        self.pages.addWidget(self.build_viewer_page())
        self.pages.addWidget(self.build_drawing_page())
        self.pages.addWidget(self.build_analysis_page())
        self.pages.addWidget(self.build_timeseries_page())
        self.pages.addWidget(self.build_timeline_page())
        self.category_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.category_list.currentRowChanged.connect(self.reset_page_scroll_position)

        self.pages_scroll_area = QScrollArea()
        self.pages_scroll_area.setWidgetResizable(True)
        self.pages_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pages_scroll_area.setWidget(self.pages)

        content_layout.addWidget(self.category_list)
        content_layout.addWidget(self.pages_scroll_area, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_preferences)
        button_box.rejected.connect(self.reject)

        outer_layout.addLayout(content_layout)
        outer_layout.addWidget(button_box)
        self.setLayout(outer_layout)

    def load_saved_preferences(self):
        try:
            saved = self.main_window.load_preferences_from_xml()
        except FileNotFoundError:
            saved = {}
        return saved

    def pref_value(self, key):
        return self.saved_preferences.get(key, DEFAULT_PREFERENCE_VALUES[key])

    def reset_page_scroll_position(self):
        if hasattr(self, "pages_scroll_area"):
            self.pages_scroll_area.verticalScrollBar().setValue(0)

    def make_spinbox(self, minimum, maximum, value):
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(int(value))
        return widget

    def make_double_spinbox(self, minimum, maximum, value, decimals):
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setSingleStep(0.1 if decimals else 1.0)
        widget.setValue(float(value))
        return widget

    def make_help_label(self, text):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        label.setStyleSheet("color: rgba(110, 110, 110, 220);")
        label.setMaximumWidth(self.preference_help_width)
        return label

    def build_field_with_help(self, widget, help_text):
        container = QWidget()
        container.setMaximumWidth(self.preference_help_width)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        if isinstance(widget, QLabel):
            widget.setWordWrap(True)
            widget.setMaximumWidth(self.preference_help_width)
        layout.addWidget(widget, 0, Qt.AlignLeft)
        layout.addWidget(self.make_help_label(help_text))
        return container

    def build_info_group_box(self, title, paragraphs):
        section = QWidget()
        section.setMaximumWidth(self.preference_page_width)
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(6)

        title_label = QLabel(title, section)
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        section_layout.addWidget(title_label)

        body = QWidget(section)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 0, 0, 0)
        layout.setSpacing(10)

        body_label = self.make_help_label("\n\n".join(paragraphs))
        body_label.setMaximumWidth(self.preference_page_width - 32)
        layout.addWidget(body_label)

        section_layout.addWidget(body)
        return section

    def build_group_box(self, title, rows):
        section = QWidget()
        section.setMaximumWidth(self.preference_page_width)
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(6)

        title_label = QLabel(title, section)
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        section_layout.addWidget(title_label)

        body = QWidget(section)
        form_layout = QFormLayout(body)
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(12)
        form_layout.setContentsMargins(16, 0, 0, 0)

        for label_text, widget in rows:
            label = QLabel(label_text)
            label.setFixedWidth(self.preference_label_width)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            form_layout.addRow(label, widget)

        section_layout.addWidget(body)
        return section

    def build_section_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet("color: rgba(0, 0, 0, 0.10);")
        line.setFixedHeight(1)
        return line

    def build_preferences_page(self, title, subtitle, groups):
        page = QWidget()
        outer_layout = QHBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        content_widget = QWidget(page)
        content_widget.setMaximumWidth(self.preference_page_width)
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 16, 28, 16)
        layout.setSpacing(20)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 4)
        title_label.setFont(title_font)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_font = subtitle_label.font()
        subtitle_font.setPointSize(subtitle_font.pointSize())
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: rgba(95, 95, 95, 220);")
        subtitle_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        title_label.setMaximumWidth(content_widget.maximumWidth())
        subtitle_label.setMaximumWidth(content_widget.maximumWidth())

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        for group_index, (group_title, rows) in enumerate(groups):
            if group_index > 0:
                layout.addWidget(self.build_section_separator())
            layout.addWidget(self.build_group_box(group_title, rows))
        layout.addStretch(1)
        page.content_layout = layout
        outer_layout.addWidget(content_widget)
        outer_layout.addStretch(1)
        return page

    def build_general_page(self):
        return self.build_preferences_page(
            "General",
            "Control overall application behavior and how much session history is kept.",
            [
                ("Session", [
                    ("Undo History Limit", self.undo_limit_field),
                    ("Default Sort", self.sort_mode_field),
                ]),
                ("Samples", [
                    ("Sample Name Pattern", self.sample_name_pattern_field),
                ]),
            ],
        )

    def build_viewer_page(self):
        return self.build_preferences_page(
            "Viewer",
            "Adjust how many frames are visible and how the image viewer behaves.",
            [
                ("Display", [
                    ("Images Shown", self.viewer_image_count_field),
                    ("Maximum Zoom", self.maximum_zoom_field),
                ]),
            ],
        )

    def build_drawing_page(self):
        page = self.build_preferences_page(
            "Drawing",
            "Set circle defaults, grid cell defaults, wheel steps, and preview colors for ROI work.",
            [
                ("Circle Defaults", [
                    ("Default Circle Radius", self.default_circle_radius_field),
                    ("Radius Wheel Step", self.radius_wheel_step_field),
                ]),
                ("Grid Defaults", [
                    ("Default Rows", self.grid_rows_field),
                    ("Default Columns", self.grid_columns_field),
                    ("Default H Pitch", self.grid_horizontal_pitch_field),
                    ("Default V Pitch", self.grid_vertical_pitch_field),
                    ("Default Tilt", self.grid_rotation_field),
                    ("Cell ID Direction", self.grid_cell_id_direction_field),
                    ("Pitch Wheel Step", self.grid_pitch_wheel_step_field),
                    ("Tilt Wheel Step", self.grid_tilt_wheel_step_field),
                ]),
                ("Handles & Labels", [
                    ("Pen Width", self.pen_width_field),
                    ("Dot Size", self.dot_size_field),
                    ("Preview Handle Size", self.preview_handle_size_field),
                    ("Label X Offset", self.circle_label_offset_x_field),
                    ("Label Y Offset", self.circle_label_offset_y_field),
                ]),
                ("Colors", [
                    ("Circle Default", self.circle_default_color_field),
                    ("Circle Hover", self.circle_hover_color_field),
                    ("Circle Selected", self.circle_selected_color_field),
                    ("Circle Edit", self.circle_edit_color_field),
                    ("Circle Pressed", self.circle_pressed_color_field),
                    ("Grid Outline", self.grid_preview_outline_color_field),
                    ("Grid Fill", self.grid_preview_fill_color_field),
                ]),
            ],
        )
        reset_visual_button = QPushButton("Restore Visual Defaults", page)
        reset_visual_button.clicked.connect(self.restore_visual_defaults)
        page.content_layout.addWidget(reset_visual_button)
        return page

    def build_timeline_page(self):
        return self.build_preferences_page(
            "Timeline",
            "Tune slider density and navigation granularity for long image sequences.",
            [
                ("Slider", [
                    ("Slider Max Zoom Pixel Interval", self.slider_maxzoom_pixel_interval_field),
                    ("Slider Tick Pixel Interval", self.slider_tick_pixel_interval_field),
                ]),
            ],
        )

    def build_analysis_page(self):
        page = self.build_preferences_page(
            "Analysis",
            "Control how grayscale traces are interpreted and how freezing events are reported.",
            [],
        )
        page.content_layout.insertWidget(
            2,
            self.build_info_group_box(
                "Grayscale",
                [
                    "Mean grayscale is measured inside each selected circle for every frame.",
                    "The solid trace shows the raw mean grayscale signal. The dashed convolution trace is the edge-enhanced signal used to detect sudden freezing steps, whether they appear as darkening or brightening depending on the selected polarity.",
                ],
            ),
        )
        page.content_layout.insertWidget(
            3,
            self.build_group_box(
                "Freeze Finding",
                [
                    (
                        "Peak Width",
                        self.build_field_with_help(
                            self.freeze_finder_width_field,
                            "Minimum event width in frames. Increase this to ignore narrow noisy dips.",
                        ),
                    ),
                    (
                        "Peak Prominence",
                        self.build_field_with_help(
                            self.freeze_finder_prominence_field,
                            "How strongly the convolution dip must stand out from the surrounding baseline before it is accepted as freezing.",
                        ),
                    ),
                    (
                        "Tail Extension Points",
                        self.build_field_with_help(
                            self.freeze_finder_tail_extend_points_field,
                            "Repeats the final grayscale value for this many extra points before convolution so drops at the end of the experiment can still be detected.",
                        ),
                    ),
                    (
                        "Convolution Half Window Points",
                        self.build_field_with_help(
                            self.convolution_half_window_points_field,
                            "This is the kernel N: the number of positive points on the left and negative points on the right. Set 0 to keep the original whole-trace window.",
                        ),
                    ),
                    (
                        "Convolution Ramp Points",
                        self.build_field_with_help(
                            self.convolution_ramp_points_field,
                            "Softens the step kernel near its center. Larger values better match gradual sloped darkening without changing the convolution implementation.",
                        ),
                    ),
                    (
                        "Detection Polarity",
                        self.build_field_with_help(
                            self.freeze_finder_detect_brightening_field,
                            "Off detects sudden darkening as freezing. Turn this on when frozen wells become brighter so the app detects upward convolution peaks instead.",
                        ),
                    ),
                    (
                        "Cycle Warm-Up Hysteresis (°C)",
                        self.build_field_with_help(
                            self.temperature_cycle_warmup_hysteresis_c_field,
                            "Extra warm-up required above the reset threshold before a new temperature cycle is created. Use this to ignore tiny threshold jitter such as 4.999 to 5.002 C.",
                        ),
                    ),
                ],
            ),
        )
        return page

    def build_timeseries_page(self):
        return self.build_preferences_page(
            "Timeseries",
            "Tune the grayscale timeseries panel appearance, including trace palette and reference-line styling.",
            [
                ("Trace Appearance", [
                    ("Trace Palette", self.timeseries_palette_field),
                    ("Trace Line Width", self.timeseries_trace_line_width_field),
                    ("Convolution Line Width", self.timeseries_convolution_line_width_field),
                ]),
                ("Reference Lines", [
                    ("Freeze Event Color", self.timeseries_freeze_line_color_field),
                    ("Freeze Event Width", self.timeseries_freeze_line_width_field),
                    ("Current Frame Color", self.timeseries_current_frame_color_field),
                    ("Current Frame Width", self.timeseries_current_frame_line_width_field),
                ]),
            ],
        )

    def save_preferences(self):
        root = Element('Preferences')

        SubElement(root, "DefaultCircleRadius").text = str(self.default_circle_radius_field.value())
        SubElement(root, "PenWidth").text = str(self.pen_width_field.value())
        SubElement(root, "MaximumZoom").text = str(self.maximum_zoom_field.value())
        SubElement(root, "DotSize").text = str(self.dot_size_field.value())
        SubElement(root, "SliderMaxZoomPixelInterval").text = str(self.slider_maxzoom_pixel_interval_field.value())
        SubElement(root, "SliderTickPixelInterval").text = str(self.slider_tick_pixel_interval_field.value())
        SubElement(root, "UndoLimit").text = str(self.undo_limit_field.value())
        SubElement(root, "SampleNamePattern").text = self.sample_name_pattern_field.text()
        SubElement(root, "ViewerImageCount").text = self.viewer_image_count_field.currentText()
        SubElement(root, "SortMode").text = self.sort_mode_field.currentData()
        SubElement(root, "GridRows").text = str(self.grid_rows_field.value())
        SubElement(root, "GridColumns").text = str(self.grid_columns_field.value())
        SubElement(root, "GridHorizontalPitch").text = str(self.grid_horizontal_pitch_field.value())
        SubElement(root, "GridVerticalPitch").text = str(self.grid_vertical_pitch_field.value())
        SubElement(root, "GridRotationDegrees").text = str(self.grid_rotation_field.value())
        SubElement(root, "GridCellIdDirection").text = str(self.grid_cell_id_direction_field.currentData())
        SubElement(root, "RadiusWheelStep").text = str(self.radius_wheel_step_field.value())
        SubElement(root, "GridPitchWheelStep").text = str(self.grid_pitch_wheel_step_field.value())
        SubElement(root, "GridTiltWheelStep").text = str(self.grid_tilt_wheel_step_field.value())
        SubElement(root, "FreezeFinderWidth").text = str(self.freeze_finder_width_field.value())
        SubElement(root, "FreezeFinderProminence").text = str(self.freeze_finder_prominence_field.value())
        SubElement(root, "FreezeFinderTailExtendPoints").text = str(self.freeze_finder_tail_extend_points_field.value())
        SubElement(root, "ConvolutionHalfWindowPoints").text = str(self.convolution_half_window_points_field.value())
        SubElement(root, "ConvolutionRampPoints").text = str(self.convolution_ramp_points_field.value())
        SubElement(root, "FreezeFinderDetectBrightening").text = "true" if self.freeze_finder_detect_brightening_field.isChecked() else "false"
        SubElement(root, "TemperatureCycleWarmupHysteresisC").text = str(
            self.temperature_cycle_warmup_hysteresis_c_field.value()
        )
        SubElement(root, "TimeseriesPalette").text = self.timeseries_palette_field.currentData()
        SubElement(root, "TimeseriesTraceLineWidth").text = str(self.timeseries_trace_line_width_field.value())
        SubElement(root, "TimeseriesConvolutionLineWidth").text = str(self.timeseries_convolution_line_width_field.value())
        SubElement(root, "TimeseriesFreezeLineColor").text = self.timeseries_freeze_line_color_field.color_value()
        SubElement(root, "TimeseriesFreezeLineWidth").text = str(self.timeseries_freeze_line_width_field.value())
        SubElement(root, "TimeseriesCurrentFrameColor").text = self.timeseries_current_frame_color_field.color_value()
        SubElement(root, "TimeseriesCurrentFrameLineWidth").text = str(self.timeseries_current_frame_line_width_field.value())
        SubElement(root, "PreviewHandleSize").text = str(self.preview_handle_size_field.value())
        SubElement(root, "CircleLabelOffsetX").text = str(self.circle_label_offset_x_field.value())
        SubElement(root, "CircleLabelOffsetY").text = str(self.circle_label_offset_y_field.value())
        SubElement(root, "CircleDefaultColor").text = self.circle_default_color_field.color_value()
        SubElement(root, "CircleHoverColor").text = self.circle_hover_color_field.color_value()
        SubElement(root, "CircleSelectedColor").text = self.circle_selected_color_field.color_value()
        SubElement(root, "CircleEditColor").text = self.circle_edit_color_field.color_value()
        SubElement(root, "CirclePressedColor").text = self.circle_pressed_color_field.color_value()
        SubElement(root, "GridPreviewOutlineColor").text = self.grid_preview_outline_color_field.color_value()
        SubElement(root, "GridPreviewFillColor").text = self.grid_preview_fill_color_field.color_value()

        tree = ElementTree(root)
        tree.write(os.path.join(resources_dir,"preferences.xml"))
        self.main_window.set_preferences(preserve_session_tool_state=True)
        self.accept()

    def restore_visual_defaults(self):
        self.pen_width_field.setValue(1.0)
        self.dot_size_field.setValue(1.0)
        self.preview_handle_size_field.setValue(float(DEFAULT_PREFERENCE_VALUES["PreviewHandleSize"]))
        self.circle_label_offset_x_field.setValue(float(DEFAULT_PREFERENCE_VALUES["CircleLabelOffsetX"]))
        self.circle_label_offset_y_field.setValue(float(DEFAULT_PREFERENCE_VALUES["CircleLabelOffsetY"]))
        self.circle_default_color_field.set_color_value(DEFAULT_VISUAL_COLORS["CircleDefaultColor"])
        self.circle_hover_color_field.set_color_value(DEFAULT_VISUAL_COLORS["CircleHoverColor"])
        self.circle_selected_color_field.set_color_value(DEFAULT_VISUAL_COLORS["CircleSelectedColor"])
        self.circle_edit_color_field.set_color_value(DEFAULT_VISUAL_COLORS["CircleEditColor"])
        self.circle_pressed_color_field.set_color_value(DEFAULT_VISUAL_COLORS["CirclePressedColor"])
        self.grid_preview_outline_color_field.set_color_value(DEFAULT_VISUAL_COLORS["GridPreviewOutlineColor"])
        self.grid_preview_fill_color_field.set_color_value(DEFAULT_VISUAL_COLORS["GridPreviewFillColor"])


class SortImagesDialog(QDialog):
    SORT_OPTIONS = [
        ("Natural Filename", "natural_filename"),
        ("Filename (A-Z)", "filename_asc"),
        ("Filename (Z-A)", "filename_desc"),
        ("Created Time", "created_time"),
        ("Modified Time", "modified_time"),
        ("EXIF Time", "exif_time"),
    ]

    def __init__(self, main_window, availability, current_mode, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.availability = availability
        self.setWindowTitle("Sort Images")
        self.resize(460, 260)

        layout = QVBoxLayout(self)

        title = QLabel("Sort loaded images or choose the default ordering for new images.")
        title.setWordWrap(True)
        layout.addWidget(title)

        form_layout = QFormLayout()
        self.sort_mode_combo = QComboBox()
        self.sort_mode_combo.setMinimumWidth(260)
        for label, value in self.SORT_OPTIONS:
            self.sort_mode_combo.addItem(label, value)

        combo_model = self.sort_mode_combo.model()
        for index, (_, value) in enumerate(self.SORT_OPTIONS):
            item = combo_model.item(index)
            if item is not None and not availability.get(value, True):
                item.setEnabled(False)

        current_index = max(0, self.sort_mode_combo.findData(current_mode))
        self.sort_mode_combo.setCurrentIndex(current_index)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: rgba(110, 110, 110, 220);")
        self.sort_mode_combo.currentIndexChanged.connect(self.update_info_label)
        self.update_info_label()

        form_layout.addRow("Sort By", self.sort_mode_combo)
        layout.addLayout(form_layout)
        layout.addWidget(self.info_label)
        layout.addStretch(1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def update_info_label(self):
        mode = self.selected_mode()
        if not self.availability.get(mode, True):
            self.info_label.setText("This sort method is not available for the current session.")
        elif mode == "natural_filename":
            self.info_label.setText("Uses human-friendly filename ordering like 1, 2, 10, 20, 100.")
        elif mode == "exif_time":
            self.info_label.setText("Uses EXIF capture timestamps. Disabled if any loaded image is missing EXIF date/time.")
        else:
            self.info_label.setText("Applies the selected ordering to the current session and future added images.")

    def selected_mode(self):
        return self.sort_mode_combo.currentData()
