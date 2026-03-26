const API = 'http://localhost:8000';

// ── 地图初始化 ────────────────────────────────────────────────
const map = L.map('map', { zoomControl: true }).setView([35, 105], 4);

L.tileLayer('https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}.png', {
  attribution: 'Tiles © Esri — Source: Esri, USGS, NOAA',
  maxZoom: 19,
}).addTo(map);

const drawnLayer   = new L.FeatureGroup().addTo(map);
const resultLayers = new L.FeatureGroup().addTo(map);

const drawControl = new L.Control.Draw({
  draw: {
    rectangle: { shapeOptions: { color: '#4d9fff', weight: 2 } },
    polygon: false, polyline: false, circle: false,
    marker: false, circlemarker: false,
  },
  edit: { featureGroup: drawnLayer },
});
map.addControl(drawControl);

// ── 状态变量 ──────────────────────────────────────────────────
let currentBbox   = null;
let currentLevel  = 'L2';
let searchResults = [];
let modalItem     = null;
let toastTimer    = null;

// ── 云量滑块 ──────────────────────────────────────────────────
function updateCloudSlider(el) {
  const pct = ((el.value - el.min) / (el.max - el.min) * 100).toFixed(1);
  el.style.setProperty('--fill', pct + '%');
  document.getElementById('cloud-value').textContent = el.value + '%';
}

// 初始化滑块填充
(function () {
  const el = document.getElementById('cloud-cover');
  updateCloudSlider(el);
})();

