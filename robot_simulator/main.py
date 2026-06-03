"""
Robot Simulator — Main Entry Point

Boots the PyQt5 application with the dark engineering theme, then opens
the main window. Headless flows continue to work via scripts/smoke_test.py.
"""

import os
import sys


def main() -> None:
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QPalette, QColor
    from PyQt5.QtWidgets import QApplication

    # Crisper text on Windows + macOS.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Robot Simulator")
    app.setStyle("Fusion")  # neutral base that QSS overrides cleanly.

    # Apply our design system before any window is shown.
    from ui.theme import BG, TEXT, apply_theme
    apply_theme(app)

    # Tinting the QPalette helps any non-styled native widgets blend in.
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG.BASE))
    palette.setColor(QPalette.Base, QColor(BG.ELEVATED))
    palette.setColor(QPalette.AlternateBase, QColor(BG.HOVER))
    palette.setColor(QPalette.WindowText, QColor(TEXT.PRIMARY))
    palette.setColor(QPalette.Text, QColor(TEXT.PRIMARY))
    palette.setColor(QPalette.ButtonText, QColor(TEXT.PRIMARY))
    palette.setColor(QPalette.ToolTipBase, QColor(BG.OVERLAY))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT.PRIMARY))
    app.setPalette(palette)

    from ui.main_window import MainWindow
    window = MainWindow(project_root=project_root)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
