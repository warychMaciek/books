import os
import requests

from flask import Flask, session, render_template, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():
    if session.get("user") is None:
        return render_template("index.html")
    else:
        return render_template("main.html", login = session["user"][0])

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/registered", methods=["POST"])
def registered():
    login = request.form.get("login")
    email = request.form.get("email")
    password = request.form.get("password")
    password_repeat = request.form.get("password-repeat")
    is_login_taken = db.execute("SELECT * FROM users WHERE username = :username", {"username": login}).fetchone()
    is_email_taken = db.execute("SELECT * FROM users WHERE email = :email", {"email": email}).fetchone()

    session["user"] = []
    session["user"].append(login)

    if is_login_taken is None and is_email_taken is None and password == password_repeat:
        if len(login) != 0 and len(email) != 0 and len(password) != 0:
            db.execute("INSERT INTO users (username, email, password) VALUES (:username, :email, :password)",
                {"username": login, "email": email, "password": password})
            db.commit()
            return render_template("main.html", login = login, greetings = "Thank you for signing up.")
        else:
            return render_template("register.html", alert = "Please enter required data")
    elif is_login_taken is not None:
        return render_template("register.html", alert = "Login is taken, try again")
    elif is_email_taken is not None:
        return render_template("register.html", alert = "Email is taken, try again")
    else:
        return render_template("register.html", alert = "Confirmed password is invalid, please confirm password correctly")


@app.route("/main", methods=["POST"])
def main():
    login = request.form.get("login")
    password = request.form.get("password")


    if db.execute("SELECT * FROM users WHERE (username = :username)", {"username": login}).rowcount == 0:
        return render_template("index.html", alert = "An account with given login does not exist.")
    elif db.execute("SELECT * FROM users WHERE (password = :password)", {"password": password}).rowcount == 0:
        return render_template("index.html", alert = "Incorrect password.")
    else:
        if session.get("user") is None:
            session["user"] = []
            session["user"].append(login)
        return render_template("main.html", login = login)


@app.route("/results", methods=["POST"])
def results():
    book = request.form.get("book")
    results = db.execute("SELECT * FROM books WHERE title ILIKE :book OR author ILIKE :book OR number ILIKE :book", {"book": '%' + book + '%'}).fetchall()
    return render_template("results.html", results = results)


@app.route("/book_page")
def book_page():
    book_number = request.args.get("type")
    book_info = db.execute("SELECT * FROM books WHERE (number = :number)", {"number": book_number}).fetchone()
    reviewer_id = db.execute("SELECT id FROM users WHERE (username = :reviewer)", {"reviewer": session["user"][0]}).fetchone()
    reviewed_already = db.execute("SELECT * FROM reviews WHERE (isbn = :isbn) AND (reviewer_id = :user)", {"isbn": book_number, "user": reviewer_id.id}).rowcount != 0
    
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "7SLmoldly4n8PWyVHIUJw", "isbns": book_number})
    goodreads_rating = res.json()["books"][0]["average_rating"]
    goodreads_ratings_count = res.json()["books"][0]["work_ratings_count"]

    reviews = db.execute("SELECT review, rating, username FROM reviews JOIN users ON users.id = reviews.reviewer_id WHERE isbn = :isbn", {"isbn": book_number}).fetchall()
    if reviews != []:
        has_reviews = True
    else:
        has_reviews = False
    return render_template("book-page.html", title = book_info.title, author = book_info.author, year = book_info.year, number = book_info.number, reviewed_already = reviewed_already, has_reviews = has_reviews, reviews = reviews, gr_rating = goodreads_rating, number_of_ratings = goodreads_ratings_count)

@app.route("/add_review", methods=["GET", "POST"])
def add_review():
    book_number = request.args.get("type")
    book_info = db.execute("SELECT * FROM books WHERE (number = :number)", {"number": book_number}).fetchone()
    rating = request.form.get("rating")
    review = request.form.get("review")
    reviewer_id = db.execute("SELECT id FROM users WHERE (username = :reviewer)", {"reviewer": session["user"][0]}).fetchone()
    db.execute("INSERT INTO reviews (isbn, reviewer_id, review, rating) VALUES (:isbn, :reviewer_id, :review, :rating)", {"isbn": book_number, "reviewer_id": reviewer_id.id, "review": review, "rating": rating})
    db.commit()

    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "7SLmoldly4n8PWyVHIUJw", "isbns": book_number})
    goodreads_rating = res.json()["books"][0]["average_rating"]
    goodreads_ratings_count = res.json()["books"][0]["work_ratings_count"]

    reviews = db.execute("SELECT review, rating, username FROM reviews JOIN users ON users.id = reviews.reviewer_id WHERE isbn = :isbn", {"isbn": book_number}).fetchall()
    if reviews != []:
        has_reviews = True
    else:
        has_reviews = False
    return render_template("book-page.html", title = book_info.title, author = book_info.author, year = book_info.year, number = book_info.number, reviewed_already = True, has_reviews = has_reviews, reviews = reviews, gr_rating = goodreads_rating, number_of_ratings = goodreads_ratings_count)

@app.route("/logout")
def logout():
    session.clear()
    return render_template("index.html")    

@app.route("/api/<isbn>")
def book_api(isbn):
    book = db.execute("SELECT * FROM books WHERE number = :isbn", {"isbn": isbn}).fetchone()
    if book is None:
        return jsonify({"error": "The book with given isbn does not exist"}), 422

    reviews = db.execute("SELECT rating FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()
    review_count = 0
    total_score = 0
    average_score = 0
    for review in reviews:
        review_count += 1
        total_score += review.rating
    if review_count != 0:
        average_score = total_score / review_count

    return jsonify({
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": book.number,
        "review_count": review_count,
        "average_score": average_score
    })