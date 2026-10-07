# Stylesheet
import os
import platform

from PySide6.QtCore import QUrl

module_dir = os.path.abspath(os.path.dirname(__file__))
resources_dir = os.path.abspath(os.path.join(module_dir, 'resources'))
if not os.path.isdir(resources_dir):
    resources_dir = os.path.abspath(os.path.join(os.path.dirname(module_dir), 'resources'))
ui_images_dir = os.path.abspath(os.path.join(resources_dir, 'ui_images'))
IS_WINDOWS = platform.system() == "Windows"

def _toolbar_style(hover, pressed, checked):
    return f"""
                QToolButton {{
                    border-radius: 5px;      /* Rounded corners */
                    width: 24px;             /* Width */
                    height: 24px;            /* Height */
                    background-color: transparent;
                    padding: 5px;
                }}
                QToolButton:hover {{
                    background-color: {hover}
                }}
                QToolButton:pressed {{
                    background-color: {pressed};
                }}
                QToolButton:checked {{
                    background-color: {checked};
                }}
                QToolButton:checked:hover {{
                    background-color: {hover}
                }}
                QToolButton:checked:pressed {{
                    background-color: {pressed}
                }}
                QToolButton::text {{
                    display: inline;
                }}
            """


darkmode_toolbar_style_sheet = _toolbar_style("rgba(10, 132, 255, 180)", "rgba(10, 132, 255, 120)", "dimgray")
light_mode_toolbar_style_sheet = _toolbar_style("rgba(0, 122, 255, 150)", "rgba(0, 122, 255, 200)", "darkgray")

slider_handle_path = os.path.abspath(os.path.join(ui_images_dir, "slider_handle.png"))
if IS_WINDOWS:
    slider_url = QUrl.fromLocalFile(slider_handle_path).toString()
    def _time_line_slider_style(border, groove, add_page, sub_page):
        return f"""
                    QSlider::groove:horizontal {{
                        border: 1px solid {border};
                        background: {groove};
                        height: 6px;
                        border-radius: 3px;
                        margin: 0px 0px 6px 0px;
                    }}

                    QSlider::add-page:horizontal {{
                        border: 1px solid {border};
                        background: {add_page};
                        height: 6px;
                        border-radius: 3px;
                        margin: 0px 0px 6px 0px;
                    }}
                    QSlider::sub-page:horizontal {{
                        border: 1px solid {border};
                        background: {sub_page};
                        height: 6px;
                        border-radius: 3px;
                        margin: 0px 0px 6px 0px;
                    }}

                    QSlider::handle:horizontal {{
                        width: 16px;
                        height: 20px;
                        border: none;
                        background: transparent;
                        margin: -7px 0px;
                    }}
                    """

    dark_mode_time_line_slider_style = _time_line_slider_style("#999999", "#323232", "#323232", "rgba(80, 80, 80, 255)")
    light_mode_time_line_slider_style = _time_line_slider_style("#212121", "#ececec", "#FFFFFF", "#ececec")
else:
    slider_url = slider_handle_path.replace(os.sep, "/")
    def _time_line_slider_style(border, groove, add_page, sub_page):
        return f"""
                    QSlider::groove:horizontal {{
                        border: 1px solid {border};
                        background: {groove};
                        height: 6px;
                        border-radius: 3px;
                        margin-bottom: 10px;
                    }}

                    QSlider::add-page:horizontal {{
                        border: 1px solid {border};
                        background: {add_page};
                        height: 6px;
                        border-radius: 3px;
                        margin-bottom: 10px;
                    }}
                    QSlider::sub-page:horizontal {{
                        border: 1px solid {border};
                        background: {sub_page};
                        height: 6px;
                        border-radius: 3px;
                        margin-bottom: 10px;
                    }}

                    QSlider::handle:horizontal {{
                        width: 16px;  /* Slightly fatter drag thumb */
                        height: 20px;  /* Adjust to your trapezoid height */
                        border: none;
                        margin: -7px 0px -13px 0px;  /* handle starts left most of the groove */
                        image: url({slider_url});
                    }}
                    """

    dark_mode_time_line_slider_style = _time_line_slider_style("#999999", "#323232", "#323232", "rgba(80, 80, 80, 255)")
    light_mode_time_line_slider_style = _time_line_slider_style("#212121", "#ececec", "#FFFFFF", "#ececec")

dark_mode_button_stylesheet = """
                QPushButton {
                    background-color: rgba(50, 50, 50, 255);
                    border: 1px solid rgba(101, 101, 101, 255);
                    border-radius: 5px;
                    width: 50px;
                    height: 15px;
                    margin-top: 5px;
                }
                QPushButton:hover {
                    background-color: rgba(10, 132, 255, 180) !important;
                }
                QPushButton:pressed {
                    background-color: rgba(10, 132, 255, 120) !important;
                }           
                QPushButton::text {
                    display: inline;
                }
            """
light_mode_button_stylesheet = """
                QPushButton {
                    background-color: rgba(236, 236, 236, 255);
                    border: 1px solid #A0A0A0;
                    border-radius: 5px;
                    min-width: 40px;
                    height: 15px;
                    margin-top: 5px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 122, 255, 150) !important;
                }
                QPushButton:pressed {
                    background-color: rgba(0, 122, 255, 200) !important;
                }             
                QPushButton::text {
                    display: inline;
                }
            """


dark_mode_status_bar_stylesheet = "color: #999999; font-size: 10pt;"
dark_mode_line_edit_style_sheet = "background-color: #323232; color: #999999;"

light_mode_status_bar_stylesheet = "color: #505050; font-size: 10pt;"
light_mode_line_edit_style_sheet = "background-color: #CCCCCC; color: #505050;"

def _zoom_slider_style(border, groove, handle_from, handle_to, add_page, sub_page):
    return f"""
            QSlider::groove:horizontal {{
                border: 1px solid {border};
                height: 5px;
                background: {groove};
                margin: 0 0 -5px 0;
            }}

            QSlider::handle:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {handle_from}, stop:1 {handle_to});
                border: 1px solid {border};
                width: 10px;
                margin: -5px 0 -5px 0;
                border-radius: 3px;
            }}

            QSlider::add-page:horizontal {{
                background: {add_page};
                margin: 0 0 -5px 0;
            }}

            QSlider::sub-page:horizontal {{
                background: {sub_page};
                margin: 0 0 -5px 0;
            }}
            """


dark_zoom_slider_stylesheet = _zoom_slider_style("#444444", "#333333", "#666666", "#555555", "#555555", "#777777")
light_zoom_slider_stylesheet = _zoom_slider_style(
    "rgba(138,138,138,255)", "rgba(229,229,234,255)", "#FFFFFF", "rgba(199,199,204,255)", "#FFFFFF", "#e3e3e3")
