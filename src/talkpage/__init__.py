#!/usr/bin/env python3
"""talkpage: local web pages where the user marks items and writes comments, and a coding agent is woken to answer.

  python talkpage.py serve <root> [--port 8190] [--open PAGE] [--lang en|ja] [--name NAME.localhost] [--reports]
                           [--tailscale]
  python talkpage.py serve --place [GROUP:]ID=FOLDER ... [--fallback ID] [--marks FILE] --reports ...
  python talkpage.py wait  [--page P] [--settle 4] [--json]
  python talkpage.py reply --page P --id ID [--status S] [--text T | --text - | --file F] [--fields JSON] [--summary S]
  python talkpage.py ack   [--page P] [--id ID ...]
  python talkpage.py show  [--page P]
  python talkpage.py reports [list | owner THEME NAME ID | read THEME... | read all | unread THEME... | open [--owner S]]

serve: <root> holds the pages; the state of <dir>/<name>.html is kept beside it in <dir>/<name>.talk.json. Only
127.0.0.1 is served. The page's Edit lets the user fix its text in place: the server writes the page's file and keeps
the fix in the state (edits). wait: blocks until the user acts on a page, prints what they did and exits; an agent
runs it in the background (Claude Code: Bash run_in_background) so that the exit wakes it. reply: answer an item (the
reply shows on the page). ack: mark what was printed as read without replying. show: all items of a page, and the
user's fixes of its text (`~ edit` lines: an agent that builds the page again takes them into its source first).
The rounds of a theme (<theme>/<round>/index.html) keep their comments apart (a round is made once every comment of
the last one is resolved); a new comment takes a number that no other round of the theme has.
P is a page path under the root or a unique part of one. --port defaults to $TALKPAGE_PORT or 8190. --lang: the
language of the server's own index page (default: $TALKPAGE_LANG, else ja for a Japanese OS, else en); talkpage.js
follows the <html lang> of each page. The page side is talkpage.js / talkpage.css (served at /_talk/); see README.md.
--name (default $TALKPAGE_NAME): also serve the pages at http://NAME/ (a second listener on 127.0.0.1:80 when it can
be had; browsers send *.localhost to this PC). --reports: the root holds reports, <theme>/<YYYYMMDD-HHMM-rN>/index.html
or <theme>/index.html; the server lists them (/_talk/api/reports, and / when the root has no index.html) and adds
talkpage.js to every page it serves. reports: list them, set a theme's owner session (owners.json), mark them read.
--tailscale: also take the requests that Tailscale serve proxies from this PC's tailnet name (set it with
`tailscale serve --bg --https=443 http://127.0.0.1:<port>`) when they carry the login of this PC's own user; the
address the user reads becomes https://<PC>.<tailnet>.ts.net/, which the user's phone opens too.
--place (instead of <root>, repeat it): one server for the reports of several folders, each at /<ID>/ (ID: a-z, 0-9
and -); GROUP heads the folder's reports in the list (several places may share one). A page path is then
<ID>/<path under the folder>. --fallback ID: a path whose first part is no place goes to /<ID>/<path> (links made
before the places). --marks: the stars and tags set in the list (default ~/.talkpage/marks-<port>.json).
"""
import argparse
import email.errors
import email.header
import html
import html.parser
import json
import locale
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get('TALKPAGE_PORT') or 8190)
ID_RE = re.compile(r'^[^\x00-\x1f\x7f]{1,200}$')     # also other tools' keys, e.g. net:/Power In/Net-(U6-EN)
RESERVED = ('thread', 'status', 'user_rev', 'agent_rev', 'seen_rev')     # item fields the agent cannot set directly
SKIP_DIRS = ('node_modules', '__pycache__')
CLIENT = ('talkpage.js', 'talkpage.css')
TYPES = {'.html': 'text/html', '.htm': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
         '.json': 'application/json', '.txt': 'text/plain', '.md': 'text/plain', '.csv': 'text/plain',
         '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
         '.webp': 'image/webp', '.gif': 'image/gif', '.ico': 'image/x-icon', '.pdf': 'application/pdf',
         '.mp4': 'video/mp4', '.woff2': 'font/woff2'}
LANGS = ('en', 'ja')
NAME_RE = re.compile(r'^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+localhost$')
PLACE_RE = re.compile(r'^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$')     # the first part of a page path under --place
TAG_RE = re.compile(r'^[^\x00-\x1f\x7f,]{1,24}$')
FOUND_SECONDS = 5                                               # the walk of the folders is reused this long
ROUND_RE = re.compile(r'^\d{8}-\d{4}-r\d+(-[^/]+)?$')      # a round <theme>/<round>/index.html (also r27-marks)
TITLE_RE = re.compile(rb'<title[^>]*>(.*?)</title', re.I | re.S)
LANG_RE = re.compile(rb'<html[^>]*?\slang\s*=\s*["\']?([A-Za-z-]+)', re.I)
META_RE = re.compile(rb'<meta\b[^>]*>', re.I)
ATTR_RE = re.compile(rb'''([A-Za-z][\w:-]*)\s*=\s*("[^"]*"|'[^']*'|[^\s"'>]+)''')
READ = ('読んだ', 'Read')                                       # the statuses of the item `read` that mean read
OPEN_SECONDS = 90                                               # a page asked with open=1 this recently is open
# added to the report pages the server hands out (--reports); fixed, nothing of the page or the user goes in
INJECT = b'<link rel="stylesheet" href="/_talk/talkpage.css"><script src="/_talk/talkpage.js" defer data-talk-report></script>'
VIEWPORT = b'<meta name="viewport" content="width=device-width, initial-scale=1">'
VIEWPORT_RE = re.compile(rb'<meta\b[^>]*\bname\s*=\s*["\']?viewport\b', re.I)
HEAD_RE = re.compile(rb'<head\b[^>]*>', re.I)
HTML_RE = re.compile(rb'<html\b[^>]*>', re.I)
DOCTYPE_RE = re.compile(rb'<!doctype\b[^>]*>', re.I)
# the index page (/_talk/)
LISTING = {
    'en': {'unread': ' — unread by the agent: %d', 'meta': 'root: %s · agent: %s', 'none': '(none yet)',
           'note': 'Only pages with a state are listed. Open the others by their path under the root.'},
    'ja': {'unread': ' — エージェント未読 %d', 'meta': 'root: %s ・ エージェント: %s', 'none': '（まだ無い）',
           'note': '状態のあるページだけを並べる。ほかのページは root からのパスで開く。'},
}
# the list of reports (/ under --reports when the root has no index.html)
REPORTS = {
    'en': {'title': 'Reports', 'unread': 'unread', 'comments': 'comments: %s', 'none': '(no reports yet)',
           'no_owner': 'no owner', 'meta': 'root: %s · all pages with a state: <a href="/_talk/">/_talk/</a>',
           'all': 'All', 'only_unread': 'Unread', 'starred': '★ Later', 'by_place': 'By place', 'by_time': 'Newest',
           'places': '%d folders · all pages with a state: <a href="/_talk/">/_talk/</a>',
           'mark_read': 'Mark read', 'mark_unread': 'Unread', 'star': 'Look again later', 'tags': 'Tags',
           'tag_prompt': 'Tags, separated by commas (empty removes them)', 'count': '%d', 'failed': 'Not saved',
           'archived': 'Hidden', 'hide': 'Hide', 'unhide': 'Show', 'hide_title': 'Hide from the list (the page stays)',
           'unhide_title': 'Back to the list', 'submission': 'Submission', 'based': 'submitted with %s',
           'missing': 'not found: %s', 'submission_title': 'Handed in; the work reports it is based on follow it'},
    'ja': {'title': 'レポートの一覧', 'unread': '未読', 'comments': 'コメント %s', 'none': '（まだ無い）',
           'no_owner': '担当なし', 'meta': 'root: %s ・ 状態のあるページの一覧: <a href="/_talk/">/_talk/</a>',
           'all': 'すべて', 'only_unread': '未読', 'starred': '★ あとで', 'by_place': '場所ごと', 'by_time': '新しい順',
           'places': 'フォルダ %d か所 ・ 状態のあるページの一覧: <a href="/_talk/">/_talk/</a>',
           'mark_read': '既読に', 'mark_unread': '未読に', 'star': 'あとでもう一度見る', 'tags': 'タグ',
           'tag_prompt': 'タグ（カンマか読点で区切る。空にすると外す）', 'count': '%d 件', 'failed': '保存できませんでした',
           'archived': '非表示', 'hide': '非表示', 'unhide': '再表示', 'hide_title': '一覧から隠す（ページは残る）',
           'unhide_title': '一覧に戻す', 'submission': '提出', 'based': '提出は %s', 'missing': '見つからない根拠: %s',
           'submission_title': '提出したページ。根拠にした作業用のレポートがその下に並ぶ'},
}
FAVICON = ("<link rel=\"icon\" href=\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
           "<text y='.9em' font-size='90'>💬</text></svg>\">")
