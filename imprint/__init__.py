"""Imprint — local-first SDLC paperwork automation.

The `imprint` package is the *functional core*: UI-free, unit-testable logic
(database + pure definitions). The Tkinter shell in `imprint_app.py` imports
from here. Keeping logic out of the GUI is what lets the tests run without
opening a window.
"""

__version__ = "1.1.0"
