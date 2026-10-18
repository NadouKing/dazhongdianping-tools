"""Read-only Dianping tools. No browser is started during import."""

from .client import DianpingClient
from .errors import DianpingError

__all__ = ["DianpingClient", "DianpingError"]
__version__ = "0.1.0"
