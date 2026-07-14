const $ = (selector) => document.querySelector(selector);
const video = $('#video');
const enrollVideo = $('#enrollVideo');
const canvas = $('#canvas');
let stream = null;
let toastTimer = null;

function showToast(message, error = false) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.className = `toast show${error ? ' error' : ''}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.className = 'toast', 4200);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'No fue posible completar la solicitud.');
  return body;
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('Este navegador no permite acceder a la cámara.');
  if (!stream) stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'user', width: {ideal: 1280}}, audio: false});
  video.srcObject = stream;
  enrollVideo.srcObject = stream;
  $('#cameraEmpty').hidden = true;
  $('#enrollEmpty').hidden = true;
  $('#cameraLabel').textContent = 'Cámara activa';
  $('#cameraButton').textContent = 'Cámara activa';
  $('#enrollCameraButton').textContent = 'Cámara activa';
  $('#recognizeButton').disabled = false;
  $('#enrollButton').disabled = false;
}

function capture(source) {
  if (!source.videoWidth) throw new Error('Espera un momento a que cargue la cámara.');
  canvas.width = source.videoWidth;
  canvas.height = source.videoHeight;
  canvas.getContext('2d').drawImage(source, 0, 0);
  return canvas.toDataURL('image/jpeg', .88);
}

async function loadStatus() {
  try {
    const data = await api('/api/status');
    $('#systemState').textContent = data.ready ? `${data.model} · listo` : 'DeepFace no instalado';
    $('.pulse').classList.toggle('ready', data.ready);
    $('#todayCount').textContent = data.present_today;
  } catch { $('#systemState').textContent = 'Servidor no disponible'; }
}

async function loadAttendance() {
  const today = new Date().toLocaleDateString('en-CA');
  try {
    const [all, todayRows] = await Promise.all([api('/api/attendance'), api(`/api/attendance?date=${today}`)]);
    $('#todayCount').textContent = todayRows.length;
    $('#latest').innerHTML = todayRows.length ? todayRows.slice(0, 4).map(row => `<div class="latest-entry"><strong>${escapeHtml(row.name)}</strong><small>${escapeHtml(row.time)}</small><small>${escapeHtml(row.student_id)}</small></div>`).join('') : '<span>Aún no hay registros hoy.</span>';
    $('#recordsBody').innerHTML = all.length ? all.map(row => `<tr><td>${escapeHtml(row.date)}</td><td>${escapeHtml(row.time)}</td><td>${escapeHtml(row.student_id)}</td><td>${escapeHtml(row.name)}</td><td>${Math.max(0, (1 - Number(row.distance)) * 100).toFixed(1)}%</td></tr>`).join('') : '<tr><td class="empty-row" colspan="5">Todavía no hay asistencias registradas.</td></tr>';
  } catch (error) { showToast(error.message, true); }
}

function escapeHtml(value) { const node = document.createElement('span'); node.textContent = value ?? ''; return node.innerHTML; }
function setBusy(button, busy, label) { button.disabled = busy; button.classList.toggle('loading', busy); if (label) button.innerHTML = busy ? 'Procesando rostro…' : label; }

document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab,.view').forEach(element => element.classList.remove('active'));
  tab.classList.add('active');
  $(`#${tab.dataset.view}`).classList.add('active');
  if (tab.dataset.view === 'records') loadAttendance();
}));

$('#cameraButton').addEventListener('click', () => startCamera().catch(error => showToast(error.message, true)));
$('#enrollCameraButton').addEventListener('click', () => startCamera().catch(error => showToast(error.message, true)));

$('#recognizeButton').addEventListener('click', async () => {
  const button = $('#recognizeButton');
  setBusy(button, true);
  try {
    const result = await api('/api/recognize', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({image: capture(video)})});
    if (!result.recognized) showToast('Rostro no reconocido. Verifica que el alumno esté registrado.', true);
    else showToast(result.already_present ? `${result.person.name} ya tenía asistencia hoy.` : `¡Presente, ${result.person.name}! Asistencia registrada.`);
    await loadAttendance();
  } catch (error) { showToast(error.message, true); }
  finally { setBusy(button, false, 'Registrar asistencia <span>→</span>'); }
});

$('#enrollForm').addEventListener('submit', async event => {
  event.preventDefault();
  const button = $('#enrollButton');
  setBusy(button, true);
  try {
    const result = await api('/api/enroll', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: $('#studentName').value, student_id: $('#studentId').value, image: capture(enrollVideo)})});
    showToast(result.updated ? `Registro de ${result.person.name} actualizado.` : `${result.person.name} quedó registrado.`);
    event.target.reset();
    await loadStatus();
  } catch (error) { showToast(error.message, true); }
  finally { setBusy(button, false, 'Guardar registro <span>→</span>'); }
});

loadStatus();
loadAttendance();
