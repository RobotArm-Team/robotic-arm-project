/**
 * 智能机械臂垃圾分拣管理看板
 * 纯原生 ES Module，无构建依赖，直接对接后端 /api/v1。
 */
const API_BASE = (new URLSearchParams(location.search).get('api') || '/api/v1').replace(/\/+$/, '');
const POLL_INTERVAL = 2000;
const MAX_EVENTS = 100;

const VIEW_META = {
  overview: { title: '系统概览', subtitle: '机械臂、服务与分拣任务的整体运行状态' },
  events: { title: '实时事件', subtitle: '按时间倒序展示后端事件，支持任务编号与状态筛选' },
  statistics: { title: '分类统计', subtitle: '任务成功率与识别类别分布' },
  exceptions: { title: '异常日志', subtitle: '坐标越界、安全拦截与任务失败的可观测记录' },
  tasks: { title: '任务受理', subtitle: '提交分拣任务、查询结果与软件安全停止' },
};

const STATUS_LABELS = {
  RECEIVED: '已接收',
  REJECTED: '已拒绝',
  EXECUTING: '执行中',
  RETRYING: '重试中',
  SUCCEEDED: '成功',
  FAILED: '失败',
  SAFE_MODE: '安全模式',
};

const HEALTH_LABELS = {
  READY: '就绪',
  BUSY: '忙碌',
  SAFE_MODE: '安全模式',
  OFFLINE: '离线',
};

const ARM_STATE_LABELS = {
  IDLE: '空闲',
  STOPPED: '已停止',
  RUNNING: '运行中',
  BUSY: '忙碌',
  HOME: '安全位',
};

const CLASS_LABELS = {
  plastic: '塑料',
  paper: '纸张',
  metal: '金属',
  glass: '玻璃',
  cardboard: '纸板',
  kitchen: '厨余',
  hazardous: '有害垃圾',
  recyclable: '可回收物',
  other: '其他',
  trash: '其他垃圾',
};

const ERROR_LABELS = {
  SAFE_MODE_ACTIVE: '急停未解除或系统处于安全/离线状态',
  WORKSPACE_REJECTED: '目标点位于有效工作区之外',
  INVALID_ARM_ID: '机械臂编号不受支持',
  VALIDATION_ERROR: '请求参数不符合接口契约',
  INVALID_REQUEST_BODY: '请求体无法解析',
  INVALID_LIMIT: '查询条数超出 1-100 范围',
  INVALID_STATUS: '未知的任务状态',
  TASK_NOT_FOUND: '任务不存在',
  INTERNAL_ERROR: '服务内部错误',
  NOT_FOUND: '请求的地址不存在',
  LOW_CONFIDENCE: '识别置信度低于阈值',
  OUT_OF_BOUNDS: '坐标越界',
  ARM_TIMEOUT: '机械臂通信或动作超时',
  GRAB_FAILED: '抓取失败',
  SERVICE_UNAVAILABLE: '下游服务不可用',
};

const state = {
  view: 'overview',
  autoRefresh: true,
  inFlight: false,
  online: null,
  health: null,
  stats: null,
  events: [],
  eventFilter: { taskId: '', status: '', limit: 20 },
  exceptionFilter: { keyword: '', type: '', limit: 50 },
  queryTask: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[ch]);
}

function formatTime(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return escapeHtml(iso);
  return date.toLocaleString('zh-CN', { hour12: false });
}

function formatClock(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleTimeString('zh-CN', { hour12: false });
}

