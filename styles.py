"""
Thème visuel de l'application (feuille de style QSS + palette).
"""

COLORS = {
    "bg": "#F4F6FB",
    "surface": "#FFFFFF",
    "border": "#E2E8F0",
    "border_strong": "#CBD5E1",
    "text": "#0F172A",
    "muted": "#64748B",
    "accent": "#4338CA",
    "accent_hover": "#3730A3",
    "accent_soft": "#EEF2FF",
    "danger": "#DC2626",
    "danger_soft": "#FEE2E2",
    "success": "#15803D",
    "success_soft": "#DCFCE7",
    "warning": "#B45309",
    "warning_soft": "#FEF3C7",
    "toolbar": "#0F172A",
}

C = COLORS

STYLESHEET = f"""
* {{
    color: {C['text']};
}}
QMainWindow, QDialog {{
    background: {C['bg']};
}}
QWidget#Page {{
    background: {C['bg']};
}}
QToolTip {{
    background: {C['toolbar']};
    color: white;
    border: none;
    padding: 6px 8px;
    border-radius: 4px;
}}

/* ---------- Barre d'outils ---------- */
QToolBar#MainToolbar {{
    background: {C['toolbar']};
    border: none;
    padding: 6px 10px;
    spacing: 4px;
}}
QToolBar#MainToolbar QToolButton {{
    color: #E2E8F0;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
}}
QToolBar#MainToolbar QToolButton:hover {{
    background: #1E293B;
    border-color: #334155;
}}
QToolBar#MainToolbar QToolButton:pressed {{
    background: #334155;
}}
QToolBar#MainToolbar QToolButton:disabled {{
    color: #475569;
}}
QToolBar#MainToolbar QLabel {{
    color: #94A3B8;
    padding: 0 4px 0 10px;
}}
QToolBar#MainToolbar QLabel#AppTitle {{
    color: white;
    font-weight: 700;
    font-size: 15px;
    padding: 0 18px 0 4px;
}}
QToolBar#MainToolbar QComboBox {{
    background: #1E293B;
    color: white;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px 10px;
    min-width: 80px;
}}
QToolBar#MainToolbar QComboBox QAbstractItemView {{
    background: white;
    color: {C['text']};
    selection-background-color: {C['accent_soft']};
    selection-color: {C['accent']};
}}
QToolBar#MainToolbar::separator {{
    background: #334155;
    width: 1px;
    margin: 6px 6px;
}}

/* ---------- Onglets ---------- */
QTabWidget::pane {{
    border: none;
    background: {C['bg']};
    top: -1px;
}}
QTabBar {{
    background: {C['surface']};
}}
QTabBar::tab {{
    background: transparent;
    color: {C['muted']};
    padding: 12px 22px;
    margin: 0;
    border: none;
    border-bottom: 3px solid transparent;
    font-weight: 600;
}}
QTabBar::tab:hover {{
    color: {C['text']};
}}
QTabBar::tab:selected {{
    color: {C['accent']};
    border-bottom: 3px solid {C['accent']};
}}

/* ---------- Cartes & groupes ---------- */
QFrame#Card, QGroupBox {{
    background: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 10px;
}}
QGroupBox {{
    margin-top: 0px;
    padding: 34px 12px 12px 12px;
    font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: padding;
    subcontrol-position: top left;
    left: 14px;
    top: 10px;
    color: {C['text']};
    font-size: 13px;
}}
QFrame#KpiCard {{
    background: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 12px;
}}
QLabel#KpiTitle {{
    color: {C['muted']};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}
QLabel#KpiValue {{
    font-size: 22px;
    font-weight: 700;
}}
QLabel#KpiHint {{
    color: {C['muted']};
    font-size: 11px;
}}
QLabel#PageTitle {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#PageSubtitle, QLabel#Muted {{
    color: {C['muted']};
}}
QLabel#SectionTitle {{
    font-size: 14px;
    font-weight: 700;
}}
QLabel#ProjectHeader {{
    font-size: 17px;
    font-weight: 700;
}}
QLabel#Badge {{
    background: {C['accent_soft']};
    color: {C['accent']};
    border-radius: 10px;
    padding: 3px 10px;
    font-weight: 600;
}}

/* Indicateurs de répartition */
QLabel#Pill {{
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 700;
    background: {C['bg']};
    border: 1px solid {C['border']};
}}
QLabel#Pill[state="ok"] {{
    background: {C['success_soft']};
    color: {C['success']};
    border-color: #86EFAC;
}}
QLabel#Pill[state="warn"] {{
    background: {C['warning_soft']};
    color: {C['warning']};
    border-color: #FCD34D;
}}
QLabel#Pill[state="error"] {{
    background: {C['danger_soft']};
    color: {C['danger']};
    border-color: #FCA5A5;
}}
QProgressBar {{
    border: none;
    background: {C['border']};
    border-radius: 4px;
    height: 8px;
    text-align: center;
    max-height: 8px;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background: {C['accent']};
}}
QProgressBar[state="ok"]::chunk {{ background: {C['success']}; }}
QProgressBar[state="error"]::chunk {{ background: {C['danger']}; }}

/* ---------- Boutons ---------- */
QPushButton {{
    background: {C['surface']};
    border: 1px solid {C['border_strong']};
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {C['bg']};
    border-color: {C['accent']};
}}
QPushButton:pressed {{
    background: {C['accent_soft']};
}}
QPushButton:disabled {{
    color: #94A3B8;
    border-color: {C['border']};
    background: #F8FAFC;
}}
QPushButton[kind="primary"] {{
    background: {C['accent']};
    border-color: {C['accent']};
    color: white;
}}
QPushButton[kind="primary"]:hover {{
    background: {C['accent_hover']};
}}
QPushButton[kind="primary"]:disabled {{
    background: #A5B4FC;
    border-color: #A5B4FC;
    color: white;
}}
QPushButton[kind="danger"] {{
    color: {C['danger']};
}}
QPushButton[kind="danger"]:hover {{
    background: {C['danger_soft']};
    border-color: {C['danger']};
}}
QPushButton[kind="danger"]:disabled {{
    color: #FCA5A5;
}}

/* ---------- Champs ---------- */
QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit, QPlainTextEdit {{
    background: {C['surface']};
    border: 1px solid {C['border_strong']};
    border-radius: 7px;
    padding: 6px 8px;
    selection-background-color: {C['accent']};
    selection-color: white;
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus,
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {C['accent']};
}}
/* Champs internes des spinbox / combos éditables : pas de double bordure */
QAbstractSpinBox QLineEdit, QComboBox QLineEdit {{
    border: none;
    padding: 0;
    margin: 0;
    background: transparent;
}}
/* Spinbox sans flèches : sans cette règle, le champ texte est réduit à 1 px */
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border;
    width: 0px;
    border: none;
}}
QAbstractSpinBox QLineEdit {{
    margin: 0 8px;
}}
QTableWidget QComboBox, QTableWidget QDoubleSpinBox {{
    padding: 2px 6px;
    border-radius: 5px;
}}
QComboBox QAbstractItemView {{
    background: white;
    border: 1px solid {C['border']};
    selection-background-color: {C['accent_soft']};
    selection-color: {C['accent']};
}}
QLineEdit[error="true"], QDoubleSpinBox[error="true"] {{
    border: 1px solid {C['danger']};
    background: #FFF7F7;
}}

/* ---------- Tableaux ---------- */
QTableWidget, QTreeWidget {{
    background: {C['surface']};
    alternate-background-color: #F8FAFC;
    border: 1px solid {C['border']};
    border-radius: 8px;
    gridline-color: transparent;
    selection-background-color: {C['accent_soft']};
    selection-color: {C['text']};
    outline: 0;
}}
QTableWidget::item, QTreeWidget::item {{
    padding: 6px 8px;
    border-bottom: 1px solid #F1F5F9;
}}
QTableWidget::item:selected, QTreeWidget::item:selected {{
    background: {C['accent_soft']};
    color: {C['text']};
}}
QHeaderView::section {{
    background: #F8FAFC;
    color: {C['muted']};
    border: none;
    border-bottom: 1px solid {C['border']};
    padding: 8px;
    font-weight: 700;
    font-size: 11px;
}}
QTableCornerButton::section {{
    background: #F8FAFC;
    border: none;
}}

/* ---------- Divers ---------- */
QStatusBar {{
    background: {C['surface']};
    border-top: 1px solid {C['border']};
    color: {C['muted']};
}}
QStatusBar QLabel {{
    color: {C['muted']};
    padding: 0 8px;
}}
QSplitter::handle {{
    background: transparent;
}}
QSplitter::handle:horizontal {{ width: 10px; }}
QSplitter::handle:vertical {{ height: 10px; }}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {C['border_strong']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {C['border_strong']};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0; height: 0;
}}
QMenuBar {{
    background: {C['surface']};
    border-bottom: 1px solid {C['border']};
}}
QMenuBar::item {{
    padding: 6px 12px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: {C['accent_soft']};
    color: {C['accent']};
}}
QMenu {{
    background: white;
    border: 1px solid {C['border']};
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 24px 6px 18px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {C['accent_soft']};
    color: {C['accent']};
}}
QMenu::separator {{
    height: 1px;
    background: {C['border']};
    margin: 4px 8px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
}}
"""
