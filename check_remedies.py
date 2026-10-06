from app import app, db, Remedy

with app.app_context():
    print("Total remedies:", Remedy.query.count())

    remedies = Remedy.query.limit(10).all()

    for remedy in remedies:
        print("-", remedy.symptom)