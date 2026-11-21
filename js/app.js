(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const API = window.API_BASE || '';
  const RACE_DATE = new Date('2027-09-26T07:00:00-05:00');
  const state = { k: '10K', p: 60, q: 1, pay: 'yape', step: 1 };
  const money = n => 'S/ ' + n.toFixed(2);

  // Countdown
  const pad = n => String(n).padStart(2, '0');
  function tick() {
    let d = Math.max(0, RACE_DATE - new Date()) / 1000;
    $('#cd-d').textContent = pad(Math.floor(d / 86400));
    $('#cd-h').textContent = pad(Math.floor(d % 86400 / 3600));
    $('#cd-m').textContent = pad(Math.floor(d % 3600 / 60));
    $('#cd-s').textContent = pad(Math.floor(d % 60));
  }
  tick(); setInterval(tick, 1000);

  // Map tooltips
  $$('.pt').forEach(g => {
    const show = () => $('#tip').textContent = g.dataset.t;
    g.addEventListener('mouseenter', show); g.addEventListener('click', show);
  });

  // Modal
  const overlay = $('#overlay');
  const open = () => { overlay.classList.add('open'); document.body.classList.add('lock'); goto(1); };
  const close = () => { overlay.classList.remove('open'); document.body.classList.remove('lock'); };
  $$('.js-open').forEach(b => b.addEventListener('click', open));
  $('#closeBtn').onclick = close; $('#finish').onclick = close;
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });

  function goto(n) {
    state.step = n;
    $$('.step').forEach((s, i) => s.classList.toggle('active', i === n - 1));
    $$('#steps div').forEach((d, i) => {
      d.classList.toggle('active', i === n - 1);
      d.classList.toggle('done', i < n - 1 || n === 4);
    });
    if (n === 3) {
      const t = money(state.p * state.q);
      $('#sum').textContent = `${state.k} × ${state.q}`;
      $('#sumTotal').textContent = t; $('#yTotal').textContent = t;
    }
    $('.modal').scrollTop = 0;
  }

  // Step 1
  function calc() { $('#qv').textContent = state.q; $('#total').textContent = money(state.p * state.q); }
  $$('.ticket').forEach(t => t.onclick = () => {
    $$('.ticket').forEach(x => x.classList.remove('sel')); t.classList.add('sel');
    state.k = t.dataset.k; state.p = +t.dataset.p; calc();
  });
  $('#qm').onclick = () => { state.q = Math.max(1, state.q - 1); calc(); };
  $('#qp').onclick = () => { state.q = Math.min(5, state.q + 1); calc(); };
  $('#to2').onclick = () => goto(2);
  $('#b1').onclick = () => goto(1);
  $('#b2').onclick = () => goto(2);

  // Step 2 validation
  const form = $('#form');
  const rules = {
    nombres: v => v.trim().length >= 2,
    apellidos: v => v.trim().length >= 2,
    dni: v => /^\d{8}$/.test(v),
    edad: v => +v >= 14 && +v <= 90,
    genero: v => !!v, talla: v => !!v, sangre: v => !!v,
    ciudad: v => v.trim().length >= 3,
    email: v => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v),
    telefono: v => /^\+?\d{9,12}$/.test(v.replace(/[\s-]/g, '')),
    emergencia: v => v.trim().length >= 6,
  };
  function validate() {
    let ok = true;
    for (const [n, fn] of Object.entries(rules)) {
      const el = form.elements[n]; const good = fn(el.value);
      el.closest('.f').classList.toggle('err', !good); if (!good) ok = false;
    }
    return ok;
  }
  form.elements.dni.addEventListener('input', e => e.target.value = e.target.value.replace(/\D/g, '').slice(0, 8));
  $('#to3').onclick = () => { if (validate()) goto(3); else $('.err input,.err select')?.focus(); };

  // Step 3
  $$('.pay-tab').forEach(t => t.onclick = () => {
    $$('.pay-tab').forEach(x => x.classList.remove('sel')); t.classList.add('sel');
    state.pay = t.dataset.p;
    $$('.pay-panel').forEach(p => p.classList.toggle('active', p.id === 'p-' + state.pay));
  });
  const payload = () => ({
    ...Object.fromEntries(new FormData(form)),
    distancia: state.k, cupos: state.q, precio_unitario: state.p, metodo_pago: state.pay,
  });
  const err = m => $('#payErr').textContent = m || '';

  async function createReg() {
    const r = await fetch(API + '/api/registrations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload()) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || 'No se pudo registrar');
    return j;
  }
  function finish(code, status) {
    $('#regCode').textContent = code; $('#regState').textContent = status; goto(4);
  }

  $('#payYape').onclick = async () => {
    err(''); const f = $('#voucher').files[0];
    const bad = !f || f.size > 5 * 1024 * 1024;
    $('#voucher').closest('.f').classList.toggle('err', bad);
    $('#vmsg').textContent = !f ? 'Adjuntá tu comprobante' : 'Archivo mayor a 5 MB';
    if (bad) return;
    const btn = $('#payYape'); btn.disabled = true; btn.textContent = 'ENVIANDO...';
    try {
      const reg = await createReg();
      const fd = new FormData(); fd.append('voucher', f);
      const r = await fetch(`${API}/api/registrations/${reg.code}/voucher`, { method: 'POST', body: fd });
      if (!r.ok) throw new Error((await r.json()).error || 'Error subiendo comprobante');
      finish(reg.code, 'PENDIENTE DE VALIDACIÓN');
    } catch (e) { err(e.message); }
    btn.disabled = false; btn.textContent = 'ENVIAR INSCRIPCIÓN';
  };

  $('#payNiubiz').onclick = async () => {
    err(''); const btn = $('#payNiubiz'); btn.disabled = true;
    try {
      const reg = await createReg();
      const r = await fetch(API + '/api/niubiz/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: reg.code }) });
      const j = await r.json();
      if (!r.ok) {
        // Niubiz no configurado: la inscripción queda registrada como pendiente.
        err(j.error || 'Niubiz no disponible');
        finish(reg.code, 'PENDIENTE (pago con tarjeta sin configurar)'); return;
      }
      // Aquí se cargaría el checkout de Niubiz con j.sessionKey / j.merchantId
      finish(reg.code, 'PENDIENTE');
    } catch (e) { err(e.message); }
    btn.disabled = false;
  };
})();