// ── 级别切换 ──────────────────────────────────────────────────
function setLevel(level, btn) {
  currentLevel = level;
  document.querySelectorAll('.pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

// ── 画框事件 ──────────────────────────────────────────────────
map.on(L.Draw.Event.CREATED, (e) => {
  drawnLayer.clearLayers();
  drawnLayer.addLayer(e.layer);

  const b = e.layer.getBounds();
  currentBbox = [
    parseFloat(b.getWest().toFixed(4)),
    parseFloat(b.getSouth().toFixed(4)),
    parseFloat(b.getEast().toFixed(4)),
    parseFloat(b.getNorth().toFixed(4)),
  ];

  const box = document.getElementById('bbox-display');
  box.classList.add('active');
  document.getElementById('bbox-hint').style.display = 'none';

  const coords = document.getElementById('bbox-coords');
  coords.style.display = 'block';
  document.getElementById('c-west').textContent  = currentBbox[0];
  document.getElementById('c-east').textContent  = currentBbox[2];
  document.getElementById('c-south').textContent = currentBbox[1];
  document.getElementById('c-north').textContent = currentBbox[3];

  document.getElementById('clear-bbox-btn').style.display = 'inline-flex';
});

function clearBbox() {
  drawnLayer.clearLayers();
  currentBbox = null;

  const box = document.getElementById('bbox-display');
  box.classList.remove('active');
  document.getElementById('bbox-hint').style.display = '';
  document.getElementById('bbox-coords').style.display = 'none';
  document.getElementById('clear-bbox-btn').style.display = 'none';
}

// ── 搜索 ──────────────────────────────────────────────────────
async function searchData() {
  if (!currentBbox) { showToast('请先在地图上画矩形选区', false, '⚠'); return; }

  const startDate = document.getElementById('start-date').value;
  const endDate   = document.getElementById('end-date').value;
  if (!startDate || !endDate) { showToast('请填写时间范围', false, '⚠'); return; }

  setSearchLoading(true);

  try {
    const res = await fetch(`${API}/api/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bbox:            currentBbox,
        start_date:      startDate,
        end_date:        endDate,
        max_cloud_cover: parseInt(document.getElementById('cloud-cover').value),
        level:           currentLevel,
        limit:           parseInt(document.getElementById('limit').value),
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '搜索失败');
    }

    const data = await res.json();
    searchResults = data.items;
    renderResults(searchResults);
    renderFootprints(searchResults);
    showToast(`找到 ${data.count} 景数据`, false, '✓');
  } catch (e) {
    showToast('错误：' + e.message, true);
  } finally {
    setSearchLoading(false);
  }
}

function setSearchLoading(loading) {
  document.getElementById('search-btn-text').style.display = loading ? 'none' : '';
  document.getElementById('search-spinner').style.display  = loading ? 'inline-block' : 'none';
  document.getElementById('search-btn').disabled = loading;
}

// ── 渲染结果列表 ──────────────────────────────────────────────
function renderResults(items) {
  const panel   = document.getElementById('results-panel');
  const list    = document.getElementById('results-list');
  const countEl = document.getElementById('results-count');
  const badge   = document.getElementById('results-level-badge');

  panel.style.display = 'flex';
  countEl.textContent = `共 ${items.length} 景`;
  badge.textContent   = currentLevel;
  badge.className     = currentLevel === 'L1' ? 'badge-l1' : 'badge-l2';
  list.innerHTML      = '';

  document.getElementById('select-all').checked = false;
  updateSelectedCount();

  if (items.length === 0) {
    list.innerHTML = '<div style="padding:24px 0;text-align:center;color:var(--text3)">未找到符合条件的数据</div>';
    return;
  }

  items.forEach((item, idx) => list.appendChild(buildCard(item, idx)));
}

function buildCard(item, idx) {
  const cloud = item.cloud_cover ?? null;
  const date  = item.datetime ? item.datetime.slice(0, 10) : '未知日期';
  const level = item.level || '';

  // 左边框颜色 class
  const cloudClass = cloud === null ? '' : cloud < 15 ? 'cloud-low' : cloud < 40 ? 'cloud-mid' : 'cloud-high';
  // 云量条颜色
  const barColor   = cloud === null ? 'var(--text3)' : cloud < 15 ? 'var(--success)' : cloud < 40 ? 'var(--warn)' : 'var(--danger)';
  const barPct     = cloud === null ? 0 : Math.min(cloud, 100);

  const card = document.createElement('div');
  card.className   = `result-card ${cloudClass}`;
  card.dataset.idx = idx;

  const thumb = item.thumbnail
    ? `<img class="card-thumb" src="${item.thumbnail}" alt="" loading="lazy" onerror="this.outerHTML='<div class=card-thumb-placeholder>🛰</div>'">`
    : `<div class="card-thumb-placeholder">🛰</div>`;

  card.innerHTML = `
    <div class="card-main">
      ${thumb}
      <div class="card-info">
        <div class="card-date">
          ${date}
          <span class="level-chip ${level === 'L1' ? 'lc-l1' : 'lc-l2'}">${level}</span>
        </div>
        <div class="card-row">
          <span class="card-scene">P${String(item.path).padStart(3,'0')} / R${String(item.row).padStart(3,'0')}</span>
        </div>
        <div class="cloud-bar-wrap">
          <div class="cloud-bar-bg">
            <div class="cloud-bar-fill" style="width:${barPct}%;background:${barColor}"></div>
          </div>
          <span class="cloud-text" style="color:${barColor}">${cloud !== null ? cloud + '%' : '--'}</span>
        </div>
      </div>
      <input type="checkbox" class="card-checkbox" onchange="onCardCheck(this)" />
    </div>
    <div class="card-actions">
      <button class="btn-card" onclick="locateItem(${idx})">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>
        定位
      </button>
      <button class="btn-card" onclick="openBandModal(${idx})">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        选波段下载
      </button>
    </div>
  `;

  card.addEventListener('mouseenter', () => highlightFootprint(idx, true));
  card.addEventListener('mouseleave', () => highlightFootprint(idx, false));

  return card;
}

function onCardCheck(cb) {
  updateSelectedCount();
  const card = cb.closest('.result-card');
  card.classList.toggle('selected', cb.checked);
}

// ── 全选 ──────────────────────────────────────────────────────
function toggleSelectAll(checked) {
  document.querySelectorAll('.card-checkbox').forEach(cb => {
    cb.checked = checked;
    cb.closest('.result-card').classList.toggle('selected', checked);
  });
  updateSelectedCount();
}

function updateSelectedCount() {
  const n = document.querySelectorAll('.card-checkbox:checked').length;
  document.getElementById('selected-count').textContent = `已选 ${n} 景`;
}

// ── 地图足迹 ──────────────────────────────────────────────────
const footprintMap = {};

function renderFootprints(items) {
  resultLayers.clearLayers();
  Object.keys(footprintMap).forEach(k => delete footprintMap[k]);

  items.forEach((item, idx) => {
    if (!item.bbox) return;
    const [w, s, e, n] = item.bbox;
    const rect = L.rectangle([[s, w], [n, e]], {
      color: '#4d9fff', weight: 1,
      fillColor: '#4d9fff', fillOpacity: 0.05,
    });

    rect.bindTooltip(
      `${item.datetime?.slice(0,10) ?? ''}  ☁ ${item.cloud_cover ?? '--'}%  P${item.path}R${item.row}`,
      { direction: 'top' }
    );
    rect.on('click', () => locateCard(idx));

    resultLayers.addLayer(rect);
    footprintMap[idx] = rect;
  });
}

function highlightFootprint(idx, on) {
  const layer = footprintMap[idx];
  if (!layer) return;
  layer.setStyle({
    color:       on ? '#34d399' : '#4d9fff',
    weight:      on ? 2 : 1,
    fillOpacity: on ? 0.12 : 0.05,
  });
}

function locateItem(idx) {
  const item = searchResults[idx];
  if (!item?.bbox) return;
  const [w, s, e, n] = item.bbox;
  map.fitBounds([[s, w], [n, e]], { padding: [60, 60] });
}

function locateCard(idx) {
  const el = document.querySelector(`.result-card[data-idx="${idx}"]`);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ── 批量下载 ──────────────────────────────────────────────────
async function downloadSelected() {
  const checked = [...document.querySelectorAll('.card-checkbox:checked')];
  if (checked.length === 0) { showToast('请先勾选景', false, '⚠'); return; }

  const queue = [];
  for (const cb of checked) {
    const item = searchResults[parseInt(cb.closest('.result-card').dataset.idx)];
    for (const [band, info] of Object.entries(item.assets)) {
      queue.push({ scene_id: item.id, band, filename: info.href.split('/').pop().split('?')[0], url: info.href });
    }
  }
  await enqueueDownloads(queue);
}

// ── 波段弹窗 ──────────────────────────────────────────────────
function openBandModal(idx) {
  modalItem = searchResults[idx];
  document.getElementById('modal-title').textContent = modalItem.id;

  const list = document.getElementById('band-list');
  list.innerHTML = '';

  for (const [band, info] of Object.entries(modalItem.assets)) {
    const label = document.createElement('label');
    label.className = 'band-item';
    label.innerHTML = `
      <input type="checkbox" value="${band}" checked />
      <span>${info.label}</span>
    `;
    list.appendChild(label);
  }

  document.getElementById('band-modal').style.display = 'flex';
}

function closeBandModal(e) {
  if (e && e.target !== document.getElementById('band-modal')) return;
  document.getElementById('band-modal').style.display = 'none';
  modalItem = null;
}

function selectPreset(preset) {
  const isL1 = modalItem?.level === 'L1';
  const presets = {
    rgb: isL1 ? ['B4', 'B3', 'B2']  : ['red', 'green', 'blue'],
    nir: isL1 ? ['B5', 'B4', 'B3']  : ['nir08', 'red', 'green'],
    all: null,
  };
  const keep = presets[preset];
  document.querySelectorAll('#band-list input[type="checkbox"]').forEach(cb => {
    cb.checked = keep ? keep.includes(cb.value) : true;
  });
}

async function confirmDownload() {
  if (!modalItem) return;

  const selected = [...document.querySelectorAll('#band-list input[type="checkbox"]:checked')]
    .map(cb => cb.value);

  if (selected.length === 0) { showToast('请至少选择一个波段', false, '⚠'); return; }

  document.getElementById('band-modal').style.display = 'none';

  const queue = selected
    .filter(band => modalItem.assets[band])
    .map(band => ({
      scene_id: modalItem.id,
      band,
      filename: modalItem.assets[band].href.split('/').pop().split('?')[0],
      url: modalItem.assets[band].href,
    }));

  await enqueueDownloads(queue);
  modalItem = null;
}

// ── 工具函数 ──────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function showToast(msg, isError = false, icon = '') {
  const el      = document.getElementById('toast');
  const iconEl  = document.getElementById('toast-icon');
  const msgEl   = document.getElementById('toast-msg');

  iconEl.textContent = icon;
  msgEl.textContent  = msg;
  el.classList.toggle('error', isError);
  el.classList.add('show');

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3000);
}

// ── 下载管理器 ────────────────────────────────────────────────
let dlMode      = 'local';
let dmOpen      = false;
let dmPollTimer = null;

const localTasks = {};
let   localQueue = [];
let   localBusy  = false;

function setDLMode(mode, btn) {
  dlMode = mode;
  document.querySelectorAll('.dm-pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('dm-server-path').style.display = mode === 'server' ? 'inline' : 'none';
}

function toggleDM() {
  dmOpen = !dmOpen;
  document.getElementById('dm-panel').style.display = dmOpen ? 'flex' : 'none';
  if (dmOpen) renderDMTasks();
}

// 统一入口：将 [{scene_id, band, filename, url}] 加入队列
async function enqueueDownloads(itemsWithBands) {
  if (dlMode === 'server') {
    const res = await fetch(`${API}/api/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: itemsWithBands, mode: 'server' }),
    });
    if (!res.ok) throw new Error('创建任务失败');
    const { count } = await res.json();
    showToast(`已加入 ${count} 个服务端下载任务`, false, '↓');
    startServerPoll();
  } else {
    for (const item of itemsWithBands) {
      const id = Math.random().toString(36).slice(2, 10);
      localTasks[id] = { id, ...item, status: 'pending', progress: 0, size_total: 0, size_done: 0, error: null };
      localQueue.push(id);
    }
    showToast(`已加入 ${itemsWithBands.length} 个本地下载任务`, false, '↓');
    processLocalQueue();
  }

  if (!dmOpen) { dmOpen = true; document.getElementById('dm-panel').style.display = 'flex'; }
  renderDMTasks();
  updateDMBadge();
}

