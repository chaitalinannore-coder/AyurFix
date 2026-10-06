import json
from app import app, db, Remedy

with app.app_context():

    with open("data.json", "r", encoding="utf-8") as f:

        records = json.load(f)

        for r in records:

            remedy = Remedy(
                symptom=r.get("symptom", ""),
                ingredient=r.get("ingredient", ""),
                scientific_name=r.get("scientific_name", ""),
                instructions=r.get("instructions", ""),
                directions=r.get("directions", ""),
                disclaimer=r.get("disclaimer", "")
            )

            db.session.add(remedy)

        db.session.commit()

        print(f"Imported {len(records)} remedies successfully!")