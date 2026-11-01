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
      'comment': 'Comment',
      'comment.ph': 'Comment (Ctrl+Enter sends)',
      'send': 'Send',
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
      'expand': 'Show the whole thread',
      'close': 'Close',
      'lost': 'Comments not found in the text',
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
      'sb.page': 'This page',
      'sb.noowner': 'No owner',
      'sb.unread': 'unread {n}',
      'sb.new': 'New',
      'sb.notoc': 'No headings',
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
      'comment': 'コメント',
      'comment.ph': 'コメント（Ctrl+Enter で送信）',
      'send': '送信',
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
      'expand': 'やりとりの全文表示',
      'close': '閉じる',
      'lost': '本文で見つからないコメント',
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
      'sb.page': 'このページ',
      'sb.noowner': '担当なし',
      'sb.unread': '未読 {n}',
      'sb.new': '新',
      'sb.notoc': '見出しなし',
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
  var MARKS = { 'new': tr('mark.new'), wait: tr('mark.wait'), read: tr('mark.read'), err: tr('mark.err') };
  var items = {};          // id -> item as the server keeps it
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
    u.mark.textContent = MARKS[m] || '';
    u.mark.setAttribute('data-m', m);
    u.mark.title = m === 'wait' ? tr('mark.wait.title') : '';
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
    [dock.unread, dock.waiting, dock.resolved, dock.progress, dock.presence].forEach(function (x) { d.appendChild(x); });
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
  // talkpage's own parts: their text is not the report's, and a selection in them is not a comment
  var OURS = '.talk-ui, .talk-bar, .talk-thread, .talk-dock, .talk-copy-btn, .talk-copied';
  var SKIP = OURS + ', script, style, noscript, textarea, template';
  var CARD_MAX = 340, MARGIN_MIN = 240, CARD_GAP = 8;
  var scopes = [];          // {root, prefix, re, lost, lostList, ix, dirty, pins}: where selecting text makes a comment
  var cards = {};           // id -> comment card of an item <prefix><number> the server keeps
  var draft = null;         // the card of a comment not sent yet (not on the server)
  var openNow = null, big = null, showResolved = false;
  var layer = null, selBtn = null, content = null, layoutQueued = false;
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

  // the first place of the text in the index, white space aside; null when it is not there
  function find(ix, text) {
    var needle = text.replace(/\s+/g, '');
    var i = needle ? ix.flat.indexOf(needle) : -1;
    if (i < 0) return null;
    var a = ix.at[i], b = ix.at[i + needle.length - 1];
    var r = document.createRange();
    r.setStart(a[0], a[1]);
    r.setEnd(b[0], b[1] + 1);
    return r;
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
    Object.keys(items).concat(order, Object.keys(cards)).forEach(function (id) {
      var m = re.exec(id);
      if (m) max = Math.max(max, +m[1]);
    });
    return prefix + (max + 1);
  }

  function makeCard(id, scope, title, isDraft) {
    var c = { id: id, card: true, scope: scope, title: title, open: false, visible: false, shown: -1 };
    c.el = el('div', 'talk-ui talk-rcard');
    var head = el('div', 'talk-rcard-head');
    c.idEl = el('span', 'talk-rcard-id', id);
    c.mark = el('span', 'talk-mark');
    head.appendChild(c.idEl);
    head.appendChild(c.mark);
    c.quote = el('div', 'talk-rcard-quote', title);
    c.sum = el('div', 'talk-rcard-sum');
    c.body = el('div', 'talk-rcard-body');
    c.lines = el('div', 'talk-rcard-lines');
    var form = el('div', 'talk-form');
    c.ta = el('textarea');
    c.ta.rows = 2;
    c.ta.placeholder = tr('comment.ph');
    c.send = button('talk-send', tr('send'));
    form.appendChild(c.ta);
    form.appendChild(c.send);
    var acts = el('div', 'talk-rcard-acts');
    c.res = button('talk-rcard-res', tr('resolve'));
    c.expand = button('talk-rcard-exp', '⤢');
    c.expand.title = tr('expand');
    c.expand.setAttribute('aria-label', tr('expand'));
    acts.appendChild(c.res);
    acts.appendChild(c.expand);
    [c.lines, form, acts].forEach(function (x) { c.body.appendChild(x); });
    [head, c.quote, c.sum, c.body].forEach(function (x) { c.el.appendChild(x); });
    c.pin = button('talk-ui talk-pin', id);
    c.el.addEventListener('click', function (e) {
      if (e.target.closest('button, textarea, a')) return;
      if (!c.open) openCard(c); else openBig(c);
    });
    c.expand.addEventListener('click', function () { openBig(c); });
    c.pin.addEventListener('click', function () { openBig(c); });
    c.send.addEventListener('click', function () { sendCard(c, c.ta); });
    c.ta.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.isComposing) { e.preventDefault(); sendCard(c, c.ta); }
    });
    c.ta.addEventListener('input', function () { keepDraft(c); });
    c.res.addEventListener('click', function () { resolveCard(c); });
    if (!isDraft) setDraftKey(c);
    byThread.set(c.el, c);
    if (io) io.observe(c.el);
    return c;
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
    c.res.hidden = !!c.draft;
    c.res.textContent = tr(c.resolved ? 'restore' : 'resolve');
    c.el.classList.toggle('talk-done', c.resolved);
    c.el.classList.toggle('talk-open', c.open);
    c.pin.classList.toggle('talk-pin-new', c.unread);      // a reply never opens a card: the page stays still
    if (big && big.c === c) renderBig();
    seen(c);
  }

  // cards for the items of the server the page does not declare
  function syncCards() {
    if (!scopes.length) return;
    if (draft && items[draft.id]) {                         // taken meanwhile (another tab): renumber the draft
      draft.id = nextId(draft.scope.prefix);
      draft.idEl.textContent = draft.pin.textContent = draft.id;
    }
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
    paintMarks();
    relayout();
    seen(c);
  }

  function closeCard(c) {
    if (c === draft) { dropDraft(); return; }
    c.open = false;
    c.el.classList.remove('talk-open');
    if (openNow === c) openNow = null;
    paintMarks();
    relayout();
  }

  function newDraft(x) {
    dropDraft();
    if (openNow) closeCard(openNow);
    var s = x.scope;
    var title = squash(x.text).slice(0, 200).trim();
    if (!find(index(s.root), title)) title = rangeText(s.root, x.range).slice(0, 200).trim();
    if (!title) return;
    var c = draft = makeCard(nextId(s.prefix), s, title, true);
    c.draft = true;
    c.sel = x.range;
    selBtn.hidden = true;
    getSelection().removeAllRanges();
    renderCard(c);
    openNow = c;
    c.open = true;
    c.el.classList.add('talk-open');
    layout();
    if (s.pins) openBig(c); else c.ta.focus({ preventScroll: true });
  }

  // a draft the user left without sending is gone
  function dropDraft() {
    var c = draft;
    if (!c || c.busy) return;
    draft = null;
    if (big && big.c === c) closeBig(true);
    if (openNow === c) openNow = null;
    [c.el, c.pin].forEach(function (x) { if (x.parentNode) x.parentNode.removeChild(x); });
    if (io) io.unobserve(c.el);
    byThread.delete(c.el);
    paintMarks();
  }

  function sendCard(c, ta) {
    var text = ta.value.trim();
    if (!text || c.busy) return;
    c.busy = true;
    c.send.disabled = true;
    if (big) big.send.disabled = true;
    post('user', { page: page, id: c.id, title: c.title, comment: text })   // a draft is made on the server here
      .then(function (d) {
        c.ta.value = '';
        if (big && big.c === c) big.ta.value = '';
        keepDraft(c);
        if (c === draft) {
          draft = null;
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
    var head = el('div', 'talk-modal-head');
    head.appendChild(el('span', 'talk-rcard-id', c.id));
    var x = button('talk-modal-close', '×');
    x.title = tr('close');
    x.setAttribute('aria-label', tr('close'));
    head.appendChild(x);
    var b = { c: c, el: m, shown: -1 };
    b.sum = el('div', 'talk-modal-sum');
    b.list = el('div', 'talk-entries talk-modal-list');
    var form = el('div', 'talk-form');
    b.ta = el('textarea');
    b.ta.rows = 3;
    b.ta.placeholder = tr('comment.ph');
    b.ta.value = c.ta.value;
    b.send = button('talk-send', tr('send'));
    form.appendChild(b.ta);
    form.appendChild(b.send);
    var acts = el('div', 'talk-rcard-acts');
    b.res = button('talk-rcard-res', '');
    acts.appendChild(b.res);
    [head, el('blockquote', 'talk-modal-quote', c.title), b.sum, b.list, form, acts]
      .forEach(function (y) { box.appendChild(y); });
    m.appendChild(box);
    m.addEventListener('click', function (e) { if (e.target === m) closeBig(); });
    x.addEventListener('click', function () { closeBig(); });
    b.send.addEventListener('click', function () { sendCard(c, b.ta); });
    b.ta.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.isComposing) { e.preventDefault(); sendCard(c, b.ta); }
    });
    b.ta.addEventListener('input', function () { c.ta.value = b.ta.value; keepDraft(c); });
    b.res.addEventListener('click', function () { resolveCard(c); });
    big = b;
    document.body.appendChild(m);
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
    big.res.hidden = !!c.draft;
    big.res.textContent = tr(c.resolved ? 'restore' : 'resolve');
  }

  // quiet: only take it away (another view replaces it)
  function closeBig(quiet) {
    if (!big) return;
    var c = big.c;
    big.el.parentNode.removeChild(big.el);
    big = null;
    if (!quiet && c.scope.pins) closeCard(c);         // no card to go back to; a draft is dropped
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
    var plain = [], strong = [], done = [];
    cardList().concat(draft ? [draft] : []).forEach(function (c) {
      if (!c.range) return;
      if (c.resolved) { if (showResolved) done.push(c.range); return; }
      (c.open ? strong : plain).push(c.range);
    });
    setMarks('talk-mark', plain, 0);
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

  // cards beside their marks in the right margin, each below the one above; a narrow margin gets numbers only
  function layout() {
    if (!layer) return;
    var base = layer.getBoundingClientRect(), vw = document.documentElement.clientWidth;
    scopes.forEach(function (s) {
      var all = cardList().filter(function (c) { return c.scope === s; });
      if (draft && draft.scope === s) all.push(draft);
      if (s.dirty) {
        s.ix = null;
        s.dirty = false;
        all.forEach(function (c) { c.range = undefined; });
      }
      all.forEach(function (c) {
        if (c.range === undefined) c.range = c.sel || find(s.ix || (s.ix = index(s.root)), c.title);
      });
      var sr = s.root.getBoundingClientRect();
      var margin = vw - sr.right;
      s.pins = margin < MARGIN_MIN;
      var w = Math.min(CARD_MAX, margin - 24), rows = [], lost = 0;
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
          top = Math.max(r.top, bottom + 4);
          c.pin.style.top = top + 'px';
          c.pin.style.left = vw - c.pin.offsetWidth - 6 - base.left + 'px';
          bottom = top + c.pin.offsetHeight;
        } else {
          c.el.style.width = w + 'px';
          c.el.style.left = sr.right + 12 - base.left + 'px';
          top = Math.max(r.top, bottom + CARD_GAP);
          c.el.style.top = top + 'px';
          bottom = top + c.el.offsetHeight;
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

  // the "comment" button by a selection of the report's text
  function onSelect() {
    var sel = getSelection(), s = null, r = null;
    if (sel && sel.rangeCount && !sel.isCollapsed) {
      r = sel.getRangeAt(0);
      s = scopeOf(r.commonAncestorContainer);
      if (s && (ours(r.commonAncestorContainer) || ours(r.startContainer) || ours(r.endContainer) ||
                !squash(sel.toString()))) s = null;
    }
    if (!s) { selBtn.hidden = true; selBtn.sel = null; return; }
    var rects = r.getClientRects(), last = rects[rects.length - 1] || r.getBoundingClientRect();
    var base = layer.getBoundingClientRect(), vw = document.documentElement.clientWidth;
    selBtn.hidden = false;
    selBtn.style.left = Math.max(4, Math.min(last.right + 4, vw - selBtn.offsetWidth - 8)) - base.left + 'px';
    selBtn.style.top = last.bottom + (touched ? 28 : 4) - base.top + 'px';     // below a phone's selection handle
    selBtn.sel = { scope: s, range: r.cloneRange(), text: sel.toString() };
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
    if (e.button !== 0 || ours(e.target)) return;
    var sel = getSelection();
    if (sel && !sel.isCollapsed) return;
    var p = caretAt(e.clientX, e.clientY);
    if (!p) return;
    var hit = cardList().filter(function (c) {
      if (!c.range || c.resolved && !showResolved) return false;
      try { return c.range.isPointInRange(p[0], p[1]); } catch (x) { return false; }
    })[0];
    if (!hit) return;
    if (hit.scope.pins) openBig(hit); else openCard(hit);
  }

  // elsewhere: the open card closes, a draft is dropped
  function onDown(e) {
    if (e.target.closest && e.target.closest('.talk-rcard, .talk-pin, .talk-modal, .talk-selbtn')) return;
    if (draft) dropDraft(); else if (openNow) closeCard(openNow);
  }

  function onKey(e) {
    if (e.key !== 'Escape' || e.isComposing) return;
    if (big) closeBig();
    else if (draft) dropDraft();
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
    layer = el('div', 'talk-ui talk-layer');
    document.body.appendChild(layer);
    selBtn = button('talk-ui talk-selbtn', tr('comment'));
    selBtn.hidden = true;
    layer.appendChild(selBtn);
    selBtn.addEventListener('mousedown', function (e) { e.preventDefault(); });    // keeps the selection
    selBtn.addEventListener('click', function () { if (selBtn.sel) newDraft(selBtn.sel); });
    // a touch selection (long press, then the handles) sends no mouseup: follow selectionchange once it settles.
    // A tap on the button would clear the selection before its click, so the touch itself opens the draft
    selBtn.addEventListener('touchstart', function (e) { e.preventDefault(); }, { passive: false });
    selBtn.addEventListener('touchend', function (e) {
      e.preventDefault();
      if (selBtn.sel) newDraft(selBtn.sel);
    });
    document.addEventListener('pointerdown', function (e) { touched = e.pointerType === 'touch'; }, true);
    document.addEventListener('mouseup', function () { if (!touched) setTimeout(onSelect, 0); });
    document.addEventListener('keyup', function (e) { if (!ours(e.target)) onSelect(); });
    document.addEventListener('selectionchange', function () {
      var sel = getSelection();
      if (!sel || sel.isCollapsed) selBtn.hidden = true;
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
  var sb = { open: true, width: 280, fold: {}, zoom: 1 };
  var sbEl = null, sbTog = null, sbBack = null, zoomLabel = null, rp = null, tp = null, tocLinks = [], tocQueued = false;
  var unzoomBtn = null;

  // the layout's width (window.innerWidth follows pinch zoom on iOS). Under 900 the sidebar lies over the report;
  // under 700 (a phone) the browser's own pinch zoom replaces the report's zoom
  function layoutWidth() { return document.documentElement.clientWidth; }
  function phone() { return layoutWidth() < 700; }

  // the report's own styles, mended in place. A rounded box with a stripe on one side: that side's corners square (the
  // stripe would bend along them like a fingernail). On a phone, a grid or a row of boxes made for a wide screen and
  // wider than its place: one column, or wrapped
  function mendReport() {
    var all = content.querySelectorAll('*'), narrow = phone();
    for (var i = 0; i < all.length && i < 8000; i++) {
      var e = all[i];
      if (ours(e)) continue;
      var s = getComputedStyle(e), d = s.display;
      var other = Math.max(parseFloat(s.borderTopWidth) || 0, parseFloat(s.borderBottomWidth) || 0);
      [['Left', 'borderTopLeftRadius', 'borderBottomLeftRadius'], ['Right', 'borderTopRightRadius', 'borderBottomRightRadius']]
        .forEach(function (k) {
          var w = parseFloat(s['border' + k[0] + 'Width']) || 0;
          if (w >= 3 && w > other * 2 && (parseFloat(s[k[1]]) || parseFloat(s[k[2]]))) e.style[k[1]] = e.style[k[2]] = '0';
        });
      if (!narrow || e.scrollWidth <= e.clientWidth + 1) continue;
      if (d === 'grid' || d === 'inline-grid') e.style.gridTemplateColumns = 'minmax(0, 1fr)';
      else if ((d === 'flex' || d === 'inline-flex') && s.flexWrap === 'nowrap' && s.flexDirection.indexOf('row') === 0) {
        e.style.flexWrap = 'wrap';
      }
    }
  }
  var reportsOff = false, reportsFirst = null, reportsTimer = 0;

  function loadPrefs() {
    try {
      var v = JSON.parse(localStorage.getItem(PREFS) || 'null');
      if (v && typeof v === 'object') {
        if (typeof v.open === 'boolean') sb.open = v.open;
        if (typeof v.width === 'number') sb.width = Math.max(200, Math.min(520, v.width));
        if (v.fold && typeof v.fold === 'object') sb.fold = v.fold;
        if (typeof v.zoom === 'number' && v.zoom > 0) sb.zoom = v.zoom;
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
    sbEl = el('nav', 'talk-ui talk-sb');
    sbEl.style.width = sb.width + 'px';
    rp = pane('reports', tr('sb.reports'));
    rp.sec.hidden = true;                                  // until /_talk/api/reports answers
    tp = pane('page', tr('sb.page'));
    tp.sec.classList.add('talk-sb-toc');
    var grip = el('div', 'talk-sb-grip');
    grip.title = tr('sb.grip');
    [rp.sec, tp.sec, grip].forEach(function (x) { sbEl.appendChild(x); });
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
    minus.addEventListener('click', function () { zoomBy(-0.1); });
    plus.addEventListener('click', function () { zoomBy(0.1); });
    zoomLabel.addEventListener('click', function () { applyZoom(1); savePrefs(); });
    fit.addEventListener('click', fitZoom);
    window.addEventListener('wheel', function (e) {          // Ctrl + wheel zooms the report, not the browser
      if (!e.ctrlKey) return;
      e.preventDefault();
      zoomBy(e.deltaY < 0 ? 0.1 : -0.1);
    }, { passive: false });
    grip.addEventListener('pointerdown', function (e) {
      e.preventDefault();
      grip.setPointerCapture(e.pointerId);
      function move(ev) {
        sb.width = Math.max(200, Math.min(520, Math.round(ev.clientX)));
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
    content.style.left = '';
    if (sbBack) sbBack.hidden = !(sb.open && layoutWidth() < 900);
    if (sbEl && sb.open && layoutWidth() >= 900) {
      var r = content.getBoundingClientRect(), right = sbEl.getBoundingClientRect().right + 12;
      if (r.left < right) {
        if (getComputedStyle(content).position === 'static') content.style.position = 'relative';
        content.style.left = (right - r.left) / sb.zoom + 'px';     // a length on a zoomed element is zoomed too
      }
    }
    relayout();
  }

  function applyZoom(z) {
    z = Math.max(0.5, Math.min(3, Math.round(z * 100) / 100));
    sb.zoom = z;
    content.style.zoom = z === 1 ? '' : String(z);
    zoomLabel.textContent = Math.round(z * 100) + '%';
    placeContent();
    dirtyAll();
  }
  function zoomBy(d) { applyZoom(Math.round((sb.zoom + d) * 10) / 10); savePrefs(); }

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

  // the zoom at which the report spans from the sidebar to the window's right edge less the comments' margin
  function fitZoom() {
    var r = content.getBoundingClientRect();
    var left = sb.open && layoutWidth() >= 900 ? sbEl.getBoundingClientRect().right + 12 : 12;
    var avail = document.documentElement.clientWidth - left - (CARD_MAX + 24);
    if (r.width > 0 && avail > 0) applyZoom(avail / (r.width / sb.zoom));
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

  // the reports by owner; unread ones bold, ones added since this page opened marked new, this page marked
  function renderReports(rows) {
    if (!reportsFirst) {
      reportsFirst = {};
      rows.forEach(function (r) { reportsFirst[r.page] = true; });
    }
    var groups = [], by = {}, keep = rp.body.scrollTop;
    rows.forEach(function (r) {
      var name = r.owner || '';
      if (!by[name]) { by[name] = []; groups.push(name); }
      by[name].push(r);
    });
    rp.body.textContent = '';
    groups.forEach(function (name) {
      var rs = by[name], n = rs.filter(isUnread).length, key = 'owner:' + name;
      var g = el('div', 'talk-sb-group');
      var head = button('talk-sb-ghead', '');
      head.appendChild(el('span', 'talk-sb-gname', name || tr('sb.noowner')));
      if (n) head.appendChild(el('span', 'talk-sb-gunread', tr('sb.unread', { n: n })));
      var list = el('div', 'talk-sb-rows');
      head.addEventListener('click', function () { toggleFold(key, head, list); });
      paintFold(key, head, list);
      rs.forEach(function (r) {
        var a = el('a', 'talk-sb-row');
        a.href = '/' + r.page.split('/').map(encodeURIComponent).join('/');
        if (isUnread(r)) a.classList.add('talk-unread');
        if (r.page === page) { a.classList.add('talk-here'); a.setAttribute('aria-current', 'page'); }
        a.appendChild(el('span', 'talk-sb-t', r.title || r.theme || r.page));
        var meta = el('span', 'talk-sb-meta', r.time || '');
        if (!reportsFirst[r.page]) meta.appendChild(el('span', 'talk-sb-new', tr('sb.new')));
        a.appendChild(meta);
        list.appendChild(a);
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

  // <body data-talk-listing>: the server's list of reports (no page file, so no state): the sidebar and zoom only
  var LISTING = false;
  function start() {
    var body = document.body;
    LISTING = body.hasAttribute('data-talk-listing');
    REPORT = !LISTING && (REPORT || body.hasAttribute('data-talk-report'));
    SIDEBAR = LISTING || REPORT || body.hasAttribute('data-talk-sidebar');
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
