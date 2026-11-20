"""
SE431 - Phase 3 - Refactoring
R3: simple classes instead of dicts and tuples
(before: member["status"], r[4], loan["copy_id"])
"""


class Member:
    def __init__(self, id, status):
        self.id = id
        self.status = status


class Book:
    def __init__(self, id, title):
        self.id = id
        self.title = title


class Loan:
    def __init__(self, id, due_date, copy_id):
        self.id = id
        self.due_date = due_date
        self.copy_id = copy_id


class BookAvailability:
    def __init__(self, id, title, author, total, available):
        self.id = id
        self.title = title
        self.author = author
        self.total = total
        self.available = available
