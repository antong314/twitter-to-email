"""Subscriber storage using JSON file."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import fcntl


@dataclass
class Subscriber:
    """Represents a newsletter subscriber."""
    
    twitter_handle: str  # Without @ symbol
    email: str
    subscribed_at: str  # ISO format datetime
    active: bool = True
    
    @classmethod
    def create(cls, twitter_handle: str, email: str) -> "Subscriber":
        """Create a new subscriber with current timestamp."""
        # Normalize handle (remove @ if present, lowercase)
        handle = twitter_handle.lstrip("@").lower()
        return cls(
            twitter_handle=handle,
            email=email.lower(),
            subscribed_at=datetime.now(timezone.utc).isoformat(),
            active=True,
        )


class SubscriberStore:
    """
    JSON file-based subscriber storage.
    
    Thread-safe using file locking for concurrent access.
    """
    
    DEFAULT_DIR = "data"
    FILENAME = "subscribers.json"
    
    def __init__(self, data_dir: Optional[str] = None):
        dir_path = Path(data_dir) if data_dir else Path(self.DEFAULT_DIR)
        self.path = dir_path / self.FILENAME
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """Create the JSON file and parent directories if they don't exist."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_subscribers([])
    
    def _read_subscribers(self) -> List[dict]:
        """Read subscribers from JSON file with file locking."""
        try:
            with open(self.path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _write_subscribers(self, subscribers: List[dict]) -> None:
        """Write subscribers to JSON file with file locking."""
        with open(self.path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(subscribers, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    def add(self, subscriber: Subscriber) -> bool:
        """
        Add a new subscriber.
        
        Returns:
            True if added, False if already exists (same email).
        """
        subscribers = self._read_subscribers()
        
        # Check if email already exists
        for s in subscribers:
            if s.get("email", "").lower() == subscriber.email.lower():
                # Update the handle if email exists but handle changed
                if s.get("twitter_handle", "").lower() != subscriber.twitter_handle.lower():
                    s["twitter_handle"] = subscriber.twitter_handle
                    s["active"] = True  # Reactivate if was inactive
                    self._write_subscribers(subscribers)
                    return True
                # Same email and handle - just reactivate if inactive
                if not s.get("active", True):
                    s["active"] = True
                    self._write_subscribers(subscribers)
                    return True
                return False  # Already exists and active
        
        # Add new subscriber
        subscribers.append(asdict(subscriber))
        self._write_subscribers(subscribers)
        return True
    
    def get_all_active(self) -> List[Subscriber]:
        """Get all active subscribers."""
        subscribers = self._read_subscribers()
        return [
            Subscriber(**s)
            for s in subscribers
            if s.get("active", True)
        ]
    
    def get_by_email(self, email: str) -> Optional[Subscriber]:
        """Find a subscriber by email."""
        subscribers = self._read_subscribers()
        for s in subscribers:
            if s.get("email", "").lower() == email.lower():
                return Subscriber(**s)
        return None
    
    def deactivate(self, email: str) -> bool:
        """
        Deactivate a subscriber (soft delete).
        
        Returns:
            True if found and deactivated, False if not found.
        """
        subscribers = self._read_subscribers()
        for s in subscribers:
            if s.get("email", "").lower() == email.lower():
                s["active"] = False
                self._write_subscribers(subscribers)
                return True
        return False
    
    def count_active(self) -> int:
        """Get count of active subscribers."""
        return len(self.get_all_active())

