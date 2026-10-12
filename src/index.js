const ROLE_LABELS={ADMIN:'Quản trị hệ thống',BGH:'BGH/ĐHĐN',DHNN_QTDBCL:'ĐHNN/KT&ĐBCLGD',TRUONG_THANH_VIEN:'Trường thành viên',KHOA_CVHT:'Khoa/CVHT'};
const ROLE_PERMS={ADMIN:['view_all','manage_users','manage_data','manage_care'],BGH:['view_all'],DHNN_QTDBCL:['view_all','manage_data','manage_care'],TRUONG_THANH_VIEN:['view_school','manage_care_school'],KHOA_CVHT:['view_school','manage_care_school']};
const ROLE_MODULES={ADMIN:['overview','studentsPanel','carePanel','schoolsPanel','usersPanel'],BGH:['overview','schoolsPanel'],DHNN_QTDBCL:['overview','studentsPanel','carePanel','schoolsPanel'],TRUONG_THANH_VIEN:['overview','studentsPanel','carePanel','schoolsPanel'],KHOA_CVHT:['overview','studentsPanel','carePanel']};
export default {async fetch(request,env){const url=new URL(request.url);try{
 if(request.method==='OPTIONS')return new Response('',{headers:cors()});
 if(url.pathname==='/api/health')return json({ok:true,service:'cdr-ta-ufl-dashboard'});
 if(url.pathname==='/api/auth/login'&&request.method==='POST')return login(request,env);
 if(url.pathname==='/api/auth/logout'&&request.method==='POST')return logout(request,env);
 if(url.pathname==='/api/auth/me')return me(request,env);
 if(url.pathname.startsWith('/api/')){const user=await auth(request,env);if(!user)return json({ok:false,error:'UNAUTHORIZED'},401);
  if(url.pathname==='/api/stats'){if(!can(user,'view_all')&&!can(user,'view_school'))return json({ok:false,error:'FORBIDDEN'},403);return stats(env,user)}
  if(url.pathname==='/api/students/import'&&request.method==='POST')return importStudents(request,env,user);
  if(url.pathname==='/api/students'){if(!['ADMIN','BGH','DHNN_QTDBCL','TRUONG_THANH_VIEN','KHOA_CVHT'].includes(user.role))return json({ok:false,error:'FORBIDDEN'},403);return students(env,user,url)}
  if(url.pathname==='/api/care'){if(!['ADMIN','DHNN_QTDBCL','TRUONG_THANH_VIEN','KHOA_CVHT'].includes(user.role))return json({ok:false,error:'FORBIDDEN'},403);return care(env,user,url)}
  if(url.pathname==='/api/schools'){if(!['ADMIN','BGH','DHNN_QTDBCL','TRUONG_THANH_VIEN'].includes(user.role))return json({ok:false,error:'FORBIDDEN'},403);return schools(env,user)}
  if(url.pathname==='/api/users'&&request.method==='GET')return users(env,user);
  if(url.pathname==='/api/users'&&request.method==='POST')return createUser(request,env,user);
  return json({ok:false,error:'NOT_FOUND'},404);
 }
 return env.ASSETS.fetch(request);
 }catch(e){return json({ok:false,error:e?.message||'Internal error'},500)}}};
