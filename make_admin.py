from app import app, db, User

with app.app_context():

    email = input("Enter admin email: ")

    user = User.query.filter_by(email=email).first()

    if user:
        user.role = "admin"
        db.session.commit()

        print("Admin role assigned successfully!")
        print("Name:", user.full_name)
        print("Email:", user.email)
        print("Role:", user.role)

    else:
        print("User not found.")