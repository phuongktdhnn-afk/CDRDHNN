import os, sqlite3, secrets, io, csv
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
import hashlib, base64

def generate_password_hash(password):
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 240000)
    return 'pbkdf2_sha256$240000$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(dk).decode()

def check_password_hash(stored, password):
    try:
        _, rounds, salt_b64, hash_b64 = stored.split('$', 3)
        salt = base64.b64decode(salt_b64)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(rounds))
        return secrets.compare_digest(base64.b64encode(dk).decode(), hash_b64)
    except Exception:
        return False
import pandas as pd
from werkzeug.middleware.proxy_fix import ProxyFix

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get('DB_PATH', os.path.join(BASE, 'cdr_dashboard.db'))
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', os.path.join(BASE, 'uploads'))
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
SECRET_FILE = os.path.join(BASE, '.secret_key')
if os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, 'r', encoding='utf-8') as _f:
        _secret = _f.read().strip()
else:
    _secret = secrets.token_hex(32)
    with open(SECRET_FILE, 'w', encoding='utf-8') as _f:
        _f.write(_secret)
app.secret_key = os.environ.get('SECRET_KEY', _secret)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'


@app.get('/health')
def health():
    return {'status': 'ok'}

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

SCHOOLS = ['ĐHSP', 'ĐHBK', 'ĐHSPKT', 'ĐHKT', 'ĐHCNTT&TTVH', 'Y Dược']
PASS_DEFAULT = 'DoiMatKhau@2026'
BGH_USERNAME = 'ĐHNN123'
BGH_PASSWORD = 'CDRDHNN123'
# Tên tài khoản cũ không dấu được giữ như bí danh để tránh lỗi khi nâng cấp bản cũ.
BGH_LEGACY_USERNAME = 'DHNN123'
SCHOOL_COLORS = {
    'ĐHSP': '#2563eb',
    'ĐHBK': '#dc2626',
    'ĐHSPKT': '#059669',
    'ĐHKT': '#d97706',
    'ĐHCNTT&TTVH': '#7c3aed',
    'Y Dược': '#0891b2',
}


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','school','viewer')),
        school TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        must_change_password INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS exam_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tt INTEGER, sbd TEXT, ma_sv TEXT, ho_ten TEXT, ngay_sinh TEXT,
        noi_sinh TEXT, lop TEXT, khoa TEXT, ket_qua TEXT, truong TEXT,
        dot_thi TEXT, nam INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_exam_school ON exam_records(truong);
    CREATE INDEX IF NOT EXISTS idx_exam_sv ON exam_records(ma_sv);
    CREATE INDEX IF NOT EXISTS idx_exam_year ON exam_records(nam);
    ''')
    if not c.execute('SELECT 1 FROM users WHERE username=?', ('admin',)).fetchone():
        c.execute('INSERT INTO users(username,password_hash,role,school) VALUES(?,?,?,?)',
                  ('admin', generate_password_hash(PASS_DEFAULT), 'admin', None))
    # Tài khoản BGH chính thức: xem tổng hợp toàn hệ thống, không cập nhật/chỉnh sửa/xuất dữ liệu.
    # Nếu tài khoản đã tồn tại thì giữ mật khẩu đã đổi; nếu chưa có thì tạo đúng thông tin đăng nhập ban đầu.
    bgh = c.execute('SELECT id FROM users WHERE username=?', (BGH_USERNAME,)).fetchone()
    if not bgh:
        # Nếu bản cũ đã tạo DHNN123 thì đổi tên sang tài khoản chính thức có dấu.
        legacy = c.execute('SELECT id FROM users WHERE username=?', (BGH_LEGACY_USERNAME,)).fetchone()
        if legacy:
            c.execute("UPDATE users SET username=?, role='viewer', school=NULL, active=1 WHERE username=?",
                      (BGH_USERNAME, BGH_LEGACY_USERNAME))
        else:
            c.execute('INSERT INTO users(username,password_hash,role,school,active,must_change_password) VALUES(?,?,?,?,1,1)',
                      (BGH_USERNAME, generate_password_hash(BGH_PASSWORD), 'viewer', None))
    else:
        c.execute("UPDATE users SET role='viewer', school=NULL, active=1 WHERE username=?", (BGH_USERNAME,))
    # Không để tồn tại tài khoản bí danh trùng quyền; nếu migration gặp xung đột thì giữ tài khoản chính thức.
    c.execute('DELETE FROM users WHERE username=? AND username<>?', (BGH_LEGACY_USERNAME, BGH_USERNAME))
    for s in SCHOOLS:
        u = 'school_' + s.lower().replace('&','and').replace(' ','_')
        if not c.execute('SELECT 1 FROM users WHERE username=?', (u,)).fetchone():
            c.execute('INSERT INTO users(username,password_hash,role,school) VALUES(?,?,?,?)',
                      (u, generate_password_hash(PASS_DEFAULT), 'school', s))
    c.commit(); c.close()


def clean_excel(path_or_file):
    raw = pd.read_excel(path_or_file, header=None)
    header = raw.iloc[2].tolist()
    # first 13 columns are the actual structured fields in the supplied workbook
    data = raw.iloc[3:, :13].copy()
    data.columns = ['TT','SBD','MÃ SV','HỌ VÀ TÊN','NƠI SINH?','NGÀY SINH','NƠI SINH','LỚP','Khóa','KẾT QUẢ','Trường','Đợt thi','Năm']
    # In the supplied file the first 5 columns include merged HỌ/TÊN; the actual order is TT,SBD,MÃ SV,HỌ,TÊN,NGÀY SINH,NƠI SINH,LỚP,Khóa,KẾT QUẢ,Trường,Đợt thi,Năm
    data = raw.iloc[3:, :13].copy()
    data.columns = ['TT','SBD','MA_SV','HO','TEN','NGAY_SINH','NOI_SINH','LOP','KHOA','KET_QUA','TRUONG','DOT_THI','NAM']
    data = data.dropna(how='all')
    data['HO_TEN'] = (data['HO'].fillna('').astype(str).str.strip() + ' ' + data['TEN'].fillna('').astype(str).str.strip()).str.strip()
    # some rows can have date-like strings; keep as display text
    for col in ['SBD','MA_SV','LOP','KHOA','KET_QUA','TRUONG','DOT_THI']:
        data[col] = data[col].fillna('').astype(str).str.strip()
    data['NAM'] = pd.to_numeric(data['NAM'], errors='coerce').astype('Int64')
    data['TT'] = pd.to_numeric(data['TT'], errors='coerce').astype('Int64')
    data = data[data['MA_SV'].ne('') & data['TRUONG'].ne('')]
    return data[['TT','SBD','MA_SV','HO_TEN','NGAY_SINH','NOI_SINH','LOP','KHOA','KET_QUA','TRUONG','DOT_THI','NAM']]


def import_excel(fileobj):
    data = clean_excel(fileobj)
    c = db()
    c.execute('DELETE FROM exam_records')
    rows=[]
    for r in data.itertuples(index=False):
        ngay = '' if pd.isna(r.NGAY_SINH) else str(r.NGAY_SINH)
        nam = None if pd.isna(r.NAM) else int(r.NAM)
        tt = None if pd.isna(r.TT) else int(r.TT)
        rows.append((tt,str(r.SBD),str(r.MA_SV),str(r.HO_TEN),ngay,str(r.NOI_SINH),str(r.LOP),str(r.KHOA),str(r.KET_QUA),str(r.TRUONG),str(r.DOT_THI),nam))
    c.executemany('''INSERT INTO exam_records(tt,sbd,ma_sv,ho_ten,ngay_sinh,noi_sinh,lop,khoa,ket_qua,truong,dot_thi,nam)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', rows)
    c.commit(); c.close()
    return len(rows)


