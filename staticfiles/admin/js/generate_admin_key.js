/**
 * generate_admin_key.js
 * Injects a "Generate Key" button next to the admin_key_input field
 * in the Django admin Institute form.
 */
(function () {
  'use strict';

  function generateHex32() {
    // Generate 16 random bytes → 32 hex characters
    var array = new Uint8Array(16);
    window.crypto.getRandomValues(array);
    return Array.from(array, function (b) {
      return b.toString(16).padStart(2, '0');
    }).join('');
  }

  function injectButton() {
    var field = document.getElementById('admin_key_input_field');
    if (!field) return; // not on create page

    // Avoid double-injecting
    if (document.getElementById('generate-key-btn')) return;

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'generate-key-btn';
    btn.textContent = '🔑 Generate Key';
    btn.style.cssText = [
      'margin-left: 10px',
      'padding: 6px 14px',
      'background: #417690',
      'color: #fff',
      'border: none',
      'border-radius: 4px',
      'font-size: 13px',
      'cursor: pointer',
      'vertical-align: middle',
      'font-family: monospace',
      'letter-spacing: 0.5px',
    ].join(';');

    btn.addEventListener('mouseover', function () {
      btn.style.background = '#2b5570';
    });
    btn.addEventListener('mouseout', function () {
      btn.style.background = '#417690';
    });

    btn.addEventListener('click', function () {
      var key = generateHex32();
      field.value = key;
      field.style.borderColor = '#28a745';

      // Show a small "Copied" hint
      var hint = document.getElementById('key-hint');
      if (!hint) {
        hint = document.createElement('span');
        hint.id = 'key-hint';
        hint.style.cssText = 'margin-left:8px; color:#28a745; font-size:12px; font-weight:bold;';
        btn.parentNode.insertBefore(hint, btn.nextSibling);
      }
      hint.textContent = '✓ Key generated!';
      setTimeout(function () { hint.textContent = ''; }, 3000);
    });

    field.parentNode.appendChild(btn);
  }

  // Run after DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectButton);
  } else {
    injectButton();
  }
})();
