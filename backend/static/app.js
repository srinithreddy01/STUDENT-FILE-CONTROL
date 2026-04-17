/* ═══════════════════════════════════════════════════════════════
   app.js — Student Sync (vanilla JS, no framework)
═══════════════════════════════════════════════════════════════ */

// ── Auth page: tab switcher ────────────────────────────────────────────────────
function switchTab(tab) {
  const loginForm  = document.getElementById('login-form');
  const signupForm = document.getElementById('signup-form');
  const tabs       = document.querySelectorAll('.auth-tab');
  if (!loginForm) return;

  if (tab === 'login') {
    loginForm.classList.remove('hidden');
    signupForm.classList.add('hidden');
    tabs[0].classList.add('active');
    tabs[1].classList.remove('active');
  } else {
    loginForm.classList.add('hidden');
    signupForm.classList.remove('hidden');
    tabs[0].classList.remove('active');
    tabs[1].classList.add('active');
  }
}

// ── Folder modal ───────────────────────────────────────────────────────────────
function openFolderModal() {
  document.getElementById('folderModal').style.display = 'flex';
  setTimeout(() => document.getElementById('folderNameInput').focus(), 50);
}

function closeFolderModal() {
  document.getElementById('folderModal').style.display = 'none';
  document.getElementById('folderNameInput').value = '';
  const err = document.getElementById('folderError');
  if (err) { err.style.display = 'none'; }
}

async function createFolder() {
  const nameInput = document.getElementById('folderNameInput');
  const name      = nameInput.value.trim();
  const errEl     = document.getElementById('folderError');

  if (!name) return;
  errEl.style.display = 'none';

  const fd = new FormData();
  fd.append('name', name);

  try {
    const res  = await fetch('/folder/create', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) {
      errEl.textContent    = data.error;
      errEl.style.display  = 'block';
      return;
    }
    closeFolderModal();
    window.location.reload();
  } catch {
    errEl.textContent   = 'Network error — please try again';
    errEl.style.display = 'block';
  }
}

// ── Delete folder ──────────────────────────────────────────────────────────────
async function deleteFolder(event, folderId) {
  event.stopPropagation();
  event.preventDefault();
  if (!confirm('Delete this folder? Files inside will move to All Files.')) return;

  const res = await fetch(`/folder/${folderId}`, { method: 'DELETE' });
  if (res.ok) {
    const url = new URL(window.location.href);
    if (url.searchParams.get('folder') == folderId) {
      window.location.href = '/dashboard';
    } else {
      window.location.reload();
    }
  }
}

// ── Delete file ────────────────────────────────────────────────────────────────
async function deleteFile(fileId) {
  if (!confirm('Permanently delete this file?')) return;
  const res = await fetch(`/file/${fileId}`, { method: 'DELETE' });
  if (res.ok) {
    const card = document.getElementById(`file-${fileId}`);
    if (card) {
      card.style.animation = 'fadeOut .3s ease forwards';
      setTimeout(() => card.remove(), 320);
    }
  }
}

// ── Upload with progress ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {

  /* ── Folder modal keyboard shortcuts ── */
  const nameInput = document.getElementById('folderNameInput');
  if (nameInput) {
    nameInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter')  createFolder();
      if (e.key === 'Escape') closeFolderModal();
    });
  }

  /* ── Upload zone ── */
  const zone          = document.getElementById('uploadZone');
  const fileInput     = document.getElementById('fileInput');
  const progressWrap  = document.getElementById('progressWrap');
  const progressBar   = document.getElementById('progressBar');
  const uploadStatus  = document.getElementById('uploadStatus');

  if (!zone) return;   // not on dashboard page

  // click zone → open file picker (prevents double-trigger from inner button clicks)
  zone.addEventListener('click', function (e) {
    if (e.target.closest('.btn')) return;
    fileInput.click();
  });

  fileInput.addEventListener('change', function () {
    if (this.files && this.files[0]) doUpload(this.files[0]);
  });

  zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', e => { e.preventDefault(); zone.classList.remove('dragover'); });
  zone.addEventListener('drop', function (e) {
    e.preventDefault();
    zone.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (f) doUpload(f);
  });

  function doUpload(file) {
    const folderParam = new URL(window.location.href).searchParams.get('folder');
    const fd = new FormData();
    fd.append('file', file);
    if (folderParam && folderParam !== 'root') {
      fd.append('folder_id', folderParam);
    }

    progressWrap.style.display = 'block';
    progressBar.style.width    = '0%';
    uploadStatus.textContent   = `Uploading "${file.name}"…`;
    zone.style.pointerEvents   = 'none';
    fileInput.value            = '';

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload');

    xhr.upload.addEventListener('progress', function (e) {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        progressBar.style.width  = pct + '%';
        uploadStatus.textContent = `Uploading… ${pct}%`;
      }
    });

    xhr.addEventListener('load', function () {
      if (xhr.status === 201) {
        uploadStatus.textContent = '✅ Upload complete! Refreshing…';
        setTimeout(() => window.location.reload(), 800);
      } else {
        let msg = 'Upload failed';
        try { msg = JSON.parse(xhr.responseText).error || msg; } catch {}
        uploadStatus.textContent   = '❌ ' + msg;
        progressWrap.style.display = 'none';
        zone.style.pointerEvents   = 'auto';
      }
    });

    xhr.addEventListener('error', function () {
      uploadStatus.textContent   = '❌ Network error — please try again';
      progressWrap.style.display = 'none';
      zone.style.pointerEvents   = 'auto';
    });

    xhr.send(fd);
  }
});
