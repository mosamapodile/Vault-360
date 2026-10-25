import os, io, importlib
from datetime import date
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

def sample_pdf():
    buf=io.BytesIO(); c=canvas.Canvas(buf);c.drawString(30,780,'SYNTHETIC BANK TRANSACTIONS - NEVER REAL FINANCIAL DATA')
    c.drawString(30,735,f'{date.today().isoformat()} Weekend market sales 350.00')
    c.drawString(30,714,f'{date.today().isoformat()} Transport -55.00')
    c.save();return buf.getvalue()

def test_statement_preview_confirmation(tmp_path,monkeypatch):
    monkeypatch.setenv('VAULT_DB',str(tmp_path/'isolated.db'))
    from backend import main
    main.DB=tmp_path/'isolated.db';main.seed()
    client=TestClient(main.app)
    login=client.post('/api/auth/login',json={'email':'thabo@demo.vault360.co.za','pin':'1234'})
    h={'Authorization':'Bearer '+login.json()['token']}
    assert client.post('/api/statements/preview',headers=h,files={'file':('a.txt',b'not pdf','text/plain')}).status_code==400
    resp=client.post('/api/statements/preview',headers=h,files={'file':('statement.pdf',sample_pdf(),'application/pdf')})
    assert resp.status_code==200,resp.text
    body=resp.json(); assert body['detected']==2,body
    assert body['pdf_saved'] is False
    deny=client.post('/api/statements/confirm',headers=h,json={'rows':body['rows'],'consent':False})
    assert deny.status_code==400
    ok=client.post('/api/statements/confirm',headers=h,json={'rows':body['rows'],'consent':True})
    assert ok.status_code==200 and ok.json()['imported']==2
    directory=client.get('/api/partners',headers=h).json()
    assert directory['live_connections']==0
    assert len(directory['partners'])==3
    setting=client.patch('/api/me',headers=h,json={'language':'sasl'})
    assert setting.status_code==200
