import sys
from pathlib import Path

PROJ_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
if str(PROJ_DIR) not in sys.path:
    sys.path.insert(0, str(PROJ_DIR))

# 预先导入 importlib.metadata 以避免 PySide6 的 shibokensupport
# import hook 在 urllib3.http2 → importlib.metadata → inspect 导入链中
# 因循环依赖导致 KeyboardInterrupt（Python 3.13+ 兼容性问题）
import importlib.metadata  # noqa: F401

from PySide6.QtWidgets import QApplication
from scripts.ui import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