// ── 本地队列（顺序下载，支持进度） ────────────────────────────
async function processLocalQueue() {
  if (localBusy || localQueue.length === 0) return;
  localBusy = true;

  while (localQueue.length > 0) {
    const id   = localQueue.shift();
    const task = localTasks[id];
    if (!task || task.status === 'cancelled') continue;

    task.status = 'downloading';
    renderDMTasks();

    try {
      const resp = await fetch(
        `${API}/api/download?url=${encodeURIComponent(task.url)}&filename=${encodeURIComponent(task.filename)}`
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const total  = parseInt(resp.headers.get('content-length') || '0');
      task.size_total = total;
      const reader = resp.body.getReader();
      const chunks = [];
      let done_bytes = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (task.status === 'cancelled') { reader.cancel(); break; }
        chunks.push(value);
        done_bytes += value.length;
        task.size_done = done_bytes;
        task.progress  = total > 0 ? Math.round(done_bytes / total * 100) : 50;
        updateTaskRow(id);
      }

      if (task.status === 'cancelled') continue;

      const blob    = new Blob(chunks);
      const blobUrl = URL.createObjectURL(blob);
      const a       = document.createElement('a');
      a.href = blobUrl; a.download = task.filename;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 5000);

      task.status   = 'completed';
      task.progress = 100;
    } catch (e) {
      task.status = 'failed';
      task.error  = e.message;
    }
    renderDMTasks();
    updateDMBadge();
  }
  localBusy = false;
}

