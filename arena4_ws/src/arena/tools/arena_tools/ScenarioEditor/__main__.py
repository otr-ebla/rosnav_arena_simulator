import sys
import signal
from PyQt5 import QtWidgets, QtCore

from .ArenaScenarioEditor import ArenaScenarioEditor


def main():

    app = QtWidgets.QApplication([])

    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    widget = ArenaScenarioEditor()
    widget.show()

    # Start a timer to periodically allow the interpreter to process signals
    timer = QtCore.QTimer()
    timer.start(100)  # 100 ms

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
