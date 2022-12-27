""" *********************************************************************
Author:         Akshay C P
Date:           29 Nov 2022
Description:    Script to generate a pdf report.
********************************************************************* """

from datetime import datetime
from fpdf import FPDF


def generate_pdf(data):
    if type(data) is not dict:
        data = data.__dict__
    
    pdf = FPDF(orientation = 'P', unit = 'mm', format = 'A4')
    pdf.set_auto_page_break(False)
    pdf.add_page()
    # pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', uni=True)
    pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
    pdf.set_font('dejavu', '', 10)
    pdf.set_text_color(255/3, 255/3, 255/3)

    pdf.set_line_width(1)
    pdf.rect(0, 0, 210, 297)

    try:
        pdf.image('./res/img/logo1.jpeg', x = 5, y = 5, w = 25, h = 25)
    except (FileNotFoundError, RuntimeError):
        pdf.rect(5, 5, 25, 25)
    try:
        pdf.image('./res/img/logo2.jpeg', x = 210-25-5, y = 5, w = 25, h = 25)
    except (FileNotFoundError, RuntimeError):
        pdf.rect(210-25-5, 5, 25, 25)

    # pdf.text(210, 10, "Hello World")
    # pdf.text(170, 10, datetime.now().strftime("%Y-%m-%d %H:%M"))

    pdf.set_xy(0, 0)
    pdf.cell(210, 35, "", border=1, align="C", fill=0)
    pdf.set_xy(0, 5)
    pdf.set_font('', '', 24)
    pdf.cell(210, 10, "HEADER1", border=0, align="C", fill=0)
    pdf.set_xy(0, 15)
    pdf.set_font('', '', 20)
    pdf.cell(210, 10, "HEADER2", border=0, align="C", fill=0)
    pdf.set_xy(0, 25)
    pdf.set_font('', '', 16)
    pdf.cell(210, 10, "HEADER3", border=0, align="C", fill=0)

    # Body
    pdf.set_font('', 'U', 14)
    pdf.set_xy(10, 40)
    pdf.cell(60, 10, "TEST DETAILS", border=0, align="L", fill=0)
    pdf.set_font('', '', 10)
    pdf.set_xy(120, 40)
    pdf.cell(60, 10, "DATE & TIME", border=0, align="L", fill=0)
    pdf.set_xy(160, 40)
    pdf.cell(60, 10, (data.get('output_datetime') or datetime.now()).strftime('%Y/%m/%d %H:%M:%S'), border=0, align="L", fill=0)
    pdf.set_xy(10, 50)
    pdf.cell(60, 10, "TEST NUMBER", border=0, align="L", fill=0)
    pdf.set_xy(10, 60)
    pdf.cell(60, 10, "CUSTOMER/VENDOR CODE", border=0, align="L", fill=0)
    pdf.set_xy(10, 70)
    pdf.cell(60, 10, "CUSTOMER/VENDOR NAME", border=0, align="L", fill=0)
    pdf.set_xy(10, 80)
    pdf.cell(60, 10, "PRODUCT CODE", border=0, align="L", fill=0)
    pdf.set_xy(10, 90)
    pdf.cell(60, 10, "PRODUCT NAME", border=0, align="L", fill=0)

    pdf.set_xy(60, 50)
    pdf.cell(60, 10, data['output_test_number'] or '', border=0, align="L", fill=0)
    pdf.set_xy(60, 60)
    pdf.cell(60, 10, data.get('customer_details', {}).get('code', ''), border=0, align="L", fill=0)
    pdf.set_xy(60, 70)
    pdf.cell(60, 10, data.get('customer_details', {}).get('name', ''), border=0, align="L", fill=0)
    pdf.set_xy(60, 80)
    pdf.cell(60, 10, data.get('product_details', {}).get('name', ''), border=0, align="L", fill=0)
    pdf.set_xy(60, 90)
    pdf.cell(60, 10, data.get('product_details', {}).get('code', ''), border=0, align="L", fill=0)

    pdf.set_xy(120, 50)
    pdf.cell(60, 10, "INVOICE NUMBER", border=0, align="L", fill=0)
    pdf.set_xy(120, 60)
    pdf.cell(60, 10, "MACHINE NUMBER", border=0, align="L", fill=0)
    pdf.set_xy(120, 70)
    pdf.cell(60, 10, "LOT NUMBER", border=0, align="L", fill=0)
    pdf.set_xy(120, 80)
    pdf.cell(60, 10, "REMARKS", border=0, align="L", fill=0)
    pdf.set_xy(120, 90)
    pdf.cell(60, 10, "SIZE", border=0, align="L", fill=0)
    pdf.set_xy(120, 100)
    # pdf.cell(60, 10, "DATE", border=0, align="L", fill=0)
    # pdf.set_xy(120, 110)
    # pdf.cell(60, 10, "TIME", border=0, align="L", fill=0)

    pdf.set_xy(160, 50)
    pdf.cell(60, 10, data.get('output_invoice_number') or '', border=0, align="L", fill=0)
    pdf.set_xy(160, 60)
    pdf.cell(60, 10, data.get('output_machine_number') or '', border=0, align="L", fill=0)
    pdf.set_xy(160, 70)
    pdf.cell(60, 10, data.get('output_lot_number') or '', border=0, align="L", fill=0)
    pdf.set_xy(160, 80)
    pdf.cell(60, 10, data.get('output_remarks') or '', border=0, align="L", fill=0)
    pdf.set_xy(160, 90)
    pdf.cell(60, 10, data.get('output_size') or '', border=0, align="L", fill=0)
    

    pdf.set_font('', 'U', 14)
    pdf.set_xy(10, 110)
    pdf.cell(60, 10, "GRAPH", border=0, align="L", fill=0)
    pdf.set_line_width(0.5)
    pdf.set_draw_color(1, 1, 1)
    pdf.set_fill_color(200, 200, 200)
    pdf.rect(10, 120, 190, 120, 'DF')
    try:
        pdf.image(data.get('canvas_path', './res/img/blank_graph.png'), x=10, y =120, w = 190, h = 120)
    except FileNotFoundError:
        pass

    pdf.set_font('', 'U', 14)
    pdf.set_xy(10, 250)
    pdf.cell(60, 10, "RESULT VALUE", border=0, align="L", fill=0)
    pdf.set_font('', '', 10)
    pdf.set_xy(60, 250)
    pdf.cell(60, 10, "PEAK (Kg)", border=0, align="L", fill=0)
    pdf.set_xy(120, 250)
    pdf.cell(60, 10, "DISP (mm)", border=0, align="L", fill=0)
    pdf.set_xy(10, 260)
    pdf.cell(60, 10, "PEAK1", border=0, align="L", fill=0)
    pdf.set_xy(60, 260)
    pdf.cell(60, 10, "131", border=0, align="L", fill=0)
    pdf.set_xy(120, 260)
    pdf.cell(60, 10, "11.6", border=0, align="L", fill=0)

    pdf.set_line_width(1)
    pdf.rect(0, 285, 210, 23)
    pdf.set_font('', '', 14)
    pdf.text(20, 292, "TESTED BY:")
    pdf.text(120, 292, "AUTHORIZED BY:")

    output_file_name = 'Automated PDF Report.pdf'
    pdf.output(output_file_name)
    return output_file_name

if __name__ == '__main__':
    from datetime import datetime
    generate_pdf({
        'customer_details': {'code': 'JASH', 'name': 'JASH PACKAGING'},
        'product_details': {'code': '401143', 'name': '35 GM MASALA MAMRA'},
        'output_machine_number': '4321',
        'output_lot_number': '1',
        'output_invoice_number': '192',
        'output_test_number': '2387',
        'canvas_path': './res/img/blank_graph.png',
        'output_datetime': datetime.now()
    })
