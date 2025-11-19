"""
Database Schemas for School App

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercase of the class name (e.g., User -> "user").
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal, List

class User(BaseModel):
    """
    Users of the school system (students and teachers)
    Collection: "user"
    """
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    role: Literal["student", "teacher"] = Field(..., description="Role in the system")
    hashed_password: str = Field(..., description="Bcrypt hashed password")
    grade: Optional[str] = Field(None, description="Student grade or class (optional for teachers)")

class Course(BaseModel):
    """
    Courses offered in the school
    Collection: "course"
    """
    title: str
    code: str
    teacher_id: Optional[str] = Field(None, description="ObjectId of teacher as string")
    student_ids: List[str] = Field(default_factory=list, description="List of student ObjectId strings enrolled")

class Announcement(BaseModel):
    """
    School-wide or course-specific announcements
    Collection: "announcement"
    """
    title: str
    body: str
    audience: Literal["all", "students", "teachers"] = "all"
