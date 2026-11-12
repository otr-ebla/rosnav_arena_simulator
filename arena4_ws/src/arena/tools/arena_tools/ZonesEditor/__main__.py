import sys
import signal
from .ZonesEditor import ZonesEditor
from PyQt5 import QtWidgets, QtCore


def main():
    app = QtWidgets.QApplication([])

    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    widget = ZonesEditor()
    widget.show()

    app.exec()

    # Start a timer to periodically allow the interpreter to process signals
    timer = QtCore.QTimer()
    timer.start(100)  # 100 ms

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
