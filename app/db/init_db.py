from app.db.session import engine, Base
from app.models import user
from app.models.event import Event  # Import the Event model
  # Ensure models are imported so they register with Base

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
