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
  const modal = document.getElementById('folderModal');
  modal.style.display = 'flex';
  setTimeout(() => {
    const input = document.getElementById('folderNameInput');
    if (input) input.focus();
  }, 60);
}

function closeFolderModal() {
  document.getElementById('folderModal').style.display = 'none';
  const input = document.getElementById('folderNameInput');
  if (input) input.value = '';
  const err = document.getElementById('folderError');
  if (err) err.style.display = 'none';
}

// Create folder via POST form-data → JSON response
async function createFolder() {
  const input = document.getElementById('folderNameInput');
  const errEl = document.getElementById('folderError');
  const name  = input ? input.value.trim() : '';

  if (!name) {
    errEl.textContent   = 'Please enter a folder name.';
    errEl.style.display = 'block';
    return;
  }
  errEl.style.display = 'none';

  const fd = new FormData();
  fd.append('name', name);

  try {
    const res  = await fetch('/folder/create', { method: 'POST', body: fd });
    const data = await res.json();

    if (!res.ok) {
      errEl.textContent   = data.error || 'Failed to create folder.';
      errEl.style.display = 'block';
      return;
    }
    // Success — close modal and go to the new folder
    closeFolderModal();
    window.location.href = '/dashboard?folder=' + data.id;

  } catch (e) {
    errEl.textContent   = 'Network error — please try again.';
    errEl.style.display = 'block';
  }
}

// ── Delete folder ──────────────────────────────────────────────────────────────
// Called from the inline × button on each folder row
async function deleteFolder(event, folderId) {
  // Stop the click from bubbling up to the folder-item (which navigates)
  event.stopPropagation();
  event.preventDefault();

  if (!confirm('Delete this folder?\nFiles inside will be moved to All Files.')) return;

  try {
    const res = await fetch('/folder/' + folderId, { method: 'DELETE' });

    if (res.ok) {
      // If we are currently inside that folder, jump to root
      const urlFolder = new URLSearchParams(window.location.search).get('folder');
      if (String(urlFolder) === String(folderId)) {
        window.location.href = '/dashboard';
      } else {
        window.location.reload();
      }
    } else {
      const data = await res.json().catch(() => ({}));
      alert('Could not delete folder: ' + (data.error || res.status));
    }
  } catch (e) {
    alert('Network error while deleting folder.');
  }
}

// ── Delete file ────────────────────────────────────────────────────────────────
async function deleteFile(fileId) {
  if (!confirm('Permanently delete this file?')) return;

  try {
    const res = await fetch('/file/' + fileId, { method: 'DELETE' });

    if (res.ok) {
      const card = document.getElementById('file-' + fileId);
      if (card) {
        card.style.transition = 'opacity .25s, transform .25s';
        card.style.opacity    = '0';
        card.style.transform  = 'scale(.96)';
        setTimeout(() => card.remove(), 260);
      }
    } else {
      const data = await res.json().catch(() => ({}));
      alert('Could not delete file: ' + (data.error || res.status));
    }
  } catch (e) {
    alert('Network error while deleting file.');
  }
}

// ── Upload with XHR progress ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {

  // Folder modal: keyboard shortcuts
  const folderInput = document.getElementById('folderNameInput');
  if (folderInput) {
    folderInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter')  createFolder();
      if (e.key === 'Escape') closeFolderModal();
    });
  }

  // Close modal when clicking the dark overlay
  const overlay = document.getElementById('folderModal');
  if (overlay) {
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeFolderModal();
    });
  }

  // ── Upload zone wiring ──────────────────────────────────────────
  const zone         = document.getElementById('uploadZone');
  const fileInput    = document.getElementById('fileInput');
  const progressWrap = document.getElementById('progressWrap');
  const progressBar  = document.getElementById('progressBar');
  const statusEl     = document.getElementById('uploadStatus');

  if (!zone || !fileInput) return;   // not on dashboard

  // Clicking zone opens picker (except when clicking the Upload button)
  zone.addEventListener('click', function (e) {
    if (e.target.closest('.btn')) return;
    fileInput.click();
  });

  fileInput.addEventListener('change', function () {
    if (this.files && this.files[0]) doUpload(this.files[0]);
  });

  zone.addEventListener('dragover', function (e) {
    e.preventDefault();
    zone.classList.add('dragover');
  });
  zone.addEventListener('dragleave', function (e) {
    e.preventDefault();
    zone.classList.remove('dragover');
  });
  zone.addEventListener('drop', function (e) {
    e.preventDefault();
    zone.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (f) doUpload(f);
  });

  function doUpload(file) {
    // Read current folder from URL
    const folderParam = new URLSearchParams(window.location.search).get('folder');

    const fd = new FormData();
    fd.append('file', file);
    // Attach folder_id only when inside a real folder (not 'root' or empty)
    if (folderParam && folderParam !== 'root') {
      fd.append('folder_id', folderParam);
    }

    // UI: show progress
    progressWrap.style.display = 'block';
    progressBar.style.width    = '0%';
    statusEl.textContent       = 'Uploading "' + file.name + '"…';
    zone.style.pointerEvents   = 'none';
    fileInput.value            = '';   // reset so the same file can be re-selected

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload');

    xhr.upload.addEventListener('progress', function (e) {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        progressBar.style.width = pct + '%';
        statusEl.textContent    = 'Uploading… ' + pct + '%';
      }
    });

    xhr.addEventListener('load', function () {
      if (xhr.status === 201) {
        statusEl.textContent = '✅ Upload complete! Refreshing…';
        setTimeout(() => window.location.reload(), 700);
      } else {
        let msg = 'Upload failed';
        try { msg = JSON.parse(xhr.responseText).error || msg; } catch {}
        statusEl.textContent       = '❌ ' + msg;
        progressWrap.style.display = 'none';
        zone.style.pointerEvents   = 'auto';
      }
    });

    xhr.addEventListener('error', function () {
      statusEl.textContent       = '❌ Network error — please try again';
      progressWrap.style.display = 'none';
      zone.style.pointerEvents   = 'auto';
    });

    xhr.send(fd);
  }
});
