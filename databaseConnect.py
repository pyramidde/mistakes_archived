import sqlite3
DB_PATH = 'database/mistakes_dB.db'


from pathlib import Path
import sqlite3


def connect_database():
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            connection.execute('''
                CREATE TABLE IF NOT EXISTS Subjects (
                    SubjectID INTEGER PRIMARY KEY,
                    Subject TEXT NOT NULL
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS Course (
                    CourseID INTEGER PRIMARY KEY,
                    SubjectID INTEGER NOT NULL,
                    Level TEXT NOT NULL,
                    FOREIGN KEY (SubjectID) REFERENCES Subjects(SubjectID)
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS Paper (
                    PaperID INTEGER PRIMARY KEY,
                    CourseID INTEGER NOT NULL,
                    PaperNumber NUMERIC NOT NULL,
                    QuestionNumber TEXT NOT NULL,
                    QuestionText TEXT NOT NULL,
                    Difficulty NUMERIC NOT NULL,
                    MaxMarks NUMERIC NOT NULL,
                    FOREIGN KEY (CourseID) REFERENCES Course(CourseID)
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS Mistake (
                    MistakeID INTEGER PRIMARY KEY,
                    PaperID INTEGER NOT NULL,
                    MarksEarned INTEGER NOT NULL,
                    FOREIGN KEY (PaperID) REFERENCES Paper(PaperID)
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS Attachment (
                    AttachmentID INTEGER PRIMARY KEY,
                    MistakeID INTEGER NOT NULL,
                    FileName TEXT NOT NULL,
                    FileData BLOB NOT NULL,
                    FOREIGN KEY (MistakeID) REFERENCES Mistake(MistakeID)
                )
            ''')
        return connection
    except sqlite3.Error:
        connection.close()
        raise


def get_courses():
    """Return the saved subject/level entries with their course IDs."""
    connection = connect_database()
    try:
        return connection.execute('''
            SELECT Course.CourseID, Subjects.Subject, Course.Level
            FROM Course
            JOIN Subjects ON Subjects.SubjectID = Course.SubjectID
            ORDER BY Subjects.Subject COLLATE NOCASE, Course.Level, Course.CourseID
        ''').fetchall()
    finally:
        connection.close()


