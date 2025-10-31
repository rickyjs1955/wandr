"""
Seed database with sample mall, user, and GeoJSON map.
Run this script to populate the database for testing/development.

Usage:
    python -m scripts.seed_data
"""

import sys
import os
from datetime import datetime

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.user import User
from app.models.mall import Mall
from app.services.auth_service import hash_password

# Sample GeoJSON for a simple rectangular mall floor plan
SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [103.8198, 1.3521],
                    [103.8205, 1.3521],
                    [103.8205, 1.3528],
                    [103.8198, 1.3528],
                    [103.8198, 1.3521]
                ]]
            },
            "properties": {
                "type": "floor_plan",
                "level": 1,
                "name": "Ground Floor"
            }
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [103.8199, 1.3522],
                    [103.8201, 1.3522],
                    [103.8201, 1.3524],
                    [103.8199, 1.3524],
                    [103.8199, 1.3522]
                ]]
            },
            "properties": {
                "type": "store",
                "name": "Store A",
                "category": "Fashion"
            }
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [103.8202, 1.3522],
                    [103.8204, 1.3522],
                    [103.8204, 1.3524],
                    [103.8202, 1.3524],
                    [103.8202, 1.3522]
                ]]
            },
            "properties": {
                "type": "store",
                "name": "Store B",
                "category": "Electronics"
            }
        }
    ]
}


def seed_database():
    """Seed database with sample data."""
    db = SessionLocal()

    try:
        print("🌱 Starting database seeding...")

        # Check if mall already exists
        existing_mall = db.query(Mall).first()
        if existing_mall:
            print("⚠️  Mall already exists. Skipping mall creation.")
            print(f"   Mall ID: {existing_mall.id}")
            print(f"   Mall Name: {existing_mall.name}")
            mall = existing_mall
        else:
            # Create sample mall
            print("\n📍 Creating sample mall...")
            mall = Mall(
                name="Demo Shopping Mall",
                geojson_map=SAMPLE_GEOJSON,
            )
            db.add(mall)
            db.commit()
            db.refresh(mall)
            print(f"✅ Mall created: {mall.name} (ID: {mall.id})")

        # Check if admin user already exists
        existing_admin = db.query(User).filter(User.email == "admin@demo.com").first()
        if existing_admin:
            print("\n⚠️  Admin user already exists. Skipping user creation.")
            print(f"   Username: {existing_admin.username}")
            print(f"   Email: {existing_admin.email}")
        else:
            # Create admin user
            print("\n👤 Creating admin user...")
            admin_user = User(
                email="admin@demo.com",
                username="admin",
                password_hash=hash_password("admin123"),  # CHANGE IN PRODUCTION!
                role="MALL_OPERATOR",
                mall_id=mall.id,
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            print(f"✅ Admin user created: {admin_user.username}")
            print(f"   Email: {admin_user.email}")
            print(f"   Password: admin123 (CHANGE IN PRODUCTION!)")
            print(f"   Role: {admin_user.role}")

        print("\n" + "="*60)
        print("✅ Database seeding completed successfully!")
        print("="*60)
        print("\n📝 Login credentials:")
        print("   Username: admin")
        print("   Password: admin123")
        print(f"\n   Mall ID: {mall.id}")
        print(f"   Mall Name: {mall.name}")
        print("\n⚠️  IMPORTANT: Change the default password in production!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
