"""Baixa e guarda em cache (cache/bh_drive.graphml) a malha viária de BH."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.road_snap import RoadSnapper  # noqa: E402

if __name__ == "__main__":
    RoadSnapper().ensure_loaded()
