import json
from sqlalchemy import inspect, text
from app import app, db, Remedy, SYMPTOM_TO_CATEGORY

with app.app_context():

    # Make sure the tables exist
    db.create_all()

    # ------------------------------------------------------------
    # Old ayurfix.db has no "category" column in the remedy table.
    # Add it here so you do NOT lose your registered users.
    # ------------------------------------------------------------
    columns = [c["name"] for c in inspect(db.engine).get_columns("remedy")]

    if "category" not in columns:
        db.session.execute(text("ALTER TABLE remedy ADD COLUMN category VARCHAR(100)"))
        db.session.commit()
        print("Added 'category' column to remedy table.")

    # ------------------------------------------------------------
    # Clear old remedies so re-running this file never duplicates them
    # ------------------------------------------------------------
    deleted = Remedy.query.delete()
    db.session.commit()
    print(f"Removed {deleted} old remedy records.")

    # ------------------------------------------------------------
    # Import data.json
    # ------------------------------------------------------------
    with open("data.json", "r", encoding="utf-8") as f:

        records = json.load(f)

    missing = set()

    for r in records:

        symptom = r.get("symptom", "").strip()

        category = SYMPTOM_TO_CATEGORY.get(symptom)

        if category is None:
            missing.add(symptom)

        remedy = Remedy(
            category=category,
            symptom=symptom,
            ingredient=r.get("ingredient", ""),
            scientific_name=r.get("scientific_name", ""),
            instructions=r.get("instructions", ""),
            directions=r.get("directions", ""),
            disclaimer=r.get("disclaimer", "")
        )

        db.session.add(remedy)

    db.session.commit()

    print(f"Imported {len(records)} remedies successfully!")

    if missing:
        print("WARNING - no category found for these symptoms (add them to CATEGORY_MAP in app.py):")
        for m in sorted(missing):
            print("  -", m)
