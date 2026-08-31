import os, sqlite3, secrets, io, csv, hashlib, base64
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
import pandas as pd
from werkzeug.middleware.proxy_fix import ProxyFix

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get('DB_PATH', os.path.join(BASE, 'cdr_dashboard.db'))
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', os.path.join(BASE, 'uploads'))
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
SECRET_FILE = os.path.join(BASE, '.secret_key')
if os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, 'r', encoding='utf-8') as f: _secret = f.read().strip()
else:
    _secret = secrets.token_hex(32)
    try:
        with open(SECRET_FILE, 'w', encoding='utf-8') as f: f.write(_secret)
    except OSError: pass
app.secret_key = os.environ.get('SECRET_KEY', _secret)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'

SCHOOLS = ['ĐHSP', 'ĐHBK', 'ĐHSPKT', 'ĐHKT', 'ĐHCNTT&TTVH', 'Y Dược']
PASS_DEFAULT = 'DoiMatKhau@2026'
BGH_USERNAME = 'ĐHNN123'
BGH_PASSWORD = 'CDRDHNN123'
BGH_LEGACY_USERNAME = 'DHNN123'
PASS_RESULTS = ('Bậc 3', 'Bậc 4', 'Bậc 5')
SCHOOL_COLORS = {
    'ĐHSP': '#2563eb', 'ĐHBK': '#dc2626', 'ĐHSPKT': '#059669',
    'ĐHKT': '#d97706', 'ĐHCNTT&TTVH': '#7c3aed', 'Y Dược': '#0891b2'
}
RESULT_COLORS = {'Bậc 3':'#16a34a','Bậc 4':'#22c55e','Bậc 5':'#15803d','Không xét':'#94a3b8','vắng':'#f59e0b','đình chỉ thi':'#ef4444','Đình chỉ':'#dc2626'}


def generate_password_hash(password):
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 240000)
    return 'pbkdf2_sha256$240000$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(dk).decode()

