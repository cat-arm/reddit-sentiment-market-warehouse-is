"""Step 23: open the Streamlit dashboard (same as `streamlit run dashboard/app.py`).

Run:  python steps/23_run_dashboard.py [--server.port 8502]
"""

import subprocess
import sys

from _run import ROOT

sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "dashboard" / "app.py")] + sys.argv[1:]))
