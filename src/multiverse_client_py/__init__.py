from __future__ import annotations
from importlib.metadata import version

__version__ = version("multiverse_client_py")

from .multiverse_client import MultiverseClient, MultiverseMetaData
