import os
from app import app, db
from models import User, Item
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

def seed():
    with app.app_context():
        # Drop and create tables
        db.drop_all()
        db.create_all()

        print("Creating users...")
        # Create Admin
        admin = User(
            name="Admin User",
            email="admin@kpriet.ac.in",
            password_hash=generate_password_hash("admin123", method='pbkdf2:sha256'),
            is_admin=True
        )
        db.session.add(admin)

        # Create Sample Students
        students = [
            ("Saran Kumar", "21cs145@kpriet.ac.in"),
            ("Priya Dharshini", "22ec012@kpriet.ac.in"),
            ("Rahul Raj", "20me088@kpriet.ac.in"),
            ("Anita Mary", "23ai005@kpriet.ac.in")
        ]

        user_objects = []
        for name, email in students:
            u = User(
                name=name,
                email=email,
                password_hash=generate_password_hash("password123", method='pbkdf2:sha256')
            )
            db.session.add(u)
            user_objects.append(u)
        
        db.session.commit()

        print("Creating sample items...")
        
        locations = [
            "Administrative and AI & DS Block",
            "Central Library",
            "Food Court",
            "Girls Hostel (Ganga, Yamuna, Kaveri)",
            "Boys Hostel",
            "Mechanical Block",
            "Civil & EEE Block"
        ]

        categories = [
            "Electronics", "Books & Documents", "Accessories & Wearables",
            "Keys & Wallets", "Clothing", "Stationery"
        ]

        # Sample Lost Items
        lost_items_data = [
            ("Blue iPhone 13", "Electronics", "Found in a black case", locations[1]),
            ("Engineering Physics Textbook", "Books & Documents", "Name written on page 10", locations[5]),
            ("Silver Casio Watch", "Accessories & Wearables", "Digital display, slight scratch", locations[2]),
            ("Keys with Red Keychain", "Keys & Wallets", "Bunch of 3 keys", locations[0])
        ]

        # Sample Found Items
        found_items_data = [
            ("Black Dell Laptop Charger", "Electronics", "Found near the library entrance", locations[1]),
            ("Brown Leather Wallet", "Keys & Wallets", "Has some ID cards inside", locations[2]),
            ("Blue Water Bottle", "Other", "Milton brand", locations[6]),
            ("Spectacles with Black Frame", "Accessories & Wearables", "Found in the computer lab", locations[0])
        ]

        all_items = []

        # Add Lost Items
        for title, cat, desc, loc in lost_items_data:
            item = Item(
                title=title,
                category=cat,
                description=desc,
                location=loc,
                date=(datetime.utcnow() - timedelta(days=random.randint(1, 5))).date(),
                type="lost",
                user_id=random.choice(user_objects).id
            )
            db.session.add(item)
            all_items.append(item)

        # Add Found Items
        for title, cat, desc, loc in found_items_data:
            item = Item(
                title=title,
                category=cat,
                description=desc,
                location=loc,
                date=(datetime.utcnow() - timedelta(days=random.randint(1, 5))).date(),
                type="found",
                user_id=random.choice(user_objects).id
            )
            db.session.add(item)
            all_items.append(item)

        db.session.commit()
        print("Database seeded successfully!")

if __name__ == '__main__':
    seed()
