"""
SE431 - Phase 2 - MR-02
Repository layer: abstracts DB access. Interchangeable implementations.

IMPORTANT:
- setup_schema() creates tables ONLY (no data).
- seed_sample_data() populates sample data (call manually for first-run tests).
- Migration must run BEFORE starting the system to move legacy data.
"""

from abc import ABC, abstractmethod


# ══════════════════════════════════════════════════════════
# Interface
# ══════════════════════════════════════════════════════════
class LibraryRepository(ABC):

    # ---- Queries ----
    @abstractmethod
    def find_member(self, member_id): ...

    @abstractmethod
    def find_book(self, book_id): ...

    @abstractmethod
    def find_available_copy(self, book_id): ...

    @abstractmethod
    def count_active_loans(self, member_id): ...

    @abstractmethod
    def find_active_loan(self, member_id, book_id): ...

    @abstractmethod
    def search_books(self, text): ...

    # ---- Mutations ----
    @abstractmethod
    def create_loan(self, member_id, copy_id, borrow_date, due_date): ...

    @abstractmethod
    def close_loan(self, loan_id): ...

    @abstractmethod
    def mark_copy_borrowed(self, copy_id): ...

    @abstractmethod
    def mark_copy_available(self, copy_id): ...

    # ---- Setup / Lifecycle ----
    @abstractmethod
    def setup_schema(self): ...

    @abstractmethod
    def seed_sample_data(self): ...

    @abstractmethod
    def close(self): ...