function cors(){return {'access-control-allow-origin':'*','access-control-allow-methods':'GET,POST,OPTIONS','access-control-allow-headers':'Content-Type,Authorization'}}
function json(d,status=200,extra={}){return new Response(JSON.stringify(d),{status,headers:{'content-type':'application/json; charset=UTF-8',...cors(),...extra}})}
async function sha(s){const b=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s));return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('')}
async function token(){const b=new Uint8Array(32);crypto.getRandomValues(b);return [...b].map(x=>x.toString(16).padStart(2,'0')).join('')}
function getCookie(req,n){const c=req.headers.get('Cookie')||'';const m=c.match(new RegExp('(?:^|; )'+n+'=([^;]+)'));return m?decodeURIComponent(m[1]):null}
async function auth(req,env){const h=req.headers.get('Authorization')||'';const t=h.startsWith('Bearer ')?h.slice(7):getCookie(req,'cdr_session');if(!t)return null;const th=await sha(t);return await env.DB.prepare("SELECT u.id,u.username,u.full_name,u.role,u.school_id,u.must_change_password,u.active FROM dashboard_sessions s JOIN dashboard_users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>datetime('now') AND u.active=1").bind(th).first()||null}
async function login(req,env){let b;try{b=await req.json()}catch{return json({ok:false,error:'Dữ liệu đăng nhập không hợp lệ'},400)}const username=String(b.username||'').trim(),password=String(b.password||'');if(!username||!password)return json({ok:false,error:'Vui lòng nhập tài khoản và mật khẩu'},400);const u=await env.DB.prepare('SELECT * FROM dashboard_users WHERE username=? AND active=1').bind(username).first();if(!u||u.password_hash!==(await sha(password)))return json({ok:false,error:'Tài khoản hoặc mật khẩu không đúng'},401);const raw=await token(),th=await sha(raw);await env.DB.prepare("INSERT INTO dashboard_sessions(token_hash,user_id,expires_at) VALUES(?,?,datetime('now','+12 hours'))").bind(th,u.id).run();return json({ok:true,user:{id:u.id,username:u.username,full_name:u.full_name,role:u.role,role_label:ROLE_LABELS[u.role],school_id:u.school_id,must_change_password:!!u.must_change_password,permissions:ROLE_PERMS[u.role]||[]}},200,{'set-cookie':`cdr_session=${encodeURIComponent(raw)}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=43200`})}
async function logout(req,env){const t=getCookie(req,'cdr_session');if(t)await env.DB.prepare('DELETE FROM dashboard_sessions WHERE token_hash=?').bind(await sha(t)).run();return json({ok:true},200,{'set-cookie':'cdr_session=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0'})}
async function me(req,env){const u=await auth(req,env);return json({ok:!!u,user:u?{...u,role_label:ROLE_LABELS[u.role],permissions:ROLE_PERMS[u.role]||[],modules:ROLE_MODULES[u.role]||[]}:null},u?200:401)}
function can(u,p){return (ROLE_PERMS[u.role]||[]).includes(p)}
function schoolFilter(u,alias='s'){return can(u,'view_all')?{sql:'1=1',bind:[]}:{sql:`${alias}.school_id=?`,bind:[u.school_id]}}
async function stats(env,u){const f=schoolFilter(u);const st=await env.DB.prepare(`SELECT COUNT(*) total FROM students s WHERE ${f.sql}`).bind(...f.bind).first();const schools=await env.DB.prepare(can(u,'view_all')?'SELECT id,code,name,data_status FROM schools ORDER BY id':'SELECT id,code,name,data_status FROM schools WHERE id=?').bind(...(can(u,'view_all')?[]:[u.school_id])).all();const c=await env.DB.prepare(`SELECT c.care_level,COUNT(*) total FROM care_cases c JOIN students s ON s.id=c.student_id WHERE ${can(u,'view_all')?'1=1':'s.school_id=?'} GROUP BY c.care_level`).bind(...(can(u,'view_all')?[]:[u.school_id])).all();return json({totalStudents:st?.total||0,care:c.results||[],schools:schools.results||[],user:{id:u.id,username:u.username,full_name:u.full_name,role:u.role,school_id:u.school_id}})}
async function students(env,u,url){const limit=Math.max(1,Math.min(Number(url.searchParams.get('limit')||500),500));const f=schoolFilter(u);const r=await env.DB.prepare(`SELECT s.id,s.student_code,s.full_name,s.major,s.cohort,s.class_name,sc.code school_code,sc.name school_name FROM students s LEFT JOIN schools sc ON sc.id=s.school_id WHERE ${f.sql} ORDER BY s.id LIMIT ?`).bind(...f.bind,limit).all();return json({results:r.results||[]})}
async function care(env,u,url){const f=schoolFilter(u,'s');const r=await env.DB.prepare(`SELECT c.id,c.student_id,c.care_level,c.reason,c.status,s.student_code,s.full_name,sc.code school_code,sc.name school_name FROM care_cases c JOIN students s ON s.id=c.student_id LEFT JOIN schools sc ON sc.id=s.school_id WHERE ${f.sql} ORDER BY c.id DESC LIMIT 500`).bind(...f.bind).all();return json({results:r.results||[]})}
async function schools(env,u){const r=await env.DB.prepare(can(u,'view_all')?'SELECT id,code,name,status,data_status FROM schools ORDER BY id':'SELECT id,code,name,status,data_status FROM schools WHERE id=?').bind(...(can(u,'view_all')?[]:[u.school_id])).all();return json({results:r.results||[]})}
async function users(env,u){if(!can(u,'manage_users'))return json({ok:false,error:'FORBIDDEN'},403);const r=await env.DB.prepare('SELECT id,username,full_name,role,school_id,active,must_change_password,created_at FROM dashboard_users ORDER BY id').all();return json({results:r.results||[]})}
async function createUser(req,env,u){if(!can(u,'manage_users'))return json({ok:false,error:'FORBIDDEN'},403);const b=await req.json();const username=String(b.username||'').trim(),password=String(b.password||'');if(!username||!password||!b.role)return json({ok:false,error:'Thiếu username/password/role'},400);if(!ROLE_LABELS[b.role])return json({ok:false,error:'Role không hợp lệ'},400);if(['TRUONG_THANH_VIEN','KHOA_CVHT'].includes(b.role)&&!b.school_id)return json({ok:false,error:'Vai trò này cần chọn trường'},400);try{await env.DB.prepare('INSERT INTO dashboard_users(username,full_name,role,school_id,password_hash,must_change_password,active) VALUES(?,?,?,?,?,?,1)').bind(username,String(b.full_name||''),b.role,b.school_id||null,await sha(password),1).run();await env.DB.prepare('INSERT INTO dashboard_audit_logs(user_id,action,target,detail) VALUES(?,?,?,?)').bind(u.id,'CREATE_USER',username,`role=${b.role}`).run();return json({ok:true})}catch(e){return json({ok:false,error:e.message},400)}}