# the list of reports (report_listing): the rows come in as JSON and the script draws them (textContent only). By place
# (a heading per group, folded by a tap) or newest first; all / unread / starred / a tag; a star, the tags and "read"
# are set by the buttons of a row; "hide" takes a row out of the list (and the sidebars) until it is shown again from
# the filter "hidden". The view, the filter and the folds stay in localStorage. A submission (a page with <meta
# name="report-basis">) is marked so and the work reports it is based on follow it, indented: those of its owner (and
# place) only there, another owner's also in their own place, with that owner's name
LISTING_PAGE = r'''<!doctype html><html lang="{{LANG}}"><head><meta charset="utf-8">{{VIEWPORT}}<title>{{TITLE}}</title>
{{FAVICON}}<style>
:root{color-scheme:light dark;--line:#8884;--dim:#777;--link:#0a5fb4;--red:#cf222e;--amber:#b45309;--chip:#8881}
@media (prefers-color-scheme:dark){:root{--link:#6cb6ff;--red:#f85149;--amber:#d29922;--dim:#999}}
body{font:15px/1.6 system-ui,sans-serif;margin:24px 16px;overflow-wrap:anywhere}
main{max-width:900px}h1{font-size:22px;margin:0 0 8px}
.meta{color:var(--dim);font-size:13px;margin:0 0 12px}
#talk-bar{display:flex;flex-wrap:wrap;gap:8px 16px;margin:0 0 12px}.grp{display:flex;flex-wrap:wrap;gap:6px}
button{font:inherit;color:inherit;cursor:pointer}
.chip{border:1px solid var(--line);background:none;border-radius:16px;padding:3px 12px;font-size:14px}
.chip.on{background:var(--link);border-color:var(--link);color:#fff}.chip .n{margin-left:6px;opacity:.75;font-size:12px}
ul{list-style:none;margin:0;padding:0}li{display:flex;align-items:flex-start;gap:8px;border-top:1px solid var(--line)}
li a{flex:1;min-width:0;display:block;padding:8px 2px;color:inherit;text-decoration:none}
li a:hover .t{text-decoration:underline}.t{font-weight:600;color:var(--link)}
.u{margin-left:8px;font-size:12px;color:var(--red)}.c{margin-left:8px;font-size:13px;color:var(--amber)}
.m{display:block;color:var(--dim);font-size:13px}.tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px}
.tag{font-size:12px;background:var(--chip);border-radius:4px;padding:0 6px}
.acts{position:relative;flex:none;display:flex;gap:4px;padding-top:6px}
.act{min-width:36px;height:32px;border:1px solid var(--line);background:none;border-radius:6px;padding:0 6px;font-size:14px}
.act.read{min-width:64px}.act.hide{min-width:56px}.act.star.on{color:#d4a017}.act:disabled{opacity:.5}
.flash{position:absolute;right:0;top:40px;z-index:2;white-space:nowrap;font-size:12px;background:var(--red);color:#fff;
  border-radius:4px;padding:2px 6px}
.group{margin:0 0 16px}.ghead{display:flex;gap:10px;align-items:baseline;width:100%;text-align:left;border:none;
  background:var(--chip);border-radius:6px;padding:6px 10px;font-size:16px;font-weight:600}
.ghead::before{content:"▾";width:1em}.ghead[aria-expanded=false]::before{content:"▸"}
.ghead .n{font-weight:400;font-size:13px;color:var(--dim)}.ghead .u{margin-left:0}
.none{color:var(--dim)}
.sub{margin-right:8px;padding:0 5px;font-size:12px;font-weight:700;color:var(--link);border:1px solid var(--link);border-radius:4px}
li.kid{margin-left:22px;padding-left:8px;border-left:1px solid var(--line)}
.note{margin-left:8px;font-size:12px;color:var(--dim)}.ref{margin-left:8px;font-size:12px;border:1px solid var(--line);
  border-radius:4px;padding:0 4px}
@media (max-width:599px){li{flex-wrap:wrap;gap:0}li a{flex-basis:100%;padding-bottom:4px}
  .acts{flex:1;justify-content:flex-end;padding:0 0 8px}.flash{top:auto;bottom:44px}}
</style></head>
<body data-talk-listing><main><h1>{{TITLE}}</h1><p class="meta">{{META}}</p><div id="talk-bar"></div>
<div id="talk-list"></div></main>
<script type="application/json" id="talk-data">{{DATA}}</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById('talk-data').textContent), M = D.m;
  var KEY = 'talk-listing', S = { view: 'place', filter: 'all', fold: {} };
  try {
    var v = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (v && typeof v === 'object') {
      if (v.view === 'place' || v.view === 'time') S.view = v.view;
      if (typeof v.filter === 'string') S.filter = v.filter;
      if (v.fold && typeof v.fold === 'object') S.fold = v.fold;
    }
  } catch (e) {}
  function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  var bar = document.getElementById('talk-bar'), list = document.getElementById('talk-list');
  function unread(r) { return r.tracked && !r.read; }
  function href(r) { return '/' + r.page.split('/').map(encodeURIComponent).join('/'); }
  function theme(r) { return r.place && r.theme.indexOf(r.place + '/') === 0 ? r.theme.slice(r.place.length + 1) : r.theme; }
  function tagsOf() {
    var n = {};
    D.rows.filter(shown).forEach(function (r) { r.tags.forEach(function (t) { n[t] = (n[t] || 0) + 1; }); });
    return n;
  }
  function shown(r) { return !r.hidden; }
  function match(r) {
    if (S.filter === 'hidden') return r.hidden;
    if (r.hidden) return false;
    if (S.filter === 'unread') return unread(r);
    if (S.filter === 'star') return r.star;
    if (S.filter.indexOf('tag:') === 0) return r.tags.indexOf(S.filter.slice(4)) >= 0;
    return true;
  }
  function chip(label, on, n, fn) {
    var b = el('button', 'chip' + (on ? ' on' : ''), label);
    if (n != null) b.appendChild(el('span', 'n', String(n)));
    b.setAttribute('aria-pressed', String(on));
    b.addEventListener('click', fn);
    return b;
  }
  function drawBar(tags) {
    bar.textContent = '';
    var f = el('div', 'grp'), rows = D.rows.filter(shown), hidden = D.rows.length - rows.length;
    [['all', M.all, rows.length], ['unread', M.only_unread, rows.filter(unread).length],
     ['star', M.starred, rows.filter(function (r) { return r.star; }).length]].forEach(function (x) {
      f.appendChild(chip(x[1], S.filter === x[0], x[2], function () { S.filter = x[0]; save(); draw(); }));
    });
    Object.keys(tags).sort().forEach(function (t) {
      f.appendChild(chip('#' + t, S.filter === 'tag:' + t, tags[t], function () { S.filter = 'tag:' + t; save(); draw(); }));
    });
    if (hidden || S.filter === 'hidden') {
      f.appendChild(chip(M.archived, S.filter === 'hidden', hidden, function () { S.filter = 'hidden'; save(); draw(); }));
    }
    bar.appendChild(f);
    if (!D.multi) return;
    var g = el('div', 'grp');
    [['place', M.by_place], ['time', M.by_time]].forEach(function (x) {
      g.appendChild(chip(x[1], S.view === x[0], null, function () { S.view = x[0]; save(); draw(); }));
    });
    bar.appendChild(g);
  }
  // a short note by the button it is about (a failed save)
  function flash(btn, text) {
    var t = el('span', 'flash', text);
    btn.parentNode.appendChild(t);
    setTimeout(function () { t.remove(); }, 2500);
  }
  function send(api, body, btn, done) {
    btn.disabled = true;
    fetch('/_talk/api/' + api, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(body) })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { done(d); draw(); })
      .catch(function () { btn.disabled = false; flash(btn, M.failed); });
  }
  // a submission's own reports: the same owner in the same place
  function own(s, k) { return k.owner === s.owner && k.group === s.group; }
  function folders() {
    var byTheme = {}, moved = {};
    D.rows.forEach(function (r) { if (r.tracked && !r.hidden) byTheme[r.theme] = r; });
    function kids(s) { return (s.basis || []).map(function (t) { return byTheme[t]; }).filter(Boolean); }
    D.rows.forEach(function (s) {
      if (s.submission && !s.hidden) kids(s).forEach(function (k) { if (own(s, k)) moved[k.page] = 1; });
    });
    return { kids: kids, moved: moved };
  }
  // sub: the submission the row follows (one of the reports it is based on)
  function row(r, withGroup, sub) {
    var li = el('li'), a = el('a');
    a.href = href(r);
    if (r.submission) {
      var mk = el('span', 'sub', M.submission);
      mk.title = M.submission_title;
      a.appendChild(mk);
    }
    a.appendChild(el('span', 't', r.title));
    if (sub) {
      li.className = 'kid';
      var br = (sub.basis_rounds || {})[r.theme], rn = br && /-(r\d+)/.exec(br);
      if (br && br !== r.round) a.appendChild(el('span', 'note', M.based.replace('%s', rn ? rn[1] : br)));
      if (!own(sub, r)) a.appendChild(el('span', 'ref', r.owner !== sub.owner ? r.owner || M.no_owner : r.group));
    }
    if (r.submission && r.basis_missing.length) {
      a.appendChild(el('span', 'note', M.missing.replace('%s', r.basis_missing.join(', '))));
    }
    if (unread(r)) a.appendChild(el('b', 'u', M.unread));
    if (r.comments.length) a.appendChild(el('span', 'c', M.comments.replace('%s', r.comments.join(', '))));
    a.appendChild(el('span', 'm', [withGroup ? r.group : '', theme(r), r.round, r.owner || M.no_owner, r.time]
      .filter(Boolean).join(' · ')));
    if (r.tags.length) {
      var tg = el('span', 'tags');
      r.tags.forEach(function (t) { tg.appendChild(el('span', 'tag', '#' + t)); });
      a.appendChild(tg);
    }
    li.appendChild(a);
    var acts = el('div', 'acts');
    var star = el('button', 'act star' + (r.star ? ' on' : ''), r.star ? '★' : '☆');
    star.title = M.star;
    star.setAttribute('aria-label', M.star);
    star.setAttribute('aria-pressed', String(r.star));
    star.addEventListener('click', function () {
      send('mark', { page: r.page, star: !r.star }, star, function (d) { r.star = d.star; });
    });
    var tag = el('button', 'act', '#');
    tag.title = M.tags;
    tag.setAttribute('aria-label', M.tags);
    tag.addEventListener('click', function () {
      var v = prompt(M.tag_prompt, r.tags.join(', '));
      if (v === null) return;
      var ts = v.split(/[,、，]/).map(function (s) { return s.trim(); }).filter(Boolean);
      send('mark', { page: r.page, tags: ts }, tag, function (d) { r.tags = d.tags; });
    });
    acts.appendChild(star);
    acts.appendChild(tag);
    if (r.tracked) {                           // a theme with rounds has the item "read"
      var rd = el('button', 'act read', r.read ? M.mark_unread : M.mark_read);
      rd.addEventListener('click', function () {
        var st = r.read ? '' : /^ja/.test(r.lang) ? D.read[0] : D.read[1];
        send('user', { page: r.page, id: 'read', status: st, notify: false }, rd,
             function () { r.read = !!st; r.status = st; });
      });
      acts.appendChild(rd);
    }
    var hd = el('button', 'act hide', r.hidden ? M.unhide : M.hide);
    hd.title = r.hidden ? M.unhide_title : M.hide_title;
    hd.addEventListener('click', function () {
      send('mark', { page: r.page, hidden: !r.hidden }, hd, function (d) { r.hidden = d.hidden; });
    });
    acts.appendChild(hd);
    li.appendChild(acts);
    return li;
  }
  function draw() {
    var tags = tagsOf();
    if (S.filter.indexOf('tag:') === 0 && !tags[S.filter.slice(4)] ||
        S.filter === 'hidden' && !D.rows.some(function (r) { return r.hidden; })) S.filter = 'all';
    drawBar(tags);
    list.textContent = '';
    // the rows to show, each with the reports it is based on (a submission); a submission also shows for its matching
    // reports (unread ones, say), and comes first in its place (not among the newest first)
    var f = S.filter === 'hidden' ? { kids: function () { return []; }, moved: {} } : folders(), items = [], ul;
    D.rows.forEach(function (r) {
      if (f.moved[r.page]) return;
      var ks = r.submission && !r.hidden ? f.kids(r).filter(match) : [];
      if (match(r) || ks.length) items.push({ r: r, kids: ks });
    });
    if (!items.length) { list.appendChild(el('p', 'none', M.none)); return; }
    if (S.view !== 'time') {
      items = items.filter(function (x) { return x.r.submission; }).concat(items.filter(function (x) { return !x.r.submission; }));
    }
    function put(ul, x, withGroup) {
      ul.appendChild(row(x.r, withGroup));
      x.kids.forEach(function (k) { ul.appendChild(row(k, withGroup, x.r)); });
    }
    if (S.view === 'time' || !D.multi) {
      ul = el('ul');
      items.forEach(function (x) { put(ul, x, D.multi); });
      list.appendChild(ul);
      return;
    }
    var groups = [], by = {};
    function add(g) { if (!by[g]) { by[g] = []; groups.push(g); } }
    D.places.forEach(function (p) { add(p.group); });
    items.forEach(function (x) { add(x.r.group); by[x.r.group].push(x); });
    groups.forEach(function (g) {
      var rs = by[g];
      if (!rs.length) return;
      var all = [].concat.apply([], rs.map(function (x) { return [x.r].concat(x.kids); }));
      var sec = el('section', 'group'), head = el('button', 'ghead'), n = all.filter(unread).length;
      sec.setAttribute('data-group', g);
      head.appendChild(el('span', '', g));
      head.appendChild(el('span', 'n', M.count.replace('%d', all.length)));
      if (n) head.appendChild(el('span', 'u', M.unread + ' ' + n));
      ul = el('ul');
      rs.forEach(function (x) { put(ul, x, false); });
      ul.hidden = !!S.fold[g];
      head.setAttribute('aria-expanded', String(!S.fold[g]));
      head.addEventListener('click', function () {
        if (S.fold[g]) delete S.fold[g]; else S.fold[g] = true;
        save();
        draw();
      });
      sec.appendChild(head);
      sec.appendChild(ul);
      list.appendChild(sec);
    });
  }
  // /<place>/ comes here as /#<place>: that place's group, open
  var h = decodeURIComponent(location.hash.slice(1)), at = D.places.filter(function (p) { return p.id === h; })[0];
  if (at) { S.view = 'place'; S.filter = 'all'; delete S.fold[at.group]; }
  draw();
  if (at) {
    [].forEach.call(list.querySelectorAll('[data-group]'), function (s) {
      if (s.getAttribute('data-group') === at.group) s.scrollIntoView();
    });
  }
  function reload() {
    fetch('/_talk/api/reports', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d && Array.isArray(d.rows)) { D.rows = d.rows; draw(); } })
      .catch(function () {});
  }
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') reload(); });
  setInterval(function () { if (document.visibilityState === 'visible') reload(); }, 60000);
})();
</script></body></html>'''


