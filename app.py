from flask import Flask, render_template, request, redirect, url_for, flash,session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, inspect, text

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

    category = db.Column(
        db.String(100)
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
# CATEGORY -> SYMPTOM MAP
# (symptom names must match data.json exactly)
# Used by import_remedies.py to fill the category column
# -----------------------------

CATEGORY_MAP = {
    "Digestive Health": [
        "Abdominal pain", "Abdominal pain (from diarrhoea)", "Bleeding piles",
        "Constipation", "Diarrhoea", "Diarrhoea in children",
        "Diarrhoea/Dysentery", "Diarrhoea/Vomiting", "Dysentery",
        "Flatulence", "Flatulence (gas)", "Hyper-acidity",
        "Hyper-acidity/Peptic ulcer/Constipation", "Indigestion",
        "Indigestion/Loss of appetite", "Intestinal worms", "Kidney stone",
        "Loss of appetite", "Piles", "Vomiting",
    ],
    "Respiratory, Cold & Fever": [
        "Cold", "Cold with fever", "Cold/Cough", "Cold/Hiccough", "Cough",
        "Cough/Cold", "Dry cough", "Ear pain", "Fever", "Hiccough",
        "Hoarseness of voice", "Nasal block", "Sinusitis",
    ],
    "Pain, Ache & Body Discomfort": [
        "Aches & pains", "Body ache", "Headache", "Joint pain",
        "Painful menses", "Tension headache", "Toothache",
    ],
    "Skin, Hair & Beauty": [
        "Acne", "Black pigmentation", "Dandruff", "Dandruff/Ring worm",
        "Face pack/skin glow", "Greying of hair",
        "Greying of hair/Hair fall/Dandruff", "Hair fall", "Skin allergy",
        "Skin disease", "Skin diseases", "Ulcer/Wounds/Burns",
        "Urticaria (skin allergy)", "Wound/Ulcer", "Wound/Ulcer/Skin disease",
        "Wounds/Ulcer", "Wounds/Ulcer/Burn",
    ],
    "Oral & Dental Care": [
        "Bad breath", "Bleeding gums", "Bleeding gums/tartar/bad breath",
        "Pyorrhoea", "Pyorrhoea (bleeding gums)",
    ],
    "Women's & Children's Health": [
        "Irritability (children)", "Lactation support", "Memory (children)",
    ],
    "General Wellness & Lifestyle": [
        "Dehydration", "Dehydration/Sun stroke", "Diabetes",
        "General health/nutrition", "Mental tension", "Obesity", "Stress",
        "Sun stroke", "Sunstroke/Dehydration",
    ],
}

# reverse lookup: symptom -> category
SYMPTOM_TO_CATEGORY = {
    symptom: category
    for category, symptoms in CATEGORY_MAP.items()
    for symptom in symptoms
}


def get_categories():
    """Build {category: [symptoms]} from the database for the dropdowns."""

    rows = db.session.query(
        Remedy.category,
        Remedy.symptom
    ).filter(
        Remedy.category.isnot(None)
    ).distinct().all()

    found = {}

    for category, symptom in rows:
        found.setdefault(category, []).append(symptom)

    # keep category order from CATEGORY_MAP, symptoms A-Z
    ordered = {}

    for category in CATEGORY_MAP:
        if category in found:
            ordered[category] = sorted(found[category])

    return ordered


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
    category = request.args.get("category", "").strip()

    # dropdown data (category -> symptoms) comes from the database
    categories = get_categories()

    # Normal home page
    if not symptom:
        return render_template(
            "index.html",
            searched=False,
            categories=categories
        )

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
                limit_reached=True,
                categories=categories
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
    # Exact match, because the symptom now comes from a dropdown
    # (so "Cold" no longer also returns "Cold/Cough")
    # --------------------------------

    match = Remedy.query.filter(
        func.lower(Remedy.symptom) == symptom.lower()
    ).all()

    print("SEARCH:", category, "->", symptom)
    print("MATCHES:", [r.symptom for r in match])

    return render_template(
        "index.html",
        searched=True,
        symptom=symptom,
        category=category,
        results=match,
        categories=categories
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

    # Older ayurfix.db files have no "category" column in the remedy table.
    # Add it automatically so the app never crashes (users are kept).
    existing_columns = [c["name"] for c in inspect(db.engine).get_columns("remedy")]

    if "category" not in existing_columns:
        db.session.execute(text("ALTER TABLE remedy ADD COLUMN category VARCHAR(100)"))
        db.session.commit()


# -----------------------------
# RUN SERVER
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)
