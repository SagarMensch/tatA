const API = window.API_BASE || 'http://localhost:8000';
const out = document.getElementById('output');

async function call(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  const data = await res.json();
  out.textContent = JSON.stringify(data, null, 2);
}

document.getElementById('healthBtn').onclick = () => call('/health');
document.getElementById('demoBtn').onclick = () => call('/demo/reconcile');
document.getElementById('genBtn').onclick = () => call('/generate/synthetic', { method: 'POST' });