def current_user():
    uid = session.get('uid')
    if not uid: return None
    c=db(); u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(uid,)).fetchone(); c.close(); return u


def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not current_user(): return redirect(url_for('login'))
        return f(*a, **kw)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **kw):
        u=current_user()
        if not u: return redirect(url_for('login'))
        if u['role']!='admin': abort(403)
        return f(*a, **kw)
    return w


def scope_clause(u):
    return ('', []) if u['role']=='admin' else (' AND truong=?', [u['school']])


def calc_dashboard(u, filters):
    c=db(); where=[]; params=[]
    if u['role']=='school': where.append('truong=?'); params.append(u['school'])
    for field, key in [('nam','year'),('khoa','cohort'),('truong','school'),('dot_thi','round'),('ket_qua','result')]:
        val=filters.get(key)
        if val and (u['role']=='admin' or field!='truong' or val==u['school']):
            where.append(f'{field}=?'); params.append(val)
    W=(' WHERE '+ ' AND '.join(where)) if where else ''
    total=c.execute(f'SELECT COUNT(*) n FROM exam_records{W}',params).fetchone()['n']
    unique=c.execute(f'SELECT COUNT(DISTINCT ma_sv) n FROM exam_records{W}',params).fetchone()['n']
    achieved=c.execute(f"SELECT COUNT(DISTINCT ma_sv) n FROM exam_records{W} AND ket_qua IN ('Bậc 3','Bậc 4','Bậc 5')" if W else "SELECT COUNT(DISTINCT ma_sv) n FROM exam_records WHERE ket_qua IN ('Bậc 3','Bậc 4','Bậc 5')",params).fetchone()['n']
    not_achieved=max(unique-achieved,0)
    repeat=c.execute(f'''SELECT COUNT(*) n FROM (SELECT ma_sv FROM exam_records{W} GROUP BY ma_sv HAVING COUNT(*)>=2 AND SUM(CASE WHEN ket_qua IN ('Bậc 3','Bậc 4','Bậc 5') THEN 1 ELSE 0 END)=0)''',params).fetchone()['n']
    def group(col):
        rows=c.execute(f'SELECT {col} label, COUNT(*) n FROM exam_records{W} GROUP BY {col} ORDER BY n DESC',params).fetchall()
        return [{'label':r['label'] or '(trống)','n':r['n']} for r in rows]
    by_year=group('nam'); by_school=group('truong'); by_cohort=group('khoa'); by_round=group('dot_thi'); by_result=group('ket_qua')
    for item in by_school:
        item['color'] = SCHOOL_COLORS.get(item['label'], '#64748b')
    # school comparison by unique students
    rows=c.execute(f'''SELECT truong label, COUNT(DISTINCT ma_sv) students,
        COUNT(DISTINCT CASE WHEN ket_qua IN ('Bậc 3','Bậc 4','Bậc 5') THEN ma_sv END) achieved
        FROM exam_records{W} GROUP BY truong ORDER BY students DESC''',params).fetchall()
    school_cmp=[]
    for r in rows:
        rate=(r['achieved']/r['students']*100) if r['students'] else 0
        school_cmp.append({'label':r['label'],'students':r['students'],'achieved':r['achieved'],'not':r['students']-r['achieved'],'rate':round(rate,2),'color':SCHOOL_COLORS.get(r['label'], '#64748b')})
    c.close()
    return dict(total=total,unique=unique,achieved=achieved,not_achieved=not_achieved,repeat=repeat,
                rate=round(achieved/unique*100,2) if unique else 0,by_year=by_year,by_school=by_school,
                by_cohort=by_cohort,by_round=by_round,by_result=by_result,school_cmp=school_cmp)


