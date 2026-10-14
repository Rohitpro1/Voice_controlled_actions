'use strict';

// Frontend API contract: a separate local backend must implement these routes.
// Until then, controls remain disabled and the UI reports the real unavailable state.
const API_BASE = `${window.location.origin}/api`;
const $ = (selector) => document.querySelector(selector);
const elements = {
  sidebarStatus: $('#sidebar-status'), sidebarDot: $('#sidebar-dot'),
  connectionTitle: $('#connection-title'), connectionDetail: $('#connection-detail'),
  connectionPill: $('#connection-pill'), refresh: $('#refresh-button'),
  lightButton: $('#light-button'), lightState: $('#light-state'), lightIndicator: $('#light-indicator'),
  voiceStart: $('#voice-start'), voiceStop: $('#voice-stop'),
  voiceStatus: $('#voice-status'), voiceCommand: $('#voice-command'), micDot: $('#mic-dot'), form: $('#notification-form'),
  sendNotification: $('#send-notification'), activity: $('#activity-list'),
  notificationHistory: $('#notification-history'), notificationCount: $('#notification-count'), toast: $('#toast')
};
let backendAvailable = false;
let flashlightOn = false;
let busy = false;
let toastTimer;

function log(message, type = 'info', detail = '') {
  const item = document.createElement('li');
  item.className = 'activity-item';
  const marker = document.createElement('span');
  marker.className = `activity-marker ${type}`;
  const content = document.createElement('div');
  const title = document.createElement('strong');
  title.textContent = message;
  const sub = document.createElement('small');
  sub.textContent = detail || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const time = document.createElement('time');
  time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  content.append(title, sub);
  item.append(marker, content, time);
  elements.activity.prepend(item);
  while (elements.activity.children.length > 30) elements.activity.lastElementChild.remove();
}

function toast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => elements.toast.classList.remove('show'), 3500);
}

function setBackendState(available, status = {}) {
  backendAvailable = available;
  const phone = status.phone_connected === true;
  const connecting = status.phone_status === 'connecting';
  const title = available
    ? (phone ? 'Phone connected' : connecting ? 'Connecting to phone' : 'Phone disconnected')
    : 'Backend unavailable';
  const detail = available
    ? (status.message || (phone ? 'Your phone is ready for controls.' : 'Start the local Python service to connect your phone.'))
    : 'Could not reach the local API at 127.0.0.1:8000. Phone controls are disabled.';
  elements.connectionTitle.textContent = title;
  elements.connectionDetail.textContent = detail;
  elements.sidebarStatus.textContent = available ? (phone ? 'Phone connected' : 'Backend running') : 'Backend unavailable';
  elements.connectionPill.querySelector('span').textContent = available ? (phone ? 'Connected' : connecting ? 'Connecting' : 'Disconnected') : 'Offline';
  const dot = elements.connectionPill.querySelector('.status-dot');
  dot.className = `status-dot ${phone ? 'connected' : available ? '' : 'error'}`;
  elements.sidebarDot.className = `status-dot ${phone ? 'connected' : available ? '' : 'error'}`;
  const enabled = available && phone && !busy;
  [elements.lightButton, elements.voiceStart, elements.sendNotification].forEach((button) => { button.disabled = !enabled; });
  elements.voiceStop.disabled = !available || !status.voice_listening || busy;
  if (typeof status.flashlight_on === 'boolean') setFlashlight(status.flashlight_on);
  if (status.voice_listening) {
    elements.voiceStatus.textContent = 'Listening';
    elements.micDot.classList.add('listening');
  } else {
    elements.voiceStatus.textContent = 'Not listening';
    elements.micDot.classList.remove('listening');
  }
  elements.voiceCommand.textContent = `Last heard: ${status.last_command || '—'}`;
}

function setFlashlight(on) {
  flashlightOn = on;
  elements.lightState.textContent = on ? 'On' : 'Off';
  elements.lightIndicator.classList.toggle('on', on);
  elements.lightButton.textContent = on ? 'Turn off' : 'Turn on';
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    signal: AbortSignal.timeout(5000)
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || body.message || `Request failed (${response.status})`);
  return body;
}

async function refreshStatus() {
  elements.refresh.disabled = true;
  try {
    const data = await request('/status');
    setBackendState(data.backend_running !== false, data);
    await refreshActivity();
    await refreshNotifications();
  } catch (error) {
    setBackendState(false);
    log('Backend unavailable', 'error', error.message);
  } finally {
    elements.refresh.disabled = false;
  }
}

