# Started by run.bat and the "Start with Windows" entry: pythonw.exe tray\launch.pyw
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tray.app import main  # noqa: E402

sys.exit(main())