def default_lang(env_name='TALKPAGE_LANG'):
    """'en' or 'ja': the environment variable env_name when set (en, ja, or a locale such as ja_JP), else 'ja' when the
    user's locale or the Windows UI language is Japanese, else 'en'."""
    v = (os.environ.get(env_name) or '').strip().lower()[:2]
    if v in LANGS:
        return v
    try:
        loc = (locale.getlocale()[0] or '').lower()
    except ValueError:
        loc = ''
    if loc.startswith(('ja', 'japanese')):
        return 'ja'
    if os.name == 'nt':
        try:
            import ctypes
            if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xff == 0x11:     # LANG_JAPANESE
                return 'ja'
        except (AttributeError, OSError):
            pass
    return 'en'


def check_name(name):
    """The name of --name in lower case, or SystemExit: only *.localhost, which browsers send to this PC."""
    n = (name or '').strip().lower()
    if not NAME_RE.match(n):
        raise SystemExit('talkpage: --name must end with .localhost (e.g. notes.localhost), which every browser sends '
                         'to this PC without a hosts entry: %s' % name)
    return n


def own_origins(port, name=None, remote=None):
    """The origins of this server's pages on one listener: 127.0.0.1, localhost and the --name, without :80, and the
    tailnet origin of --tailscale."""
    suffix = '' if port == 80 else ':%d' % port
    own = tuple('http://%s%s' % (h, suffix) for h in ('127.0.0.1', 'localhost') + ((name,) if name else ()))
    return own + ((remote,) if remote else ())


def serve_origin(serve, port):
    """The origin at which `tailscale serve status --json` (parsed) proxies the root path to 127.0.0.1:<port>, such
    as https://pc.tail1234.ts.net, or None. Only a proxy of / counts: the pages ask for absolute paths."""
    targets = ('http://127.0.0.1:%d' % port, 'http://localhost:%d' % port)
    for hostport, web in ((serve or {}).get('Web') or {}).items():
        proxy = (((web or {}).get('Handlers') or {}).get('/') or {}).get('Proxy') or ''
        if proxy.rstrip('/').lower() not in targets:
            continue
        host, _, p = hostport.rpartition(':')
        tls = ((serve.get('TCP') or {}).get(p) or {}).get('HTTPS')
        scheme, default = ('https', '443') if tls else ('http', '80')
        return '%s://%s%s' % (scheme, host.lower(), '' if p == default else ':' + p)
    return None


def tailscale(port):
    """(origin, login) when Tailscale serve proxies this PC's tailnet name to 127.0.0.1:<port>: the origin of
    serve_origin() and the login name of this PC's own user. Else (None, why)."""
    exe = shutil.which('tailscale') or r'C:\Program Files\Tailscale\tailscale.exe'
    if not os.path.isfile(exe):
        return None, 'the tailscale command is not installed'

    def run(*args):
        r = subprocess.run([exe] + list(args), capture_output=True, timeout=15)
        return json.loads(r.stdout.decode('utf-8') or 'null')
    try:
        st, serve = run('status', '--json'), run('serve', 'status', '--json')
        me = st['Self']
        login = st['User'][str(me['UserID'])]['LoginName']
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as e:
        return None, 'tailscale status failed (%s)' % e
    if st.get('BackendState') != 'Running':
        return None, 'Tailscale is %s' % st.get('BackendState')
    origin = serve_origin(serve, port)
    if not origin:
        return None, 'nothing serves 127.0.0.1:%d; set it with: tailscale serve --bg --https=443 http://127.0.0.1:%d' \
            % (port, port)
    return origin, login


def head(path, n=65536):
    """The first n bytes of a file, or b''."""
    try:
        with open(path, 'rb') as f:
            return f.read(n)
    except OSError:
        return b''


def page_title(data):
    m = TITLE_RE.search(data)
    return ' '.join(html.unescape(m.group(1).decode('utf-8', 'replace')).split())[:200] if m else ''


def page_lang(data):
    m = LANG_RE.search(data)
    return m.group(1).decode('ascii').lower() if m else ''


def page_basis(data):
    """A submission's basis: the words of <meta name="report-basis" content="<theme>/<round> <theme> …">, or None for
    a page without it."""
    for m in META_RE.finditer(data):
        a = {k.lower(): v.strip(b'"\'') for k, v in ATTR_RE.findall(m.group(0))}
        if a.get(b'name', b'').lower() == b'report-basis':
            return html.unescape(a.get(b'content', b'').decode('utf-8', 'replace')).split()
    return None


def basis_word(word):
    """(theme, round or '') of a word of report-basis: a round named after the theme's path, or the theme alone."""
    parts = [x for x in word.split('/') if x]
    for i, x in enumerate(parts):
        if i and ROUND_RE.match(x):
            return '/'.join(parts[:i]), x
    return '/'.join(parts), ''


def report_key(page):
    """The theme key of a page under --reports: the folder above its round (<theme>/<round>/...), the folder of a
    single index.html, or the path of any other single page. owners.json is keyed by it."""
    parts = page.split('/')
    for i in range(len(parts) - 2, 0, -1):
        if ROUND_RE.match(parts[i]):
            return '/'.join(parts[:i])
    return '/'.join(parts[:-1]) if parts[-1] == 'index.html' and len(parts) > 1 else page


def owner_names(owners):
    """{theme: owner name} with one name per session id, the one most of its themes carry: a theme left with an old
    name (the session was renamed) still goes into the same group."""
    count = {}
    for v in owners.values():
        if isinstance(v.get('id'), str) and v['id'] and isinstance(v.get('name'), str):
            c = count.setdefault(v['id'], {})
            c[v['name']] = c.get(v['name'], 0) + 1
    best = {i: max(c, key=c.get) for i, c in count.items()}
    out = {}
    for t, v in owners.items():
        name = best.get(v.get('id')) or v.get('name')
        out[t] = name if isinstance(name, str) else ''
    return out


def bad_part(s):
    """A part of a URL path that is never served: empty, . and .., a hidden name, a backslash, and a colon (on
    Windows a drive, which would leave the folder, or a file's stream)."""
    return s in ('', '.', '..') or s.startswith('.') or '\\' in s or ':' in s


def quoted(parts, raw):
    """A path of our own for a redirect, from the parts of a request's path (ending with / when raw does): never
    //host, which a browser would take for another site."""
    return '/' + '/'.join(urllib.parse.quote(x) for x in parts) + ('/' if raw.endswith('/') and parts else '')


def inject(data):
    """A phone-width viewport for a page without one (after <head>, else <html>, else the doctype, else at the start;
    without it a phone lays the page out wider than the screen), and the client before the last </body> (else at the
    end) of a page that does not load talkpage.js itself."""
    if not VIEWPORT_RE.search(data):
        m = HEAD_RE.search(data) or HTML_RE.search(data) or DOCTYPE_RE.search(data)
        i = m.end() if m else 0
        data = data[:i] + VIEWPORT + data[i:]
    if b'/_talk/talkpage.js' in data:
        return data
    i = data.lower().rfind(b'</body>')
    return data + INJECT if i < 0 else data[:i] + INJECT + data[i:]


def stamp():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def natural(key):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', key)]


def check_status(status):
    if status is None:
        return None
    if not isinstance(status, str) or len(status.strip()) > 24:
        raise ValueError('status: a short string ("" clears it)')
    return status.strip()


def check_anchor(anchor):
    """Where a comment on selected text was, to put its card near there once the text has changed:
    {heads: [the texts of its headings, outer first], id: the closest element id, pos: 0-1 of the way down}. Unknown
    keys and invalid values are dropped; None when nothing valid is left."""
    if anchor is None:
        return None
    if not isinstance(anchor, dict):
        raise ValueError('anchor: an object {heads, id, pos}')
    out = {}
    heads = anchor.get('heads')
    if isinstance(heads, list):
        out['heads'] = [h.strip()[:120] for h in heads[:6] if isinstance(h, str) and h.strip()]
    if isinstance(anchor.get('id'), str) and ID_RE.match(anchor['id']):
        out['id'] = anchor['id']
    pos = anchor.get('pos')
    if isinstance(pos, (int, float)) and not isinstance(pos, bool) and 0 <= pos <= 1:
        out['pos'] = round(float(pos), 3)
    return out or None


def waiting(it):
    return it.get('user_rev', 0) > it.get('agent_rev', 0)


def last_reply(it):
    """The revision of the agent's last message on an item (the user has read them all when seen_rev reaches it)."""
    return max([m.get('rev', 0) for m in it['thread'] if m.get('who') == 'agent' and m.get('text')] or [0])


# ---------------------------------------------------------------- the rounds of a theme
COMMENT_ID = re.compile(r'^([A-Za-z]+)(\d+)$')      # comments on selected text: C1, C2... (talkpage.js nextId)


# ---------------------------------------------------------------- the user's fixes of a page's text (Edit on the page)
EDIT_TAGS = ('p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td', 'th', 'dt', 'dd', 'figcaption', 'caption',
             'blockquote')                     # talkpage.js EDITABLE
VOID = ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr')
UNSAFE_TAGS = ('script', 'iframe', 'frame', 'frameset', 'object', 'embed', 'applet', 'style', 'link', 'meta', 'base',
               'form', 'template')
UNSAFE_URL = re.compile(r'^(javascript|vbscript):', re.I)


def squash(t):
    return re.sub(r'\s+', ' ', t).strip()


