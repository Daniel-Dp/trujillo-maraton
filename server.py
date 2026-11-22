"""Backend Maratón Internacional de Trujillo 2027 (Flask) – listo para Render."""
import csv, hmac, hashlib, io, json, os, re, secrets, smtplib, threading, time, base64
from html import escape as html_escape
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS

BASE = Path(__file__).parent
app = Flask(__name__, static_folder=None)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

PRICES = {"10K": 60, "21K": 80, "42K": 100}
SECRET = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")  # obligatorio para login
TOKEN_TTL = 8 * 3600

# ---------------- Persistencia: Firestore/Storage o fallback local ----------------
_db = _bucket = None
try:
    import firebase_admin
    from firebase_admin import credentials, firestore, storage
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    cred_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_json or cred_file:
        cred = credentials.Certificate(json.loads(cred_json) if cred_json else cred_file)
        firebase_admin.initialize_app(cred, {"storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET")})
        _db = firestore.client()
        _bucket = storage.bucket()
except Exception as e:  # pragma: no cover
    print("Firebase no disponible, usando almacén local:", e)

LOCAL_DB = BASE / "local_db.json"
UPLOADS = BASE / "uploads"
_lock = threading.Lock()


def _local_read():
    return json.loads(LOCAL_DB.read_text("utf-8")) if LOCAL_DB.exists() else {}


def _local_write(d):
    LOCAL_DB.write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")


def db_get(code):
    if _db:
        s = _db.collection("registrations").document(code).get()
        return s.to_dict() if s.exists else None
    return _local_read().get(code)


def db_set(code, data):
    if _db:
        _db.collection("registrations").document(code).set(data, merge=True)
        return
    with _lock:
        d = _local_read(); d.setdefault(code, {}).update(data); _local_write(d)


def db_all():
    if _db:
        return [s.to_dict() for s in _db.collection("registrations").stream()]
    return list(_local_read().values())


def db_find_dni(dni):
    return any(r.get("dni") == dni for r in db_all())


# ---------------- Utilidades ----------------
def new_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "TRU27-" + "".join(secrets.choice(alphabet) for _ in range(6))


def sign(payload: str) -> str:
    return hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(user):
    exp = str(int(time.time()) + TOKEN_TTL)
    p = base64.urlsafe_b64encode(f"{user}|{exp}".encode()).decode()
    return f"{p}.{sign(p)}"


def check_token(tok):
    try:
        p, s = tok.split(".")
        if not hmac.compare_digest(s, sign(p)):
            return False
        _, exp = base64.urlsafe_b64decode(p).decode().split("|")
        return int(exp) > time.time()
    except Exception:
        return False


def admin_required(fn):
    from functools import wraps

    @wraps(fn)
    def w(*a, **k):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not check_token(auth[7:]):
            return jsonify(error="No autorizado"), 401
        return fn(*a, **k)
    return w


def send_email(to, subject, body, html=None):
    host = os.environ.get("SMTP_HOST")
    if not host:
        print(f"[email no enviado – SMTP no configurado] {to}: {subject}")
        return False
    try:
        msg = EmailMessage()
        msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER", "")
        msg["To"], msg["Subject"] = to, subject
        msg.set_content(body)
        if html:
            msg.add_alternative(html, subtype="html")
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT") or 587), timeout=15) as s:
            s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS") or os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
        return True
    except Exception as e:
        print("Error enviando correo:", e)
        return False


