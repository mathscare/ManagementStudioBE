# models.py
from sqlalchemy import Column, Integer, String, Table, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

# Association table for many-to-many relationship between files and tags
file_tags = Table(
    "file_tags",
    Base.metadata,
    Column("file_id", Integer, ForeignKey("files.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True)
)

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    restored_url = Column(String, nullable=True)
    restored_url_expiration = Column(DateTime, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), default=1, nullable=False) 
    tags = relationship("Tag", secondary=file_tags, back_populates="files")
    
    # Add relationship to tenant
    tenant = relationship("Tenant", back_populates="files")

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, default='default', nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), default=1, nullable=False) 
    files = relationship("File", secondary=file_tags, back_populates="tags")
    
    # Add relationship to tenant
    tenant = relationship("Tenant", back_populates="tags")