async function refreshActivity() {
  try {
    const { logs = [] } = await request('/logs');
    if (!logs.length) return;
    elements.activity.replaceChildren();
    for (const entry of logs.slice().reverse()) {
      const item = document.createElement('li');
      item.className = 'activity-item';
      const marker = document.createElement('span');
      marker.className = `activity-marker ${entry.level || 'info'}`;
      const content = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = entry.message || 'Backend event';
      const sub = document.createElement('small');
      sub.textContent = entry.detail || '';
      const time = document.createElement('time');
      time.textContent = entry.time || '';
      content.append(title, sub);
      item.append(marker, content, time);
      elements.activity.append(item);
    }
  } catch (_) {
    // Status already reports API availability; the activity list can retry next poll.
  }
}

async function refreshNotifications() {
  try {
    const { notifications = [] } = await request('/notifications');
    elements.notificationCount.textContent = `${notifications.length} notification${notifications.length === 1 ? '' : 's'}`;
    elements.notificationHistory.replaceChildren();
    if (!notifications.length) {
      const empty = document.createElement('li');
      empty.className = 'history-empty';
      empty.textContent = 'Sent notifications will appear here.';
      elements.notificationHistory.append(empty);
      return;
    }
    for (const notification of notifications.slice().reverse()) {
      const item = document.createElement('li');
      item.className = 'history-item';
      const top = document.createElement('div');
      top.className = 'history-item-top';
      const title = document.createElement('strong');
      title.textContent = notification.title;
      const meta = document.createElement('span');
      meta.textContent = `${notification.time} · ${notification.source}`;
      const message = document.createElement('p');
      message.textContent = notification.message;
      top.append(title, meta);
      item.append(top, message);
      elements.notificationHistory.append(item);
    }
  } catch (_) {
    // Retry notification history on the next refresh.
  }
}

async function runAction(path, body, successText) {
  if (!backendAvailable || busy) return;
  busy = true;
  setBackendState(true, { phone_connected: true });
  try {
    const data = await request(path, { method: 'POST', body: JSON.stringify(body) });
    if (path === '/flashlight' && typeof body.on === 'boolean') setFlashlight(body.on);
    log(data.message || successText, 'success');
    toast(data.message || successText);
    await refreshStatus();
  } catch (error) {
    log('Command failed', 'error', error.message);
    toast(`Command failed: ${error.message}`);
    await refreshStatus();
  } finally {
    busy = false;
    await refreshStatus();
  }
}

elements.refresh.addEventListener('click', refreshStatus);
$('#settings-refresh').addEventListener('click', refreshStatus);
$('#reconnect-button').addEventListener('click', async () => {
  const button = $('#reconnect-button');
  button.disabled = true;
  try {
    const data = await request('/reconnect', { method: 'POST', body: '{}' });
    toast(data.message || 'Phone connected');
    log(data.message || 'Phone connected', 'success');
  } catch (error) {
    toast(`Reconnect failed: ${error.message}`);
    log('Phone reconnect failed', 'error', error.message);
  } finally {
    button.disabled = false;
    await refreshStatus();
  }
});
elements.lightButton.addEventListener('click', () => runAction('/flashlight', { on: !flashlightOn }, `Flashlight turned ${flashlightOn ? 'off' : 'on'}`));
elements.voiceStart.addEventListener('click', () => runAction('/voice/start', {}, 'Voice control started'));
elements.voiceStop.addEventListener('click', () => runAction('/voice/stop', {}, 'Voice control stopped'));
elements.form.addEventListener('submit', (event) => {
  event.preventDefault();
  const title = $('#notification-title').value.trim();
  const message = $('#notification-message').value.trim();
  if (!title || !message) return toast('Enter both a title and message.');
  runAction('/notification', { title, message }, 'Notification sent');
});
$('#clear-activity').addEventListener('click', () => {
  elements.activity.replaceChildren();
  log('Activity cleared');
});

refreshStatus();
setInterval(async () => {
  try {
    const data = await request('/status');
    setBackendState(data.backend_running !== false, data);
    await refreshActivity();
    await refreshNotifications();
  } catch (_) {
    setBackendState(false);
  }
}, 4000);