class Blocks(html.parser.HTMLParser):
    """The elements <tag> in the body of a page as the page's script sees them: [(start of the content, its end, its
    text)] in the source, the text squashed; nothing inside data-talk (the script adds its own parts there), template
    or noscript. open: how many elements <tag> are not closed by their own end tag (where they end is not known)."""

    def __init__(self, src, tag):
        super().__init__(convert_charrefs=True)
        self.tag, self.found, self.open, self.stack = tag, [], 0, []
        self.body = not re.search(r'<body\b', src, re.I)        # a page without <body>: all of it
        self.lines = [0] + [m.end() for m in re.finditer('\n', src)]
        self.feed(src)
        self.close()
        self.open += sum(1 for e in self.stack if e['start'] is not None)

    def at(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag == 'body':
            self.body = True
        if tag in VOID:
            return
        skip = (tag in ('template', 'noscript') or any(k == 'data-talk' for k, _ in attrs)
                or bool(self.stack and self.stack[-1]['skip']))
        mine = tag == self.tag and self.body and not skip
        self.stack.append({'tag': tag, 'skip': skip, 'start': self.at() + len(self.get_starttag_text()) if mine else None,
                           'text': [] if mine else None})

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]['tag'] == tag:
                e = self.stack[i]
                if e['start'] is not None:
                    self.found.append((e['start'], self.at(), squash(''.join(e['text']))))
                self.open += sum(1 for x in self.stack[i + 1:] if x['start'] is not None)   # ended by this one
                del self.stack[i:]
                return

    def handle_data(self, data):
        for e in self.stack:
            if e['text'] is not None:
                e['text'].append(data)


def find_block(src, tag, text, nth, count=None):
    """(start, end) of the content of the nth element <tag> whose text is `text`, in document order. Refused when the
    file does not hold what the page showed: fewer of them (the page was rebuilt), another number of them than the page
    counted (`count`; elements made or removed by the page's own script), or elements <tag> whose end is not written
    (where the browser ends them, and so its count, could differ from this one)."""
    b = Blocks(src, tag)
    hits = sorted((a, z) for a, z, t in b.found if t == squash(text))
    if b.open:
        raise ValueError("edit: %d <%s> of the file have no </%s>; fix the page's source instead" % (b.open, tag, tag))
    if nth >= len(hits) or count is not None and count != len(hits):
        raise ValueError('edit: the file has %d <%s> with this text, the page had %s (was the page rebuilt?)'
                         % (len(hits), tag, count if count is not None else 'more'))
    return hits[nth]


class Unsafe(html.parser.HTMLParser):
    """What in a block's new content could run: tags of scripts and embedding, on… attributes, javascript: URLs. The
    text is only text (a word such as "one=1" or "javascript:" written in it is no markup)."""

    def __init__(self, src):
        super().__init__(convert_charrefs=True)
        self.bad = []
        self.feed(src)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag in UNSAFE_TAGS:
            self.bad.append('<%s>' % tag)
        for k, v in attrs:
            if k.startswith('on'):
                self.bad.append(k)
            elif v and UNSAFE_URL.match(re.sub(r'[\x00-\x20]+', '', v)):
                self.bad.append('%s=%s' % (k, v[:20]))

    handle_startendtag = handle_starttag


def replace_file(tmp, path):
    for i in range(20):                        # Windows: an editor or sync client may hold the file for a moment
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.05)


def upgrade(it):
    """Items written without revisions (older review files): the item waits if its last message is the user's."""
    it.setdefault('status', '')
    th = it.setdefault('thread', [])
    if 'user_rev' not in it:
        last_agent = max([i for i, m in enumerate(th) if m.get('who') == 'agent'] or [-1])
        for i, m in enumerate(th):
            m.setdefault('rev', 1 if i > last_agent and m.get('who') == 'user' else 0)
        it['user_rev'] = 1 if th and th[-1].get('who') == 'user' else 0
    it.setdefault('agent_rev', 0)
    it.setdefault('seen_rev', 0)


class Store:
    """State of one page: {page, rev, items: {id: item}} plus whatever else the owner keeps in the file.

    item: {title, status, thread: [{who: user|agent, text | status, time, rev}], user_rev, agent_rev, seen_rev, ...}.
    user_rev is the revision of the user's last action meant for the agent (a comment, or a status the page reports),
    agent_rev of the agent's last reply or ack, seen_rev of the last agent message the user has read. The item waits
    for the agent while user_rev > agent_rev. Callers hold Talk.cond."""

    def __init__(self, path, page):
        self.path, self.page = path, page
        self.taken = {}                        # id -> user_rev already handed to a `wait` (memory only)
        self.mtime = None
        self.data = {'page': page, 'rev': 0, 'items': {}}
        self.load()

    def load(self):
        if not os.path.isfile(self.path):
            return
        with open(self.path, encoding='utf-8') as f:
            d = json.load(f)
        d.setdefault('items', {})
        for it in d['items'].values():
            upgrade(it)
        d['rev'] = max(int(d.get('rev') or 0), 1)
        self.data, self.mtime = d, os.path.getmtime(self.path)

    def fresh(self):
        """Pick up an edit made outside the server; a deleted file starts the page over."""
        if not os.path.isfile(self.path):
            if self.mtime is not None:
                self.mtime, self.taken = None, {}
                self.data = {'page': self.page, 'rev': self.data['rev'] + 1, 'items': {}}
        elif os.path.getmtime(self.path) != self.mtime:
            self.load()

    def save(self):
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
            f.write('\n')
        replace_file(tmp, self.path)
        self.mtime = os.path.getmtime(self.path)

    def _next(self):
        self.data['rev'] += 1
        return self.data['rev']

    def item(self, iid, create=False):
        if not isinstance(iid, str) or not ID_RE.match(iid):
            raise ValueError('id: 1-200 characters, no control characters')
        it = self.data['items'].get(iid)
        if it is None:
            if not create:
                raise ValueError('unknown item: %s' % iid)
            it = self.data['items'][iid] = {'status': '', 'thread': [], 'user_rev': 0, 'agent_rev': 0, 'seen_rev': 0}
        return it

    def user(self, iid, title=None, status=None, comment=None, notify=True, anchor=None):
        """A status and / or a comment from the user. A title or an anchor alone (where a comment on selected text
        was) is kept without waking the agent."""
        it = self.item(iid, create=True)
        status = check_status(status)
        anchor = check_anchor(anchor)
        comment = (comment or '').strip() if isinstance(comment, str) else ''
        title = str(title).strip()[:200] if title else ''
        changed = status is not None and status != it['status']
        if not changed and not comment:
            if title and title != it.get('title') or anchor and anchor != it.get('anchor'):
                if title:
                    it['title'] = title
                if anchor:
                    it['anchor'] = anchor
                self._next()
                self.save()
            return it
        rev = self._next()
        if title:
            it['title'] = title
        if anchor:
            it['anchor'] = anchor
        if changed:
            it['status'] = status
            it['thread'].append({'who': 'user', 'status': status, 'time': stamp(), 'rev': rev})
        if comment:
            it['thread'].append({'who': 'user', 'text': comment, 'time': stamp(), 'rev': rev})
        if comment or notify:
            it['user_rev'] = rev
        self.save()
        return it

    def agent(self, iid, reply=None, status=None, fields=None):
        """A reply and / or a status from the agent; either way the item no longer waits."""
        it = self.item(iid, create=True)
        status = check_status(status)
        if fields is not None and (not isinstance(fields, dict) or any(k in RESERVED for k in fields)):
            raise ValueError('fields: an object without ' + ', '.join(RESERVED))
        rev = self._next()
        it.update(fields or {})
        if status is not None and status != it['status']:
            it['status'] = status
            it['thread'].append({'who': 'agent', 'status': status, 'time': stamp(), 'rev': rev})
        reply = reply.strip() if isinstance(reply, str) else ''
        if reply:
            it['thread'].append({'who': 'agent', 'text': reply, 'time': stamp(), 'rev': rev})
        it['agent_rev'] = rev
        self.save()
        return it

    def ack(self, ids=None):
        done = [k for k, it in self.data['items'].items() if waiting(it) and (ids is None or k in ids)]
        if done:
            rev = self._next()
            for k in done:
                self.data['items'][k]['agent_rev'] = rev
            self.save()
        return sorted(done, key=natural)

    def edited(self, tag, before, after):
        """Keep the user's fix of the page's text: an agent that builds the page again takes it into its source first
        (show lists them). The agent is not woken."""
        self.data.setdefault('edits', []).append({'time': stamp(), 'tag': tag, 'before': squash(before)[:300],
                                                  'after': squash(after)[:300]})
        del self.data['edits'][:-200]
        self._next()
        self.save()

    def seen(self, iid):
        it = self.item(iid)
        last = last_reply(it)
        if last > it['seen_rev']:
            it['seen_rev'] = last
            self._next()
            self.save()
        return it

    def view(self):
        return {'page': self.page, 'file': self.path.replace('\\', '/'), 'rev': self.data['rev'],
                'items': self.data['items'], 'edits': self.data.get('edits', [])}

    def waiting_items(self, undelivered=False):
        out = []
        for k in sorted(self.data['items'], key=natural):
            it = self.data['items'][k]
            delivered = self.taken.get(k, 0) >= it['user_rev']
            if not waiting(it) or undelivered and delivered:
                continue
            new = [m for m in it['thread'] if m.get('who') == 'user' and m.get('rev', 0) > it['agent_rev']]
            out.append({'page': self.page, 'id': k, 'title': it.get('title', ''), 'status': it['status'], 'new': new,
                        'delivered': delivered})
        return out


class Place:
    """A folder of pages: at / when it is the only one (id ''), else at /<id>/ (--place)."""

    def __init__(self, pid, root, group=''):
        self.id, self.root, self.group = pid, os.path.realpath(root), group or pid

    def key(self, rel):
        """The page path of a path under the folder."""
        return self.id + '/' + rel if self.id and rel else self.id or rel


def parse_place(text):
    """(group, id, folder) of --place [GROUP:]ID=FOLDER, or SystemExit."""
    left, sep, folder = text.partition('=')
    group, _, pid = left.rpartition(':')
    if not sep or not folder or not PLACE_RE.match(pid) or ROUND_RE.match(pid):
        raise SystemExit('talkpage: --place [GROUP:]ID=FOLDER, ID of a-z, 0-9 and - (not like a round): %s' % text)
    return group.strip(), pid, folder


