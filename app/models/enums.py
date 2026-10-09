"""Enum types shared by models and schemas."""

import enum


class UserStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"


class UserRole(str, enum.Enum):
    employee = "employee"
    intern = "intern"
    admin = "admin"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    revoked = "revoked"
