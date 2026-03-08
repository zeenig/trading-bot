import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.execution.engine import get_engine


if __name__ == "__main__":
    engine = get_engine()
    try:
        engine.run_continuous()
    except KeyboardInterrupt:
        engine.stop()
        print("Trading cycle stopped.")
