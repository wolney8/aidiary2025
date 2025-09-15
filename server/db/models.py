# server/db/models.py
# SQLAlchemy models mapping to existing database schema
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import os

Base = declarative_base()

class User(Base):
    """User model mapping to existing users table."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(Text, nullable=False)
    password = Column(Text, nullable=False)
    first_name = Column(Text)
    last_name = Column(Text)
    age = Column(Integer)
    sex = Column(Text)
    goals = Column(Text)
    dailydiary_api_key = Column(Text)
    dreamdiary_api_key = Column(Text)
    chatgpt_daily_diary_coachname = Column(Text)
    chatgpt_dream_diary_coachname = Column(Text)
    
    # Relationships
    configurations = relationship('Configuration', back_populates='user')
    daily_entries = relationship('DailyDiaryEntry', back_populates='user')
    dream_entries = relationship('DreamDiaryEntry', back_populates='user')

class Configuration(Base):
    """Configuration model mapping to existing configurations table."""
    __tablename__ = 'configurations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    daily_diary_prompt = Column(Text)
    dream_diary_prompt = Column(Text)
    
    # Relationships
    user = relationship('User', back_populates='configurations')

class DailyDiaryEntry(Base):
    """Daily diary entry model mapping to existing dailydiary_entries table."""
    __tablename__ = 'dailydiary_entries'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    entry_date = Column(Date)
    entry_number = Column(Integer)
    user_message = Column(Text)
    ai_response = Column(Text)
    daily_people_names = Column(Text)
    tags = Column(Text)
    
    # Relationships
    user = relationship('User', back_populates='daily_entries')

class DreamDiaryEntry(Base):
    """Dream diary entry model mapping to existing dreamdiary_entries table."""
    __tablename__ = 'dreamdiary_entries'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    entry_date = Column(Date)
    entry_number = Column(Integer)
    title = Column(Text)
    cast = Column(Text)
    location = Column(Text)
    period = Column(Text)
    emotion = Column(Text)
    plot = Column(Text)
    symbols_and_imagery = Column(Text)
    insight = Column(Text)
    action = Column(Text)
    other = Column(Text)
    summary = Column(Text)
    interpretation = Column(Text)
    image_prompt = Column(Text)
    image_url = Column(Text)
    dream_people_names = Column(Text)
    tags = Column(Text)
    
    # Relationships
    user = relationship('User', back_populates='dream_entries')

def get_session():
    """Create database session."""
    db_path = os.getenv('DB_PATH', './app.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    return Session()