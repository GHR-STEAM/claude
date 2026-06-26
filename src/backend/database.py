"""
MongoDB database configuration and setup for Mergington High School API.
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv
import logging

from .seed_data import initial_activities, get_initial_teachers

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Connect to MongoDB
mongodb_url = os.getenv('MONGODB_URL', 'mongodb://localhost:27017/')
database_name = os.getenv('DATABASE_NAME', 'mergington_high')
client = MongoClient(mongodb_url)
db = client[database_name]
activities_collection = db['activities']
teachers_collection = db['teachers']


def init_database():
    """Initialize database with seed data if collections are empty."""
    # Initialize activities if empty
    if activities_collection.count_documents({}) == 0:
        for name, details in initial_activities.items():
            activities_collection.insert_one({"_id": name, **details})
        logger.info(f"Seeded {len(initial_activities)} activities")

    # Initialize teacher accounts if empty
    if teachers_collection.count_documents({}) == 0:
        teachers = get_initial_teachers()
        for teacher in teachers:
            teachers_collection.insert_one({"_id": teacher["username"], **teacher})
        logger.info(f"Seeded {len(teachers)} teachers")

