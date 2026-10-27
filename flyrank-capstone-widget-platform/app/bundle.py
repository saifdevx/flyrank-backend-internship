"""The widget bundle and its content-hash version. Changing widget.js changes the URL, so browsers can cache it forever."""
import hashlib

from . import config

BYTES = (config.ROOT / "app" / "static" / "widget.js").read_bytes()
VERSION = hashlib.sha256(BYTES).hexdigest()[:8]
