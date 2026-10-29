import sys
import os
import threading
import signal
from dotenv import load_dotenv

load_dotenv(override=True)
if "AWS_SESSION_TOKEN" in os.environ:
    del os.environ["AWS_SESSION_TOKEN"]

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.visuals import VisibilityController

def main():
    # Allow python to handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    
    # Initialize the visualization controller
    vis_controller = VisibilityController()
    
    # Start the main translucent interface
    window = MainWindow(vis_controller)
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
