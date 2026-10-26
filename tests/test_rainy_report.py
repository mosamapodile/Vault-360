import os
from fastapi.testclient import TestClient
from backend import main
from pypdf import PdfReader
import io


def test_rainy_goal_progress_and_report(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB', tmp_path / 'rainy-test.sqlite3')
    main.seed()
    with TestClient(main.app) as client:
        login = client.post('/api/auth/login', json={'email':'thabo@demo.vault360.co.za','pin':'1234'})
        assert login.status_code == 200
        h={'Authorization':'Bearer '+login.json()['token']}
        initial=client.get('/api/rainy-day',headers=h)
        assert initial.status_code==200 and initial.json()['goal'] is None
        bad=client.post('/api/rainy-day/entries',headers=h,json={'amount':20})
        assert bad.status_code==400
        assert client.put('/api/rainy-day/goal',headers=h,json={'purpose':'Emergency transport','target':1000}).status_code ==200
        assert client.post('/api/rainy-day/entries',headers=h,json={'amount':80}).status_code ==200
        state=client.get('/api/rainy-day',headers=h).json()
        assert state['goal']['target']==1000 and state['recorded_savings']==80
        assert state['suggested_monthly_contribution']<=100
        assert client.get('/api/reports/readiness.pdf').status_code==401
        resp=client.get('/api/reports/readiness.pdf',headers=h)
        assert resp.status_code==200 and resp.content.startswith(b'%PDF')
        reader=PdfReader(io.BytesIO(resp.content))
        assert len(reader.pages)==1
        content=reader.pages[0].extract_text()
        assert 'NOT A PAYSLIP' in content
        assert 'Thabo Mokoena' in content