class Talk:
    """The stores under one root (or the places of --place), the agent's presence, and the /_talk/api/ routes.
    Another server can host stores kept at its own paths (attach) and hand /_talk/api/ requests to get() / post()."""

    def __init__(self, root=None, port=PORT, lang='en', name=None, reports=False, remote=None, places=None,
                 fallback=None, marks=None):
        if places:                             # [(group, id, folder)] of parse_place()
            self.places = [Place(pid, folder, group) for group, pid, folder in places]
            ids = [p.id for p in self.places]
            if len(set(ids)) != len(ids):
                raise ValueError('two places with one id: %s' % ', '.join(ids))
            if fallback and fallback not in ids:
                raise ValueError('--fallback: no place %s' % fallback)
        else:
            self.places = [Place('', root)] if root else []
        self.multi = bool(places)
        self.root = None if self.multi else self.places[0].root if self.places else None
        self.fallback = fallback if self.multi else None
        self.marks_path = marks or os.path.join(os.path.expanduser('~'), '.talkpage', 'marks-%d.json' % port)
        self._found = (0.0, None)              # (when, the walk of reports())
        self._info = {}                        # file -> page_info()
        self.port = port
        self.lang = lang if lang in LANGS else 'en'      # of the index page; the pages carry their own <html lang>
        self.name = name or None                         # --name, checked by check_name()
        self.on80 = False                                # a second listener serves the name on port 80
        self.remote, self.remote_login = remote or (None, None)     # --tailscale: (origin, login) of tailscale()
        self.report_mode = bool(reports and self.places)
        self.viewed = {}                                 # page -> when a page last asked for its state with open=1
        self.cond = threading.Condition()
        self.stores = {}
        self.listeners = 0                     # `wait` requests in progress
        self.last_listen = 0.0                 # end of the last one
        self.taken_at = 0.0                    # when a `wait` last took items (the agent is working on them)
        self.last_user_at = 0.0
        self.scan()
        threading.Thread(target=self._watch_presence, daemon=True).start()

    @property
    def url(self):
        """The address the user reads: the tailnet one of --tailscale (this PC's browser and the phone both open it),
        else local_url."""
        return self.remote + '/' if self.remote else self.local_url

    @property
    def local_url(self):
        """This PC's address: http://NAME/ when port 80 serves it, else http://NAME:<port>/ or 127.0.0.1."""
        if self.name:
            return 'http://%s/' % self.name if self.on80 or self.port == 80 else 'http://%s:%d/' % (self.name, self.port)
        return 'http://127.0.0.1:%d/' % self.port

    def owners(self):
        """{theme: {name, id}} of each place's owners.json (written by `talkpage reports owner`), the themes as page
        paths (with the place's id)."""
        out = {}
        for pl in self.places:
            try:
                with open(os.path.join(pl.root, 'owners.json'), encoding='utf-8') as f:
                    d = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(d, dict):
                out.update((pl.key(k), v) for k, v in d.items() if isinstance(v, dict))
        return out

    def marks(self):
        """{page: {star, tags, hidden}} set in the list of reports (the file of --marks), or {}."""
        try:
            with open(self.marks_path, encoding='utf-8') as f:
                d = json.load(f)
        except (OSError, ValueError):
            return {}
        pages = d.get('pages') if isinstance(d, dict) else None
        return {k: v for k, v in pages.items() if isinstance(v, dict)} if isinstance(pages, dict) else {}

    def mark(self, page, star=None, tags=None, hidden=None):
        """Star a report, set its tags or hide it from the list (None keeps them). Callers hold self.cond."""
        p, _ = self.page_file(page)
        if star is not None and not isinstance(star, bool):
            raise ValueError('star: true or false')
        if hidden is not None and not isinstance(hidden, bool):
            raise ValueError('hidden: true or false')
        if tags is not None:
            if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
                raise ValueError('tags: a list of strings')
            tags = list(dict.fromkeys(t.strip() for t in tags if t.strip()))
            if len(tags) > 8 or not all(TAG_RE.match(t) for t in tags):
                raise ValueError('tags: up to 8, each 1-24 characters without commas or control characters')
        marks = self.marks()
        m = dict(marks.get(p) or {})
        if star is not None:
            m['star'] = star
        if tags is not None:
            m['tags'] = tags
        if hidden is not None:
            m['hidden'] = hidden
        m = {k: v for k, v in m.items() if v}
        if m:
            marks[p] = m
        else:
            marks.pop(p, None)
        os.makedirs(os.path.dirname(self.marks_path) or '.', exist_ok=True)
        tmp = self.marks_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'pages': marks}, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write('\n')
        os.replace(tmp, self.marks_path)
        return {'page': p, 'star': bool(m.get('star')), 'tags': m.get('tags') or [], 'hidden': bool(m.get('hidden'))}

    def walk_reports(self):
        """(theme, round, page, file, place) of each report: the last round of each theme with rounds, and the single
        pages. The walk is reused for FOUND_SECONDS (the pages' sidebars ask every 30 s)."""
        when, found = self._found
        if found is not None and time.time() - when < FOUND_SECONDS:
            return found
        found = []
        for pl in self.places:
            for d, dirs, files in os.walk(pl.root):
                dirs[:] = sorted(x for x in dirs if not x.startswith(('.', '_')) and x not in SKIP_DIRS)
                rel = os.path.relpath(d, pl.root).replace('\\', '/')
                rel = '' if rel == '.' else rel
                rounds = [x for x in dirs if ROUND_RE.match(x) and os.path.isfile(os.path.join(d, x, 'index.html'))]
                if rounds and (rel or pl.id):  # a theme: its last round; the earlier ones are linked from its index
                    r = max(rounds, key=natural)   # (a place's own rounds: the place is the theme)
                    found.append((pl.key(rel), r, pl.key('/'.join(x for x in (rel, r, 'index.html') if x)),
                                  os.path.join(d, r, 'index.html'), pl))
                dirs[:] = [x for x in dirs if not ROUND_RE.match(x)]     # the other files of a round are not rows
                for f in sorted(files):
                    if not f.lower().endswith(('.html', '.htm')) or f == 'index.html' and (rounds or not rel):
                        continue               # the index of the rounds, and the place's own index
                    page = pl.key(rel + '/' + f if rel else f)
                    found.append((report_key(page), '', page, os.path.join(d, f), pl))
        self._found = (time.time(), found)
        return found

    def page_info(self, full):
        """(mtime, title, lang, report-basis) of a page's file, read again whenever it changed (a fixed title or basis
        shows on the next request, not after the walk's FOUND_SECONDS); None when it is gone."""
        try:
            mt = os.path.getmtime(full)
        except OSError:
            return None
        hit = self._info.get(full)
        if hit is None or hit[0] != mt:
            data = head(full)
            hit = self._info[full] = (mt, page_title(data), page_lang(data), page_basis(data))
        return hit

    def reports(self):
        """The reports under the places, newest first. A single page with <meta name="report-basis"> is a submission:
        basis (the themes found, in order), basis_rounds (the round named for a theme), basis_missing (words that name
        no theme with rounds); the rows of those themes carry in (the submissions that name them)."""
        found = self.walk_reports()
        owners, marks = self.owners(), self.marks()
        names = owner_names(owners)
        rows = []
        with self.cond:
            for theme, r, page, full, pl in found:
                info = self.page_info(full)
                if info is None:
                    continue
                mt, title, lang, basis = info
                t = ('%s-%s-%s %s:%s' % (r[:4], r[4:6], r[6:8], r[9:11], r[11:13]) if r
                     else time.strftime('%Y-%m-%d %H:%M', time.localtime(mt)))
                s = self.stores.get(page)
                if s is None and os.path.isfile(os.path.splitext(full)[0] + '.talk.json'):
                    try:
                        s = self.store(page)
                    except (OSError, ValueError):
                        s = None
                elif s is not None:
                    s.fresh()
                read = s.data['items'].get('read', {}).get('status', '') if s else ''
                comments = [x['id'] for x in s.waiting_items() if any('text' in m for m in x['new'])] if s else []
                owner = names.get(theme, '')
                owner_id = owners.get(theme, {}).get('id', '')
                mk = marks.get(page, {})
                tags = mk.get('tags') if isinstance(mk.get('tags'), list) else []
                rows.append({'page': page, 'theme': theme, 'round': r, 'title': title or theme,
                             'owner': owner if isinstance(owner, str) else '',
                             'owner_id': owner_id if isinstance(owner_id, str) else '', 'tracked': bool(r),
                             'status': read if r else '-', 'read': bool(r) and read in READ,
                             'comments': comments, 'time': t, 'lang': lang, 'place': pl.id, 'group': pl.group,
                             'star': mk.get('star') is True, 'tags': [x for x in tags if isinstance(x, str)],
                             'hidden': mk.get('hidden') is True, 'submission': not r and basis is not None,
                             'basis': basis if not r else None})
        themes = {x['theme']: x for x in rows if x['tracked']}
        for x in rows:                         # the basis of each submission: themes of its place first, then any
            words = x.pop('basis')
            if not x['submission']:
                continue
            x['basis'], x['basis_rounds'], x['basis_missing'] = [], {}, []
            for w in words:
                name, rnd = basis_word(w)
                key = next((k for k in ([x['place'] + '/' + name] if x['place'] else []) + [name] if k in themes), None)
                if key is None:
                    x['basis_missing'].append(w)
                    continue
                if key not in x['basis']:
                    x['basis'].append(key)
                    themes[key].setdefault('in', []).append(x['theme'])
                if rnd:
                    x['basis_rounds'][key] = rnd
        rows.sort(key=lambda x: x['time'], reverse=True)
        return {'root': self.root and self.root.replace('\\', '/'), 'url': self.url, 'rows': rows,
                'places': self.place_list()}

    def place_list(self):
        return [{'id': p.id, 'group': p.group, 'root': p.root.replace('\\', '/')} for p in self.places]

    def scan(self):
        for pl in self.places:
            for d, dirs, files in os.walk(pl.root):
                dirs[:] = [x for x in dirs if not x.startswith('.') and x not in SKIP_DIRS]
                for f in files:
                    page_file = os.path.join(d, f[:-len('.talk.json')] + '.html')
                    if f.endswith('.talk.json') and os.path.isfile(page_file):
                        page = pl.key(os.path.relpath(page_file, pl.root).replace('\\', '/'))
                        try:
                            self.stores[page] = Store(os.path.join(d, f), page)
                        except (OSError, ValueError) as e:
                            print('talkpage: skipped %s: %s' % (os.path.join(d, f), e), file=sys.stderr)

    # A theme's rounds (<theme>/<round>/index.html, a new round made from the last one once every comment on it is
    # resolved) keep their comments apart; only the numbers stay unique over the theme, so that C12 names one comment.
    def rounds(self, page):
        """The pages of the same name in every round of page's theme, oldest first; [] for a page outside rounds
        (under --place the place's own rounds count: the place is the theme)."""
        parts = page.split('/')
        if len(parts) < 3 or not ROUND_RE.match(parts[-2]) or any(bad_part(x) for x in parts):
            return []                          # (the keys of attached stores may be anything)
        hit = self.locate(parts)
        if not hit:
            return []
        theme = os.path.join(hit[0].root, *hit[1][:-2])
        try:
            names = [d for d in os.listdir(theme)
                     if ROUND_RE.match(d) and os.path.isfile(os.path.join(theme, d, parts[-1]))]
        except OSError:
            return []
        return ['/'.join(parts[:-2] + [d, parts[-1]]) for d in sorted(names, key=natural)]

    def taken(self, page):
        """The ids of the comments on the theme's other rounds: a new comment on page takes a number none of them has."""
        out = set()
        for p in self.rounds(page):
            s = self.stores.get(p) if p != page else None
            out.update(k for k in (s.data['items'] if s else ()) if COMMENT_ID.match(k))
        return sorted(out, key=natural)

    def html_pages(self):
        out = []
        for pl in self.places:
            for d, dirs, files in os.walk(pl.root):
                dirs[:] = [x for x in dirs if not x.startswith('.') and x not in SKIP_DIRS]
                out += [pl.key(os.path.relpath(os.path.join(d, f), pl.root).replace('\\', '/')) for f in files
                        if f.lower().endswith(('.html', '.htm'))]
        return sorted(out)

    def attach(self, page, path):
        """Keep the state of `page` (any key) in `path`, e.g. a review file of another tool."""
        with self.cond:
            s = self.stores[page] = Store(path, page)
            return s

    def locate(self, parts):
        """(place, the parts under its folder) of a path's parts, or None: under --place the first part names the
        place."""
        if not self.multi:
            return (self.places[0], parts) if self.places else None
        for pl in self.places:
            if parts and parts[0] == pl.id:
                return pl, parts[1:]
        return None

    def page_file(self, page):
        """(page path, file) for a page path from a URL or the command line, or ValueError."""
        p = urllib.parse.unquote(str(page or '')).replace('\\', '/').lstrip('/')
        if p == '' or p.endswith('/'):
            p += 'index.html'
        parts = p.split('/')
        hit = None if any(bad_part(s) for s in parts) else self.locate(parts)
        if not hit or not hit[1] or not p.lower().endswith(('.html', '.htm')):
            raise ValueError('page: an .html path under the root: %s' % p)
        pl, rest = hit
        full = os.path.realpath(os.path.join(pl.root, *rest))
        if not full.startswith(pl.root + os.sep) or not os.path.isfile(full):
            raise ValueError('no such page: %s' % p)
        return p, full

    def store(self, page, loose=False):
        """The store of a page; loose also takes a unique part of the path of a page that has a state."""
        if page in self.stores:
            s = self.stores[page]
            s.fresh()
            return s
        try:
            p, full = self.page_file(page)
        except ValueError:
            if not loose or not page:
                raise
            hits = [k for k in self.stores if page in k] or [k for k in self.html_pages() if page in k]
            if len(hits) != 1:
                raise ValueError('page %r matches %s' % (page, ', '.join(hits[:20]) if hits else 'no page'))
            p = hits[0]
            if p not in self.stores:
                p, full = self.page_file(p)
        s = self.stores.get(p)
        if s is None:
            s = self.stores[p] = Store(os.path.splitext(full)[0] + '.talk.json', p)
        s.fresh()
        return s

    def presence(self):
        t = time.time()
        if self.listeners:
            return 'listening'
        if self.taken_at and self.taken_at >= self.last_listen - 0.5 and t - self.taken_at < 3600:
            return 'working'
        return 'listening' if t - self.last_listen < 2.5 else 'absent'

    def _watch_presence(self):
        """Wake the pages when the presence changes by time alone (a `wait` that did not come back)."""
        prev = None
        while True:
            time.sleep(1)
            with self.cond:
                cur = self.presence()
                if cur != prev:
                    self.cond.notify_all()
                    prev = cur

    # ---------------------------------------------------------------- API (bodies are serialised under the lock)
    def get(self, path, q):
        """GET /_talk/api/<name>: (code, JSON bytes) or None."""
        def one(k, d=None):
            return (q.get(k) or [d])[0]
        if path == '/_talk/api/info':
            with self.cond:
                now = time.time()
                return 200, dump({'tool': 'talkpage', 'root': self.root and self.root.replace('\\', '/'),
                                  'places': self.place_list() if self.multi else [], 'port': self.port, 'lang': self.lang, 'presence': self.presence(),
                                  'name': self.name or '', 'url': self.url, 'local_url': self.local_url,
                                  'open': sorted(p for p, t in self.viewed.items() if now - t < OPEN_SECONDS),
                                  'pages': sorted(self.stores)})
        if path == '/_talk/api/reports':
            if not self.report_mode:
                return 404, dump({'error': 'the server runs without --reports'})
            return 200, dump(self.reports())
        if path == '/_talk/api/state':
            rev, pres, wait = int(one('rev', -1)), one('presence'), min(float(one('wait', 0)), 55)
            with self.cond:
                s = self.store(one('page'), loose=True)
                if one('open') == '1':
                    self.viewed[s.page] = time.time()
                if wait > 0:
                    self.cond.wait_for(lambda: s.data['rev'] != rev or pres is not None and self.presence() != pres,
                                       wait)
                return 200, dump(dict(s.view(), presence=self.presence(), taken=self.taken(s.page)))
        if path == '/_talk/api/pending':
            return 200, self.pending(one('page'), min(float(one('wait', 0)), 55), one('listen') == '1',
                                     one('take') == '1')
        return None

    def pending(self, page, wait, listen, take):
        """Items waiting for the agent. listen: asked by `wait` (counts as the agent being there, returns only
        items not handed out yet); take: hand them out."""
        def pick():
            return [x for k, s in sorted(self.stores.items()) if not page or page in k
                    for x in s.waiting_items(undelivered=listen)]
        with self.cond:
            if listen:
                self.listeners += 1
                self.cond.notify_all()
            try:
                for s in self.stores.values():
                    s.fresh()
                items = pick()
                if not items and wait > 0:
                    self.cond.wait_for(pick, wait)
                    items = pick()
                if take and items:
                    for x in items:
                        s = self.stores[x['page']]
                        s.taken[x['id']] = s.data['items'][x['id']]['user_rev']
                    self.taken_at = time.time()
                if self.report_mode:                   # who the comment is for: the theme's owner session
                    owners = self.owners()
                    items = [dict(x, theme=report_key(x['page']), owner=owners.get(report_key(x['page'])))
                             for x in items]
                return dump({'now': time.time(), 'last_user_at': self.last_user_at, 'presence': self.presence(),
                             'url': self.url, 'items': items})
            finally:
                if listen:
                    self.listeners -= 1
                    self.last_listen = time.time()
                    self.cond.notify_all()

    def post(self, path, body):
        """POST /_talk/api/<name>: (code, JSON bytes) or None."""
        if not isinstance(body, dict):
            raise ValueError('a JSON object is expected')
        if path != '/_talk/api/ack' and not body.get('page'):
            raise ValueError('page is required')
        with self.cond:
            if path == '/_talk/api/mark':          # the list of reports: a star, the tags, hidden
                if not self.report_mode:
                    return 404, dump({'error': 'the server runs without --reports'})
                return 200, dump(self.mark(body.get('page'), body.get('star'), body.get('tags'), body.get('hidden')))
            if path == '/_talk/api/edit':
                return self.edit(body)
            if path == '/_talk/api/user':
                s = self.store(body.get('page'))
                it = s.user(body.get('id'), body.get('title'), body.get('status'), body.get('comment'),
                            body.get('notify', True) is not False, body.get('anchor'))
                if it['user_rev'] == s.data['rev']:
                    self.last_user_at = time.time()
            elif path == '/_talk/api/seen':
                s = self.store(body.get('page'))
                it = s.seen(body.get('id'))
            elif path == '/_talk/api/agent':
                s = self.store(body.get('page'), loose=True)
                it = s.agent(body.get('id'), body.get('reply'), body.get('status'), body.get('fields'))
            elif path == '/_talk/api/ack':
                ids = body.get('ids')
                if ids is not None and not (isinstance(ids, list) and all(isinstance(i, str) for i in ids)):
                    raise ValueError('ids: a list of item ids')
                stores = [self.store(body['page'], loose=True)] if body.get('page') else list(self.stores.values())
                acked = {s.page: s.ack(ids) for s in stores}
                self.cond.notify_all()
                return 200, dump({'acked': {k: v for k, v in acked.items() if v}})
            else:
                return None
            self.cond.notify_all()
            return 200, dump(dict(it, id=body.get('id'), page=s.page, rev=s.data['rev']))

    def edit(self, body):
        """The user's fix of a block of the page's text (Edit on the page): the block, found in the page's file by its
        tag, its text and which one of the same it is (of `count`), gets the new content, and the fix is kept in the
        page's state (edits). Callers hold self.cond."""
        p, full = self.page_file(body.get('page'))
        tag, text, nth, count, new, after = (body.get(k) for k in ('tag', 'text', 'nth', 'count', 'html', 'after'))

        def whole(n):
            return isinstance(n, int) and not isinstance(n, bool) and n >= 0
        if (tag not in EDIT_TAGS or not isinstance(text, str) or not squash(text) or not whole(nth)
                or count is not None and not whole(count) or not isinstance(new, str) or len(new) > 50000):
            raise ValueError('edit: {page, tag (one of %s), text, nth, count?, html, after?}' % ' '.join(EDIT_TAGS))
        bad = Unsafe(new).bad
        if bad:
            raise ValueError('edit: the new content may hold text, links and formatting only, not %s'
                             % ', '.join(bad[:3]))
        with open(full, 'rb') as f:
            raw = f.read()
        src = raw.decode('utf-8-sig')
        a, z = find_block(src, tag, text, nth, count)
        if '\r\n' in src:                      # the file's own line ends
            new = new.replace('\r\n', '\n').replace('\n', '\r\n')
        tmp = full + '.tmp'
        with open(tmp, 'wb') as f:
            f.write((b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') +
                    (src[:a] + new + src[z:]).encode('utf-8'))
        replace_file(tmp, full)
        s = self.store(p)
        s.edited(tag, text, after if isinstance(after, str) else html.unescape(re.sub(r'<[^>]*>', '', new)))
        self.cond.notify_all()
        return 200, dump({'page': p, 'rev': s.data['rev']})

    def listing(self):
        m = LISTING[self.lang]
        with self.cond:
            rows = []
            for p, s in sorted(self.stores.items()):
                if not os.path.isfile(s.path):
                    continue
                n = len(s.waiting_items())
                href = '/' + urllib.parse.quote(p) if self.places and not os.path.isabs(p) else None
                name = '<a href="%s">%s</a>' % (href, html.escape(p)) if href else html.escape(p)
                rows.append('<li>%s%s</li>' % (name, m['unread'] % n if n else ''))
            root = html.escape(', '.join(pl.root for pl in self.places) or '-')
        return ('<!doctype html><html lang="%s"><head><meta charset="utf-8">%s<title>talkpage</title>%s'
                '<style>:root{color-scheme:light dark}'
                'body{font:15px/1.7 system-ui,sans-serif;margin:24px 16px;max-width:860px;overflow-wrap:break-word}'
                '.m{color:#888;font-size:13px}</style></head><body><h1>talkpage</h1>'
                '<p class="m">%s</p><ul>%s</ul><p class="m">%s</p></body></html>'
                % (self.lang, VIEWPORT.decode(), FAVICON, m['meta'] % (root, self.presence()),
                   ''.join(rows) or '<li>%s</li>' % m['none'], m['note'])).encode('utf-8')

    def report_listing(self):
        """The list of reports at / (--reports: a root without index.html, or the places): drawn by its script from
        the rows of reports(), which go in as JSON; the stars, the tags and "read" are set from it."""
        m = REPORTS[self.lang]
        d = self.reports()
        data = json.dumps({'rows': d['rows'], 'places': d['places'], 'multi': self.multi, 'read': READ, 'm': m},
                          ensure_ascii=False).replace('<', '\\u003c')        # nothing in it ends the <script>
        meta = m['places'] % len(self.places) if self.multi else m['meta'] % html.escape(self.root)
        page = LISTING_PAGE
        for k, v in (('LANG', self.lang), ('VIEWPORT', VIEWPORT.decode()), ('FAVICON', FAVICON),
                     ('TITLE', html.escape(m['title'])), ('META', meta), ('DATA', data)):
            page = page.replace('{{%s}}' % k, v)
        return page.encode('utf-8')


def dump(obj):
    return json.dumps(obj, ensure_ascii=False).encode('utf-8')


# ---------------------------------------------------------------- HTTP server
class Handler(BaseHTTPRequestHandler):
    talk = None
    server_version = 'talkpage/1'
    API = ('/_talk/api/',)                     # routes for the pages' scripts and the agent, not for opening

    def log_message(self, *_):
        pass

    def _send(self, code, body, ctype='application/json', headers=None):
        if not isinstance(body, bytes):
            body = dump(body)
        text = ctype.startswith('text/') or ctype.endswith(('json', 'javascript'))
        self.send_response(code)
        self.send_header('Content-Type', ctype + ('; charset=utf-8' if text else ''))
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')     # another site cannot frame a page to steer clicks
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _acts(self, path, q):
        """A request that changes something: every POST / DELETE, and the agent's `wait` taking items."""
        return self.command != 'GET' or path == '/_talk/api/pending' and bool(q.get('listen') or q.get('take'))

    def _local(self, path, q):
        """Only this server's own pages and the agent's commands. Host: another name is DNS rebinding. Origin (every
        POST, other sites' fetches): ours or nothing. Sec-Fetch-Site (also <img>, <script>, forms): another site may
        open a page by a link and nothing else. What acts needs our Origin, or a request of our page (same-origin,
        or our Referer in a browser without Sec-Fetch-Site); clients without a browser send Origin (call())."""
        port = self.server.server_address[1]
        remote = self.talk.remote if port == self.talk.port else None     # Tailscale serve proxies to --port
        own = own_origins(port, self.talk.name, remote)
        h = self.headers
        host = (h.get('Host') or '').lower()
        if host not in [urllib.parse.urlsplit(o).netloc for o in own]:
            return False
        if remote and host == urllib.parse.urlsplit(remote).netloc and not self._own_user():
            return False
        origin = (h.get('Origin') or '').lower()
        if origin:
            return origin in own                                   # also refuses "null" (sandboxed frames, file:)
        site = (h.get('Sec-Fetch-Site') or '').lower()
        if site in ('cross-site', 'same-site'):
            return (self.command == 'GET' and not path.startswith(self.API)
                    and h.get('Sec-Fetch-Mode') == 'navigate' and h.get('Sec-Fetch-Dest') == 'document')
        ref = urllib.parse.urlsplit(h.get('Referer') or '')
        ref = ('%s://%s' % (ref.scheme, ref.netloc)).lower() if ref.netloc else ''
        if ref and ref not in own:
            return False
        return not self._acts(path, q) or site == 'same-origin' or bool(ref)

    def _own_user(self):
        """A request by the tailnet name comes through Tailscale serve, which drops these headers from what a device
        sends and sets them itself: the login of the device's user, or Tailscale-Funnel-Request from the internet
        (and no login from a tagged device). Only this PC's own user passes."""
        h = self.headers
        if h.get('Tailscale-Funnel-Request'):
            return False
        try:
            login = str(email.header.make_header(email.header.decode_header(h.get('Tailscale-User-Login') or '')))
        except (email.errors.HeaderParseError, LookupError, UnicodeDecodeError):
            return False
        return bool(login) and login.lower() == self.talk.remote_login.lower()

    def _run(self, fn):
        try:
            path, _, query = self.path.partition('?')
            if not self._local(path, urllib.parse.parse_qs(query)):
                port = self.server.server_address[1]
                return self._send(403, {'error': 'only pages of http://127.0.0.1:%d; a client without a browser sends '
                                                 'the header Origin: http://127.0.0.1:%d' % (port, port)})
            fn()
        except (BrokenPipeError, ConnectionError):
            pass                               # the page went away during a long poll
        except ValueError as e:
            self._send(400, {'error': str(e)})
        except OSError as e:
            self._send(500, {'error': str(e)})

    def do_GET(self):
        self._run(self._get)

    def do_POST(self):
        self._run(self._post)

    def _get(self):
        path, _, query = self.path.partition('?')
        r = self.talk.get(path, urllib.parse.parse_qs(query))
        if r:
            return self._send(*r)
        if path in ('/_talk', '/_talk/'):
            return self._send(200, self.talk.listing(), 'text/html')
        if path.startswith('/_talk/'):
            name = path[len('/_talk/'):]
            if name not in CLIENT:
                return self._send(404, {'error': 'not found'})
            with open(os.path.join(HERE, name), 'rb') as f:
                return self._send(200, f.read(), TYPES[os.path.splitext(name)[1]])
        self._static(path)

    def _index(self):
        """/ of the root without index.html, and / of the places: the list of reports, else the pages with a state."""
        if self.talk.report_mode:
            return self._send(200, inject(self.talk.report_listing()), 'text/html')
        return self._send(200, self.talk.listing(), 'text/html')

    def _static(self, raw):
        talk = self.talk
        parts = [s for s in urllib.parse.unquote(raw).split('/') if s]
        if any(bad_part(s) for s in parts):
            return self._send(404, {'error': 'not found'})
        if talk.multi and not parts:
            return self._index()
        hit = talk.locate(parts)
        if hit is None:                        # under --place: a path from before the places, if --fallback says where
            if talk.fallback and parts:
                return self._send(301, b'', 'text/plain', {'Location': quoted([talk.fallback] + parts, raw)})
            return self._send(404, {'error': 'not found'})
        pl, rest = hit
        root = pl.root
        full = os.path.realpath(os.path.join(root, *rest))
        if full != root and not full.startswith(root + os.sep):
            return self._send(404, {'error': 'not found'})
        if os.path.isdir(full):
            if not raw.endswith('/'):
                return self._send(301, b'', 'text/plain', {'Location': quoted(parts, '/')})
            if not os.path.isfile(os.path.join(full, 'index.html')) and full == root:
                if talk.multi and talk.report_mode:          # a place's own folder: its group in the list
                    return self._send(302, b'', 'text/plain', {'Location': '/#' + pl.id})
                return self._index()
            full = os.path.join(full, 'index.html')
        ctype = TYPES.get(os.path.splitext(full)[1].lower())
        if not ctype or not os.path.isfile(full):
            return self._send(404, {'error': 'not found'})
        with open(full, 'rb') as f:
            data = f.read()
        if self.talk.report_mode and ctype == 'text/html':
            data = inject(data)                # in the response only; the file stays as it is
        self._send(200, data, ctype)

    def _post(self):
        if not (self.headers.get('Content-Type') or '').lower().startswith('application/json'):
            return self._send(415, {'error': 'Content-Type: application/json'})
        n = int(self.headers.get('Content-Length') or 0)
        if n > 1000000:
            raise ValueError('body too large')
        body = json.loads(self.rfile.read(n).decode('utf-8')) if n else {}
        r = self.talk.post(self.path.partition('?')[0], body)
        self._send(*r) if r else self._send(404, {'error': 'not found'})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != 'nt'     # on Windows SO_REUSEADDR would let two servers share the port

    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)