def filter_options(u):
    c=db(); extra=' WHERE truong=?' if u['role']=='school' else ''; p=[u['school']] if u['role']=='school' else []
    opts={}
    for col in ['nam','khoa','truong','dot_thi','ket_qua']:
        rows=c.execute(f'SELECT DISTINCT {col} v FROM exam_records{extra} ORDER BY {col}',p).fetchall()
        opts[col]=[r['v'] for r in rows if r['v'] not in (None,'')]
    c.close(); return opts

@app.context_processor
def inject():
    return {'user': current_user(), 'school_list': SCHOOLS, 'school_colors': SCHOOL_COLORS}

@app.route('/')
@login_required
def index():
    u=current_user(); f={k:request.args.get(k,'') for k in ['year','cohort','school','round','result']}
    if u['role']=='school': f['school']=u['school']
    return render_template('dashboard.html', d=calc_dashboard(u,f), opts=filter_options(u), filters=f)

@app.route('/students')
@login_required
def students():
    u=current_user()
    if u['role']=='viewer': abort(403)
    q=request.args.get('q','').strip(); status=request.args.get('status','all'); school=request.args.get('school','')
    where=[]; p=[]
    if u['role']=='school': where.append('truong=?'); p.append(u['school'])
    elif school: where.append('truong=?'); p.append(school)
    if q: where.append('(ma_sv LIKE ? OR ho_ten LIKE ?)'); p += [f'%{q}%',f'%{q}%']
    W=' WHERE '+ ' AND '.join(where) if where else ''
    c=db()
    rows=c.execute(f'''SELECT ma_sv, MAX(ho_ten) ho_ten, MAX(truong) truong, MAX(khoa) khoa,
      COUNT(*) attempts, MAX(dot_thi) latest_round,
      MAX(CASE WHEN ket_qua IN ('Bậc 3','Bậc 4','Bậc 5') THEN 1 ELSE 0 END) achieved
      FROM exam_records{W} GROUP BY ma_sv ORDER BY attempts DESC, ma_sv LIMIT 1000''',p).fetchall()
    out=[]
    for r in rows:
        if r['achieved']: st='Đã đạt'
        elif r['attempts']>=3: st='Rất cao'
        elif r['attempts']>=2: st='Cao'
        else: st='Theo dõi'
        if status!='all' and st!=status: continue
        out.append(dict(r, status=st))
    c.close(); return render_template('students.html',rows=out,q=q,status=status,school=school)