def check_password_hash(stored, password):
    try:
        _, rounds, salt_b64, hash_b64 = stored.split('$', 3)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), base64.b64decode(salt_b64), int(rounds))
        return secrets.compare_digest(base64.b64encode(dk).decode(), hash_b64)
    except Exception: return False

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init_db():
    c=db(); c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL,school TEXT,active INTEGER NOT NULL DEFAULT 1,must_change_password INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS exam_records(id INTEGER PRIMARY KEY AUTOINCREMENT,tt INTEGER,sbd TEXT,ma_sv TEXT,ho_ten TEXT,ngay_sinh TEXT,noi_sinh TEXT,lop TEXT,khoa TEXT,ket_qua TEXT,truong TEXT,dot_thi TEXT,nam INTEGER);
    CREATE INDEX IF NOT EXISTS idx_exam_school ON exam_records(truong);
    CREATE INDEX IF NOT EXISTS idx_exam_sv ON exam_records(ma_sv);
    CREATE INDEX IF NOT EXISTS idx_exam_year ON exam_records(nam);
    CREATE INDEX IF NOT EXISTS idx_exam_round ON exam_records(dot_thi);
    ''')
    if not c.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        c.execute('INSERT INTO users(username,password_hash,role,school) VALUES(?,?,?,?)',('admin',generate_password_hash(PASS_DEFAULT),'admin',None))
    bgh=c.execute('SELECT id FROM users WHERE username=?',(BGH_USERNAME,)).fetchone()
    if not bgh:
        legacy=c.execute('SELECT id FROM users WHERE username=?',(BGH_LEGACY_USERNAME,)).fetchone()
        if legacy: c.execute("UPDATE users SET username=?,role='viewer',school=NULL,active=1 WHERE username=?",(BGH_USERNAME,BGH_LEGACY_USERNAME))
        else: c.execute('INSERT INTO users(username,password_hash,role,school,active,must_change_password) VALUES(?,?,?,?,1,1)',(BGH_USERNAME,generate_password_hash(BGH_PASSWORD),'viewer',None))
    else: c.execute("UPDATE users SET role='viewer',school=NULL,active=1 WHERE username=?",(BGH_USERNAME,))
    c.execute('DELETE FROM users WHERE username=? AND username<>?',(BGH_LEGACY_USERNAME,BGH_USERNAME))
    for s in SCHOOLS:
        u='school_'+s.lower().replace('&','and').replace(' ','_')
        if not c.execute('SELECT 1 FROM users WHERE username=?',(u,)).fetchone(): c.execute('INSERT INTO users(username,password_hash,role,school) VALUES(?,?,?,?)',(u,generate_password_hash(PASS_DEFAULT),'school',s))
    c.commit(); c.close()

def current_user():
    uid=session.get('uid')
    if not uid: return None
    c=db(); u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(uid,)).fetchone(); c.close(); return u

def login_required(f):
    @wraps(f)
    def w(*a,**kw):
        if not current_user(): return redirect(url_for('login'))
        return f(*a,**kw)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a,**kw):
        u=current_user()
        if not u: return redirect(url_for('login'))
        if u['role']!='admin': abort(403)
        return f(*a,**kw)
    return w

def restricted_detail(f):
    @wraps(f)
    def w(*a,**kw):
        u=current_user()
        if not u: return redirect(url_for('login'))
        if u['role']=='viewer': abort(403)
        return f(*a,**kw)
    return w

def clean_excel(path_or_file):
    raw=pd.read_excel(path_or_file,header=None)
    data=raw.iloc[3:,:13].copy()
    data.columns=['TT','SBD','MA_SV','HO','TEN','NGAY_SINH','NOI_SINH','LOP','KHOA','KET_QUA','TRUONG','DOT_THI','NAM']
    data=data.dropna(how='all')
    data['HO_TEN']=(data['HO'].fillna('').astype(str).str.strip()+' '+data['TEN'].fillna('').astype(str).str.strip()).str.strip()
    for col in ['SBD','MA_SV','LOP','KHOA','KET_QUA','TRUONG','DOT_THI']: data[col]=data[col].fillna('').astype(str).str.strip()
    data['NAM']=pd.to_numeric(data['NAM'],errors='coerce').astype('Int64'); data['TT']=pd.to_numeric(data['TT'],errors='coerce').astype('Int64')
    data=data[data['MA_SV'].ne('') & data['TRUONG'].ne('')]
    return data[['TT','SBD','MA_SV','HO_TEN','NGAY_SINH','NOI_SINH','LOP','KHOA','KET_QUA','TRUONG','DOT_THI','NAM']]

def import_excel(fileobj):
    data=clean_excel(fileobj); c=db(); c.execute('DELETE FROM exam_records'); rows=[]
    for r in data.itertuples(index=False):
        rows.append((None if pd.isna(r.TT) else int(r.TT),str(r.SBD),str(r.MA_SV),str(r.HO_TEN),'' if pd.isna(r.NGAY_SINH) else str(r.NGAY_SINH),str(r.NOI_SINH),str(r.LOP),str(r.KHOA),str(r.KET_QUA),str(r.TRUONG),str(r.DOT_THI),None if pd.isna(r.NAM) else int(r.NAM)))
    c.executemany('INSERT INTO exam_records(tt,sbd,ma_sv,ho_ten,ngay_sinh,noi_sinh,lop,khoa,ket_qua,truong,dot_thi,nam) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',rows); c.commit(); c.close(); return len(rows)

def filter_parts(u, args=None):
    args=args or request.args; where=[]; p=[]
    if u['role']=='school': where.append('truong=?'); p.append(u['school'])
    vals=[('nam','year'),('khoa','cohort'),('truong','school'),('dot_thi','round'),('ket_qua','result')]
    for field,key in vals:
        v=args.get(key,'').strip()
        if v and (field!='truong' or u['role']=='admin' or v==u['school']): where.append(field+'=?'); p.append(v)
    return (' WHERE '+' AND '.join(where)) if where else '',p

def pct(a,b): return round(a/b*100,2) if b else 0.0

def aggregate(u, args=None):
    W,p=filter_parts(u,args); c=db()
    total=c.execute(f'SELECT COUNT(*) n FROM exam_records{W}',p).fetchone()['n']
    unique=c.execute(f'SELECT COUNT(DISTINCT ma_sv) n FROM exam_records{W}',p).fetchone()['n']
    achieved=c.execute(f"SELECT COUNT(DISTINCT ma_sv) n FROM exam_records{W + (' AND ' if W else ' WHERE ')}ket_qua IN ('Bậc 3','Bậc 4','Bậc 5')",p).fetchone()['n']
    notach=max(unique-achieved,0)
    rounds=c.execute(f'SELECT COUNT(DISTINCT dot_thi) n FROM exam_records{W}',p).fetchone()['n']
    repeat=c.execute(f'''SELECT COUNT(*) n FROM (SELECT ma_sv FROM exam_records{W} GROUP BY ma_sv HAVING COUNT(*)>=2 AND SUM(CASE WHEN ket_qua IN ('Bậc 3','Bậc 4','Bậc 5') THEN 1 ELSE 0 END)=0)''',p).fetchone()['n']
    c.close(); return {'total':total,'unique':unique,'achieved':achieved,'not_achieved':notach,'rate':pct(achieved,unique),'rounds':rounds,'repeat':repeat}

def years_data(u,args=None):
    W,p=filter_parts(u,args); c=db()
    rows=c.execute(f'''SELECT nam year,COUNT(*) attempts,COUNT(DISTINCT ma_sv) students,COUNT(DISTINCT dot_thi) rounds,
      COUNT(DISTINCT CASE WHEN ket_qua IN ('Bậc 3','Bậc 4','Bậc 5') THEN ma_sv END) achieved
      FROM exam_records{W} GROUP BY nam ORDER BY nam''',p).fetchall(); c.close()
    out=[]; prev=None
    for r in rows:
        d=dict(r); d['not']=d['students']-d['achieved']; d['rate']=pct(d['achieved'],d['students'])
        d['growth_students']=None if prev is None else round((d['students']-prev['students'])/prev['students']*100,2) if prev['students'] else None
        d['growth_attempts']=None if prev is None else round((d['attempts']-prev['attempts'])/prev['attempts']*100,2) if prev['attempts'] else None
        d['growth_rate_pp']=None if prev is None else round(d['rate']-prev['rate'],2)
        out.append(d); prev=d
    return out

def school_data(u,args=None):
    W,p=filter_parts(u,args); c=db()
    rows=c.execute(f'''SELECT truong school,COUNT(*) attempts,COUNT(DISTINCT ma_sv) students,
      COUNT(DISTINCT CASE WHEN ket_qua IN ('Bậc 3','Bậc 4','Bậc 5') THEN ma_sv END) achieved,
      COUNT(DISTINCT dot_thi) rounds FROM exam_records{W} GROUP BY truong ORDER BY students DESC''',p).fetchall(); c.close()
    return [dict(r,not_=r['students']-r['achieved'],rate=pct(r['achieved'],r['students']),color=SCHOOL_COLORS.get(r['school'],'#64748b')) for r in rows]

def round_data(u,args=None):
    W,p=filter_parts(u,args); c=db()
    rows=c.execute(f'''SELECT nam year,dot_thi round,COUNT(*) attempts,COUNT(DISTINCT ma_sv) students,
      COUNT(DISTINCT CASE WHEN ket_qua IN ('Bậc 3','Bậc 4','Bậc 5') THEN ma_sv END) achieved
      FROM exam_records{W} GROUP BY nam,dot_thi ORDER BY nam,dot_thi''',p).fetchall(); c.close()
    return [dict(r,not_=r['students']-r['achieved'],rate=pct(r['achieved'],r['students'])) for r in rows]

def result_data(u,args=None):
    W,p=filter_parts(u,args); c=db(); rows=c.execute(f'SELECT ket_qua result,COUNT(*) n FROM exam_records{W} GROUP BY ket_qua ORDER BY n DESC',p).fetchall(); c.close()
    total=sum(r['n'] for r in rows); return [dict(r,rate=pct(r['n'],total),color=RESULT_COLORS.get(r['result'],'#64748b')) for r in rows]

def filter_options(u):
    W,p=filter_parts(u,{'year':'','cohort':'','school':'','round':'','result':''}); c=db(); out={}
    for col in ['nam','khoa','truong','dot_thi','ket_qua']:
        rs=c.execute(f'SELECT DISTINCT {col} v FROM exam_records{W} ORDER BY {col}',p).fetchall(); out[col]=[r['v'] for r in rs if r['v'] not in (None,'')]
    c.close(); return out

@app.context_processor
def inject(): return {'user':current_user(),'school_list':SCHOOLS,'school_colors':SCHOOL_COLORS}

@app.get('/health')
def health(): return {'status':'ok'}

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form.get('username','').strip(); password=request.form.get('password','')
        c=db(); u=c.execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone(); c.close()
        if u and check_password_hash(u['password_hash'],password):
            session.clear(); session['uid']=u['id']
            if u['must_change_password']: return redirect(url_for('change_password'))
            return redirect(url_for('index'))
        flash('Tài khoản hoặc mật khẩu không đúng.','error')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/change-password',methods=['GET','POST'])
@login_required
def change_password():
    if request.method=='POST':
        old=request.form.get('old',''); new=request.form.get('new','')
        u=current_user()
        if not check_password_hash(u['password_hash'],old) or len(new)<8: flash('Mật khẩu cũ không đúng hoặc mật khẩu mới quá ngắn.','error')
        else:
            c=db(); c.execute('UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?',(generate_password_hash(new),u['id'])); c.commit(); c.close(); flash('Đổi mật khẩu thành công.','ok'); return redirect(url_for('index'))
    return render_template('change_password.html')

@app.route('/')
@login_required
def index():
    u=current_user(); return render_template('dashboard.html',d=aggregate(u),years=years_data(u),schools=school_data(u),results=result_data(u),opts=filter_options(u),filters={k:request.args.get(k,'') for k in ['year','cohort','school','round','result']})

@app.route('/executive')
@login_required
def executive():
    u=current_user(); return render_template('executive.html',d=aggregate(u),years=years_data(u),schools=school_data(u))

@app.route('/years')
@login_required
def years():
    u=current_user(); return render_template('years.html',d=aggregate(u),rows=years_data(u),opts=filter_options(u))

@app.route('/schools')
@login_required
def schools():
    u=current_user(); return render_template('schools.html',d=aggregate(u),rows=school_data(u),opts=filter_options(u))

@app.route('/rounds')
@login_required
def rounds():
    u=current_user(); rows=round_data(u); return render_template('rounds.html',d=aggregate(u),rows=rows)

@app.route('/students')
@restricted_detail
def students():
    u=current_user(); q=request.args.get('q','').strip(); status=request.args.get('status','all'); school=request.args.get('school',''); where=[];p=[]
    if u['role']=='school': where.append('truong=?');p.append(u['school'])
    elif school: where.append('truong=?');p.append(school)
    if q: where.append('(ma_sv LIKE ? OR ho_ten LIKE ?)');p += [f'%{q}%',f'%{q}%']
    W=' WHERE '+' AND '.join(where) if where else ''
    c=db(); rs=c.execute(f'''SELECT ma_sv,MAX(ho_ten) ho_ten,MAX(truong) truong,MAX(khoa) khoa,COUNT(*) attempts,MAX(dot_thi) latest_round,
      MAX(CASE WHEN ket_qua IN ('Bậc 3','Bậc 4','Bậc 5') THEN 1 ELSE 0 END) achieved FROM exam_records{W} GROUP BY ma_sv ORDER BY attempts DESC,ma_sv LIMIT 1000''',p).fetchall();c.close()
    out=[]
    for r in rs:
        st='Đã đạt' if r['achieved'] else ('Rất cao' if r['attempts']>=3 else ('Cao' if r['attempts']>=2 else 'Theo dõi'))
        if status=='all' or st==status: out.append(dict(r,status=st))
    return render_template('students.html',rows=out,q=q,status=status,school=school)

@app.route('/student/<ma_sv>')
@restricted_detail
def student_detail(ma_sv):
    u=current_user(); c=db(); rows=c.execute('SELECT * FROM exam_records WHERE ma_sv=? ORDER BY nam,dot_thi',(ma_sv,)).fetchall();c.close()
    if not rows: abort(404)
    if u['role']=='school' and rows[0]['truong']!=u['school']: abort(403)
    return render_template('student.html',rows=rows,ma_sv=ma_sv)

@app.route('/data')
@admin_required
def data_view():
    q=request.args.get('q','').strip(); school=request.args.get('school',''); year=request.args.get('year',''); where=[];p=[]
    if q: where.append('(ma_sv LIKE ? OR ho_ten LIKE ?)');p += [f'%{q}%',f'%{q}%']
    if school: where.append('truong=?');p.append(school)
    if year: where.append('nam=?');p.append(year)
    W=' WHERE '+' AND '.join(where) if where else ''
    c=db(); rows=c.execute(f'SELECT tt,sbd,ma_sv,ho_ten,khoa,ket_qua,truong,dot_thi,nam FROM exam_records{W} ORDER BY nam DESC,truong,ma_sv LIMIT 2000',p).fetchall(); c.close()
    return render_template('data.html',rows=rows,q=q,school=school,year=year,years=filter_options(current_user())['nam'])

@app.route('/admin')
@admin_required
def admin():
    c=db(); users=c.execute('SELECT id,username,role,school,active,must_change_password FROM users ORDER BY role DESC,username').fetchall(); n=c.execute('SELECT COUNT(*) n FROM exam_records').fetchone()['n'];c.close(); return render_template('admin.html',users=users,n=n,default_password=PASS_DEFAULT)

@app.post('/admin/upload')
@admin_required
def upload():
    f=request.files.get('file')
    if not f or not f.filename.lower().endswith(('.xlsx','.xls')): flash('Vui lòng chọn file Excel (.xlsx/.xls).','error'); return redirect(url_for('admin'))
    try: flash(f'Đã cập nhật {import_excel(f):,} lượt thi vào hệ thống.','ok')
    except Exception as e: flash('Không thể nhập Excel: '+str(e),'error')
    return redirect(url_for('admin'))

@app.post('/admin/user')
@admin_required
def create_user():
    username=request.form.get('username','').strip(); role=request.form.get('role','school'); school=request.form.get('school','').strip()
    if not username or role not in ('school','viewer'): flash('Thông tin tài khoản không hợp lệ.','error'); return redirect(url_for('admin'))
    if role=='school' and school not in SCHOOLS: flash('Tài khoản trường phải gắn với một trường hợp lệ.','error'); return redirect(url_for('admin'))
    if role=='viewer': school=None
    c=db()
    try: c.execute('INSERT INTO users(username,password_hash,role,school) VALUES(?,?,?,?)',(username,generate_password_hash(PASS_DEFAULT),role,school));c.commit();flash('Đã tạo tài khoản.','ok')
    except sqlite3.IntegrityError: flash('Tên tài khoản đã tồn tại.','error')
    finally: c.close()
    return redirect(url_for('admin'))

@app.post('/admin/user/<int:uid>/toggle')
@admin_required
def toggle_user(uid):
    c=db();c.execute('UPDATE users SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=? AND role IN ("school","viewer")',(uid,));c.commit();c.close();return redirect(url_for('admin'))

@app.route('/export')
@admin_required
def export_csv():
    c=db(); rows=c.execute('SELECT tt,sbd,ma_sv,ho_ten,ngay_sinh,noi_sinh,lop,khoa,ket_qua,truong,dot_thi,nam FROM exam_records ORDER BY truong,ma_sv,nam').fetchall();c.close()
    out=io.StringIO();w=csv.writer(out);w.writerow(['TT','SBD','Mã SV','Họ tên','Ngày sinh','Nơi sinh','Lớp','Khóa','Kết quả','Trường','Đợt thi','Năm']);w.writerows([tuple(r) for r in rows]);out.seek(0)
    return send_file(io.BytesIO(out.getvalue().encode('utf-8-sig')),as_attachment=True,download_name='du_lieu_CDR.csv',mimetype='text/csv')

init_db()
if __name__=='__main__': app.run(host=os.environ.get('HOST','0.0.0.0'),port=int(os.environ.get('PORT','5000')))