def insert_paper_mistake(course_id, paper_number, question_number, question_text,
                         difficulty, max_marks, marks_earned, file_paths=()):
    """Store a Paper, Mistake and any attached files in one transaction."""
    question_number = (question_number or "").strip() or "N/A"
    question_text = (question_text or "").strip() or "N/A"
    paper_number = paper_number or 0
    difficulty = difficulty or 0
    max_marks = max_marks or 0
    marks_earned = marks_earned or 0
    if course_id is None:
        raise ValueError("Add and select a subject/course first.")
    if paper_number < 0 or not 0 <= difficulty <= 5:
        raise ValueError("Paper number cannot be negative; difficulty must be 0–5.")
    if max_marks < 0 or marks_earned < 0:
        raise ValueError("Marks cannot be negative.")
    if max_marks > 0 and marks_earned > max_marks:
        raise ValueError("Marks earned cannot exceed maximum marks.")

    # Read before inserting: an unreadable file must not leave a partial record.
    files = [(Path(path).name, Path(path).read_bytes()) for path in file_paths]

    connection = connect_database()
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT CourseID FROM Course WHERE CourseID = ?", (course_id,)
            ).fetchone() is None:
                raise ValueError("That course no longer exists. Reopen this page and select a course.")
            # Explicit IDs work with both INTEGER and existing NUMERIC keys.
            paper_id = connection.execute(
                "SELECT COALESCE(MAX(PaperID), 0) + 1 FROM Paper"
            ).fetchone()[0]
            mistake_id = connection.execute(
                "SELECT COALESCE(MAX(MistakeID), 0) + 1 FROM Mistake"
            ).fetchone()[0]
            connection.execute('''
                INSERT INTO Paper (PaperID, CourseID, PaperNumber, QuestionNumber,
                                   QuestionText, Difficulty, MaxMarks)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (paper_id, course_id, paper_number, question_number,
                  question_text, difficulty, max_marks))
            connection.execute(
                "INSERT INTO Mistake (MistakeID, PaperID, MarksEarned) VALUES (?, ?, ?)",
                (mistake_id, paper_id, marks_earned),
            )
            connection.executemany(
                "INSERT INTO Attachment (MistakeID, FileName, FileData) VALUES (?, ?, ?)",
                [(mistake_id, name, data) for name, data in files],
            )
        return paper_id, mistake_id
    finally:
        connection.close()


def get_course_mistakes(course_id):
    connection = connect_database()
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute('''
            SELECT m.MistakeID, p.PaperNumber, p.QuestionNumber, p.QuestionText,
                   p.Difficulty, p.MaxMarks, m.MarksEarned,
                   (SELECT COUNT(*) FROM Attachment a
                    WHERE a.MistakeID = m.MistakeID) AS FileCount
            FROM Mistake m JOIN Paper p ON p.PaperID = m.PaperID
            WHERE p.CourseID = ? ORDER BY m.MistakeID DESC
        ''', (course_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_attachments(mistake_id):
    connection = connect_database()
    try:
        return connection.execute(
            "SELECT AttachmentID, FileName FROM Attachment WHERE MistakeID = ? ORDER BY AttachmentID",
            (mistake_id,),
        ).fetchall()
    finally:
        connection.close()


def get_attachment(attachment_id):
    connection = connect_database()
    try:
        return connection.execute(
            "SELECT FileName, FileData FROM Attachment WHERE AttachmentID = ?",
            (attachment_id,),
        ).fetchone()
    finally:
        connection.close()


def delete_course(course_id):
    """Delete a course and its attachments, mistakes and papers atomically."""
    connection = connect_database()
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT SubjectID FROM Course WHERE CourseID = ?", (course_id,)
            ).fetchone()
            if row is None:
                return False
            connection.execute('''
                DELETE FROM Attachment WHERE MistakeID IN (
                    SELECT m.MistakeID FROM Mistake m
                    JOIN Paper p ON p.PaperID = m.PaperID WHERE p.CourseID = ?
                )
            ''', (course_id,))
            connection.execute('''
                DELETE FROM Mistake WHERE PaperID IN (
                    SELECT PaperID FROM Paper WHERE CourseID = ?
                )
            ''', (course_id,))
            connection.execute("DELETE FROM Paper WHERE CourseID = ?", (course_id,))
            connection.execute("DELETE FROM Course WHERE CourseID = ?", (course_id,))
            connection.execute('''
                DELETE FROM Subjects WHERE SubjectID = ?
                AND NOT EXISTS (SELECT 1 FROM Course WHERE SubjectID = ?)
            ''', (row[0], row[0]))
        return True
    finally:
        connection.close()


def insert_subject(subject, level):
    """Insert a subject/course pair. Return False if it already exists."""
    subject = subject.strip()
    if not subject:
        raise ValueError("Enter a subject first.")
    if level not in ("Higher Level", "Standard Level"):
        raise ValueError("Choose a valid level.")

    connection = connect_database()
    try:
        with connection:
            # Keep ID allocation and both inserts in one transaction.
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT SubjectID FROM Subjects WHERE lower(trim(Subject)) = lower(?)",
                (subject,),
            ).fetchone()

            if row:
                subject_id = row[0]
            else:
                # Explicit IDs also support the NUMERIC primary keys in your diagram.
                subject_id = connection.execute(
                    "SELECT COALESCE(MAX(SubjectID), 0) + 1 FROM Subjects"
                ).fetchone()[0]
                connection.execute(
                    "INSERT INTO Subjects (SubjectID, Subject) VALUES (?, ?)",
                    (subject_id, subject),
                )

            existing = connection.execute(
                "SELECT CourseID FROM Course WHERE SubjectID = ? AND Level = ?",
                (subject_id, level),
            ).fetchone()
            if existing:
                return False

            course_id = connection.execute(
                "SELECT COALESCE(MAX(CourseID), 0) + 1 FROM Course"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO Course (CourseID, SubjectID, Level) VALUES (?, ?, ?)",
                (course_id, subject_id, level),
            )
        return True
    finally:
        connection.close()
