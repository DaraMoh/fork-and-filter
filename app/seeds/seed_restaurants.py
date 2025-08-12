# app/seeds/seed_restaurants.py
from app import create_app, db
from app.models import Restaurant, Checkin

def run():
    app = create_app()
    with app.app_context():
        rows = [
            Restaurant(name="Falafel House",  lat=32.780, lng=-96.800, price_tier=2, halal=True,  menu="falafel|shawarma|hummus", neighborhood="Dallas"),
            Restaurant(name="Shawarma King",  lat=32.948, lng=-96.730, price_tier=2, halal=True,  menu="shawarma|tabbouleh|wraps", neighborhood="Richardson"),
            Restaurant(name="Taco Spot",      lat=32.785, lng=-96.810, price_tier=1, halal=False, menu="tacos|queso|chips",       neighborhood="Dallas"),
            Restaurant(name="Pho Corner",     lat=33.020, lng=-96.699, price_tier=2, halal=False, menu="pho|noodles|banh mi",     neighborhood="Plano"),
            Restaurant(name="Big D Burger",   lat=32.814, lng=-96.949, price_tier=2, halal=False, menu="burger|fries|shakes",     neighborhood="Irving"),
            Restaurant(name="Cowtown Pizza",  lat=32.756, lng=-97.331, price_tier=2, halal=False, menu="pizza|margherita|pepperoni", neighborhood="Fort Worth"),
            Restaurant(name="BBQ Junction",   lat=32.736, lng=-97.108, price_tier=3, halal=False, menu="brisket|ribs|sides",      neighborhood="Arlington"),
            Restaurant(name="Frisco Sushi",   lat=33.151, lng=-96.824, price_tier=3, halal=False, menu="sushi|rolls|sashimi",     neighborhood="Frisco"),
            Restaurant(name="Carrollton Curry", lat=32.976, lng=-96.890, price_tier=2, halal=True, menu="biryani|curry|naan",     neighborhood="Carrollton"),
            Restaurant(name="Garland Noodle House", lat=32.913, lng=-96.639, price_tier=1, halal=False, menu="noodles|dumplings|fried rice", neighborhood="Garland"),
            Restaurant(name="Addison Kebab",  lat=32.962, lng=-96.829, price_tier=2, halal=True,  menu="kebab|shawarma|hummus",   neighborhood="Addison"),
            Restaurant(name="Denton Diner",   lat=33.215, lng=-97.133, price_tier=1, halal=False, menu="pancakes|omelette|coffee", neighborhood="Denton"),
        ]
        db.session.bulk_save_objects(rows)
        db.session.commit()
        print(f"✅ Seeded {len(rows)} restaurants")

        # optional: add some “busy now” check-ins so busyness shows up
        from datetime import datetime
        now = datetime.utcnow()
        targets = [("Shawarma King", 8), ("Falafel House", 5), ("Taco Spot", 2)]
        for name, n in targets:
            r = Restaurant.query.filter_by(name=name).first()
            if r:
                for _ in range(n):
                    db.session.add(Checkin(restaurant_id=r.id, created_at=now))
        db.session.commit()
        print("✅ Seeded recent check-ins")

if __name__ == "__main__":
    run()
