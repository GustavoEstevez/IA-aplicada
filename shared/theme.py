"""Identidad visual compartida de VigiWork."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "vigiwork_logo.png"


def app_icon() -> QIcon:
    return QIcon(str(LOGO_PATH))

COLORS = {
    "background": "#1F1F1F",
    "panel": "#292929",
    "panel_hover": "#353535",
    "orange": "#FF7A00",
    "white": "#F2F2F2",
    "muted": "#B7B7B7",
    "border": "#414141",
    "danger": "#E24B4B",
}

APP_STYLESHEET = """
    QWidget {
        background: #1F1F1F;
        color: #F2F2F2;
        font: 14px 'Segoe UI';
    }
    QMainWindow, QDialog { background: #1F1F1F; }
    QScrollArea { background: #1F1F1F; border: 0; }
    QScrollBar:vertical {
        background: #1F1F1F;
        width: 12px;
        margin: 2px;
    }
    QScrollBar::handle:vertical { background: #555555; border-radius: 5px; min-height: 28px; }
    QScrollBar::handle:vertical:hover { background: #FF7A00; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
    QWidget#brandHeader { background: transparent; }
    QLabel#brandLogo { background: transparent; }
    QLabel#eyebrow {
        color: #FF7A00;
        font-size: 11px;
        font-weight: 700;
    }
    QLabel#pageTitle { color: #F2F2F2; font-size: 23px; font-weight: 700; }
    QLabel#subtle, QLabel#url { color: #B7B7B7; background: transparent; }
    QLabel#status {
        color: #F2F2F2;
        background: #292929;
        border: 1px solid #414141;
        border-left: 3px solid #FF7A00;
        border-radius: 7px;
        padding: 9px 12px;
    }
    QLabel#fps { color: #FF7A00; font-weight: 700; background: transparent; }
    QLabel#video, QLabel#preview {
        background: #111111;
        border: 1px solid #414141;
        border-radius: 10px;
        color: #B7B7B7;
    }
    QLineEdit, QComboBox {
        background: #292929;
        border: 1px solid #414141;
        border-radius: 7px;
        padding: 10px 12px;
        color: #F2F2F2;
        selection-background-color: #FF7A00;
    }
    QLineEdit:focus, QComboBox:focus { border: 1px solid #FF7A00; }
    QComboBox::drop-down { width: 28px; border: 0; }
    QComboBox QAbstractItemView {
        background: #292929;
        color: #F2F2F2;
        border: 1px solid #414141;
        selection-background-color: #4A3422;
        outline: 0;
    }
    QPushButton {
        background: #292929;
        border: 1px solid #414141;
        border-radius: 7px;
        padding: 9px 14px;
        color: #F2F2F2;
    }
    QPushButton:hover { background: #353535; border-color: #FF7A00; }
    QPushButton#primary {
        background: #FF7A00;
        border-color: #FF7A00;
        color: #1F1F1F;
        font-weight: 700;
    }
    QPushButton#primary:hover { background: #FF922E; border-color: #FF922E; }
    QPushButton#danger { border-color: #7D3737; color: #FF9D9D; }
    QPushButton#danger:hover { background: #472727; border-color: #E24B4B; }
    QPushButton:disabled { color: #777777; background: #252525; border-color: #343434; }
    QTreeWidget {
        background: #292929;
        alternate-background-color: #303030;
        border: 1px solid #414141;
        border-radius: 8px;
        outline: 0;
    }
    QTreeWidget::item { padding: 9px 7px; }
    QTreeWidget::item:selected { background: #4A3422; color: #F2F2F2; }
    QTreeWidget::indicator {
        width: 17px;
        height: 17px;
        border: 1px solid #777777;
        border-radius: 4px;
        background: #1F1F1F;
    }
    QTreeWidget::indicator:checked { background: #FF7A00; border-color: #FF7A00; }
    QHeaderView::section {
        background: #242424;
        color: #B7B7B7;
        border: 0;
        border-bottom: 1px solid #414141;
        padding: 9px;
        font-weight: 600;
    }
    QDialogButtonBox QPushButton { min-width: 92px; }
"""


def brand_header(role: str, subtitle: str) -> QWidget:
    header = QWidget()
    header.setObjectName("brandHeader")
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 2)
    row.setSpacing(18)

    logo = QLabel()
    logo.setObjectName("brandLogo")
    logo.setAccessibleName("VigiWork")
    pixmap = QPixmap(str(LOGO_PATH))
    if not pixmap.isNull():
        logo.setPixmap(pixmap.scaled(
            128, 82, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
    row.addWidget(logo)

    copy = QVBoxLayout()
    copy.setSpacing(3)
    eyebrow = QLabel("SEGURIDAD INTELIGENTE")
    eyebrow.setObjectName("eyebrow")
    title = QLabel(role)
    title.setObjectName("pageTitle")
    detail = QLabel(subtitle)
    detail.setObjectName("subtle")
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(detail)
    row.addLayout(copy)
    row.addStretch(1)
    return header


def scrollable(content: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setWidget(content)
    return area
