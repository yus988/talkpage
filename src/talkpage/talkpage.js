/* talkpage client. Elements marked data-talk="<id>" get status buttons and a comment thread kept by the talkpage
   server (talkpage.py, in <page>.talk.json beside the page); the agent's replies appear in place. Elements marked
   data-copy get a copy button. Loaded from the server at /_talk/talkpage.js; see README.md. The text is English or
   Japanese by the page's <html lang> (else the browser's language).
   Reports (data-talk-report on this <script> or on <body>): the user selects text of the report to comment on it (a
   card in the right margin), a sidebar lists the reports (/_talk/api/reports) and the headings of the page, and a
   "read" item ends the report. data-talk-select="<prefix>" and <body data-talk-sidebar> give those parts alone. */
(function () {
  'use strict';
  var API = '/_talk/api/';
  var html = document.documentElement;
  var script = document.currentScript;    // only while this file runs (also when deferred)
  var REPORT = !!(script && script.hasAttribute('data-talk-report')), SIDEBAR = false;
  var page = html.getAttribute('data-talk-page') || decodeURIComponent(location.pathname).replace(/^\/+/, '');
  if (!page || /\/$/.test(page)) page += 'index.html';
  var TONES = { OK: 'ok', '了承': 'ok', '済': 'ok', '完了': 'ok', NG: 'ng', '要修正': 'ng',
                '飛ばし': 'skip', 'スキップ': 'skip', '対象外': 'skip' };
  var TEXT = {
    en: {
      'presence.listening': 'Agent: listening',
      'presence.listening.title': 'Statuses and comments reach the agent right away',
      'presence.working': 'Agent: working',
      'presence.working.title': 'The agent is working on what it received. What you write now is saved and reaches it when it listens again',
      'presence.absent': 'Agent: not waiting',
      'presence.absent.title': 'What you write is saved and reaches the agent when it starts waiting',
      'presence.down': 'Server offline',
      'presence.down.title': 'Cannot reach the talkpage server. What you write now is not saved',
      'mark.new': 'New reply',
      'mark.wait': 'Unread by agent',
      'mark.read': 'Read by agent',
      'mark.err': 'Not saved',
      'mark.wait.title': 'The agent has not read what you wrote yet',
      'mark.short.new': 'New reply',
      'mark.short.wait': 'AI unread',
      'mark.short.read': 'AI read',
      'mark.short.err': 'Not saved',
      'comment': 'Comment',
      'comment.ph': 'Comment (Ctrl+Enter sends)',
      'send': 'Send',
      'send.title': 'Send (Ctrl+Enter)',
      'thread.toggle': 'Show or hide the thread',
      'shrink': 'Back to the card',
      'edit': 'Edit',
      'edit.title': 'Fix the text in place: each block is saved when you leave it or press Enter; Esc puts it back',
      'edit.one.title': 'Fix this block in place (Enter or a click elsewhere saves, Esc puts it back)',
      'pic.note': '{z}%  Wheel to zoom, drag to move, click or Esc to close',
      'edit.saving': 'Saving…',
      'edit.saved': 'Saved',
      'edit.failed': 'Not saved: {msg}',
      'who.agent': 'Agent',
      'who.user': 'You',
      'cleared': 'cleared the status',
      'dock.unread': 'New replies {n}',
      'dock.unread.title': 'Go to an item with a new reply from the agent',
      'dock.waiting': 'Unread by agent {n}',
      'dock.waiting.title': 'Go to an item the agent has not read yet',
      'dock.progress': 'Done {done} / {all}',
      'dock.progress.title': 'Items with a status / items that take one',
      'paren': ' ({x})',
      'list.failed': 'Could not load the items: {msg}',
      'copy': 'Copy',
      'copied': 'Copied',
      'copy.failed': 'Copy failed',
      'status.resolved': 'Resolved',
      'resolve': 'Resolve',
      'restore': 'Restore',
      'delete': 'Delete',
      'expand': 'Show the whole thread',
      'close': 'Close',
      'lost': 'Comments not found in the text',
      'moved': 'The text has changed: shown near its old place (it was “{q}”)',
      'dock.resolved': 'Resolved {n}',
      'dock.resolved.title': 'Show or hide the resolved comments',
      'sb.toggle': 'Show or hide the sidebar',
      'sb.zoomout': 'Smaller text',
      'sb.zoomin': 'Larger text',
      'sb.zoomreset': 'Back to 100%',
      'sb.fit': 'Fit',
      'sb.fit.title': 'Fit the report between the sidebar and the comments',
      'sb.grip': 'Drag to change the width',
      'sb.reports': 'Reports',
      'sb.all': 'All reports (stars, tags)',
      'sb.home': '← List',
      'sb.home.title': 'The list of reports',
      'sb.split': 'Drag for the height of the reports (double click: half and half)',
      'sb.noowner': 'No owner',
      'sb.unread': 'unread {n}',
      'sb.total': 'Unread {n}',
      'sb.totalnew': ' (new {n})',
      'sb.total.title': 'Reports not marked Read (new: since this page was opened)',
      'sb.new': 'New',
      'sb.notoc': 'No headings',
      'sb.submission': 'Submission',
      'sb.basis': 'Show or hide the work reports it is based on',
      'sb.based': 'submitted with {r}',
      'sb.nobasis': 'No report of its basis is found',
      'sb.missing': 'Not found: {x}',
      'read.title': 'Did you read this report',
      'read.note': 'Press Read when you are done. Select text in the report to comment on it.',
      'read.states': 'Read:ok,Again:ask'
    },
    ja: {
      'presence.listening': 'エージェント 受付中',
      'presence.listening.title': 'チェックとコメントは、すぐエージェントに届きます',
      'presence.working': 'エージェント 対応中',
      'presence.working.title': 'エージェントが届いた書き込みを処理しています。この間の書き込みも保存され、次に受け付けたときに届きます',
      'presence.absent': 'エージェント 待ち受けなし',
      'presence.absent.title': '書き込みは保存されます。エージェントが待ち受けを始めたときに届きます',
      'presence.down': 'サーバー未接続',
      'presence.down.title': 'talkpage のサーバーにつながりません。この間の書き込みは保存されません',
      'mark.new': '新しい返信',
      'mark.wait': 'エージェント未読',
      'mark.read': 'エージェント既読',
      'mark.err': '保存の失敗',
      'mark.wait.title': 'エージェントがまだ読んでいない書き込みがあります',
      'mark.short.new': '新しい返信',
      'mark.short.wait': 'AI 未読',
      'mark.short.read': 'AI 既読',
      'mark.short.err': '保存の失敗',
      'comment': 'コメント',
      'comment.ph': 'コメント（Ctrl+Enter で送信）',
      'send': '送信',
      'send.title': '送信（Ctrl+Enter）',
      'thread.toggle': 'やりとりの表示の切り替え',
      'shrink': 'カードに戻す',
      'edit': '編集',
      'edit.title': '本文をその場で書き換える（塊ごとに保存。Enter か、ほかの所を押すと保存、Esc で取り消し）',
      'edit.one.title': 'この塊をその場で書き換える（Enter か、ほかの所を押すと保存、Esc で取り消し）',
      'pic.note': '{z}%　ホイールで拡大・縮小、ドラッグで移動、クリックか Esc で閉じる',
      'edit.saving': '保存中…',
      'edit.saved': '保存しました',
      'edit.failed': '保存できませんでした：{msg}',
      'who.agent': 'エージェント',
      'who.user': 'あなた',
      'cleared': '状態を解除',
      'dock.unread': '新しい返信 {n}',
      'dock.unread.title': 'エージェントの新しい返信がある項目へ移動',
      'dock.waiting': 'エージェント未読 {n}',
      'dock.waiting.title': 'エージェントがまだ読んでいない項目へ移動',
      'dock.progress': '記入 {done} / {all}',
      'dock.progress.title': '状態を付けた項目 / 状態を付けられる項目',
      'paren': '（{x}）',
      'list.failed': '項目の読み込みの失敗: {msg}',
      'copy': 'コピー',
      'copied': 'コピーしました',
      'copy.failed': 'コピーの失敗',
      'status.resolved': '解決',
      'resolve': '解決',
      'restore': '戻す',
      'delete': '削除',
      'expand': 'やりとりの全文表示',
      'close': '閉じる',
      'lost': '本文で見つからないコメント',
      'moved': '本文が変わったため、近い場所に表示（元の文：「{q}」）',
      'dock.resolved': '解決済み {n}',
      'dock.resolved.title': '解決済みのコメントの表示の切り替え',
      'sb.toggle': 'サイドバーの表示の切り替え',
      'sb.zoomout': '本文の縮小',
      'sb.zoomin': '本文の拡大',
      'sb.zoomreset': '100% に戻す',
      'sb.fit': '全幅',
      'sb.fit.title': 'サイドバーとコメントの間の幅に本文を合わせる',
      'sb.grip': 'ドラッグで幅の変更',
      'sb.reports': 'レポート',
      'sb.all': 'レポートの一覧（スター・タグ）',
      'sb.home': '← 一覧',
      'sb.home.title': 'レポートの一覧',
      'sb.split': 'ドラッグでレポートの欄の高さの変更（ダブルクリックで半分ずつに戻す）',
      'sb.noowner': '担当なし',
      'sb.unread': '未読 {n}',
      'sb.total': '未読 {n}',
      'sb.totalnew': '（新 {n}）',
      'sb.total.title': '「読んだ」を押していないレポートの数（新: このページを開いた後に増えたもの）',
      'sb.new': '新',
      'sb.notoc': '見出しなし',
      'sb.submission': '提出',
      'sb.basis': '根拠にした作業用のレポートの表示の切り替え',
      'sb.based': '提出は {r}',
      'sb.nobasis': '根拠のレポートが見つからない',
      'sb.missing': '見つからない根拠: {x}',
      'read.title': 'このレポートを読んだか',
      'read.note': '読み終えたら『読んだ』。本文の文字を選ぶとコメントできます。',
      'read.states': '読んだ:ok,もう一度:ask'
    }
  };
  var LANG = /^ja\b/i.test(html.getAttribute('lang') || navigator.language || '') ? 'ja' : 'en';
  function tr(key, vars) {
    var s = TEXT[LANG][key] != null ? TEXT[LANG][key] : TEXT.en[key];
    return vars ? s.replace(/\{(\w+)\}/g, function (m, k) { return vars[k] != null ? String(vars[k]) : m; }) : s;
  }
  var PRESENCE = {};
  ['listening', 'working', 'absent', 'down'].forEach(function (p) {
    PRESENCE[p] = [tr('presence.' + p), tr('presence.' + p + '.title')];
  });
  var MARKS = {}, SHORT_MARKS = {};       // SHORT_MARKS: in a comment card's one-row head
  ['new', 'wait', 'read', 'err'].forEach(function (m) { MARKS[m] = tr('mark.' + m); SHORT_MARKS[m] = tr('mark.short.' + m); });
  var items = {};          // id -> item as the server keeps it
  var taken = [];          // ids of the comments of the theme's other rounds (a new comment takes another number)
  var ui = {};             // id -> the item's elements and settings
  var order = [];          // declared ids in document order
  var rev = -1, presence = 'down', downWhy = '', jumpAt = -1, listeners = [], dock = {};
  var baseTitle = document.title;
  var byThread = new Map();
  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) {
    es.forEach(function (e) { var u = byThread.get(e.target); if (u) { u.visible = e.isIntersecting; seen(u); } });
  }) : null;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function button(cls, text) { var b = el('button', cls, text); b.type = 'button'; return b; }
  function up(node, name) { var n = node.closest('[' + name + ']'); return n ? n.getAttribute(name) : null; }
  function list(s) { return s.split(',').map(function (t) { return t.trim(); }).filter(Boolean); }
  function states(s) {
    return list(s == null ? 'OK,NG' : s).map(function (t) {
      var p = t.split(':');
      return { name: p[0], tone: p[1] || TONES[p[0]] || 'ask' };
    });
  }
  function when(t) { return t ? t.slice(5, 16).replace('-', '/') : ''; }
  function json(r) {
    return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || r.status); return d; });
  }
  function post(name, body) {
    return fetch(API + name, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                               body: JSON.stringify(body) }).then(json);
  }

  // text of a message: line breaks kept, `code` and http(s) links, nothing else is markup
  function fmt(text, into) {
    text.split(/(`[^`\n]+`)/).forEach(function (part) {
      if (/^`[^`\n]+`$/.test(part)) { into.appendChild(el('code', null, part.slice(1, -1))); return; }
      part.split(/(https?:\/\/[^\s<>"'）」]+)/).forEach(function (seg) {
        if (!/^https?:\/\//.test(seg)) { into.appendChild(document.createTextNode(seg)); return; }
        var a = el('a', null, seg); a.href = seg; a.target = '_blank'; a.rel = 'noopener'; into.appendChild(a);
      });
    });
  }

  // ---------------------------------------------------------------- items
  function build(node) {
    var id = node.getAttribute('data-talk');
    if (!id || ui[id]) { if (id) console.warn('talkpage: duplicate data-talk id', id); return; }
    var u = ui[id] = {
      id: id, el: node, open: false, shown: -1, visible: false,
      title: node.getAttribute('data-talk-title') || node.innerText.replace(/\s+/g, ' ').trim().slice(0, 120),
      states: states(up(node, 'data-talk-states')), wake: up(node, 'data-talk-wake') || '*', btns: {}
    };
    order.push(id);
    var bar = el('div', 'talk-bar');
    u.states.forEach(function (s) {
      var b = button('talk-st', s.name);
      b.setAttribute('data-tone', s.tone);
      b.setAttribute('aria-pressed', 'false');
      b.addEventListener('click', function () { setStatus(u, s.name); });
      u.btns[s.name] = b;
      bar.appendChild(b);
    });
    u.cbtn = button('talk-cbtn', tr('comment'));
    u.cbtn.setAttribute('aria-expanded', 'false');
    u.count = el('span', 'talk-count');
    u.cbtn.appendChild(u.count);
    u.cbtn.addEventListener('click', function () { openThread(u, !u.open); if (u.open) u.ta.focus(); });
    u.mark = el('span', 'talk-mark');
    bar.appendChild(u.cbtn);
    bar.appendChild(u.mark);
    u.thread = el('div', 'talk-thread');
    u.thread.hidden = true;
    u.list = el('div', 'talk-entries');
    var form = el('div', 'talk-form');
    u.ta = el('textarea');
    u.ta.rows = 2;
    u.ta.placeholder = tr('comment.ph');
    u.send = button('talk-send', tr('send'));
    form.appendChild(u.ta);
    form.appendChild(u.send);
    u.thread.appendChild(u.list);
    u.thread.appendChild(form);
    u.send.addEventListener('click', function () { sendComment(u); });
    u.ta.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.isComposing) { e.preventDefault(); sendComment(u); }
    });
    u.draft = 'talk-draft:' + page + ':' + id;           // an unsent comment survives a reload (this browser only)
    try { u.ta.value = localStorage.getItem(u.draft) || ''; } catch (e) {}
    u.ta.addEventListener('input', function () {
      try { if (u.ta.value) localStorage.setItem(u.draft, u.ta.value); else localStorage.removeItem(u.draft); } catch (e) {}
    });
    var slot = node.querySelector('[data-talk-slot]') || node;
    slot.appendChild(bar);
    slot.appendChild(u.thread);
    byThread.set(u.thread, u);
    if (io) io.observe(u.thread);
    if (u.ta.value) openThread(u, true);
  }

  function setStatus(u, name) {
    var cur = (items[u.id] || {}).status || '';
    var next = cur === name ? '' : name;
    var notify = u.wake === '*' || (u.wake !== 'none' && list(u.wake).some(function (w) { return w === next || w === cur; }));
    paint(u, next);
    post('user', { page: page, id: u.id, title: u.title, status: next, notify: notify })
      .then(take)
      .catch(function (e) { paint(u, cur); fail(u, e); });
  }

  function sendComment(u) {
    var text = u.ta.value.trim();
    if (!text || u.send.disabled) return;
    u.send.disabled = true;
    post('user', { page: page, id: u.id, title: u.title, comment: text })
      .then(function (d) {
        u.ta.value = '';
        try { localStorage.removeItem(u.draft); } catch (e) {}
        take(d);
      })
      .catch(function (e) { fail(u, e); })
      .then(function () { u.send.disabled = false; });
  }

  function fail(u, e) { mark(u, 'err'); u.mark.title = String(e && e.message || e); }

  function mark(u, m) {
    u.mark.textContent = (u.short ? SHORT_MARKS : MARKS)[m] || '';
    u.mark.setAttribute('data-m', m);
    u.mark.title = m === 'wait' ? tr('mark.wait.title') : u.short ? MARKS[m] || '' : '';
  }

  function paint(u, s) {
    Object.keys(u.btns).forEach(function (k) { u.btns[k].setAttribute('aria-pressed', String(k === s)); });
    var st = u.states.filter(function (x) { return x.name === s; })[0];
    if (s) {
      u.el.setAttribute('data-talk-status', s);
      u.el.setAttribute('data-talk-tone', st ? st.tone : TONES[s] || 'ask');
    } else {
      u.el.removeAttribute('data-talk-status');
      u.el.removeAttribute('data-talk-tone');
    }
  }

  function openThread(u, on) {
    u.open = on;
    u.thread.hidden = !on;
    u.cbtn.setAttribute('aria-expanded', String(on));
    seen(u);
  }

  function entry(m) {
    var who = tr(m.who === 'agent' ? 'who.agent' : 'who.user');
    if (!m.text) return el('div', 'talk-ev', when(m.time) + '  ' + who + ': ' + (m.status || tr('cleared')));
    var box = el('div', 'talk-msg talk-' + (m.who === 'agent' ? 'agent' : 'user'));
    box.appendChild(el('span', 'talk-who', who + '  ' + when(m.time)));
    var body = el('div', 'talk-text');
    fmt(m.text, body);
    box.appendChild(body);
    return box;
  }

  function render(id) {
    var u = ui[id];
    if (!u) return;
    var it = items[id] || { status: '', thread: [], user_rev: 0, agent_rev: 0, seen_rev: 0 };
    paint(u, it.status || '');
    var msgs = it.thread.filter(function (m) { return m.text; });
    u.count.textContent = msgs.length ? ' ' + msgs.length : '';
    u.unread = msgs.some(function (m) { return m.who === 'agent' && m.rev > (it.seen_rev || 0); });
    u.waiting = it.user_rev > it.agent_rev;
    mark(u, u.unread ? 'new' : u.waiting ? 'wait' : it.user_rev > 0 ? 'read' : '');
    if (it.thread.length !== u.shown) {
      var first = u.shown < 0;
      u.list.textContent = '';
      it.thread.forEach(function (m) { u.list.appendChild(entry(m)); });
      u.shown = it.thread.length;
      if (first && msgs.length && !u.open) openThread(u, true);   // only on load: a later reply never moves the page
    }
    seen(u);
  }

  // the user has read the agent's messages of an item when its thread is open on screen
  function seen(u) {
    if (!u.unread || !u.open || (io && !u.visible) || document.visibilityState !== 'visible' || u.seenBusy) return;
    u.seenBusy = true;
    post('seen', { page: page, id: u.id }).then(take).catch(function () {}).then(function () { u.seenBusy = false; });
  }

  function take(d) {
    items[d.id] = d;
    render(d.id);
    if (cards[d.id]) { renderCard(cards[d.id]); relayout(); }
    updateDock();
    if (d.id === 'read' && SIDEBAR) loadReports();   // "read" on this page: the sidebar's list at once, not in 30 s
  }

  // ---------------------------------------------------------------- dock (fixed, bottom right)
  function buildDock() {
    var d = el('div', 'talk-dock');
    d.setAttribute('role', 'status');
    dock.unread = button('talk-jump', '');
    dock.unread.title = tr('dock.unread.title');
    dock.waiting = button('talk-jump', '');
    dock.waiting.title = tr('dock.waiting.title');
    dock.progress = el('span', 'talk-progress');
    dock.progress.title = tr('dock.progress.title');
    dock.presence = el('span', 'talk-presence');
    dock.resolved = button('talk-jump', '');
    dock.resolved.title = tr('dock.resolved.title');
    dock.resolved.setAttribute('aria-pressed', 'false');
    dock.edit = button('talk-jump talk-edit-btn', tr('edit'));      // only on a page with text to fix
    dock.edit.title = tr('edit.title');
    dock.edit.setAttribute('aria-pressed', 'false');
    dock.edit.hidden = !FILE_PAGE || !editables().length;
    dock.edit.addEventListener('click', function () { setEditing(!editing); });
    [dock.unread, dock.waiting, dock.resolved, dock.edit, dock.progress, dock.presence]
      .forEach(function (x) { d.appendChild(x); });
    dock.unread.addEventListener('click', function () { jump(function (u) { return u.unread; }, true); });
    dock.waiting.addEventListener('click', function () { jump(function (u) { return u.waiting; }, false); });
    dock.resolved.addEventListener('click', function () {
      showResolved = !showResolved;
      Object.keys(cards).forEach(function (id) { renderCard(cards[id]); });
      relayout();
      updateDock();
    });
    document.body.appendChild(d);
  }

  function updateDock() {
    var n = { unread: 0, waiting: 0, done: 0, all: 0, resolved: 0 };
    targets().forEach(function (u) {
      if (u.unread) n.unread++;
      if (u.waiting) n.waiting++;
      if (u.resolved) n.resolved++;
      if (u.states && u.states.length) { n.all++; if (items[u.id] && items[u.id].status) n.done++; }
    });
    dock.unread.hidden = !n.unread;
    dock.unread.textContent = tr('dock.unread', { n: n.unread });
    dock.waiting.hidden = !n.waiting;
    dock.waiting.textContent = tr('dock.waiting', { n: n.waiting });
    dock.resolved.hidden = !n.resolved;
    dock.resolved.textContent = tr('dock.resolved', { n: n.resolved });
    dock.resolved.setAttribute('aria-pressed', String(showResolved));
    dock.progress.textContent = n.all ? tr('dock.progress', { done: n.done, all: n.all }) : '';
    var p = PRESENCE[presence] || PRESENCE.absent;
    dock.presence.textContent = p[0];
    dock.presence.title = p[1] + (presence === 'down' && downWhy ? tr('paren', { x: downWhy }) : '');
    dock.presence.setAttribute('data-p', presence);
    document.title = (n.unread ? '(' + n.unread + ') ' : '') + baseTitle;
  }

  // the items of the page and the comment cards, in that order
  function targets() {
    return order.map(function (id) { return ui[id]; }).concat(cardList());
  }

  function jump(pred, open) {
    var all = targets();
    var hits = all.filter(pred);
    if (!hits.length) return;
    var u = hits.filter(function (x) { return all.indexOf(x) > jumpAt; })[0] || hits[0];
    jumpAt = all.indexOf(u);
    if (u.card) { goCard(u); return; }
    if (open) openThread(u, true);
    u.el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    u.el.classList.remove('talk-flash');
    void u.el.offsetWidth;
    u.el.classList.add('talk-flash');
  }

  // ---------------------------------------------------------------- server state (long poll)
  function apply(d) {
    rev = d.rev;
    presence = d.presence || 'absent';
    taken = d.taken || [];
    Object.keys(d.items || {}).forEach(function (k) { items[k] = d.items[k]; });
    order.forEach(render);
    syncCards();
    updateDock();
    listeners.forEach(function (fn) { try { fn(d); } catch (e) { console.error(e); } });
  }

  // A tab on screen long-polls; a hidden one asks every 20 s instead, since a browser keeps at most 6 connections to
  // one server and many tabs in a long poll would hold each other up. open=1: the server counts the page as open.
  var pollGen = 0, pollTimer = 0, pollCtl = null;
  function loop(first) {
    var gen = ++pollGen;
    clearTimeout(pollTimer);
    if (pollCtl) pollCtl.abort();
    var hidden = document.visibilityState === 'hidden';
    var ctl = pollCtl = 'AbortController' in window ? new AbortController() : null;
    var q = 'state?page=' + encodeURIComponent(page) + '&open=1' +
            (first || hidden ? '' : '&rev=' + rev + '&presence=' + presence + '&wait=25');
    fetch(API + q, { cache: 'no-store', signal: ctl ? ctl.signal : undefined }).then(json)
      .then(function (d) {
        if (gen !== pollGen) return;
        apply(d);
        if (document.visibilityState === 'hidden') pollTimer = setTimeout(function () { loop(false); }, 20000);
        else loop(false);
      })
      .catch(function (e) {
        if (gen !== pollGen) return;                 // aborted for the next request
        presence = 'down';
        downWhy = e && e.message || '';
        updateDock();
        pollTimer = setTimeout(function () { loop(true); }, hidden ? 20000 : 3000);
      });
  }

  function pollOnVisibility() {
    if (document.visibilityState === 'hidden') {
      ++pollGen;                                     // end the long poll; ask again in 20 s
      clearTimeout(pollTimer);
      if (pollCtl) pollCtl.abort();
      pollTimer = setTimeout(function () { loop(false); }, 20000);
    } else {
      loop(presence === 'down');
    }
  }

  // ---------------------------------------------------------------- items declared in JSON
  function lists() {
    var boxes = [].slice.call(document.querySelectorAll('[data-talk-list]'));
    return Promise.all(boxes.map(function (box) {
      var src = box.getAttribute('data-talk-list');
      var inline = box.querySelector('script[type="application/json"]');
      var got = src ? fetch(src, { cache: 'no-store' }).then(json)
                    : Promise.resolve(JSON.parse(inline ? inline.textContent : '[]'));
      return got.then(function (data) {
        (Array.isArray(data) ? data : data.items || []).forEach(function (d) {
          var card = el('div', 'talk-card');
          card.setAttribute('data-talk', d.id);
          card.setAttribute('data-talk-title', d.id + ' ' + (d.title || ''));
          if (d.states != null) card.setAttribute('data-talk-states', d.states);
          if (d.wake != null) card.setAttribute('data-talk-wake', d.wake);
          var head = el('div', 'talk-card-head');
          head.appendChild(el('span', 'talk-card-id', d.id));
          head.appendChild(el('span', 'talk-card-title', d.title || ''));
          card.appendChild(head);
          if (d.html || d.text) {
            var body = el('div', 'talk-card-body');
            if (d.html) body.innerHTML = d.html; else body.textContent = d.text;   // html: written by the page's author
            card.appendChild(body);
          }
          box.appendChild(card);
        });
      }).catch(function (e) { box.appendChild(el('p', 'talk-error', tr('list.failed', { msg: e.message }))); });
    }));
  }

  // ---------------------------------------------------------------- copy buttons
  function copyText(text) {
    function legacy() {
      return new Promise(function (ok, ng) {
        var t = el('textarea');
        t.value = text;
        t.style.position = 'fixed';
        t.style.opacity = '0';
        document.body.appendChild(t);
        t.select();
        try { if (document.execCommand('copy')) ok(); else ng(new Error('copy')); } catch (e) { ng(e); }
        document.body.removeChild(t);
      });
    }
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text).catch(legacy);
    return legacy();
  }

  function copies() {
    document.querySelectorAll('[data-copy]').forEach(function (box) {
      if (box.querySelector('.talk-copy-btn')) return;
      var fixed = box.getAttribute('data-copy') || null;
      var src = fixed ? null : box.querySelector('code, pre');
      if (!fixed && !src) fixed = box.textContent.trim();
      var b = button('talk-copy-btn', tr('copy'));
      var note = el('span', 'talk-copied');
      note.setAttribute('aria-live', 'polite');
      box.classList.add('talk-copy');
      box.appendChild(b);
      box.appendChild(note);
      b.addEventListener('click', function () {
        copyText(fixed != null ? fixed : src.textContent).then(function () {
          note.textContent = tr('copied');
          clearTimeout(note.timer);
          note.timer = setTimeout(function () { note.textContent = ''; }, 1500);
        }, function () { note.textContent = tr('copy.failed'); });
      });
    });
  }

  // ---------------------------------------------------------------- reports: comments on selected text
  // A card sits beside its text, found again by the item's title. When the text has changed (an edit, a rebuild),
  // the card goes near its old place, by most of the text or by the item's anchor (its headings, the element with an
  // id, its share of the way down); only a comment with nothing to go by is listed at the end of the report.
  // talkpage's own parts: their text is not the report's, and a selection in them is not a comment
  var OURS = '.talk-ui, .talk-bar, .talk-thread, .talk-dock, .talk-copy-btn, .talk-copied';
  var SKIP = OURS + ', script, style, noscript, textarea, template';
  var CARD_MAX = 340, MARGIN_MIN = 240, CARD_GAP = 8;
  var scopes = [];          // {root, prefix, re, lost, lostList, ix, dirty, pins}: where selecting text makes a comment
  var cards = {};           // id -> comment card of an item <prefix><number> the server keeps
  var drafts = [];          // the cards of comments not sent yet (not on the server)
  var openNow = null, big = null, showResolved = false;
  var layer = null, selLayer = null, selBtn = null, selEdit = null, content = null, layoutQueued = false;
  var touched = false, selTimer = 0;            // the last pointer was a finger; the wait for a touch selection
  var marks = !!(window.CSS && CSS.highlights && typeof Highlight === 'function');

  function ours(node) {
    var e = node && (node.nodeType === 1 ? node : node.parentElement);
    return !!(e && e.closest(OURS));
  }
  function squash(s) { return s.replace(/\s+/g, ' ').trim(); }
  function firstLine(t) { return (t.split('\n').filter(function (s) { return s.trim(); })[0] || '').trim(); }
  function isResolved(s) { return s === '解決' || s === 'Resolved'; }

  // the report's text nodes under root, in document order
  function texts(root) {
    var w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (n.nodeType === 1) return n.matches(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_SKIP;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var out = [], n;
    while ((n = w.nextNode())) out.push(n);
    return out;
  }

  // the text under root without white space, and where each of its characters is
  function index(root) {
    var flat = [], at = [];
    texts(root).forEach(function (n) {
      var s = n.data;
      for (var i = 0; i < s.length; i++) if (!/\s/.test(s[i])) { flat.push(s[i]); at.push([n, i]); }
    });
    return { flat: flat.join(''), at: at };
  }

  // characters a … z-1 of the index as a Range
  function span(ix, a, z) {
    var s = ix.at[a], e = ix.at[z - 1], r = document.createRange();
    r.setStart(s[0], s[1]);
    r.setEnd(e[0], e[1] + 1);
    return r;
  }
  function blockRange(e) { var r = document.createRange(); r.selectNode(e); return r; }

  // the first place of the text in the index, white space aside; null when it is not there
  function find(ix, text) {
    var needle = text.replace(/\s+/g, '');
    var i = needle ? ix.flat.indexOf(needle) : -1;
    return i < 0 ? null : span(ix, i, i + needle.length);
  }

  // the first character of the index at or after the start of a range (the index is in document order)
  function startOf(ix, range) {
    var lo = 0, hi = ix.at.length;
    while (lo < hi) {
      var mid = (lo + hi) >> 1, c;
      try { c = range.comparePoint(ix.at[mid][0], ix.at[mid][1]); } catch (e) { return -1; }
      if (c < 0) lo = mid + 1; else hi = mid;
    }
    return lo < ix.at.length ? lo : -1;
  }

  // the report's headings that place a comment (h1 is the page's title)
  function headings(root) {
    return [].filter.call(root.querySelectorAll('h2, h3, h4, h5, h6'), function (h) { return !ours(h); });
  }
  // a heading's text without its number (2. / 4-1 / S3 / ③) and white space, so a renumbered heading still matches
  function bare(t) {
    return squash(t).replace(/^(?:[A-Z]{0,2}\d+(?:[-.．]\d+)*[.．]?|[①-⑳])[\s　]*/, '').replace(/[\s　]/g, '');
  }

  // where a comment's text is, kept with its item (the field anchor) to place the card once the text has changed: the
  // headings it is under (outer first), the closest element with an id, and its share of the way down the text. A tool
  // that finds the place of an older comment again can write the same
  function anchorOf(s, range, ix) {
    var start = range.startContainer, stack = [];
    headings(s.root).forEach(function (h) {
      if (!(h === start || h.compareDocumentPosition(start) & Node.DOCUMENT_POSITION_FOLLOWING)) return;
      var lv = +h.tagName[1];
      while (stack.length && stack[stack.length - 1].lv >= lv) stack.pop();
      stack.push({ lv: lv, t: squash(h.textContent).slice(0, 120) });
    });
    var a = { heads: stack.map(function (h) { return h.t; }).filter(Boolean) };
    var e = start.nodeType === 1 ? start : start.parentElement, idEl = e && e.closest('[id]');
    if (idEl && idEl.id && idEl !== s.root && s.root.contains(idEl) && !ours(idEl)) a.id = idEl.id;
    var at = startOf(ix, range);
    if (at >= 0 && ix.flat.length) a.pos = Math.round(at / ix.flat.length * 1000) / 1000;
    return a;
  }

  // most of the text still there: pieces of it vote for where it starts, and the place with the most votes wins
  function nearQuote(ix, needle) {
    var text = ix.flat, L = Math.max(4, Math.min(10, Math.floor(needle.length / 3))), step = Math.max(2, L >> 1);
    var votes = [], n = 0;
    for (var i = 0; i + L <= needle.length; i += step) {
      var piece = needle.slice(i, i + L), hits = [], at = text.indexOf(piece);
      while (at >= 0 && hits.length < 4) { hits.push(at); at = text.indexOf(piece, at + 1); }
      n++;
      if (!hits.length || hits.length > 3) continue;       // gone, or too common to tell
      hits.forEach(function (h) { votes.push({ s: h - i, h: h, w: 1 / hits.length }); });
    }
    var best = null;
    votes.forEach(function (v) {
      var near = votes.filter(function (x) { return Math.abs(x.s - v.s) <= 30; });
      var w = near.reduce(function (t, x) { return t + x.w; }, 0);
      if (!best || w > best.w) best = { w: w, near: near };
    });
    if (!best || best.w < Math.max(2, n * 0.34)) return null;
    var hs = best.near.map(function (x) { return x.h; });
    return { a: Math.min.apply(null, hs), z: Math.max.apply(null, hs) + L };
  }

  // the Range of a comment's text and how near it is: near '' the text itself, 'text' most of it, 'block' only near
  // its old place (its heading, the element with its id, its share of the way down). null: nothing to go by
  function locate(s, ix, title, a) {
    a = a && typeof a === 'object' ? a : {};
    var text = ix.flat, len = text.length, needle = title.replace(/\s+/g, '');
    var pos = typeof a.pos === 'number' ? a.pos : null, want = pos === null ? 0 : pos * len, at = -1;
    if (!len || !needle) return null;
    for (var k = text.indexOf(needle); k >= 0; k = text.indexOf(needle, k + 1)) {   // twice: the one nearer its old place
      if (at < 0 || Math.abs(k - want) < Math.abs(at - want)) at = k;
    }
    if (at >= 0) return { range: span(ix, at, at + needle.length), near: '' };
    var heads = (Array.isArray(a.heads) ? a.heads : []).map(function (h) { return bare(String(h)); }).filter(Boolean);
    var all = headings(s.root);
    function headOf(hs, w) {                              // the heading with this text, or one that has it in it
      return hs.filter(function (h) { return bare(h.textContent) === w; })[0] || (w.length >= 6 && hs.filter(function (h) {
        var b = bare(h.textContent);
        return b.length >= 6 && (b.indexOf(w) >= 0 || w.indexOf(b) >= 0);
      })[0]) || null;
    }
    var e = typeof a.id === 'string' && a.id ? document.getElementById(a.id) : null;
    if (e && (e === s.root || !s.root.contains(e) || ours(e))) e = null;
    // an id such as F1 goes to another item when the items are renumbered: when its element has headings of its own,
    // one of them must still match
    if (e && heads.length) {
      var own = all.filter(function (h) { return e.contains(h); });
      if (own.length && !heads.some(function (w) { return headOf(own, w); })) e = null;
    }
    // most of the text, but only where it was: in the element with the id, or about as far down
    var q = nearQuote(ix, needle);
    if (q && (e ? e.contains(ix.at[q.a][0]) : pos === null || Math.abs(q.a / len - pos) < 0.15)) {
      return { range: span(ix, q.a, q.z), near: 'text' };
    }
    // its heading, innermost first (inside the element with the id when there is one: a section's own heading is
    // nearer than the section), then that element, then the same share of the way down
    var hs = e ? all.filter(function (h) { return e.contains(h); }) : all;
    for (var i = heads.length - 1; i >= 0; i--) {
      var h = headOf(hs, heads[i]);
      if (h) return { range: blockRange(h), near: 'block' };
    }
    if (e) return { range: blockRange(e), near: 'block' };
    if (pos === null) return null;
    var p = Math.min(len - 1, Math.max(0, Math.floor(pos * len)));
    return { range: span(ix, p, p + 1), near: 'block' };
  }

  // where a card goes: a draft by its selection, else its text found again, else near its old place (≈ before its id)
  function place(s, c) {
    if (c.sel) { c.range = c.sel; c.near = ''; return; }
    var ix = s.ix || (s.ix = index(s.root)), it = items[c.id] || {};
    var p = locate(s, ix, c.title, it.anchor);
    c.range = p ? p.range : null;
    c.near = p ? p.near : '';
    c.idEl.textContent = c.pin.textContent = (c.near ? '≈' : '') + c.id;
    c.el.classList.toggle('talk-rcard-moved', !!c.near);
    c.el.title = c.near ? tr('moved', { q: c.title }) : '';
    // a comment from before anchors were kept: note where its text is while it is still there, for a later change
    if (p && !p.near && items[c.id] && !it.anchor && !c.anchoring) {
      c.anchoring = true;
      post('user', { page: page, id: c.id, anchor: anchorOf(s, c.range, ix), notify: false }).then(take).catch(function () {});
    }
  }

  // the report's own text in a range (without talkpage's parts)
  function rangeText(root, range) {
    var s = '';
    texts(root).forEach(function (n) {
      if (!range.intersectsNode(n)) return;
      s += n.data.slice(n === range.startContainer ? range.startOffset : 0,
                        n === range.endContainer ? range.endOffset : n.data.length);
    });
    return squash(s);
  }

  function scopeOf(node) {
    var e = node && (node.nodeType === 1 ? node : node.parentElement), hit = null;
    scopes.forEach(function (s) { if (e && s.root.contains(e)) hit = s; });     // the innermost one
    return hit;
  }

  function cardList() {
    return Object.keys(cards).sort(function (a, b) { return a.localeCompare(b, undefined, { numeric: true }); })
      .map(function (id) { return cards[id]; });
  }

  function nextId(prefix) {
    var re = new RegExp('^' + prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(\\d+)$'), max = 0;
    Object.keys(items).concat(order, Object.keys(cards), taken, drafts.map(function (d) { return d.id; })).forEach(function (id) {
      var m = re.exec(id);
      if (m) max = Math.max(max, +m[1]);
    });
    return prefix + (max + 1);
  }

  function makeCard(id, scope, title, isDraft) {
    var c = { id: id, card: true, scope: scope, title: title, open: false, visible: false, shown: -1, short: true };
    c.el = el('div', 'talk-ui talk-rcard');
    // one row at the top: the id, a speech bubble with the number of messages (opens and closes the card), the mark
    // (new reply …), then resolve, ⤢ and send at the right end; the box to write in below spans the card
    var head = el('div', 'talk-rcard-head');
    c.idEl = el('span', 'talk-rcard-id', id);
    c.bub = button('talk-rcard-bub', '');
    c.bub.appendChild(bubble());
    c.count = el('span', 'talk-count');
    c.bub.appendChild(c.count);
    c.bub.title = tr('thread.toggle');
    c.bub.setAttribute('aria-label', tr('comment'));
    c.bub.setAttribute('aria-expanded', 'false');
    c.mark = el('span', 'talk-mark');
    c.res = button('talk-rcard-res', tr('resolve'));
    c.expand = button('talk-rcard-exp', '⤢');
    c.expand.title = tr('expand');
    c.expand.setAttribute('aria-label', tr('expand'));
    c.send = button('talk-send', tr('send'));
    c.send.title = tr('send.title');
    [c.idEl, c.bub, c.mark, c.res, c.expand, c.send].forEach(function (x) { head.appendChild(x); });
    c.quote = el('div', 'talk-rcard-quote', title);
    c.sum = el('div', 'talk-rcard-sum');
    c.body = el('div', 'talk-rcard-body');
    c.lines = el('div', 'talk-rcard-lines');
    var form = el('div', 'talk-form');
    c.ta = el('textarea');
    c.ta.rows = 2;
    c.ta.placeholder = tr('comment.ph');
    form.appendChild(c.ta);
    [c.lines, form].forEach(function (x) { c.body.appendChild(x); });
    [head, c.quote, c.sum, c.body].forEach(function (x) { c.el.appendChild(x); });
    c.pin = button('talk-ui talk-pin', id);
    c.el.addEventListener('click', function (e) {
      if (e.target.closest('button, textarea, a')) return;
      if (!c.open) openCard(c); else openBig(c);
    });
    c.bub.addEventListener('click', function () {
      if (c.draft) c.ta.focus({ preventScroll: true });
      else if (c.open) closeCard(c);
      else openCard(c);
    });
    c.expand.addEventListener('click', function () { openBig(c); });
    c.pin.addEventListener('click', function () { openBig(c); });
    c.send.addEventListener('click', function () { sendCard(c, c.ta); });
    c.ta.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.isComposing) { e.preventDefault(); sendCard(c, c.ta); }
    });
    c.ta.addEventListener('input', function () { keepDraft(c); });
    c.res.addEventListener('click', function () { if (c.draft) dropDraft(c); else resolveCard(c); });
    if (!isDraft) setDraftKey(c);
    byThread.set(c.el, c);
    if (io) io.observe(c.el);
    return c;
  }

  function bubble() {                                       // a speech bubble in the text's colour
    var NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg'), p = document.createElementNS(NS, 'path');
    svg.setAttribute('viewBox', '0 0 16 16');
    svg.setAttribute('aria-hidden', 'true');
    p.setAttribute('d', 'M2.5 2.5h11a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H7.5L4.5 14v-2.5h-2a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1z');
    svg.appendChild(p);
    return svg;
  }

  // an unsent comment of a card on the server survives a reload (this browser only), as on an item
  function setDraftKey(c) {
    c.draftKey = 'talk-draft:' + page + ':' + c.id;
    try { c.ta.value = localStorage.getItem(c.draftKey) || c.ta.value; } catch (e) {}
  }
  function keepDraft(c) {
    if (!c.draftKey) return;
    try { if (c.ta.value) localStorage.setItem(c.draftKey, c.ta.value); else localStorage.removeItem(c.draftKey); } catch (e) {}
  }

  function line(m) {
    var d = el('div', 'talk-rcard-line talk-' + (m.who === 'agent' ? 'agent' : 'user'));
    d.appendChild(el('span', 'talk-who', tr(m.who === 'agent' ? 'who.agent' : 'who.user') + '  ' + when(m.time)));
    d.appendChild(el('span', 'talk-rcard-text', m.text ? firstLine(m.text) : (m.status || tr('cleared'))));
    return d;
  }

  function renderCard(c) {
    var it = items[c.id] || { status: '', thread: [], user_rev: 0, agent_rev: 0, seen_rev: 0 };
    var msgs = it.thread.filter(function (m) { return m.text; });
    c.unread = msgs.some(function (m) { return m.who === 'agent' && m.rev > (it.seen_rev || 0); });
    c.waiting = it.user_rev > it.agent_rev;
    c.resolved = isResolved(it.status || '');
    mark(c, c.unread ? 'new' : c.waiting ? 'wait' : it.user_rev > 0 ? 'read' : '');
    c.count.textContent = msgs.length ? String(msgs.length) : '';
    var last = msgs[msgs.length - 1];
    c.sum.textContent = it.summary ? String(it.summary)
      : last ? tr(last.who === 'agent' ? 'who.agent' : 'who.user') + ': ' + firstLine(last.text) : '';
    c.sum.classList.toggle('talk-rcard-summary', !!it.summary);
    if (it.thread.length !== c.shown) {
      c.lines.textContent = '';
      it.thread.forEach(function (m) { c.lines.appendChild(line(m)); });
      c.shown = it.thread.length;
      c.lines.scrollTop = c.lines.scrollHeight;
    }
    c.res.textContent = tr(c.draft ? 'delete' : c.resolved ? 'restore' : 'resolve');
    c.el.classList.toggle('talk-done', c.resolved);
    c.el.classList.toggle('talk-open', c.open);
    c.pin.classList.toggle('talk-pin-new', c.unread);      // a reply never opens a card: the page stays still
    if (big && big.c === c) renderBig();
    seen(c);
  }

  // cards for the items of the server the page does not declare
  function syncCards() {
    if (!scopes.length) return;
    drafts.forEach(function (d) {
      if (!items[d.id]) return;                             // taken meanwhile (another tab): renumber the draft
      d.id = nextId(d.scope.prefix);
      d.idEl.textContent = d.pin.textContent = d.id;
    });
    Object.keys(items).forEach(function (id) {
      if (cards[id] || ui[id]) return;
      var s = scopes.filter(function (x) { return x.re.test(id); })[0];
      if (s) cards[id] = makeCard(id, s, items[id].title || id);
    });
    Object.keys(cards).forEach(function (id) { renderCard(cards[id]); });
    relayout();
  }

  function openCard(c) {
    if (openNow && openNow !== c) closeCard(openNow);
    openNow = c;
    c.open = true;
    c.el.classList.add('talk-open');
    c.bub.setAttribute('aria-expanded', 'true');
    paintMarks();
    relayout();
    seen(c);
  }

  function closeCard(c) {
    c.open = false;
    c.el.classList.remove('talk-open');
    c.bub.setAttribute('aria-expanded', 'false');
    if (openNow === c) openNow = null;
    paintMarks();
    relayout();
  }

  function newDraft(x) {
    if (openNow) closeCard(openNow);
    var s = x.scope, ix = index(s.root);
    var title = squash(x.text).slice(0, 200).trim();
    if (!find(ix, title)) title = rangeText(s.root, x.range).slice(0, 200).trim();
    if (!title) return;
    var c = makeCard(nextId(s.prefix), s, title, true);
    drafts.push(c);
    c.draft = true;
    c.sel = x.range;
    c.anchor = anchorOf(s, x.range, ix);                    // sent with the first comment
    selBtn.hidden = true;
    getSelection().removeAllRanges();
    renderCard(c);
    openNow = c;
    c.open = true;
    c.el.classList.add('talk-open');
    c.bub.setAttribute('aria-expanded', 'true');
    layout();
    if (s.pins) openBig(c); else c.ta.focus({ preventScroll: true });
  }

  // a draft stays until it is sent or its "delete" is pressed, also with nothing written (one talks to the voice input
  // while looking elsewhere on the page)
  function dropDraft(c) {
    var i = drafts.indexOf(c);
    if (i < 0 || c.busy) return;
    drafts.splice(i, 1);
    if (big && big.c === c) closeBig(true);
    if (openNow === c) openNow = null;
    [c.el, c.pin].forEach(function (x) { if (x.parentNode) x.parentNode.removeChild(x); });
    if (io) io.unobserve(c.el);
    byThread.delete(c.el);
    paintMarks();
    relayout();
  }

  function sendCard(c, ta) {
    var text = ta.value.trim();
    if (c.busy) return;
    if (!text) {                                          // send in the head with nothing written: the box to write in
      if (!c.open) openCard(c);
      ta.focus({ preventScroll: true });
      return;
    }
    c.busy = true;
    c.send.disabled = true;
    if (big) big.send.disabled = true;
    // a draft is made on the server here, with where its text is
    post('user', { page: page, id: c.id, title: c.title, comment: text, anchor: c.draft ? c.anchor : undefined })
      .then(function (d) {
        c.ta.value = '';
        if (big && big.c === c) big.ta.value = '';
        keepDraft(c);
        if (c.draft) {
          drafts.splice(drafts.indexOf(c), 1);
          c.draft = false;
          cards[c.id] = c;
          c.draftKey = 'talk-draft:' + page + ':' + c.id;
        }
        take(d);
      })
      .catch(function (e) { fail(c, e); })
      .then(function () {
        c.busy = false;
        c.send.disabled = false;
        if (big) big.send.disabled = false;
      });
  }

  // resolved: hidden with its mark, and the agent is not woken; "restore" clears the status
  function resolveCard(c) {
    var next = c.resolved ? '' : tr('status.resolved');
    post('user', { page: page, id: c.id, title: c.title, status: next, notify: false })
      .then(function (d) {
        if (next && !showResolved) { if (big && big.c === c) closeBig(true); closeCard(c); }
        take(d);
        updateDock();
      })
      .catch(function (e) { fail(c, e); });
  }

  // the whole thread in the middle of the screen
  function openBig(c) {
    closeBig(true);
    openCard(c);
    var m = el('div', 'talk-ui talk-modal');
    var box = el('div', 'talk-modal-box');
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    // the head stays at the top while the thread scrolls: the id, then resolve, back to the card (× with no card to go
    // back to) and send at the right end, as in the card
    var head = el('div', 'talk-modal-head');
    head.appendChild(el('span', 'talk-rcard-id', c.idEl.textContent));     // with ≈ when near its old place
    var b = { c: c, el: m, shown: -1 };
    b.res = button('talk-rcard-res', '');
    var x = button('talk-modal-close', c.scope.pins ? '×' : '⤡');
    x.title = tr(c.scope.pins ? 'close' : 'shrink');
    x.setAttribute('aria-label', x.title);
    b.send = button('talk-send', tr('send'));
    b.send.title = tr('send.title');
    [b.res, x, b.send].forEach(function (y) { head.appendChild(y); });
    b.sum = el('div', 'talk-modal-sum');
    b.list = el('div', 'talk-entries talk-modal-list');
    var form = el('div', 'talk-form');
    b.ta = el('textarea');
    b.ta.rows = 3;
    b.ta.placeholder = tr('comment.ph');
    b.ta.value = c.ta.value;
    form.appendChild(b.ta);
    [head, el('blockquote', 'talk-modal-quote', c.title), b.sum, b.list, form]
      .forEach(function (y) { box.appendChild(y); });
    m.appendChild(box);
    m.addEventListener('click', function (e) { if (e.target === m) closeBig(); });
    x.addEventListener('click', function () { closeBig(); });
    b.send.addEventListener('click', function () { sendCard(c, b.ta); });
    b.ta.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.isComposing) { e.preventDefault(); sendCard(c, b.ta); }
    });
    b.ta.addEventListener('input', function () { c.ta.value = b.ta.value; keepDraft(c); });
    b.res.addEventListener('click', function () { if (c.draft) dropDraft(c); else resolveCard(c); });
    b.box = box;
    big = b;
    document.body.appendChild(m);
    zoomBig();
    c.visible = true;
    renderBig();
    seen(c);
    b.ta.focus({ preventScroll: true });
  }

  function renderBig() {
    var c = big.c, it = items[c.id] || { thread: [] };
    big.sum.textContent = it.summary ? String(it.summary) : '';
    big.sum.hidden = !it.summary;
    if (it.thread.length !== big.shown) {
      big.list.textContent = '';
      it.thread.forEach(function (m) { big.list.appendChild(entry(m)); });
      big.shown = it.thread.length;
      big.list.scrollTop = big.list.scrollHeight;
    }
    big.res.textContent = tr(c.draft ? 'delete' : c.resolved ? 'restore' : 'resolve');
  }

  // the whole thread grows with the report's zoom like the cards (the dark background around it stays as it is);
  // Ctrl + wheel over it zooms the report, so the thread with it
  function zoomBig() {
    var z = cardZoom(), s = big.box.style;
    if (z === 1) { s.zoom = s.width = s.maxHeight = ''; return; }
    s.zoom = String(z);
    s.width = Math.min(760 * z, document.documentElement.clientWidth - 32) / z + 'px';
    s.maxHeight = window.innerHeight * 0.86 / z + 'px';
  }

  // quiet: only take it away (another view replaces it)
  function closeBig(quiet) {
    if (!big) return;
    var c = big.c;
    big.el.parentNode.removeChild(big.el);
    big = null;
    if (!quiet && c.scope.pins) closeCard(c);         // no card to go back to; a draft stays as its number
  }

  // a jump from the dock
  function goCard(c) {
    if (c.resolved && !showResolved) {
      showResolved = true;
      cardList().forEach(renderCard);
      updateDock();
    }
    layout();
    if (c.scope.pins && c.range) { openBig(c); return; }
    openCard(c);
    layout();
    c.el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }

  function setMarks(name, ranges, priority) {
    if (!ranges.length) { CSS.highlights.delete(name); return; }
    var h = new Highlight();
    ranges.forEach(function (r) { h.add(r); });
    h.priority = priority;
    CSS.highlights.set(name, h);
  }

  function paintMarks() {
    if (!marks) return;
    var plain = [], near = [], strong = [], done = [];
    cardList().concat(drafts).forEach(function (c) {
      if (!c.range || c.near === 'block') return;            // a card only near its old place marks no text
      if (c.resolved) { if (showResolved) done.push(c.range); return; }
      (c.open ? strong : c.near ? near : plain).push(c.range);
    });
    setMarks('talk-mark', plain, 0);
    setMarks('talk-mark-near', near, 0);
    setMarks('talk-mark-done', done, 1);
    setMarks('talk-mark-open', strong, 2);
  }

  function relayout() {
    if (layoutQueued || !layer) return;
    layoutQueued = true;
    function run() { if (layoutQueued) { layoutQueued = false; layout(); } }
    requestAnimationFrame(run);
    setTimeout(run, 100);                  // a page drawn in the background gets no animation frames
  }

  // the report's zoom (the sidebar's − 100% ＋ and "fit"): the cards and the whole thread grow with it
  function cardZoom() { return SIDEBAR && content ? sb.zoom : 1; }

  // cards beside their marks in the right margin, each below the one above; a narrow margin gets numbers only. The
  // layer of the cards is zoomed like the report: the places are worked out on the screen and divided by the zoom
  function layout() {
    if (!layer) return;
    var z = cardZoom(), base = layer.getBoundingClientRect(), vw = document.documentElement.clientWidth;
    layer.style.zoom = z === 1 ? '' : String(z);
    if (big) zoomBig();
    scopes.forEach(function (s) {
      var all = cardList().filter(function (c) { return c.scope === s; });
      drafts.forEach(function (d) { if (d.scope === s) all.push(d); });
      if (s.dirty) {
        s.ix = null;
        s.dirty = false;
        all.forEach(function (c) { c.range = undefined; });
      }
      all.forEach(function (c) { if (c.range === undefined) place(s, c); });
      var sr = s.root.getBoundingClientRect();
      var margin = vw - sr.right;
      s.pins = margin < MARGIN_MIN * z;
      var w = Math.min(CARD_MAX * z, margin - 24), rows = [], lost = 0;
      all.forEach(function (c) {
        var shown = !c.resolved || showResolved;
        c.el.hidden = !shown;
        c.pin.hidden = true;
        if (!shown) return;
        if (!c.range) {
          if (c.el.parentNode !== s.lostList) s.lostList.appendChild(c.el);
          c.el.style.top = c.el.style.left = c.el.style.width = '';
          lost++;
          return;
        }
        var rr = c.range.getClientRects()[0] || c.range.getBoundingClientRect();
        rows.push({ c: c, top: rr.top - base.top });
      });
      rows.sort(function (a, b) { return a.top - b.top; });
      var bottom = -Infinity;
      rows.forEach(function (r) {
        var c = r.c, top;
        if (c.el.parentNode !== layer) layer.appendChild(c.el);
        if (c.pin.parentNode !== layer) layer.appendChild(c.pin);
        if (s.pins) {
          c.el.hidden = true;
          c.pin.hidden = false;
          var pr = c.pin.getBoundingClientRect();
          top = Math.max(r.top, bottom + 4);
          c.pin.style.top = top / z + 'px';
          c.pin.style.left = (vw - pr.width - 6 - base.left) / z + 'px';
          bottom = top + pr.height;
        } else {
          c.el.style.width = w / z + 'px';
          c.el.style.left = (sr.right + 12 - base.left) / z + 'px';
          top = Math.max(r.top, bottom + CARD_GAP * z);
          c.el.style.top = top / z + 'px';
          bottom = top + c.el.getBoundingClientRect().height;
        }
      });
      s.lost.hidden = !lost;
    });
    paintMarks();
  }

  function dirtyAll() {
    scopes.forEach(function (s) { s.dirty = true; });
    relayout();
  }

  // the "comment" button by a selection of the report's text, and "edit" beside it when the selection is in one block
  // of text (while text is being written in, selecting is for writing: neither)
  function onSelect() {
    var sel = getSelection(), s = null, r = null;
    if (sel && sel.rangeCount && !sel.isCollapsed && !editing && !editBlock(document.activeElement)) {
      r = sel.getRangeAt(0);
      s = scopeOf(r.commonAncestorContainer);
      if (s && (ours(r.commonAncestorContainer) || ours(r.startContainer) || ours(r.endContainer) ||
                !squash(sel.toString()))) s = null;
    }
    if (!s) { selBtn.hidden = selEdit.hidden = true; selBtn.sel = selEdit.block = null; return; }
    var b = FILE_PAGE ? blockOf(r.startContainer) : null;
    selEdit.block = b && b === blockOf(r.endContainer) ? b : null;
    selBtn.hidden = false;
    selEdit.hidden = !selEdit.block;
    var rects = r.getClientRects(), last = rects[rects.length - 1] || r.getBoundingClientRect();
    var base = selLayer.getBoundingClientRect(), vw = document.documentElement.clientWidth;
    var w = selBtn.offsetWidth + (selEdit.block ? selEdit.offsetWidth + 4 : 0);
    var left = Math.max(4, Math.min(last.right + 4, vw - w - 8)) - base.left;
    var top = last.bottom + (touched ? 28 : 4) - base.top + 'px';           // below a phone's selection handle
    selBtn.style.left = left + 'px';
    selEdit.style.left = left + selBtn.offsetWidth + 4 + 'px';
    selBtn.style.top = selEdit.style.top = top;
    selBtn.sel = { scope: s, range: r.cloneRange(), text: sel.toString() };
    selEdit.range = selBtn.sel.range;
  }

  function caretAt(x, y) {
    if (document.caretPositionFromPoint) {
      var p = document.caretPositionFromPoint(x, y);
      return p && [p.offsetNode, p.offset];
    }
    if (document.caretRangeFromPoint) {
      var r = document.caretRangeFromPoint(x, y);
      return r && [r.startContainer, r.startOffset];
    }
    return null;
  }

  // a click on marked text opens its card
  function onClick(e) {
    if (e.button !== 0 || ours(e.target) || editing || editBlock(e.target)) return;   // a click to write in
    var sel = getSelection();
    if (sel && !sel.isCollapsed) return;
    var p = caretAt(e.clientX, e.clientY);
    if (!p) return;
    var hit = cardList().filter(function (c) {
      if (!c.range || c.near === 'block' || c.resolved && !showResolved) return false;
      try { return c.range.isPointInRange(p[0], p[1]); } catch (x) { return false; }
    })[0];
    if (!hit) return;
    if (hit.scope.pins) openBig(hit); else openCard(hit);
  }

  // elsewhere: the open card closes (a draft stays)
  function onDown(e) {
    if (e.target.closest && e.target.closest('.talk-rcard, .talk-pin, .talk-modal, .talk-selbtn')) return;
    if (openNow) closeCard(openNow);
  }

  function onKey(e) {
    if (e.key !== 'Escape' || e.isComposing) return;
    if (big) closeBig();
    else if (openNow) closeCard(openNow);
  }

  function setupSelect() {
    if (REPORT) scopes.push({ root: content, prefix: 'C' });
    document.querySelectorAll('[data-talk-select]').forEach(function (n) {
      if (!(REPORT && n === content)) scopes.push({ root: n, prefix: n.getAttribute('data-talk-select') || 'C' });
    });
    if (!scopes.length) return;
    scopes.forEach(function (s) {
      s.re = new RegExp('^' + s.prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\d+$');
      s.dirty = true;
      s.lost = el('div', 'talk-ui talk-lost');
      s.lost.hidden = true;
      s.lost.appendChild(el('div', 'talk-lost-head', tr('lost')));
      s.lostList = el('div', 'talk-lost-list');
      s.lost.appendChild(s.lostList);
      s.root.appendChild(s.lost);
    });
    layer = el('div', 'talk-ui talk-layer');                 // the cards (zoomed with the report)
    selLayer = el('div', 'talk-ui talk-layer');              // the selection's buttons (never zoomed)
    document.body.appendChild(layer);
    document.body.appendChild(selLayer);
    selBtn = button('talk-ui talk-selbtn', tr('comment'));
    selEdit = button('talk-ui talk-selbtn talk-seledit', tr('edit'));
    selEdit.title = tr('edit.one.title');
    function onSelBtn(b) {
      if (b === selBtn && selBtn.sel) newDraft(selBtn.sel);
      if (b === selEdit && selEdit.block) editOne(selEdit.block, selEdit.range);
      selBtn.hidden = selEdit.hidden = true;
    }
    [selBtn, selEdit].forEach(function (b) {
      b.hidden = true;
      selLayer.appendChild(b);
      b.addEventListener('mousedown', function (e) { e.preventDefault(); });      // keeps the selection
      b.addEventListener('click', function () { onSelBtn(b); });
      // a touch selection (long press, then the handles) sends no mouseup: follow selectionchange once it settles.
      // A tap on the button would clear the selection before its click, so the touch itself acts
      b.addEventListener('touchstart', function (e) { e.preventDefault(); }, { passive: false });
      b.addEventListener('touchend', function (e) { e.preventDefault(); onSelBtn(b); });
    });
    document.addEventListener('pointerdown', function (e) { touched = e.pointerType === 'touch'; }, true);
    document.addEventListener('mouseup', function () { if (!touched) setTimeout(onSelect, 0); });
    document.addEventListener('keyup', function (e) { if (!ours(e.target)) onSelect(); });
    document.addEventListener('selectionchange', function () {
      var sel = getSelection();
      if (!sel || sel.isCollapsed) selBtn.hidden = selEdit.hidden = true;
      clearTimeout(selTimer);
      if (touched && sel && !sel.isCollapsed) selTimer = setTimeout(onSelect, 400);
    });
    document.addEventListener('mousedown', onDown);
    document.addEventListener('click', onClick);
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', relayout);
    window.addEventListener('load', dirtyAll);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(dirtyAll);
    if ('ResizeObserver' in window) {
      var ro = new ResizeObserver(dirtyAll);
      scopes.forEach(function (s) { ro.observe(s.root); });
    }
  }

  // ---------------------------------------------------------------- reports: the "read" item at the end
  function readBox(rows) {
    if (!REPORT || ui.read) return;
    var row = rows.filter(function (r) { return r.page === page; })[0];
    if (!row || !row.tracked) return;
    var box = el('section', 'talk-ui talk-readbox');
    box.setAttribute('data-talk', 'read');
    box.setAttribute('data-talk-states', tr('read.states'));
    box.setAttribute('data-talk-wake', 'none');
    box.setAttribute('data-talk-title', tr('read.title'));
    box.appendChild(el('div', 'talk-readbox-title', tr('read.title')));
    box.appendChild(el('p', 'talk-readbox-note', tr('read.note')));
    content.appendChild(box);
    build(box);
    render('read');
    updateDock();
  }

  // ---------------------------------------------------------------- reports: the sidebar
  var PREFS = 'talk-sidebar';
  // the width at first is 340 px; a saved 280 is the first default (saved with the other settings, not chosen), so it
  // moves up too. rh: the reports' height, 0 for half
  var SB_W = 340, OLD_SB_W = 280;
  var sb = { open: true, width: SB_W, fold: {}, zoom: 1, rh: 0 };
  var sbEl = null, sbTog = null, sbBack = null, zoomLabel = null, rp = null, tp = null, tocLinks = [], tocQueued = false;
  var unzoomBtn = null, homeLink = null;

  // the layout's width (window.innerWidth follows pinch zoom on iOS). Under 900 the sidebar lies over the report;
  // under 700 (a phone) the browser's own pinch zoom replaces the report's zoom
  function layoutWidth() { return document.documentElement.clientWidth; }
  function phone() { return layoutWidth() < 700; }

  // the report's own styles, mended in place. A rounded box with a stripe on one side: that side's corners square (the
  // stripe would bend along them like a fingernail). On a phone, a grid or a row of boxes made for a wide screen and
  // wider than its place: one column, or wrapped. The style each had is kept (mended): the text written back by Edit
  // is the page's own
  function mendReport() {
    var all = content.querySelectorAll('*'), narrow = phone();
    function mend(e) { if (!mended.has(e)) mended.set(e, e.getAttribute('style')); return e.style; }
    for (var i = 0; i < all.length && i < 8000; i++) {
      var e = all[i];
      if (ours(e)) continue;
      var s = getComputedStyle(e), d = s.display;
      var other = Math.max(parseFloat(s.borderTopWidth) || 0, parseFloat(s.borderBottomWidth) || 0);
      [['Left', 'borderTopLeftRadius', 'borderBottomLeftRadius'], ['Right', 'borderTopRightRadius', 'borderBottomRightRadius']]
        .forEach(function (k) {
          var w = parseFloat(s['border' + k[0] + 'Width']) || 0;
          if (w >= 3 && w > other * 2 && (parseFloat(s[k[1]]) || parseFloat(s[k[2]]))) mend(e)[k[1]] = mend(e)[k[2]] = '0';
        });
      if (!narrow || e.scrollWidth <= e.clientWidth + 1) continue;
      if (d === 'grid' || d === 'inline-grid') mend(e).gridTemplateColumns = 'minmax(0, 1fr)';
      else if ((d === 'flex' || d === 'inline-flex') && s.flexWrap === 'nowrap' && s.flexDirection.indexOf('row') === 0) {
        mend(e).flexWrap = 'wrap';
      }
    }
  }
  var reportsOff = false, reportsFirst = null, reportsTimer = 0;

  function loadPrefs() {
    try {
      var v = JSON.parse(localStorage.getItem(PREFS) || 'null');
      if (v && typeof v === 'object') {
        if (typeof v.open === 'boolean') sb.open = v.open;
        if (typeof v.width === 'number') sb.width = v.width === OLD_SB_W ? SB_W : Math.max(200, Math.min(640, v.width));
        if (v.fold && typeof v.fold === 'object') sb.fold = v.fold;
        if (typeof v.zoom === 'number' && v.zoom > 0) sb.zoom = v.zoom;
        if (typeof v.rh === 'number' && v.rh >= 0) sb.rh = v.rh;
      }
    } catch (e) {}
  }
  function savePrefs() {
    try { localStorage.setItem(PREFS, JSON.stringify(sb)); } catch (e) {}
  }

  // the report: <main>, else a box around what <body> holds besides talkpage's parts
  function findContent() {
    var m = document.querySelector('main');
    if (m) return m;
    var box = el('div', 'talk-content');
    [].slice.call(document.body.childNodes).forEach(function (n) {
      if (n.nodeType === 1 && (ours(n) || /^(SCRIPT|STYLE|LINK|TEMPLATE)$/.test(n.tagName))) return;
      box.appendChild(n);
    });
    document.body.insertBefore(box, document.body.firstChild);
    return box;
  }

  function toggleFold(key, head, body, sec) {
    if (sb.fold[key]) delete sb.fold[key]; else sb.fold[key] = true;
    paintFold(key, head, body, sec);
    savePrefs();
  }
  function paintFold(key, head, body, sec) {
    var folded = !!sb.fold[key];
    body.hidden = folded;
    head.setAttribute('aria-expanded', String(!folded));
    if (sec) sec.classList.toggle('talk-folded', folded);
  }

  function pane(key, name) {
    var p = { sec: el('section', 'talk-sb-pane'), head: button('talk-sb-head', name), body: el('div', 'talk-sb-body') };
    p.head.addEventListener('click', function () { toggleFold(key, p.head, p.body, p.sec); });
    p.sec.appendChild(p.head);
    p.sec.appendChild(p.body);
    paintFold(key, p.head, p.body, p.sec);
    return p;
  }

  function buildSidebar() {
    loadPrefs();
    if (layoutWidth() < 900) sb.open = false;              // over the report on a narrow window: closed at first
    if (phone()) sb.zoom = 1;
    document.documentElement.classList.add('talk-has-sb');
    mendReport();
    var bar = el('div', 'talk-ui talk-sbbar');
    sbTog = button('talk-sb-tog', '☰');
    sbTog.title = tr('sb.toggle');
    sbTog.setAttribute('aria-label', tr('sb.toggle'));
    var minus = button('talk-sb-zbtn', '−'), plus = button('talk-sb-zbtn', '＋'), fit = button('talk-sb-fit', tr('sb.fit'));
    zoomLabel = button('talk-sb-zoom', '100%');
    minus.title = tr('sb.zoomout');
    plus.title = tr('sb.zoomin');
    zoomLabel.title = tr('sb.zoomreset');
    fit.title = tr('sb.fit.title');
    [sbTog, minus, zoomLabel, plus, fit].forEach(function (x) { bar.appendChild(x); });
    if (!LISTING) {                                        // back to the list of reports, once the server says it has one
      homeLink = el('a', 'talk-sb-home', tr('sb.home'));
      homeLink.href = '/';
      homeLink.title = tr('sb.home.title');
      homeLink.hidden = true;
      bar.insertBefore(homeLink, sbTog.nextSibling);
    }
    sbEl = el('nav', 'talk-ui talk-sb');
    sbEl.style.width = sb.width + 'px';
    rp = pane('reports', tr('sb.reports'));
    rp.sec.hidden = true;                                  // until /_talk/api/reports answers
    rp.sec.classList.add('talk-sb-reps');
    rp.total = el('span', 'talk-sb-total');                 // all the unread reports, and how many came since
    rp.total.title = tr('sb.total.title');
    rp.head.appendChild(rp.total);
    // this page's headings: always open, so no heading of their own; the bar above them sets the reports' height
    tp = { sec: el('section', 'talk-sb-pane talk-sb-toc'), body: el('div', 'talk-sb-body') };
    tp.sec.appendChild(tp.body);
    var split = el('div', 'talk-sb-split');
    split.title = tr('sb.split');
    var grip = el('div', 'talk-sb-grip');
    grip.title = tr('sb.grip');
    [rp.sec, split, tp.sec, grip].forEach(function (x) { sbEl.appendChild(x); });
    splitter(split);
    sbBack = el('div', 'talk-ui talk-sb-back');            // a tap outside the sidebar lying over the report closes it
    sbBack.hidden = true;
    unzoomBtn = button('talk-ui talk-unzoom', '100%');
    unzoomBtn.title = tr('sb.zoomreset');
    unzoomBtn.hidden = true;
    [sbBack, sbEl, bar, unzoomBtn].forEach(function (x) { document.body.appendChild(x); });
    buildToc(tp.body);
    sbTog.addEventListener('click', function () { setOpen(!sb.open, true); });
    sbBack.addEventListener('click', function () { setOpen(false, false); });
    unzoomBtn.addEventListener('click', unzoom);
    if (window.visualViewport) {
      visualViewport.addEventListener('resize', placeUnzoom);
      visualViewport.addEventListener('scroll', placeUnzoom);
    }
    // the buttons keep what is in the middle of the window where it is; Ctrl + wheel keeps what is under the pointer
    minus.addEventListener('click', function () { zoomBy(-0.1, window.innerHeight / 2); });
    plus.addEventListener('click', function () { zoomBy(0.1, window.innerHeight / 2); });
    zoomLabel.addEventListener('click', function () { applyZoom(1, window.innerHeight / 2); savePrefs(); });
    fit.addEventListener('click', function () { fitZoom(); });
    window.addEventListener('wheel', function (e) {          // Ctrl + wheel zooms the report, not the browser
      if (!e.ctrlKey) return;
      e.preventDefault();
      zoomBy(e.deltaY < 0 ? 0.1 : -0.1, e.clientY);
    }, { passive: false });
    grip.addEventListener('pointerdown', function (e) {
      e.preventDefault();
      grip.setPointerCapture(e.pointerId);
      function move(ev) {
        sb.width = Math.max(200, Math.min(640, Math.round(ev.clientX)));
        sbEl.style.width = sb.width + 'px';
        placeContent();
      }
      function end() {
        grip.removeEventListener('pointermove', move);
        grip.removeEventListener('pointerup', end);
        grip.removeEventListener('pointercancel', end);
        savePrefs();
      }
      grip.addEventListener('pointermove', move);
      grip.addEventListener('pointerup', end);
      grip.addEventListener('pointercancel', end);
    });
    window.addEventListener('resize', placeContent);
    window.addEventListener('scroll', function () {
      if (tocQueued) return;
      tocQueued = true;
      requestAnimationFrame(function () { tocQueued = false; tocHere(); });
    }, { passive: true });
    applyZoom(sb.zoom);
    setOpen(sb.open, false);
    tocHere();
  }

  // the bar between the reports and this page's headings: dragged up and down, the reports' height (kept in this
  // browser); a double click puts them back to half and half
  function splitter(bar) {
    function apply() {
      if (sb.rh) sbEl.style.setProperty('--talk-sb-rflex', '0 1 ' + sb.rh + 'px');
      else sbEl.style.removeProperty('--talk-sb-rflex');
    }
    bar.addEventListener('pointerdown', function (e) {
      e.preventDefault();
      bar.setPointerCapture(e.pointerId);
      var top = rp.sec.getBoundingClientRect().top, max = sbEl.getBoundingClientRect().bottom - top - 80;
      function move(ev) { sb.rh = Math.round(Math.max(60, Math.min(max, ev.clientY - top))); apply(); }
      function end() {
        bar.removeEventListener('pointermove', move);
        bar.removeEventListener('pointerup', end);
        bar.removeEventListener('pointercancel', end);
        savePrefs();
      }
      bar.addEventListener('pointermove', move);
      bar.addEventListener('pointerup', end);
      bar.addEventListener('pointercancel', end);
    });
    bar.addEventListener('dblclick', function () { sb.rh = 0; apply(); savePrefs(); });
    apply();
  }

  function setOpen(on, save) {
    sb.open = on;
    sbEl.hidden = !on;
    sbTog.setAttribute('aria-expanded', String(on));
    if (save && layoutWidth() >= 900) savePrefs();
    placeContent();
  }

  // the report keeps its place; only where the sidebar would cover it, it moves right by that much
  function placeContent() {
    if (!content) return;
    content.style.left = content.style.maxWidth = '';
    if (sbBack) sbBack.hidden = !(sb.open && layoutWidth() < 900);
    var side = sbEl && sb.open && layoutWidth() >= 900, right = side ? sbEl.getBoundingClientRect().right + 12 : 12;
    var narrowed = roomForCards(right), r = content.getBoundingClientRect();
    if (narrowed || (side && r.left < right)) {
      if (getComputedStyle(content).position === 'static') content.style.position = 'relative';
      content.style.left = (right - r.left) / sb.zoom + 'px';     // a length on a zoomed element is zoomed too
    }
    relayout();
  }
  // the cards never cover the report: when the zoomed report and a margin for the cards do not fit side by side right
  // of the sidebar (x), the report starts at x and narrows to what is left (the same size, its lines wrap anew). Not in
  // a window too narrow even for that: there the margin gets numbers only
  function roomForCards(x) {
    if (!scopes.length) return false;
    var z = sb.zoom, r = content.getBoundingClientRect(), vw = document.documentElement.clientWidth;
    var room = vw - x - MARGIN_MIN * z - 24;
    if (Math.max(r.left, x) + r.width <= vw - MARGIN_MIN * z || room < 320) return false;
    content.style.maxWidth = room / z + 'px';
    return true;
  }

  // what is at the window's height y in the report: a line of text there (tried across the report), else the smallest
  // block around y, else the nearest block. Not a large box: the report's lines wrap anew at another zoom, so only a
  // line or a small block keeps its place
  var HOLD_BLOCKS = 'p, li, h1, h2, h3, h4, h5, h6, td, th, dt, dd, figcaption, caption, blockquote, pre, img, svg, canvas, video';
  function caretRange(x, y) {
    try {
      if (document.caretPositionFromPoint) {
        var p = document.caretPositionFromPoint(x, y);
        if (!p || !p.offsetNode) return null;
        var r = document.createRange();
        r.setStart(p.offsetNode, p.offset);
        return r;
      }
      return document.caretRangeFromPoint ? document.caretRangeFromPoint(x, y) : null;
    } catch (e) { return null; }
  }
  function spotAt(y) {
    var c = content.getBoundingClientRect();
    for (var i = 1; i <= 5; i++) {
      var x = Math.min(Math.max(c.left + c.width * i / 6, 1), window.innerWidth - 2), r = caretRange(x, y);
      var b = r && r.startContainer.nodeType === 3 && content.contains(r.startContainer) && !ours(r.startContainer) &&
              r.getBoundingClientRect();
      if (b && b.height && b.top <= y + 2 && b.bottom >= y - 2) return r;
    }
    var best = null, bh = Infinity, near = null, nd = Infinity;
    content.querySelectorAll(HOLD_BLOCKS).forEach(function (e) {
      if (ours(e) || e.parentElement && e.parentElement.closest('svg')) return;
      var b = e.getBoundingClientRect();
      if (!b.height) return;
      if (b.top <= y && b.bottom >= y) { if (b.height < bh) { bh = b.height; best = e; } }
      else { var d = Math.min(Math.abs(b.top - y), Math.abs(b.bottom - y)); if (d < nd) { nd = d; near = e; } }
    });
    return best || near || content;
  }
  // keeps what is at the window's height y there across a change of the zoom: returns what puts it back. Below a line
  // of text by a distance that grows with the zoom; in a block by the share of its height (a picture need not grow with
  // the zoom, a grid may put it elsewhere)
  function holdAt(y) {
    y = Math.min(Math.max(y, 1), window.innerHeight - 2);
    var s = spotAt(y), z0 = sb.zoom, b = s.getBoundingClientRect(), off = y - b.top, f = b.height ? off / b.height : 0;
    return function () {
      var line = !s.nodeType, n = (line ? s.startContainer.isConnected : s.isConnected) ? s.getBoundingClientRect()
                                                                                          : content.getBoundingClientRect();
      var d = n.top + (line ? off * sb.zoom / z0 : f * n.height) - y;
      if (Math.abs(d) >= 1) window.scrollBy({ top: d, behavior: 'instant' });
    };
  }

  // at: a height in the window whose text stays there (none on load)
  function applyZoom(z, at) {
    var keep = at == null ? null : holdAt(at);
    z = Math.max(0.5, Math.min(3, Math.round(z * 100) / 100));
    sb.zoom = z;
    content.style.zoom = z === 1 ? '' : String(z);
    zoomLabel.textContent = Math.round(z * 100) + '%';
    placeContent();
    dirtyAll();
    if (keep) keep();
  }
  function zoomBy(d, at) { applyZoom(Math.round((sb.zoom + d) * 10) / 10, at); savePrefs(); }

  // after a pinch zoom: "100%" at the top right of what is on screen, its size kept (a fixed element sits on the layout
  // viewport, which the visual viewport moves over and magnifies)
  function placeUnzoom() {
    var v = window.visualViewport, on = !!v && v.scale > 1.05;
    unzoomBtn.hidden = !on;
    if (!on) return;
    var s = 1 / v.scale;
    unzoomBtn.style.transform = 'translate(' + (v.offsetLeft + v.width - 10 * s) + 'px, ' + (v.offsetTop + 10 * s) +
      'px) scale(' + s + ') translateX(-100%)';
  }
  // a maximum scale of 1 for a moment brings the page back to its width
  function unzoom() {
    var m = document.querySelector('meta[name="viewport"]');
    if (!m) return;
    var was = m.getAttribute('content') || '';
    m.setAttribute('content', was.replace(/,?\s*maximum-scale\s*=[^,]*/i, '') + ', maximum-scale=1');
    setTimeout(function () { m.setAttribute('content', was); placeUnzoom(); }, 400);
  }

  // the zoom at which the report spans from the sidebar to the window's right edge less the comments' margin; the
  // cards grow with the same zoom: (report + card) × zoom + the gaps = the room
  function fitZoom() {
    content.style.maxWidth = '';                           // the report's own width, not the one narrowed for the cards
    var r = content.getBoundingClientRect(), cards = scopes.length ? CARD_MAX : 0;
    var left = sb.open && layoutWidth() >= 900 ? sbEl.getBoundingClientRect().right + 12 : 12;
    var avail = document.documentElement.clientWidth - left - (cards ? 24 : 12);
    if (r.width > 0 && avail > 0) applyZoom(avail / (r.width / sb.zoom + cards), window.innerHeight / 2);
    savePrefs();
  }

  function buildToc(box) {
    var hs = [].slice.call(content.querySelectorAll('h1, h2, h3')).filter(function (h) { return !ours(h); });
    if (!hs.length) { box.appendChild(el('p', 'talk-sb-empty', tr('sb.notoc'))); return; }
    hs.forEach(function (h) {
      var a = el('a', 'talk-toc talk-toc-' + h.tagName.toLowerCase(), squash(h.textContent));
      a.href = h.id ? '#' + encodeURIComponent(h.id) : '#';
      a.addEventListener('click', function (e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button) return;
        e.preventDefault();
        h.scrollIntoView({ block: 'start', behavior: 'smooth' });
        if (layoutWidth() < 900) setOpen(false, false);
      });
      box.appendChild(a);
      tocLinks.push({ h: h, a: a });
    });
  }

  // the heading being read
  function tocHere() {
    if (!tocLinks.length) return;
    var cur = tocLinks[0];
    tocLinks.forEach(function (t) { if (t.h.getBoundingClientRect().top < 90) cur = t; });
    tocLinks.forEach(function (t) {
      t.a.classList.toggle('talk-here', t === cur);
      if (t === cur) t.a.setAttribute('aria-current', 'location'); else t.a.removeAttribute('aria-current');
    });
    var b = tp.body, a = cur.a;
    if (a.offsetTop < b.scrollTop) b.scrollTop = a.offsetTop - 8;
    else if (a.offsetTop + a.offsetHeight > b.scrollTop + b.clientHeight) b.scrollTop = a.offsetTop + a.offsetHeight - b.clientHeight + 8;
  }

  function isUnread(r) { return r.tracked && !r.read; }

  // a report in the sidebar: one line, the name cut with … and its round and time after it, which go to a second line
  // only when they do not fit (the whole title in the tooltip). A title that ends with its round and time ("… r3 10-29
  // 15:50") is shown without them, as they follow anyway
  var WHEN_RE = /\s+r\d+\s+\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}$/;
  // sub: the submission whose folder the row is in, ref: the name of the group the row stays in as well (another owner's)
  function reportRow(r, sub, ref) {
    var a = el('a', 'talk-sb-row'), txt = el('span', 'talk-sb-text'), title = r.title || r.theme || r.page;
    var rn = /-(r\d+)/.exec(r.round || '');
    a.href = '/' + r.page.split('/').map(encodeURIComponent).join('/');
    a.title = title;
    if (isUnread(r)) a.classList.add('talk-unread');
    if (r.page === page) { a.classList.add('talk-here'); a.setAttribute('aria-current', 'page'); }
    txt.appendChild(el('span', 'talk-sb-t', (r.star ? '★ ' : '') + (title.replace(WHEN_RE, '') || title)));
    var when = [rn && rn[1], (r.time || '').slice(5)].filter(Boolean).join(' ');
    if (when) txt.appendChild(el('span', 'talk-sb-meta', when));
    if (!reportsFirst[r.page]) txt.appendChild(el('span', 'talk-sb-new', tr('sb.new')));
    var br = sub && (sub.basis_rounds || {})[r.theme], brn = br && /-(r\d+)/.exec(br);
    if (br && br !== r.round) {                             // a newer round since the submission was based on it
      txt.appendChild(el('span', 'talk-sb-note', tr('sb.based', { r: brn ? brn[1] : br })));
    }
    if (ref) txt.appendChild(el('span', 'talk-sb-note talk-sb-other', ref));
    a.appendChild(txt);
    return a;
  }

  // a submission (a page with <meta name="report-basis">): a folder like a release, the page's own row with a mark and
  // a button that shows the work reports it is based on (closed at first, unless this page is one of them)
  function subFolder(s, kids, own, ref) {
    var box = el('div', 'talk-sb-sub'), head = el('div', 'talk-sb-subhead'), body = el('div', 'talk-sb-subbody');
    var open = button('talk-sb-open', '');
    open.title = tr('sb.basis');
    open.setAttribute('aria-label', tr('sb.basis'));
    head.appendChild(open);
    head.appendChild(el('span', 'talk-sb-tag', tr('sb.submission')));
    head.appendChild(reportRow(s));
    var n = kids.filter(isUnread).length;
    if (n) head.appendChild(el('span', 'talk-sb-gunread', tr('sb.unread', { n: n })));
    if (s.page === page) head.classList.add('talk-here');
    kids.forEach(function (k) { body.appendChild(reportRow(k, s, own(k) ? '' : ref(k))); });
    if (!kids.length) body.appendChild(el('p', 'talk-sb-empty', tr('sb.nobasis')));
    if ((s.basis_missing || []).length) {
      body.appendChild(el('p', 'talk-sb-empty', tr('sb.missing', { x: s.basis_missing.join(', ') })));
    }
    var key = 'sub:' + s.page, inside = kids.some(function (k) { return k.page === page; });
    function shut() { return key in sb.fold ? !!sb.fold[key] : !inside; }
    function paint() { var x = shut(); body.hidden = x; open.setAttribute('aria-expanded', String(!x)); }
    open.addEventListener('click', function () { sb.fold[key] = shut() ? 0 : 1; savePrefs(); paint(); });
    paint();
    box.appendChild(head);
    box.appendChild(body);
    return box;
  }

  // the reports by place (a server of several folders) or by owner; unread ones bold, ones added since this page opened
  // marked new, this page marked; the ones hidden in the list left out (but this page). A submission comes first in
  // its group as a folder: the reports it is based on of the same owner (and group) move into it, another owner's stay
  // in their own group and appear in the folder too, with that owner's name
  function renderReports(rows) {
    rows = rows.filter(function (r) { return !r.hidden || r.page === page; });
    if (!reportsFirst) {
      reportsFirst = {};
      rows.forEach(function (r) { reportsFirst[r.page] = true; });
    }
    var unread = rows.filter(isUnread), fresh = unread.filter(function (r) { return !reportsFirst[r.page]; });
    rp.total.textContent = unread.length ? tr('sb.total', { n: unread.length }) +
      (fresh.length ? tr('sb.totalnew', { n: fresh.length }) : '') : '';
    rp.total.classList.toggle('talk-sb-fresh', !!fresh.length);
    var groups = [], by = {}, keep = rp.body.scrollTop, byTheme = {}, moved = {};
    var byPlace = rows.some(function (r) { return r.group; });
    function gkey(r) { return (byPlace ? r.group : r.owner) || ''; }
    rows.forEach(function (r) { if (r.tracked) byTheme[r.theme] = r; });
    function kidsOf(s) { return (s.basis || []).map(function (t) { return byTheme[t]; }).filter(Boolean); }
    rows.forEach(function (s) {
      if (!s.submission) return;
      kidsOf(s).forEach(function (k) { if (k.owner === s.owner && gkey(k) === gkey(s)) moved[k.page] = true; });
    });
    rows.forEach(function (r) {
      if (moved[r.page]) return;                            // in its submission's folder
      var name = gkey(r);
      if (!by[name]) { by[name] = []; groups.push(name); }
      by[name].push(r);
    });
    rp.body.textContent = '';
    if (!LISTING) {                            // the list of all reports, with its stars and tags
      var all = el('a', 'talk-sb-row talk-sb-all', tr('sb.all'));
      all.href = '/';
      rp.body.appendChild(all);
    }
    groups.forEach(function (name) {
      var rs = by[name], unread = {}, key = (byPlace ? 'place:' : 'owner:') + name;
      rs.forEach(function (r) {                             // the group's own rows and its submissions' moved ones
        (r.submission ? kidsOf(r).filter(function (k) { return moved[k.page]; }) : [r])
          .forEach(function (k) { if (isUnread(k) && gkey(k) === name) unread[k.page] = true; });
      });
      var n = Object.keys(unread).length;
      var g = el('div', 'talk-sb-group');
      var head = button('talk-sb-ghead', '');
      head.appendChild(el('span', 'talk-sb-gname', name || tr('sb.noowner')));
      if (n) head.appendChild(el('span', 'talk-sb-gunread', tr('sb.unread', { n: n })));
      var list = el('div', 'talk-sb-rows');
      head.addEventListener('click', function () { toggleFold(key, head, list); });
      paintFold(key, head, list);
      rs.filter(function (r) { return r.submission; }).concat(rs.filter(function (r) { return !r.submission; }))
        .forEach(function (r) {
          if (!r.submission) { list.appendChild(reportRow(r)); return; }
          list.appendChild(subFolder(r, kidsOf(r), function (k) { return k.owner === r.owner && gkey(k) === gkey(r); },
                                     function (k) { return k.owner !== r.owner ? k.owner || tr('sb.noowner') : gkey(k); }));
        });
      g.appendChild(head);
      g.appendChild(list);
      rp.body.appendChild(g);
    });
    rp.sec.hidden = false;
    rp.body.scrollTop = keep;
  }

  // every 30 s and when the tab comes to the front; 404 (a server without --reports): the headings alone
  function loadReports() {
    if (reportsOff) return;
    clearTimeout(reportsTimer);
    fetch(API + 'reports', { cache: 'no-store' })
      .then(function (r) {
        if (r.status === 404) { reportsOff = true; return null; }
        return json(r);
      })
      .then(function (d) {
        if (!d) return;
        var rows = Array.isArray(d.rows) ? d.rows : [];
        if (homeLink) homeLink.hidden = false;
        if (rp) renderReports(rows);
        readBox(rows);
      })
      .catch(function () {})
      .then(function () {
        if (reportsOff) return;
        reportsTimer = setTimeout(function () {
          if (document.visibilityState !== 'hidden') loadReports();
        }, 30000);
      });
  }

  // ---------------------------------------------------------------- Edit: the user fixes the page's text in place
  // Edit in the dock makes each block of text (a paragraph, a list item, a heading, a table cell …) take plain text;
  // Edit beside a selection does it for the block of the selected text alone. Leaving a block (or Enter) saves it:
  // /_talk/api/edit finds it in the page's file by its tag, its text and which one of the same it is, writes its new
  // content and keeps the fix for the agent (show). Esc puts it back. A block that holds other blocks stays as it is.
  var EDITABLE = 'p, li, h1, h2, h3, h4, h5, h6, td, th, dt, dd, figcaption, caption, blockquote';   // EDIT_TAGS of the server
  var FILE_PAGE = !html.hasAttribute('data-talk-page');    // the state is beside the page's own file, which can be written
  var editing = false, editOrig = new WeakMap(), editNote = null, mended = new WeakMap();

  function canEdit(e) {
    return !e.closest(OURS + ', [data-talk], [data-copy], svg') && !e.querySelector(EDITABLE) && !!squash(e.textContent);
  }
  function editables() { return [].filter.call(document.body.querySelectorAll(EDITABLE), canEdit); }
  function blockOf(node) {                                  // the block of text a node is in, when it can be written in
    var e = node && (node.nodeType === 1 ? node : node.parentElement), b = e && e.closest(EDITABLE);
    return b && canEdit(b) ? b : null;
  }
  function editBlock(t) { return t && t.closest ? t.closest('[data-talk-edit]') : null; }
  // which one of the blocks with its tag and its text it is, and how many there are, as the server counts them in the
  // file (talkpage's own parts and the items' threads are not in the file)
  function blockKey(b, text) {
    var tag = b.tagName.toLowerCase(), n = 0, nth = -1;
    document.body.querySelectorAll(tag).forEach(function (x) {
      if (x.closest(OURS + ', [data-talk]') || squash(x.textContent) !== text) return;
      if (x === b) nth = n;
      n++;
    });
    return { tag: tag, nth: nth, count: n };
  }
  // the block's content as the page's file has it: without the styles mendReport() put on what is inside
  function sourceHTML(b) {
    var all = b.querySelectorAll('*');
    if (![].some.call(all, function (e) { return mended.has(e); })) return b.innerHTML;
    var copy = b.cloneNode(true), twins = copy.querySelectorAll('*');
    [].forEach.call(all, function (e, i) {
      if (!mended.has(e)) return;
      var s = mended.get(e);
      if (s == null) twins[i].removeAttribute('style'); else twins[i].setAttribute('style', s);
    });
    return copy.innerHTML;
  }
  function makeEditable(e) {
    try { e.contentEditable = 'plaintext-only'; } catch (x) { e.contentEditable = 'true'; }
    e.spellcheck = false;
    e.setAttribute('data-talk-edit', '');
  }
  function unmakeEditable(e) { e.removeAttribute('contenteditable'); e.removeAttribute('data-talk-edit'); }

  function setEditing(on) {
    editing = on;
    html.classList.toggle('talk-editing', on);
    dock.edit.setAttribute('aria-pressed', String(on));
    if (selBtn) selBtn.hidden = selEdit.hidden = true;
    editables().forEach(function (e) {
      if (on) { makeEditable(e); return; }
      if (e === document.activeElement) e.blur();          // saves it
      unmakeEditable(e);
    });
  }
  // Edit beside the selection: that one block, with the selected text still selected (typing replaces it)
  function editOne(b, range) {
    makeEditable(b);
    b.focus({ preventScroll: true });
    var s = getSelection();
    s.removeAllRanges();
    if (range) s.addRange(range);
  }

  // "saving", "saved" or why not, just above the block's right end
  function noteEdit(b, text, bad) {
    if (!editNote) {
      var holder = el('div', 'talk-ui talk-layer');
      editNote = el('div', 'talk-edit-note');
      editNote.setAttribute('aria-live', 'polite');
      holder.appendChild(editNote);
      document.body.appendChild(holder);
    }
    editNote.textContent = text;
    editNote.block = b;
    editNote.classList.toggle('talk-edit-note-ng', !!bad);
    editNote.hidden = false;
    var r = b.getBoundingClientRect(), base = editNote.parentNode.getBoundingClientRect();
    editNote.style.left = Math.max(4, r.right - editNote.offsetWidth) - base.left + 'px';
    editNote.style.top = r.top - editNote.offsetHeight - 4 - base.top + 'px';
    clearTimeout(editNote.timer);
    if (!bad) editNote.timer = setTimeout(function () { editNote.hidden = true; }, 1500);
  }

  document.addEventListener('focusin', function (e) {
    var b = editBlock(e.target);
    if (b && !editOrig.has(b)) {                            // a block that could not be saved keeps its first text
      var text = squash(b.textContent);
      editOrig.set(b, { html: b.innerHTML, text: text, key: blockKey(b, text) });
    }
  });
  document.addEventListener('keydown', function (e) {
    var b = editBlock(e.target);
    if (!b || e.isComposing || e.keyCode === 229) return;   // Enter while converting (Japanese input) only confirms
    if (e.key === 'Enter') { e.preventDefault(); b.blur(); }
    if (e.key === 'Escape') {                               // back as it was; the open card stays
      var o = editOrig.get(b);
      if (o) b.innerHTML = o.html;
      e.stopPropagation();
      b.blur();
    }
  }, true);
  document.addEventListener('focusout', function (e) {
    var b = editBlock(e.target), o = b && editOrig.get(b);
    if (b && !editing) unmakeEditable(b);                   // the one block of Edit beside a selection
    if (!o) return;
    dirtyAll();                                             // its text nodes changed: the comments' places too
    if (b.innerHTML === o.html) {                           // nothing changed, or put back with Esc
      editOrig.delete(b);
      b.classList.remove('talk-edit-ng');
      if (editNote && editNote.block === b) editNote.hidden = true;
      return;
    }
    noteEdit(b, tr('edit.saving'));
    post('edit', { page: page, tag: o.key.tag, text: o.text, nth: o.key.nth, count: o.key.count, html: sourceHTML(b),
                   after: squash(b.textContent) })
      .then(function () { editOrig.delete(b); b.classList.remove('talk-edit-ng'); noteEdit(b, tr('edit.saved')); })
      .catch(function (err) { b.classList.add('talk-edit-ng'); noteEdit(b, tr('edit.failed', { msg: err.message }), true); });
  });

  // ---------------------------------------------------------------- start, and the API for pages of their own
  window.TalkPage = {
    page: page,
    items: function () { return items; },
    on: function (fn) { listeners.push(fn); },
    user: function (id, body) {
      return post('user', Object.assign({ page: page, id: id }, body)).then(function (d) { take(d); return d; });
    },
    seen: function (id) { return post('seen', { page: page, id: id }).then(function (d) { take(d); return d; }); }
  };

  // ---------------------------------------------------------------- the page's own layers over the whole window
  // the cards, the dock and the sidebar sit above the report; a layer of the page that covers the window (a picture
  // shown large, a dialog) stays on top of them: they hide while it is open (html.talk-covered)
  var cover = null;
  function covers(e) {
    if (!(e instanceof Element) || ours(e)) return false;
    var s = getComputedStyle(e);
    if (s.position !== 'fixed' || s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false;
    var r = e.getBoundingClientRect();
    return r.width >= window.innerWidth * 0.8 && r.height >= window.innerHeight * 0.8;
  }
  function watchCover() {
    if (!('MutationObserver' in window)) return;
    new MutationObserver(function (ms) {
      var found = cover && cover.isConnected && covers(cover) ? cover : null;
      ms.forEach(function (m) {
        if (found) return;
        var list = m.type === 'attributes' ? [m.target] : [].slice.call(m.addedNodes);
        list.some(function (e) { return covers(e) && (found = e); });
      });
      if (found === cover) return;
      cover = found;
      html.classList.toggle('talk-covered', !!cover);
      picReset();
    }).observe(document.body, { subtree: true, childList: true, attributes: true,
                                attributeFilter: ['class', 'style', 'hidden', 'open'] });
    watchPicture();
  }

  // a picture shown large by such a layer: the wheel (with Ctrl or not) zooms it around the pointer, up to 16 times, and a
  // drag moves it. A click that did not drag still closes the layer as the page does, and so does Esc
  var pic = null, picZ = 1, picX = 0, picY = 0, picDrag = null, picMoved = false, picNote = null;
  function picOf(layer) {                                   // the largest picture in the layer (an outer svg, not its parts)
    var best = null, area = 0;
    layer.querySelectorAll('img, svg, canvas, video').forEach(function (e) {
      if (e.parentElement && e.parentElement.closest('svg')) return;
      var r = e.getBoundingClientRect();
      if (r.width * r.height > area) { area = r.width * r.height; best = e; }
    });
    return best;
  }
  function picSet() {
    pic.style.transformOrigin = '0 0';
    pic.style.transform = picZ === 1 ? '' : 'translate(' + picX + 'px, ' + picY + 'px) scale(' + picZ + ')';
    pic.style.cursor = picZ === 1 ? '' : picDrag ? 'grabbing' : 'grab';
    picNote.textContent = tr('pic.note', { z: Math.round(picZ * 100) });
  }
  function picReset() {
    if (pic) { pic.style.transform = pic.style.transformOrigin = pic.style.cursor = ''; }
    pic = null; picZ = 1; picX = picY = 0; picDrag = null;
    if (!picNote) { picNote = el('div', 'talk-ui talk-pic-note'); document.body.appendChild(picNote); }
    picNote.hidden = true;
    if (cover && (pic = picOf(cover))) { picNote.hidden = false; picSet(); }
  }
  function watchPicture() {
    window.addEventListener('wheel', function (e) {
      if (!cover || !pic || !pic.isConnected) return;
      e.preventDefault();
      e.stopPropagation();                                  // not the report's zoom (Ctrl) behind the layer
      var r = pic.getBoundingClientRect(), ox = r.left - picX, oy = r.top - picY;
      // by the amount turned: a notch of a mouse wheel (100 px) is 1.25 times, a touchpad's small steps zoom smoothly
      var d = e.deltaY * (e.deltaMode === 1 ? 33 : e.deltaMode === 2 ? window.innerHeight : 1);
      var z = Math.min(16, Math.max(1, picZ * Math.pow(1.25, Math.max(-4, Math.min(4, -d / 100)))));
      if (z === 1) { picX = picY = 0; }
      else {                                                // the point under the pointer stays under it
        picX = e.clientX - ox - (e.clientX - ox - picX) * z / picZ;
        picY = e.clientY - oy - (e.clientY - oy - picY) * z / picZ;
      }
      picZ = z;
      picSet();
    }, { passive: false, capture: true });
    window.addEventListener('pointerdown', function (e) {
      if (!cover || !pic || picZ === 1 || e.button !== 0) return;
      e.preventDefault();                                   // no dragging of the image itself
      picDrag = { x: e.clientX - picX, y: e.clientY - picY, sx: e.clientX, sy: e.clientY };
      picMoved = false;
      picSet();
    }, true);
    window.addEventListener('pointermove', function (e) {
      if (!picDrag) return;
      if (Math.abs(e.clientX - picDrag.sx) + Math.abs(e.clientY - picDrag.sy) > 4) picMoved = true;
      picX = e.clientX - picDrag.x;
      picY = e.clientY - picDrag.y;
      picSet();
    }, true);
    window.addEventListener('pointerup', function () { if (picDrag) { picDrag = null; picSet(); } }, true);
    window.addEventListener('click', function (e) {          // the click that ends a drag does not close the layer
      if (!picMoved) return;
      picMoved = false;
      e.preventDefault();
      e.stopPropagation();
    }, true);
  }

  // a link in the page to another page opens in a new tab, so the page stays where it was read; a link within the page,
  // one with its own target, and the sidebar's list (moving between reports) stay as they are
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    if (editing || a.hasAttribute('target') || a.hasAttribute('download') || a.closest(OURS)) return;
    if (!/^(https?|file):$/.test(a.protocol) || a.href.split('#')[0] === location.href.split('#')[0]) return;
    a.target = '_blank';
    a.rel = (a.rel ? a.rel + ' ' : '') + 'noopener';
  });

  // <body data-talk-listing>: the server's list of reports (no page file, so no state): the sidebar and zoom only
  var LISTING = false;
  function start() {
    var body = document.body;
    LISTING = body.hasAttribute('data-talk-listing');
    REPORT = !LISTING && (REPORT || body.hasAttribute('data-talk-report'));
    SIDEBAR = LISTING || REPORT || body.hasAttribute('data-talk-sidebar');
    watchCover();
    if (LISTING) {
      content = findContent();
      buildSidebar();
      loadReports();
      return;
    }
    lists().then(function () {
      document.querySelectorAll('[data-talk]').forEach(build);
      copies();
      if (SIDEBAR) content = findContent();
      buildDock();
      setupSelect();
      if (SIDEBAR) buildSidebar();
      if (SIDEBAR) loadReports();
      syncCards();
      updateDock();
      loop(true);
    });
  }
  document.addEventListener('visibilitychange', function () {
    if (SIDEBAR && document.visibilityState === 'visible') loadReports();
    if (LISTING || !dock.presence) return;
    targets().forEach(seen);
    pollOnVisibility();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
