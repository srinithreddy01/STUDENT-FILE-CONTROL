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

# ── App setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = 'studentsync_secretkey_2026'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024   # 500 MB

BASE_DIR      = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DB_FILE       = os.path.join(BASE_DIR, 'database.db')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── Jinja2 custom filter ───────────────────────────────────────────────────────
@app.template_filter('format_size')
def format_size(size):
    if not size or size == 0:
        return '0 B'
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = int(math.floor(math.log(size, 1024)))
    i = min(i, len(units) - 1)
    return f"{size / (1024 ** i):.1f} {units[i]}"


# ── Database ───────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS folders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            name         TEXT NOT NULL,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS files (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            folder_id     INTEGER,
            filename      TEXT NOT NULL,
            original_name TEXT NOT NULL,
            size          INTEGER NOT NULL,
            upload_date   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id)   REFERENCES users(id),
            FOREIGN KEY(folder_id) REFERENCES folders(id)
        );
    ''')
    conn.commit()
    conn.close()


init_db()


# ── Auth decorator ─────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'user_id' in session else url_for('auth'))


@app.route('/auth')
def auth():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('auth.html')


@app.route('/auth/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and bcrypt.checkpw(password.encode(), user['password']):
        session['user_id']  = user['id']
        session['username'] = user['username']
        return redirect(url_for('dashboard'))

    return render_template('auth.html',
        error_login='Invalid username or password',
        show_signup=False)


@app.route('/auth/signup', methods=['POST'])
def signup():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        return render_template('auth.html',
            error_signup='All fields are required', show_signup=True)

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                    (username, hashed))
        conn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return render_template('auth.html',
            error_signup='Username already taken', show_signup=True)
    conn.close()

    session['user_id']  = user_id
    session['username'] = username
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth'))


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/dashboard')
@login_required
def dashboard():
    user_id   = session['user_id']
    folder_id = request.args.get('folder')   # None | 'root' | '<int>'

    conn = get_db()
    folders = conn.execute(
        'SELECT * FROM folders WHERE user_id = ? ORDER BY name ASC',
        (user_id,)
    ).fetchall()

    if folder_id == 'root':
        files = conn.execute(
            'SELECT * FROM files WHERE user_id = ? AND folder_id IS NULL '
            'ORDER BY upload_date DESC', (user_id,)
        ).fetchall()
        current_label = 'Uncategorised'
    elif folder_id:
        files = conn.execute(
            'SELECT * FROM files WHERE user_id = ? AND folder_id = ? '
            'ORDER BY upload_date DESC', (user_id, folder_id)
        ).fetchall()
        match = next((f for f in folders if str(f['id']) == folder_id), None)
        current_label = match['name'] if match else 'Folder'
    else:
        files = conn.execute(
            'SELECT * FROM files WHERE user_id = ? ORDER BY upload_date DESC',
            (user_id,)
        ).fetchall()
        current_label = 'All Files'

    conn.close()

    return render_template('dashboard.html',
        folders=folders,
        files=files,
        active_folder=folder_id,
        current_label=current_label,
        username=session['username']
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FOLDER ROUTES  (AJAX / JSON)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/folder/create', methods=['POST'])
@login_required
def create_folder():
    name    = request.form.get('name', '').strip()
    user_id = session['user_id']

    if not name:
        return jsonify({'error': 'Folder name is required'}), 400

    conn = get_db()
    if conn.execute('SELECT id FROM folders WHERE user_id = ? AND name = ?',
                    (user_id, name)).fetchone():
        conn.close()
        return jsonify({'error': 'A folder with that name already exists'}), 409

    cur = conn.cursor()
    cur.execute('INSERT INTO folders (user_id, name) VALUES (?, ?)', (user_id, name))
    conn.commit()
    folder_id = cur.lastrowid
    conn.close()
    return jsonify({'id': folder_id, 'name': name}), 201


@app.route('/folder/<int:folder_id>', methods=['DELETE'])
@login_required
def delete_folder(folder_id):
    user_id = session['user_id']
    conn = get_db()
    row = conn.execute(
        'SELECT id FROM folders WHERE id = ? AND user_id = ?',
        (folder_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Not found'}), 404

    conn.execute('UPDATE files SET folder_id = NULL WHERE folder_id = ?', (folder_id,))
    conn.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Folder deleted'}), 200


# ══════════════════════════════════════════════════════════════════════════════
#  FILE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    user_id   = session['user_id']
    folder_id = request.form.get('folder_id') or None

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'No filename'}), 400

    original_name = f.filename
    ext          = os.path.splitext(original_name)[1]
    unique_name  = str(uuid.uuid4()) + ext
    save_path    = os.path.join(UPLOAD_FOLDER, unique_name)
    f.save(save_path)
    size = os.path.getsize(save_path)

    conn = get_db()
    conn.execute(
        'INSERT INTO files (user_id, folder_id, filename, original_name, size) '
        'VALUES (?, ?, ?, ?, ?)',
        (user_id, folder_id, unique_name, original_name, size)
    )
    conn.commit()
    conn.close()
    return jsonify({'message': 'Uploaded successfully', 'name': original_name}), 201


@app.route('/download/<int:file_id>')
@login_required
def download(file_id):
    user_id = session['user_id']
    conn    = get_db()
    rec     = conn.execute(
        'SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, user_id)
    ).fetchone()
    conn.close()

    if not rec:
        return 'File not found or access denied', 404

    path = os.path.join(UPLOAD_FOLDER, rec['filename'])
    if not os.path.exists(path):
        return 'File missing on server', 404

    return send_file(path, as_attachment=True, download_name=rec['original_name'])


@app.route('/file/<int:file_id>', methods=['DELETE'])
@login_required
def delete_file(file_id):
    user_id = session['user_id']
    conn    = get_db()
    rec     = conn.execute(
        'SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, user_id)
    ).fetchone()

    if not rec:
        conn.close()
        return jsonify({'error': 'Not found'}), 404

    path = os.path.join(UPLOAD_FOLDER, rec['filename'])
    if os.path.exists(path):
        os.remove(path)

    conn.execute('DELETE FROM files WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'File deleted'}), 200


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
