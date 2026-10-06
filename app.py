from flask import Flask, render_template, request, redirect, url_for, flash,session
from flask_sqlalchemy import SQLAlchemy

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import generate_password_hash, check_password_hash

from datetime import datetime


# -----------------------------
# CREATE FLASK APP
# -----------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = "ayurfix-secret-key"

# SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ayurfix.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# -----------------------------
# DATABASE
# -----------------------------

db = SQLAlchemy(app)


# -----------------------------
# LOGIN MANAGER
# -----------------------------

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = "login"


# -----------------------------
# USER MODEL
# -----------------------------

class User(UserMixin, db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    full_name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        default="user",
        nullable=False
    )


# -----------------------------
# SEARCH HISTORY MODEL
# -----------------------------

class SearchHistory(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    search_term = db.Column(
        db.String(200),
        nullable=False
    )

    searched_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )


# -----------------------------
# REMEDY MODEL
# -----------------------------

class Remedy(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    symptom = db.Column(
        db.String(200),
        nullable=False
    )

    ingredient = db.Column(
        db.String(200)
    )

    scientific_name = db.Column(
        db.String(200)
    )

    instructions = db.Column(
        db.Text
    )

    directions = db.Column(
        db.Text
    )

    disclaimer = db.Column(
        db.Text
    )


# -----------------------------
# LOAD USER
# -----------------------------

@login_manager.user_loader
def load_user(user_id):

    return db.session.get(
        User,
        int(user_id)
    )


# -----------------------------
# HOME PAGE + SEARCH
# -----------------------------

@app.route("/")
def home():
    symptom = request.args.get("symptom", "").strip()

    # Normal home page
    if not symptom:
        return render_template("index.html", searched=False)

    # --------------------------------
    # GUEST SEARCH RESTRICTION
    # --------------------------------

    if not current_user.is_authenticated:

        search_count = session.get("search_count", 0)

        # Allow only 2 searches
        if search_count >= 2:
            return render_template(
                "index.html",
                searched=False,
                limit_reached=True
            )

        # Count this search
        session["search_count"] = search_count + 1

    # --------------------------------
    # SAVE SEARCH FOR LOGGED-IN USER
    # --------------------------------

    if current_user.is_authenticated:

        history = SearchHistory(
            user_id=current_user.id,
            search_term=symptom
        )

        db.session.add(history)
        db.session.commit()

    # --------------------------------
    # SEARCH REMEDY DATABASE
    # --------------------------------

    query = symptom.lower()

    match = Remedy.query.filter(
        Remedy.symptom.ilike(f"%{query}%")
    ).all()

    print("SEARCH:", symptom)
    print("MATCHES:", [r.symptom for r in match])

    return render_template(
        "index.html",
        searched=True,
        symptom=symptom,
        results=match
    )

# -----------------------------
# REGISTER
# -----------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        terms = request.form.get("terms")

        # Check empty fields
        if not full_name or not email or not password:

            flash("Please fill all required fields.")

            return redirect(
                url_for("register")
            )

        # Check password confirmation
        if password != confirm_password:

            flash("Passwords do not match.")

            return redirect(
                url_for("register")
            )

        # Check terms checkbox
        if not terms:

            flash("Please accept the Terms and Conditions.")

            return redirect(
                url_for("register")
            )

        # Check if email already exists
        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "An account with this email already exists."
            )

            return redirect(
                url_for("register")
            )

        # Hash password
        password_hash = generate_password_hash(
            password
        )

        # Create user
        new_user = User(
            full_name=full_name,
            email=email,
            password_hash=password_hash
        )

        # Save user
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully!")

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# -----------------------------
# LOGIN
# -----------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        # Find user
        user = User.query.filter_by(
            email=email
        ).first()

        # Verify password
        if user and check_password_hash(user.password_hash, password):
            login_user(user)

        # Reset guest search counter
            session.pop("search_count", None)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

        return redirect(
            url_for("login")
        )

    return render_template(
        "login.html"
    )


# -----------------------------
# DASHBOARD
# -----------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    history = SearchHistory.query.filter_by(
        user_id=current_user.id
    ).order_by(
        SearchHistory.searched_at.desc()
    ).all()

    return render_template(
        "dashboard.html",
        history=history
    )
@app.route("/admin")
@login_required
def admin_dashboard():

    # Only admins can access this page
    if current_user.role != "admin":
        return "Access Denied", 403

    # Get all users
    users = User.query.order_by(User.full_name).all()

    # Get all search history
    all_history = SearchHistory.query.order_by(
        SearchHistory.searched_at.desc()
    ).all()

    # Organize searches according to user_id
    user_searches = {}

    for item in all_history:

        if item.user_id not in user_searches:
            user_searches[item.user_id] = []

        user_searches[item.user_id].append(item)

    return render_template(
        "admin_dashboard.html",
        users=users,
        user_searches=user_searches
    )

# -----------------------------
# LOGOUT
# -----------------------------

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("home")
    )


# -----------------------------
# CREATE DATABASE
# -----------------------------

with app.app_context():
    db.create_all()


# -----------------------------
# RUN SERVER
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)