# ══════════════════════════════════════════════════════════
# SQLite Implementation
# ══════════════════════════════════════════════════════════
class SQLiteRepository(LibraryRepository):

    def __init__(self, path):
        import sqlite3
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys = ON")

    # ══════════════════════════════════════════════════════
    # Schema — tables only, NO data
    # ══════════════════════════════════════════════════════
    def setup_schema(self):
        c = self.db.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS members(
                id TEXT PRIMARY KEY,
                name TEXT,
                status TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS books(
                id INTEGER PRIMARY KEY,
                title TEXT,
                author TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS book_copies(
                copy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'AVAILABLE',
                CHECK (status IN ('AVAILABLE','BORROWED','DAMAGED','LOST')),
                FOREIGN KEY(book_id) REFERENCES books(id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS loans(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id TEXT,
                copy_id INTEGER NOT NULL,
                borrow_date TEXT,
                due_date TEXT,
                returned INTEGER DEFAULT 0,
                FOREIGN KEY(copy_id) REFERENCES book_copies(copy_id),
                FOREIGN KEY(member_id) REFERENCES members(id)
            )
        """)

        self.db.commit()

    # ══════════════════════════════════════════════════════
    # Sample data — ONLY for first-run without migration
    # ══════════════════════════════════════════════════════
    def seed_sample_data(self):
        """
        Populate sample data. Use ONLY if you're NOT running migration.
        If you ran migrate.py, do NOT call this.
        """
        c = self.db.cursor()

        c.execute("INSERT OR IGNORE INTO members VALUES ('S1','Ali','ACTIVE')")
        c.execute("INSERT OR IGNORE INTO members VALUES ('S2','Sara','ACTIVE')")
        c.execute("INSERT OR IGNORE INTO members VALUES ('S3','Omar','INACTIVE')")

        c.execute("INSERT OR IGNORE INTO books VALUES (1,'Clean Code','Robert Martin')")
        c.execute("INSERT OR IGNORE INTO books VALUES (2,'Refactoring','Martin Fowler')")
        c.execute("INSERT OR IGNORE INTO books VALUES (3,'Design Patterns','Gamma et al.')")

        self._ensure_copies(c, 1, 3)
        self._ensure_copies(c, 2, 2)
        self._ensure_copies(c, 3, 1)

        self.db.commit()

    def _ensure_copies(self, cur, book_id, count):
        cur.execute("SELECT COUNT(*) FROM book_copies WHERE book_id=?", (book_id,))
        existing = cur.fetchone()[0]
        for _ in range(count - existing):
            cur.execute(
                "INSERT INTO book_copies(book_id,status) VALUES(?, 'AVAILABLE')",
                (book_id,)
            )

    # ══════════════════════════════════════════════════════
    # Queries
    # ══════════════════════════════════════════════════════
    def find_member(self, member_id):
        c = self.db.cursor()
        c.execute("SELECT id,status FROM members WHERE id=?", (member_id,))
        row = c.fetchone()
        return {"id": row[0], "status": row[1]} if row else None

    def find_book(self, book_id):
        c = self.db.cursor()
        c.execute("SELECT id,title FROM books WHERE id=?", (book_id,))
        row = c.fetchone()
        return {"id": row[0], "title": row[1]} if row else None

    def find_available_copy(self, book_id):
        c = self.db.cursor()
        c.execute(
            """SELECT copy_id FROM book_copies
               WHERE book_id=? AND status='AVAILABLE'
               ORDER BY copy_id LIMIT 1""",
            (book_id,)
        )
        row = c.fetchone()
        return row[0] if row else None

    def count_active_loans(self, member_id):
        c = self.db.cursor()
        c.execute(
            "SELECT COUNT(*) FROM loans WHERE member_id=? AND returned=0",
            (member_id,)
        )
        return c.fetchone()[0]

    def find_active_loan(self, member_id, book_id):
        c = self.db.cursor()
        c.execute(
            """SELECT l.id, l.due_date, l.copy_id
               FROM loans l
               JOIN book_copies bc ON bc.copy_id = l.copy_id
               WHERE l.member_id=? AND bc.book_id=? AND l.returned=0
               LIMIT 1""",
            (member_id, book_id)
        )
        row = c.fetchone()
        return {"id": row[0], "due_date": row[1], "copy_id": row[2]} if row else None

    def search_books(self, text):
        c = self.db.cursor()
        pat = "%" + text + "%"
        c.execute(
            """SELECT b.id, b.title, b.author,
                      COUNT(bc.copy_id) AS total,
                      SUM(CASE WHEN bc.status='AVAILABLE' THEN 1 ELSE 0 END) AS avail
               FROM books b
               LEFT JOIN book_copies bc ON bc.book_id = b.id
               WHERE b.title LIKE ? OR b.author LIKE ?
               GROUP BY b.id""",
            (pat, pat)
        )
        return c.fetchall()

    # ══════════════════════════════════════════════════════
    # Mutations
    # ══════════════════════════════════════════════════════
    def create_loan(self, member_id, copy_id, borrow_date, due_date):
        c = self.db.cursor()
        c.execute(
            """INSERT INTO loans(member_id,copy_id,borrow_date,due_date,returned)
               VALUES(?,?,?,?,0)""",
            (member_id, copy_id, borrow_date, due_date)
        )
        self.db.commit()
        return c.lastrowid

    def close_loan(self, loan_id):
        c = self.db.cursor()
        c.execute("UPDATE loans SET returned=1 WHERE id=?", (loan_id,))
        self.db.commit()

    def mark_copy_borrowed(self, copy_id):
        c = self.db.cursor()
        c.execute(
            "UPDATE book_copies SET status='BORROWED' WHERE copy_id=?",
            (copy_id,)
        )
        self.db.commit()

    def mark_copy_available(self, copy_id):
        c = self.db.cursor()
        c.execute(
            "UPDATE book_copies SET status='AVAILABLE' WHERE copy_id=?",
            (copy_id,)
        )
        self.db.commit()

    def close(self):
        self.db.close()


# ══════════════════════════════════════════════════════════
# PostgreSQL Implementation
# ══════════════════════════════════════════════════════════
class PostgresRepository(LibraryRepository):

    def __init__(self, conn_str):
        import psycopg2
        self.db = psycopg2.connect(conn_str)

    def setup_schema(self):
        c = self.db.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS members(
                id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(100),
                status VARCHAR(20)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS books(
                id SERIAL PRIMARY KEY,
                title VARCHAR(200),
                author VARCHAR(200)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS book_copies(
                copy_id SERIAL PRIMARY KEY,
                book_id INTEGER NOT NULL REFERENCES books(id),
                status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE'
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS loans(
                id SERIAL PRIMARY KEY,
                member_id VARCHAR(50) REFERENCES members(id),
                copy_id INTEGER NOT NULL REFERENCES book_copies(copy_id),
                borrow_date TEXT,
                due_date TEXT,
                returned INTEGER DEFAULT 0
            )
        """)
        self.db.commit()

    def seed_sample_data(self):
        c = self.db.cursor()
        c.execute("INSERT INTO members VALUES ('S1','Ali','ACTIVE') ON CONFLICT DO NOTHING")
        c.execute("INSERT INTO members VALUES ('S2','Sara','ACTIVE') ON CONFLICT DO NOTHING")
        c.execute("INSERT INTO members VALUES ('S3','Omar','INACTIVE') ON CONFLICT DO NOTHING")
        c.execute("INSERT INTO books VALUES (1,'Clean Code','Robert Martin') ON CONFLICT DO NOTHING")
        c.execute("INSERT INTO books VALUES (2,'Refactoring','Martin Fowler') ON CONFLICT DO NOTHING")
        c.execute("INSERT INTO books VALUES (3,'Design Patterns','Gamma et al.') ON CONFLICT DO NOTHING")
        self._ensure_copies(c, 1, 3)
        self._ensure_copies(c, 2, 2)
        self._ensure_copies(c, 3, 1)
        self.db.commit()

    def _ensure_copies(self, cur, book_id, count):
        cur.execute("SELECT COUNT(*) FROM book_copies WHERE book_id=%s", (book_id,))
        existing = cur.fetchone()[0]
        for _ in range(count - existing):
            cur.execute(
                "INSERT INTO book_copies(book_id,status) VALUES(%s, 'AVAILABLE')",
                (book_id,)
            )

    def find_member(self, member_id):
        c = self.db.cursor()
        c.execute("SELECT id,status FROM members WHERE id=%s", (member_id,))
        row = c.fetchone()
        return {"id": row[0], "status": row[1]} if row else None

    def find_book(self, book_id):
        c = self.db.cursor()
        c.execute("SELECT id,title FROM books WHERE id=%s", (book_id,))
        row = c.fetchone()
        return {"id": row[0], "title": row[1]} if row else None

    def find_available_copy(self, book_id):
        c = self.db.cursor()
        c.execute(
            """SELECT copy_id FROM book_copies
               WHERE book_id=%s AND status='AVAILABLE'
               ORDER BY copy_id LIMIT 1""",
            (book_id,)
        )
        row = c.fetchone()
        return row[0] if row else None

    def count_active_loans(self, member_id):
        c = self.db.cursor()
        c.execute(
            "SELECT COUNT(*) FROM loans WHERE member_id=%s AND returned=0",
            (member_id,)
        )
        return c.fetchone()[0]

    def find_active_loan(self, member_id, book_id):
        c = self.db.cursor()
        c.execute(
            """SELECT l.id, l.due_date, l.copy_id
               FROM loans l
               JOIN book_copies bc ON bc.copy_id = l.copy_id
               WHERE l.member_id=%s AND bc.book_id=%s AND l.returned=0
               LIMIT 1""",
            (member_id, book_id)
        )
        row = c.fetchone()
        return {"id": row[0], "due_date": row[1], "copy_id": row[2]} if row else None

    def search_books(self, text):
        c = self.db.cursor()
        pat = "%" + text + "%"
        c.execute(
            """SELECT b.id, b.title, b.author,
                      COUNT(bc.copy_id),
                      SUM(CASE WHEN bc.status='AVAILABLE' THEN 1 ELSE 0 END)
               FROM books b
               LEFT JOIN book_copies bc ON bc.book_id = b.id
               WHERE b.title ILIKE %s OR b.author ILIKE %s
               GROUP BY b.id""",
            (pat, pat)
        )
        return c.fetchall()

    def create_loan(self, member_id, copy_id, borrow_date, due_date):
        c = self.db.cursor()
        c.execute(
            """INSERT INTO loans(member_id,copy_id,borrow_date,due_date,returned)
               VALUES(%s,%s,%s,%s,0) RETURNING id""",
            (member_id, copy_id, borrow_date, due_date)
        )
        new_id = c.fetchone()[0]
        self.db.commit()
        return new_id

    def close_loan(self, loan_id):
        c = self.db.cursor()
        c.execute("UPDATE loans SET returned=1 WHERE id=%s", (loan_id,))
        self.db.commit()

    def mark_copy_borrowed(self, copy_id):
        c = self.db.cursor()
        c.execute("UPDATE book_copies SET status='BORROWED' WHERE copy_id=%s", (copy_id,))
        self.db.commit()

    def mark_copy_available(self, copy_id):
        c = self.db.cursor()
        c.execute("UPDATE book_copies SET status='AVAILABLE' WHERE copy_id=%s", (copy_id,))
        self.db.commit()

    def close(self):
        self.db.close()


# ══════════════════════════════════════════════════════════
# Factory
# ══════════════════════════════════════════════════════════
def make_repository(db_type="sqlite", **kwargs):
    if db_type == "sqlite":
        path = kwargs.get("path", "library_phase2B_MR02.db")
        repo = SQLiteRepository(path)
    elif db_type == "postgres":
        conn = kwargs.get(
            "conn_str",
            "postgresql://user:pass@localhost:5432/library"
        )
        repo = PostgresRepository(conn)
    else:
        raise ValueError(f"Unknown DB type: {db_type}")

    repo.setup_schema()
    return repo