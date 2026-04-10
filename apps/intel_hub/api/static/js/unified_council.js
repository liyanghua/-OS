/**
 * unified_council.js — 统一 Council 面板组件
 *
 * 合并 Brief 内联 JS、council_right_rail.js、Assets 内联 JS 三套实现。
 * 纯 vanilla JS，无外部依赖，所有 DOM 操作使用 createElement，不用 innerHTML。
 *
 * 用法:
 *   window.UnifiedCouncil.init({
 *     stage: 'brief',
 *     opportunityId: '...',
 *     container: document.getElementById('council-root'),
 *     onProposalApplied: function(data) { ... }
 *   });
 *   // 页面卸载前:
 *   window.UnifiedCouncil.destroy();
 */
(function (global) {
  'use strict';

  var API_PREFIX = '/content-planning';
  var SSE_RECONNECT_MS = 5000;

  var STATUS_LABELS = {
    idle:         '待命',
    working:      '进行中',
    consensus:    '已形成共识',
    disagreement: '存在分歧',
    complete:     '已完成',
    failed:       '失败'
  };

  var STAGE_ZH = {
    brief:    'Brief',
    strategy: 'Strategy',
    plan:     'Plan',
    asset:    'Asset'
  };

  /* ── 工具函数 ── */

  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function txt(text) {
    return document.createTextNode(text != null ? String(text) : '');
  }

  function el(tag, cls, styles) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (styles) node.style.cssText = styles;
    return node;
  }

  function appendChildren(parent, children) {
    for (var i = 0; i < children.length; i++) {
      if (typeof children[i] === 'string') {
        parent.appendChild(txt(children[i]));
      } else if (children[i]) {
        parent.appendChild(children[i]);
      }
    }
    return parent;
  }

  function btn(label, cls, onClick) {
    var b = el('button', cls, '');
    b.type = 'button';
    b.appendChild(txt(label));
    if (onClick) b.addEventListener('click', onClick);
    return b;
  }

  function clearNode(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function timeStr() {
    return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }

  async function api(method, path, body) {
    var opts = {
      method: method,
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    var resp = await fetch(API_PREFIX + path, opts);
    var data = await resp.json();
    if (!resp.ok) {
      var detail = data && data.detail;
      var msg = typeof detail === 'string' ? detail : (detail && detail.message ? detail.message : 'HTTP ' + resp.status);
      throw new Error(msg);
    }
    return data;
  }

  /* ── 注入最小样式（仅执行一次） ── */

  var styleInjected = false;
  function injectStyles() {
    if (styleInjected) return;
    styleInjected = true;
    var css = [
      '.uc-panel{font-family:inherit;font-size:13px;color:var(--ink,#222);line-height:1.55}',
      '.uc-section{border:1px solid var(--border,#e5e0d8);border-radius:14px;padding:14px;margin-bottom:12px;background:var(--surface,#fffdf8)}',
      '.uc-section-title{margin:0 0 10px;font-size:13px;font-weight:700;color:var(--accent,#8a4b2f)}',
      '.uc-status-bar{display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:12px;margin-bottom:12px;font-size:12px;font-weight:600}',
      '.uc-status-idle{background:#f5f5f5;color:#757575}',
      '.uc-status-working{background:#fff7ed;color:#9a3412}',
      '.uc-status-consensus{background:#dcfce7;color:#166534}',
      '.uc-status-disagreement{background:#fef2f2;color:#991b1b}',
      '.uc-status-complete{background:#dbeafe;color:#1e40af}',
      '.uc-status-failed{background:#fef2f2;color:#b71c1c}',
      '.uc-discussion{margin-bottom:12px}',
      '.uc-discussion textarea{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid var(--border,#e5e0d8);border-radius:12px;font:inherit;font-size:13px;resize:vertical;min-height:68px;background:var(--surface,#fff);color:var(--ink,#222)}',
      '.uc-discussion-actions{display:flex;gap:8px;margin-top:8px}',
      '.uc-btn{display:inline-flex;align-items:center;justify-content:center;padding:8px 16px;border:none;border-radius:12px;font:inherit;font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap}',
      '.uc-btn:disabled{opacity:.5;cursor:not-allowed}',
      '.uc-btn-primary{background:var(--accent,#8a4b2f);color:#fff}',
      '.uc-btn-secondary{background:var(--accent-soft,#f3ebe4);color:var(--accent,#8a4b2f);border:1px solid rgba(138,75,47,.2)}',
      '.uc-btn-danger{background:#fee2e2;color:#991b1b}',
      '.uc-result-area{max-height:320px;overflow-y:auto;border:1px solid var(--border,#e5e0d8);border-radius:10px;padding:10px;background:var(--bg-subtle,#fafafa);font-size:12px}',
      '.uc-msg{padding:8px 0;border-bottom:1px solid var(--border,#e5e0d8)}',
      '.uc-msg:last-child{border-bottom:none}',
      '.uc-msg-header{display:flex;justify-content:space-between;gap:8px;margin-bottom:4px}',
      '.uc-msg-name{font-weight:700;color:var(--accent,#8a4b2f)}',
      '.uc-msg-name.user{color:var(--ink,#222)}',
      '.uc-msg-time{font-size:11px;color:var(--muted,#999)}',
      '.uc-msg-body{line-height:1.55;color:var(--ink,#222)}',
      '.uc-msg-conf{font-size:11px;color:var(--muted,#999);margin-left:6px}',
      '.uc-proposal{margin-bottom:12px}',
      '.uc-proposal-group{margin-bottom:10px}',
      '.uc-proposal-group-title{font-size:12px;font-weight:700;color:var(--accent,#8a4b2f);margin-bottom:6px}',
      '.uc-diff-item{display:flex;gap:8px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--border,#e5e0d8);font-size:12px}',
      '.uc-diff-field{font-weight:600;color:var(--ink,#222)}',
      '.uc-diff-before{color:#b71c1c;text-decoration:line-through}',
      '.uc-diff-after{color:#2e7d32}',
      '.uc-score{margin-bottom:12px}',
      '.uc-score-row{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(138,75,47,.08);font-size:12px}',
      '.uc-agent{margin-bottom:12px}'
    ].join('\n');
    var styleEl = document.createElement('style');
    styleEl.setAttribute('data-uc', '1');
    styleEl.appendChild(txt(css));
    document.head.appendChild(styleEl);
  }

  /* ── 主组件 ── */

  var instance = null;

  function init(config) {
    if (instance) instance._teardown();

    if (!config || !config.container || !config.opportunityId) {
      throw new Error('UnifiedCouncil.init: container 和 opportunityId 必填');
    }

    injectStyles();

    var stage = config.stage || 'brief';
    var oid = config.opportunityId;
    var container = config.container;
    var onProposalApplied = config.onProposalApplied || null;

    var councilStatus = 'idle';
    var currentProposalId = '';
    var evtSource = null;
    var reconnectTimer = null;

    /* refs */
    var statusBarEl, statusLabelEl, statusDetailEl;
    var discussionInput, discussionResultEl;
    var proposalDiffEl, proposalActionsEl, applyBtn, rejectBtn;
    var scoreContentEl;
    var agentResultEl;

    /* ── 构建 DOM ── */

    clearNode(container);
    var panel = el('div', 'uc-panel');
    container.appendChild(panel);

    // 1. 状态栏
    var statusSection = buildStatusBar();
    panel.appendChild(statusSection);

    // 2. 讨论区
    panel.appendChild(buildDiscussionSection());

    // 3. Proposal 区
    panel.appendChild(buildProposalSection());

    // 4. 评分区
    panel.appendChild(buildScoreSection());

    // 5. Agent 结果区
    panel.appendChild(buildAgentSection());

    /* ── 构建各区域 ── */

    function buildStatusBar() {
      statusBarEl = el('div', 'uc-status-bar uc-status-idle');
      statusLabelEl = el('span', '', 'font-weight:700');
      statusLabelEl.appendChild(txt(STAGE_ZH[stage] + ' Council'));
      statusDetailEl = el('span', '', 'margin-left:auto;font-size:11px');
      statusDetailEl.appendChild(txt(STATUS_LABELS.idle));
      appendChildren(statusBarEl, [statusLabelEl, statusDetailEl]);
      return statusBarEl;
    }

    function buildDiscussionSection() {
      var sec = el('div', 'uc-section uc-discussion');
      var title = el('div', 'uc-section-title');
      title.appendChild(txt('Council 讨论'));
      sec.appendChild(title);

      discussionInput = document.createElement('textarea');
      discussionInput.className = '';
      discussionInput.placeholder = '围绕当前 ' + (STAGE_ZH[stage] || stage) + ' 提问，例如：请评估当前策略的核心风险…';
      discussionInput.rows = 3;
      discussionInput.style.cssText = 'width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid var(--border,#e5e0d8);border-radius:12px;font:inherit;font-size:13px;resize:vertical;min-height:68px;background:var(--surface,#fff);color:var(--ink,#222)';
      sec.appendChild(discussionInput);

      var actions = el('div', '', 'display:flex;gap:8px;margin-top:8px');
      var startBtn = btn('发起讨论', 'uc-btn uc-btn-primary', onStartDiscussion);
      var evalBtn = btn('运行评价', 'uc-btn uc-btn-secondary', onRunEvaluation);
      appendChildren(actions, [startBtn, evalBtn]);
      sec.appendChild(actions);

      discussionResultEl = el('div', 'uc-result-area', 'margin-top:10px');
      var placeholder = el('div', '', 'color:var(--muted,#999);font-size:12px');
      placeholder.appendChild(txt('讨论结果将在此展示…'));
      discussionResultEl.appendChild(placeholder);
      sec.appendChild(discussionResultEl);

      return sec;
    }

    function buildProposalSection() {
      var sec = el('div', 'uc-section uc-proposal');
      var title = el('div', 'uc-section-title');
      title.appendChild(txt('Proposal'));
      sec.appendChild(title);

      proposalDiffEl = el('div', '', '');
      var emptyMsg = el('div', '', 'color:var(--muted,#999);font-size:12px');
      emptyMsg.appendChild(txt('暂无 proposal'));
      proposalDiffEl.appendChild(emptyMsg);
      sec.appendChild(proposalDiffEl);

      proposalActionsEl = el('div', '', 'display:flex;gap:8px;margin-top:10px');
      proposalActionsEl.style.display = 'none';

      applyBtn = btn('应用变更', 'uc-btn uc-btn-primary', onApplyProposal);
      rejectBtn = btn('拒绝', 'uc-btn uc-btn-danger', onRejectProposal);
      appendChildren(proposalActionsEl, [applyBtn, rejectBtn]);
      sec.appendChild(proposalActionsEl);

      return sec;
    }

    function buildScoreSection() {
      var sec = el('div', 'uc-section uc-score');
      var title = el('div', 'uc-section-title');
      title.appendChild(txt('评分'));
      sec.appendChild(title);

      scoreContentEl = el('div', '', 'font-size:12px;color:var(--muted,#999)');
      scoreContentEl.appendChild(txt('暂无评分'));
      sec.appendChild(scoreContentEl);

      return sec;
    }

    function buildAgentSection() {
      var sec = el('div', 'uc-section uc-agent');
      var title = el('div', 'uc-section-title');
      title.appendChild(txt('Agent 结果'));
      sec.appendChild(title);

      agentResultEl = el('div', 'uc-result-area', '');
      var placeholder = el('div', '', 'color:var(--muted,#999);font-size:12px');
      placeholder.appendChild(txt('等待 Agent 事件…'));
      agentResultEl.appendChild(placeholder);
      sec.appendChild(agentResultEl);

      return sec;
    }

    /* ── 状态管理 ── */

    function setStatus(newStatus, detail) {
      councilStatus = newStatus;
      statusBarEl.className = 'uc-status-bar uc-status-' + newStatus;
      clearNode(statusDetailEl);
      var label = STATUS_LABELS[newStatus] || newStatus;
      if (detail) label += ' · ' + detail;
      statusDetailEl.appendChild(txt(label));
    }

    /* ── 讨论区消息 ── */

    function appendDiscussionMsg(role, name, body, confidence) {
      if (discussionResultEl.children.length === 1 &&
          discussionResultEl.firstChild.textContent.indexOf('讨论结果') >= 0) {
        clearNode(discussionResultEl);
      }
      var msg = el('div', 'uc-msg');
      var header = el('div', 'uc-msg-header');
      var nameEl = el('span', 'uc-msg-name' + (role === 'user' ? ' user' : ''));
      nameEl.appendChild(txt(name || ''));
      if (confidence != null) {
        var confEl = el('span', 'uc-msg-conf');
        confEl.appendChild(txt(Math.round(confidence * 100) + '%'));
        appendChildren(header, [nameEl, confEl]);
      } else {
        header.appendChild(nameEl);
      }
      var timeEl = el('span', 'uc-msg-time');
      timeEl.appendChild(txt(timeStr()));
      header.appendChild(timeEl);
      msg.appendChild(header);

      var bodyEl = el('div', 'uc-msg-body');
      bodyEl.appendChild(txt(String(body || '').substring(0, 2000)));
      msg.appendChild(bodyEl);

      discussionResultEl.appendChild(msg);
      discussionResultEl.scrollTop = discussionResultEl.scrollHeight;
    }

    function renderConsensusBlock(discussion) {
      if (!discussion) return;
      var consensus = discussion.consensus || discussion.executive_summary;
      if (consensus) {
        var block = el('div', 'uc-msg', 'background:#dcfce7;border-radius:10px;padding:10px;margin-top:6px');
        var hdr = el('div', '', 'font-weight:700;font-size:12px;color:#166534;margin-bottom:4px');
        hdr.appendChild(txt('共识'));
        block.appendChild(hdr);
        var body = el('div', 'uc-msg-body');
        body.appendChild(txt(consensus));
        block.appendChild(body);
        discussionResultEl.appendChild(block);
      }

      var disagreements = discussion.disagreements_structured || discussion.disagreements;
      if (disagreements && disagreements.length) {
        var dBlock = el('div', 'uc-msg', 'background:#fef2f2;border-radius:10px;padding:10px;margin-top:6px');
        var dHdr = el('div', '', 'font-weight:700;font-size:12px;color:#991b1b;margin-bottom:4px');
        dHdr.appendChild(txt('分歧'));
        dBlock.appendChild(dHdr);
        for (var i = 0; i < Math.min(disagreements.length, 6); i++) {
          var item = disagreements[i];
          var text = typeof item === 'string' ? item : (item.topic || item.reason_summary || '');
          if (!text) continue;
          var line = el('div', '', 'margin-bottom:4px;line-height:1.5;font-size:12px');
          line.appendChild(txt('· ' + text));
          dBlock.appendChild(line);
        }
        discussionResultEl.appendChild(dBlock);
      }

      discussionResultEl.scrollTop = discussionResultEl.scrollHeight;
    }

    /* ── Proposal 渲染 ── */

    function renderProposal(proposal) {
      clearNode(proposalDiffEl);
      if (!proposal || !proposal.diff || !proposal.diff.changes || !proposal.diff.changes.length) {
        var empty = el('div', '', 'color:var(--muted,#999);font-size:12px');
        empty.appendChild(txt(proposal ? 'proposal 无字段变化' : '暂无 proposal'));
        proposalDiffEl.appendChild(empty);
        proposalActionsEl.style.display = 'none';
        return;
      }

      currentProposalId = proposal.proposal_id || '';

      if (proposal.summary) {
        var summaryEl = el('div', '', 'font-size:12px;color:var(--ink,#222);margin-bottom:10px;line-height:1.55');
        summaryEl.appendChild(txt(proposal.summary));
        proposalDiffEl.appendChild(summaryEl);
      }

      var changes = proposal.diff.changes;
      for (var i = 0; i < changes.length; i++) {
        var change = changes[i];
        var row = el('div', 'uc-diff-item');

        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = change.field;
        cb.checked = !change.blocked;
        cb.disabled = !!change.blocked;
        cb.className = 'uc-proposal-cb';
        cb.style.cssText = 'margin-top:2px;flex-shrink:0';
        row.appendChild(cb);

        var content = el('div', '', 'flex:1;min-width:0');
        var fieldName = el('div', 'uc-diff-field');
        fieldName.appendChild(txt(change.field));
        if (change.blocked) {
          var lockBadge = el('span', '', 'color:#b71c1c;font-size:11px;margin-left:4px');
          lockBadge.appendChild(txt('(locked)'));
          fieldName.appendChild(lockBadge);
        }
        content.appendChild(fieldName);

        var before = el('div', 'uc-diff-before');
        before.appendChild(txt('- ' + JSON.stringify(change.before)));
        content.appendChild(before);

        var after = el('div', 'uc-diff-after');
        after.appendChild(txt('+ ' + JSON.stringify(change.after)));
        content.appendChild(after);

        row.appendChild(content);
        proposalDiffEl.appendChild(row);
      }

      proposalActionsEl.style.display = currentProposalId ? 'flex' : 'none';
    }

    /* ── 评分渲染 ── */

    function renderScorecard(evalItem, baseline) {
      clearNode(scoreContentEl);
      if (!evalItem || !evalItem.payload) {
        scoreContentEl.appendChild(txt('暂无评分'));
        return;
      }
      var p = evalItem.payload;
      var overall = el('div', '', 'font-size:13px;font-weight:700;color:var(--ink,#222);margin-bottom:8px');
      overall.appendChild(txt('当前分数 ' + Math.round((p.overall_score || 0) * 100) + '/100'));
      scoreContentEl.appendChild(overall);

      if (baseline && baseline.rubric_version === p.rubric_version) {
        var delta = (p.overall_score || 0) - (baseline.overall_score || 0);
        var deltaEl = el('div', '', 'font-size:12px;margin-bottom:8px;color:' + (delta >= 0 ? '#166534' : '#b91c1c'));
        deltaEl.appendChild(txt('Baseline ' + Math.round((baseline.overall_score || 0) * 100) + '/100 · \u0394 ' + (delta >= 0 ? '+' : '') + Math.round(delta * 100)));
        scoreContentEl.appendChild(deltaEl);
      }

      var dims = p.dimensions || [];
      for (var i = 0; i < dims.length; i++) {
        var row = el('div', 'uc-score-row');
        var dimName = el('span', '');
        dimName.appendChild(txt(dims[i].name_zh || dims[i].name || ''));
        var dimScore = el('strong', '');
        dimScore.appendChild(txt(String(Math.round((dims[i].score || 0) * 100))));
        appendChildren(row, [dimName, dimScore]);
        scoreContentEl.appendChild(row);
      }

      if (p.explanation) {
        var explEl = el('div', '', 'margin-top:8px;color:var(--muted,#999);line-height:1.5;font-size:12px');
        explEl.appendChild(txt(p.explanation));
        scoreContentEl.appendChild(explEl);
      }
    }

    /* ── Agent 结果区 ── */

    function appendAgentResult(name, explanation, confidence) {
      if (agentResultEl.children.length === 1 &&
          agentResultEl.firstChild.textContent.indexOf('等待') >= 0) {
        clearNode(agentResultEl);
      }
      var msg = el('div', 'uc-msg');
      var header = el('div', 'uc-msg-header');
      var nameEl = el('span', 'uc-msg-name');
      nameEl.appendChild(txt(name || 'Agent'));
      header.appendChild(nameEl);
      if (confidence != null) {
        var confEl = el('span', 'uc-msg-conf');
        confEl.appendChild(txt(Math.round(confidence * 100) + '%'));
        header.appendChild(confEl);
      }
      var timeEl = el('span', 'uc-msg-time');
      timeEl.appendChild(txt(timeStr()));
      header.appendChild(timeEl);
      msg.appendChild(header);

      var bodyEl = el('div', 'uc-msg-body');
      bodyEl.appendChild(txt(String(explanation || '').substring(0, 2000)));
      msg.appendChild(bodyEl);

      agentResultEl.appendChild(msg);
      agentResultEl.scrollTop = agentResultEl.scrollHeight;
    }

    /* ── API 操作 ── */

    async function onStartDiscussion() {
      var question = (discussionInput.value || '').trim();
      if (!question) return;

      setStatus('working', '讨论中…');
      appendDiscussionMsg('user', '你', question, null);
      discussionInput.value = '';

      try {
        var data = await api('POST',
          '/stages/' + stage + '/' + encodeURIComponent(oid) + '/discussions',
          { question: question, include_chat_context: true }
        );

        if (data.discussion) {
          var msgs = data.discussion.messages || [];
          for (var i = 0; i < msgs.length; i++) {
            var m = msgs[i];
            if (m.role === 'user') continue;
            var meta = m.metadata || {};
            appendDiscussionMsg(
              m.role,
              meta.agent_name || m.agent_role || 'Agent',
              m.content || '',
              meta.confidence != null ? meta.confidence : null
            );
          }
          renderConsensusBlock(data.discussion);
        }

        if (data.proposal) {
          renderProposal(data.proposal);
          setStatus('consensus', 'Proposal 已就绪');
        } else {
          setStatus('complete');
        }
      } catch (err) {
        setStatus('failed', err.message);
        appendDiscussionMsg('system', '系统', '讨论失败: ' + err.message, null);
      }
    }

    async function onRunEvaluation() {
      setStatus('working', '评价运行中…');
      try {
        await api('POST', '/evaluations/' + stage + '/' + encodeURIComponent(oid) + '/run');
        await loadScorecard();
        setStatus('complete', '评价完成');
      } catch (err) {
        setStatus('failed', '评价失败: ' + err.message);
      }
    }

    async function onApplyProposal() {
      if (!currentProposalId) return;
      var selected = [];
      var cbs = proposalDiffEl.querySelectorAll('.uc-proposal-cb:checked');
      for (var i = 0; i < cbs.length; i++) selected.push(cbs[i].value);
      if (!selected.length) return;

      applyBtn.disabled = true;
      setStatus('working', '应用 proposal…');
      try {
        var data = await api('POST',
          '/proposals/' + encodeURIComponent(currentProposalId) + '/apply',
          { selected_fields: selected }
        );
        setStatus('complete', '已应用: ' + (data.applied_fields || selected).join(', '));
        proposalActionsEl.style.display = 'none';
        if (onProposalApplied) onProposalApplied(data);
      } catch (err) {
        setStatus('failed', '应用失败: ' + err.message);
      } finally {
        applyBtn.disabled = false;
      }
    }

    async function onRejectProposal() {
      if (!currentProposalId) return;
      rejectBtn.disabled = true;
      try {
        await api('POST',
          '/proposals/' + encodeURIComponent(currentProposalId) + '/reject'
        );
        setStatus('idle', 'Proposal 已拒绝');
        clearNode(proposalDiffEl);
        var emptyMsg = el('div', '', 'color:var(--muted,#999);font-size:12px');
        emptyMsg.appendChild(txt('proposal 已拒绝'));
        proposalDiffEl.appendChild(emptyMsg);
        proposalActionsEl.style.display = 'none';
        currentProposalId = '';
      } catch (err) {
        setStatus('failed', '拒绝失败: ' + err.message);
      } finally {
        rejectBtn.disabled = false;
      }
    }

    async function loadScorecard() {
      try {
        var data = await api('GET', '/evaluations/' + encodeURIComponent(oid));
        var items = data.items || [];
        var latest = null;
        var baseline = null;
        for (var i = 0; i < items.length; i++) {
          var it = items[i];
          if (!latest && it.eval_type === 'stage_run' && it.payload && it.payload.stage === stage) {
            latest = it;
          }
          if (!baseline && it.eval_type === 'baseline' && it.payload && it.payload.stage_scores && it.payload.stage_scores[stage]) {
            baseline = it.payload.stage_scores[stage];
          }
        }
        renderScorecard(latest, baseline);
      } catch (_) {
        renderScorecard(null, null);
      }
    }

    /* ── SSE ── */

    function connectSse() {
      if (evtSource) return;
      try {
        var url = API_PREFIX + '/stream/' + encodeURIComponent(oid);
        evtSource = new EventSource(url);

        evtSource.addEventListener('agent_result', function (e) {
          try {
            var d = JSON.parse(e.data);
            var p = d.payload || {};
            appendAgentResult(d.agent_name || d.agent_role, p.explanation, p.confidence);
          } catch (_) {}
        });

        evtSource.addEventListener('council_session_started', function () {
          setStatus('working', '收集各角色观点');
        });

        evtSource.addEventListener('council_phase_changed', function (e) {
          try {
            var d = JSON.parse(e.data);
            var p = d.payload || {};
            if (p.phase === 'synthesizing_consensus') {
              setStatus('working', '正在综合共识');
            } else if (p.phase === 'session_ready') {
              setStatus('consensus', '会话产出已就绪');
            }
          } catch (_) {}
        });

        evtSource.addEventListener('council_participant_message', function (e) {
          try {
            var d = JSON.parse(e.data);
            var p = d.payload || {};
            var snippet = (p.snippet || '').substring(0, 180);
            if (snippet) {
              appendDiscussionMsg('agent', p.agent_name || p.agent_id || '参与者', snippet, null);
            }
          } catch (_) {}
        });

        evtSource.addEventListener('council_synthesis_completed', function (e) {
          try {
            var d = JSON.parse(e.data);
            var p = d.payload || {};
            if (p.consensus) {
              appendDiscussionMsg('system', '综合共识', p.consensus, null);
            }
          } catch (_) {}
        });

        evtSource.addEventListener('council_proposal_ready', function () {
          setStatus('consensus', '提案已就绪');
        });

        evtSource.addEventListener('council_session_completed', function () {
          setStatus('complete');
        });

        evtSource.addEventListener('council_session_failed', function (e) {
          try {
            var d = JSON.parse(e.data);
            var msg = (d.payload || {}).error_message || '';
            setStatus('failed', msg);
          } catch (_) {
            setStatus('failed');
          }
        });

        var sseEventNames = [
          'council_agents_working', 'council_consensus_ready',
          'council_disagreement_detected', 'council_complete',
          'discussion_message', 'object_updated'
        ];
        for (var i = 0; i < sseEventNames.length; i++) {
          (function (evName) {
            evtSource.addEventListener(evName, function (e) {
              try {
                var d = JSON.parse(e.data);
                handleGenericSse(evName, d);
              } catch (_) {}
            });
          })(sseEventNames[i]);
        }

        evtSource.onerror = function () {
          closeSse();
          reconnectTimer = setTimeout(connectSse, SSE_RECONNECT_MS);
        };
      } catch (_) {}
    }

    function handleGenericSse(evName, data) {
      var p = data.payload || {};
      if (evName === 'council_agents_working') {
        setStatus('working', '多 Agent 协同中');
      } else if (evName === 'council_consensus_ready') {
        setStatus('consensus', '共识已形成');
      } else if (evName === 'council_disagreement_detected') {
        setStatus('disagreement', p.topic || '');
      } else if (evName === 'council_complete') {
        setStatus('complete');
      } else if (evName === 'discussion_message') {
        if (p.role === 'agent' && p.content) {
          appendDiscussionMsg('agent', data.agent_name || 'Council', p.content.substring(0, 200), null);
        }
      } else if (evName === 'object_updated') {
        appendAgentResult('系统', (data.object_type || '') + ' 已更新', null);
      }
    }

    function closeSse() {
      if (evtSource) {
        try { evtSource.close(); } catch (_) {}
        evtSource = null;
      }
    }

    /* ── 初始化加载 ── */

    setTimeout(function () {
      connectSse();
      loadScorecard();
    }, 50);

    /* ── 实例暴露 ── */

    function teardown() {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      closeSse();
      clearNode(container);
    }

    instance = {
      _teardown: teardown,
      setStatus: setStatus,
      appendDiscussionMsg: appendDiscussionMsg,
      appendAgentResult: appendAgentResult,
      renderProposal: renderProposal,
      renderScorecard: renderScorecard,
      loadScorecard: loadScorecard,
      destroy: teardown
    };

    return instance;
  }

  function destroy() {
    if (instance) {
      instance._teardown();
      instance = null;
    }
  }

  global.UnifiedCouncil = {
    init: init,
    destroy: destroy
  };

})(typeof window !== 'undefined' ? window : this);
