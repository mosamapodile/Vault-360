from fastapi.testclient import TestClient
from backend import main

def test_complete_partner_journey(tmp_path,monkeypatch):
    main.DB=tmp_path/'partners.sqlite3';main.seed()
    client=TestClient(main.app)
    auth=client.post('/api/auth/login',json={'email':'thabo@demo.vault360.co.za','pin':'1234'})
    assert auth.status_code==200
    h={'Authorization':'Bearer '+auth.json()['token']}
    providers=client.get('/api/partners',headers=h).json()
    assert {p['id'] for p in providers['partners']}=={'limpopo','township','city'}
    q=client.post('/api/partners/quote',headers=h,json={'partner_id':'limpopo','amount':300,'months':3})
    assert q.status_code==200,q.text
    assert not q.json()['readiness']['ready']
    assert client.post('/api/quest',headers=h,json={'answers':[1,2,0,1,0]}).status_code==200
    q=client.post('/api/partners/quote',headers=h,json={'partner_id':'limpopo','amount':300,'months':3})
    assert q.status_code==200
    assert q.json()['readiness']['ready'],q.json()['readiness']['issues']
    created=client.post('/api/partners/requests',headers=h,json={'partner_id':'limpopo','amount':300,'months':3,'tier':'Start','consent':True})
    assert created.status_code==200,created.text
    rid=created.json()['id']
    for action,expected in [('screen','CONDITIONAL_MATCH'),('accept','ACCEPTED_IN_SANDBOX'),('release','SANDBOX_LEDGER_CREDITED')]:
        x=client.post('/api/partners/requests/'+rid+'/advance',headers=h,json={'action':action})
        assert x.status_code==200,x.text
        assert x.json()['status']==expected
    r=client.get('/api/partners/requests',headers=h).json()[0]
    assert len(r['schedule'])==3
    for x in r['schedule']:
        pay=client.post('/api/partners/requests/'+rid+'/pay/'+x['id'],headers=h)
        assert pay.status_code==200,pay.text
    final=client.get('/api/partners/requests',headers=h).json()[0]
    assert final['status']=='SETTLED_IN_SANDBOX'
    assert len(final['events'])>=8
