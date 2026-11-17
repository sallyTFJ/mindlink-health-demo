(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const app = {
    token: '', apiAvailable: false, hostedDemo: false, state: null,
    voiceEnabled: false, lastSpokenKey: '', lastSpokenAt: 0,
    demoStarted: Date.now(), localCheckin: null
  };
  const reasonText = {
    eeg_input_disabled: '采集未启用', eeg_stale: '脑电已断流', no_raw_samples: '等待 RAW',
    poor_contact: '接触质量不足', poor_or_unknown_contact: '接触质量不足',
    waiting_for_contiguous_5_seconds: '积累连续 5 秒', waiting_for_wearable: '等待手表',
    waiting_for_measurement: '等待测量', stale: '数据已过期'
  };

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const toast = message => {
    $('toast').textContent = message;
    $('toast').classList.add('show');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => $('toast').classList.remove('show'), 3400);
  };
  const status = data => data?.valid ? '实时有效' : (reasonText[data?.reason] || data?.reason || '等待数据');

  async function api(path, data) {
    const response = await fetch(path, {
      method: data ? 'POST' : 'GET',
      headers: { Authorization: `Bearer ${app.token}`, ...(data ? { 'Content-Type': 'application/json' } : {}) },
      body: data ? JSON.stringify(data) : undefined,
      signal: AbortSignal.timeout(path === '/api/state' ? 1800 : 15000)
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || body.error || `HTTP ${response.status}`);
    return body;
  }

  function demoSupport(now) {
    const item = app.localCheckin;
    if (item && now - item.at < 20 * 60 * 1000) {
      const map = {
        calm: ['steady', '节律平稳，继续按自己的节奏', '现在的节律比较平稳。继续按自己的速度来，需要我时随时告诉我。', ['保持自然呼吸', '每小时短暂活动一下']],
        tense: ['notice', '先让这一分钟慢下来', '我在。先把肩膀放松一点，缓慢呼气六秒，再自然吸气四秒。', ['做 3 轮 4 秒吸气、6 秒呼气', '离开屏幕 2 分钟']],
        overwhelmed: ['pause', '现在不需要解决全部问题', '我在。先不要逼自己处理全部事情。我们只做三轮缓慢呼吸，然后联系一个你信任的人。', ['做三轮缓慢呼吸', '联系可信任的人', '若仍无法缓解，寻求专业帮助']],
        task_complete: ['celebrate', '这件难事，你完成了', '做得很好。你刚刚完成了一件不容易的事。先停十秒，感受一下自己已经做到的部分。', ['写下一句“我刚刚做到了什么”', '给自己 30 秒肯定']],
        unsafe: ['urgent', '现在先把安全放在第一位', '谢谢你告诉我。现在先不要一个人扛着。请联系身边可信任的人，让对方陪着你；如果危险正在发生，请立即联系当地紧急援助。', ['联系一位可信任的人并请对方陪伴', '离开危险环境并远离可能造成伤害的物品', '如危险正在发生，立即联系当地紧急援助']]
      };
      const [level, title, voice, actions] = map[item.kind];
      return { level, title, message: voice, voice_text: voice, actions, confidence: 'self_report', can_diagnose: false, medical_disclaimer: '这是用户主动反馈后的陪伴提示，不是医学诊断。' };
    }
    return { level: 'steady', title: '节律平稳，继续按自己的节奏', message: '演示数据没有出现需要打断的持续组合变化。', voice_text: '现在的节律比较平稳。继续按自己的速度来，需要我时随时告诉我。', actions: ['保持自然呼吸', '完成困难任务后记得给自己肯定'], confidence: 'demo', can_diagnose: false, medical_disclaimer: '当前为合成演示，不代表任何人的真实生理或心理状态。' };
  }

  function makeDemoState() {
    const now = Date.now();
    const t = (now - app.demoStarted) / 1000;
    const bpm = Math.round(72 + Math.sin(t / 4) * 4 + Math.sin(t / 1.7) * 2);
    const attention = 68 + Math.sin(t / 7) * 9;
    const valence = .28 + Math.sin(t / 9) * .13;
    const raw = [], envelope = [];
    for (let i = 0; i < 640; i += 1) {
      const x = t + i / 128;
      const value = 118 * Math.sin(Math.PI * 20.4 * x) + 34 * Math.sin(Math.PI * 10.2 * x) + 12 * Math.sin(Math.PI * 44 * x);
      raw.push(value); envelope.push(Math.abs(value) * .72 + 40);
    }
    const bandHistory = Array.from({ length: 42 }, (_, i) => ({
      t: now / 1000 - (41 - i), quality: 0,
      relative_power: [.12, .18, .34 + Math.sin((t + i) / 7) * .07, .28, .08]
    }));
    const heartHistory = Array.from({ length: 50 }, (_, i) => ({ t: now / 1000 - (49 - i) * 2, bpm: Math.round(72 + Math.sin((t + i) / 5) * 4) }));
    return {
      schema_version: 'mindlink.state.v2', generated_at: now / 1000, mode: 'demo_simulation', wellness_score: Math.round(80 + Math.sin(t / 8) * 3),
      eeg: { valid: true, reason: null, source: 'demo_simulation', quality: 0, total: Math.round(t * 512), raw, envelope, age_s: 0 },
      brain_state: { valid: true, source: 'demo_simulation', attention_score: attention, valence_score: valence, sample_time_end_unix_s: now / 1000 },
      band_history: bandHistory, band_names: ['δ 1–4', 'θ 4–8', 'α 8–13', 'β 13–30', 'γ 30–45'],
      heart_rate: { valid: true, bpm, source: 'demo_watch', age_s: 0, history: heartHistory },
      blood_pressure: { valid: true, systolic: 118, diastolic: 76, source: 'demo_watch', age_s: 0 },
      spo2: { valid: true, percent: 98, source: 'demo_watch', age_s: 0 },
      support: demoSupport(now),
      semantics: 'Synthetic demo only; not a person or diagnosis.'
    };
  }

  function drawLine(canvas, values, color, range, emptyText) {
    const ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = '#eadfce'; ctx.lineWidth = 1;
    for (let i = 1; i < 4; i += 1) { ctx.beginPath(); ctx.moveTo(0, h * i / 4); ctx.lineTo(w, h * i / 4); ctx.stroke(); }
    if (!values.length) { ctx.fillStyle = '#87918d'; ctx.font = '15px sans-serif'; ctx.fillText(emptyText, 18, h / 2); return; }
    const [lo, hi] = range; ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.lineJoin = 'round'; ctx.beginPath();
    values.forEach((value, index) => { const x = index * w / Math.max(1, values.length - 1), y = h - 10 - (value - lo) / (hi - lo) * (h - 20); index ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.stroke();
  }

  function drawWave(eeg) {
    const canvas = $('wave'), ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h); ctx.strokeStyle = '#ebdfd0'; ctx.lineWidth = 1;
    for (let i = 1; i < 5; i += 1) { ctx.beginPath(); ctx.moveTo(0, h * i / 5); ctx.lineTo(w, h * i / 5); ctx.stroke(); }
    if (!eeg?.valid || !eeg.raw?.length) { ctx.fillStyle = '#7f8b86'; ctx.font = '16px sans-serif'; ctx.fillText('等待连续、有效的真实 RAW 数据', 24, h / 2); return; }
    const finite = eeg.raw.filter(Number.isFinite); const max = Math.max(60, ...finite.map(Math.abs));
    [[eeg.raw, '#d55f56', 2], [eeg.envelope || [], '#efa95d', 1.4]].forEach(([values, color, width]) => {
      ctx.strokeStyle = color; ctx.lineWidth = width; ctx.beginPath(); let open = false;
      values.forEach((value, i) => { if (!Number.isFinite(value)) { open = false; return; } const x = i * w / Math.max(1, values.length - 1); const centered = color === '#efa95d' ? value - max * .45 : value; const y = h / 2 - centered / max * (h * .38); if (open) ctx.lineTo(x, y); else ctx.moveTo(x, y); open = true; });
      ctx.stroke();
    });
  }

  function drawBands(state) {
    const canvas = $('bands'), ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height, rows = 5;
    ctx.clearRect(0, 0, w, h); const history = state.band_history || [], names = state.band_names || [];
    if (!history.length) { ctx.fillStyle = '#7f8b86'; ctx.font = '15px sans-serif'; ctx.fillText('等待频段功率', 20, h / 2); return; }
    ctx.font = '12px sans-serif';
    names.forEach((name, row) => {
      ctx.fillStyle = '#66736e'; ctx.fillText(name, 7, row * h / rows + 18);
      history.forEach((item, index) => { const value = clamp(item.relative_power?.[row] || 0, 0, 1); ctx.fillStyle = `hsl(${29 + value * 118},${38 + value * 24}%,${91 - value * 48}%)`; const cell = (w - 75) / history.length; ctx.fillRect(72 + index * cell, row * h / rows + 2, cell + .7, h / rows - 4); });
    });
  }

  function speak(text, automatic = false) {
    if (!app.voiceEnabled || !('speechSynthesis' in window)) { if (!automatic) toast('请先点击“开启语音陪伴”'); return; }
    if (automatic && Date.now() - app.lastSpokenAt < 45000) return;
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text); utterance.lang = 'zh-CN'; utterance.rate = .88; utterance.pitch = 1.02; utterance.volume = .95;
    const voices = speechSynthesis.getVoices(); utterance.voice = voices.find(v => /^zh(-|_)/i.test(v.lang)) || null;
    speechSynthesis.speak(utterance); app.lastSpokenAt = Date.now();
  }

  function render(state) {
    app.state = state; const demo = state.mode === 'demo_simulation';
    $('modeText').textContent = demo ? '合成演示模式 · 数值不代表真人' : '真实硬件模式 · 本机处理';
    $('modeBanner').classList.toggle('demo', demo);
    $('connection').textContent = demo ? '演示流在线' : '本地实时服务在线';
    const score = state.wellness_score;
    $('wellnessScore').textContent = Number.isFinite(score) ? score : '—';
    $('wellnessLabel').textContent = Number.isFinite(score) ? (score >= 75 ? '节律平稳' : score >= 55 ? '建议留意' : '建议暂停') : '等待数据';
    $('eegStatus').textContent = status(state.eeg); $('quality').textContent = state.eeg?.quality === 0 ? '良好' : (state.eeg?.quality ?? '未知');
    $('focus').textContent = state.brain_state?.valid ? state.brain_state.attention_score.toFixed(0) : '—';
    $('valence').textContent = state.brain_state?.valid ? state.brain_state.valence_score.toFixed(2) : '—';
    $('total').textContent = Number.isFinite(state.eeg?.total) ? state.eeg.total.toLocaleString() : '—';
    $('heartStatus').textContent = status(state.heart_rate); $('bpm').textContent = state.heart_rate?.valid ? state.heart_rate.bpm : '—'; $('heartSource').textContent = state.heart_rate?.source || '—';
    const bp = state.blood_pressure || {}; $('bloodPressure').textContent = bp.valid ? `${bp.systolic} / ${bp.diastolic}` : '— / —'; $('bpSource').textContent = bp.valid ? `${bp.source || '设备'} · ${Math.round(bp.age_s || 0)} 秒前` : status(bp);
    const oxygen = state.spo2 || {}; $('spo2').textContent = oxygen.valid ? oxygen.percent : '—'; $('spo2Source').textContent = oxygen.valid ? `${oxygen.source || '设备'} · ${Math.round(oxygen.age_s || 0)} 秒前` : status(oxygen);
    drawWave(state.eeg); drawBands(state);
    drawLine($('heartChart'), (state.heart_rate?.history || []).map(item => item.bpm).filter(Number.isFinite), '#e5675c', [45, 115], '等待实时心率');

    const support = state.support || demoSupport(Date.now());
    $('supportCard').dataset.level = support.level || 'collecting'; $('supportTitle').textContent = support.title; $('supportMessage').textContent = support.message;
    $('voiceText').textContent = support.voice_text; $('supportConfidence').textContent = support.confidence === 'self_report' ? '基于主动反馈' : support.confidence === 'none' ? '数据不足' : '谨慎提示';
    $('medicalNote').textContent = support.medical_disclaimer || '趋势提示不等于医学或心理诊断。';
    $('actionList').replaceChildren(...(support.actions || []).map(action => { const li = document.createElement('li'); li.textContent = action; return li; }));
    const speakKey = `${support.level}:${support.title}`;
    if (app.voiceEnabled && speakKey !== app.lastSpokenKey && ['notice', 'pause', 'urgent', 'celebrate'].includes(support.level)) speak(support.voice_text, true);
    app.lastSpokenKey = speakKey;
  }

  async function poll() {
    try {
      const state = app.apiAvailable ? await api('/api/state') : makeDemoState(); render(state);
    } catch (error) {
      $('connection').textContent = '本地服务连接中断';
      if (app.state) { const stale = structuredClone(app.state); stale.eeg.valid = false; stale.brain_state.valid = false; stale.heart_rate.valid = false; stale.band_history = []; render(stale); }
    } finally { setTimeout(poll, 850); }
  }

  $('voiceButton').addEventListener('click', () => {
    app.voiceEnabled = !app.voiceEnabled; $('voiceButton').setAttribute('aria-pressed', String(app.voiceEnabled));
    $('voiceButton').innerHTML = app.voiceEnabled ? '<span>◖</span> 语音陪伴已开启' : '<span>◖</span> 开启语音陪伴';
    if (app.voiceEnabled) { speak('语音陪伴已开启。我会尽量少打扰，只在需要时温柔提醒。'); toast('已启用本机中文语音'); } else { window.speechSynthesis?.cancel(); toast('语音陪伴已关闭'); }
  });
  $('speakNow').addEventListener('click', () => speak(app.state?.support?.voice_text || $('voiceText').textContent));
  $('exportButton').addEventListener('click', () => {
    if (!app.state) return; const url = URL.createObjectURL(new Blob([JSON.stringify(app.state, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `mindlink-state-${new Date().toISOString().replace(/[:.]/g, '-')}.json`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  $('portsButton').addEventListener('click', async () => {
    if (!app.apiAvailable) return toast('在线展示页不能枚举本机串口；请运行本地版');
    try { const result = await api('/api/ports'); toast(result.ports?.map(item => `${item.port} ${item.description}`).join('；') || '未找到串口；检查不会占用端口'); } catch (error) { toast(error.message); }
  });
  document.querySelectorAll('[data-checkin]').forEach(button => button.addEventListener('click', async () => {
    const kind = button.dataset.checkin;
    try {
      if (app.apiAvailable) await api('/api/v1/check-in', { kind }); else app.localCheckin = { kind, at: Date.now() };
      render(app.apiAvailable ? await api('/api/state') : makeDemoState());
      const labels = { calm: '已记录：我现在还好', tense: '我会陪你慢下来', overwhelmed: '已启动低负担陪伴', task_complete: '这一刻值得被记住', unsafe: '已显示立即安全步骤' };
      toast(labels[kind]);
    } catch (error) { toast(error.message); }
  }));
  const openDialog = dialog => typeof dialog.showModal === 'function' ? dialog.showModal() : dialog.setAttribute('open', '');
  $('guideButton').addEventListener('click', () => openDialog($('guideDialog'))); $('stimulationButton').addEventListener('click', () => openDialog($('stimulationDialog')));
  document.querySelectorAll('[data-dialog-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));

  (async () => {
    try {
      const response = await fetch('/api/bootstrap', { signal: AbortSignal.timeout(1800) });
      if (!response.ok) throw new Error('no local runtime');
      const bootstrap = await response.json(); app.token = bootstrap.token; app.apiAvailable = true;
    } catch (_error) {
      app.hostedDemo = true; app.apiAvailable = false;
      $('modeText').textContent = '网页合成演示 · 本地版可连接硬件'; $('connection').textContent = '合成演示流在线';
    }
    poll();
  })();
})();
