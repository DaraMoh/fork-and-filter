from . import db
from datetime import datetime

class Restaurant(db.Model):
    __tablename__ = "restaurants"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    price_tier = db.Column(db.Integer) # 1=$, 2=$$, 3=$$$
    halal = db.Column(db.Boolean, default=False)
    menu = db.Column(db.Text)
    neighborhood = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # FOR OSM
    description = db.Column(db.Text)
    website = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    opening_hours = db.Column(db.String(120))
    source = db.Column(db.String(32))
    external_id = db.Column(db.String(80))

class Checkin(db.Model):
    __tablename__ = "checkins"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    