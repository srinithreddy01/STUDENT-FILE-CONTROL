/* =================================================================
   app.js — Student Sync  (plain ES5-compatible vanilla JS)
================================================================= */

/* ── Auth: tab switcher ──────────────────────────────────────────*/
function showTab(tab) {
  var loginForm  = document.getElementById('login-form');
  var signupForm = document.getElementById('signup-form');
  var btns       = document.querySelectorAll('.tab-btn');

  if (!loginForm) return;

  if (tab === 'login') {
    loginForm.classList.remove('hidden');
    signupForm.classList.add('hidden');
  } else {
    loginForm.classList.add('hidden');
    signupForm.classList.remove('hidden');
  }
  btns.forEach(function(b) {
    b.classList.toggle('active', b.dataset.tab === tab);
  });
}

/* ── Create Folder modal ────────────────────────────────────────*/
function openModal() {
  var bd = document.getElementById('modal');
  if (!bd) return;
  bd.style.display = 'flex';
  clearModalErr();
  var inp = document.getElementById('folderInput');
  if (inp) { inp.value = ''; setTimeout(function(){ inp.focus(); }, 60); }
}

function closeModal() {
  var bd = document.getElementById('modal');
  if (bd) bd.style.display = 'none';
  clearModalErr();
}

function clearModalErr() {
  var e = document.getElementById('modalError');
  if (e) e.textContent = '';
}

function showModalErr(msg) {
  var e = document.getElementById('modalError');
  if (e) e.textContent = msg;
}

function createFolder() {
  var inp  = document.getElementById('folderInput');
  var name = inp ? inp.value.trim() : '';
  if (!name) { showModalErr('Please enter a folder name.'); return; }
  clearModalErr();

  var fd = new FormData();
  fd.append('name', name);

  fetch('/api/folder/create', { method: 'POST', body: fd })
    .then(function(res) {
      return res.json().then(function(data) {
        return { ok: res.ok, data: data };
      });
    })
    .then(function(r) {
      if (!r.ok) { showModalErr(r.data.error || 'Could not create folder.'); return; }
      closeModal();
      window.location.href = '/dashboard?folder=' + r.data.id;
    })
    .catch(function() { showModalErr('Network error. Please try again.'); });
}

/* ── Delete folder ──────────────────────────────────────────────*/
function deleteFolder(event, fid) {
  event.stopPropagation();
  event.preventDefault();

  if (!confirm('Delete this folder?\nFiles inside will be moved to All Files.')) return;

  fetch('/api/folder/' + fid + '/delete', { method: 'POST' })
    .then(function(res) {
      if (res.ok) {
        var cur = new URLSearchParams(window.location.search).get('folder');
        if (String(cur) === String(fid)) {
          window.location.href = '/dashboard';
        } else {
          window.location.reload();
        }
      } else {
        return res.json().then(function(d) {
          alert('Error: ' + (d.error || 'Could not delete folder.'));
        });
      }
    })
    .catch(function() { alert('Network error — please try again.'); });
}

/* ── Delete file ────────────────────────────────────────────────*/
function deleteFile(fid) {
  if (!confirm('Permanently delete this file?')) return;

  fetch('/api/file/' + fid + '/delete', { method: 'POST' })
    .then(function(res) {
      if (res.ok) {
        var card = document.getElementById('fc-' + fid);
        if (card) {
          card.style.transition = 'opacity .2s, transform .2s';
          card.style.opacity    = '0';
          card.style.transform  = 'scale(.95)';
          setTimeout(function() { card.remove(); updateCount(-1); }, 230);
        }
      } else {
        return res.json().then(function(d) {
          alert('Error: ' + (d.error || 'Could not delete file.'));
        });
      }
    })
    .catch(function() { alert('Network error — please try again.'); });
}

function updateCount(delta) {
  var el = document.getElementById('file-count');
  if (el) {
    var n = parseInt(el.textContent || '0') + delta;
    el.textContent = n < 0 ? 0 : n;
  }
}

/* ── Upload ─────────────────────────────────────────────────────*/
document.addEventListener('DOMContentLoaded', function() {

  /* Folder modal keyboard shortcuts */
  var folderInput = document.getElementById('folderInput');
  if (folderInput) {
    folderInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter')  createFolder();
      if (e.key === 'Escape') closeModal();
    });
  }

  /* Close modal when clicking backdrop */
  var backdrop = document.getElementById('modal');
  if (backdrop) {
    backdrop.addEventListener('click', function(e) {
      if (e.target === backdrop) closeModal();
    });
  }

  /* --- Upload zone wiring --- */
  var zone      = document.getElementById('dropZone');
  var fileInput = document.getElementById('fileInput');
  var progWrap  = document.getElementById('progWrap');
  var progFill  = document.getElementById('progFill');
  var statusEl  = document.getElementById('uploadStatus');

  if (!zone || !fileInput) return;

  /* Click zone to open file picker */
  zone.addEventListener('click', function(e) {
    if (e.target.closest('button')) return;  // don't trigger on buttons inside zone
    fileInput.click();
  });

  fileInput.addEventListener('change', function() {
    if (this.files && this.files[0]) upload(this.files[0]);
    this.value = '';   // reset so same file can be re-selected
  });

  /* Drag & drop */
  zone.addEventListener('dragover', function(e) {
    e.preventDefault(); zone.classList.add('dragover');
  });
  zone.addEventListener('dragleave', function(e) {
    if (!zone.contains(e.relatedTarget)) zone.classList.remove('dragover');
  });
  zone.addEventListener('drop', function(e) {
    e.preventDefault(); zone.classList.remove('dragover');
    var f = e.dataTransfer.files[0];
    if (f) upload(f);
  });

  /* XHR upload with progress tracking */
  function upload(file) {
    var folderId = new URLSearchParams(window.location.search).get('folder');

    var fd = new FormData();
    fd.append('file', file);
    if (folderId && folderId !== 'root') fd.append('folder_id', folderId);

    progWrap.style.display   = 'block';
    progFill.style.width     = '0%';
    progFill.style.background = '#2563eb';
    statusEl.textContent     = 'Uploading "' + file.name + '"…';
    statusEl.style.color     = '#64748b';
    zone.style.pointerEvents = 'none';

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload');

    xhr.upload.addEventListener('progress', function(e) {
      if (e.lengthComputable) {
        var pct = Math.round(e.loaded / e.total * 100);
        progFill.style.width = pct + '%';
        statusEl.textContent = 'Uploading… ' + pct + '%';
      }
    });

    xhr.addEventListener('load', function() {
      if (xhr.status === 201) {
        progFill.style.background = '#16a34a';
        progFill.style.width      = '100%';
        statusEl.textContent      = '✓  Upload complete! Reloading…';
        statusEl.style.color      = '#16a34a';
        setTimeout(function() { window.location.reload(); }, 700);
      } else {
        var msg = 'Upload failed.';
        try { msg = JSON.parse(xhr.responseText).error || msg; } catch(ex) {}
        statusEl.textContent     = '✗  ' + msg;
        statusEl.style.color     = '#dc2626';
        progWrap.style.display   = 'none';
        zone.style.pointerEvents = 'auto';
      }
    });

    xhr.addEventListener('error', function() {
      statusEl.textContent     = '✗  Network error — please try again.';
      statusEl.style.color     = '#dc2626';
      progWrap.style.display   = 'none';
      zone.style.pointerEvents = 'auto';
    });

    xhr.send(fd);
  }
});
