import sys
import sqlite3
import databaseConnect

from pathlib import Path
from attachmentViewer import AttachmentViewer
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)


def make_number_input(maximum):
    field = QLineEdit()
    field.setPlaceholderText("0")
    field.setValidator(QIntValidator(0, maximum, field))
    return field


class MistakesArchive(QWidget):
    def __init__(self):
        super().__init__()
        self.pending_files = []
        self.setup_window()
        self.create_home_page()
        self.create_manage_page()
        self.create_subject_page()
        self.create_paper_page()
        self.create_mistakes_page()
        self.refresh_subjects()

    def setup_window(self):
        self.setWindowTitle("Mistakes Archive")
        self.resize(900, 600)
        layout = QVBoxLayout(self)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages)

    def create_home_page(self):
        self.home_page = QWidget()
        layout = QVBoxLayout(self.home_page)
        layout.addWidget(QLabel("Subjects and levels — click an entry to see its mistakes"))
        self.subject_list = QListWidget()
        self.subject_list.itemClicked.connect(self.show_course_mistakes)
        layout.addWidget(self.subject_list)

        buttons = QHBoxLayout()
        self.paper_button = QPushButton("Add paper and mistake")
        self.paper_button.clicked.connect(self.show_paper_page)
        buttons.addWidget(self.paper_button)
        layout.addLayout(buttons)
        self.subject_summary = QLabel("")
        self.subject_summary.setWordWrap(True)
        layout.addWidget(self.subject_summary)
        self.manage_button = QPushButton("Manage subjects…")
        self.manage_button.clicked.connect(self.show_manage_page)
        layout.addWidget(self.manage_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.pages.addWidget(self.home_page)

    def create_manage_page(self):
        self.manage_page = QWidget()
        layout = QVBoxLayout(self.manage_page)
        layout.addWidget(QLabel("Manage subjects and levels"))
        self.manage_list = QListWidget()
        layout.addWidget(self.manage_list)
        self.manage_status = QLabel("")
        self.manage_status.setWordWrap(True)
        layout.addWidget(self.manage_status)
        buttons = QHBoxLayout()
        self.subject_button = QPushButton("Add subject")
        self.subject_button.clicked.connect(self.show_subject_page)
        self.delete_button = QPushButton("Delete selected subject / level")
        self.delete_button.clicked.connect(self.delete_selected_subject)
        back = QPushButton("Back to subjects")
        back.clicked.connect(self.show_home_page)
        buttons.addWidget(self.subject_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(back)
        layout.addLayout(buttons)
        self.pages.addWidget(self.manage_page)

    def show_manage_page(self):
        self.refresh_subjects()
        self.pages.setCurrentWidget(self.manage_page)

    def create_subject_page(self):
        self.subject_page = QWidget()
        layout = QVBoxLayout(self.subject_page)
        layout.addWidget(QLabel("Add subject"))
        form = QFormLayout()
        self.subject_input = QLineEdit()
        self.level_input = QComboBox()
        self.level_input.addItems(["Higher Level", "Standard Level"])
        form.addRow("Subject:", self.subject_input)
        form.addRow("Level:", self.level_input)
        layout.addLayout(form)
        self.subject_status = QLabel("Enter a subject and choose its level.")
        self.subject_status.setWordWrap(True)
        layout.addWidget(self.subject_status)
        self.insert_button = QPushButton("Insert")
        self.insert_button.clicked.connect(self.insert_subject)
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.show_manage_page)
        layout.addWidget(self.insert_button)
        layout.addWidget(self.back_button)
        self.pages.addWidget(self.subject_page)

    def show_subject_page(self):
        self.pages.setCurrentWidget(self.subject_page)
        self.subject_input.setFocus()

    def create_paper_page(self):
        self.paper_page = QWidget()
        layout = QVBoxLayout(self.paper_page)
        layout.addWidget(QLabel("Add paper and mistake"))
        layout.addWidget(QLabel("Optional text becomes N/A; blank numbers become 0 (unspecified)."))

        # Put the small fields on the left and question/files on the right.
        columns = QHBoxLayout()
        form = QFormLayout()
        self.course_input = QComboBox()
        self.paper_number_input = make_number_input(99)
        self.question_number_input = QLineEdit()
        self.question_number_input.setPlaceholderText("e.g. 3(b)(ii), or leave blank")
        self.difficulty_input = make_number_input(5)
        self.max_marks_input = make_number_input(1000)
        self.marks_earned_input = make_number_input(1000)
        form.addRow("Subject / level:", self.course_input)
        form.addRow("Paper number:", self.paper_number_input)
        form.addRow("Question number:", self.question_number_input)
        form.addRow("Difficulty (1–5):", self.difficulty_input)
        form.addRow("Maximum marks:", self.max_marks_input)
        form.addRow("Marks earned:", self.marks_earned_input)
        columns.addLayout(form, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Question text (optional)"))
        self.question_text_input = QTextEdit()
        self.question_text_input.setPlaceholderText("Type a question, attach a file/image, or both.")
        right.addWidget(self.question_text_input)
        self.pending_file_list = QListWidget()
        right.addWidget(self.pending_file_list)
        file_buttons = QHBoxLayout()
        self.attach_button = QPushButton("Attach files / images")
        self.attach_button.clicked.connect(self.choose_files)
        self.clear_files_button = QPushButton("Clear files")
        self.clear_files_button.clicked.connect(self.clear_files)
        file_buttons.addWidget(self.attach_button)
        file_buttons.addWidget(self.clear_files_button)
        right.addLayout(file_buttons)
        columns.addLayout(right, 1)
        layout.addLayout(columns)

        self.paper_status = QLabel("")
        self.paper_status.setWordWrap(True)
        layout.addWidget(self.paper_status)
        buttons = QHBoxLayout()
        self.paper_insert_button = QPushButton("Insert")
        self.paper_insert_button.clicked.connect(self.insert_paper_mistake)
        self.paper_back_button = QPushButton("Back")
        self.paper_back_button.clicked.connect(self.show_home_page)
        buttons.addWidget(self.paper_insert_button)
        buttons.addWidget(self.paper_back_button)
        layout.addLayout(buttons)
        self.pages.addWidget(self.paper_page)

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach files or images", "",
            "All files (*);;Images (*.png *.jpg *.jpeg *.webp *.bmp);;PDF files (*.pdf)",
        )
        for path in paths:
            if path not in self.pending_files:
                self.pending_files.append(path)
                self.pending_file_list.addItem(Path(path).name)

    def clear_files(self):
        self.pending_files.clear()
        self.pending_file_list.clear()

    def show_paper_page(self):
        selected = self.subject_list.currentItem()
        selected_id = (selected.data(Qt.ItemDataRole.UserRole)
                       if selected else self.course_input.currentData())
        self.course_input.clear()
        self.paper_insert_button.setEnabled(False)
        self.pages.setCurrentWidget(self.paper_page)
        try:
            courses = databaseConnect.get_courses()
        except sqlite3.Error as error:
            self.paper_status.setText(f"Could not load courses: {error}")
            return
        for course_id, subject, level in courses:
            self.course_input.addItem(f"{subject} — {level}", course_id)
        index = self.course_input.findData(selected_id)
        if index >= 0:
            self.course_input.setCurrentIndex(index)
        self.paper_insert_button.setEnabled(bool(courses))
        self.paper_status.setText(
            "Only the subject/course is required. Files are stored when you click Insert."
            if courses else "Add a subject through Manage subjects first, then return here."
        )

    def insert_paper_mistake(self):
        number_fields = [self.paper_number_input, self.difficulty_input,
                         self.max_marks_input, self.marks_earned_input]
        if any(field.text().strip() and not field.hasAcceptableInput() for field in number_fields):
            self.paper_status.setText("Use whole numbers in the allowed ranges (difficulty 0–5).")
            return
        try:
            paper_id, mistake_id = databaseConnect.insert_paper_mistake(
                self.course_input.currentData(),
                int(self.paper_number_input.text().strip() or 0),
                self.question_number_input.text(),
                self.question_text_input.toPlainText(),
                int(self.difficulty_input.text().strip() or 0),
                int(self.max_marks_input.text().strip() or 0),
                int(self.marks_earned_input.text().strip() or 0),
                self.pending_files,
            )
        except (sqlite3.Error, ValueError, OSError) as error:
            self.paper_status.setText(f"Could not insert: {error}")
            return
        self.subject_summary.setText(f"Inserted paper {paper_id} and mistake {mistake_id}.")
        self.question_number_input.clear()
        self.question_text_input.clear()
        for field in number_fields:
            field.clear()
        self.clear_files()
        self.show_home_page()

    def create_mistakes_page(self):
        self.mistakes_page = QWidget()
        layout = QVBoxLayout(self.mistakes_page)
        self.mistakes_title = QLabel("")
        layout.addWidget(self.mistakes_title)
        columns = QHBoxLayout()
        self.mistake_list = QListWidget()
        self.mistake_list.currentItemChanged.connect(self.show_mistake_details)
        columns.addWidget(self.mistake_list, 1)
        details = QVBoxLayout()
        self.mistake_details = QTextEdit()
        self.mistake_details.setReadOnly(True)
        self.mistake_details.setMaximumHeight(110)
        details.addWidget(self.mistake_details)
        details.addWidget(QLabel("Attachments — select a file to view"))
        self.attachment_list = QListWidget()
        self.attachment_list.currentItemChanged.connect(self.preview_attachment)
        self.attachment_list.setMaximumHeight(85)
        details.addWidget(self.attachment_list)
        self.attachment_viewer = AttachmentViewer()
        details.addWidget(self.attachment_viewer, 1)
        self.export_button = QPushButton("Save selected attachment as…")
        self.export_button.clicked.connect(self.export_attachment)
        details.addWidget(self.export_button)
        columns.addLayout(details, 2)
        layout.addLayout(columns)
        self.mistakes_status = QLabel("")
        self.mistakes_status.setWordWrap(True)
        layout.addWidget(self.mistakes_status)
        buttons = QHBoxLayout()
        add_button = QPushButton("Add paper and mistake")
        add_button.clicked.connect(self.show_paper_page)
        back_button = QPushButton("Back to subjects")
        back_button.clicked.connect(self.show_home_page)
        buttons.addWidget(add_button)
        buttons.addWidget(back_button)
        layout.addLayout(buttons)
        self.pages.addWidget(self.mistakes_page)

    def show_course_mistakes(self, item):
        self.mistakes_title.setText(item.text())
        self.mistake_list.clear()
        self.mistake_details.clear()
        self.attachment_list.clear()
        self.attachment_viewer.clear()
        self.mistakes_status.clear()
        self.pages.setCurrentWidget(self.mistakes_page)
        try:
            rows = databaseConnect.get_course_mistakes(item.data(Qt.ItemDataRole.UserRole))
        except sqlite3.Error as error:
            self.mistakes_status.setText(f"Could not load mistakes: {error}")
            return
        for row in rows:
            entry = QListWidgetItem(
                f"#{row['MistakeID']} | Paper {row['PaperNumber']} | Q {row['QuestionNumber']}"
                f" | {row['MarksEarned']}/{row['MaxMarks']} | Files: {row['FileCount']}"
            )
            entry.setData(Qt.ItemDataRole.UserRole, row)
            self.mistake_list.addItem(entry)
        if rows:
            self.mistake_list.setCurrentRow(0)
        else:
            self.mistakes_status.setText("No mistakes for this subject/level yet.")

    def show_mistake_details(self, item, previous=None):
        self.mistake_details.clear()
        self.attachment_list.clear()
        self.attachment_viewer.clear()
        if item is None:
            return
        row = item.data(Qt.ItemDataRole.UserRole)
        self.mistake_details.setPlainText(
            f"Mistake #{row['MistakeID']}\nPaper: {row['PaperNumber']}\n"
            f"Question: {row['QuestionNumber']}\nDifficulty: {row['Difficulty']}\n"
            f"Marks: {row['MarksEarned']}/{row['MaxMarks']}\n\n{row['QuestionText']}"
        )
        try:
            for attachment_id, name in databaseConnect.get_attachments(row['MistakeID']):
                entry = QListWidgetItem(name)
                entry.setData(Qt.ItemDataRole.UserRole, attachment_id)
                self.attachment_list.addItem(entry)
            if self.attachment_list.count():
                self.attachment_list.setCurrentRow(0)
        except sqlite3.Error as error:
            self.mistakes_status.setText(f"Could not load attachments: {error}")

    def preview_attachment(self, item, previous=None):
        self.attachment_viewer.clear()
        if item is None:
            return
        try:
            attachment = databaseConnect.get_attachment(item.data(Qt.ItemDataRole.UserRole))
            if attachment is None:
                self.attachment_viewer.show_message("Attachment no longer exists.")
                return
            self.attachment_viewer.load_file(*attachment)
        except sqlite3.Error as error:
            self.mistakes_status.setText(f"Could not load attachment: {error}")

    def export_attachment(self):
        item = self.attachment_list.currentItem()
        if item is None:
            self.mistakes_status.setText("Select an attachment first.")
            return
        try:
            attachment = databaseConnect.get_attachment(item.data(Qt.ItemDataRole.UserRole))
            if attachment is None:
                self.mistakes_status.setText("Attachment no longer exists.")
                return
            name, data = attachment
            path, _ = QFileDialog.getSaveFileName(self, "Save attachment", Path(name).name)
            if path:
                Path(path).write_bytes(data)
                self.mistakes_status.setText(f"Saved: {path}")
        except (sqlite3.Error, OSError) as error:
            self.mistakes_status.setText(f"Could not save attachment: {error}")

    def show_home_page(self):
        self.refresh_subjects()
        self.pages.setCurrentWidget(self.home_page)

    def refresh_subjects(self):
        selected = self.subject_list.currentItem()
        selected_id = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        try:
            courses = databaseConnect.get_courses()
        except sqlite3.Error as error:
            self.subject_summary.setText(f"Could not load subjects: {error}")
            return
        self.subject_list.clear()
        managed = self.manage_list.currentItem()
        managed_id = managed.data(Qt.ItemDataRole.UserRole) if managed else None
        self.manage_list.clear()
        for course_id, subject, level in courses:
            item = QListWidgetItem(f"{subject} — {level}")
            item.setData(Qt.ItemDataRole.UserRole, course_id)
            self.subject_list.addItem(item)
            if course_id == selected_id:
                self.subject_list.setCurrentItem(item)
            managed_item = QListWidgetItem(f"{subject} — {level}")
            managed_item.setData(Qt.ItemDataRole.UserRole, course_id)
            self.manage_list.addItem(managed_item)
            if course_id == managed_id:
                self.manage_list.setCurrentItem(managed_item)
        if not courses:
            self.subject_summary.setText("No subjects saved. Open Manage subjects to add one.")

    def delete_selected_subject(self):
        item = self.manage_list.currentItem()
        if item is None:
            self.manage_status.setText("Select a subject and level to delete.")
            return
        name = item.text()
        answer = QMessageBox.question(
            self, "Delete subject / course?",
            f"Are you sure you want to delete {name}?\n\n"
            "All papers, mistakes and attachments linked to this course will also be deleted.\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = databaseConnect.delete_course(item.data(Qt.ItemDataRole.UserRole))
        except sqlite3.IntegrityError:
            self.manage_status.setText("Cannot delete: another database record still references this course.")
            return
        except sqlite3.Error as error:
            self.manage_status.setText(f"Could not delete: {error}")
            return
        self.manage_status.setText(f"Deleted {name} and its linked records." if deleted else "Entry already removed.")
        self.subject_summary.clear()
        self.refresh_subjects()

    def insert_subject(self):
        subject = self.subject_input.text().strip()
        try:
            inserted = databaseConnect.insert_subject(subject, self.level_input.currentText())
        except (sqlite3.Error, ValueError) as error:
            self.subject_status.setText(f"Could not insert: {error}")
            return
        if not inserted:
            self.subject_status.setText("That subject and level already exist.")
            return
        self.subject_summary.setText(f"Inserted: {subject} — {self.level_input.currentText()}")
        self.subject_input.clear()
        self.subject_status.setText("Enter a subject and choose its level.")
        self.show_manage_page()


def main():
    app = QApplication(sys.argv)
    window = MistakesArchive()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
