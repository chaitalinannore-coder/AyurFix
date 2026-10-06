from app import app, db

with app.app_context():

    db.session.execute(
        db.text(
            "ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'user' NOT NULL"
        )
    )

    db.session.commit()

    print("Role column added successfully!")