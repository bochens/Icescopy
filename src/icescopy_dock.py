from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import QSize, Qt


class DockTitleBar(QWidget):
    def __init__(self, dock_widget, title, parent=None):
        super().__init__(parent or dock_widget)
        self.dock_widget = dock_widget
        self.setFixedHeight(26)
        self.setAutoFillBackground(True)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        header_row = QWidget(self)
        layout = QHBoxLayout(header_row)
        layout.setContentsMargins(8, 1, 8, 3)
        layout.setSpacing(4)

        self.button_row = QWidget(header_row)
        button_layout = QHBoxLayout(self.button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)

        self.close_button = QToolButton(self.button_row)
        self.close_button.setAutoRaise(True)
        self.close_button.setFixedSize(14, 14)
        self.close_button.setIconSize(QSize(10, 10))
        self.close_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.close_button.clicked.connect(self.dock_widget.close)

        self.float_button = QToolButton(self.button_row)
        self.float_button.setAutoRaise(True)
        self.float_button.setFixedSize(14, 14)
        self.float_button.setIconSize(QSize(10, 10))
        self.float_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarNormalButton))
        self.float_button.clicked.connect(self.toggle_floating)

        button_layout.addWidget(self.close_button)
        button_layout.addWidget(self.float_button)

        self.title_label = QLabel(str(title), header_row)
        title_font = QFont(self.title_label.font())
        title_font.setPointSize(max(title_font.pointSize(), 12))
        title_font.setWeight(QFont.Medium)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)

        self.right_spacer = QWidget(header_row)
        self.right_spacer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        layout.addWidget(self.button_row, 0)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.right_spacer, 0)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setStyleSheet("color: rgba(0, 0, 0, 40);")

        outer_layout.addWidget(header_row)
        outer_layout.addWidget(separator)

        self.left_edge_cover = QFrame(self)
        self.left_edge_cover.setFrameShape(QFrame.NoFrame)
        self.left_edge_cover.setStyleSheet("background: palette(window);")
        self.left_edge_cover.hide()

        self.right_edge_cover = QFrame(self)
        self.right_edge_cover.setFrameShape(QFrame.NoFrame)
        self.right_edge_cover.setStyleSheet("background: palette(window);")
        self.right_edge_cover.hide()

        self.dock_widget.featuresChanged.connect(self.refresh_buttons)
        self.dock_widget.topLevelChanged.connect(self.refresh_buttons)
        try:
            self.dock_widget.dockLocationChanged.connect(self.refresh_buttons)
        except Exception:
            pass
        self.refresh_buttons()

    def toggle_floating(self):
        self.dock_widget.setFloating(not self.dock_widget.isFloating())

    def refresh_buttons(self, *args):
        features = self.dock_widget.features()
        self.close_button.setVisible(bool(features & QDockWidget.DockWidgetClosable))
        self.float_button.setVisible(bool(features & QDockWidget.DockWidgetFloatable))
        self.right_spacer.setFixedWidth(self.button_row.sizeHint().width())
        float_icon = (
            QStyle.SP_TitleBarNormalButton
            if self.dock_widget.isFloating()
            else QStyle.SP_TitleBarMaxButton
        )
        self.float_button.setIcon(self.style().standardIcon(float_icon))
        self.update_edge_covers()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_edge_covers()

    def update_edge_covers(self):
        left_visible = False
        right_visible = False
        main_window = self.dock_widget.parentWidget()
        if isinstance(main_window, QMainWindow) and not self.dock_widget.isFloating():
            try:
                dock_area = main_window.dockWidgetArea(self.dock_widget)
            except Exception:
                dock_area = Qt.NoDockWidgetArea
            if dock_area == Qt.LeftDockWidgetArea:
                right_visible = True
            elif dock_area == Qt.RightDockWidgetArea:
                left_visible = True

        cover_width = 2
        self.left_edge_cover.setGeometry(0, 0, cover_width, self.height())
        self.right_edge_cover.setGeometry(
            max(0, self.width() - cover_width),
            0,
            cover_width,
            self.height(),
        )
        self.left_edge_cover.setVisible(left_visible)
        self.right_edge_cover.setVisible(right_visible)

    def mousePressEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        event.ignore()

    def mouseDoubleClickEvent(self, event):
        event.ignore()
