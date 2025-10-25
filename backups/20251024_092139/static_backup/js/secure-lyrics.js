// Secure lyrics display - disable copy, screenshot, right-click
(function() {
  'use strict';
  
  // Disable right-click context menu
  document.addEventListener('contextmenu', function(e) {
    e.preventDefault();
    showToast('🪔 Right-click disabled for sacred content', 'warning');
    return false;
  });
  
  // Disable text selection on lyrics
  const lyricsElements = document.querySelectorAll('.lyrics-content, .secure-content');
  lyricsElements.forEach(el => {
    el.style.userSelect = 'none';
    el.style.webkitUserSelect = 'none';
    el.style.mozUserSelect = 'none';
    el.style.msUserSelect = 'none';
  });
  
  // Disable keyboard shortcuts
  document.addEventListener('keydown', function(e) {
    // Ctrl+C, Ctrl+X, Ctrl+S, Ctrl+U, Ctrl+A
    if (e.ctrlKey || e.metaKey) {
      const key = e.key.toLowerCase();
      if (['c', 'x', 's', 'u', 'a', 'p'].includes(key)) {
        e.preventDefault();
        showToast('🪔 Copy/print disabled for devotional content', 'warning');
        return false;
      }
    }
    
    // PrintScreen key
    if (e.key === 'PrintScreen') {
      e.preventDefault();
      showToast('🪔 Screenshot blocked for sacred lyrics', 'warning');
      navigator.clipboard.writeText('');
      return false;
    }
    
    // F12 (Developer tools) - optional, might annoy developers
    // Uncomment if you want strict protection
    // if (e.key === 'F12') {
    //   e.preventDefault();
    //   return false;
    // }
  });
  
  // Detect screenshot attempts (limited effectiveness)
  document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
      const lyricsContent = document.querySelectorAll('.lyrics-content');
      lyricsContent.forEach(el => {
        el.style.filter = 'blur(10px)';
      });
    } else {
      setTimeout(() => {
        const lyricsContent = document.querySelectorAll('.lyrics-content');
        lyricsContent.forEach(el => {
          el.style.filter = 'none';
        });
      }, 100);
    }
  });
  
  // Watermark overlay (visual deterrent)
  function addWatermark() {
    const watermark = document.createElement('div');
    watermark.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 9999;
      background-image: repeating-linear-gradient(
        45deg,
        transparent,
        transparent 100px,
        rgba(217, 119, 6, 0.03) 100px,
        rgba(217, 119, 6, 0.03) 200px
      );
      font-size: 48px;
      color: rgba(146, 64, 14, 0.05);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      user-select: none;
    `;
    watermark.textContent = '🕉️ Ayyappa Bhajans';
    
    const lyricsPage = document.querySelector('.lyrics-content');
    if (lyricsPage) {
      document.body.appendChild(watermark);
    }
  }
  
  // Initialize on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addWatermark);
  } else {
    addWatermark();
  }
  
  // Disable drag and drop
  document.addEventListener('dragstart', function(e) {
    e.preventDefault();
    return false;
  });
  
  console.log('🪔 Sacred content protection active');
})();