def confirmation_html(rec):
    e = html_escape
    rows = [("Código de inscripción", rec["code"]),
            ("Corredor", f"{rec['nombres']} {rec['apellidos']}"),
            ("Distancia", rec["distancia"]), ("Cupos", rec["cupos"]),
            ("Monto total", f"S/ {rec['total']:.2f}"), ("Estado", "Pendiente de validación"),
            ("Fecha del evento", "Domingo 26 de septiembre 2027 - Plaza de Armas de Trujillo")]
    trs = "".join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid #2a2a2a;color:#9a9a9a;font-size:12px;letter-spacing:1px;text-transform:uppercase">{e(k)}</td>'
        f'<td style="padding:10px 0;border-bottom:1px solid #2a2a2a;text-align:right;color:#fff;font-weight:700">{e(str(v))}</td></tr>'
        for k, v in rows)
    return f"""<!DOCTYPE html><html><body style="margin:0;background:#0A0A0A;font-family:Arial,Helvetica,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0A0A0A"><tr><td align="center" style="padding:24px 12px">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#161616">
<tr><td style="padding:24px;border-bottom:3px solid #FF5500;color:#fff;font-size:22px;font-weight:800;letter-spacing:2px">DATARIX <span style="color:#FF5500">|</span> MARATÓN TRUJILLO</td></tr>
<tr><td style="padding:32px 24px 8px;color:#fff;font-size:30px;font-weight:800;text-transform:uppercase;line-height:1.1">¡Hola, {e(rec['nombres'])}!<br><span style="color:#FF5500">Recibimos tu inscripción</span></td></tr>
<tr><td style="padding:8px 24px 16px;color:#cfcfcf;font-size:14px;line-height:1.5">Gracias por sumarte a la Maratón Internacional de Trujillo 2027. Estos son los datos de tu inscripción:</td></tr>
<tr><td style="padding:0 24px"><table width="100%" cellpadding="0" cellspacing="0">{trs}</table></td></tr>
<tr><td style="padding:24px;text-align:center"><div style="display:inline-block;border:2px solid #FF5500;color:#FF5500;font-size:26px;font-weight:800;letter-spacing:3px;padding:12px 22px">{e(rec['code'])}</div>
<div style="color:#9a9a9a;font-size:12px;margin-top:8px">Presenta este código y tu DNI en el retiro de kits</div></td></tr>
<tr><td style="padding:16px 24px;color:#777;font-size:11px;text-align:center">© 2027 DataRix · Maratón Internacional de Trujillo</td></tr>
</table></td></tr></table></body></html>"""


def confirmation_text(rec):
    return (f"Hola {rec['nombres']} {rec['apellidos']}, recibimos tu inscripción.\nCódigo: {rec['code']}\n"
            f"Distancia: {rec['distancia']}\nCupos: {rec['cupos']}\nMonto total: S/ {rec['total']:.2f}\n"
            "Estado: Pendiente de validación\n\n"
            "Evento: Domingo 26 de septiembre 2027 - Plaza de Armas de Trujillo.")


def send_confirmation_async(rec):
    """Envía el correo en un hilo; nunca lanza excepciones ni retrasa la respuesta."""
    def job():
        try:
            send_email(rec["email"], f"Inscripción recibida {rec['code']} – Maratón Trujillo 2027",
                       confirmation_text(rec), confirmation_html(rec))
        except Exception as ex:
            print("Email:", ex)
    threading.Thread(target=job, daemon=True).start()


def validate(d):
    req = ["nombres", "apellidos", "dni", "edad", "genero", "ciudad", "email",
           "telefono", "talla", "sangre", "emergencia", "distancia", "cupos"]
    for f in req:
        if not str(d.get(f, "")).strip():
            return f"Falta el campo {f}"
    if not re.fullmatch(r"\d{8}", str(d["dni"])): return "DNI inválido"
    if d["distancia"] not in PRICES: return "Distancia inválida"
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", d["email"]): return "Correo inválido"
    if not re.fullmatch(r"\+?\d{9,12}", re.sub(r"[\s-]", "", d["telefono"])): return "Teléfono inválido"
    if d["talla"] not in ("S", "M", "L", "XL"): return "Talla inválida"
    try:
        if not 14 <= int(d["edad"]) <= 90: return "Edad fuera de rango"
        if not 1 <= int(d["cupos"]) <= 5: return "Cupos inválidos (1-5)"
    except ValueError:
        return "Edad/cupos inválidos"
    return None


# ---------------- API pública ----------------
@app.post("/api/registrations")
def create_registration():
    d = request.get_json(silent=True) or {}
    if (e := validate(d)):
        return jsonify(error=e), 400
    if db_find_dni(d["dni"]):
        return jsonify(error="Ya existe una inscripción con este DNI"), 409
    code = new_code()
    cupos = int(d["cupos"])
    rec = {k: str(d[k]).strip() for k in ["nombres", "apellidos", "dni", "genero", "ciudad", "email",
                                            "telefono", "talla", "sangre", "emergencia", "distancia"]}
    rec.update(code=code, edad=int(d["edad"]), cupos=cupos,
               total=PRICES[d["distancia"]] * cupos,  # el precio SIEMPRE se calcula en servidor
               metodo_pago="niubiz" if d.get("metodo_pago") == "niubiz" else "yape",
               status="pending", voucher_url=None,
               created_at=datetime.now(timezone.utc).isoformat())
    db_set(code, rec)
    send_confirmation_async(dict(rec))
    return jsonify(code=code, total=rec["total"]), 201