// ── 服务端轮询 ─────────────────────────────────────────────────
function startServerPoll() {
  if (dmPollTimer) return;
  dmPollTimer = setInterval(async () => {
    try {
      const data   = await (await fetch(`${API}/api/tasks`)).json();
      const active = data.tasks.filter(t => ['pending','downloading'].includes(t.status));
      renderServerTasks(data.tasks);
      updateDMBadge();
      if (active.length === 0) { clearInterval(dmPollTimer); dmPollTimer = null; }
    } catch (_) {}
  }, 1500);
}

// ── 渲染 ──────────────────────────────────────────────────────
let _lastServerTasks = [];

function renderDMTasks() {
  dlMode === 'local' ? renderLocalTasks() : renderServerTasks(_lastServerTasks);
  updateDMBadge();
}

function renderLocalTasks() {
  const list  = document.getElementById('dm-list');
  const items = Object.values(localTasks);
  document.getElementById('dm-empty').style.display = items.length ? 'none' : 'block';
  [...list.children].forEach(el => { if (!el.id) el.remove(); });
  items.slice().reverse().forEach(task => {
    if (!list.querySelector(`[data-id="${task.id}"]`))
      list.insertBefore(buildTaskRow(task, 'local'), list.firstChild);
  });
  updateDMSummary(items);
}