@app.route('/student/<ma_sv>')
@login_required
def student_detail(ma_sv):
    u=current_user()
    if u['role']=='viewer': abort(403)
    c=db(); rows=c.execute('SELECT * FROM exam_records WHERE ma_sv=? ORDER BY nam, dot_thi',(ma_sv,)).fetchall(); c.close()
    if not rows: abort(404)
    if u['role']=='school' and rows[0]['truong']!=u['school']: abort(403)
    return render_template('student.html',rows=rows, ma_sv=ma_sv)

@app.route('/admin')
@admin_required
def admin():
    c=db(); users=c.execute('SELECT id,username,role,school,active,must_change_password FROM users ORDER BY role DESC, username').fetchall(); n=c.execute('SELECT COUNT(*) n FROM exam_records').fetchone()['n']; c.close()
    return render_template('admin.html',users=users,n=n,default_password=PASS_DEFAULT)

@app.route('/admin/upload', methods=['POST'])
@admin_required
def upload():
    f=request.files.get('file')
    if not f or not f.filename.lower().endswith(('.xlsx','.xls')):
        flash('Vui lòng chọn file Excel (.xlsx/.xls).','error'); return redirect(url_for('admin'))
    try:
        n=import_excel(f)
        flash(f'Đã cập nhật {n:,} lượt thi vào hệ thống.','ok')
    except Exception as e:
        flash('Không thể nhập Excel: '+str(e),'error')
    return redirect(url_for('admin'))

@app.route('/admin/user', methods=['POST'])
@admin_required
def create_user():
    username=request.form.get('username','').strip(); role=request.form.get('role','school'); school=request.form.get('school','').strip()
    if not username or role not in ('school','viewer'):
        flash('Thông tin tài khoản không hợp lệ.','error'); return redirect(url_for('admin'))
    if role=='school' and school not in SCHOOLS:
        flash('Tài khoản trường phải gắn với một trường hợp lệ.','error'); return redirect(url_for('admin'))
    if role=='viewer': school=None
    c=db()
    try:
        c.execute('INSERT INTO users(username,password_hash,role,school) VALUES(?,?,?,?)',(username,generate_password_hash(PASS_DEFAULT),role,school)); c.commit(); flash('Đã tạo tài khoản. Mật khẩu ban đầu: '+PASS_DEFAULT,'ok')
    except sqlite3.IntegrityError: flash('Tên tài khoản đã tồn tại.','error')
    finally: c.close()
    return redirect(url_for('admin'))

@app.route('/admin/user/<int:uid>/toggle', methods=['POST'])
@admin_required
def toggle_user(uid):
    c=db(); c.execute('UPDATE users SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=? AND role IN ("school","viewer")',(uid,)); c.commit(); c.close(); return redirect(url_for('admin'))

@app.route('/change-password', methods=['GET','POST'])
@login_required
def change_password():
    if request.method=='POST':
        old=request.form.get('old',''); new=request.form.get('new','')
        u=current_user()
        if not check_password_hash(u['password_hash'],old) or len(new)<8: flash('Mật khẩu cũ không đúng hoặc mật khẩu mới quá ngắn.','error')
        else:
            c=db(); c.execute('UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?',(generate_password_hash(new),u['id'])); c.commit(); c.close(); flash('Đổi mật khẩu thành công.','ok'); return redirect(url_for('index'))
    return render_template('change_password.html')

@app.route('/login', methods=['GET','POST'])
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

@app.route('/export')
@admin_required
def export_csv():
    u=current_user(); c=db(); rows=c.execute('SELECT tt,sbd,ma_sv,ho_ten,ngay_sinh,noi_sinh,lop,khoa,ket_qua,truong,dot_thi,nam FROM exam_records ORDER BY truong,ma_sv,nam').fetchall(); c.close()
    output=io.StringIO(); w=csv.writer(output); w.writerow(['TT','SBD','Mã SV','Họ tên','Ngày sinh','Nơi sinh','Lớp','Khóa','Kết quả','Trường','Đợt thi','Năm']); w.writerows([tuple(r) for r in rows]); output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')),as_attachment=True,download_name='du_lieu_CDR.csv',mimetype='text/csv')

# Initialize database whenever the app is imported (required by Gunicorn/hosting).
init_db()

if __name__=='__main__':
    # Load supplied workbook only on first run if database is empty
    c=db(); n=c.execute('SELECT COUNT(*) n FROM exam_records').fetchone()['n']; c.close()
    src=os.path.join('/mnt/data','Du lieu thi CDR tao dashboard.xlsx')
    if n==0 and os.path.exists(src):
        try: import_excel(src)
        except Exception as e: print('Initial import failed:',e)
    app.run(host=os.environ.get('HOST', '0.0.0.0'), port=int(os.environ.get('PORT', 5000)), debug=False)
