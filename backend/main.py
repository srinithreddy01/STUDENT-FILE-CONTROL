#!/usr/bin/env python3
"""
Student Sync — Pure Python Full-Stack File Manager
UI: NiceGUI  |  DB: SQLite  |  Auth: bcrypt + app.storage.user
Run: python main.py
"""

import os
import math
import sqlite3
import uuid
import bcrypt
from pathlib import Path
from nicegui import ui, app, events
from fastapi.responses import FileResponse, RedirectResponse

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).parent
UPLOADS  = BASE_DIR / 'uploads'
DB_FILE  = str(BASE_DIR / 'database.db')
UPLOADS.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════════
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
    conn.commit()
    conn.close()


init_db()


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
def fmt_size(b):
    try:
        b = int(b)
        if b == 0:
            return '0 B'
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        i = min(int(math.floor(math.log(max(b, 1), 1024))), 4)
        return f"{b / (1024 ** i):.1f} {units[i]}"
    except Exception:
        return '? B'


def current_user():
    """Return (user_id, username) from NiceGUI's per-browser session storage."""
    return (
        app.storage.user.get('user_id'),
        app.storage.user.get('username')
    )


# ══════════════════════════════════════════════════════════════════
#  FASTAPI ROUTE: file download (binary response)
# ══════════════════════════════════════════════════════════════════
@app.get('/dl/{file_id}')
async def download_file(file_id: int):
    uid, _ = current_user()
    if not uid:
        return RedirectResponse('/auth')

    conn = get_db()
    rec  = conn.execute(
        'SELECT * FROM files WHERE id=? AND user_id=?', (file_id, uid)
    ).fetchone()
    conn.close()

    if not rec:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse('File not found', status_code=404)

    path = UPLOADS / rec['stored_name']
    if not path.exists():
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse('File missing on server', status_code=404)

    return FileResponse(
        str(path),
        filename=rec['original_name'],
        media_type='application/octet-stream'
    )


# ══════════════════════════════════════════════════════════════════
#  GLOBAL STYLES  (applied to every page)
# ══════════════════════════════════════════════════════════════════
GLOBAL_CSS = '''
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    body, .nicegui-content { font-family: "Inter", sans-serif !important; }

    /* --- auth page gradient --- */
    .auth-bg { background: linear-gradient(135deg, #dbeafe 0%, #f8fafc 55%, #f0fdf4 100%); }

    /* --- file cards hover --- */
    .file-card { transition: transform .15s, box-shadow .15s; cursor: default; }
    .file-card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,.09); }

    /* --- folder sidebar rows --- */
    .folder-row { transition: background .12s; }
    .folder-del  { opacity: 0; pointer-events: none; transition: opacity .15s; }
    .folder-row:hover .folder-del { opacity: .75; pointer-events: auto; }
    .folder-del:hover { opacity: 1 !important; }

    /* --- upload zone --- */
    .q-uploader { border: 2px dashed #e2e8f0 !important; border-radius: 14px !important;
                  background: white !important; width: 100% !important; }
    .q-uploader:hover { border-color: #2563eb !important; background: #eff6ff !important; }
    .q-uploader__header { background: transparent !important; color: #64748b !important; }
    .q-uploader__list    { display: none; }

    /* --- drawer top spacing --- */
    .q-drawer { padding-top: 0 !important; }
'''