@app.post("/api/registrations/<code>/voucher")
def upload_voucher(code):
    rec = db_get(code)
    if not rec: return jsonify(error="Inscripción no encontrada"), 404
    f = request.files.get("voucher")
    if not f: return jsonify(error="Falta archivo"), 400
    ext = Path(f.filename or "").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".pdf", ".webp"):
        return jsonify(error="Formato no permitido"), 400
    name = f"vouchers/{code}{ext}"
    if _bucket:
        blob = _bucket.blob(name)
        blob.upload_from_file(f.stream, content_type=f.mimetype)
        url = blob.generate_signed_url(expiration=3600 * 24 * 365 * 5)
    else:
        UPLOADS.mkdir(exist_ok=True)
        (UPLOADS / f"{code}{ext}").write_bytes(f.read())
        url = f"/uploads/{code}{ext}"
    db_set(code, {"voucher_url": url})
    return jsonify(ok=True)


@app.post("/api/niubiz/session")
def niubiz_session():
    """Stub: aquí se solicita el accessToken y sessionKey a Niubiz (apisandbox.vnforappstest.com)."""
    if not all(os.environ.get(k) for k in ("NIUBIZ_MERCHANT_ID", "NIUBIZ_USER", "NIUBIZ_PASSWORD")):
        return jsonify(error="Pasarela Niubiz aún no configurada. Tu inscripción quedó pendiente; usá Yape/Plin."), 503
    return jsonify(error="Integración Niubiz pendiente de implementar con credenciales reales"), 501


# ---------------- API admin ----------------
@app.post("/api/admin/login")
def admin_login():
    d = request.get_json(silent=True) or {}
    if not ADMIN_PASSWORD:
        return jsonify(error="ADMIN_PASSWORD no configurada en el servidor"), 503
    ok = hmac.compare_digest(str(d.get("username", "")), ADMIN_USER) & \
        hmac.compare_digest(str(d.get("password", "")), ADMIN_PASSWORD)
    if not ok:
        time.sleep(1)
        return jsonify(error="Credenciales inválidas"), 401
    return jsonify(token=make_token(ADMIN_USER))


@app.get("/api/admin/registrations")
@admin_required
def admin_list():
    rows = sorted(db_all(), key=lambda r: r.get("created_at", ""), reverse=True)
    ok = [r for r in rows if r["status"] == "approved"]
    return jsonify(registrations=rows, kpis=dict(
        total=len(rows), approved=len(ok), pending=len(rows) - len(ok),
        revenue=sum(r["total"] for r in ok)))


@app.post("/api/admin/registrations/<code>/approve")
@admin_required
def admin_approve(code):
    rec = db_get(code)
    if not rec: return jsonify(error="No encontrada"), 404
    db_set(code, {"status": "approved", "approved_at": datetime.now(timezone.utc).isoformat()})
    sent = send_email(rec["email"], f"Pago confirmado – {code}",
                      f"Hola {rec['nombres']}, tu pago fue aprobado. Código: {code}. "
                      f"Distancia: {rec['distancia']}. Retiro de kits con DNI y este código. ¡Nos vemos el 26/09/2027!")
    return jsonify(ok=True, email_sent=sent)


@app.get("/api/admin/export.csv")
@admin_required
def admin_export():
    cols = ["code", "nombres", "apellidos", "dni", "edad", "genero", "ciudad", "email", "telefono",
            "talla", "sangre", "emergencia", "distancia", "cupos", "total", "metodo_pago",
            "status", "voucher_url", "created_at"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(cols)
    for r in db_all():
        # evita inyección de fórmulas en Excel
        w.writerow([("'" + str(v)) if str(v)[:1] in "=+-@" and c not in ("telefono", "total") else v
                    for c in cols for v in [r.get(c, "")]])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=corredores.csv"})


# ---------------- Estáticos ----------------
@app.get("/uploads/<path:n>")
@admin_required
def uploads(n):
    return send_from_directory(UPLOADS, n)


@app.get("/")
def home(): return send_from_directory(BASE, "index.html")


@app.get("/admin.html")
def admin_page(): return send_from_directory(BASE, "admin.html")


@app.get("/<path:p>")
def static_files(p):
    if p.split("/")[0] not in ("assets", "css", "js"):
        return "Not found", 404
    return send_from_directory(BASE, p)


@app.get("/healthz")
def health(): return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
