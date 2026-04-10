/**
 * Strategy / Plan / Brief 右栏统一：统一线程 + Council SSE + HTTP 折叠完整记录 + include_chat_context。
 * 不监听 chat_response SSE，避免与 sendChat 的 fetch 双写。
 */
(function (global) {
  'use strict';

  var COUNCIL_FSM_LABELS = {
    idle: '待命',
    submitting: '提交中',
    running_collecting: '收集中',
    running_synthesizing: '综合共识',
    proposal_ready: '提案就绪',
    completed: '已完成',
    failed: '失败'
  };

  var COUNCIL_SSE_NAMES = [
    'council_session_started',
    'council_phase_changed',
    'council_participant_started',
    'council_participant_message',
    'council_participant_completed',
    'council_synthesis_started',
    'council_synthesis_completed',
    'council_proposal_ready',
    'council_session_completed',
    'council_session_failed'
  ];

  function escapeHtml(s) {
    if (s == null) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function scheduleDeferred(fn, delayMs) {
    delayMs = delayMs || 0;
    function run() {
      try {
        fn();
      } catch (e) {}
    }
    if (typeof requestIdleCallback !== 'undefined') {
      requestIdleCallback(function () {
        setTimeout(run, delayMs);
      }, { timeout: 3000 });
    } else {
      setTimeout(run, Math.max(delayMs, 16));
    }
  }

  /**
   * @param {object} config
   * @param {string} config.opportunityId
   * @param {string} config.apiPrefix e.g. '/content-planning' (no trailing slash)
   * @param {string} config.stage 'brief' | 'strategy' | 'plan'
   * @param {string} config.chatCurrentStage same as backend current_stage for /chat
   * @param {string} [config.idPrefix] for final transcript id default
   * @param {object} config.ids element ids
   * @param {object} [config.labels]
   * @param {function(object): void} [config.onCouncilHttpComplete]
   * @param {function(Error): void} [config.onCouncilHttpError]
   */
  function initCouncilRightRail(config) {
    if (!config || !config.opportunityId) throw new Error('council_right_rail: opportunityId required');

    var opportunityId = config.opportunityId;
    var apiPrefix = (config.apiPrefix || '/content-planning').replace(/\/$/, '');
    var stage = config.stage || 'brief';
    var chatCurrentStage = config.chatCurrentStage || stage;
    var idPrefix = config.idPrefix || 'rail';
    var ids = config.ids || {};
    var labels = config.labels || {};

    var councilPostInFlight = false;
    var activeCouncilSessionId = '';
    var councilFsm = 'idle';
    var threadEl = null;
    var evtSource = null;

    function el(id) {
      if (!id) return null;
      return document.getElementById(id);
    }

    function getThreadEl() {
      if (!threadEl && ids.thread) threadEl = el(ids.thread);
      return threadEl;
    }

    function setCouncilStatus(msg, isError) {
      var statusEl = el(ids.councilStatus);
      if (!statusEl) return;
      statusEl.textContent = msg || '';
      statusEl.style.color = isError ? '#b71c1c' : msg ? 'var(--accent)' : 'var(--muted)';
    }

    function appendThreadEntry(kind, title, body, confidence) {
      var te = getThreadEl();
      if (!te) return;
      var hint = labels.threadEmptyHint || '在此查看';
      var first = te.firstElementChild;
      if (first && first.textContent && first.textContent.indexOf(hint) >= 0 && te.children.length === 1) {
        te.innerHTML = '';
      }
      var item = document.createElement('div');
      item.className = (idPrefix || 'rail') + '-thread-entry';
      item.setAttribute('data-kind', kind || '');
      var border =
        kind === 'user'
          ? 'border-left:3px solid var(--accent);padding-left:8px;'
          : 'padding:6px 0;border-bottom:1px solid var(--border);';
      item.style.cssText = border + 'margin-bottom:4px;';
      var header =
        '<strong style="color:' + (kind === 'user' ? 'var(--ink)' : 'var(--accent)') + '">' + escapeHtml(title || '') + '</strong>';
      if (confidence != null) header += ' <span style="color:var(--muted)">(' + Math.round(confidence * 100) + '%)</span>';
      var time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      header += ' <span style="float:right;color:var(--muted);font-size:11px">' + time + '</span>';
      item.innerHTML =
        header +
        '<div style="margin-top:4px;line-height:1.5;color:var(--ink);clear:both">' +
        escapeHtml((body || '').substring(0, 2000)) +
        '</div>';
      te.appendChild(item);
      te.scrollTop = te.scrollHeight;
    }

    function dispatchSseToThread(parsedEvent) {
      var ev = parsedEvent;
      var et = ev.event_type || '';
      var pl = ev.payload || {};
      if (et === 'council_phase') {
        var ph = el(ids.councilPhase);
        if (ph) ph.textContent = pl.label_zh || pl.phase || '';
        return;
      }
      if (et === 'discussion_message') {
        if (councilPostInFlight) return;
        if (pl.role === 'agent' && pl.content) {
          appendThreadEntry('council', ev.agent_name || 'Council', (pl.content || '').substring(0, 200), null);
        }
        return;
      }
      if (et === 'agent_result') {
        var conf = pl.confidence != null ? pl.confidence : null;
        appendThreadEntry('agent', ev.agent_name || ev.agent_role || 'Agent', (pl.explanation || '').substring(0, 2000), conf);
        return;
      }
      if (et === 'object_updated') {
        appendThreadEntry('system', '系统', (ev.object_type || '') + ' 已更新', null);
      }
    }

    function setCouncilFsm(next, detail) {
      councilFsm = next;
      var fsmEl = el(ids.councilFsm);
      if (fsmEl) {
        fsmEl.textContent =
          '状态：' + (COUNCIL_FSM_LABELS[next] || next) + (detail ? ' · ' + detail : '');
      }
      var ph = el(ids.councilPhase);
      if (ph && detail && (next === 'running_collecting' || next === 'running_synthesizing')) {
        ph.textContent = detail;
      }
    }

    function beginCouncilThreadBlock() {
      var te = getThreadEl();
      if (!te) return;
      te.setAttribute('data-council-live', '1');
      appendThreadEntry('phase', 'Council', labels.beginCouncilBanner || '── Council 进行中 ──', null);
    }

    function appendCouncilLiveRow(title, body) {
      appendThreadEntry('council', title, body, null);
    }

    function councilSessionPanel(session) {
      var panel = el(ids.sessionPanel);
      if (!panel || !session) return;
      panel.style.display = 'block';
      var tb = session.timing_breakdown || {};
      panel.innerHTML =
        '<span style="color:var(--muted)">会话</span> ' +
        escapeHtml(session.session_id || '') +
        ' · 总耗时 ' +
        (session.timing_ms != null ? session.timing_ms : '—') +
        'ms' +
        ' · 专家 ' +
        (tb.specialists_ms != null ? tb.specialists_ms : '—') +
        'ms · 综合 ' +
        (tb.synthesis_ms != null ? tb.synthesis_ms : '—') +
        'ms';
    }

    function councilParticipantsPanel(obs) {
      var participantsEl = el(ids.participants);
      if (!participantsEl || !obs || !obs.agents || !obs.agents.length) {
        if (participantsEl) participantsEl.innerHTML = '';
        return;
      }
      var html = '<div style="font-weight:600;margin-bottom:4px;color:var(--ink)">参与者可观测</div>';
      obs.agents.forEach(function (a) {
        var badge = a.degraded ? '<span style="color:#b71c1c">降级</span>' : a.used_llm ? 'LLM' : '规则';
        html +=
          '<div style="display:flex;justify-content:space-between;gap:8px;margin-bottom:4px;font-size:11px;"><span>' +
          escapeHtml(a.agent_id || '') +
          '</span><span>' +
          badge +
          ' · ' +
          (a.timing_ms != null ? a.timing_ms : 0) +
          'ms</span></div>';
      });
      if (obs.synthesis) {
        var syn = obs.synthesis;
        html +=
          '<div style="margin-top:6px;font-size:11px;color:var(--muted)">综合阶段：' +
          (syn.degraded ? '降级 ' : '') +
          (syn.timing_ms != null ? syn.timing_ms : 0) +
          'ms</div>';
      }
      participantsEl.innerHTML = html;
    }

    function councilConsensusPanel(discussion) {
      var consensusEl = el(ids.consensus);
      if (!consensusEl) return;
      var c = discussion && (discussion.consensus || '');
      var ex = discussion && (discussion.executive_summary || '');
      if (!c && !ex) {
        consensusEl.style.display = 'none';
        consensusEl.innerHTML = '';
        return;
      }
      consensusEl.style.display = 'block';
      consensusEl.innerHTML =
        '<div style="font-weight:700;margin-bottom:4px;color:var(--ink)">可执行共识</div>' +
        (c ? '<div style="line-height:1.55">' + escapeHtml(c) + '</div>' : '') +
        (ex ? '<div style="margin-top:6px;color:var(--muted);font-size:11px">摘要：' + escapeHtml(ex) + '</div>' : '');
    }

    function councilDisagreementPanel(discussion) {
      var disagreementsEl = el(ids.disagreements);
      if (!disagreementsEl) return;
      var structured = discussion && discussion.disagreements_structured;
      var flat = discussion && discussion.disagreements;
      var parts = [];
      if (structured && structured.length) {
        structured.forEach(function (d) {
          if (!d || typeof d !== 'object') return;
          var topic = d.topic || d.reason_summary || '';
          parts.push(topic + (d.reason_summary && d.topic ? ' — ' + d.reason_summary : ''));
        });
      }
      if ((!parts || !parts.length) && flat && flat.length) {
        flat.forEach(function (x) {
          if (typeof x === 'string') parts.push(x);
        });
      }
      if (!parts.length) {
        disagreementsEl.style.display = 'none';
        disagreementsEl.innerHTML = '';
        return;
      }
      disagreementsEl.style.display = 'block';
      disagreementsEl.innerHTML =
        '<div style="font-weight:700;margin-bottom:4px;color:var(--ink)">分歧与待决</div>' +
        parts
          .slice(0, 6)
          .map(function (p) {
            return '<div style="margin-bottom:4px;line-height:1.5">· ' + escapeHtml(p) + '</div>';
          })
          .join('');
    }

    function renderCouncilPanelsFromHttp(data) {
      if (data && data.session) councilSessionPanel(data.session);
      if (data && data.observability) councilParticipantsPanel(data.observability);
      if (data && data.discussion) {
        councilConsensusPanel(data.discussion);
        councilDisagreementPanel(data.discussion);
      }
    }

    function handleCouncilSsePayload(raw) {
      try {
        var ev = typeof raw === 'string' ? JSON.parse(raw) : raw;
        var pl = ev.payload || {};
        var oid = ev.object_id || '';
        if (!councilPostInFlight && oid && activeCouncilSessionId && oid !== activeCouncilSessionId) return;

        if (ev.event_type === 'council_session_started') {
          activeCouncilSessionId = pl.session_id || oid || activeCouncilSessionId;
          setCouncilFsm('running_collecting', pl.label || '正在收集各角色观点');
        } else if (ev.event_type === 'council_phase_changed') {
          if (pl.phase === 'synthesizing_consensus') setCouncilFsm('running_synthesizing', pl.label || '正在综合共识');
          else if (pl.phase === 'session_ready') setCouncilFsm('proposal_ready', pl.label || '会话产出已就绪');
          else if (pl.phase === 'collecting_opinions') setCouncilFsm('running_collecting', pl.label || '');
        } else if (ev.event_type === 'council_participant_started') {
          appendCouncilLiveRow(pl.agent_name || pl.agent_id || '参与者', '开始发言…');
        } else if (ev.event_type === 'council_participant_message') {
          var sn = (pl.snippet || '').slice(0, 180);
          appendCouncilLiveRow(pl.agent_name || pl.agent_id || '参与者', sn || '(内容)');
        } else if (ev.event_type === 'council_participant_completed') {
          var st = pl.status === 'failed' ? '失败' : '完成';
          var deg = pl.degraded ? ' · 降级' : '';
          appendCouncilLiveRow(pl.agent_id || '参与者', st + deg + ' · ' + (pl.timing_ms || 0) + 'ms');
        } else if (ev.event_type === 'council_synthesis_started') {
          setCouncilFsm('running_synthesizing', '正在综合共识与分歧');
        } else if (ev.event_type === 'council_synthesis_completed') {
          var syn = (pl.consensus || '').slice(0, 200);
          if (syn) appendCouncilLiveRow('综合共识', syn);
        } else if (ev.event_type === 'council_proposal_ready') {
          setCouncilFsm('proposal_ready', '提案已就绪');
        } else if (ev.event_type === 'council_session_completed') {
          setCouncilFsm('completed', '');
        } else if (ev.event_type === 'council_session_failed') {
          setCouncilFsm('failed', pl.error_message || '');
        }
      } catch (e) {}
    }

    function buildDiscussionHtml(discussion) {
      if (!discussion || !discussion.messages || !discussion.messages.length) {
        return '<span style="color:var(--muted)">暂无讨论过程</span>';
      }
      var html = '';
      (discussion.messages || []).forEach(function (m) {
        if (m.role === 'user') {
          html +=
            '<div style="margin-bottom:8px;"><strong style="color:var(--ink)">你</strong><div style="font-size:12px;line-height:1.5;">' +
            escapeHtml(m.content || '') +
            '</div></div>';
          return;
        }
        if (m.role === 'agent') {
          var meta = m.metadata || {};
          if (meta.status === 'failed') {
            html +=
              '<div style="color:#b71c1c;font-size:12px;margin-bottom:8px;">' +
              escapeHtml(meta.agent_name || m.agent_role || 'Agent') +
              '：' +
              escapeHtml(m.content || '') +
              '</div>';
            return;
          }
          var stance = meta.stance || '';
          var map = { support: '支持', oppose: '反对', neutral: '中立', supplement: '补充' };
          var stanceZh = map[stance] || stance;
          var claim = meta.claim || '';
          html += '<div style="border:1px solid var(--border);border-radius:8px;padding:8px;margin-bottom:8px;font-size:12px;">';
          html +=
            '<div style="display:flex;justify-content:space-between;gap:8px;"><strong>' +
            escapeHtml(meta.agent_name || m.agent_role || 'Agent') +
            '</strong>';
          if (stance) html += '<span style="color:var(--accent);white-space:nowrap;">' + escapeHtml(stanceZh) + '</span>';
          html += '</div>';
          if (claim) html += '<div style="color:var(--muted);margin-top:4px;">' + escapeHtml(claim) + '</div>';
          html +=
            '<details style="margin-top:6px;"><summary style="cursor:pointer">全文</summary><div style="margin-top:6px;line-height:1.5;">' +
            escapeHtml(m.content || '') +
            '</div></details>';
          html += '</div>';
          return;
        }
        if (m.role === 'system' || (m.metadata && m.metadata.type === 'consensus')) {
          html +=
            '<div style="background:var(--bg-subtle,#f5f5f5);padding:8px;border-radius:8px;font-size:12px;margin-top:4px;"><strong>共识</strong><div style="margin-top:4px;line-height:1.5;">' +
            escapeHtml(m.content || '') +
            '</div></div>';
        }
      });
      return html || '<span style="color:var(--muted)">暂无</span>';
    }

    function renderDiscussion(discussion) {
      var te = getThreadEl();
      if (!te) return;
      te.removeAttribute('data-council-live');
      var finalId = ids.finalTranscript || idPrefix + '-council-final-transcript';
      var prev = el(finalId);
      if (prev) prev.remove();
      var inner = buildDiscussionHtml(discussion);
      var wrap = document.createElement('div');
      wrap.id = finalId;
      wrap.style.cssText = 'margin-top:10px;padding-top:10px;border-top:1px dashed var(--border);';
      wrap.innerHTML =
        '<details style="border-radius:6px;">' +
        '<summary style="cursor:pointer;margin-bottom:0;font-size:12px;font-weight:600;color:var(--muted);">展开：服务端完整讨论记录</summary>' +
        '<div style="font-size:12px;max-height:240px;overflow-y:auto;margin-top:8px;">' +
        inner +
        '</div></details>';
      te.appendChild(wrap);
      te.scrollTop = te.scrollHeight;
    }

    function wireCouncilButton() {
      var btn = el(ids.councilBtn);
      var q = el(ids.councilQuestion);
      if (!btn || !q) return;
      btn.addEventListener('click', function () {
        var question = (q.value || '').trim();
        if (!question) {
          setCouncilStatus('请先输入问题', true);
          return;
        }
        setCouncilFsm('submitting', '');
        councilPostInFlight = true;
        activeCouncilSessionId = '';
        appendThreadEntry('user', labels.userCouncilTitle || '你 · Council', question, null);
        beginCouncilThreadBlock();
        setCouncilStatus(labels.councilRunningStatus || 'Council 讨论中…', false);
        var url =
          apiPrefix + '/stages/' + stage + '/' + encodeURIComponent(opportunityId) + '/discussions';
        fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: question, include_chat_context: true })
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            activeCouncilSessionId = data.run_id || (data.session && data.session.session_id) || activeCouncilSessionId;
            renderCouncilPanelsFromHttp(data);
            if (data.discussion) renderDiscussion(data.discussion);
            if (config.onCouncilHttpComplete) config.onCouncilHttpComplete(data);
            setCouncilFsm('completed', '');
            var ph = el(ids.councilPhase);
            if (ph) ph.textContent = '';
          })
          .catch(function (err) {
            setCouncilStatus('讨论失败', true);
            setCouncilFsm('failed', '');
            if (config.onCouncilHttpError) config.onCouncilHttpError(err);
          })
          .finally(function () {
            councilPostInFlight = false;
          });
      });
    }

    function wireChatToCouncil() {
      var chatToCouncil = el(ids.chatToCouncil);
      if (!chatToCouncil) return;
      chatToCouncil.addEventListener('click', function () {
        var tl = getThreadEl();
        var lastLine = '';
        if (tl && tl.lastElementChild) lastLine = tl.lastElementChild.innerText || '';
        var ta = el(ids.councilQuestion);
        if (ta) {
          var hint = labels.chatToCouncilHint || '请将上一句对话结论转为可决策问题：';
          ta.value = lastLine ? hint + '\n' + lastLine : hint;
          ta.focus();
        }
        setCouncilStatus(labels.chatToCouncilStatus || '已预填 Council 问题，可编辑后发起', false);
      });
    }

    function sendChat() {
      var chatInput = el(ids.chatInput);
      var chatStatus = el(ids.chatStatus);
      var msg = chatInput ? chatInput.value.trim() : '';
      if (!msg) return;
      appendThreadEntry('user', labels.userChatTitle || '你', msg, null);
      if (chatInput) chatInput.value = '';
      if (chatStatus) chatStatus.textContent = labels.chatThinkingStatus || 'Agent 思考中…';
      var chatUrl = apiPrefix + '/chat/' + encodeURIComponent(opportunityId);
      fetch(chatUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: msg,
          role: 'human',
          current_stage: chatCurrentStage,
          mode: 'fast'
        })
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (chatStatus) chatStatus.textContent = '';
          appendThreadEntry('agent', data.agent_name || 'Agent', data.explanation || '无回复', data.confidence);
        })
        .catch(function () {
          if (chatStatus) chatStatus.textContent = labels.chatSendFailed || '发送失败';
        });
    }

    function wireChat() {
      var chatSend = el(ids.chatSend);
      var chatInput = el(ids.chatInput);
      if (chatSend) chatSend.addEventListener('click', sendChat);
      if (chatInput) {
        chatInput.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChat();
          }
        });
      }
    }

    function wireSse() {
      scheduleDeferred(function () {
        try {
          var streamPath = config.sseStreamPath || apiPrefix + '/stream/' + encodeURIComponent(opportunityId);
          evtSource = new EventSource(streamPath);
          evtSource.addEventListener('agent_result', function (e) {
            try {
              dispatchSseToThread(JSON.parse(e.data));
            } catch (err) {}
          });
          evtSource.addEventListener('object_updated', function (e) {
            try {
              dispatchSseToThread(JSON.parse(e.data));
            } catch (err) {}
          });
          evtSource.addEventListener('council_phase', function (e) {
            try {
              dispatchSseToThread(JSON.parse(e.data));
            } catch (err) {}
          });
          evtSource.addEventListener('discussion_message', function (e) {
            try {
              dispatchSseToThread(JSON.parse(e.data));
            } catch (err) {}
          });
          COUNCIL_SSE_NAMES.forEach(function (name) {
            evtSource.addEventListener(name, function (e) {
              try {
                handleCouncilSsePayload(JSON.parse(e.data));
              } catch (err) {}
            });
          });
          evtSource.onerror = function () {
            var te = getThreadEl();
            if (te) {
              var div = document.createElement('div');
              div.style.cssText = 'color:var(--muted);font-size:11px;padding:4px 0;';
              div.textContent = labels.sseErrorHint || 'SSE 连接中断，刷新页面重连';
              te.appendChild(div);
            }
          };
        } catch (err) {}
      }, 40);
    }

    wireCouncilButton();
    wireChat();
    wireChatToCouncil();
    wireSse();

    return {
      appendThreadEntry: appendThreadEntry,
      renderDiscussion: renderDiscussion,
      renderCouncilPanelsFromHttp: renderCouncilPanelsFromHttp,
      getCouncilPostInFlight: function () {
        return councilPostInFlight;
      },
      destroy: function () {
        if (evtSource) {
          try {
            evtSource.close();
          } catch (e) {}
          evtSource = null;
        }
      }
    };
  }

  global.CouncilRightRail = { init: initCouncilRightRail };
})(typeof window !== 'undefined' ? window : this);
