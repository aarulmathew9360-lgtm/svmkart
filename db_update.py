from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Check if the column exists first by trying to select it
        db.session.execute(text('SELECT phone FROM user LIMIT 1'))
        print("Phone column already exists.")
    except Exception as e:
        db.session.rollback()
        # Alter table
        db.session.execute(text('ALTER TABLE user ADD COLUMN phone VARCHAR(20) DEFAULT ""'))
        db.session.commit()
        print("Phone column added to user table.")
