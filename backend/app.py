import os
import sqlite3
import uuid
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import bcrypt

app = Flask(__name__)
CORS(app)

# Allow 500MB max uploads
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_FILE = os.path.join(os.path.dirname(__file__), 'database.db')


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            folder_id INTEGER,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            size INTEGER NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(folder_id) REFERENCES folders(id)
        )
    ''')
    conn.commit()
    conn.close()


init_db()


# ── Auth ─────────────────────────────────────────────────────────────

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'error': 'Missing credentials'}), 400

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
        conn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Username already exists'}), 409
    conn.close()
    return jsonify({'message': 'Signup successful', 'user_id': user_id}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return jsonify({'message': 'Login successful', 'user_id': user['id'], 'username': user['username']}), 200
    return jsonify({'error': 'Invalid credentials'}), 401


# ── Folders ──────────────────────────────────────────────────────────

@app.route('/folders/<int:user_id>', methods=['GET'])
def list_folders(user_id):
    conn = get_db_connection()
    folders = conn.execute(
        'SELECT * FROM folders WHERE user_id = ? ORDER BY name ASC', (user_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(f) for f in folders]), 200


@app.route('/create_folder', methods=['POST'])
def create_folder():
    data = request.json
    user_id = data.get('user_id')
    name = data.get('name', '').strip()

    if not user_id or not name:
        return jsonify({'error': 'Missing user_id or folder name'}), 400

    conn = get_db_connection()
    # prevent duplicate folder names per user
    existing = conn.execute(
        'SELECT id FROM folders WHERE user_id = ? AND name = ?', (user_id, name)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({'error': 'A folder with that name already exists'}), 409

    cur = conn.cursor()
    cur.execute('INSERT INTO folders (user_id, name) VALUES (?, ?)', (user_id, name))
    conn.commit()
    folder_id = cur.lastrowid
    conn.close()
    return jsonify({'message': 'Folder created', 'folder_id': folder_id, 'name': name}), 201


@app.route('/delete_folder/<int:folder_id>', methods=['DELETE'])
def delete_folder(folder_id):
    user_id = request.args.get('user_id')
    conn = get_db_connection()

    folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', (folder_id, user_id)).fetchone()
    if not folder:
        conn.close()
        return jsonify({'error': 'Folder not found or unauthorized'}), 404

    # Move files in this folder to root (no folder)
    conn.execute('UPDATE files SET folder_id = NULL WHERE folder_id = ?', (folder_id,))
    conn.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Folder deleted, files moved to root'}), 200


# ── Files ─────────────────────────────────────────────────────────────

@app.route('/upload', methods=['POST'])
def upload_file():
    user_id = request.form.get('user_id')
    folder_id = request.form.get('folder_id') or None

    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    original_name = file.filename
    ext = os.path.splitext(original_name)[1]
    unique_filename = str(uuid.uuid4()) + ext
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(file_path)

    size = os.path.getsize(file_path)

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO files (user_id, folder_id, filename, original_name, size) VALUES (?, ?, ?, ?, ?)',
        (user_id, folder_id, unique_filename, original_name, size)
    )
    conn.commit()
    conn.close()

    return jsonify({'message': 'File uploaded successfully', 'original_name': original_name}), 201


@app.route('/files/<int:user_id>', methods=['GET'])
def list_files(user_id):
    folder_id = request.args.get('folder_id')
    conn = get_db_connection()
    if folder_id == 'root':
        files = conn.execute(
            'SELECT * FROM files WHERE user_id = ? AND folder_id IS NULL ORDER BY upload_date DESC',
            (user_id,)
        ).fetchall()
    elif folder_id:
        files = conn.execute(
            'SELECT * FROM files WHERE user_id = ? AND folder_id = ? ORDER BY upload_date DESC',
            (user_id, folder_id)
        ).fetchall()
    else:
        files = conn.execute(
            'SELECT * FROM files WHERE user_id = ? ORDER BY upload_date DESC',
            (user_id,)
        ).fetchall()
    conn.close()
    return jsonify([dict(f) for f in files]), 200


@app.route('/download/<int:file_id>', methods=['GET'])
def download_file(file_id):
    user_id = request.args.get('user_id')
    conn = get_db_connection()
    file_record = conn.execute(
        'SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, user_id)
    ).fetchone()
    conn.close()

    if not file_record:
        return jsonify({'error': 'File not found or unauthorized'}), 404

    file_path = os.path.join(UPLOAD_FOLDER, file_record['filename'])
    if not os.path.exists(file_path):
        return jsonify({'error': 'File missing on server'}), 404

    return send_file(file_path, as_attachment=True, download_name=file_record['original_name'])


@app.route('/delete/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    user_id = request.args.get('user_id')
    conn = get_db_connection()
    file_record = conn.execute(
        'SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, user_id)
    ).fetchone()

    if not file_record:
        conn.close()
        return jsonify({'error': 'File not found or unauthorized'}), 404

    file_path = os.path.join(UPLOAD_FOLDER, file_record['filename'])
    if os.path.exists(file_path):
        os.remove(file_path)

    conn.execute('DELETE FROM files WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'File deleted successfully'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