// ADMIN-only CSV/JSON import. Existing records are updated by student_code.
async function importStudents(request,env,user){
 if(user.role!=='ADMIN')return json({ok:false,error:'FORBIDDEN: Chỉ ADMIN được nhập/cập nhật dữ liệu.'},403);
 let b;try{b=await request.json()}catch{return json({ok:false,error:'Dữ liệu gửi lên không hợp lệ'},400)}
 if(!Array.isArray(b.rows)||b.rows.length>10000)return json({ok:false,error:'Danh sách phải có tối đa 10.000 dòng'},400);
 let imported=0,skipped=0;
 for(const row of b.rows){
  const code=String(row.student_code||row.ma_sv||'').trim();
  const name=String(row.full_name||row.ho_ten||'').trim();
  const schoolCode=String(row.school_code||row.ma_truong||'').trim().toUpperCase();
  if(!code||!schoolCode){skipped++;continue;}
  const school=await env.DB.prepare('SELECT id FROM schools WHERE code=?').bind(schoolCode).first();
  if(!school){skipped++;continue;}
  await env.DB.prepare(`INSERT INTO students(student_code,full_name,school_id,major,cohort,class_name,updated_at)
   VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
   ON CONFLICT(student_code) DO UPDATE SET full_name=excluded.full_name,school_id=excluded.school_id,major=excluded.major,cohort=excluded.cohort,class_name=excluded.class_name,updated_at=CURRENT_TIMESTAMP`)
   .bind(code,name,school.id,String(row.major||row.nganh||''),String(row.cohort||row.khoa||''),String(row.class_name||row.lop||'')).run();
  await env.DB.prepare("UPDATE schools SET data_status='DA_CO_DU_LIEU',updated_at=CURRENT_TIMESTAMP WHERE id=?").bind(school.id).run();
  imported++;
 }
 await env.DB.prepare('INSERT INTO dashboard_audit_logs(user_id,action,target,detail) VALUES(?,?,?,?)').bind(user.id,'IMPORT_STUDENTS','students',`imported=${imported}; skipped=${skipped}`).run();
 return json({ok:true,imported,skipped});
}
