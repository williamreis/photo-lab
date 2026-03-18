(function () {
  const API = '/api/v1/agent/analyze/persist_async';
  const API_HISTORY = '/api/v1/history';
  const API_JOBS = '/api/v1/jobs';
  let enriched = [];
  let activeTab = 'ess';

  const $ = function (id) { return document.getElementById(id); };
  function setUploadLoading(statusTxt, phaseTxt) {
    var s = $('upload-status');
    if (s) s.textContent = statusTxt || '';
    var p = $('upload-phase');
    if (p) p.textContent = phaseTxt || '—';
  }
  function setUploadElapsed(mmss) {
    var e = $('upload-elapsed');
    if (e) e.textContent = mmss || '00:00';
  }
  function formatElapsed(ms) {
    var sec = Math.max(0, Math.floor(ms / 1000));
    var m = Math.floor(sec / 60);
    var s = sec % 60;
    return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
  }

  function openHistory() {
    var bd = $('history-backdrop');
    var dr = $('history-drawer');
    bd.classList.remove('hidden');
    void bd.offsetWidth;
    bd.classList.remove('opacity-0');
    dr.classList.add('is-open');
    loadHistoryList();
  }
  function closeHistory() {
    $('history-backdrop').classList.add('opacity-0');
    $('history-drawer').classList.remove('is-open');
    setTimeout(function () {
      $('history-backdrop').classList.add('hidden');
    }, 320);
  }
  async function loadHistoryList() {
    $('history-loading').classList.remove('hidden');
    $('history-empty').classList.add('hidden');
    $('history-list').innerHTML = '';
    try {
      var res = await fetch(API_HISTORY + '?limit=50');
      var items = await res.json();
      $('history-loading').classList.add('hidden');
      if (!items.length) {
        $('history-empty').classList.remove('hidden');
        return;
      }
      items.forEach(function (it) {
        var row = document.createElement('button');
        row.type = 'button';
        row.className = 'history-item w-full flex gap-4 p-3 text-left';
        row.dataset.id = it.id;
        row.dataset.status = it.status || '';
        row.dataset.jobId = it.job_id || '';
        var dt = it.created_at ? new Date(it.created_at) : null;
        var dateStr = dt && !isNaN(dt.getTime())
          ? dt.toLocaleString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
          : '';
        var st = String(it.status || '').toLowerCase();
        var isProcessing = st === 'processing';
        var isFailed = st === 'failed';
        var statusBadge = isProcessing
          ? '<span class="history-badge history-badge--processing"><span class="history-badge__dot"></span>Processando</span>'
          : (isFailed
            ? '<span class="history-badge history-badge--failed"><span class="history-badge__dot history-badge__dot--failed"></span>Falhou</span>'
            : '');
        row.innerHTML =
          '<div class="history-thumb w-[72px] h-[72px] rounded-xl overflow-hidden shrink-0 bg-slate-800/80 ring-1 ring-white/10">' +
          '<img src="' + escapeAttr(it.image_url) + '" alt="" class="w-full h-full object-cover"/>' +
          ((isProcessing || isFailed) ? '<div class="history-thumb__overlay"></div>' : '') +
          '</div>' +
          '<div class="min-w-0 flex-1 py-0.5">' +
          '<p class="text-[10px] font-mono text-teal-500/80 flex items-center justify-between gap-2">' +
          '<span class="min-w-0 truncate">' + escapeHtml(dateStr) + ' · ' + (it.marker_count || 0) + ' pts</span>' +
          statusBadge +
          '</p>' +
          '<p class="text-sm text-slate-300 mt-1.5 line-clamp-2 leading-snug">' + escapeHtml(it.preview || '') + '</p></div>';
        row.addEventListener('click', function () {
          if (isProcessing) {
            alert('Esta análise ainda está em processamento.');
            return;
          }
          if (isFailed) {
            alert((it.error_message ? ('Falhou: ' + it.error_message) : 'Falha no processamento.'));
            return;
          }
          openHistoryEntry(it.id);
        });
        $('history-list').appendChild(row);
      });
    } catch (e) {
      $('history-loading').classList.add('hidden');
      $('history-empty').classList.remove('hidden');
      $('history-empty').innerHTML = 'Não foi possível carregar o histórico.';
    }
  }
  function escapeAttr(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }
  async function openHistoryEntry(id) {
    try {
      var res = await fetch(API_HISTORY + '/' + encodeURIComponent(id));
      if (!res.ok) throw new Error('Não encontrado');
      var d = await res.json();
      if (String(d.status || '').toLowerCase() === 'failed') {
        alert((d.error_message ? ('Falhou: ' + d.error_message) : (d.analysis || 'Falha no processamento.')));
        return;
      }
      if (String(d.status || '').toLowerCase() === 'processing') {
        alert('Esta análise ainda está em processamento.');
        return;
      }
      closeHistory();
      showResult({
        image_url: d.image_url,
        analysis: d.analysis || '',
        markers: (d.markers || []).map(function (m) {
          return {
            id: m.id,
            x: m.x,
            y: m.y,
            query: m.query || '',
            description: m.description || '',
            relevance: m.relevance || '',
            photoshop_technique: m.photoshop_technique || ''
          };
        })
      });
    } catch (err) {
      alert(err.message || 'Erro ao abrir');
    }
  }

  $('btn-hist-upload').addEventListener('click', openHistory);
  $('btn-hist-result').addEventListener('click', openHistory);
  $('history-close').addEventListener('click', closeHistory);
  $('history-backdrop').addEventListener('click', closeHistory);

  function isEssential(m) {
    return (m.relevance || '').toUpperCase() === 'ESSENCIAL';
  }

  function enrichMarkers(markers) {
    const rec = [];
    const ess = [];
    markers.forEach(function (m) {
      if (isEssential(m)) ess.push(Object.assign({}, m));
      else rec.push(Object.assign({}, m));
    });
    var n = 1;
    var out = [];
    rec.forEach(function (m) {
      m.displayNum = n++;
      m.tier = 'rec';
      out.push(m);
    });
    ess.forEach(function (m) {
      m.displayNum = n++;
      m.tier = 'ess';
      out.push(m);
    });
    if (out.length === 0 && markers.length) {
      markers.forEach(function (m, i) {
        var x = Object.assign({}, m);
        x.displayNum = i + 1;
        x.tier = isEssential(m) ? 'ess' : 'rec';
        out.push(x);
      });
    }
    return out;
  }

  function updateHeaderCounts() {
    var ne = enriched.filter(function (m) { return m.tier === 'ess'; }).length;
    var nr = enriched.filter(function (m) { return m.tier === 'rec'; }).length;
    $('hdr-ess-n').textContent = ne;
    $('hdr-rec-n').textContent = nr;
    $('tab-ess-count').textContent = ne;
    $('tab-rec-count').textContent = nr;
  }

  function renderLists() {
    var le = $('list-essential');
    var lr = $('list-recommended');
    le.innerHTML = '';
    lr.innerHTML = '';
    enriched.forEach(function (m) {
      var ess = m.tier === 'ess';
      var card = document.createElement('div');
      card.className = 'report-card flex report-card--' + m.displayNum;
      card.dataset.num = String(m.displayNum);
      card.innerHTML =
        '<div class="shrink-0 ' + (ess ? 'bar-ess' : 'bar-rec') + '"></div>' +
        '<div class="flex gap-3 p-3.5 flex-1 min-w-0">' +
        '<div class="w-10 h-10 rounded-full shrink-0 flex items-center justify-center text-sm font-bold ' +
        (ess ? 'badge-ess' : 'badge-rec') + ' shadow-md">' + m.displayNum + '</div>' +
        '<div class="min-w-0">' +
        '<p class="text-sm text-slate-100 font-medium leading-snug">' + escapeHtml(m.description || m.query || 'Item') + '</p>' +
        '<p class="text-[11px] text-slate-500 mt-2 flex items-start gap-2">' +
        '<span class="text-teal-500/80 shrink-0" aria-hidden="true">◆</span>' +
        '<span>' + escapeHtml(m.photoshop_technique || '—') + '</span></p></div></div>';
      card.addEventListener('mouseenter', function () { highlightMarker(m.displayNum); });
      card.addEventListener('mouseleave', clearHighlight);
      (ess ? le : lr).appendChild(card);
    });
    if (!enriched.filter(function (m) { return m.tier === 'ess'; }).length) {
      le.innerHTML = '<p class="text-sm text-slate-600 text-center py-10">Nenhum item essencial.</p>';
    }
    if (!enriched.filter(function (m) { return m.tier === 'rec'; }).length) {
      lr.innerHTML = '<p class="text-sm text-slate-600 text-center py-10">Nenhum item recomendado.</p>';
    }
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function setTab(which) {
    activeTab = which;
    var essAct = which === 'ess';
    $('tab-ess').className = 'report-tab ' + (essAct ? 'report-tab--active-ess' : '');
    $('tab-rec').className = 'report-tab ' + (!essAct ? 'report-tab--active-rec' : '');
    $('list-essential').classList.toggle('hidden', !essAct);
    $('list-recommended').classList.toggle('hidden', essAct);
  }

  function scrollReportToCard(displayNum, tier) {
    hideTip();
    setTab(tier === 'ess' ? 'ess' : 'rec');
    highlightMarker(displayNum);
    var sc = $('report-scroll');
    function doScroll() {
      var card = document.querySelector('#report-scroll .report-card[data-num="' + displayNum + '"]');
      if (card && sc) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
      }
    }
    requestAnimationFrame(function () {
      requestAnimationFrame(doScroll);
    });
  }

  function highlightMarker(num) {
    document.querySelectorAll('.marker-pin').forEach(function (el) {
      el.classList.toggle('is-active', el.dataset.num === String(num));
    });
    document.querySelectorAll('.report-card').forEach(function (el) {
      el.classList.toggle('is-highlight', el.dataset.num === String(num));
    });
  }

  function clearHighlight() {
    document.querySelectorAll('.marker-pin.is-active').forEach(function (el) { el.classList.remove('is-active'); });
    document.querySelectorAll('.report-card.is-highlight').forEach(function (el) { el.classList.remove('is-highlight'); });
  }

  function layoutMarkers() {
    var layer = $('markers-layer');
    layer.innerHTML = '';
    layer.style.pointerEvents = 'none';
    enriched.forEach(function (m) {
      var wrap = document.createElement('div');
      wrap.className = 'absolute pointer-events-auto';
      wrap.style.left = (m.x * 100) + '%';
      wrap.style.top = (m.y * 100) + '%';
      wrap.style.transform = 'translate(-50%, -50%)';
      wrap.style.zIndex = '25';
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'marker-pin ' + (m.tier === 'ess' ? 'marker-pin--ess' : 'marker-pin--rec');
      btn.textContent = String(m.displayNum);
      btn.dataset.num = String(m.displayNum);
      btn.setAttribute('title', 'Clique para ir à descrição no laudo');
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        scrollReportToCard(m.displayNum, m.tier);
      });
      btn.addEventListener('mouseenter', function (e) {
        highlightMarker(m.displayNum);
        showTip(e, m);
      });
      btn.addEventListener('mousemove', moveTip);
      btn.addEventListener('mouseleave', function () { clearHighlight(); hideTip(); });
      btn.addEventListener('focus', function (e) { highlightMarker(m.displayNum); showTip(e, m); });
      btn.addEventListener('blur', function () { clearHighlight(); hideTip(); });
      wrap.appendChild(btn);
      layer.appendChild(wrap);
    });
  }

  var floatTip = $('float-tooltip');
  function showTip(e, m) {
    $('tt-rel').textContent = m.relevance || (m.tier === 'ess' ? 'Essencial' : 'Recomendado');
    $('tt-title').textContent = m.query || 'Área';
    $('tt-desc').textContent = m.description || '';
    $('tt-xy').textContent = 'x ' + Number(m.x).toFixed(3) + ' · y ' + Number(m.y).toFixed(3);
    $('tt-tech').textContent = m.photoshop_technique ? m.photoshop_technique : '';
    floatTip.style.display = 'block';
    requestAnimationFrame(function () { floatTip.style.opacity = '1'; moveTip(e); });
  }
  function moveTip(e) {
    var pad = 14, x = e.clientX + pad, y = e.clientY + pad;
    var r = floatTip.getBoundingClientRect();
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - pad;
    if (y + r.height > innerHeight - 8) y = e.clientY - r.height - pad;
    floatTip.style.left = x + 'px';
    floatTip.style.top = y + 'px';
  }
  function hideTip() {
    floatTip.style.opacity = '0';
    setTimeout(function () { floatTip.style.display = 'none'; }, 120);
  }

  function simpleMd(md) {
    if (!md) return '';
    return escapeHtml(md).replace(/\n/g, '<br/>');
  }

  $('tab-ess').addEventListener('click', function () { setTab('ess'); });
  $('tab-rec').addEventListener('click', function () { setTab('rec'); });

  function showResult(data) {
    enriched = enrichMarkers(data.markers || []);
    $('result-image').src = data.image_url;
    $('analysis-full').innerHTML = simpleMd(data.analysis || '');
    updateHeaderCounts();
    renderLists();
    setTab(enriched.some(function (m) { return m.tier === 'ess'; }) ? 'ess' : 'rec');
    $('result-image').onload = function () { layoutMarkers(); };
    if ($('result-image').complete) layoutMarkers();
    $('screen-upload').classList.add('hidden');
    $('screen-result').classList.remove('hidden');
  }

  $('btn-new').addEventListener('click', function () {
    $('screen-result').classList.add('hidden');
    $('screen-upload').classList.remove('hidden');
    enriched = [];
    hideTip();
  });

  $('file-input').addEventListener('change', function () {
    var f = this.files && this.files[0];
    if (f) upload(f);
    this.value = '';
  });
  ['dragenter', 'dragover'].forEach(function (ev) {
    $('upload-zone').addEventListener(ev, function (e) { e.preventDefault(); $('upload-zone').classList.add('dragover'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    $('upload-zone').addEventListener(ev, function (e) { e.preventDefault(); $('upload-zone').classList.remove('dragover'); });
  });
  $('upload-zone').addEventListener('drop', function (e) {
    var f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f && f.type.indexOf('image/') === 0) upload(f);
    else {
      $('upload-error').textContent = 'Use apenas imagem.';
      $('upload-error').classList.remove('hidden');
    }
  });

  async function pollJob(jobId) {
    var delay = 1200;
    var maxDelay = 5000;
    var startedAt = Date.now();
    while (true) {
      var res = await fetch(API_JOBS + '/' + encodeURIComponent(jobId));
      var data = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        var d = data.detail;
        if (Array.isArray(d)) d = d.map(function (x) { return x.msg || JSON.stringify(x); }).join(' ');
        throw new Error(d || 'Erro ' + res.status);
      }

      if (data.status === 'done') return data.result;
      if (data.status === 'failed') throw new Error(data.error || 'Falha no processamento.');

      if (data.status === 'queued') setUploadLoading('Upload recebido', 'Na fila');
      else setUploadLoading('Analisando a imagem', 'Processamento');

      // backoff suave (e evita loop apertado)
      await new Promise(function (r) { return setTimeout(r, delay); });
      delay = Math.min(maxDelay, Math.floor(delay * 1.25));

      // fallback: após muito tempo, mantém o texto mas continua esperando
      if (Date.now() - startedAt > 30 * 60 * 1000) {
        setUploadLoading('Ainda processando…', 'Processamento');
      }
    }
  }

  async function upload(file) {
    $('upload-error').classList.add('hidden');
    $('upload-loading').classList.remove('hidden');
    var t0 = Date.now();
    var timer = setInterval(function () {
      setUploadElapsed(formatElapsed(Date.now() - t0));
    }, 250);
    setUploadElapsed('00:00');
    setUploadLoading('Enviando imagem', 'Upload');
    $('upload-zone').classList.add('opacity-50', 'pointer-events-none');
    try {
      var fd = new FormData();
      fd.append('image', file);
      var res = await fetch(API, { method: 'POST', body: fd });
      var data = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        var d = data.detail;
        if (Array.isArray(d)) d = d.map(function (x) { return x.msg || JSON.stringify(x); }).join(' ');
        throw new Error(d || 'Erro ' + res.status);
      }
      if (!data.job_id) throw new Error('Resposta inválida: job_id ausente.');
      setUploadLoading('Upload recebido', 'Na fila');
      var result = await pollJob(data.job_id);
      showResult(result);
    } catch (err) {
      $('upload-error').textContent = err.message || String(err);
      $('upload-error').classList.remove('hidden');
    } finally {
      clearInterval(timer);
      $('upload-loading').classList.add('hidden');
      $('upload-zone').classList.remove('opacity-50', 'pointer-events-none');
    }
  }
})();

