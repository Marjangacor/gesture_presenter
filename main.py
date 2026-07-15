import sys
from PySide6.QtWidgets import QApplication
from config.settings_manager import SettingsManager
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    settings = SettingsManager()

    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
