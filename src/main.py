import sys
import os
import logging

# Set up logging to a file in the user's home directory if bundled
if getattr(sys, 'frozen', False):
    log_file = os.path.join(os.path.expanduser("~"), "IconifyGo_debug.log")
    logging.basicConfig(filename=log_file, level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Starting IconifyGo (Bundled)")
else:
    logging.basicConfig(level=logging.INFO)

# Robust path handling for both development and PyInstaller
if getattr(sys, 'frozen', False):
    # If bundled, the base path is sys._MEIPASS
    project_root = sys._MEIPASS
else:
    # If dev, it's the directory containing 'src'
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from src.ui.main_window import MainWindow
from src.utils.paths import get_resource_path

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IconifyGo")
    
    # Set application icon (macOS Dock icon)
    icon_path = get_resource_path(os.path.join("res", "iconifygo.icns"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("Unhandled exception in main:")
        if not getattr(sys, 'frozen', False):
            raise
