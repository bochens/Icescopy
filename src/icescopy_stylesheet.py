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

darkmode_toolbar_style_sheet = """
                QToolButton {
                    border-radius: 5px;      /* Rounded corners */
                    width: 24px;             /* Width */
                    height: 24px;            /* Height */
                    background-color: transparent;
                    padding: 5px;
                }
                QToolButton:hover {
                    background-color: rgba(10, 132, 255, 180)
                }
                QToolButton:pressed {
                    background-color: rgba(10, 132, 255, 120);
                }
                QToolButton:checked {
                    background-color: dimgray;
                }             
                QToolButton:checked:hover {
                    background-color: rgba(10, 132, 255, 180)
                }
                QToolButton:checked:pressed {
                    background-color: rgba(10, 132, 255, 120)
                }
                QToolButton::text {
                    display: inline;
                }
            """

light_mode_toolbar_style_sheet = """
                QToolButton {
                    border-radius: 5px;      /* Rounded corners */
                    width: 24px;             /* Width */
                    height: 24px;            /* Height */
                    background-color: transparent;
                    padding: 5px;
                }
                QToolButton:hover {
                    background-color: rgba(0, 122, 255, 150)
                }
                QToolButton:pressed {
                    background-color: rgba(0, 122, 255, 200);
                }
                QToolButton:checked {
                    background-color: darkgray;
                }     
                QToolButton:checked:hover {
                    background-color: rgba(0, 122, 255, 150)
                }   
                QToolButton:checked:pressed {
                    background-color: rgba(0, 122, 255, 200)
                }            
                QToolButton::text {
                    display: inline;
                }
            """

slider_handle_path = os.path.abspath(os.path.join(ui_images_dir, "slider_handle.png"))
if IS_WINDOWS:
    slider_url = QUrl.fromLocalFile(slider_handle_path).toString()
    dark_mode_time_line_slider_style = f"""
                    QSlider::groove:horizontal {{
                        border: 1px solid #999999;
                        background: #323232;
                        height: 6px;
                        border-radius: 3px;
                        margin: 0px 0px 6px 0px;
                    }}

                    QSlider::add-page:horizontal {{
                        border: 1px solid #999999;
                        background: #323232;
                        height: 6px;
                        border-radius: 3px;
                        margin: 0px 0px 6px 0px;
                    }}
                    QSlider::sub-page:horizontal {{
                        border: 1px solid #999999;
                        background: rgba(80, 80, 80, 255);
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
    light_mode_time_line_slider_style = f"""
                    QSlider::groove:horizontal {{
                        border: 1px solid #212121;
                        background: #ececec;
                        height: 6px;
                        border-radius: 3px;
                        margin: 0px 0px 6px 0px;
                    }}

                    QSlider::add-page:horizontal {{
                        border: 1px solid #212121;
                        background: #FFFFFF;
                        height: 6px;
                        border-radius: 3px;
                        margin: 0px 0px 6px 0px;
                    }}
                    QSlider::sub-page:horizontal {{
                        border: 1px solid #212121;
                        background: #ececec;
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
else:
    slider_url = slider_handle_path.replace(os.sep, "/")
    dark_mode_time_line_slider_style = f"""
                    QSlider::groove:horizontal {{
                        border: 1px solid #999999;
                        background: #323232;
                        height: 6px;
                        border-radius: 3px;
                        margin-bottom: 10px;
                    }}

                    QSlider::add-page:horizontal {{
                        border: 1px solid #999999;
                        background: #323232;
                        height: 6px;
                        border-radius: 3px;
                        margin-bottom: 10px;
                    }}
                    QSlider::sub-page:horizontal {{
                        border: 1px solid #999999;
                        background: rgba(80, 80, 80, 255);
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
    light_mode_time_line_slider_style = f"""
                    QSlider::groove:horizontal {{
                        border: 1px solid #212121;
                        background: #ececec;
                        height: 6px;
                        border-radius: 3px;
                        margin-bottom: 10px;
                    }}

                    QSlider::add-page:horizontal {{
                        border: 1px solid #212121;
                        background: #FFFFFF;
                        height: 6px;
                        border-radius: 3px;
                        margin-bottom: 10px;
                    }}
                    QSlider::sub-page:horizontal {{
                        border: 1px solid #212121;
                        background: #ececec;
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

dark_zoom_slider_stylesheet = """
            QSlider::groove:horizontal {
                border: 1px solid #444444;
                height: 5px;
                background: #333333;
                margin: 0 0 -5px 0;
            }

            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #666666, stop:1 #555555);
                border: 1px solid #444444;
                width: 10px;
                margin: -5px 0 -5px 0;
                border-radius: 3px;
            }

            QSlider::add-page:horizontal {
                background: #555555;
                margin: 0 0 -5px 0;
            }

            QSlider::sub-page:horizontal {
                background: #777777;
                margin: 0 0 -5px 0;
            }
            """

light_zoom_slider_stylesheet = """
            QSlider::groove:horizontal {
                border: 1px solid rgba(138,138,138,255);
                height: 5px;
                background: rgba(229,229,234,255);
                margin: 0 0 -5px 0;
            }

            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFFFFF, stop:1 rgba(199,199,204,255));
                border: 1px solid rgba(138,138,138,255);
                width: 10px;
                margin: -5px 0 -5px 0;
                border-radius: 3px;
            }

            QSlider::add-page:horizontal {
                background: #FFFFFF;
                margin: 0 0 -5px 0;
            }

            QSlider::sub-page:horizontal {
                background: #e3e3e3;
                margin: 0 0 -5px 0;
            }
            """
