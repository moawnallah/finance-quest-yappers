import sys
from pathlib import Path

# Make `import prediction` work when pytest is run from the repo root or from backend/data.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
