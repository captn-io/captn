from abc import ABC, abstractmethod
from typing import List, Optional

class NotificationCollector:
    """
    Collects notification messages during execution and dispatches them at the end.
    """
    def __init__(self):
        """
        Initialize the notification collector.

        Creates a new collector instance with an empty message list.
        """
        self.messages: List[str] = []

    def add(self, message: str):
        """
        Add a message to the collector.

        Parameters:
            message (str): Message to add to the collection
        """
        self.messages.append(message)

    def clear(self):
        """
        Clear all collected messages.
        """
        self.messages.clear()

    def get_all(self) -> List[str]:
        """
        Get all collected messages.

        Returns:
            List[str]: Copy of all collected messages
        """
        return self.messages[:]

class BaseNotifier(ABC):
    """
    Abstract base class for all notifiers.
    """
    def __init__(self, enabled: bool = True):
        """
        Initialize the base notifier.

        Parameters:
            enabled (bool): Whether the notifier is enabled
        """
        self.enabled = enabled

    @abstractmethod
    def send(self, messages: List[str]):
        """
        Send notification messages.

        Parameters:
            messages (List[str]): List of messages to send
        """
        pass