function renderServerTasks(serverList) {
  _lastServerTasks = serverList;
  if (dlMode !== 'server') return;
  const list = document.getElementById('dm-list');
  document.getElementById('dm-empty').style.display = serverList.length ? 'none' : 'block';
  [...list.children].forEach(el => { if (!el.id) el.remove(); });
  serverList.slice().reverse().forEach(task => {
    const existing = list.querySelector(`[data-id="${task.id}"]`);
    if (existing) {
      const fill = existing.querySelector('.dm-task-progress-fill');
      const icon = existing.querySelector('.dm-status-icon');
      if (fill) { fill.style.width = task.progress + '%'; fill.className = `dm-task-progress-fill ${task.status}`; }
      if (icon) { icon.className = `dm-status-icon ${task.status}`; icon.textContent = statusIcon(task.status); }
      const sz = existing.querySelector('.dm-task-size');
      if (sz) sz.textContent = formatSize(task.size_downloaded, task.size_total);
    } else {
      list.insertBefore(buildTaskRow(task, 'server'), list.firstChild);
    }
  });
  updateDMSummary(serverList);
}

function updateTaskRow(id) {
  const task = localTasks[id];
  const el   = document.querySelector(`[data-id="${id}"]`);
  if (!task || !el) return;
  const fill = el.querySelector('.dm-task-progress-fill');
  const icon = el.querySelector('.dm-status-icon');
  const sz   = el.querySelector('.dm-task-size');
  if (fill) { fill.style.width = task.progress + '%'; fill.className = `dm-task-progress-fill ${task.status}`; }
  if (icon) { icon.className = `dm-status-icon ${task.status}`; icon.textContent = statusIcon(task.status); }
  if (sz)   sz.textContent = formatSize(task.size_done, task.size_total);
}

