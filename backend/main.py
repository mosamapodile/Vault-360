"""Vault 360: illustrative microcredit orchestration demo, NOT a lending service."""
import os, sqlite3, json, secrets, hashlib, hmac, time, csv, io, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DB = Path(os.getenv('VAULT_DB', str(ROOT / 'vault360.sqlite3')))
DEMO_MODE = os.getenv('VAULT_DEMO_MODE', 'true').lower() == 'true'
app = FastAPI(title='Vault 360 Demo API', version='1.0.0', docs_url='/api/docs', openapi_url='/api/openapi.json')
TOKENS = {}  # intentionally ephemeral: demo only

def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys = ON')
    return c

def uid(): return secrets.token_hex(10)
def now(): return datetime.now(timezone.utc).isoformat()
def round_money(x): return round(float(x) + 1e-9, 2)

def seed():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS rainy_day_goals(user_id TEXT PRIMARY KEY, target REAL NOT NULL, purpose TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS rainy_day_entries(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, amount REAL NOT NULL, noted_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, pin_hash TEXT NOT NULL, salt TEXT NOT NULL, language TEXT DEFAULT 'en', accessibility INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS transactions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL, day TEXT NOT NULL, description TEXT NOT NULL, amount REAL NOT NULL, category TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS comprehension(user_id TEXT PRIMARY KEY,score INTEGER NOT NULL,answers TEXT NOT NULL,completed_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS assessments(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,created_at TEXT NOT NULL, result TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS applications(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,tier TEXT NOT NULL,amount REAL NOT NULL,status TEXT NOT NULL,assessment_id TEXT NOT NULL,created_at TEXT NOT NULL, decision_note TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS repayments(id TEXT PRIMARY KEY,application_id TEXT NOT NULL,day TEXT NOT NULL,amount REAL NOT NULL,status TEXT NOT NULL, FOREIGN KEY(application_id) REFERENCES applications(id));
        CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,user_id TEXT,event TEXT NOT NULL,details TEXT NOT NULL,occurred_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS partner_requests(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,partner_id TEXT NOT NULL,tier TEXT NOT NULL,amount REAL NOT NULL,monthly_payment REAL NOT NULL,total_repayable REAL NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,decision TEXT NOT NULL,consent INTEGER NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS partner_events(id TEXT PRIMARY KEY,request_id TEXT NOT NULL,event TEXT NOT NULL,description TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(request_id) REFERENCES partner_requests(id));
        CREATE TABLE IF NOT EXISTS partner_schedules(id TEXT PRIMARY KEY,request_id TEXT NOT NULL,due_on TEXT NOT NULL,amount REAL NOT NULL,status TEXT NOT NULL,paid_on TEXT,FOREIGN KEY(request_id) REFERENCES partner_requests(id));
        ''')
        if not db.execute('SELECT 1 FROM users WHERE email=?', ('thabo@demo.vault360.co.za',)).fetchone():
            salt = secrets.token_hex(16)
            db.execute('INSERT INTO users(id,name,email,pin_hash,salt) VALUES(?,?,?,?,?)',('demo-thabo','Thabo Mokoena','thabo@demo.vault360.co.za', hash_pin('1234',salt),salt))
            from datetime import date, timedelta
            today=date.today()
            for age in range(89,-1,-1):
                day=(today-timedelta(days=age)).isoformat()
                # Several periodic small receipts: delivery / repairs / sales, never a salary
                if age % 3 == 0: add_tx(db,'demo-thabo',day,'Local delivery income',370 + (age % 7)*33,'income')
                if age % 7 == 1: add_tx(db,'demo-thabo',day,'Weekend market sales',680 + (age % 4)*85,'income')
                if age % 5 == 2: add_tx(db,'demo-thabo',day,'Supplies and stock',-(210 + (age % 3)*30),'business')
                if age % 6 == 4: add_tx(db,'demo-thabo',day,'Groceries',-245,'living')
                if age % 11 == 5: add_tx(db,'demo-thabo',day,'Transport',-160,'transport')

def hash_pin(pin, salt): return hashlib.pbkdf2_hmac('sha256',pin.encode(),bytes.fromhex(salt),160000).hex()
def add_tx(db,user_id,day,description,amount,category):
    db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?)',(uid(),user_id,day,description,round_money(amount),category))
def audit(db,user_id,event,details):
    db.execute('INSERT INTO audit VALUES(?,?,?,?,?)',(uid(),user_id,event,json.dumps(details),now()))

@app.on_event('startup')
def startup(): seed()

class Login(BaseModel):
    email: str
    pin: str
class Settings(BaseModel):
    language: Optional[str] = None
    accessibility: Optional[bool] = None
class Answer(BaseModel):
    answers: list[int] = Field(min_length=5,max_length=5)
class Application(BaseModel):
    tier: str
    amount: float = Field(gt=0,le=5000)
    acknowledged: bool
class TxIn(BaseModel):
    day: str
    description: str = Field(min_length=2,max_length=120)
    amount: float = Field(ge=-100000,le=100000)
    category: str

QUESTIONS = [
    {'id':1,'q':'What is the total cost of credit?','choices':['Only the amount borrowed','The amount borrowed plus fees and interest','Only the monthly instalment'],'correct':1},
    {'id':2,'q':'If a payment date falls before your usual earnings, you should…','choices':['Ignore the due date','Borrow from another lender immediately','Contact the lender to discuss options before it is overdue'],'correct':2},
    {'id':3,'q':'Why do lenders assess affordability?','choices':['To check if repayments leave money for living costs','To reward people who borrow frequently','To guarantee everyone approval'],'correct':0},
    {'id':4,'q':'Which statement about variable income is correct?','choices':['Your best month guarantees the next month','Budget using a conservative view of your income','Expenses do not matter'],'correct':1},
    {'id':5,'q':'Before accepting a credit agreement, you should…','choices':['Read the costs, dates and terms','Only look at the approved amount','Share your PIN with a broker'],'correct':0},
]

async def user(authorization: Optional[str]=Header(None)):
    token=(authorization or '').removeprefix('Bearer ').strip()
    info=TOKENS.get(token)
    if not info or info['expiry'] < time.time(): raise HTTPException(401,'Sign in to continue')
    with connection() as db:
        row=db.execute('SELECT id,name,email,language,accessibility FROM users WHERE id=?',(info['uid'],)).fetchone()
        if not row: raise HTTPException(401,'Session expired')
        return dict(row)

@app.get('/api/health')
def health(): return {'status':'ok','mode':'DEMO','lending_enabled':False}

@app.post('/api/auth/login')
def login(data:Login):
    with connection() as db:
        row=db.execute('SELECT * FROM users WHERE email=?',(data.email.strip().lower(),)).fetchone()
        if not row or not hmac.compare_digest(hash_pin(data.pin,row['salt']),row['pin_hash']): raise HTTPException(401,'Invalid email or PIN')
        token=secrets.token_urlsafe(36); TOKENS[token]={'uid':row['id'],'expiry':time.time()+3600*8}
        audit(db,row['id'],'login',{'demo':True})
        return {'token':token,'user':{'name':row['name'],'email':row['email'],'language':row['language'],'accessibility':bool(row['accessibility'])}}

@app.post('/api/auth/logout')
def logout(authorization: Optional[str]=Header(None)):
    TOKENS.pop((authorization or '').removeprefix('Bearer ').strip(),None)
    return {'ok':True}

@app.get('/api/me')
def me(u=Depends(user)): return {**u,'accessibility':bool(u['accessibility'])}

@app.patch('/api/me')
def settings(data:Settings,u=Depends(user)):
    with connection() as db:
        if data.language is not None:
            if data.language not in ('en','zu','nso','xh','af','st','tn','ss','ve','ts','nr','sasl'): raise HTTPException(400,'Unsupported language code')
            db.execute('UPDATE users SET language=? WHERE id=?',(data.language,u['id']))
        if data.accessibility is not None: db.execute('UPDATE users SET accessibility=? WHERE id=?',(int(data.accessibility),u['id']))
        audit(db,u['id'],'preferences_updated',data.model_dump(exclude_none=True))
    return {'ok':True}

@app.get('/api/transactions')
def transactions(u=Depends(user)):
    with connection() as db:
        return [dict(r) for r in db.execute('SELECT id,day,description,amount,category FROM transactions WHERE user_id=? ORDER BY day DESC,id DESC',(u['id'],))]

@app.post('/api/transactions')
def create_tx(data:TxIn,u=Depends(user)):
    if data.category not in ('income','business','living','transport','other'): raise HTTPException(400,'Invalid category')
    if (data.category=='income') != (data.amount>0): raise HTTPException(400,'Income must be positive; expenses must be zero or negative')
    try: day=datetime.strptime(data.day,'%Y-%m-%d').date()
    except ValueError: raise HTTPException(400,'Invalid date')
    from datetime import date,timedelta
    if day > date.today() or day < date.today()-timedelta(days=89): raise HTTPException(400,'Only transactions from the past 90 days may be added')
    with connection() as db:
        add_tx(db,u['id'],data.day,data.description,data.amount,data.category)
        audit(db,u['id'],'transaction_added',{'category':data.category,'amount':data.amount})
    return {'ok':True}

@app.post('/api/transactions/import')
async def import_csv(file:UploadFile=File(...),u=Depends(user)):
    if not (file.filename or '').lower().endswith('.csv'): raise HTTPException(400,'Upload a CSV file')
    raw=await file.read(256001)
    if len(raw)>256000: raise HTTPException(413,'Maximum CSV size is 250 KB')
    try:
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        if len(rows)>500: raise ValueError('Maximum 500 rows')
        batch=[]
        from datetime import date,timedelta
        for row in rows:
            day=datetime.strptime(row['day'],'%Y-%m-%d').date()
            if day > date.today() or day < date.today()-timedelta(days=89): raise ValueError('Date outside past 90 days')
            amount=float(row['amount']); category=row['category'].lower().strip()
            if category not in ('income','business','living','transport','other') or (category=='income') != (amount>0) or abs(amount)>100000: raise ValueError('Invalid amount/category')
            batch.append((day.isoformat(),row['description'][:120],amount,category))
        if not batch: raise ValueError('No rows found')
    except (ValueError,KeyError,TypeError,UnicodeDecodeError) as exc: raise HTTPException(400,f'CSV rejected: {exc}')
    with connection() as db:
        for r in batch: add_tx(db,u['id'],*r)
        audit(db,u['id'],'csv_import',{'count':len(batch)})
    return {'ok':True,'imported':len(batch)}


# Private PDF preview: process in memory, never save PDF bytes, require user confirmation before importing.
# Supported: text-based PDFs with ISO or DD/MM/YYYY dates, description, signed amount.
# Not a universal bank-statement parser; scanned/encrypted/complex column statements need review.
class ConfirmImport(BaseModel):
    rows: list[TxIn] = Field(min_length=1,max_length=350)
    consent: bool

@app.post('/api/statements/preview')
async def statement_preview(file:UploadFile=File(...),u=Depends(user)):
    if not (file.filename or '').lower().endswith('.pdf'):
        raise HTTPException(400,'Choose a PDF statement')
    raw=await file.read(3_000_001)
    if len(raw)>3_000_000: raise HTTPException(413,'Maximum PDF size is 3 MB')
    if not raw.startswith(b'%PDF-'): raise HTTPException(400,'Invalid PDF signature')
    try:
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(raw),strict=True)
        if reader.is_encrypted: raise HTTPException(422,'Password-protected PDFs are not supported. Do not share your bank password.')
        if len(reader.pages)>20: raise HTTPException(413,'Limit 20 pages')
        content='\n'.join(page.extract_text(extraction_mode='layout') or '' for page in reader.pages)
    except HTTPException: raise
    except Exception: raise HTTPException(422,'Could not read PDF; use a text-based verified statement')
    rows=[]
    # Conservative matching: avoids misreading balance columns as actual transaction amounts.
    pattern=re.compile(r'^\s*(\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4})\s+(.{3,85}?)\s+(-?\d{1,3}(?:[ ,]\d{3})*(?:[.]\d{2})|-?\d+[.]\d{2})\s*$',re.M)
    from datetime import date,timedelta
    for m in pattern.finditer(content):
        day,desc,raw_amount=m.groups()
        try:
            if day[2] in '/-': day=datetime.strptime(day.replace('/','-'),'%d-%m-%Y').date()
            else: day=date.fromisoformat(day)
            amount=round_money(float(raw_amount.replace(' ','').replace(',','')))
        except ValueError: continue
        if not date.today()-timedelta(days=89)<=day<=date.today() or amount==0 or abs(amount)>100000: continue
        category='income' if amount>0 else 'other'
        rows.append({'day':day.isoformat(),'description':desc.strip(),'amount':amount,'category':category})
    return {'rows':rows[:350],'detected':len(rows),'needs_review':True,'message':('Review every detected amount and category before importing. PDF layouts vary.' if rows else 'No unambiguous transactions found. FNB statements often have multiple amount columns; use manual entry until a verified mapping is developed.'),'pdf_saved':False}

@app.post('/api/statements/confirm')
def confirm_statement(data:ConfirmImport,u=Depends(user)):
    if not data.consent: raise HTTPException(400,'Consent to save selected parsed entries is required')
    from datetime import date,timedelta
    checked=[]
    for r in data.rows:
        try: day=date.fromisoformat(r.day)
        except ValueError: raise HTTPException(400,'Invalid date')
        if not date.today()-timedelta(days=89)<=day<=date.today(): raise HTTPException(400,'Date outside 90 days')
        if r.category not in ('income','business','living','transport','other') or (r.category=='income')!=(r.amount>0): raise HTTPException(400,'Invalid amount/category')
        checked.append(r)
    with connection() as db:
        for r in checked: add_tx(db,u['id'],r.day,r.description,r.amount,r.category)
        audit(db,u['id'],'pdf_rows_confirmed',{'count':len(checked)})
    return {'ok':True,'imported':len(checked),'disclosure':'Uploaded PDF was never stored; confirmed entries saved in demo SQLite'}

# FICTITIOUS sandbox-only organisations; not licensed or real institutions.
PARTNERS = [
 {'id':'limpopo','name':'Mavela Community Credit','short':'Mavela','region':'Rural Limpopo','location':'Giyani / villages','icon':'🌿','type':'Community-first','tagline':'Your work matters, wherever you earn.','story':'Built around farmers, market traders and mobile service providers whose income follows seasonal and weekly rhythms.','focus':['Market-day income','Seasonal cash flow','Low-bandwidth access'],'min_amount':200,'max_amount':1200,'terms':[3,4],'annual_rate':0.12,'service_fee':0},
 {'id':'township','name':'KasiRise Finance Network','short':'KasiRise','region':'Township economies','location':'Soweto & townships','icon':'🏘️','type':'Local enterprise','tagline':'For the hustle behind every street.','story':'Designed for spaza traders, stylists, delivery riders and informal businesses building income through community trade.','focus':['Trade and gig history','Frequent deposits','Local merchants'],'min_amount':300,'max_amount':2000,'terms':[3,4],'annual_rate':0.15,'service_fee':0},
 {'id':'city','name':'MetroBridge Credit Collective','short':'MetroBridge','region':'City and urban','location':'Johannesburg metro','icon':'🌆','type':'Urban opportunity','tagline':'A path forward, even without a payslip.','story':'For freelancers, creators, self-employed professionals and platform workers with diverse incoming payments.','focus':['Multiple income sources','Freelance invoices','Urban mobility'],'min_amount':500,'max_amount':3000,'terms':[3,4],'annual_rate':0.18,'service_fee':0},
]

@app.get('/api/partners')
def partners(u=Depends(user)):
    return {'environment':'LOCAL_SANDBOX','live_connections':0,'partners':PARTNERS,'disclaimer':'All partner names, rates and decisions are fictional and for product testing. No external credit provider is connected.'}

class PartnerQuote(BaseModel):
    partner_id: str
    amount: float = Field(ge=100,le=3000)
    months: int = Field(ge=3,le=4)

class PartnerRequest(PartnerQuote):
    tier: str
    consent: bool

class PartnerAction(BaseModel):
    action: str

def quote_values(spec, amount, months):
    if amount < spec['min_amount'] or amount > spec['max_amount'] or months not in spec['terms']:
        raise HTTPException(400,'Amount or term is outside partner sandbox parameters')
    interest=round_money(amount * spec['annual_rate'] * months/12)
    total=round_money(amount+interest+spec['service_fee'])
    return {'principal':round_money(amount),'interest':interest,'fee':spec['service_fee'],'total_repayable':total,'monthly_payment':round_money(total/months),'months':months,'annual_rate':spec['annual_rate']}

def get_partner(pid):
    partner=next((x for x in PARTNERS if x['id']==pid),None)
    if partner is None: raise HTTPException(404,'Partner not found')
    return partner

def partner_eligibility(db,uid_,q):
    m=compute(uid_,db)
    literacy=db.execute('SELECT score FROM comprehension WHERE user_id=?',(uid_,)).fetchone()
    issues=[]
    if not literacy: issues.append('Complete the financial understanding quest')
    elif literacy['score']<60: issues.append('Revisit the financial understanding quest')
    if m['transaction_count']<12: issues.append('Provide at least 12 transaction records')
    if not m['eligible_for_demo']: issues.append('Insufficient consistent disposable cash flow in the current 90-day view')
    if q['monthly_payment']>m['indicative_monthly_repayment_cap']: issues.append('Estimated repayment exceeds the conservative planning cap')
    return {'ready':not issues,'issues':issues,'income_analysis':m,'literacy_score':literacy['score'] if literacy else None}

@app.post('/api/partners/quote')
def partner_quote(data:PartnerQuote,u=Depends(user)):
    p=get_partner(data.partner_id);q=quote_values(p,data.amount,data.months)
    with connection() as db: review=partner_eligibility(db,u['id'],q)
    return {'partner':p,'quote':q,'readiness':review,'disclaimer':'Fictional sandbox pricing for product testing, not a quotation from a real provider.'}

def event(db,rid,name,description):
    db.execute('INSERT INTO partner_events VALUES(?,?,?,?,?)',(uid(),rid,name,description,now()))

@app.post('/api/partners/requests')
def submit_partner_request(data:PartnerRequest,u=Depends(user)):
    if not data.consent: raise HTTPException(400,'Consent is required to share an illustrative assessment in the local sandbox')
    p=get_partner(data.partner_id)
    if data.tier not in ('Start','Grow','Plus'): raise HTTPException(400,'Invalid tier')
    tier_ceiling={'Start':1000,'Grow':2000,'Plus':3000}[data.tier]
    if data.amount>tier_ceiling: raise HTTPException(400,'Selected tier limit exceeded')
    q=quote_values(p,data.amount,data.months)
    with connection() as db:
        review=partner_eligibility(db,u['id'],q)
        if not review['ready']: raise HTTPException(400,'Not ready: '+'; '.join(review['issues']))
        rid=uid(); timestamp=now()
        db.execute('INSERT INTO partner_requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,u['id'],p['id'],data.tier,q['principal'],q['monthly_payment'],q['total_repayable'],'SUBMITTED',timestamp,timestamp,'Awaiting sandbox screening',1))
        event(db,rid,'REQUEST_CREATED','You prepared a consented Vault 360 financial summary')
        event(db,rid,'PARTNER_RECEIVED',p['name']+' sandbox adapter received the request')
        audit(db,u['id'],'partner_sandbox_request',{'id':rid,'partner_id':p['id'],'amount':q['principal']})
    return {'id':rid,'status':'SUBMITTED','message':'Request delivered to a local fictional partner adapter; continue to the decision step.'}

@app.get('/api/partners/requests')
def partner_requests(u=Depends(user)):
    with connection() as db:
        rows=[]
        for r in db.execute('SELECT * FROM partner_requests WHERE user_id=? ORDER BY created_at DESC',(u['id'],)):
            x=dict(r)
            x['partner']=get_partner(x['partner_id'])
            x['events']=[dict(e) for e in db.execute('SELECT event,description,created_at FROM partner_events WHERE request_id=? ORDER BY rowid',(x['id'],))]
            x['schedule']=[dict(e) for e in db.execute('SELECT id,due_on,amount,status,paid_on FROM partner_schedules WHERE request_id=? ORDER BY due_on',(x['id'],))]
            rows.append(x)
    return rows

@app.post('/api/partners/requests/{rid}/advance')
def advance_request(rid:str, data:PartnerAction,u=Depends(user)):
    from datetime import date,timedelta
    with connection() as db:
        row=db.execute('SELECT * FROM partner_requests WHERE id=? AND user_id=?',(rid,u['id'])).fetchone()
        if not row: raise HTTPException(404,'Request not found')
        status=row['status']; action=data.action
        next_status=None
        if status=='SUBMITTED' and action=='screen':
            m=compute(u['id'],db)
            if row['monthly_payment']>m['indicative_monthly_repayment_cap']:
                next_status='NEEDS_REVIEW';desc='Sandbox screening flags affordability for human review'
            else:
                next_status='CONDITIONAL_MATCH';desc='Sandbox partner found an illustrative match; no actual approval'
        elif status=='CONDITIONAL_MATCH' and action=='accept':
            next_status='ACCEPTED_IN_SANDBOX';desc='You accepted a fictional matched offer for walkthrough purposes'
            months=max(3,round(row['total_repayable']/row['monthly_payment']))
            # recurring planning dates anchored to user-selected cadence demonstration (not bank mandates)
            for n in range(1,months+1):
                due=(date.today()+timedelta(days=n*30)).isoformat()
                amount=row['monthly_payment'] if n<months else round_money(row['total_repayable']-row['monthly_payment']*(months-1))
                db.execute('INSERT INTO partner_schedules VALUES(?,?,?,?,?,?)',(uid(),rid,due,amount,'PLANNED',None))
        elif status=='CONDITIONAL_MATCH' and action=='decline':
            next_status='DECLINED_BY_USER';desc='You decided not to continue'
        elif status=='ACCEPTED_IN_SANDBOX' and action=='release':
            next_status='SANDBOX_LEDGER_CREDITED';desc='A fictional credit event was recorded in the test ledger; no payment occurred'
        else: raise HTTPException(409,'That action is not available at this stage')
        db.execute('UPDATE partner_requests SET status=?,updated_at=?,decision=? WHERE id=?',(next_status,now(),desc,rid))
        event(db,rid,next_status,desc)
        audit(db,u['id'],'partner_sandbox_action',{'request_id':rid,'action':action,'status':next_status})
    return {'id':rid,'status':next_status,'message':desc}

@app.post('/api/partners/requests/{rid}/pay/{schedule_id}')
def pay_schedule(rid:str,schedule_id:str,u=Depends(user)):
    with connection() as db:
        row=db.execute('SELECT status FROM partner_requests WHERE id=? AND user_id=?',(rid,u['id'])).fetchone()
        if not row or row['status'] not in ('SANDBOX_LEDGER_CREDITED','REPAYMENT_IN_PROGRESS','SETTLED_IN_SANDBOX'):
            raise HTTPException(409,'Sandbox ledger must be credited before recording repayments')
        x=db.execute('SELECT * FROM partner_schedules WHERE id=? AND request_id=?',(schedule_id,rid)).fetchone()
        if not x or x['status']!='PLANNED': raise HTTPException(409,'Payment unavailable')
        db.execute('UPDATE partner_schedules SET status=?,paid_on=? WHERE id=?',('PAID_SANDBOX',now(),schedule_id))
        left=db.execute('SELECT COUNT(*) FROM partner_schedules WHERE request_id=? AND status=?',(rid,'PLANNED')).fetchone()[0]
        new_status='SETTLED_IN_SANDBOX' if left==0 else 'REPAYMENT_IN_PROGRESS'
        db.execute('UPDATE partner_requests SET status=?,updated_at=? WHERE id=?',(new_status,now(),rid))
        event(db,rid,'REPAYMENT_RECORDED','Illustrative repayment recorded in local ledger')
        if left==0: event(db,rid,'SETTLED_IN_SANDBOX','All fictional repayments completed')
        audit(db,u['id'],'sandbox_payment',{'request_id':rid,'schedule_id':schedule_id})
    return {'status':new_status,'remaining':left,'message':'Only the local simulation ledger was updated; no money moved.'}

@app.get('/api/quest')
def quest(u=Depends(user)):
    with connection() as db: record=db.execute('SELECT score,completed_at FROM comprehension WHERE user_id=?',(u['id'],)).fetchone()
    return {'questions':[{k:v for k,v in q.items() if k!='correct'} for q in QUESTIONS], 'result':dict(record) if record else None}

@app.post('/api/quest')
def submit_quest(data:Answer,u=Depends(user)):
    if any(a not in (0,1,2) for a in data.answers): raise HTTPException(400,'Answers must be 0, 1 or 2')
    score=round(sum(a==q['correct'] for a,q in zip(data.answers,QUESTIONS))/len(QUESTIONS)*100)
    with connection() as db:
        db.execute('INSERT INTO comprehension VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET score=excluded.score,answers=excluded.answers,completed_at=excluded.completed_at',(u['id'],score,json.dumps(data.answers),now()))
        audit(db,u['id'],'financial_comprehension_completed',{'score':score})
    return {'score':score,'message':'Educational score only, not a credit score or lending decision'}

def compute(u_id, db):
    from datetime import date,timedelta
    records=[dict(r) for r in db.execute('SELECT day,amount,category FROM transactions WHERE user_id=? AND day>=?',(u_id,(date.today()-timedelta(days=89)).isoformat()))]
    months=[{'income':0,'expenses':0} for _ in range(3)]
    for r in records:
        age=(date.today()-date.fromisoformat(r['day'])).days
        i=min(2,age//30)
        if r['amount']>0: months[i]['income']+=r['amount']
        else: months[i]['expenses']+=abs(r['amount'])
    incomes=[round_money(m['income']) for m in months]
    expenses=[round_money(m['expenses']) for m in months]
    avg=sum(incomes)/3; conservative=min(incomes) if incomes else 0
    mean=avg; std=(sum((v-mean)**2 for v in incomes)/3)**.5
    volatility=round(std/mean*100,1) if mean else 100
    avg_expense=sum(expenses)/3
    # heuristic: retain essential expenses and a contingency; NOT a credit model
    cash_velocity=max(0,round_money(min(conservative,avg*.8)-avg_expense- max(300,avg*.15)))
    eligible= len(records)>=12 and all(v>0 for v in incomes) and cash_velocity>=200
    return {'days':90,'transaction_count':len(records),'monthly_income':incomes,'monthly_expenses':expenses,'total_income':round_money(sum(incomes)),'income_average':round_money(avg),'income_volatility_pct':volatility,'disposable_cash_velocity':cash_velocity,'indicative_monthly_repayment_cap':round_money(min(cash_velocity*.25,650)),'eligible_for_demo':eligible,'reason':('Illustrative affordability threshold met' if eligible else 'Insufficient documented cash flow for the demo threshold'), 'method':'Conservative three-period income minus average expenses and a contingency; 25% of remainder capped at R650 as a demo guardrail. Not a credit score or regulatory affordability assessment.'}

@app.get('/api/assessment')
def assessment(u=Depends(user)):
    with connection() as db:
        metrics=compute(u['id'],db)
        q=db.execute('SELECT score FROM comprehension WHERE user_id=?',(u['id'],)).fetchone()
        metrics['comprehension_score']=q['score'] if q else None
        metrics['quest_complete']=q is not None
        metrics['tiers']=tier_options(metrics)
        return metrics

def tier_options(m):
    # No actual offer, just cap examples; demo amounts require separate review
    caps={'Start':1000,'Grow':2000,'Plus':3000}
    n=m['transaction_count']; cap=m['indicative_monthly_repayment_cap']
    return [{'name':name,'limit':limit,'illustrative_repayment':round_money(limit/3),'available': bool(m['eligible_for_demo'] and m['quest_complete'] and m['comprehension_score']>=60 and cap>=limit/3 and n>=12+(i*6))} for i,(name,limit) in enumerate(caps.items())]

@app.post('/api/applications')
def apply(data:Application,u=Depends(user)):
    if not data.acknowledged: raise HTTPException(400,'Acknowledge the demo disclosure')
    with connection() as db:
        m=compute(u['id'],db)
        q=db.execute('SELECT score FROM comprehension WHERE user_id=?',(u['id'],)).fetchone()
        m['quest_complete']=q is not None;m['comprehension_score']=q['score'] if q else None
        options={t['name']:t for t in tier_options(m)}
        t=options.get(data.tier)
        if not t: raise HTTPException(400,'Unknown tier')
        if not t['available']: raise HTTPException(400,'This illustrative tier is not available based on the demo guardrails')
        if round_money(data.amount)>t['limit']: raise HTTPException(400,'Amount exceeds this tier cap')
        if round_money(data.amount/3)>m['indicative_monthly_repayment_cap']: raise HTTPException(400,'Amount exceeds the illustrative repayment guardrail')
        aid=uid();mid=uid()
        db.execute('INSERT INTO assessments VALUES(?,?,?,?)',(mid,u['id'],now(),json.dumps(m)))
        db.execute('INSERT INTO applications VALUES(?,?,?,?,?,?,?,?)',(aid,u['id'],data.tier,round_money(data.amount),'DEMO_REVIEW',mid,now(),'Simulation only. No lender has made an offer; no funds will be disbursed.'))
        # Align illustrative instalments to recorded income peaks over coming months, not actual mandates
        from datetime import date,timedelta
        for i in range(1,4):
            day=(date.today()+timedelta(days=i*30)).isoformat()
            db.execute('INSERT INTO repayments VALUES(?,?,?,?,?)',(uid(),aid,day,round_money(data.amount/3),'PLANNED_DEMO'))
        audit(db,u['id'],'demo_application_created',{'tier':data.tier,'amount':data.amount})
        return {'id':aid,'status':'DEMO_REVIEW','message':'Saved as a demo simulation only; no credit agreement or payout exists.'}

@app.get('/api/applications')
def applications(u=Depends(user)):
    with connection() as db:
        result=[]
        for row in db.execute('SELECT * FROM applications WHERE user_id=? ORDER BY created_at DESC',(u['id'],)):
            x=dict(row);x['repayments']=[dict(r) for r in db.execute('SELECT day,amount,status FROM repayments WHERE application_id=? ORDER BY day',(x['id'],))]
            result.append(x)
        return result

@app.get('/api/audit')
def audit_log(u=Depends(user)):
    with connection() as db: return [dict(r) for r in db.execute('SELECT event,details,occurred_at FROM audit WHERE user_id=? ORDER BY occurred_at DESC LIMIT 30',(u['id'],))]


# --- Rainy Day: educational planning only; NEVER a deposit account or wallet ---
class RainyDayGoal(BaseModel):
    target: float = Field(ge=50,le=100000)
    purpose: str = Field(min_length=3,max_length=80)

class RainyDayEntry(BaseModel):
    amount: float = Field(gt=0,le=100000)

@app.get('/api/rainy-day')
def rainy_day(u=Depends(user)):
    with connection() as db:
        goal=db.execute('SELECT target,purpose FROM rainy_day_goals WHERE user_id=?',(u['id'],)).fetchone()
        entries=db.execute('SELECT id,amount,noted_at FROM rainy_day_entries WHERE user_id=? ORDER BY noted_at DESC',(u['id'],)).fetchall()
        m=compute(u['id'],db)
        saved=round_money(sum(row['amount'] for row in entries))
        # Planner heuristic, not a command to save. Preserve essentials and never make a real transfer.
        suggested=round_money(min(100,max(0,m['disposable_cash_velocity']*.05)))
        return {'goal':dict(goal) if goal else None,'recorded_savings':saved,'entries':[dict(e) for e in entries],
                'suggested_monthly_contribution':suggested,'note':'Planner only. No savings are held, transferred, or verified. Do not set aside money needed for food, rent, transport, debt payments or other essentials.'}

@app.put('/api/rainy-day/goal')
def set_rainy_day_goal(data:RainyDayGoal,u=Depends(user)):
    with connection() as db:
        db.execute('INSERT INTO rainy_day_goals(user_id,target,purpose,created_at) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET target=excluded.target,purpose=excluded.purpose',(u['id'],round_money(data.target),data.purpose.strip(),now()))
        audit(db,u['id'],'rainy_day_goal_saved',{'target':data.target})
    return {'message':'Savings planning goal saved. No money has moved.'}

@app.post('/api/rainy-day/entries')
def add_rainy_day_entry(data:RainyDayEntry,u=Depends(user)):
    with connection() as db:
        if not db.execute('SELECT 1 FROM rainy_day_goals WHERE user_id=?',(u['id'],)).fetchone(): raise HTTPException(400,'Create a goal first')
        db.execute('INSERT INTO rainy_day_entries VALUES(?,?,?,?)',(uid(),u['id'],round_money(data.amount),now()))
        audit(db,u['id'],'rainy_day_progress_noted',{'amount':data.amount})
    return {'message':'Progress noted manually. Vault 360 did not receive money.'}

@app.get('/api/reports/readiness.pdf')
def readiness_pdf(u=Depends(user)):
    # On-demand PDF generated in memory. No PDFs are stored server-side.
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from xml.sax.saxutils import escape
    buf=io.BytesIO(); w,h=A4; doc=canvas.Canvas(buf,pagesize=A4)
    dark=HexColor('#09282b'); teal=HexColor('#009e95'); gold=HexColor('#e5a900')
    with connection() as db:
        m=compute(u['id'],db)
        q=db.execute('SELECT score FROM comprehension WHERE user_id=?',(u['id'],)).fetchone()
    doc.setFillColor(dark);doc.rect(0,h-125,w,125,fill=1,stroke=0)
    doc.setFillColor(gold);doc.setFont('Helvetica-Bold',13);doc.drawString(42,h-43,'VAULT 360')
    doc.setFillColor(HexColor('#ffffff'));doc.setFont('Helvetica-Bold',19);doc.drawString(42,h-73,'Financial Readiness Snapshot')
    doc.setFont('Helvetica',10);doc.drawString(42,h-95,'Educational assessment  |  DEMO / NOT VERIFIED')
    doc.setFillColor(dark);doc.setFont('Helvetica-Bold',11)
    doc.drawString(42,h-155,'Profile: '+u['name'][:72])
    doc.setFont('Helvetica',10);doc.drawString(42,h-174,'Prepared: '+datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC'))
    doc.drawString(42,h-190,'Assessment period: most recent 90 days (three 30-day periods)')
    doc.setStrokeColor(teal);doc.line(42,h-209,w-42,h-209)
    fields=[
      ('Recorded inflows (90 days)',f"R {m['total_income']:,.2f}"),
      ('Average monthly inflows',f"R {m['income_average']:,.2f}"),
      ('Income volatility',f"{m['income_volatility_pct']:.1f}%"),
      ('Transaction records analysed',str(m['transaction_count'])),
      ('Estimated conservative monthly cash',f"R {m['disposable_cash_velocity']:,.2f}"),
      ('Illustrative monthly repayment guardrail',f"R {m['indicative_monthly_repayment_cap']:,.2f}"),
      ('Financial comprehension result',str(q['score'])+'%' if q else 'Not completed'),
      ('Prototype assessment', 'Ready for an illustrative review' if m['eligible_for_demo'] else 'More documented activity needed')
    ]
    y=h-245
    for i,(label,value) in enumerate(fields):
        if i%2==0:
            doc.setFillColor(HexColor('#edf7f6'));doc.rect(42,y-12,w-84,28,stroke=0,fill=1)
        doc.setFillColor(dark);doc.setFont('Helvetica',9);doc.drawString(50,y,label)
        doc.setFont('Helvetica-Bold',10);doc.drawRightString(w-50,y,value)
        y-=32
    y-=14
    doc.setFillColor(teal);doc.setFont('Helvetica-Bold',11);doc.drawString(42,y,'How this snapshot is calculated')
    y-=20
    for line in [
        'Transaction data is grouped into three 30-day periods.',
        'Conservative cash estimates account for weaker income periods,',
        'average expenses and a fixed contingency allowance.',
        'Amounts are heuristic estimates, not verified funds or a legal affordability test.'
    ]:
        doc.setFillColor(dark);doc.setFont('Helvetica',9);doc.drawString(42,y,line);y-=15
    y-=15
    doc.setFillColor(HexColor('#fdf1cc'));doc.roundRect(42,y-78,w-84,88,9,fill=1,stroke=0)
    doc.setFillColor(dark);doc.setFont('Helvetica-Bold',10);doc.drawString(52,y-10,'IMPORTANT — NOT A PAYSLIP OR CREDIT APPROVAL')
    for i,line in enumerate([
        'Vault 360 is not a lender, bank, credit bureau or document verifier.',
        'This is an educational, self-reported/sandbox financial-readiness summary.',
        'It is not proof of income, a certified statement, a credit score, or a loan offer.',
        'Lenders must independently verify information, perform KYC and affordability checks.',
    ]):
        doc.setFont('Helvetica',8.5);doc.drawString(52,y-28-i*14,line)
    doc.setFillColor(dark);doc.setFont('Helvetica',8);doc.drawString(42,38,'Vault 360 | Different Paydays. Real Possibilities. | Demo data only')
    doc.showPage();doc.save();buf.seek(0)
    return Response(content=buf.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="Vault360-Readiness-Snapshot.pdf"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

app.mount('/assets',StaticFiles(directory=str(ROOT/'assets')),name='assets')
app.mount('/static',StaticFiles(directory=str(ROOT/'frontend')),name='static')
@app.get('/')
def home(): return FileResponse(ROOT/'frontend'/'index.html')

# Serve frontend assets when testing locally.
# These routes do not interfere with existing /api endpoints.

@app.get("/styles.css", include_in_schema=False)
def local_styles():
    return FileResponse(
        ROOT / "frontend" / "styles.css",
        media_type="text/css"
    )


@app.get("/app.js", include_in_schema=False)
def local_javascript():
    return FileResponse(
        ROOT / "frontend" / "app.js",
        media_type="application/javascript"
    )


@app.get("/favicon.svg", include_in_schema=False)
def local_favicon():
    return FileResponse(
        ROOT / "frontend" / "favicon.svg",
        media_type="image/svg+xml"
    )