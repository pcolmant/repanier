"""
Entrepôt centralisé des styles openpyxl pour tous les exports Excel de Repanier.
"""

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# Polices (Fonts)
FONT_TITLE = Font(name="Calibri", size=14, bold=True)
FONT_HEADER = Font(name="Calibri", size=11, bold=True)
FONT_NORMAL = Font(name="Calibri", size=11, bold=False)
FONT_BOLD = Font(name="Calibri", size=11, bold=True)
FONT_BOLD_ITALIC = Font(name="Calibri", size=11, bold=True, italic=True)
FONT_ITALIC = Font(name="Calibri", size=11, italic=True)
FONT_RED = Font(name="Calibri", size=11, color="FF0000FF")
FONT_BLUE = Font(name="Calibri", size=11, color="FF0000FF")
FONT_GRAY = Font(name="Calibri", size=11, color="FF939393")
FONT_RED_BOLD = Font(name="Calibri", size=11, bold=True, color="FF0000FF")
FONT_LABEL_BIG = Font(size=36)

# Remplissages (Fills)
FILL_YELLOW = PatternFill(fill_type="solid", start_color="FFFF00", end_color="FFFF00")
FILL_HEADER = PatternFill(fill_type="solid", start_color="E0E0E0", end_color="E0E0E0")

# Alignements
ALIGN_CENTER = Alignment(wrap_text=False, vertical="center", horizontal="center")
ALIGN_RIGHT = Alignment(horizontal="right")
ALIGN_LEFT_WRAP = Alignment(wrap_text=True)
ALIGN_LEFT_NOWRAP = Alignment(wrap_text=False)

# Bordures
BORDER_THIN = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
BORDER_TOP_THIN = Border(top=Side(style="thin"))
BORDER_BOTTOM_THIN = Border(bottom=Side(style="thin"))
BORDER_TOP_THIN_BOTTOM_THIN = Border(top=Side(style="thin"), bottom=Side(style="thin"))
BORDER_BOTTOM_MEDIUM_DASHED = Border(bottom=Side(style="mediumDashed"))
BORDER_HAIR = Border(bottom=Side(style="hair"))
BORDER_LABEL_TOP = Border(
    top=Side(style="thin"), left=Side(style="thin"), right=Side(style="thin")
)
BORDER_LABEL_BOTTOM = Border(
    bottom=Side(style="thin"), left=Side(style="thin"), right=Side(style="thin")
)