function buildTaskRow(task, mode) {
  const div = document.createElement('div');
  div.className  = 'dm-task';
  div.dataset.id = task.id;
  const saveBtn   = (mode === 'server' && task.status === 'completed')
    ? `<button class="dm-action-btn save" onclick="saveServerFile('${task.id}')">保存到本地</button>` : '';
  const cancelBtn = ['pending','downloading'].includes(task.status)
    ? `<button class="dm-action-btn" onclick="cancelTask('${task.id}','${mode}')">取消</button>` : '';
  const copyUrl   = task.url ? task.url.replace(/'/g, "\\'") : '';
  const copyBtn   = copyUrl
    ? `<button class="dm-action-btn copy" onclick="copyTaskUrl('${copyUrl}',this)" title="复制下载链接">
         <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
       </button>` : '';
  div.innerHTML = `
    <div class="dm-task-row1">
      <div class="dm-status-icon ${task.status}">${statusIcon(task.status)}</div>
      <span class="dm-task-name" title="${task.filename}">${task.filename}</span>
      <span class="dm-task-size">${formatSize(task.size_done ?? task.size_downloaded ?? 0, task.size_total)}</span>
      <div class="dm-task-actions">${saveBtn}${cancelBtn}${copyBtn}</div>
    </div>
    <div class="dm-task-progress">
      <div class="dm-task-progress-fill ${task.status}" style="width:${task.progress}%"></div>
    </div>
    ${task.error ? `<div class="dm-task-error">${task.error}</div>` : ''}
  `;
  return div;
}

async function copyTaskUrl(url, btn) {
  try {
    // PC L2 URL 需要先签名
    let finalUrl = url;
    if (!url.includes('landsatlook.usgs.gov') && !url.includes('usgs-landsat')) {
      const r = await fetch(`${API}/sign?url=${encodeURIComponent(url)}`);
      if (r.ok) finalUrl = (await r.json()).signed_url;
    }
    await navigator.clipboard.writeText(finalUrl);
    const orig = btn.innerHTML;
    btn.textContent = '✓';
    btn.style.color = 'var(--success)';
    setTimeout(() => { btn.innerHTML = orig; btn.style.color = ''; }, 1500);
  } catch {
    showToast('复制失败', 'error');
  }
}

function statusIcon(s) {
  return { pending:'…', downloading:'↓', completed:'✓', failed:'✗', cancelled:'—' }[s] || '?';
}

function formatSize(done, total) {
  if (!done && !total) return '';
  const f = b => b >= 1e9 ? (b/1e9).toFixed(1)+'G' : b >= 1e6 ? (b/1e6).toFixed(1)+'M' : b >= 1e3 ? (b/1e3).toFixed(0)+'K' : b+'B';
  return total > 0 ? `${f(done)} / ${f(total)}` : f(done);
}

function updateDMSummary(tasks) {
  const a = tasks.filter(t => ['pending','downloading'].includes(t.status)).length;
  const c = tasks.filter(t => t.status === 'completed').length;
  const f = tasks.filter(t => t.status === 'failed').length;
  const parts = [];
  if (a) parts.push(`${a} 进行中`);
  if (c) parts.push(`${c} 已完成`);
  if (f) parts.push(`${f} 失败`);
  document.getElementById('dm-summary').textContent = parts.join('  ·  ');
}

function updateDMBadge() {
  const tasks  = dlMode === 'local' ? Object.values(localTasks) : _lastServerTasks;
  const active = tasks.filter(t => ['pending','downloading'].includes(t.status)).length;
  const badge  = document.getElementById('dm-badge');
  badge.style.display = active > 0 ? 'flex' : 'none';
  badge.textContent   = active;
}

async function clearCompleted() {
  if (dlMode === 'server') {
    await fetch(`${API}/api/tasks/completed`, { method: 'DELETE' });
    _lastServerTasks = _lastServerTasks.filter(t => !['completed','failed','cancelled'].includes(t.status));
  } else {
    Object.keys(localTasks).forEach(id => {
      if (['completed','failed','cancelled'].includes(localTasks[id].status)) delete localTasks[id];
    });
  }
  renderDMTasks();
}

async function cancelTask(id, mode) {
  if (mode === 'server') {
    await fetch(`${API}/api/tasks/${id}`, { method: 'DELETE' });
  } else {
    if (localTasks[id]) localTasks[id].status = 'cancelled';
    localQueue = localQueue.filter(q => q !== id);
  }
  renderDMTasks();
}

// ── USGS EarthData 认证 ───────────────────────────────────────
async function checkAuthStatus() {
  try {
    const data = await (await fetch(`${API}/api/auth/status`)).json();
    const btn  = document.getElementById('auth-btn');
    const lbl  = document.getElementById('auth-btn-label');
    if (data.configured) {
      btn.classList.add('ok');
      lbl.textContent = data.username;
    } else {
      btn.classList.remove('ok');
      lbl.textContent = '未配置';
    }
  } catch (_) {}
}

function openAuthModal() {
  document.getElementById('auth-modal').style.display = 'flex';
  document.getElementById('auth-error').style.display = 'none';
}

function closeAuthModal(e) {
  if (e && e.target !== document.getElementById('auth-modal')) return;
  document.getElementById('auth-modal').style.display = 'none';
}

async function saveEarthData() {
  const username = document.getElementById('earth-username').value.trim();
  const password = document.getElementById('earth-password').value;
  if (!username || !password) {
    showAuthError('请填写用户名和密码');
    return;
  }
  setAuthSaving(true);
  try {
    const res = await fetch(`${API}/api/auth/earthdata`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) { showAuthError(data.detail || '验证失败'); return; }
    document.getElementById('auth-modal').style.display = 'none';
    showToast('USGS 账号配置成功', false, '✓');
    checkAuthStatus();
  } catch (e) {
    showAuthError('请求失败：' + e.message);
  } finally {
    setAuthSaving(false);
  }
}

function showAuthError(msg) {
  const el = document.getElementById('auth-error');
  el.textContent  = msg;
  el.style.display = 'block';
}

function setAuthSaving(saving) {
  document.getElementById('auth-save-text').style.display    = saving ? 'none'         : '';
  document.getElementById('auth-save-spinner').style.display = saving ? 'inline-block' : 'none';
  document.getElementById('auth-save-btn').disabled = saving;
}

// 页面加载后检查认证状态
checkAuthStatus();
