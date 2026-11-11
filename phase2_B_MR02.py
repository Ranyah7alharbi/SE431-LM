"""
SE431 - Phase 2 - MR-02
Main entry point. UI only.
Switch DB by changing DB_TYPE below.
"""

from repository import make_repository
from service import LibraryService


# ══════════════════════════════════════════════════════════
# CONFIG — change ONE line to switch DB
# ══════════════════════════════════════════════════════════
DB_TYPE = "sqlite"        # ← change to "postgres" to switch

SQLITE_PATH = "library_phase2B_MR02.db"
PG_CONN_STR = "postgresql://user:pass@localhost:5432/library"


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
        print("\n════════ LIBRARY (MR-02 Layered) ════════")
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
            member = input("Member ID: ").strip()
            try:
                book = int(input("Book ID: "))
            except ValueError:
                print("Invalid book ID")
                continue
            ok, msg = service.borrow(member, book)
            print(msg)

        elif choice == "3":
            member = input("Member ID: ").strip()
            try:
                book = int(input("Book ID: "))
            except ValueError:
                print("Invalid book ID")
                continue
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