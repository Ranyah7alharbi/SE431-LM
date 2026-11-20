"""
SE431 - Phase 3 - Refactoring
Main entry point. UI only.
Switch DB by changing DB_TYPE below.

Changes from Phase 2:
  R6  _read_ids() extracts the repeated member-ID / book-ID input
      block that appeared identically in both borrow and return
      branches into a single helper, keeping the UI DRY.
"""

from repository3 import make_repository
from service import LibraryService


# ══════════════════════════════════════════════════════════
# CONFIG — change ONE line to switch DB
# ══════════════════════════════════════════════════════════
DB_TYPE = "sqlite"        # ← change to "postgres" to switch

SQLITE_PATH = "library_phase2B_MR02.db"
PG_CONN_STR = "postgresql://user:pass@localhost:5432/library"


# ══════════════════════════════════════════════════════════
# R6: shared input helper — avoids duplicating the two-line
#     member/book read in both borrow and return branches.
# ══════════════════════════════════════════════════════════
def _read_ids():
    """
    Read a member ID (string) and a book ID (integer) from stdin.
    Returns (member_id, book_id), or (None, None) on invalid book ID.
    """
    member = input("Member ID: ").strip()
    try:
        book = int(input("Book ID: "))
    except ValueError:
        print("Invalid book ID")
        return None, None
    return member, book


# ══════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════
def main():
    repo = make_repository(
        DB_TYPE,
        path=SQLITE_PATH,
        conn_str=PG_CONN_STR
    )
    service = LibraryService(repo)

    while True:
        print("\n════════ LIBRARY (Phase 3 Refactored) ════════")
        print(f"   [DB: {DB_TYPE}]")
        print("1. Search")
        print("2. Borrow")
        print("3. Return")
        print("4. Exit")

        choice = input("Choice: ").strip()

        if choice == "1":
            text = input("Search text: ")
            rows = service.search_books(text)
            if not rows:
                print("No books found.")
            for r in rows:
                avail = r[4] or 0
                print(f"  [{r[0]}] {r[1]} - {r[2]}  Available: {avail}/{r[3]}")

        elif choice == "2":
            member, book = _read_ids()          # R6
            if member is not None:
                ok, msg = service.borrow(member, book)
                print(msg)

        elif choice == "3":
            member, book = _read_ids()          # R6
            if member is not None:
                ok, msg = service.return_book(member, book)
                print(msg)

        elif choice == "4":
            repo.close()
            print("Goodbye.")
            break

        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
