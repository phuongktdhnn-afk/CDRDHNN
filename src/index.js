const SESSION_COOKIE = "cdr_session";
const SESSION_DAYS = 7;

function json(data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {"content-type": "application/json; charset=utf-8", ...extra}
  });
}

function corsHeaders(origin) {
  const allowed = origin || "*";
  return {
    "access-control-allow-origin": allowed,
    "access-control-allow-credentials": "true",
    "access-control-allow-headers": "content-type",
    "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS"
  };
}

function withCors(resp, origin) {
  const h = new Headers(resp.headers);
  for (const [k,v] of Object.entries(corsHeaders(origin))) h.set(k,v);
  return new Response(resp.body, {status: resp.status, headers:h});
}

function b64(bytes) {
  let s = "";
  const a = new Uint8Array(bytes);
  for (let i=0;i<a.length;i++) s += String.fromCharCode(a[i]);
  return btoa(s).replaceAll("+","-").replaceAll("/","_").replaceAll("=","");
}

function unb64(s) {
  s = s.replaceAll("-","+").replaceAll("_","/");
  while (s.length % 4) s += "=";
  const raw = atob(s);
  const a = new Uint8Array(raw.length);
  for (let i=0;i<raw.length;i++) a[i]=raw.charCodeAt(i);
  return a;
}

async function pbkdf2(password, saltBytes, iterations=120000) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]
  );
  return new Uint8Array(await crypto.subtle.deriveBits(
    {name:"PBKDF2", hash:"SHA-256", salt:saltBytes, iterations}, key, 256
  ));
}

async function makePasswordHash(password) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iterations = 120000;
  const digest = await pbkdf2(password, salt, iterations);
  return `pbkdf2$sha256$${iterations}$${b64(salt)}$${b64(digest)}`;
}

async function verifyPassword(password, encoded) {
  const p = String(encoded || "").split("$");
  if (p.length !== 5 || p[0] !== "pbkdf2" || p[1] !== "sha256") return false;
  const iterations = Number(p[2]);
  if (!Number.isFinite(iterations) || iterations < 10000) return false;
  const actual = await pbkdf2(password, unb64(p[3]), iterations);
  const expected = unb64(p[4]);
  if (actual.length !== expected.length) return false;
  let diff = 0;
  for (let i=0;i<actual.length;i++) diff |= actual[i] ^ expected[i];
  return diff === 0;
}

function parseCookies(req) {
  const out = {};
  const raw = req.headers.get("cookie") || "";
  raw.split(";").forEach(x => {
    const i=x.indexOf("=");
    if(i>0) out[x.slice(0,i).trim()] = decodeURIComponent(x.slice(i+1).trim());
  });
  return out;
}

async function currentUser(req, env) {
  const token = parseCookies(req)[SESSION_COOKIE];
  if (!token) return null;
  const row = await env.DB.prepare(`
    SELECT u.id,u.username,u.full_name,u.email,u.role_code,u.school_id,u.status
    FROM sessions s JOIN users u ON u.id=s.user_id
    WHERE s.token_hash=? AND s.expires_at>datetime('now') AND u.status='active'
  `).bind(await sha256(token)).first();
  return row || null;
}

async function sha256(value) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return b64(buf);
}

async function createSession(userId, env) {
  const token = b64(crypto.getRandomValues(new Uint8Array(32))) + "." +
    b64(crypto.getRandomValues(new Uint8Array(16)));
  const hash = await sha256(token);
  await env.DB.prepare(
    `INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,datetime('now','+7 days'))`
  ).bind(hash,userId).run();
  return token;
}

function sessionCookie(token) {
  return `${SESSION_COOKIE}=${encodeURIComponent(token)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${SESSION_DAYS*86400}`;
}
function expiredCookie() {
  return `${SESSION_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`;
}

async function requireUser(req, env) {
  const user = await currentUser(req, env);
  return user;
}