function formatDuration(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${Math.round(value)} ms`;
}

function classLabel(classId) {
  if (!classId) return '—';
  return CLASS_LABELS[String(classId).toLowerCase()] || classId;
}

function statusBadge(status) {
  const key = String(status || '').toLowerCase();
  return `<span class="badge badge-${escapeHtml(key || 'unknown')}">${escapeHtml(STATUS_LABELS[status] || status || '未知')}</span>`;
}

function healthBadge(status) {
  const key = String(status || '').toLowerCase();
  return `<span class="badge badge-health-${escapeHtml(key || 'offline')}">${escapeHtml(HEALTH_LABELS[status] || status || '未知')}</span>`;
}

function renderCard({ label, value, hint, tone = '', small = false }) {
  return `
    <div class="card ${tone}">
      <span class="card-label">${escapeHtml(label)}</span>
      <strong class="card-value${small ? ' small' : ''}">${value}</strong>
      <span class="card-hint">${escapeHtml(hint || '')}</span>
    </div>`;
}

/* ------------------------------ 接口层 ------------------------------ */
const api = {
  async request(path, { method = 'GET', body } = {}) {
    const options = {
      method,
      headers: { Accept: 'application/json' },
    };
    if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    if (typeof AbortSignal !== 'undefined' && AbortSignal.timeout) {
      options.signal = AbortSignal.timeout(6000);
    }
    const response = await fetch(`${API_BASE}${path}`, options);
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!response.ok) {
      const error = new Error((data && data.message) || `请求失败（HTTP ${response.status}）`);
      error.status = response.status;
      error.code = data && data.code;
      error.payload = data;
      throw error;
    }
    return data;
  },
  getHealth: () => api.request('/health'),
  listEvents: (limit = MAX_EVENTS) => api.request(`/events?limit=${limit}`),
  getSummary: () => api.request('/statistics/summary'),
  createTask: payload => api.request('/tasks', { method: 'POST', body: payload }),
  getTask: taskId => api.request(`/tasks/${encodeURIComponent(taskId)}`),
  safetyStop: reason => api.request('/safety/stop', { method: 'POST', body: { reason } }),
};

/* ------------------------------ 渲染 ------------------------------ */
function renderConnection() {
  const dot = $('#connDot');
  const text = $('#connText');
  const alertBar = $('#alertBar');
  dot.classList.remove('online', 'offline');
  if (state.online === null) {
    text.textContent = '连接中…';
    alertBar.classList.add('hidden');
    return;
  }
  if (state.online) {
    dot.classList.add('online');
    text.textContent = '后端已连接';
    alertBar.classList.add('hidden');
    return;
  }
  dot.classList.add('offline');
  text.textContent = '后端连接失败';
  alertBar.classList.remove('hidden');
  alertBar.innerHTML = `<strong>无法连接后端服务。</strong> 请确认后端已在 8080 端口启动（<code>src/backend</code> 下执行 <code>.\\mvnw.cmd spring-boot:run</code>），页面会在恢复后自动刷新。`;
}

function renderHealth() {
  const container = $('#healthCards');
  const health = state.health;
  if (!health) {
    container.innerHTML = [
      renderCard({ label: '系统状态', value: '—', hint: '等待数据' }),
      renderCard({ label: '机械臂状态', value: '—', hint: '等待数据' }),
      renderCard({ label: '急停状态', value: '—', hint: '等待数据' }),
      renderCard({ label: '故障状态', value: '—', hint: '等待数据' }),
    ].join('');
    return;
  }
  const estop = Boolean(health.estop_active);
  const faultCleared = Boolean(health.fault_cleared);
  container.innerHTML = [
    renderCard({
      label: '系统状态',
      value: healthBadge(health.status),
      hint: `上报时间 ${formatClock(health.timestamp)}`,
      tone: health.status === 'READY' ? 'tone-success' : health.status === 'SAFE_MODE' || health.status === 'OFFLINE' ? 'tone-danger' : 'tone-warn',
      small: true,
    }),
    renderCard({
      label: '机械臂状态',
      value: escapeHtml(ARM_STATE_LABELS[health.arm_state] || health.arm_state || '—'),
      hint: `原始值 ${escapeHtml(health.arm_state || '—')}`,
      tone: 'tone-purple',
      small: true,
    }),
    renderCard({
      label: '急停状态',
      value: estop ? '已触发' : '未触发',
      hint: estop ? '任务请求将被拒绝' : '安全门禁正常',
      tone: estop ? 'tone-danger' : 'tone-success',
      small: true,
    }),
    renderCard({
      label: '故障状态',
      value: faultCleared ? '已清除' : '未清除',
      hint: faultCleared ? '可以接收新任务' : '需先排除故障',
      tone: faultCleared ? 'tone-success' : 'tone-danger',
      small: true,
    }),
  ].join('');
}

function computeRate(total, success) {
  if (!total) return 0;
  return Math.round((success / total) * 1000) / 10;
}

function renderStats() {
  const stats = state.stats;
  const container = $('#statCards');
  if (!stats) {
    container.innerHTML = [
      renderCard({ label: '任务总数', value: '—', hint: '等待数据' }),
      renderCard({ label: '成功数', value: '—', hint: '等待数据' }),
      renderCard({ label: '失败数', value: '—', hint: '等待数据' }),
      renderCard({ label: '成功率', value: '—', hint: '等待数据' }),
    ].join('');
    $('#statsRange').textContent = '—';
    renderClassBars($('#classBars'), {});
    renderDonut();
    return;
  }
  const rate = computeRate(stats.total_tasks, stats.success_count);
  container.innerHTML = [
    renderCard({ label: '任务总数', value: String(stats.total_tasks), hint: '全部已受理任务' }),
    renderCard({ label: '成功数', value: String(stats.success_count), hint: '状态为 SUCCEEDED', tone: 'tone-success' }),
    renderCard({ label: '失败数', value: String(stats.failure_count), hint: '含 FAILED 与 SAFE_MODE', tone: 'tone-danger' }),
    renderCard({ label: '成功率', value: `${rate}%`, hint: '成功数 / 任务总数', tone: 'tone-success' }),
  ].join('');
  $('#statsRange').textContent = `${formatTime(stats.from)} → ${formatTime(stats.to)}`;
  renderClassBars($('#classBars'), stats.by_class || {});
  renderDonut();
}

function renderClassBars(container, byClass) {
  if (!container) return;
  const entries = Object.entries(byClass || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    container.innerHTML = '<p class="empty">暂无识别类别数据。视觉侧写入 detection_event 后自动展示。</p>';
    return;
  }
  const max = Math.max(...entries.map(([, count]) => count), 1);
  container.innerHTML = `<div class="bars">${entries.map(([classId, count]) => `
    <div class="bar-row">
      <span class="bar-label" title="${escapeHtml(classId)}">${escapeHtml(classLabel(classId))}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max((count / max) * 100, 3)}%"></div></div>
      <span class="bar-value">${count}</span>
    </div>`).join('')}</div>`;
}

function renderDonut() {
  const stats = state.stats;
  const donut = $('#successDonut');
  if (!stats) {
    donut.style.background = 'conic-gradient(var(--border-strong) 0 100%)';
    $('#donutRate').textContent = '—';
    $('#legendSuccess').textContent = '0';
    $('#legendFailure').textContent = '0';
    $('#legendRest').textContent = '0';
    return;
  }
  const success = stats.success_count;
  const failure = stats.failure_count;
  const rest = Math.max(stats.total_tasks - success - failure, 0);
  const finished = success + failure;
  const ratio = finished ? success / finished : 0;
  const successDeg = (ratio * 100).toFixed(1);
  donut.style.background = finished
    ? `conic-gradient(var(--accent-2) 0 ${successDeg}%, var(--danger) ${successDeg}% 100%)`
    : 'conic-gradient(var(--border-strong) 0 100%)';
  $('#donutRate').textContent = finished ? `${Math.round(ratio * 100)}%` : '—';
  $('#legendSuccess').textContent = String(success);
  $('#legendFailure').textContent = String(failure);
  $('#legendRest').textContent = String(rest);
}

function eventTime(event) {
  return (event.timestamps && (event.timestamps.created_at || event.timestamps.updated_at)) || '';
}

function eventMetrics(event) {
  return event.metrics || {};
}

function renderRecentEvents() {
  const body = $('#recentEventsBody');
  const list = state.events.slice(0, 8);
  if (!list.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty">暂无事件。提交一个任务后会出现在这里。</td></tr>';
    return;
  }
  body.innerHTML = list.map(event => `
    <tr>
      <td class="mono">${escapeHtml(formatTime(eventTime(event)))}</td>
      <td class="mono">${escapeHtml(event.task_id || '—')}</td>
      <td>${statusBadge(event.status)}</td>
      <td class="mono">${escapeHtml(formatDuration(eventMetrics(event).duration_ms))}</td>
      <td class="mono">${event.error_code ? `<code>${escapeHtml(event.error_code)}</code>` : '—'}</td>
    </tr>`).join('');
}

function filteredEvents() {
  const filter = state.eventFilter;
  const keyword = filter.taskId.trim().toLowerCase();
  let list = state.events;
  if (keyword) {
    list = list.filter(event => String(event.task_id || '').toLowerCase().includes(keyword));
  }
  if (filter.status) {
    list = list.filter(event => event.status === filter.status);
  }
  return list.slice(0, filter.limit);
}

function renderEvents() {
  const body = $('#eventsBody');
  const list = filteredEvents();
  $('#eventCount').textContent = `${list.length} 条`;
  if (!list.length) {
    body.innerHTML = '<tr><td colspan="9" class="empty">没有符合条件的事件。</td></tr>';
    return;
  }
  body.innerHTML = list.map(event => {
    const metrics = eventMetrics(event);
    const vision = metrics.vision_verified;
    return `
      <tr>
        <td class="mono">${escapeHtml(formatTime(eventTime(event)))}</td>
        <td class="mono">${escapeHtml(event.task_id || '—')}</td>
        <td>${statusBadge(event.status)}</td>
        <td class="mono">${escapeHtml(event.arm_id || '—')}</td>
        <td>${escapeHtml(classLabel(event.class_id))}</td>
        <td class="mono">${escapeHtml(formatDuration(metrics.duration_ms))}</td>
        <td class="mono">${escapeHtml(metrics.retry_count ?? '—')}</td>
        <td>${vision === true ? '通过' : vision === false ? '未通过' : '—'}</td>
        <td class="mono">${event.error_code ? `<code>${escapeHtml(event.error_code)}</code>` : '—'}</td>
      </tr>`;
  }).join('');
}

function exceptionTypeOf(event) {
  if (event.error_code) {
    return { code: event.error_code, label: ERROR_LABELS[event.error_code] || event.error_code };
  }
  if (['REJECTED', 'FAILED', 'SAFE_MODE'].includes(event.status)) {
    return {
      code: `STATUS_${event.status}`,
      label: event.status === 'REJECTED' ? '任务被安全门禁拒绝'
        : event.status === 'FAILED' ? '任务执行失败'
          : '系统进入安全模式',
    };
  }
  return null;
}

function exceptionRows() {
  return state.events
    .map(event => {
      const type = exceptionTypeOf(event);
      if (!type) return null;
      return {
        time: eventTime(event),
        taskId: event.task_id || '—',
        type: type.code,
        typeLabel: type.label,
        status: event.status,
        result: STATUS_LABELS[event.status] || event.status || '—',
      };
    })
    .filter(Boolean);
}

function filteredExceptions() {
  const filter = state.exceptionFilter;
  const keyword = filter.keyword.trim().toLowerCase();
  let list = exceptionRows();
  if (keyword) {
    list = list.filter(row => row.taskId.toLowerCase().includes(keyword) || row.type.toLowerCase().includes(keyword));
  }
  if (filter.type) {
    list = list.filter(row => row.type === filter.type);
  }
  return list.slice(0, filter.limit);
}

function renderExceptions() {
  const rows = filteredExceptions();
  const all = exceptionRows();
  const taskCount = new Set(all.map(row => row.taskId)).size;
  const latest = all.length ? all[0].time : '';
  $('#exceptionCards').innerHTML = [
    renderCard({ label: '异常记录', value: String(all.length), hint: '最近 100 条事件中的异常', tone: all.length ? 'tone-danger' : 'tone-success' }),
    renderCard({ label: '涉及任务', value: String(taskCount), hint: '去重后的任务编号数', tone: 'tone-warn' }),
    renderCard({ label: '最近异常', value: latest ? escapeHtml(formatClock(latest)) : '无', hint: latest ? formatTime(latest) : '当前无异常记录', tone: 'tone-purple', small: true }),
  ].join('');
  $('#exceptionCount').textContent = `${rows.length} 条`;
  const body = $('#exceptionBody');
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty">暂无异常记录。</td></tr>';
    return;
  }
  body.innerHTML = rows.map(row => `
    <tr>
      <td class="mono">${escapeHtml(formatTime(row.time))}</td>
      <td class="mono">${escapeHtml(row.taskId)}</td>
      <td class="mono"><code>${escapeHtml(row.type)}</code></td>
      <td>${statusBadge(row.status)}</td>
      <td>${escapeHtml(row.typeLabel)}</td>
      <td>${escapeHtml(row.result)}</td>
    </tr>`).join('');
}

function renderStatistics() {
  const stats = state.stats;
  const cards = $('#statisticsCards');
  if (!stats) {
    cards.innerHTML = '';
    $('#statisticsRange').textContent = '—';
    $('#statisticsBars').innerHTML = '<p class="empty">加载中…</p>';
    $('#classTableBody').innerHTML = '<tr><td colspan="3" class="empty">加载中…</td></tr>';
    return;
  }
  const rate = computeRate(stats.total_tasks, stats.success_count);
  const failureRate = computeRate(stats.total_tasks, stats.failure_count);
  cards.innerHTML = [
    renderCard({ label: '任务总数', value: String(stats.total_tasks), hint: '统计区间内全部任务' }),
    renderCard({ label: '成功率', value: `${rate}%`, hint: `${stats.success_count} / ${stats.total_tasks}`, tone: 'tone-success' }),
    renderCard({ label: '失败率', value: `${failureRate}%`, hint: `${stats.failure_count} / ${stats.total_tasks}`, tone: 'tone-danger' }),
    renderCard({ label: '识别类别数', value: String(Object.keys(stats.by_class || {}).length), hint: '来自 detection_event', tone: 'tone-purple' }),
  ].join('');
  $('#statisticsRange').textContent = `${formatTime(stats.from)} → ${formatTime(stats.to)}`;
  renderClassBars($('#statisticsBars'), stats.by_class || {});

  const entries = Object.entries(stats.by_class || {}).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  const body = $('#classTableBody');
  if (!entries.length) {
    body.innerHTML = '<tr><td colspan="3" class="empty">暂无识别数据。</td></tr>';
    return;
  }
  body.innerHTML = entries.map(([classId, count]) => `
    <tr>
      <td>${escapeHtml(classLabel(classId))} <span class="mono">${escapeHtml(classId)}</span></td>
      <td class="mono">${count}</td>
      <td class="mono">${total ? ((count / total) * 100).toFixed(1) : '0.0'}%</td>
    </tr>`).join('');
}

function renderTaskResult() {
  const container = $('#taskResult');
  const task = state.queryTask;
  if (!task) {
    container.innerHTML = '<p class="empty">尚未查询任务。</p>';
    return;
  }
  container.innerHTML = `
    <div class="result-head">
      <strong>${escapeHtml(task.task_id || '—')}</strong>
      ${statusBadge(task.status)}
    </div>
    <div class="result-grid">
      <div class="result-item"><span>视觉复核</span><b>${task.vision_verified ? '通过' : '未通过'}</b></div>
      <div class="result-item"><span>重试次数</span><b>${escapeHtml(task.retry_count ?? '—')}</b></div>
      <div class="result-item"><span>耗时</span><b>${escapeHtml(formatDuration(task.duration_ms))}</b></div>
      <div class="result-item"><span>错误码</span><b>${escapeHtml(task.error_code || '无')}</b></div>
    </div>
    <pre class="result-json">servo_state = ${escapeHtml(JSON.stringify(task.servo_state ?? {}, null, 2))}</pre>`;
}

function renderAll() {
  renderConnection();
  renderHealth();
  renderStats();
  renderRecentEvents();
  renderEvents();
  renderExceptions();
  renderStatistics();
  renderTaskResult();
}

/* ------------------------------ 提示 ------------------------------ */
function toast(message, type = 'info') {
  const stack = $('#toastStack');
  const item = document.createElement('div');
  item.className = `toast ${type}`;
  item.innerHTML = `<span class="toast-dot"></span><span>${escapeHtml(message)}</span>`;
  stack.appendChild(item);
  setTimeout(() => {
    item.style.opacity = '0';
    item.style.transform = 'translateY(6px)';
    item.style.transition = 'opacity .2s ease, transform .2s ease';
    setTimeout(() => item.remove(), 220);
  }, 4200);
}

function setFormMessage(element, message, type = '') {
  element.textContent = message;
  element.className = `form-msg${type ? ` ${type}` : ''}`;
}

/* ------------------------------ 刷新循环 ------------------------------ */
async function refresh(manual = false) {
  if (state.inFlight) return;
  state.inFlight = true;
  try {
    const [health, stats, events] = await Promise.all([
      api.getHealth(),
      api.getSummary(),
      api.listEvents(MAX_EVENTS),
    ]);
    state.health = health;
    state.stats = stats;
    state.events = Array.isArray(events) ? events : [];
    state.online = true;
    $('#updatedAt').textContent = `更新于 ${formatClock(new Date().toISOString())}`;
    renderAll();
  } catch (error) {
    state.online = false;
    renderConnection();
    if (manual) toast(error.message || '刷新失败', 'error');
  } finally {
    state.inFlight = false;
  }
}

function startPolling() {
  setInterval(() => {
    if (!state.autoRefresh || document.hidden) return;
    refresh(false);
  }, POLL_INTERVAL);
}

/* ------------------------------ 视图切换 ------------------------------ */
function switchView(view) {
  if (!VIEW_META[view]) return;
  state.view = view;
  $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.view === view));
  $$('.view').forEach(panel => panel.classList.toggle('active', panel.id === `view-${view}`));
  $('#pageTitle').textContent = VIEW_META[view].title;
  $('#pageSubtitle').textContent = VIEW_META[view].subtitle;
}

/* ------------------------------ 交互绑定 ------------------------------ */
function bindNavigation() {
  $$('.nav-item').forEach(item => {
    item.addEventListener('click', () => switchView(item.dataset.view));
  });
  $$('[data-goto]').forEach(item => {
    item.addEventListener('click', () => switchView(item.dataset.goto));
  });
}

function bindRefresh() {
  $('#refreshBtn').addEventListener('click', () => refresh(true));
  $('#autoRefresh').addEventListener('change', event => {
    state.autoRefresh = event.target.checked;
    if (state.autoRefresh) refresh(false);
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refresh(false);
  });
}

function bindEventFilters() {
  const taskInput = $('#eventTaskId');
  const statusSelect = $('#eventStatus');
  const limitSelect = $('#eventLimit');
  $('#eventApply').addEventListener('click', () => {
    state.eventFilter = {
      taskId: taskInput.value,
      status: statusSelect.value,
      limit: Number(limitSelect.value) || 20,
    };
    renderEvents();
  });
  $('#eventReset').addEventListener('click', () => {
    taskInput.value = '';
    statusSelect.value = '';
    limitSelect.value = '20';
    state.eventFilter = { taskId: '', status: '', limit: 20 };
    renderEvents();
  });
  [taskInput, statusSelect, limitSelect].forEach(control => {
    control.addEventListener('keydown', event => {
      if (event.key === 'Enter') $('#eventApply').click();
    });
  });
}

function bindExceptionFilters() {
  const keywordInput = $('#exceptionKeyword');
  const typeSelect = $('#exceptionType');
  const limitSelect = $('#exceptionLimit');
  $('#exceptionApply').addEventListener('click', () => {
    state.exceptionFilter = {
      keyword: keywordInput.value,
      type: typeSelect.value,
      limit: Number(limitSelect.value) || 50,
    };
    renderExceptions();
  });
  $('#exceptionReset').addEventListener('click', () => {
    keywordInput.value = '';
    typeSelect.value = '';
    limitSelect.value = '50';
    state.exceptionFilter = { keyword: '', type: '', limit: 50 };
    renderExceptions();
  });
  keywordInput.addEventListener('keydown', event => {
    if (event.key === 'Enter') $('#exceptionApply').click();
  });
}

function bindCreateTask() {
  const form = $('#createTaskForm');
  const taskIdInput = $('#createTaskId');
  const message = $('#createTaskMsg');
  const button = $('#createTaskBtn');

  const nextTaskId = () => `task-${Date.now()}`;
  taskIdInput.value = nextTaskId();
  $('#randomTaskBtn').addEventListener('click', () => {
    taskIdInput.value = nextTaskId();
    setFormMessage(message, '');
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const data = new FormData(form);
    const taskId = String(data.get('task_id') || '').trim();
    const calibrationId = String(data.get('calibration_id') || '').trim();
    const numbers = ['x_mm', 'y_mm', 'z_mm', 'timeout_ms'].map(key => Number(data.get(key)));
    if (!taskId) {
      setFormMessage(message, '请填写任务编号。', 'error');
      return;
    }
    if (!calibrationId) {
      setFormMessage(message, '请填写标定编号。', 'error');
      return;
    }
    if (numbers.some(value => !Number.isFinite(value))) {
      setFormMessage(message, '坐标与超时时间必须是有效数字。', 'error');
      return;
    }
    const payload = {
      task_id: taskId,
      arm_id: data.get('arm_id'),
      target_pose: {
        task_id: taskId,
        x_mm: numbers[0],
        y_mm: numbers[1],
        z_mm: numbers[2],
        calibration_id: calibrationId,
        workspace_ok: data.get('workspace_ok') === 'on',
      },
      bin_id: data.get('bin_id'),
      timeout_ms: numbers[3],
    };

    button.disabled = true;
    setFormMessage(message, '提交中…');
    try {
      const result = await api.createTask(payload);
      const duplicated = Boolean(result && result.idempotent);
      setFormMessage(message, duplicated ? '任务已存在，返回已有任务状态。' : '任务已受理。', 'ok');
      toast(duplicated ? `任务 ${taskId} 已存在，返回已有状态` : `任务 ${taskId} 已受理`, duplicated ? 'info' : 'success');
      $('#queryTaskId').value = taskId;
      taskIdInput.value = nextTaskId();
      await refresh(false);
    } catch (error) {
      const detail = error.code ? `${error.code}：${error.message}` : error.message;
      setFormMessage(message, detail || '提交失败', 'error');
      toast(detail || '提交失败', 'error');
      await refresh(false);
    } finally {
      button.disabled = false;
    }
  });
}

function bindSafety() {
  const form = $('#safetyForm');
  const message = $('#safetyMsg');
  const button = $('#safetyBtn');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const reason = String(new FormData(form).get('reason') || '').trim();
    if (!reason) {
      setFormMessage(message, '请填写停止原因。', 'error');
      return;
    }
    button.disabled = true;
    setFormMessage(message, '下发中…');
    try {
      const result = await api.safetyStop(reason);
      setFormMessage(message, `已进入 ${result.status}（${formatTime(result.requested_at)}）`, 'ok');
      toast('软件安全停止已下发，系统进入 SAFE_MODE', 'success');
      await refresh(false);
    } catch (error) {
      const detail = error.code ? `${error.code}：${error.message}` : error.message;
      setFormMessage(message, detail || '下发失败', 'error');
      toast(detail || '下发失败', 'error');
    } finally {
      button.disabled = false;
    }
  });
}

function bindTaskQuery() {
  const input = $('#queryTaskId');
  const button = $('#queryTaskBtn');
  const lookup = async () => {
    const taskId = input.value.trim();
    if (!taskId) {
      toast('请输入任务编号', 'error');
      return;
    }
    button.disabled = true;
    try {
      const task = await api.getTask(taskId);
      state.queryTask = task;
      renderTaskResult();
    } catch (error) {
      state.queryTask = null;
      renderTaskResult();
      toast(error.code ? `${error.code}：${error.message}` : error.message, 'error');
    } finally {
      button.disabled = false;
    }
  };
  button.addEventListener('click', lookup);
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter') lookup();
  });
}

function init() {
  $('#apiBaseLabel').textContent = API_BASE;
  bindNavigation();
  bindRefresh();
  bindEventFilters();
  bindExceptionFilters();
  bindCreateTask();
  bindSafety();
  bindTaskQuery();
  renderAll();
  refresh(true);
  startPolling();
}

init();