# ---------------------------------------------------------------- command line
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))     # never through a proxy


def call(a, path, body=None, timeout=15, **q):
    url = 'http://127.0.0.1:%d%s' % (a.port, path)
    q = {k: v for k, v in q.items() if v not in (None, '')}
    if q:
        url += '?' + urllib.parse.urlencode(q)
    data = dump(body) if body is not None else None
    head = {'Origin': 'http://127.0.0.1:%d' % a.port}                # the server refuses writes without our Origin
    if data:
        head['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data, head)
    try:
        with _opener.open(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get('error')
        except ValueError:
            msg = str(e)
        raise SystemExit('talkpage: %s' % msg)


def cmd_serve(a):
    if bool(a.root) == bool(a.place):
        raise SystemExit('talkpage: serve <root>, or serve --place [GROUP:]ID=FOLDER ... (not both)')
    places = [parse_place(x) for x in a.place or ()]
    for _, _, folder in places or [('', '', a.root)]:
        if not os.path.isdir(folder):
            raise SystemExit('talkpage: not a folder: %s' % folder)
    root = os.path.realpath(a.root) if a.root else None
    name = check_name(a.name) if a.name else None
    remote = None
    if a.tailscale:
        remote = tailscale(a.port)
        if not remote[0]:
            print('talkpage: not on the tailnet: %s' % remote[1], file=sys.stderr, flush=True)
            remote = None
    try:
        talk = Talk(root, a.port, a.lang or default_lang('TALKPAGE_LANG'), name, a.reports, remote, places,
                    a.fallback, a.marks)
    except ValueError as e:
        raise SystemExit('talkpage: %s' % e)
    Handler.talk = talk
    try:
        srv = Server(('127.0.0.1', a.port), Handler)
    except OSError as e:
        raise SystemExit('talkpage: cannot listen on 127.0.0.1:%d (%s). Another talkpage? '
                         'http://127.0.0.1:%d/_talk/api/info tells its root.' % (a.port, e, a.port))
    srv80 = None
    if name and a.port != 80:                  # the same pages at http://NAME/ (browsers do not write :80)
        try:
            srv80 = Server(('127.0.0.1', 80), Handler)
            threading.Thread(target=srv80.serve_forever, kwargs={'poll_interval': 0.2}, daemon=True).start()
            talk.on80 = True
        except OSError as e:
            print('talkpage: port 80 is not free (%s); the pages are at http://%s:%d/' % (e, name, a.port),
                  file=sys.stderr, flush=True)
    url = talk.url
    print('talkpage: %s at %s%s (%d pages with a state%s). Ctrl-C to stop.'
          % (root or ', '.join('/%s/ %s' % (p.id, p.root) for p in talk.places), url, ' and ' + talk.local_url if talk.remote else '', len(talk.stores),
             ', reports' if talk.report_mode else ''), flush=True)
    if a.open:
        page = os.path.relpath(os.path.realpath(a.open), root) if root and os.path.isabs(a.open) else a.open
        p, _ = talk.page_file(page)
        webbrowser.open(url + urllib.parse.quote(p))
    try:
        srv.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        if srv80:
            srv80.shutdown()
            srv80.server_close()


def me(a, sub):
    port = '' if a.port == 8190 else ' --port %d' % a.port
    return 'python "%s" %s%s' % (os.path.abspath(__file__).replace('\\', '/'), sub, port)


def print_pending(a, d, rest):
    print('talkpage: the user acted on %d item(s)  %s' % (len(d['items']), d['url']))
    by = {}
    for x in d['items']:
        by.setdefault(x['page'], []).append(x)
    for page, xs in by.items():
        print('== page: %s' % page)
        for x in xs:
            print('- %s  [%s]  %s' % (x['id'], x['status'] or '-', x['title']))
            for m in x['new']:
                t = m.get('time', '')[11:]
                if 'text' in m:
                    lines = m['text'].splitlines() or ['']
                    print('    %s comment: %s' % (t, lines[0]))
                    for line in lines[1:]:
                        print('      ' + line)
                else:
                    print('    %s status: %s' % (t, m.get('status') or '(cleared)'))
    if rest:
        print('also waiting (printed before, not answered): ' + ', '.join('%s %s' % (x['page'], x['id']) for x in rest))
    print('reply: ' + me(a, 'reply') + ' --page "<page>" --id <id> [--status S] --text "..."'
          '  (long or non-ASCII text: --text - with the text on stdin)')
    print('read, no reply: ' + me(a, 'ack') + ' --page "<page>" [--id <id> ...]')
    print('then wait again in the background: ' + me(a, 'wait'))


def cmd_wait(a):
    while True:
        try:
            d = call(a, '/_talk/api/pending', timeout=70, page=a.page, wait=50, listen=1)
            if not d['items']:
                continue
            while d['now'] - d['last_user_at'] < a.settle:          # let a run of clicks finish first
                time.sleep(min(1.0, a.settle - (d['now'] - d['last_user_at'])) + 0.05)
                d = call(a, '/_talk/api/pending', page=a.page, listen=1)
            d = call(a, '/_talk/api/pending', page=a.page, listen=1, take=1)
            if not d['items']:
                continue
            shown = {(x['page'], x['id']) for x in d['items']}
            rest = [x for x in call(a, '/_talk/api/pending', page=a.page)['items'] if (x['page'], x['id']) not in shown]
        except (urllib.error.URLError, OSError):                     # the server is not up yet, or restarting
            time.sleep(2)
            continue
        if a.json:                                                   # for an agent that hands the items on as they are
            print(json.dumps({'url': d['url'], 'items': d['items'],
                              'also_waiting': [{'page': x['page'], 'id': x['id']} for x in rest]}, ensure_ascii=False))
        else:
            print_pending(a, d, rest)
        return


def cmd_reply(a):
    text = a.text
    if a.file:
        with open(a.file, encoding='utf-8') as f:
            text = f.read()
    elif text == '-':
        text = sys.stdin.buffer.read().decode('utf-8')
    fields = None
    if a.fields and a.fields.startswith('@'):                       # @file: Japanese text without the shell's quoting
        with open(a.fields[1:], encoding='utf-8') as f:
            fields = json.load(f)
    elif a.fields:
        fields = json.loads(a.fields)
    if a.summary is not None:                                       # a 2-3 line summary of the whole thread
        fields = dict(fields or {}, summary=a.summary.strip())
    body = {'page': a.page, 'id': a.id, 'reply': text, 'status': a.status, 'fields': fields}
    r = call(a, '/_talk/api/agent', body)
    print('talkpage: %s  %s  [%s]  %d message(s)' % (r['page'], r['id'], r['status'] or '-',
                                                    sum(1 for m in r['thread'] if m.get('text'))))


def cmd_ack(a):
    r = call(a, '/_talk/api/ack', {'page': a.page, 'ids': a.id or None})
    print('talkpage: read ' + ('; '.join('%s: %s' % (p, ', '.join(ids)) for p, ids in r['acked'].items()) or 'nothing'))


def cmd_show(a):
    pages = [a.page] if a.page else call(a, '/_talk/api/info')['pages']
    for p in pages:
        d = call(a, '/_talk/api/state', page=p)
        print('== page: %s  (%s)' % (d['page'], d['file']))
        for k in sorted(d['items'], key=natural):
            it = d['items'][k]
            print('- %s  [%s]%s  %s' % (k, it['status'] or '-', '  *waiting*' if waiting(it) else '',
                                        it.get('title', '')[:80]))
            msgs = [m for m in it['thread'] if m.get('text')]
            if msgs:
                m = msgs[-1]
                print('    last %s %s: %s' % (m['who'], m.get('time', '')[5:16], m['text'].splitlines()[0][:100]))
        for e in d.get('edits', []):           # the user's own fixes of the text: take them in before building it again
            print('~ edit %s <%s>  %s  ->  %s' % (e['time'][5:16], e['tag'], e['before'][:100], e['after'][:100]))


def reports_data(a):
    """(info, /_talk/api/reports) of a server run with --reports, or SystemExit with the reason."""
    try:
        info = call(a, '/_talk/api/info')
        return info, call(a, '/_talk/api/reports')
    except (urllib.error.URLError, OSError) as e:
        raise SystemExit('talkpage: no server on 127.0.0.1:%d (%s); start it with: talkpage serve <root> --reports'
                         % (a.port, getattr(e, 'reason', e)))


def report_line(x, opened):
    line = '\t'.join((x['theme'], x['round'] or '-', x['owner'] or '-', x['title']))
    if x.get('submission'):
        line += ' [submission; basis: %s]' % (', '.join(x['basis']) or '-')
    if x['comments']:
        line += ' [comments: %s]' % ','.join(x['comments'])
    return line + (' [open]' if x['page'] in opened else '')


def cmd_reports(a):
    info, d = reports_data(a)
    rows, opened = d['rows'], set(info.get('open') or [])
    by_theme = {x['theme']: x for x in rows}
    oldest = sorted(rows, key=lambda x: x['time'])
    act, args = a.action, a.args

    def tracked(names):
        if not names:
            raise SystemExit('talkpage: reports %s: name one or more themes (or all)' % act)
        if names == ['all']:
            return [x for x in oldest if x['tracked']]
        bad = [n for n in names if n not in by_theme or not by_theme[n]['tracked']]
        if bad:
            raise SystemExit('talkpage: not a theme with rounds: %s' % ', '.join(bad))
        return [by_theme[n] for n in names]

    if act == 'list':
        if args:
            raise SystemExit('talkpage: reports list takes no arguments')
        groups = (('unread', [x for x in oldest if x['tracked'] and not x['read']]),
                  ('read', [x for x in rows if x['tracked'] and x['read']]),
                  ('pages', [x for x in rows if not x['tracked']]))
        for label, xs in groups:
            print('== %s: %d' % (label, len(xs)))
            for x in xs:
                print(report_line(x, opened))
        missing = ['%s: %s' % (x['page'], w) for x in rows for w in x.get('basis_missing') or []]
        if missing:
            print('basis not found (report-basis; a theme with rounds, or <theme>/<round>): ' + ', '.join(missing))
    elif act == 'owner':
        if len(args) != 3:
            raise SystemExit('talkpage: reports owner <theme> <name> <id>')
        theme, name, sid = args
        if theme not in by_theme:
            raise SystemExit('talkpage: no such theme: %s' % theme)
        folder, key = d['root'], theme                          # under --place: that place's owners.json
        for pl in d.get('places') or []:
            if pl['id'] and theme.startswith(pl['id'] + '/'):
                folder, key = pl['root'], theme[len(pl['id']) + 1:]
        path = os.path.join(folder, 'owners.json')
        owners = {}
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                try:
                    owners = json.load(f)
                except ValueError as e:
                    raise SystemExit('talkpage: %s is not JSON (%s); fix or remove it' % (path, e))
            if not isinstance(owners, dict):
                raise SystemExit('talkpage: %s is not a JSON object' % path)
        owners[key] = {'name': name, 'id': sid}
        for v in owners.values():               # the session's other themes take the name too (it may have been renamed)
            if isinstance(v, dict) and v.get('id') == sid:
                v['name'] = name
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(owners, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write('\n')
        os.replace(tmp, path)
        print('talkpage: owner of %s: %s (%s)' % (theme, name, sid))
    elif act in ('read', 'unread'):
        for x in tracked(args):
            status = ''
            if act == 'read':                                       # in the page's language, like its buttons
                lang = x.get('lang') or ''
                status = READ[0] if lang.startswith('ja') else READ[1]
            call(a, '/_talk/api/agent', {'page': x['page'], 'id': 'read', 'status': status})
            print('talkpage: %s  [%s]' % (x['page'], status or '-'))
    elif act == 'open':
        if args:
            raise SystemExit('talkpage: reports open [--owner S]')
        if a.owner:
            xs = [x for x in oldest if a.owner in x['owner']]
        else:
            xs = [x for x in oldest if x['tracked'] and not x['read']]
        xs = [x for x in xs if x['page'] not in opened]             # already open in a tab
        for x in xs:
            webbrowser.open(info['url'] + urllib.parse.quote(x['page']))
            print('talkpage: opened ' + x['page'])
        if not xs:
            print('talkpage: nothing to open')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--port', type=int, default=PORT)
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('serve', help='serve the pages under a folder')
    s.add_argument('root', nargs='?')
    s.add_argument('--place', action='append',
                   help='[GROUP:]ID=FOLDER instead of <root>, repeated: the folder at /ID/, headed GROUP in the list')
    s.add_argument('--fallback', help='under --place: a path whose first part is no place goes to /FALLBACK/<path>')
    s.add_argument('--marks', help='the stars and tags of the list (default ~/.talkpage/marks-<port>.json)')
    s.add_argument('--open', help='open this page (path under the root, or the file) in the default browser')
    s.add_argument('--lang', choices=LANGS,
                   help='language of the index page (default: $TALKPAGE_LANG, else ja for a Japanese OS, else en)')
    s.add_argument('--name', default=os.environ.get('TALKPAGE_NAME') or None,
                   help='also serve at http://NAME/, a name ending in .localhost (default: $TALKPAGE_NAME)')
    s.add_argument('--reports', action='store_true',
                   help='the root holds reports: list them at / and add talkpage.js to the pages')
    s.add_argument('--tailscale', action='store_true',
                   help="also serve what Tailscale serve proxies here, to this PC's own user (phone, other PCs)")
    s = sub.add_parser('wait', help='block until the user acts, print it, exit')
    s.add_argument('--page', help='only this page (path or a unique part of it)')
    s.add_argument('--settle', type=float, default=4.0, help='seconds without new clicks before printing (default 4)')
    s.add_argument('--json', action='store_true', help='print one JSON object {url, items, also_waiting} instead')
    s = sub.add_parser('reply', help='answer an item')
    s.add_argument('--page', required=True)
    s.add_argument('--id', required=True)
    s.add_argument('--status', help='set the status ("" clears it)')
    s.add_argument('--text', help='the reply; "-" reads it from stdin (UTF-8)')
    s.add_argument('--file', help='read the reply from this UTF-8 file')
    s.add_argument('--fields', help='JSON object of extra item fields to store, or @file with that JSON (UTF-8)')
    s.add_argument('--summary', help='a 2-3 line summary of the thread, shown on the page (fields.summary)')
    s = sub.add_parser('ack', help='mark what waits as read without replying')
    s.add_argument('--page')
    s.add_argument('--id', action='append', help='only these items (repeat)')
    s = sub.add_parser('show', help="all items of a page, and the user's fixes of its text (~ edit)")
    s.add_argument('--page')
    s = sub.add_parser('reports', help='the reports of a server run with --reports')
    s.add_argument('action', nargs='?', default='list', choices=('list', 'owner', 'read', 'unread', 'open'))
    s.add_argument('args', nargs='*')
    s.add_argument('--owner', help='open: the pages of the themes whose owner contains this')
    for sp in sub.choices.values():                                 # --port also after the subcommand
        sp.add_argument('--port', type=int, default=argparse.SUPPRESS)
    a = p.parse_args()
    {'serve': cmd_serve, 'wait': cmd_wait, 'reply': cmd_reply, 'ack': cmd_ack, 'show': cmd_show,
     'reports': cmd_reports}[a.cmd](a)


if __name__ == '__main__':
    main()
