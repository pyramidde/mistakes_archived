
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
                CREATE TABLE IF NOT EXISTS Exercise (
                    ExerciseID INTEGER PRIMARY KEY,
                    CourseID INTEGER NOT NULL,
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
                    PaperID INTEGER,
                    MarksEarned INTEGER NOT NULL,
                    ExerciseID INTEGER,
                    FOREIGN KEY (PaperID) REFERENCES Paper(PaperID),
                    FOREIGN KEY (ExerciseID) REFERENCES Exercise(ExerciseID),
                    CHECK ((PaperID IS NOT NULL) != (ExerciseID IS NOT NULL))
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
        upgrade_mistake_table(connection)
        return connection
    except sqlite3.Error:
        connection.close()
        raise


def upgrade_mistake_table(connection):
    """Support databases made by the older, paper-only version of the app."""
    columns = {row[1]: row for row in connection.execute('PRAGMA table_info(Mistake)')}
    if 'ExerciseID' not in columns:
        with connection:
            connection.execute('ALTER TABLE Mistake ADD COLUMN ExerciseID INTEGER REFERENCES Exercise(ExerciseID)')
    if not columns['PaperID'][3]:
        return
    if set(columns) - {'MistakeID', 'PaperID', 'MarksEarned', 'ExerciseID'}:
        raise sqlite3.OperationalError('Make PaperID nullable in your Mistake table before using exercises.')
    # Rebuild the old NOT NULL PaperID column without dropping attachments.
    connection.execute('PRAGMA foreign_keys = OFF')
    try:
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            definitions = connection.execute("""
                SELECT sql FROM sqlite_master WHERE tbl_name = 'Mistake'
                AND type IN ('index', 'trigger') AND sql IS NOT NULL
            """).fetchall()
            connection.execute('''CREATE TABLE Mistake_upgrade (
                MistakeID INTEGER PRIMARY KEY, PaperID INTEGER,
                MarksEarned INTEGER NOT NULL, ExerciseID INTEGER,
                FOREIGN KEY (PaperID) REFERENCES Paper(PaperID),
                FOREIGN KEY (ExerciseID) REFERENCES Exercise(ExerciseID),
                CHECK ((PaperID IS NOT NULL) != (ExerciseID IS NOT NULL))
            )''')
            connection.execute('''INSERT INTO Mistake_upgrade
                SELECT MistakeID, PaperID, MarksEarned, ExerciseID FROM Mistake''')
            connection.execute('DROP TABLE Mistake')
            connection.execute('ALTER TABLE Mistake_upgrade RENAME TO Mistake')
            for (definition,) in definitions:
                connection.execute(definition)
            if connection.execute('PRAGMA foreign_key_check').fetchall():
                raise sqlite3.IntegrityError('Foreign-key check failed during database upgrade.')
    finally:
        connection.execute('PRAGMA foreign_keys = ON')


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
    """Compatibility wrapper for the original paper-only entry function."""
    return insert_mistake(course_id, 'Paper', paper_number, question_number, question_text,
                          difficulty, max_marks, marks_earned, file_paths)


def insert_mistake(course_id, source_type, paper_number, question_number, question_text,
                   difficulty, max_marks, marks_earned, file_paths=()):
    """Store either a Paper or an Exercise, its Mistake and attachments."""
    if source_type not in ('Paper', 'Exercise'):
        raise ValueError('Choose Paper or Exercise.')
    question_number = (question_number or "").strip() or "N/A"
    question_text = (question_text or "").strip() or "N/A"
    paper_number = (paper_number or 0) if source_type == 'Paper' else 0
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
            source_id = connection.execute(
                f"SELECT COALESCE(MAX({source_type}ID), 0) + 1 FROM {source_type}"
            ).fetchone()[0]
            mistake_id = connection.execute(
                "SELECT COALESCE(MAX(MistakeID), 0) + 1 FROM Mistake"
            ).fetchone()[0]
            if source_type == 'Paper':
                connection.execute('''
                    INSERT INTO Paper (PaperID, CourseID, PaperNumber, QuestionNumber,
                                       QuestionText, Difficulty, MaxMarks)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (source_id, course_id, paper_number, question_number,
                      question_text, difficulty, max_marks))
            else:
                connection.execute('''
                    INSERT INTO Exercise (ExerciseID, CourseID, QuestionNumber,
                                          QuestionText, Difficulty, MaxMarks)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (source_id, course_id, question_number, question_text, difficulty, max_marks))
            connection.execute(
                "INSERT INTO Mistake (MistakeID, PaperID, MarksEarned, ExerciseID) VALUES (?, ?, ?, ?)",
                (mistake_id, source_id if source_type == 'Paper' else None,
                 marks_earned, source_id if source_type == 'Exercise' else None),
            )
            connection.executemany(
                "INSERT INTO Attachment (MistakeID, FileName, FileData) VALUES (?, ?, ?)",
                [(mistake_id, name, data) for name, data in files],
            )
        return source_id, mistake_id
    finally:
        connection.close()


def get_course_mistakes(course_id):
    connection = connect_database()
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute('''
            SELECT m.MistakeID, m.PaperID, m.ExerciseID, p.PaperNumber,
                   CASE WHEN m.ExerciseID IS NOT NULL THEN 'Exercise' ELSE 'Paper' END AS SourceType,
                   COALESCE(p.QuestionNumber, e.QuestionNumber) AS QuestionNumber,
                   COALESCE(p.QuestionText, e.QuestionText) AS QuestionText,
                   COALESCE(p.Difficulty, e.Difficulty) AS Difficulty,
                   COALESCE(p.MaxMarks, e.MaxMarks) AS MaxMarks, m.MarksEarned,
                   (SELECT COUNT(*) FROM Attachment a
                    WHERE a.MistakeID = m.MistakeID) AS FileCount
            FROM Mistake m LEFT JOIN Paper p ON p.PaperID = m.PaperID
            LEFT JOIN Exercise e ON e.ExerciseID = m.ExerciseID
            WHERE p.CourseID = ? OR e.CourseID = ? ORDER BY m.MistakeID DESC
        ''', (course_id, course_id)).fetchall()
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


def delete_mistake(mistake_id):
    """Delete a mistake and its files; remove its paper if no attempts remain."""
    connection = connect_database()
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT PaperID, ExerciseID FROM Mistake WHERE MistakeID = ?", (mistake_id,)
            ).fetchone()
            if row is None:
                return False
            connection.execute("DELETE FROM Attachment WHERE MistakeID = ?", (mistake_id,))
            connection.execute("DELETE FROM Mistake WHERE MistakeID = ?", (mistake_id,))
            connection.execute('''
                DELETE FROM Paper WHERE PaperID = ?
                AND NOT EXISTS (SELECT 1 FROM Mistake WHERE PaperID = ?)
            ''', (row[0], row[0]))
            connection.execute('''
                DELETE FROM Exercise WHERE ExerciseID = ?
                AND NOT EXISTS (SELECT 1 FROM Mistake WHERE ExerciseID = ?)
            ''', (row[1], row[1]))
        return True
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
                    LEFT JOIN Paper p ON p.PaperID = m.PaperID
                    LEFT JOIN Exercise e ON e.ExerciseID = m.ExerciseID
                    WHERE p.CourseID = ? OR e.CourseID = ?
                )
            ''', (course_id, course_id))
            connection.execute('''
                DELETE FROM Mistake WHERE PaperID IN (
                    SELECT PaperID FROM Paper WHERE CourseID = ?
                ) OR ExerciseID IN (SELECT ExerciseID FROM Exercise WHERE CourseID = ?)
            ''', (course_id, course_id))
            connection.execute("DELETE FROM Paper WHERE CourseID = ?", (course_id,))
            connection.execute("DELETE FROM Exercise WHERE CourseID = ?", (course_id,))
            connection.execute("DELETE FROM Course WHERE CourseID = ?", (course_id,))
            connection.execute('''
                DELETE FROM Subjects WHERE SubjectID = ?
                AND NOT EXISTS (SELECT 1 FROM Course WHERE SubjectID = ?)
            ''', (row[0], row[0]))
        return True
    finally:
        connection.close()


def delete_all_data():
    """Empty the archive's tables together, keeping their structure."""
    connection = connect_database()
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            # Delete children first so foreign-key checks stay enabled.
            for table in ("Attachment", "Mistake", "Paper", "Exercise", "Course", "Subjects"):
                connection.execute(f'DELETE FROM "{table}"')
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
