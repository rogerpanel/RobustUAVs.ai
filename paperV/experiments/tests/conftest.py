import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# number of Theorem 1 property-test episodes (2,000 for the full gate, run by run_campaign.py --phase p1-property)
PROPERTY_EPISODES = int(os.environ.get("PAPERV_PROPERTY_EPISODES", "12"))
