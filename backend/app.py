import os
import math
import sqlite3
import uuid
import bcrypt
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_file, jsonify
)

# ── App ────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = 'studentsync_2026_secret_key_xyz'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024   # 500 MB

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DB_FILE       = os.path.join(BASE_DIR, 'database.db')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── Jinja2 filters ─────────────────────────────────────────────────────────────
@app.template_filter('fsize')
def fsize_filter(b):
    try:
        b = int(b)
        if b == 0: return '0 B'
        u = ['B','KB','MB','GB','TB']
        i = min(int(math.floor(math.log(max(b,1), 1024))), len(u)-1)
        return f"{b/(1024**i):.1f} {u[i]}"
    except Exception:
        return '? B'

@app.template_filter('fdate')
def fdate_filter(s):
    try: return str(s)[:10]
    except Exception: return str(s)


# ── Database ───────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = get_db()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS folders (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name    TEXT NOT NULL,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS files (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            folder_id     INTEGER,
            stored_name   TEXT NOT NULL,
            original_name TEXT NOT NULL,
            size          INTEGER NOT NULL DEFAULT 0,
            uploaded      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    c.commit(); c.close()

init_db()


# ── Auth guard ─────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if 'user_id' not in session:
            return redirect(url_for('auth_page'))
        return f(*a, **kw)
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
#  AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def root():
    return redirect(url_for('dashboard') if 'user_id' in session else url_for('auth_page'))

@app.route('/auth')
def auth_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('auth.html')

@app.route('/auth/login', methods=['POST'])
def do_login():
    username = (request.form.get('username') or '').strip()
    password =  request.form.get('password') or ''

    if not username or not password:
        return render_template('auth.html',
            login_error='Please fill in all fields.', show='login')

    c    = get_db()
    user = c.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    c.close()

    if not user or not bcrypt.checkpw(password.encode(), bytes(user['password'])):
        return render_template('auth.html',
            login_error='Incorrect username or password.', show='login')

    session.clear()
    session['user_id']  = user['id']
    session['username'] = user['username']
    return redirect(url_for('dashboard'))

@app.route('/auth/signup', methods=['POST'])
def do_signup():
    username = (request.form.get('username') or '').strip()
    password =  request.form.get('password') or ''

    if not username or not password:
        return render_template('auth.html',
            signup_error='Please fill in all fields.', show='signup')
    if len(password) < 6:
        return render_template('auth.html',
            signup_error='Password must be at least 6 characters.', show='signup')

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    c = get_db()
    try:
        cur = c.cursor()
        cur.execute('INSERT INTO users (username, password) VALUES (?,?)', (username, hashed))
        c.commit()
        uid = cur.lastrowid
    except sqlite3.IntegrityError:
        c.close()
        return render_template('auth.html',
            signup_error='Username already taken — choose another.', show='signup')
    c.close()

    session.clear()
    session['user_id']  = uid
    session['username'] = username
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth_page'))


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD (server-rendered)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/dashboard')
@login_required
def dashboard():
    uid       = session['user_id']
    folder_id = request.args.get('folder')   # None | 'root' | '<int>'

    c       = get_db()
    folders = c.execute(
        'SELECT * FROM folders WHERE user_id=? ORDER BY name COLLATE NOCASE', (uid,)
    ).fetchall()

    if folder_id == 'root':
        files = c.execute(
            'SELECT * FROM files WHERE user_id=? AND folder_id IS NULL ORDER BY uploaded DESC',
            (uid,)).fetchall()
        label = 'Uncategorised'
    elif folder_id:
        files = c.execute(
            'SELECT * FROM files WHERE user_id=? AND folder_id=? ORDER BY uploaded DESC',
            (uid, folder_id)).fetchall()
        m     = next((f for f in folders if str(f['id']) == folder_id), None)
        label = m['name'] if m else 'Folder'
    else:
        files = c.execute(
            'SELECT * FROM files WHERE user_id=? ORDER BY uploaded DESC',
            (uid,)).fetchall()
        label = 'All Files'

    c.close()
    return render_template('dashboard.html',
        folders=folders,
        files=files,
        active_folder=folder_id,
        folder_label=label,
        username=session['username'])


# ══════════════════════════════════════════════════════════════════════════════
#  FOLDER API  (all POST — maximally browser-compatible)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/folder/create', methods=['POST'])
@login_required
def api_create_folder():
    uid  = session['user_id']
    name = (request.form.get('name') or '').strip()

    if not name:
        return jsonify(error='Folder name cannot be empty.'), 400

    c = get_db()
    if c.execute('SELECT id FROM folders WHERE user_id=? AND name=?', (uid, name)).fetchone():
        c.close()
        return jsonify(error='A folder with that name already exists.'), 409

    cur = c.cursor()
    cur.execute('INSERT INTO folders (user_id, name) VALUES (?,?)', (uid, name))
    c.commit()
    fid = cur.lastrowid
    c.close()
    return jsonify(ok=True, id=fid, name=name), 201

@app.route('/api/folder/<int:fid>/delete', methods=['POST'])
@login_required
def api_delete_folder(fid):
    uid = session['user_id']
    c   = get_db()

    if not c.execute('SELECT id FROM folders WHERE id=? AND user_id=?', (fid, uid)).fetchone():
        c.close()
        return jsonify(error='Folder not found.'), 404

    # Move files in this folder to un-categorised
    c.execute('UPDATE files SET folder_id=NULL WHERE folder_id=?', (fid,))
    c.execute('DELETE FROM folders WHERE id=?', (fid,))
    c.commit(); c.close()
    return jsonify(ok=True), 200


# ══════════════════════════════════════════════════════════════════════════════
#  FILE API
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    uid       = session['user_id']
    folder_id = request.form.get('folder_id') or None

    if 'file' not in request.files:
        return jsonify(error='No file provided.'), 400

    f = request.files['file']
    if not f or not f.filename:
        return jsonify(error='Invalid file.'), 400

    original = f.filename
    ext      = os.path.splitext(original)[1]
    stored   = str(uuid.uuid4()) + ext
    path     = os.path.join(UPLOAD_FOLDER, stored)
    f.save(path)
    size = os.path.getsize(path)

    c = get_db()
    c.execute(
        'INSERT INTO files (user_id, folder_id, stored_name, original_name, size) VALUES (?,?,?,?,?)',
        (uid, folder_id, stored, original, size))
    c.commit(); c.close()
    return jsonify(ok=True, name=original), 201

@app.route('/api/file/<int:fid>/delete', methods=['POST'])
@login_required
def api_delete_file(fid):
    uid = session['user_id']
    c   = get_db()
    rec = c.execute('SELECT * FROM files WHERE id=? AND user_id=?', (fid, uid)).fetchone()

    if not rec:
        c.close()
        return jsonify(error='File not found.'), 404

    p = os.path.join(UPLOAD_FOLDER, rec['stored_name'])
    if os.path.exists(p):
        os.remove(p)

    c.execute('DELETE FROM files WHERE id=?', (fid,))
    c.commit(); c.close()
    return jsonify(ok=True), 200

@app.route('/download/<int:fid>')
@login_required
def download(fid):
    uid = session['user_id']
    c   = get_db()
    rec = c.execute('SELECT * FROM files WHERE id=? AND user_id=?', (fid, uid)).fetchone()
    c.close()

    if not rec:
        return 'File not found', 404

    path = os.path.join(UPLOAD_FOLDER, rec['stored_name'])
    if not os.path.exists(path):
        return 'File missing on server', 404

    return send_file(path, as_attachment=True, download_name=rec['original_name'])


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
