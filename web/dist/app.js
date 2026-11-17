(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const state = {
    live: false,
    timer: null,
    heartRate: 72,
    calm: 68,
    sync: 82,
    assessmentAnswers: [],
    deferredPrompt: null
  };

  const dashboardDate = $('#dashboardDate');
  if (dashboardDate) {
    const parts = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: '2-digit', month: 'short' }).formatToParts(new Date());
    const value = key => parts.find(part => part.type === key)?.value || '';
    dashboardDate.textContent = `${value('weekday').toUpperCase()} · ${value('day')} ${value('month').toUpperCase()}`;
  }

  const toast = (message) => {
    const el = $('#toast');
    el.textContent = message;
    el.classList.add('is-visible');
    window.clearTimeout(el._timer);
    el._timer = window.setTimeout(() => el.classList.remove('is-visible'), 2600);
  };

  const switchView = (name, updateHash = true) => {
    const panel = $(`[data-view-panel="${name}"]`) || $('[data-view-panel="home"]');
    $$('.view').forEach(view => view.classList.toggle('is-active', view === panel));
    $$('[data-view]').forEach(button => button.classList.toggle('is-active', button.dataset.view === panel.dataset.viewPanel));
    if (updateHash) history.replaceState(null, '', `#${panel.dataset.viewPanel}`);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  $$('[data-view]').forEach(button => button.addEventListener('click', () => switchView(button.dataset.view)));
  const requestedView = location.hash.replace('#', '');
  if (requestedView && $(`[data-view-panel="${requestedView}"]`)) switchView(requestedView, false);

  const openModal = (id) => {
    const modal = $(`#${id}`);
    if (!modal) return;
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    $('.modal-close', modal)?.focus();
  };
  const closeModal = (modal) => {
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  };
  $$('[data-close-modal]').forEach(button => button.addEventListener('click', () => closeModal(button.closest('.modal'))));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') $$('.modal.is-open').forEach(closeModal);
  });

  ['#connectDeviceButton', '#demoDeviceButton', '#profileConnect'].forEach(selector => {
    $(selector)?.addEventListener('click', () => openModal('deviceModal'));
  });

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const tickLiveData = () => {
    state.heartRate = clamp(Math.round(state.heartRate + (Math.random() - .48) * 4), 64, 86);
    state.calm = clamp(Math.round(state.calm + (Math.random() - .5) * 5), 52, 84);
    state.sync = clamp(Math.round((state.calm * .44) + (100 - Math.abs(state.heartRate - 71) * 2.1) * .36 + 18), 58, 94);
    const alpha = (8.6 + state.calm / 50 + (Math.random() - .5) * .22).toFixed(1);
    $('#heartRate').textContent = state.heartRate;
    $('#heroHeart').textContent = `${state.heartRate} bpm`;
    $('#calmScore').textContent = state.calm;
    $('#syncScore').textContent = state.sync;
    $('#heroSync').textContent = state.sync;
    $('#heroAlpha').textContent = `${alpha} Hz`;
    $('.ring-meter').style.setProperty('--score', state.sync);
    $$('.spectrum i').forEach(bar => bar.style.setProperty('--h', `${clamp(Number.parseInt(bar.style.getPropertyValue('--h')) + (Math.random() - .5) * 16, 18, 90)}%`));
  };

  const startLiveDemo = (device) => {
    state.live = true;
    window.clearInterval(state.timer);
    state.timer = window.setInterval(tickLiveData, 1200);
    tickLiveData();
    closeModal($('#deviceModal'));
    switchView('dashboard');
    toast(`${device}合成实时流已连接`);
  };
  $('#simulateEEG').addEventListener('click', () => startLiveDemo('EEG'));
  $('#simulateWatch').addEventListener('click', () => startLiveDemo('智能手表'));

  $$('.segmented button').forEach(button => button.addEventListener('click', () => {
    $$('.segmented button').forEach(item => item.classList.remove('is-active'));
    button.classList.add('is-active');
    toast(`已切换为${button.textContent}趋势视图（演示）`);
  }));
  $$('.today-plan input').forEach(input => input.addEventListener('change', () => {
    const completed = $$('.today-plan input:checked').length;
    toast(completed ? `已完成 ${completed} 个微行动，做得很好` : '微行动已恢复为待完成');
  }));

  const botReplies = [
    {
      match: /睡眠|入睡|早醒/,
      text: '最近 7 天你的平均睡眠是 7 小时 18 分，时长达标，但入睡时间波动约 52 分钟。与其追求更久，今晚更值得做的是把上床时间提前固定在 23:15 左右。你愿意先试 3 天吗？'
    },
    {
      match: /焦虑|难受|压力|心情/,
      text: '谢谢你告诉我。先不急着分析原因：如果把现在的紧绷感从 0 到 10 打分，它大概是多少？你也可以先跟着我慢慢呼气 6 秒、吸气 4 秒，做 5 轮。若你有伤害自己或他人的念头，请立刻联系身边可信任的人与当地紧急援助。'
    },
    {
      match: /下午|疲惫|专注|累/,
      text: '从演示趋势看，15:20 后脑电放松度下降，同时心率轻微上升，且你已连续坐了 76 分钟。这更像认知负荷累积，不等同于疾病信号。现在最小的有效行动是离开屏幕 5–10 分钟，补水并走动。'
    },
    {
      match: /今晚|计划|建议/,
      text: '今晚可以很轻：① 饭后慢走 10 分钟；② 22:45 开启低刺激模式；③ 睡前写一句“今天我已经完成了什么”。只选一项也算完成。'
    }
  ];
  const addMessage = (text, type) => {
    const wrapper = document.createElement('div');
    wrapper.className = `message ${type}`;
    const icon = type === 'bot' ? document.createElement('img') : document.createElement('span');
    if (type === 'bot') { icon.src = 'assets/logo-mark.svg'; icon.alt = ''; }
    else { icon.className = 'user-dot'; icon.textContent = '林'; }
    const bubble = document.createElement('div');
    const p = document.createElement('p');
    p.textContent = text;
    const time = document.createElement('small');
    time.textContent = type === 'bot' ? '灵犀 · 刚刚' : '你 · 刚刚';
    bubble.append(p, time);
    wrapper.append(icon, bubble);
    $('#chatMessages').appendChild(wrapper);
    $('#chatMessages').scrollTop = $('#chatMessages').scrollHeight;
  };
  const replyTo = (text) => {
    const found = botReplies.find(reply => reply.match.test(text));
    return found?.text || '我听到了。这个问题可以从数据趋势、身体感受和生活情境三个方向看。演示版先记录你的描述；接入完整 PHA 服务后，会由数据科学、健康知识与陪伴教练三个角色共同分析。';
  };
  const sendChat = (text) => {
    const clean = text.trim();
    if (!clean) return;
    addMessage(clean, 'user');
    window.setTimeout(() => addMessage(replyTo(clean), 'bot'), 420);
  };
  $('#chatForm').addEventListener('submit', event => {
    event.preventDefault();
    const input = $('#chatInput');
    sendChat(input.value);
    input.value = '';
  });
  $$('.prompt-chips button').forEach(button => button.addEventListener('click', () => sendChat(button.textContent)));
  $('#clearChat').addEventListener('click', () => {
    $('#chatMessages').replaceChildren();
    addMessage('新的对话开始了。今天你更想照顾身体，还是照顾心情？', 'bot');
  });

  const dataFile = $('#dataFile');
  $('#importDataButton').addEventListener('click', () => dataFile.click());
  dataFile.addEventListener('change', async () => {
    const file = dataFile.files[0];
    if (!file) return;
    try {
      const raw = await file.text();
      if (file.name.toLowerCase().endsWith('.json')) {
        const parsed = JSON.parse(raw);
        const latest = parsed.latest || parsed;
        if (Number.isFinite(Number(latest.heart_rate_bpm))) {
          state.heartRate = Number(latest.heart_rate_bpm);
          $('#heartRate').textContent = state.heartRate;
          $('#heroHeart').textContent = `${state.heartRate} bpm`;
        }
        localStorage.setItem('mindlink:last-import', JSON.stringify({ name: file.name, importedAt: new Date().toISOString() }));
        toast('JSON 数据已在本地解析');
      } else {
        const header = raw.split(/\r?\n/, 1)[0].toLowerCase();
        const recognized = ['datetime','steps','sleep','heart','eeg','timestamp'].filter(key => header.includes(key));
        toast(recognized.length ? `CSV 已识别：${recognized.join('、')}` : 'CSV 已读取，请按数据字典映射字段');
      }
    } catch (error) {
      toast(`导入失败：${error.message}`);
    } finally { dataFile.value = ''; }
  });

  const reportInput = $('#reportFile');
  const reportZone = $('#uploadZone');
  const addReportRows = (files) => {
    [...files].forEach(file => {
      const row = document.createElement('div');
      row.className = 'report-row';
      const icon = document.createElement('span');
      icon.className = `file-icon ${file.name.toLowerCase().endsWith('.csv') ? 'csv' : ''}`;
      icon.textContent = file.name.split('.').pop().slice(0, 4).toUpperCase();
      const meta = document.createElement('div');
      const title = document.createElement('strong'); title.textContent = file.name;
      const size = document.createElement('small'); size.textContent = `${(file.size / 1024).toFixed(1)} KB · 本地待解析`;
      meta.append(title, size);
      const status = document.createElement('span'); status.className = 'report-status'; status.textContent = '本地读取';
      const button = document.createElement('button'); button.textContent = '查看'; button.addEventListener('click', () => toast('完整报告结构化需要接入 OCR / 医疗文档解析服务'));
      row.append(icon, meta, status, button);
      $('#reportList').prepend(row);
    });
    toast(`已在本地读取 ${files.length} 个文件`);
  };
  $('#uploadReportButton').addEventListener('click', () => reportInput.click());
  reportZone.addEventListener('click', () => reportInput.click());
  reportZone.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') reportInput.click(); });
  reportInput.addEventListener('change', () => { if (reportInput.files.length) addReportRows(reportInput.files); reportInput.value = ''; });
  ['dragenter','dragover'].forEach(name => reportZone.addEventListener(name, event => { event.preventDefault(); reportZone.classList.add('is-dragging'); }));
  ['dragleave','drop'].forEach(name => reportZone.addEventListener(name, event => { event.preventDefault(); reportZone.classList.remove('is-dragging'); }));
  reportZone.addEventListener('drop', event => { if (event.dataTransfer.files.length) addReportRows(event.dataTransfer.files); });

  const assessmentQuestions = [
    '面对复杂任务，我更容易从哪里获得动力？',
    '团队意见不一致时，我通常先做什么？',
    '一段高投入工作后，什么最能帮助我恢复？'
  ];
  const assessmentOptions = [
    ['探索新可能','完成可见成果','帮助他人推进'],
    ['整理事实和结构','理解每个人的顾虑','快速尝试一个方案'],
    ['独处整理','与信任的人交流','运动或动手实践']
  ];
  const renderAssessment = (name) => {
    state.assessmentAnswers = [];
    $('#assessmentTitle').textContent = name;
    const content = $('#assessmentContent');
    content.replaceChildren();
    assessmentQuestions.forEach((question, index) => {
      const block = document.createElement('div'); block.className = 'assessment-question';
      const prompt = document.createElement('p'); prompt.textContent = `${index + 1}. ${question}`;
      const options = document.createElement('div'); options.className = 'assessment-options';
      assessmentOptions[index].forEach((label, optionIndex) => {
        const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
        button.addEventListener('click', () => {
          $$('.assessment-options button', block).forEach(item => item.classList.remove('is-selected'));
          button.classList.add('is-selected');
          state.assessmentAnswers[index] = optionIndex;
          if (state.assessmentAnswers.filter(answer => answer !== undefined).length === assessmentQuestions.length) showAssessmentResult(content, name);
        });
        options.appendChild(button);
      });
      block.append(prompt, options); content.appendChild(block);
    });
  };
  const showAssessmentResult = (content, name) => {
    $('.assessment-result', content)?.remove();
    const counts = [0,0,0]; state.assessmentAnswers.forEach(answer => counts[answer]++);
    const top = counts.indexOf(Math.max(...counts));
    const labels = ['洞察建构者','关系连接者','行动实验者'];
    const descriptions = [
      '你倾向于先理解系统与事实，再形成自己的判断。适合把复杂问题讲清楚，也要记得给行动留出空间。',
      '你敏锐地感知人与情境，擅长创造安全感与协作。注意不要把所有人的情绪都背在自己身上。',
      '你通过尝试获得能量，能把想法快速变成反馈。关键是为高频行动保留复盘与恢复。'
    ];
    const result = document.createElement('div'); result.className = 'assessment-result';
    const h3 = document.createElement('h3'); h3.textContent = `${name}结果：${labels[top]}`;
    const p = document.createElement('p'); p.textContent = `${descriptions[top]} 这是简短自我反思结果，不是诊断或官方测评。`;
    result.append(h3, p); content.appendChild(result); result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };
  $$('.assessment-start').forEach(button => button.addEventListener('click', () => { renderAssessment(button.dataset.assessment); openModal('assessmentModal'); }));

  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault(); state.deferredPrompt = event; $('#installPwa').hidden = false;
  });
  $('#installPwa').addEventListener('click', async () => {
    if (!state.deferredPrompt) return;
    state.deferredPrompt.prompt(); await state.deferredPrompt.userChoice; state.deferredPrompt = null; $('#installPwa').hidden = true;
  });
  if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
    window.addEventListener('load', () => navigator.serviceWorker.register('./sw.js').catch(() => {}));
  }
})();
