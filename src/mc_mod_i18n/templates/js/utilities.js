/* Pure utility helpers extracted from index.html (Sprint H2).
   No coupling to inline-script globals — safe to load before the main script. */

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function formatSeconds(value) {
  const seconds = Number(value || 0);
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return '0s';
  }
  if (seconds < 60) {
    return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes}m ${rest}s`;
}

function formatBytes(value) {
  const bytes = Math.max(0, Number(value || 0));
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatElapsed(ms) {
  if (ms == null) return '-';
  if (ms < 1000) return ms + 'ms';
  const s = ms / 1000;
  if (s < 60) return s.toFixed(1) + 's';
  const m = Math.floor(s / 60);
  const rs = Math.round(s % 60);
  return m + 'm ' + rs + 's';
}

function downloadJson(filename, value) {
  const blob = new Blob([JSON.stringify(value, null, 2) + '\n'], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function downloadText(filename, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function missingTokens(sourceTokens, targetTokens) {
  const counts = new Map();
  targetTokens.forEach(token => counts.set(token, (counts.get(token) || 0) + 1));
  const missing = [];
  sourceTokens.forEach(token => {
    const count = counts.get(token) || 0;
    if (count > 0) {
      counts.set(token, count - 1);
    } else {
      missing.push(token);
    }
  });
  return missing;
}

function paginate(items, page, pageSize) {
  const totalItems = items.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const currentPage = Math.min(Math.max(1, Number(page) || 1), totalPages);
  const start = (currentPage - 1) * pageSize;
  const end = Math.min(start + pageSize, totalItems);
  return {
    rows: items.slice(start, end),
    page: currentPage,
    totalPages,
    start,
    end,
    totalItems
  };
}

function pagerPages(currentPage, totalPages) {
  const pages = new Set([1, totalPages]);
  for (let page = currentPage - 2; page <= currentPage + 2; page += 1) {
    if (page >= 1 && page <= totalPages) {
      pages.add(page);
    }
  }
  return Array.from(pages).sort((a, b) => a - b);
}
