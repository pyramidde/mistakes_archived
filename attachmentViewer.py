"""Reusable in-app viewer for saved images, PDFs and plain text files."""

from pathlib import Path

from PyQt6.QtCore import QBuffer, QIODevice, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget,
    QTextEdit, QVBoxLayout, QWidget,
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
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        for title, action in [("Zoom +", self.zoom_in), ("Zoom −", self.zoom_out),
                              ("Fit width", self.fit_width)]:
            button = QPushButton(title)
            button.clicked.connect(action)
            controls.addWidget(button)
        layout.addLayout(controls)
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
        self.views.addWidget(self.image_scroll)
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.views.addWidget(self.text_view)
        self.pdf_view = None
        if QPdfView is not None:
            self.pdf_document = QPdfDocument(self)
            self.pdf_view = QPdfView(self)
            self.pdf_view.setDocument(self.pdf_document)
            self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self.pdf_document.statusChanged.connect(self.pdf_status_changed)
            self.views.addWidget(self.pdf_view)
        self.clear()

    def clear(self):
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
            self.show_message("This PDF could not be opened. It may be damaged or password-protected.")

    def fit_width(self):
        if self.views.currentWidget() is self.image_scroll and not self.image.isNull():
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
            self.image_scale = min(8.0, max(0.05, self.image_scale * factor))
            self.update_image()
        elif self.pdf_view is not None and self.views.currentWidget() is self.pdf_view:
            scale = self.pdf_view.zoomFactor()
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
            self.pdf_view.setZoomFactor(min(8.0, max(0.05, scale * factor)))

    def zoom_in(self):
        self.zoom(1.25)

    def zoom_out(self):
        self.zoom(0.8)
