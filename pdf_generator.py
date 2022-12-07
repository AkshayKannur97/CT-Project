""" *********************************************************************
Author:         Akshay C P
Date:           29 Nov 2022
Description:    Script to generate a pdf report.
********************************************************************* """

from datetime import datetime
from fpdf import FPDF


pdf = FPDF(orientation = 'P', unit = 'mm', format = 'A4')
pdf.add_page()
pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf', uni=True)
pdf.set_font('dejavu', '', 10)
pdf.set_text_color(255/3, 255/3, 255/3)

pdf.image('./res/img/verified.png', x = 50, y = 50, w = 110, h = 197)

pdf.text(10, 10, "Hello World")
pdf.text(170, 10, datetime.now().strftime("%Y-%m-%d %H:%M"))

pdf.set_xy(20, 20)
pdf.cell(50, 20, "ID", border=1, align="L", fill=0)

pdf.set_xy(70, 20)
pdf.cell(50, 20, "W001", border=1, align="L", fill=0)

pdf.set_xy(20, 40)
pdf.cell(50, 20, "MATERIAL", border=1, align="L", fill=0)

pdf.set_xy(70, 40)
pdf.cell(50, 20, "GOLD", border=1, align="L", fill=0)

pdf.set_xy(20, 60)
pdf.cell(50, 20, "DISPLACEMENT", border=1, align="L", fill=0)

pdf.set_xy(70, 60)
pdf.cell(50, 20, "10 cm", border=1, align="L", fill=0)

pdf.output('Automated PDF Report.pdf')