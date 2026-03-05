const API = window.API_BASE || 'http://localhost:8000';
const out = document.getElementById('output');
const graphSvg = document.getElementById('graphSvg');
const graphMeta = document.getElementById('graphMeta');

function activateTab(tabId) {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
  document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
  document.getElementById(tabId).classList.add('active');
}

document.querySelectorAll('.tab').forEach(btn => {
  btn.onclick = () => activateTab(btn.dataset.tab);
});

async function call(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  const data = await res.json();
  out.textContent = JSON.stringify(data, null, 2);
  return data;
}

function colorByType(type) {
  const map = {
    Transaction: '#22d3ee',
    Customer: '#34d399',
    OpenItem: '#fbbf24',
    BankIFSC: '#a78bfa',
    Lane: '#fb7185',
    Policy: '#60a5fa',
    Entity: '#94a3b8',
  };
  return map[type] || '#94a3b8';
}

function renderGraph(payload) {
  graphSvg.innerHTML = '';
  const width = 1100;
  const height = 520;
  const nodes = payload.nodes || [];
  const edges = payload.edges || [];

  const grouped = {};
  nodes.forEach(n => {
    if (!grouped[n.type]) grouped[n.type] = [];
    grouped[n.type].push(n);
  });

  const types = Object.keys(grouped);
  const typeX = {};
  types.forEach((t, i) => {
    typeX[t] = 120 + i * ((width - 240) / Math.max(types.length - 1, 1));
  });

  const pos = {};
  types.forEach(type => {
    const arr = grouped[type];
    arr.forEach((n, idx) => {
      const y = 80 + idx * Math.min(28, (height - 120) / Math.max(arr.length, 1));
      pos[n.id] = { x: typeX[type], y };
    });
  });

  edges.forEach(e => {
    const a = pos[e.source];
    const b = pos[e.target];
    if (!a || !b) return;
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', a.x);
    line.setAttribute('y1', a.y);
    line.setAttribute('x2', b.x);
    line.setAttribute('y2', b.y);
    line.setAttribute('class', 'edge');
    graphSvg.appendChild(line);
  });

  types.forEach(type => {
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    t.setAttribute('x', typeX[type] - 35);
    t.setAttribute('y', 24);
    t.setAttribute('class', 'legend');
    t.textContent = type;
    graphSvg.appendChild(t);
  });

  nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', p.x);
    c.setAttribute('cy', p.y);
    c.setAttribute('r', 7);
    c.setAttribute('fill', colorByType(n.type));
    c.setAttribute('class', 'node');
    graphSvg.appendChild(c);

    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', p.x + 11);
    label.setAttribute('y', p.y + 4);
    label.setAttribute('class', 'label');
    label.textContent = n.label;
    graphSvg.appendChild(label);
  });

  graphMeta.textContent = `Loaded ${nodes.length} nodes and ${edges.length} edges from live API.`;
}

async function loadGraph() {
  const payload = await call('/demo/knowledge-graph');
  renderGraph(payload);
}

document.getElementById('healthBtn').onclick = () => call('/health');
document.getElementById('demoBtn').onclick = () => call('/demo/reconcile');
document.getElementById('genBtn').onclick = () => call('/generate/synthetic', { method: 'POST' });
document.getElementById('graphBtn').onclick = loadGraph;
