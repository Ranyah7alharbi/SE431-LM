"""
SE431 - Phase 2 - Data Migration
Converts legacy library.db (single-copy) → new phase2 schema (copy entity).

Run from MR-2/ directory:
    python migrate.py
"""

import sqlite3
import os
import shutil


# ══════════════════════════════════════════════════════════
# Paths — all relative to this script's directory
# ══════════════════════════════════════════════════════════
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))

LEGACY_DB = os.path.join(BASE_DIR, "library.db")
NEW_DB    = os.path.join(BASE_DIR, "library_phase2B_MR02.db")
BACKUP_DB = os.path.join(BASE_DIR, "library_phase2B_MR02.db.bak")


# ══════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════
def print_section(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ══════════════════════════════════════════════════════════
# Main Migration
# ══════════════════════════════════════════════════════════
def migrate():
    # ---- 1. Pre-checks ----
    print_section("1. PRE-CHECKS")

    if not os.path.exists(LEGACY_DB):
        print(f"❌ Legacy DB not found: {LEGACY_DB}")
        print("   Make sure 'library.db' exists in the same folder as migrate.py.")
        print("   If not, run: python lms_original.py (from 01-legacy/) to generate it.")
        return

    print(f"✅ Legacy DB found: {LEGACY_DB}")

    if os.path.exists(NEW_DB):
        print(f"⚠️  New DB exists: {NEW_DB}")
        answer = input("   Overwrite? (y/n): ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return
        if os.path.exists(BACKUP_DB):
            os.remove(BACKUP_DB)
        shutil.move(NEW_DB, BACKUP_DB)
        print(f"   Backed up to: {BACKUP_DB}")

    # ---- 2. Inspect legacy ----
    print_section("2. INSPECT LEGACY")

    src = sqlite3.connect(LEGACY_DB)
    sc = src.cursor()

    sc.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in sc.fetchall()}
    print(f"  Tables found: {sorted(tables)}")

    required = {"members", "books", "loans"}
    missing = required - tables
    if missing:
        print(f"❌ Missing tables: {missing}")
        src.close()
        return

    sc.execute("SELECT COUNT(*) FROM members")
    n_members = sc.fetchone()[0]

    sc.execute("SELECT COUNT(*) FROM books")
    n_books = sc.fetchone()[0]

    sc.execute("SELECT COUNT(*) FROM loans")
    n_loans = sc.fetchone()[0]

    sc.execute("SELECT COUNT(*) FROM loans WHERE returned=0")
    n_active = sc.fetchone()[0]

    print(f"  Members       : {n_members}")
    print(f"  Books         : {n_books}")
    print(f"  Loans (total) : {n_loans}")
    print(f"  Loans (active): {n_active}")

    # ---- 3. Create new DB + schema ----
    print_section("3. CREATE NEW SCHEMA")

    dst = sqlite3.connect(NEW_DB)
    dst.execute("PRAGMA foreign_keys = ON")
    dc = dst.cursor()

    dc.executescript("""
        CREATE TABLE members(
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT
        );

        CREATE TABLE books(
            id INTEGER PRIMARY KEY,
            title TEXT,
            author TEXT
        );

        CREATE TABLE book_copies(
            copy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'AVAILABLE',
            CHECK (status IN ('AVAILABLE','BORROWED','DAMAGED','LOST')),
            FOREIGN KEY(book_id) REFERENCES books(id)
        );

        CREATE TABLE loans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT,
            copy_id INTEGER NOT NULL,
            borrow_date TEXT,
            due_date TEXT,
            returned INTEGER DEFAULT 0,
            FOREIGN KEY(copy_id) REFERENCES book_copies(copy_id),
            FOREIGN KEY(member_id) REFERENCES members(id)
        );
    """)
    print("  ✅ New schema created")

    # ---- 4. Migrate members ----
    print_section("4. MIGRATE MEMBERS")

    sc.execute("SELECT id,name,status FROM members")
    members = sc.fetchall()
    dc.executemany("INSERT INTO members VALUES (?,?,?)", members)
    print(f"  ✅ {len(members)} members copied")

    # ---- 5. Migrate books ----
    print_section("5. MIGRATE BOOKS")

    sc.execute("SELECT id,title,author FROM books")
    books = sc.fetchall()
    dc.executemany("INSERT INTO books VALUES (?,?,?)", books)
    print(f"  ✅ {len(books)} books copied")

    # ---- 6. Create base copies ----
    print_section("6. CREATE COPIES")
    print("  Strategy: 1 base copy per book (legacy had single-copy model).")

    book_to_copies = {}

    for (book_id, title, author) in books:
        dc.execute(
            "INSERT INTO book_copies(book_id,status) VALUES(?, 'AVAILABLE')",
            (book_id,)
        )
        copy_id = dc.lastrowid
        book_to_copies[book_id] = copy_id
        print(f"    Book {book_id}: base copy #{copy_id}")

    # ---- 7. Migrate loans ----
    print_section("7. MIGRATE LOANS")

    sc.execute("""
        SELECT id, member_id, book_id, borrow_date, due_date, returned
        FROM loans
        ORDER BY borrow_date
    """)
    legacy_loans = sc.fetchall()

    migrated = 0
    skipped = 0

    for (loan_id, member_id, book_id, bdate, ddate, returned) in legacy_loans:
        if book_id not in book_to_copies:
            print(f"    ⚠️  Loan {loan_id}: book {book_id} missing → skipped")
            skipped += 1
            continue

        copy_id = book_to_copies[book_id]

        # Active loan → mark copy as BORROWED
        if returned == 0:
            dc.execute(
                "UPDATE book_copies SET status='BORROWED' WHERE copy_id=?",
                (copy_id,)
            )

        dc.execute("""
            INSERT INTO loans(member_id, copy_id, borrow_date, due_date, returned)
            VALUES(?,?,?,?,?)
        """, (member_id, copy_id, bdate, ddate, returned))

        migrated += 1
        status = "BORROWED" if returned == 0 else "returned"
        print(f"    Loan {loan_id}: book {book_id} → copy #{copy_id} ({status})")

    print(f"\n  ✅ Migrated: {migrated}  |  Skipped: {skipped}")

    dst.commit()

    # ---- 8. Integrity checks ----
    print_section("8. INTEGRITY CHECKS")

    dc.execute("PRAGMA foreign_key_check")
    fk_issues = dc.fetchall()
    print(f"  Foreign key violations: {len(fk_issues)}")
    if fk_issues:
        for issue in fk_issues:
            print(f"    ⚠️  {issue}")

    dc.execute("SELECT COUNT(*) FROM members")
    new_members = dc.fetchone()[0]
    dc.execute("SELECT COUNT(*) FROM books")
    new_books = dc.fetchone()[0]
    dc.execute("SELECT COUNT(*) FROM book_copies")
    new_copies = dc.fetchone()[0]
    dc.execute("SELECT COUNT(*) FROM loans")
    new_loans = dc.fetchone()[0]
    dc.execute("SELECT COUNT(*) FROM loans WHERE returned=0")
    new_active = dc.fetchone()[0]
    dc.execute("SELECT COUNT(*) FROM book_copies WHERE status='BORROWED'")
    new_borrowed = dc.fetchone()[0]

    print(f"  Members       : {new_members}  (expected {n_members})  "
          f"{'✅' if new_members == n_members else '❌'}")
    print(f"  Books         : {new_books}  (expected {n_books})  "
          f"{'✅' if new_books == n_books else '❌'}")
    print(f"  Copies        : {new_copies}  (expected {n_books} base copies)")
    print(f"  Loans         : {new_loans}  (expected {n_loans})  "
          f"{'✅' if new_loans == n_loans else '❌'}")
    print(f"  Active loans  : {new_active}")
    print(f"  BORROWED copies: {new_borrowed}")

    if new_active == new_borrowed:
        print("  ✅ Consistency: active loans = BORROWED copies")
    else:
        print("  ❌ MISMATCH: active loans ≠ BORROWED copies")

    # ---- 9. Final inventory ----
    print_section("9. FINAL INVENTORY")

    dc.execute("""
        SELECT b.id, b.title,
               COUNT(bc.copy_id) AS total,
               SUM(CASE WHEN bc.status='AVAILABLE' THEN 1 ELSE 0 END) AS avail,
               SUM(CASE WHEN bc.status='BORROWED'  THEN 1 ELSE 0 END) AS borrowed
        FROM books b
        LEFT JOIN book_copies bc ON bc.book_id = b.id
        GROUP BY b.id
        ORDER BY b.id
    """)
    for row in dc.fetchall():
        avail    = row[3] or 0
        borrowed = row[4] or 0
        print(f"  Book {row[0]}: {row[1]:<25}  "
              f"total={row[2]}  avail={avail}  borrowed={borrowed}")

    # ---- 10. Done ----
    print_section("10. DONE")
    print(f"  ✅ Migration complete: {NEW_DB}")
    print(f"  Next: python phase2_B_MR02.py")

    src.close()
    dst.close()


# ══════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    migrate()