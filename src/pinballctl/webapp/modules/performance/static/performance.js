(() => {
  const root = document.getElementById('performance-root');
  if (!root) return;

  const status = document.getElementById('performance-status');
  const detail = document.getElementById('performance-status-detail');
  const lastEsp = document.getElementById('performance-last-esp');
  const heartbeats = document.getElementById('performance-heartbeats');
  const live = document.getElementById('performance-live');
  const range = document.getElementById('performance-range');
  const overload = document.getElementById('performance-overload');
  const reset = document.getElementById('performance-reset');
  const counters = document.getElementById('performance-counters');
  const canvas = document.getElementById('performance-plot');
  const plot = canvas.parentElement;
  const chartEmpty = document.getElementById('performance-chart-empty');
  const legend = document.getElementById('performance-chart-legend');
  const chartButtons = root.querySelectorAll('[data-chart]');
  const metricFields = root.querySelectorAll('[data-metric]');
  const sessionFields = root.querySelectorAll('[data-session-total]');
  const charts = {
    rates: {
      keys: ['rx_rate', 'completed_rate', 'confirmed_rate'],
      label: 'Event throughput',
      legend: 'Blue: received · Green: host processed · Amber: ESP confirmations',
      empty: 'Waiting for an event rate sample.',
    },
    queue: {
      keys: ['queued', 'worker_pending', 'awaiting'],
      label: 'Event backlog',
      legend: 'Blue: waiting to send · Green: host work · Amber: awaiting ESP',
      empty: 'Waiting for a backlog sample.',
    },
    latency: {
      keys: ['latency_p95_ms', 'delivery_p95_ms', 'host_p95_ms'],
      label: 'Event latency',
      legend: 'Blue: serial round trip · Green: delivery including queue · Amber: host completion',
      empty: 'Latency appears after an event is processed or confirmed.',
    },
  };
  let data = null;
  let chartKey = 'rates';
  let busy = false;

  const clock = timestamp => new Date(timestamp * 1000).toLocaleTimeString();

  function renderChart() {
    const chart = charts[chartKey];
    const {width, height} = canvas.getBoundingClientRect();
    const scale = window.devicePixelRatio || 1;
    canvas.width = width * scale;
    canvas.height = height * scale;
    canvas.setAttribute('aria-label', chart.label + ' over time');
    legend.textContent = chart.legend;
    const ctx = canvas.getContext('2d');
    ctx.scale(scale, scale);
    const left = 46;
    const right = width - 12;
    const top = 10;
    const bottom = height - 23;
    const rows = data?.history || [];
    const end = rows.at(-1)?.at || Date.now() / 1000;
    const start = end - Number(range.value);
    const visible = rows.filter(row => row.at >= start);
    const values = visible.flatMap(row => chart.keys.map(key => row[key])).filter(Number.isFinite);
    chartEmpty.hidden = values.length > 0;
    chartEmpty.textContent = rows.length ? chart.empty : 'Waiting for a Bridge sample.';
    if (!values.length) return;

    const max = Math.max(1, ...values);
    const colors = getComputedStyle(root);
    ctx.font = '11px system-ui';
    ctx.fillStyle = colors.getPropertyValue('--bs-secondary-color').trim() || '#94a3b8';
    ctx.strokeStyle = colors.getPropertyValue('--bs-border-color').trim() || '#334155';
    for (let i = 0; i <= 3; i++) {
      const y = bottom - (bottom - top) * i / 3;
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(right, y);
      ctx.stroke();
      ctx.fillText((max * i / 3).toFixed(1), 2, y + 4);
    }
    ctx.fillText(`−${range.value}s`, left, height - 5);
    ctx.fillText('Latest', right - 33, height - 5);

    chart.keys.forEach((key, index) => {
      ctx.strokeStyle = ['#60a5fa', '#34d399', '#fbbf24'][index];
      ctx.lineWidth = 2;
      ctx.beginPath();
      let previous = null;
      for (const row of visible) {
        const value = row[key];
        if (!Number.isFinite(value)) {
          previous = null;
          continue;
        }
        const x = left + (row.at - start) / (end - start) * (right - left);
        const y = bottom - value / max * (bottom - top);
        if (previous === null || row.at - previous > 3) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        previous = row.at;
      }
      ctx.stroke();
    });
  }

  function renderMetrics() {
    const latest = data?.latest;
    for (const field of metricFields) {
      const key = field.dataset.metric;
      const value = latest?.[key];
      field.textContent = Number.isFinite(value)
        ? value.toFixed(key.includes('rate') || key.includes('ms') ? 1 : 0)
        : '—';
    }
    for (const field of sessionFields) {
      const value = latest?.[field.dataset.sessionTotal];
      field.hidden = !Number.isFinite(value);
      if (!field.hidden) field.textContent = value.toLocaleString() + ' this session';
    }
    if (Number.isFinite(data?.last_esp_message_at) && data.last_esp_message_at > 0) {
      lastEsp.textContent = clock(data.last_esp_message_at);
    } else {
      lastEsp.textContent = '—';
    }
    heartbeats.textContent = Number.isFinite(data?.heartbeats) ? String(data.heartbeats) : '—';
    heartbeats.title = data?.last_heartbeat_at ? 'Last heartbeat at ' + clock(data.last_heartbeat_at) : '';
    renderChart();
  }

  function showStatus(title, message, tone = '') {
    status.textContent = title;
    status.className = 'fw-semibold' + (tone ? ' text-' + tone + '-emphasis' : '');
    detail.textContent = message;
  }

  function renderStatus() {
    const latest = data.latest;
    if (data.stale) {
      showStatus('Bridge sample delayed', 'Showing the last sample. Retrying automatically.', 'warning');
    } else if (!data.connected) {
      showStatus('Bridge running · Waiting for ESP', 'The Bridge is responding. No recent ESP traffic.');
    } else if (!latest || latest.rx_rate === null) {
      showStatus('ESP connected · Sampling', 'Waiting for enough data to calculate rates.', 'success');
    } else if (data.overload) {
      showStatus('ESP connected · Overload', 'Activations stopped. Inspect backlog and counters.', 'danger');
    } else if (latest.rx_rate === 0 && latest.completed_rate === 0 && !latest.worker_pending) {
      showStatus('ESP connected · Gameplay idle', 'Heartbeat and link traffic are shown separately from gameplay.', 'success');
    } else {
      showStatus('ESP connected · Events flowing', 'Latest sample at ' + clock(latest.at), 'success');
    }
  }

  function mergeHistory(next) {
    const previous = data?.history || [];
    const lastAt = previous.at(-1)?.at;
    if (!lastAt || next.session !== data.session || next.latest?.at < lastAt) return next;
    next.history = previous.concat((next.history || []).filter(row => row.at > lastAt)).slice(-300);
    return next;
  }

  async function refresh() {
    if (busy || !live.checked || document.hidden) return;
    busy = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2500);
    try {
      const lastAt = data?.history?.at(-1)?.at;
      const query = Number.isFinite(lastAt) ? '?after=' + encodeURIComponent(lastAt) : '';
      const response = await fetch('/api/performance/status' + query, {
        cache: 'no-store', signal: controller.signal,
      });
      if (response.status === 401) {
        showStatus('Sign in to view live metrics', 'The current browser session has expired.', 'warning');
        return;
      }
      const next = await response.json();
      if (!response.ok || !next.ok) {
        showStatus('Waiting for Bridge', data?.latest
          ? 'Showing the last sample. Retrying automatically.'
          : 'Start the Bridge to see live metrics. Retrying automatically.', 'warning');
        return;
      }
      data = mergeHistory(next);
      overload.hidden = !data.overload;
      reset.disabled = !data.disabled_confirmed;
      renderMetrics();
      renderStatus();
    } catch {
      showStatus(controller.signal.aborted ? 'Bridge status timed out' : 'Could not reach the Performance API',
        data?.latest ? 'Showing the last sample. Retrying automatically.' : 'Retrying automatically.', 'warning');
    } finally {
      clearTimeout(timeout);
      busy = false;
    }
  }

  reset.addEventListener('click', async () => {
    reset.disabled = true;
    try {
      const response = await fetch('/api/performance/reset-overload', {
        method: 'POST', signal: AbortSignal.timeout(2500),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Reset failed');
      showStatus('Safe recovery requested', 'Waiting for cooldown and ESP confirmation.');
      refresh();
    } catch (error) {
      const message = error.name === 'TimeoutError' || error.name === 'AbortError'
        ? 'The Bridge did not respond in time.' : error.message;
      showStatus('Could not request recovery', message, 'warning');
      reset.disabled = false;
    }
  });

  for (const button of chartButtons) {
    button.addEventListener('click', () => {
      chartKey = button.dataset.chart;
      for (const option of chartButtons) {
        const selected = option === button;
        option.classList.toggle('active', selected);
        option.setAttribute('aria-pressed', String(selected));
      }
      renderChart();
    });
  }
  document.getElementById('performance-open-counters').addEventListener('click', () => counters.showModal());
  range.addEventListener('change', renderChart);
  live.addEventListener('change', () => {
    if (live.checked) refresh();
    else showStatus('Live updates paused', 'Showing the last sample.');
  });
  new ResizeObserver(renderChart).observe(plot);
  document.addEventListener('visibilitychange', refresh);
  setInterval(refresh, 1000);
  renderChart();
  refresh();
})();
