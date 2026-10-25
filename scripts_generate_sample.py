"""Creates fictional, parser-friendly financial statement for safe local testing."""
from pathlib import Path
from datetime import date,timedelta
from reportlab.pdfgen import canvas
out=Path(__file__).parent/'assets'/'SYNTHETIC-statement-demo.pdf'
c=canvas.Canvas(str(out),pagesize=(595,842))
c.setFont('Helvetica-Bold',20);c.drawString(48,778,'VAULT 360 / SAMPLE STATEMENT')
c.setFont('Helvetica',11);c.drawString(48,752,'FICTIONAL DEMO DATA - NOT A BANK STATEMENT')
c.drawString(48,732,'Use this sample in the PDF importer. No real customer records.')
for i in range(21):
    d=(date.today()-timedelta(days=i*4)).isoformat()
    desc='Market delivery income' if i%3 else 'Groceries'
    amt=round(220+(i%4)*65,2) if i%3 else -round(75+(i%4)*14,2)
    c.drawString(48,700-i*27,f'{d} {desc} {amt:.2f}')
c.save();print(out)
