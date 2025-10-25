// Toast notification system
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <div class="toast-content">
      <span class="toast-icon">${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
      <span class="toast-message">${message}</span>
    </div>
  `;
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.classList.add('show');
  }, 100);
  
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Offline song saver
function saveOffline(songId, title) {
  if ('serviceWorker' in navigator && 'caches' in window) {
    const url = `/songs/view/${songId}/`;
    
    navigator.serviceWorker.controller.postMessage({
      type: 'SAVE_OFFLINE',
      url: url
    });
    
    caches.open('ayyappa-offline-songs').then(cache => {
      cache.add(url).then(() => {
        showToast(`📥 "${title}" saved for offline reading!`);
      }).catch(err => {
        showToast('Failed to save song offline', 'error');
        console.error('Offline save failed:', err);
      });
    });
  } else {
    showToast('Offline mode not supported in this browser', 'warning');
  }
}

// PWA install prompt
let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  
  const installBtn = document.getElementById('pwa-install-btn');
  if (installBtn) {
    installBtn.style.display = 'block';
  }
});

function installPWA() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        showToast('🪔 App installed successfully!');
      }
      deferredPrompt = null;
    });
  }
}

// Delete modal
function showDeleteModal(songId, songTitle) {
  const modal = document.getElementById('delete-modal');
  const titleSpan = document.getElementById('delete-song-title');
  const confirmBtn = document.getElementById('confirm-delete-btn');
  
  if (modal && titleSpan && confirmBtn) {
    titleSpan.textContent = songTitle;
    confirmBtn.onclick = () => confirmDelete(songId);
    modal.style.display = 'flex';
  }
}

function closeDeleteModal() {
  const modal = document.getElementById('delete-modal');
  if (modal) {
    modal.style.display = 'none';
  }
}

function confirmDelete(songId) {
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  
  fetch(`/songs/delete/${songId}/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': csrfToken,
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showToast(data.message);
      closeDeleteModal();
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } else {
      showToast(data.message || 'Failed to delete song', 'error');
    }
  })
  .catch(err => {
    showToast('Network error occurred', 'error');
    console.error('Delete failed:', err);
  });
}

// Close modal on outside click
window.onclick = function(event) {
  const modal = document.getElementById('delete-modal');
  if (event.target === modal) {
    closeDeleteModal();
  }
}

// Service Worker Registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/js/serviceworker.js')
      .then(registration => {
        console.log('🪔 PWA Service Worker registered:', registration.scope);
      })
      .catch(error => {
        console.log('Service Worker registration failed:', error);
      });
  });
}
