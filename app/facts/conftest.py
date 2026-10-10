"""Make `import main` work no matter which directory pytest was started from."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