# ══════════════════════════════════════════════════════════════════
#  AUTH PAGE  /  /auth
# ══════════════════════════════════════════════════════════════════
@ui.page('/')
@ui.page('/auth')
def auth_page():
    uid, _ = current_user()
    if uid:
        ui.navigate.to('/dashboard')
        return

    ui.add_css(GLOBAL_CSS + 'body { background: linear-gradient(135deg,#dbeafe,#f8fafc 55%,#f0fdf4); }')
    ui.query('body').classes('min-h-screen flex items-center justify-center')

    with ui.card().classes('w-96 rounded-2xl shadow-2xl overflow-hidden p-0'):
        with ui.column().classes('p-8 gap-0 w-full'):

            # ── Brand ─────────────────────────────────────────────
            with ui.row().classes('items-center justify-center gap-2 mb-1'):
                ui.icon('folder_copy', color='primary', size='30px')
                ui.label('Student Sync').classes('text-2xl font-bold text-blue-600')

            ui.label('Manage your study files securely from anywhere').classes(
                'text-xs text-gray-400 text-center mb-5 block'
            )

            # ── Error banner ───────────────────────────────────────
            err = ui.label('').classes(
                'text-xs text-red-600 font-medium bg-red-50 border border-red-200 '
                'rounded-lg px-3 py-2 w-full mb-3 hidden'
            )

            def show_err(msg: str):
                err.set_text(msg)
                err.classes(remove='hidden')

            def hide_err():
                err.classes(add='hidden')

            # ── Tabs ───────────────────────────────────────────────
            with ui.tabs().classes('w-full bg-gray-100 rounded-xl mb-4').props('dense') as tabs:
                t_login  = ui.tab('Sign In',  icon='login')
                t_signup = ui.tab('Sign Up', icon='person_add')

            with ui.tab_panels(tabs, value=t_login).classes('w-full'):

                # ─ Login panel ─────────────────────────────────────
                with ui.tab_panel(t_login).classes('p-0 gap-2 flex flex-col'):
                    l_user = ui.input('Username', placeholder='Your username').classes('w-full')
                    l_pass = ui.input(
                        'Password', placeholder='Your password',
                        password=True, password_toggle_button=True
                    ).classes('w-full')

                    def do_login():
                        hide_err()
                        u = l_user.value.strip()
                        p = l_pass.value
                        if not u or not p:
                            show_err('Please fill in all fields.')
                            return
                        conn = get_db()
                        user = conn.execute(
                            'SELECT * FROM users WHERE username=?', (u,)
                        ).fetchone()
                        conn.close()
                        if not user or not bcrypt.checkpw(p.encode(), bytes(user['password'])):
                            show_err('Incorrect username or password.')
                            return
                        app.storage.user['user_id']  = user['id']
                        app.storage.user['username'] = user['username']
                        ui.navigate.to('/dashboard')

                    l_user.on('keydown.enter', do_login)
                    l_pass.on('keydown.enter', do_login)
                    ui.button('Sign In', icon='login', on_click=do_login).classes(
                        'w-full mt-2'
                    ).props('unelevated color=primary')

                # ─ Signup panel ────────────────────────────────────
                with ui.tab_panel(t_signup).classes('p-0 gap-2 flex flex-col'):
                    s_user = ui.input(
                        'Choose a username', placeholder='e.g. john_student'
                    ).classes('w-full')
                    s_pass = ui.input(
                        'Create a password', placeholder='Min. 6 characters',
                        password=True, password_toggle_button=True
                    ).classes('w-full')

                    def do_signup():
                        hide_err()
                        u = s_user.value.strip()
                        p = s_pass.value
                        if not u or not p:
                            show_err('Please fill in all fields.')
                            return
                        if len(p) < 6:
                            show_err('Password must be at least 6 characters.')
                            return
                        hashed = bcrypt.hashpw(p.encode(), bcrypt.gensalt())
                        conn   = get_db()
                        try:
                            cur = conn.cursor()
                            cur.execute(
                                'INSERT INTO users (username, password) VALUES (?,?)',
                                (u, hashed)
                            )
                            conn.commit()
                            new_uid = cur.lastrowid
                        except sqlite3.IntegrityError:
                            conn.close()
                            show_err('Username already taken — choose another.')
                            return
                        conn.close()
                        app.storage.user['user_id']  = new_uid
                        app.storage.user['username'] = u
                        ui.navigate.to('/dashboard')

                    s_user.on('keydown.enter', do_signup)
                    s_pass.on('keydown.enter', do_signup)
                    ui.button('Create Account', icon='person_add', on_click=do_signup).classes(
                        'w-full mt-2'
                    ).props('unelevated color=primary')