async function api(req, env, url) {
  const method = req.method;
  if (method === "OPTIONS") return new Response(null, {status:204});

  if (url.pathname === "/api/health") {
    try {
      const r = await env.DB.prepare("SELECT 1 AS ok").first();
      const counts = await env.DB.batch([
        env.DB.prepare("SELECT COUNT(*) AS total FROM users"),
        env.DB.prepare("SELECT COUNT(*) AS total FROM students"),
        env.DB.prepare("SELECT COUNT(*) AS total FROM care_cases")
      ]);
      return json({ok:true, db:r?.ok===1, counts:{
        users: counts[0]?.results?.[0]?.total ?? 0,
        students: counts[1]?.results?.[0]?.total ?? 0,
        care_cases: counts[2]?.results?.[0]?.total ?? 0
      }});
    } catch(e) {
      return json({ok:false,error:String(e)},500);
    }
  }

  if (url.pathname === "/api/setup" && method === "POST") {
    const setupKey = req.headers.get("x-setup-key") || "";
    if (!env.SETUP_KEY || setupKey !== env.SETUP_KEY) return json({ok:false,error:"SETUP_KEY không đúng"},403);
    const body = await req.json();
    const username = String(body.username||"").trim();
    const password = String(body.password||"");
    if (!username || password.length < 10) return json({ok:false,error:"Tài khoản và mật khẩu hợp lệ (mật khẩu tối thiểu 10 ký tự) là bắt buộc"},400);
    const hash = await makePasswordHash(password);
    await env.DB.prepare(`
      INSERT INTO users(username,email,full_name,role_code,status,password_hash)
      VALUES(?,?,?,?,?,?)
      ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash,status='active'
    `).bind(
      username,
      String(body.email||""),
      String(body.full_name||username),
      String(body.role_code||"ADMIN"),
      "active",
      hash
    ).run();
    return json({ok:true,message:"Đã tạo/cập nhật tài khoản"});
  }

  if (url.pathname === "/api/login" && method === "POST") {
    const body = await req.json();
    const username = String(body.username||"").trim();
    const password = String(body.password||"");
    const user = await env.DB.prepare(
      `SELECT * FROM users WHERE username=? AND status='active'`
    ).bind(username).first();
    if (!user || !(await verifyPassword(password,user.password_hash))) {
      return json({ok:false,error:"Tài khoản hoặc mật khẩu không đúng"},401);
    }
    await env.DB.prepare(`DELETE FROM sessions WHERE expires_at<=datetime('now')`).run();
    const token = await createSession(user.id, env);
    await env.DB.prepare(`UPDATE users SET last_login_at=datetime('now') WHERE id=?`).bind(user.id).run();
    return json({ok:true,user:{
      id:user.id,username:user.username,full_name:user.full_name,
      email:user.email,role_code:user.role_code,school_id:user.school_id
    }},200,{"set-cookie":sessionCookie(token)});
  }

  if (url.pathname === "/api/logout" && method === "POST") {
    const token = parseCookies(req)[SESSION_COOKIE];
    if(token) await env.DB.prepare(`DELETE FROM sessions WHERE token_hash=?`).bind(await sha256(token)).run();
    return json({ok:true},200,{"set-cookie":expiredCookie()});
  }

  const user = await requireUser(req, env);
  if (!user) return json({ok:false,error:"Chưa đăng nhập"},401);

  if (url.pathname === "/api/me") return json({ok:true,user});

  if (url.pathname === "/api/dashboard") {
    const total = await env.DB.prepare(`SELECT COUNT(*) total FROM students`).first();
    const attained = await env.DB.prepare(`SELECT COUNT(*) total FROM students WHERE cdr_status='Đã đạt'`).first();
    const risk = await env.DB.prepare(`
      SELECT risk_level, COUNT(*) total FROM care_cases
      GROUP BY risk_level ORDER BY total DESC
    `).all();
    const schools = await env.DB.prepare(`
      SELECT COALESCE(school_name,'Chưa xác định') school_name,
             COUNT(*) total,
             SUM(CASE WHEN cdr_status='Đã đạt' THEN 1 ELSE 0 END) attained
      FROM students GROUP BY school_name ORDER BY total DESC
    `).all();
    return json({ok:true,
      kpi:{students:total?.total||0,attained:attained?.total||0},
      risks:risk.results||[],schools:schools.results||[]
    });
  }

  if (url.pathname === "/api/students") {
    const q = (url.searchParams.get("q")||"").trim();
    const school = (url.searchParams.get("school")||"").trim();
    let sql=`SELECT id,student_code,full_name,school_name,cohort,class_name,cdr_status,latest_result,attempts,risk_level
             FROM students WHERE 1=1`;
    const args=[];
    if(q){sql+=` AND (student_code LIKE ? OR full_name LIKE ?)`;args.push(`%${q}%`,`%${q}%`)}
    if(school){sql+=` AND school_name=?`;args.push(school)}
    sql+=` ORDER BY school_name,student_code LIMIT 2000`;
    const r=await env.DB.prepare(sql).bind(...args).all();
    return json({ok:true,rows:r.results||[]});
  }

  if (url.pathname === "/api/care-cases") {
    const r = await env.DB.prepare(`
      SELECT id,student_code,full_name,school_name,cohort,risk_level,reason,status,updated_at
      FROM care_cases ORDER BY
      CASE risk_level WHEN 'Rất cao' THEN 1 WHEN 'Cao' THEN 2 WHEN 'Trung bình' THEN 3 ELSE 4 END,
      updated_at DESC LIMIT 2000
    `).all();
    return json({ok:true,rows:r.results||[]});
  }

  return json({ok:false,error:"API không tồn tại"},404);
}

async function asset(req, env, path) {
  const key = path === "/" ? "index.html" : path.replace(/^\/+/,"");
  const obj = await env.ASSETS.get(key);
  if (!obj) return new Response("Not found",{status:404});
  const headers = new Headers();
  obj.writeHttpMetadata(headers);
  headers.set("etag",obj.httpEtag);
  return new Response(obj.body,{headers});
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    try {
      if (url.pathname.startsWith("/api/")) return api(req,env,url);
      return asset(req,env,url.pathname);
    } catch(e) {
      return json({ok:false,error:String(e)},500);
    }
  }
};
