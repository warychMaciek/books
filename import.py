import csv
import os

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def main():
    f = open("books.csv")
    reader = csv.reader(f)

    db.execute("CREATE TABLE books (number VARCHAR UNIQUE, title VARCHAR NOT NULL, author VARCHAR NOT NULL, year VARCHAR NOT NULL)")

    for n, t, a, y in reader:
        db.execute("INSERT INTO books (number, title, author, year) VALUES (:number, :title, :author, :year)",
                    {"number": n, "title": t, "author": a, "year": y})
        print(f"Added book {t}, which has number {n}, {a} published it in {y}.")
    db.commit()

if __name__ == "__main__":
    main()
