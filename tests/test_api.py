import os,tempfile
fd,path=tempfile.mkstemp(suffix='.sqlite3');os.close(fd)
os.environ['VAULT_DB']=path
from fastapi.testclient import TestClient
from backend.main import app,seed
seed()
client=TestClient(app)
def auth():
    resp=client.post('/api/auth/login',json={'email':'thabo@demo.vault360.co.za','pin':'1234'})
    assert resp.status_code==200
    return {'Authorization':'Bearer '+resp.json()['token']}
def test_health():
    r=client.get('/api/health');assert r.status_code==200 and not r.json()['lending_enabled']
def test_login_and_guards():
    assert client.get('/api/assessment').status_code==401
    assert client.post('/api/auth/login',json={'email':'thabo@demo.vault360.co.za','pin':'wrong'}).status_code==401
    h=auth();a=client.get('/api/assessment',headers=h).json()
    assert a['transaction_count']>10 and len(a['monthly_income'])==3
    assert a['comprehension_score'] is None
    assert client.post('/api/applications',headers=h,json={'tier':'Start','amount':600,'acknowledged':True}).status_code==400
def test_quest_and_application():
    h=auth()
    r=client.post('/api/quest',headers=h,json={'answers':[1,2,0,1,0]});assert r.status_code==200 and r.json()['score']==100
    a=client.get('/api/assessment',headers=h).json()
    assert a['tiers'][0]['available']
    r=client.post('/api/applications',headers=h,json={'tier':'Start','amount':600,'acknowledged':True})
    assert r.status_code==200,r.text
    assert r.json()['status']=='DEMO_REVIEW'
    assert len(client.get('/api/applications',headers=h).json()[0]['repayments'])==3
def test_locale_csv_validation():
    h=auth()
    assert client.patch('/api/me',headers=h,json={'language':'nso'}).status_code==200
    assert client.patch('/api/me',headers=h,json={'language':'xx'}).status_code==400
    data=b'day,description,amount,category\n2099-01-01,Invalid future,100,income\n'
    r=client.post('/api/transactions/import',headers=h,files={'file':('transactions.csv',data,'text/csv')})
    assert r.status_code==400