# ══════════════════════════════════════════════════════════════════
#  DASHBOARD PAGE  /dashboard
# ══════════════════════════════════════════════════════════════════
@ui.page('/dashboard')
def dashboard_page():
    uid, username = current_user()
    if not uid:
        ui.navigate.to('/auth')
        return

    ui.add_css(GLOBAL_CSS + 'body { background-color: #f1f5f9; }')

    # Mutable state
    st = {
        'folder_id':   None,
        'folder_name': 'All Files',
        'history':     [],          # list of (folder_id, folder_name) for Back navigation
    }

    # ── Navbar ──────────────────────────────────────────────────────
    with ui.header(elevated=False).classes(
        'bg-white border-b px-4 h-16 items-center justify-between shadow-sm z-50'
    ):
        with ui.row().classes('items-center gap-2'):

            # ── Back arrow button ─────────────────────────────────
            back_btn = ui.button(
                icon='arrow_back',
                on_click=lambda: go_back()
            ).props('flat round dense').classes(
                'text-gray-400 hover:text-blue-600 hover:bg-blue-50'
            ).tooltip('Go back')

            # Brand
            ui.icon('folder_copy', color='primary', size='24px')
            ui.label('Student Sync').classes('text-xl font-bold text-blue-600')

        with ui.row().classes('items-center gap-4'):
            ui.label(f'👋  {username}').classes('text-sm text-gray-400 font-medium')

            def logout():
                app.storage.user.clear()
                ui.navigate.to('/auth')

            ui.button('Logout', icon='logout', on_click=logout).props('flat dense')

    # ── Left Drawer (Sidebar) ────────────────────────────────────────
    with ui.left_drawer(value=True, fixed=True, bordered=True).classes(
        'bg-white px-3 pt-6 pb-4 flex flex-col gap-1'
    ) as drawer:
        sidebar_col = ui.column().classes('w-full gap-0')

    # ── Main Content ─────────────────────────────────────────────────
    with ui.column().classes('p-8 gap-6 w-full max-w-screen-xl mx-auto'):

        # Top bar: title + upload button
        with ui.row().classes('items-end justify-between w-full'):
            with ui.column().classes('gap-0'):
                page_title = ui.label(st['folder_name']).classes(
                    'text-2xl font-bold text-gray-900'
                )
                file_count = ui.label('').classes('text-sm text-gray-400 mt-1')

            upload_btn = ui.button(
                'Upload File', icon='upload',
                on_click=lambda: ui.run_javascript(
                    'document.querySelector(".q-uploader__input").click()'
                )
            ).classes('bg-blue-600 text-white font-semibold').props('unelevated')

        # ── Upload zone ─────────────────────────────────────────────
        with ui.element('div').classes('w-full'):
            folder_hint_label = ui.label(
                'Drag & drop or click to browse — files over 50 MB fully supported'
            ).classes('text-xs text-gray-400 text-center mb-2')

            def handle_upload(e: events.UploadEventArguments):
                folder_id = st['folder_id']
                original  = e.name
                ext       = os.path.splitext(original)[1]
                stored    = str(uuid.uuid4()) + ext
                path      = UPLOADS / stored

                with open(str(path), 'wb') as f:
                    f.write(e.content.read())

                sz = path.stat().st_size
                conn = get_db()
                conn.execute(
                    'INSERT INTO files (user_id,folder_id,stored_name,original_name,size) '
                    'VALUES (?,?,?,?,?)',
                    (uid, folder_id, stored, original, sz)
                )
                conn.commit()
                conn.close()
                ui.notify(f'✅  "{original}" uploaded!', type='positive', position='top-right')
                load_files()

            uploader = ui.upload(
                on_upload=handle_upload,
                auto_upload=True,
                max_file_size=500 * 1024 * 1024,
            ).props('flat label="Drop files here or click → Upload File" '
                    'accept=* color=primary icon=cloud_upload').classes('w-full')

        # ── Files container ─────────────────────────────────────────
        files_col = ui.element('div').classes('w-full')

    # ══════════════════════════════════════════════════════════════
    #  INNER FUNCTIONS
    # ══════════════════════════════════════════════════════════════

    def _apply_folder(folder_id, folder_name):
        """Update state and refresh UI — does NOT touch history."""
        st['folder_id']   = folder_id
        st['folder_name'] = folder_name
        page_title.set_text(folder_name)
        hint = (
            f'📁 Uploading into: {folder_name}'
            if folder_id is not None
            else 'Drag & drop or click to browse — files over 50 MB fully supported'
        )
        folder_hint_label.set_text(hint)
        # Enable/disable back button
        back_btn.props(
            'flat round dense' +
            ('' if st['history'] else ' disable')
        )
        build_sidebar()
        load_files()

    def select_folder(folder_id, folder_name):
        """Navigate INTO a folder — push current location onto history stack."""
        # Push current before switching (skip duplicates)
        prev = (st['folder_id'], st['folder_name'])
        if not st['history'] or st['history'][-1] != prev:
            st['history'].append(prev)
        _apply_folder(folder_id, folder_name)

    def go_back():
        """Pop the history stack and return to the previous location."""
        if not st['history']:
            return
        prev_id, prev_name = st['history'].pop()
        _apply_folder(prev_id, prev_name)

    def go_home():
        """Jump to All Files, clearing history."""
        st['history'].clear()
        _apply_folder(None, 'All Files')

    # ── Build sidebar ───────────────────────────────────────────────
    def build_sidebar():
        sidebar_col.clear()
        conn    = get_db()
        folders = conn.execute(
            'SELECT * FROM folders WHERE user_id=? ORDER BY name COLLATE NOCASE', (uid,)
        ).fetchall()
        conn.close()

        with sidebar_col:

            # ── HOME button (always visible, prominent) ────────────
            with ui.element('div').classes(
                'flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer mb-2 '
                'font-semibold text-sm '
                + ('bg-blue-600 text-white shadow-md'
                   if st['folder_id'] is None
                   else 'bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100')
            ).on('click', lambda: go_home()):
                ui.icon('home', size='20px')
                ui.label('Home').classes('flex-1')
                if st['folder_id'] is None:
                    ui.icon('check_circle', size='16px').classes('opacity-70')

            ui.separator().classes('my-2')
            ui.label('MY FOLDERS').classes(
                'text-xs font-bold uppercase tracking-widest text-gray-300 px-2 mb-1'
            )

            if folders:
                for folder in folders:
                    fid       = folder['id']
                    fname     = folder['name']
                    is_active = str(st['folder_id']) == str(fid)

                    with ui.element('div').classes(
                        'folder-row flex items-center gap-2 px-3 py-2 rounded-xl cursor-pointer mb-1 '
                        'text-sm font-medium ' +
                        ('bg-blue-50 text-blue-600 border border-blue-200'
                         if is_active else 'text-gray-500 hover:bg-gray-100')
                    ).on('click', lambda fid=fid, fname=fname: select_folder(fid, fname)):
                        ui.icon('folder_open' if is_active else 'folder', size='18px')
                        ui.label(fname).classes('flex-1 truncate').tooltip(fname)

                        def make_folder_del(fid=fid, fname=fname):
                            def do():
                                conn = get_db()
                                conn.execute(
                                    'UPDATE files SET folder_id=NULL WHERE folder_id=?', (fid,)
                                )
                                conn.execute('DELETE FROM folders WHERE id=?', (fid,))
                                conn.commit()
                                conn.close()
                                ui.notify(
                                    f'🗑  Folder "{fname}" deleted. Files moved to All Files.',
                                    type='info', position='top-right'
                                )
                                if st['folder_id'] == fid:
                                    select_folder(None, 'All Files')
                                else:
                                    build_sidebar()
                            return do

                        ui.button(
                            icon='close',
                            on_click=make_folder_del()
                        ).props('flat round dense color=red size=xs').classes(
                            'folder-del'
                        ).tooltip('Delete folder')
            else:
                ui.label('No folders yet').classes(
                    'text-xs italic text-gray-300 px-3 mt-1'
                )

            ui.separator().classes('my-3')

            # ── New Folder ──────────────────────────────────────────
            def open_new_folder_dialog():
                with ui.dialog() as dlg, ui.card().classes('p-6 rounded-2xl w-80 gap-0 shadow-2xl'):
                    with ui.row().classes('items-center gap-2 mb-1'):
                        ui.icon('create_new_folder', color='primary', size='22px')
                        ui.label('New Folder').classes('text-lg font-bold text-gray-900')

                    ui.label('Give your folder a name').classes(
                        'text-xs text-gray-400 mb-4 block'
                    )

                    f_input = ui.input(
                        'Folder name', placeholder='e.g. Semester 1 Notes'
                    ).classes('w-full')
                    f_err   = ui.label('').classes(
                        'text-xs text-red-500 font-medium hidden mt-1'
                    )

                    with ui.row().classes('justify-end gap-2 mt-4'):
                        ui.button('Cancel', on_click=dlg.close).props('flat')

                        def create_folder():
                            name = f_input.value.strip()
                            if not name:
                                f_err.set_text('Please enter a folder name.')
                                f_err.classes(remove='hidden')
                                return
                            conn = get_db()
                            if conn.execute(
                                'SELECT id FROM folders WHERE user_id=? AND name=?',
                                (uid, name)
                            ).fetchone():
                                conn.close()
                                f_err.set_text('A folder with that name already exists.')
                                f_err.classes(remove='hidden')
                                return
                            cur = conn.cursor()
                            cur.execute(
                                'INSERT INTO folders (user_id,name) VALUES (?,?)', (uid, name)
                            )
                            conn.commit()
                            new_fid = cur.lastrowid
                            conn.close()
                            dlg.close()
                            ui.notify(
                                f'📁 Folder "{name}" created!',
                                type='positive', position='top-right'
                            )
                            select_folder(new_fid, name)

                        f_input.on('keydown.enter', create_folder)
                        ui.button(
                            'Create Folder', icon='check', on_click=create_folder
                        ).props('unelevated color=primary')

                dlg.open()

            ui.button(
                'New Folder', icon='create_new_folder',
                on_click=open_new_folder_dialog
            ).props('flat dense').classes(
                'w-full text-gray-400 text-sm normal-case justify-start px-3 hover:text-blue-600'
            )

    # ── Load files ──────────────────────────────────────────────────
    def load_files():
        files_col.clear()
        conn = get_db()
        if st['folder_id'] is None:
            rows = conn.execute(
                'SELECT * FROM files WHERE user_id=? ORDER BY uploaded DESC', (uid,)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM files WHERE user_id=? AND folder_id=? ORDER BY uploaded DESC',
                (uid, st['folder_id'])
            ).fetchall()
        conn.close()

        n = len(rows)
        file_count.set_text(f'{n} file{"s" if n != 1 else ""}')

        with files_col:
            if not rows:
                with ui.column().classes('items-center py-20 text-gray-300 w-full'):
                    ui.icon('description', size='64px')
                    ui.label('No files here yet — upload something!').classes(
                        'text-sm mt-3 text-gray-400'
                    )
                return

            with ui.element('div').classes('grid gap-4').style(
                'grid-template-columns: repeat(auto-fill, minmax(300px, 1fr))'
            ):
                for row in rows:
                    fid   = row['id']
                    fname = row['original_name']
                    fsize = fmt_size(row['size'])
                    fdate = str(row['uploaded'])[:10]

                    with ui.card().classes(
                        'file-card flex-row items-center gap-3 px-4 py-3 '
                        'rounded-xl bg-white border border-gray-100 shadow-sm'
                    ):
                        # File icon
                        with ui.element('div').classes(
                            'w-11 h-11 bg-blue-50 rounded-xl flex items-center '
                            'justify-center flex-shrink-0'
                        ):
                            ui.icon('description', color='primary', size='22px')

                        # Name + meta
                        with ui.column().classes('flex-1 min-w-0 gap-0'):
                            ui.label(fname).classes(
                                'text-sm font-semibold text-gray-900 truncate'
                            ).tooltip(fname)
                            ui.label(f'{fsize}  ·  {fdate}').classes(
                                'text-xs text-gray-400 mt-0.5'
                            )

                        # ── Download + Trash bin buttons ────────────
                        with ui.row().classes('gap-1 flex-shrink-0'):

                            # Download
                            ui.button(
                                icon='download',
                                on_click=lambda fid=fid: ui.run_javascript(
                                    f'window.location.href="/dl/{fid}"'
                                )
                            ).props('flat round dense color=primary').tooltip('Download file')

                            # Trash bin  🗑
                            def make_delete(fid=fid, fname=fname):
                                def do():
                                    conn = get_db()
                                    rec  = conn.execute(
                                        'SELECT stored_name FROM files WHERE id=? AND user_id=?',
                                        (fid, uid)
                                    ).fetchone()
                                    if rec:
                                        p = UPLOADS / rec['stored_name']
                                        if p.exists():
                                            p.unlink()
                                        conn.execute('DELETE FROM files WHERE id=?', (fid,))
                                        conn.commit()
                                    conn.close()
                                    ui.notify(
                                        f'🗑  "{fname}" deleted.',
                                        type='warning', position='top-right'
                                    )
                                    load_files()
                                return do

                            ui.button(
                                icon='delete',
                                on_click=make_delete()
                            ).props('flat round dense color=red').tooltip('Delete file')

    # ── Initial render ───────────────────────────────────────────────
    back_btn.props('flat round dense disable')   # no history yet
    build_sidebar()
    load_files()


# ══════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════
ui.run(
    host='0.0.0.0',
    port=5000,
    title='Student Sync',
    favicon='📁',
    storage_secret='studentsync_nicegui_storage_2026',
    show=False,
    reload=False,
)
