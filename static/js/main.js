// ClipAI Frontend Logic
// Open Design 规范 — 无 AI 味

(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const els = {
    dropzone: $('#dropzone'),
    fileInput: $('#fileInput'),
    previewPanel: $('#previewPanel'),
    previewVideo: $('#previewVideo'),
    videoBadge: $('#videoBadge'),
    videoName: $('#videoName'),
    videoMeta: $('#videoMeta'),
    configPanel: $('#configPanel'),
    progressPanel: $('#progressPanel'),
    resultPanel: $('#resultPanel'),
    errorPanel: $('#errorPanel'),
    progressBar: $('#progressBar'),
    progressPercent: $('#progressPercent'),
    progressMessage: $('#progressMessage'),
    resultDesc: $('#resultDesc'),
    resultVideo: $('#resultVideo'),
    downloadBtn: $('#downloadBtn'),
    errorDesc: $('#errorDesc'),
    startProcessBtn: $('#startProcess'),
    newProjectBtn: $('#newProjectBtn'),
    retryBtn: $('#retryBtn'),
    historyList: $('#historyList'),
    segments: $$('.segment'),
    pills: $$('.pill'),
    targetDuration: $('#targetDuration'),
    instruction: $('#instruction'),
    modeSwitcher: $('#modeSwitcher'),
    apiKey: $('#apiKey'),
    optRemoveSilence: $('#optRemoveSilence'),
    optSubtitle: $('#optSubtitle'),
    optDenoise: $('#optDenoise'),
    optZoom: $('#optZoom'),
    optBgm: $('#optBgm'),
    navbar: $('#navbar'),
    navLinks: $$('.nav-link'),
  };

  let state = { jobId: null, file: null, ws: null, isProcessing: false };
  const CIRCUMFERENCE = 2 * Math.PI * 52;

  function init() { bindEvents(); loadHistory(); initNavbarScroll(); }

  function bindEvents() {
    els.dropzone.addEventListener('click', () => els.fileInput.click());
    els.dropzone.addEventListener('dragover', onDragOver);
    els.dropzone.addEventListener('dragleave', onDragLeave);
    els.dropzone.addEventListener('drop', onDrop);
    els.fileInput.addEventListener('change', onFileSelect);

    if (els.modeSwitcher) {
      els.modeSwitcher.querySelectorAll('.segment').forEach((seg) => {
        seg.addEventListener('click', () => {
          els.modeSwitcher.querySelectorAll('.segment').forEach((s) => s.classList.remove('active'));
          seg.classList.add('active');
          onModeChange(seg.dataset.videoMode);
        });
      });
    }

    els.segments.forEach((seg) => {
      seg.addEventListener('click', () => {
        els.segments.forEach((s) => s.classList.remove('active'));
        seg.classList.add('active');
      });
    });

    els.pills.forEach((pill) => {
      pill.addEventListener('click', () => {
        els.pills.forEach((p) => p.classList.remove('active'));
        pill.classList.add('active');
      });
    });

    els.startProcessBtn.addEventListener('click', startProcess);
    els.newProjectBtn.addEventListener('click', resetWorkspace);
    els.retryBtn.addEventListener('click', resetWorkspace);
    window.addEventListener('scroll', updateNavActive);
  }

  function onModeChange(mode) {
    if (mode === 'visual') {
      els.modeHint.textContent = '适用于风景、航拍、无旁白的纯画面视频。AI 分析画面镜头、运动、色彩来剪辑。可输入自然语言指令（如"保留日落片段，去掉晃动的"）。';
      els.optRemoveSilence.disabled = true;
      els.optSubtitle.disabled = true;
      els.optDenoise.disabled = true;
    } else {
      els.modeHint.textContent = '适用于口播、播客、Vlog 等有人声的视频。AI 分析语音内容来剪辑。';
      els.optRemoveSilence.disabled = false;
      els.optSubtitle.disabled = false;
      els.optDenoise.disabled = false;
    }
  }

  function onDragOver(e) { e.preventDefault(); els.dropzone.classList.add('drag-active'); }
  function onDragLeave(e) { e.preventDefault(); if (!els.dropzone.contains(e.relatedTarget)) els.dropzone.classList.remove('drag-active'); }
  function onDrop(e) { e.preventDefault(); els.dropzone.classList.remove('drag-active'); if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]); }
  function onFileSelect(e) { if (e.target.files.length) handleFile(e.target.files[0]); }

  function handleFile(file) {
    const validExts = ['.mp4', '.mov', '.avi', '.mkv', '.webm'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!validExts.includes(ext)) { showError('不支持的文件格式'); return; }
    if (file.size > 500 * 1024 * 1024) { showError('文件过大'); return; }
    state.file = file;
    const url = URL.createObjectURL(file);
    els.previewVideo.src = url;
    els.videoBadge.textContent = ext.toUpperCase().replace('.', '');
    els.videoName.textContent = file.name;
    els.previewVideo.onloadedmetadata = () => {
      els.videoMeta.textContent = `${formatTime(els.previewVideo.duration)} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
    };
    showPanel('preview'); showPanel('config');
  }

  async function startProcess() {
    if (!state.file || state.isProcessing) return;
    state.isProcessing = true;
    els.startProcessBtn.classList.add('loading');
    els.startProcessBtn.disabled = true;
    try {
      const formData = new FormData();
      formData.append('file', state.file);
      const uploadRes = await fetch('/api/upload', { method: 'POST', body: formData });
      const uploadData = await uploadRes.json();
      if (!uploadRes.ok) throw new Error(uploadData.error || '上传失败');
      state.jobId = uploadData.job_id;

      const videoMode = els.modeSwitcher?.querySelector('.segment.active')?.dataset.videoMode || 'speech';
      const mode = $('.segment.active')?.dataset.mode || 'auto';
      const style = $('.pill.active')?.dataset.style || 'vlog';
      const instruction = els.instruction?.value?.trim() || '';

      const processForm = new FormData();
      processForm.append('job_id', state.jobId);
      processForm.append('api_key', els.apiKey?.value?.trim() || '');
      processForm.append('video_mode', videoMode);
      processForm.append('mode', mode);
      processForm.append('style', style);
      processForm.append('instruction', instruction);
      processForm.append('remove_silence', els.optRemoveSilence.checked);
      processForm.append('add_subtitle', els.optSubtitle.checked);
      processForm.append('denoise_audio', els.optDenoise.checked);
      processForm.append('add_zoom', els.optZoom.checked);
      processForm.append('add_bgm', els.optBgm.checked);
      if (els.targetDuration.value) processForm.append('target_duration', els.targetDuration.value);

      const processRes = await fetch('/api/process', { method: 'POST', body: processForm });
      const processData = await processRes.json();
      if (!processRes.ok) throw new Error(processData.error || '启动失败');
      showPanel('progress');
      connectWebSocket(state.jobId);
    } catch (err) {
      showError(err.message || '处理失败');
      state.isProcessing = false;
      els.startProcessBtn.classList.remove('loading');
      els.startProcessBtn.disabled = false;
    }
  }

  function connectWebSocket(jobId) {
    const wsUrl = `ws://${window.location.host}/ws/${jobId}`;
    const ws = new WebSocket(wsUrl);
    state.ws = ws;
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      updateProgress(data);
      if (data.status === 'completed') { ws.close(); showResult(data); state.isProcessing = false; els.startProcessBtn.classList.remove('loading'); els.startProcessBtn.disabled = false; loadHistory(); }
      else if (data.status === 'failed') { ws.close(); showError(data.message || '处理失败'); state.isProcessing = false; els.startProcessBtn.classList.remove('loading'); els.startProcessBtn.disabled = false; }
    };
    ws.onerror = () => startPolling(jobId);
  }

  function startPolling(jobId) {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${jobId}`);
        const data = await res.json();
        updateProgress(data);
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval);
          if (data.status === 'completed') showResult(data); else showError(data.message || '处理失败');
          state.isProcessing = false;
          els.startProcessBtn.classList.remove('loading');
          els.startProcessBtn.disabled = false;
        }
      } catch (e) { console.error('轮询错误:', e); }
    }, 1500);
  }

  function updateProgress(data) {
    const pct = Math.min(data.progress || 0, 100);
    els.progressBar.style.strokeDashoffset = CIRCUMFERENCE - (pct / 100) * CIRCUMFERENCE;
    els.progressPercent.textContent = Math.round(pct);
    els.progressMessage.textContent = data.message || '处理中...';
    const stepMap = { 20: 1, 35: 2, 50: 3, 70: 4, 100: 5 };
    const activeStep = Object.entries(stepMap).find(([k]) => pct <= parseInt(k));
    const stepNum = activeStep ? parseInt(activeStep[1]) : 5;
    $$('.step').forEach((step) => {
      const s = parseInt(step.dataset.step);
      step.classList.remove('active', 'done');
      if (s < stepNum) step.classList.add('done'); else if (s === stepNum) step.classList.add('active');
    });
  }

  function showResult(data) {
    showPanel('result');
    const timeline = data.timeline || [];
    const kept = timeline.filter((t) => t.action === 'keep');
    const removed = timeline.filter((t) => t.action === 'remove');
    const keptDuration = kept.reduce((s, t) => s + (t.duration || 0), 0);
    els.resultDesc.textContent = `保留了 ${kept.length} 个片段，删除了 ${removed.length} 处冗余，输出时长约 ${formatTime(keptDuration)}`;
    if (data.output_path) { els.resultVideo.src = `/api/download/${data.job_id}`; els.downloadBtn.href = `/api/download/${data.job_id}`; }
  }

  function showError(message) { showPanel('error'); els.errorDesc.textContent = message; state.isProcessing = false; els.startProcessBtn.classList.remove('loading'); els.startProcessBtn.disabled = false; }

  function resetWorkspace() {
    state = { jobId: null, file: null, ws: null, isProcessing: false };
    els.fileInput.value = ''; els.targetDuration.value = ''; if (els.instruction) els.instruction.value = '';
    els.previewVideo.src = ''; els.resultVideo.src = '';
    if (els.modeSwitcher) { els.modeSwitcher.querySelectorAll('.segment').forEach((s) => s.classList.remove('active')); const speechBtn = els.modeSwitcher.querySelector('[data-video-mode="speech"]'); if (speechBtn) speechBtn.classList.add('active'); onModeChange('speech'); }
    hidePanel('preview'); hidePanel('config'); hidePanel('progress'); hidePanel('result'); hidePanel('error');
    els.progressBar.style.strokeDashoffset = CIRCUMFERENCE; els.progressPercent.textContent = '0'; els.progressMessage.textContent = '准备中...';
    $$('.step').forEach((s) => s.classList.remove('active', 'done'));
    els.startProcessBtn.classList.remove('loading'); els.startProcessBtn.disabled = false;
  }

  function showPanel(name) { const map = { preview: els.previewPanel, config: els.configPanel, progress: els.progressPanel, result: els.resultPanel, error: els.errorPanel }; const p = map[name]; if (p) p.classList.remove('hidden'); }
  function hidePanel(name) { const map = { preview: els.previewPanel, config: els.configPanel, progress: els.progressPanel, result: els.resultPanel, error: els.errorPanel }; const p = map[name]; if (p) p.classList.add('hidden'); }

  async function loadHistory() {
    try { const res = await fetch('/api/history'); const jobs = await res.json(); renderHistory(jobs); } catch (e) { console.error('加载历史失败:', e); }
  }

  function renderHistory(jobs) {
    if (!jobs || jobs.length === 0) { els.historyList.innerHTML = `<div class="history-empty"><svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="8" y="12" width="32" height="24" rx="3"/><path d="M16 20l6 4-6 4"/></svg><p>暂无任务，上传视频开始你的第一个项目</p></div>`; return; }
    const recent = jobs.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)).slice(0, 10);
    els.historyList.innerHTML = recent.map((job) => {
      const statusClass = job.status === 'completed' ? 'completed' : job.status === 'processing' ? 'processing' : 'failed';
      const statusText = job.status === 'completed' ? '已完成' : job.status === 'processing' ? '处理中' : '失败';
      return `<div class="history-item" data-job-id="${job.id}"><div class="history-thumb" style="background: var(--bg-tertiary);"></div><div class="history-info"><p class="history-name">任务 #${job.id}</p><p class="history-meta">${formatDate(job.created_at)} · ${job.message || statusText}</p></div><span class="history-status ${statusClass}">${statusText}</span><div class="history-actions">${job.status === 'completed' && job.output_path ? `<a href="/api/download/${job.id}" class="history-btn" title="下载" download><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4-4m0 0l-4 4m4-4v12"/></svg></a>` : ''}<button class="history-btn" title="删除" onclick="deleteJob('${job.id}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg></button></div></div>`;
    }).join('');
  }

  window.deleteJob = async function (jobId) { if (!confirm('确定删除此任务？')) return; try { const res = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' }); if (res.ok) loadHistory(); } catch (e) { console.error('删除失败:', e); } };

  function initNavbarScroll() { let lastScroll = 0; window.addEventListener('scroll', () => { const currentScroll = window.scrollY; els.navbar.style.background = currentScroll > 60 ? 'rgba(15, 15, 15, 0.95)' : 'rgba(15, 15, 15, 0.85)'; lastScroll = currentScroll; }); }
  function updateNavActive() { const sections = ['upload', 'features', 'history']; const scrollPos = window.scrollY + 100; sections.forEach((id) => { const section = $(`#${id}`); if (!section) return; const link = $(`.nav-link[href="#${id}"]`); if (link) { if (scrollPos >= section.offsetTop && scrollPos < section.offsetTop + section.offsetHeight) link.classList.add('active'); else link.classList.remove('active'); } }); }

  function formatTime(seconds) { if (!seconds || isNaN(seconds)) return '00:00'; const m = Math.floor(seconds / 60); const s = Math.floor(seconds % 60); return `${m}:${s.toString().padStart(2, '0')}`; }
  function formatDate(isoString) { if (!isoString) return '未知时间'; const d = new Date(isoString); return `${d.getMonth() + 1}月${d.getDate()}日 ${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`; }

  init();
})();
