from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    role_obj = relationship("Role", back_populates="users") 
