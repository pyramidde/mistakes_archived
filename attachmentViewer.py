
from pathlib import Path
import sys

from PyQt6.QtCore import QBuffer, QEvent, QIODevice, QPointF, Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget,
    QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
except ImportError:
    QPdfDocument = QPdfView = None


class AttachmentViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.image = QPixmap()
        self.image_scale = 1.0
        self.pdf_buffer = None
        self.auto_fit_images = True
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        fit_button = QPushButton("Fit width")
        fit_button.clicked.connect(self.fit_width)
        controls.addWidget(fit_button)
        controls.addStretch()
        layout.addLayout(controls)
        navigation = QHBoxLayout()
        self.previous_page_button = QPushButton("Previous")
        self.previous_page_button.clicked.connect(self.previous_page)
        self.page_input = QSpinBox()
        self.page_input.setRange(1, 1)
        self.page_input.setPrefix("Page ")
        self.page_input.valueChanged.connect(self.go_to_page)
        self.page_count = QLabel("/ 0")
        self.next_page_button = QPushButton("Next")
        self.next_page_button.clicked.connect(self.next_page)
        navigation.addWidget(self.previous_page_button)
        navigation.addWidget(self.page_input)
        navigation.addWidget(self.page_count)
        navigation.addWidget(self.next_page_button)
        self.pdf_navigation = QWidget()
        self.pdf_navigation.setLayout(navigation)
        layout.addWidget(self.pdf_navigation)
        self.views = QStackedWidget()
        layout.addWidget(self.views)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.views.addWidget(self.message)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_scroll = QScrollArea()
        self.image_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_scroll.setWidget(self.image_label)
        self.install_zoom_controls(self.image_scroll)
        self.views.addWidget(self.image_scroll)
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.views.addWidget(self.text_view)
        self.pdf_view = None
        if QPdfView is not None:
            self.pdf_document = QPdfDocument(self)
            self.pdf_view = QPdfView(self)
            self.pdf_view.setDocument(self.pdf_document)
            self.install_zoom_controls(self.pdf_view)
            self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self.pdf_document.statusChanged.connect(self.pdf_status_changed)
            self.pdf_document.pageCountChanged.connect(self.update_pdf_pages)
            self.pdf_view.pageNavigator().currentPageChanged.connect(self.sync_pdf_page)
            self.views.addWidget(self.pdf_view)
        self.clear()

    def clear(self):
        self.pdf_navigation.hide()
        if self.pdf_view is not None:
            self.pdf_document.close()
        if self.pdf_buffer is not None:
            self.pdf_buffer.close()
            self.pdf_buffer = None
        self.image = QPixmap()
        self.image_label.clear()
        self.text_view.clear()
        self.show_message("Select an attachment to view it here.")

    def show_message(self, text):
        self.message.setText(text)
        self.views.setCurrentWidget(self.message)

    def load_file(self, name, data):
        self.clear()
        extension = Path(name).suffix.lower()
        if extension == ".pdf" or data.lstrip().startswith(b"%PDF-"):
            if self.pdf_view is None:
                self.show_message("PDF viewing needs PyQt6-Pdf. Install the packages in requirements.txt.")
                return
            # Keep the in-memory file alive while Qt renders its pages.
            self.pdf_buffer = QBuffer()
            self.pdf_buffer.setData(data)
            self.pdf_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self.views.setCurrentWidget(self.pdf_view)
            self.pdf_navigation.show()
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self.pdf_document.load(self.pdf_buffer)
            return
        if self.image.loadFromData(data):
            self.views.setCurrentWidget(self.image_scroll)
            self.fit_width()
        elif extension in (".txt", ".md", ".csv", ".json", ".log", ".py"):
            self.text_view.setPlainText(data.decode("utf-8", errors="replace"))
            self.views.setCurrentWidget(self.text_view)
        else:
            self.show_message("No built-in viewer for this file type. You can still save a copy.")

    def pdf_status_changed(self, status):
        if status == QPdfDocument.Status.Error:
            self.pdf_navigation.hide()
            self.show_message("This PDF could not be opened. It may be damaged or password-protected.")

    def update_pdf_pages(self, count):
        self.page_input.blockSignals(True)
        self.page_input.setRange(1, max(1, count))
        self.page_input.setValue(1)
        self.page_input.blockSignals(False)
        self.page_count.setText(f"/ {count}")
        self.page_input.setEnabled(count > 0)
        self.previous_page_button.setEnabled(count > 1)
        self.next_page_button.setEnabled(count > 1)

    def sync_pdf_page(self, page):
        self.page_input.blockSignals(True)
        self.page_input.setValue(page + 1)
        self.page_input.blockSignals(False)

    def go_to_page(self, page):
        if self.pdf_view is not None and self.pdf_document.pageCount():
            self.pdf_view.pageNavigator().jump(page - 1, QPointF())

    def previous_page(self):
        self.page_input.setValue(self.page_input.value() - 1)

    def next_page(self):
        self.page_input.setValue(self.page_input.value() + 1)

    def install_zoom_controls(self, view):
        viewport = view.viewport()
        viewport.installEventFilter(self)
        # macOS supplies native trackpad gestures. Other platforms can also
        # deliver touch pinches through Qt's gesture recognizer.
        if sys.platform != "darwin":
            viewport.grabGesture(Qt.GestureType.PinchGesture)

    def eventFilter(self, watched, event):
        active = self.views.currentWidget()
        if active in (self.image_scroll, self.pdf_view) and watched is active.viewport():
            if event.type() == QEvent.Type.Wheel:
                modifiers = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
                if event.modifiers() & modifiers:
                    delta = event.pixelDelta().y() or event.angleDelta().y()
                    if delta:
                        self.zoom(1.25 ** (max(-480, min(480, delta)) / 120))
                    event.accept()
                    return True
            elif event.type() == QEvent.Type.NativeGesture:
                if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                    self.zoom(max(0.01, 1.0 + event.value()))
                    event.accept()
                    return True
            elif event.type() == QEvent.Type.Gesture:
                pinch = event.gesture(Qt.GestureType.PinchGesture)
                if pinch is not None:
                    self.zoom(pinch.scaleFactor() / (pinch.lastScaleFactor() or 1.0))
                    event.accept(pinch)
                    return True
        if (watched is self.image_scroll.viewport() and event.type() == QEvent.Type.Resize
                and self.auto_fit_images):
            QTimer.singleShot(0, self.fit_width)
        return super().eventFilter(watched, event)

    def fit_width(self):
        if self.views.currentWidget() is self.image_scroll and not self.image.isNull():
            self.auto_fit_images = True
            self.image_scale = max(0.05, (self.image_scroll.viewport().width() - 20) / self.image.width())
            self.update_image()
        elif self.pdf_view is not None and self.views.currentWidget() is self.pdf_view:
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def update_image(self):
        scaled = self.image.scaledToWidth(
            max(1, int(self.image.width() * self.image_scale)),
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())

    def zoom(self, factor):
        if self.views.currentWidget() is self.image_scroll:
            self.auto_fit_images = False
            self.image_scale = min(8.0, max(0.05, self.image_scale * factor))
            self.update_image()
        elif self.pdf_view is not None and self.views.currentWidget() is self.pdf_view:
            scale = self.pdf_view.zoomFactor()
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
            self.pdf_view.setZoomFactor(min(8.0, max(0.05, scale * factor)))

