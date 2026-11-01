#!/usr/bin/env python3
"""talkpage: local web pages where the user marks items and writes comments, and a coding agent is woken to answer.

  python talkpage.py serve <root> [--port 8190] [--open PAGE] [--lang en|ja] [--name NAME.localhost] [--reports]
                           [--tailscale]
  python talkpage.py wait  [--page P] [--settle 4] [--json]
  python talkpage.py reply --page P --id ID [--status S] [--text T | --text - | --file F] [--fields JSON] [--summary S]
  python talkpage.py ack   [--page P] [--id ID ...]
  python talkpage.py show  [--page P]
  python talkpage.py reports [list | owner THEME NAME ID | read THEME... | read all | unread THEME... | open [--owner S]]

serve: <root> holds the pages; the state of <dir>/<name>.html is kept beside it in <dir>/<name>.talk.json. Only
127.0.0.1 is served. wait: blocks until the user acts on a page, prints what they did and exits; an agent runs it in
the background (Claude Code: Bash run_in_background) so that the exit wakes it. reply: answer an item (the reply
shows on the page). ack: mark what was printed as read without replying. show: all items of a page.
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
"""
import argparse
import email.errors
import email.header
import html
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
ROUND_RE = re.compile(r'^\d{8}-\d{4}-r\d+(-[^/]+)?$')      # a round <theme>/<round>/index.html (also r27-marks)
TITLE_RE = re.compile(rb'<title[^>]*>(.*?)</title', re.I | re.S)
LANG_RE = re.compile(rb'<html[^>]*?\slang\s*=\s*["\']?([A-Za-z-]+)', re.I)
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
           'no_owner': 'no owner', 'meta': 'root: %s · all pages with a state: <a href="/_talk/">/_talk/</a>'},
    'ja': {'title': 'レポートの一覧', 'unread': '未読', 'comments': 'コメント %s', 'none': '（まだ無い）',
           'no_owner': '担当なし', 'meta': 'root: %s ・ 状態のあるページの一覧: <a href="/_talk/">/_talk/</a>'},
}
FAVICON = ("<link rel=\"icon\" href=\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
           "<text y='.9em' font-size='90'>💬</text></svg>\">")


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


def report_key(page):
    """The theme key of a page under --reports: the folder above its round (<theme>/<round>/...), the folder of a
    single index.html, or the path of any other single page. owners.json is keyed by it."""
    parts = page.split('/')
    for i in range(len(parts) - 2, 0, -1):
        if ROUND_RE.match(parts[i]):
            return '/'.join(parts[:i])
    return '/'.join(parts[:-1]) if parts[-1] == 'index.html' and len(parts) > 1 else page


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


def waiting(it):
    return it.get('user_rev', 0) > it.get('agent_rev', 0)


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
        for i in range(20):                    # Windows: an editor or sync client may hold the file for a moment
            try:
                os.replace(tmp, self.path)
                break
            except PermissionError:
                if i == 19:
                    raise
                time.sleep(0.05)
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

    def user(self, iid, title=None, status=None, comment=None, notify=True):
        it = self.item(iid, create=True)
        status = check_status(status)
        comment = (comment or '').strip() if isinstance(comment, str) else ''
        title = str(title).strip()[:200] if title else ''
        changed = status is not None and status != it['status']
        if not changed and not comment:
            if title and title != it.get('title'):
                it['title'] = title
                self._next()
                self.save()
            return it
        rev = self._next()
        if title:
            it['title'] = title
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

    def seen(self, iid):
        it = self.item(iid)
        last = max([m.get('rev', 0) for m in it['thread'] if m.get('who') == 'agent' and m.get('text')] or [0])
        if last > it['seen_rev']:
            it['seen_rev'] = last
            self._next()
            self.save()
        return it

    def view(self):
        return {'page': self.page, 'file': self.path.replace('\\', '/'), 'rev': self.data['rev'],
                'items': self.data['items']}

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


class Talk:
    """The stores under one root, the agent's presence, and the /_talk/api/ routes. Another server can host stores
    kept at its own paths (attach) and hand /_talk/api/ requests to get() / post()."""

    def __init__(self, root=None, port=PORT, lang='en', name=None, reports=False, remote=None):
        self.root = os.path.realpath(root) if root else None
        self.port = port
        self.lang = lang if lang in LANGS else 'en'      # of the index page; the pages carry their own <html lang>
        self.name = name or None                         # --name, checked by check_name()
        self.on80 = False                                # a second listener serves the name on port 80
        self.remote, self.remote_login = remote or (None, None)     # --tailscale: (origin, login) of tailscale()
        self.report_mode = bool(reports and self.root)
        self.viewed = {}                                 # page -> when a page last asked for its state with open=1
        self.cond = threading.Condition()
        self.stores = {}
        self.listeners = 0                     # `wait` requests in progress
        self.last_listen = 0.0                 # end of the last one
        self.taken_at = 0.0                    # when a `wait` last took items (the agent is working on them)
        self.last_user_at = 0.0
        if self.root:
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
        """{theme: {name, id}} of <root>/owners.json (written by `talkpage reports owner`), or {}."""
        try:
            with open(os.path.join(self.root, 'owners.json'), encoding='utf-8') as f:
                d = json.load(f)
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in d.items() if isinstance(v, dict)} if isinstance(d, dict) else {}

    def reports(self):
        """The reports under the root: the last round of each theme with rounds, and the single pages, newest first."""
        found = []                             # (theme key, round, page, file, time)
        for d, dirs, files in os.walk(self.root):
            dirs[:] = sorted(x for x in dirs if not x.startswith(('.', '_')) and x not in SKIP_DIRS)
            rel = os.path.relpath(d, self.root).replace('\\', '/')
            rel = '' if rel == '.' else rel
            rounds = [x for x in dirs if ROUND_RE.match(x) and os.path.isfile(os.path.join(d, x, 'index.html'))]
            if rounds and rel:                 # a theme: its last round; the earlier ones are linked from its index
                r = max(rounds, key=natural)
                found.append((rel, r, '%s/%s/index.html' % (rel, r), os.path.join(d, r, 'index.html'),
                              '%s-%s-%s %s:%s' % (r[:4], r[4:6], r[6:8], r[9:11], r[11:13])))
            dirs[:] = [x for x in dirs if not ROUND_RE.match(x)]     # the other files of a round are not rows
            for f in sorted(files):
                if not f.lower().endswith(('.html', '.htm')) or f == 'index.html' and (rounds or not rel):
                    continue                   # the index of the rounds, and the root's own index
                page = rel + '/' + f if rel else f
                try:
                    t = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(os.path.join(d, f))))
                except OSError:
                    continue
                found.append((report_key(page), '', page, os.path.join(d, f), t))
        owners = self.owners()
        rows = []
        with self.cond:
            for theme, r, page, full, t in found:
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
                owner = owners.get(theme, {}).get('name', '')
                rows.append({'page': page, 'theme': theme, 'round': r, 'title': page_title(head(full)) or theme,
                             'owner': owner if isinstance(owner, str) else '', 'tracked': bool(r),
                             'status': read if r else '-', 'read': bool(r) and read in READ,
                             'comments': comments, 'time': t})
        rows.sort(key=lambda x: x['time'], reverse=True)
        return {'root': self.root.replace('\\', '/'), 'url': self.url, 'rows': rows}

    def scan(self):
        for d, dirs, files in os.walk(self.root):
            dirs[:] = [x for x in dirs if not x.startswith('.') and x not in SKIP_DIRS]
            for f in files:
                page_file = os.path.join(d, f[:-len('.talk.json')] + '.html')
                if f.endswith('.talk.json') and os.path.isfile(page_file):
                    page = os.path.relpath(page_file, self.root).replace('\\', '/')
                    try:
                        self.stores[page] = Store(os.path.join(d, f), page)
                    except (OSError, ValueError) as e:
                        print('talkpage: skipped %s: %s' % (os.path.join(d, f), e), file=sys.stderr)

    def html_pages(self):
        out = []
        for d, dirs, files in os.walk(self.root) if self.root else ():
            dirs[:] = [x for x in dirs if not x.startswith('.') and x not in SKIP_DIRS]
            out += [os.path.relpath(os.path.join(d, f), self.root).replace('\\', '/') for f in files
                    if f.lower().endswith(('.html', '.htm'))]
        return sorted(out)

    def attach(self, page, path):
        """Keep the state of `page` (any key) in `path`, e.g. a review file of another tool."""
        with self.cond:
            s = self.stores[page] = Store(path, page)
            return s

    def page_file(self, page):
        """(page path, file) for a page path from a URL or the command line, or ValueError."""
        p = urllib.parse.unquote(str(page or '')).replace('\\', '/').lstrip('/')
        if p == '' or p.endswith('/'):
            p += 'index.html'
        parts = p.split('/')
        if (not self.root or any(s in ('', '.', '..') or s.startswith('.') for s in parts)
                or not p.lower().endswith(('.html', '.htm'))):
            raise ValueError('page: an .html path under the root: %s' % p)
        full = os.path.realpath(os.path.join(self.root, *parts))
        if not full.startswith(self.root + os.sep) or not os.path.isfile(full):
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
                                  'port': self.port, 'lang': self.lang, 'presence': self.presence(),
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
                return 200, dump(dict(s.view(), presence=self.presence()))
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
            if path == '/_talk/api/user':
                s = self.store(body.get('page'))
                it = s.user(body.get('id'), body.get('title'), body.get('status'), body.get('comment'),
                            body.get('notify', True) is not False)
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

    def listing(self):
        m = LISTING[self.lang]
        with self.cond:
            rows = []
            for p, s in sorted(self.stores.items()):
                if not os.path.isfile(s.path):
                    continue
                n = len(s.waiting_items())
                href = '/' + urllib.parse.quote(p) if self.root and not os.path.isabs(p) else None
                name = '<a href="%s">%s</a>' % (href, html.escape(p)) if href else html.escape(p)
                rows.append('<li>%s%s</li>' % (name, m['unread'] % n if n else ''))
            root = html.escape(self.root or '-')
        return ('<!doctype html><html lang="%s"><head><meta charset="utf-8">%s<title>talkpage</title>%s'
                '<style>:root{color-scheme:light dark}'
                'body{font:15px/1.7 system-ui,sans-serif;margin:24px 16px;max-width:860px;overflow-wrap:break-word}'
                '.m{color:#888;font-size:13px}</style></head><body><h1>talkpage</h1>'
                '<p class="m">%s</p><ul>%s</ul><p class="m">%s</p></body></html>'
                % (self.lang, VIEWPORT.decode(), FAVICON, m['meta'] % (root, self.presence()),
                   ''.join(rows) or '<li>%s</li>' % m['none'], m['note'])).encode('utf-8')

    def report_listing(self):
        """The list of reports at / (--reports, the root has no index.html); every value is escaped."""
        m = REPORTS[self.lang]
        rows = []
        for x in self.reports()['rows']:
            meta = ' · '.join(html.escape(v) for v in (x['theme'], x['round'], x['owner'] or m['no_owner'], x['time'])
                              if v)
            mark = '<b class="u">%s</b>' % m['unread'] if x['tracked'] and not x['read'] else ''
            if x['comments']:
                mark += '<span class="c">%s</span>' % html.escape(m['comments'] % ', '.join(x['comments']))
            rows.append('<li><a href="/%s"><span class="t">%s</span>%s<span class="m">%s</span></a></li>'
                        % (html.escape(urllib.parse.quote(x['page'])), html.escape(x['title']), mark, meta))
        return ('<!doctype html><html lang="%s"><head><meta charset="utf-8">%s<title>%s</title>%s'
                '<style>:root{color-scheme:light dark}'               # a whole row is the link: a finger-sized target
                'body{font:15px/1.6 system-ui,sans-serif;margin:24px 16px;max-width:860px;overflow-wrap:break-word}'
                'h1{font-size:22px}ul{list-style:none;margin:0;padding:0}li{border-top:1px solid #8884}'
                'li a{display:block;padding:8px 2px;color:inherit;text-decoration:none}li a:hover .t{text-decoration:underline}'
                '.t{font-weight:600;color:#0a5fb4}.u{margin-left:8px;font-size:12px;color:#cf222e}'
                '.c{margin-left:8px;font-size:13px;color:#b45309}.m{display:block;color:#888;font-size:13px}'
                '@media (prefers-color-scheme:dark){.t{color:#6cb6ff}.u{color:#f85149}.c{color:#d29922}}</style></head>'
                '<body data-talk-listing><h1>%s</h1>'                      # no file behind it: no state, no items
                '<p class="m">%s</p><ul>%s</ul></body></html>'
                % (self.lang, VIEWPORT.decode(), html.escape(m['title']), FAVICON, html.escape(m['title']),
                   m['meta'] % html.escape(self.root), ''.join(rows) or '<li>%s</li>' % m['none'])).encode('utf-8')


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

    def _static(self, raw):
        root = self.talk.root
        parts = [s for s in urllib.parse.unquote(raw).split('/') if s]
        if not root or any(s in ('.', '..') or s.startswith('.') or '\\' in s for s in parts):
            return self._send(404, {'error': 'not found'})
        full = os.path.realpath(os.path.join(root, *parts))
        if full != root and not full.startswith(root + os.sep):
            return self._send(404, {'error': 'not found'})
        if os.path.isdir(full):
            if not raw.endswith('/'):
                return self._send(301, b'', 'text/plain', {'Location': raw + '/'})
            if not os.path.isfile(os.path.join(full, 'index.html')) and full == root:
                if self.talk.report_mode:
                    return self._send(200, inject(self.talk.report_listing()), 'text/html')
                return self._send(200, self.talk.listing(), 'text/html')
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
    root = os.path.realpath(a.root)
    if not os.path.isdir(root):
        raise SystemExit('talkpage: not a folder: %s' % a.root)
    name = check_name(a.name) if a.name else None
    remote = None
    if a.tailscale:
        remote = tailscale(a.port)
        if not remote[0]:
            print('talkpage: not on the tailnet: %s' % remote[1], file=sys.stderr, flush=True)
            remote = None
    talk = Talk(root, a.port, a.lang or default_lang('TALKPAGE_LANG'), name, a.reports, remote)
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
          % (root, url, ' and ' + talk.local_url if talk.remote else '', len(talk.stores),
             ', reports' if talk.report_mode else ''), flush=True)
    if a.open:
        page = os.path.relpath(os.path.realpath(a.open), root) if os.path.isabs(a.open) else a.open
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
    elif act == 'owner':
        if len(args) != 3:
            raise SystemExit('talkpage: reports owner <theme> <name> <id>')
        theme, name, sid = args
        if theme not in by_theme:
            raise SystemExit('talkpage: no such theme: %s' % theme)
        path = os.path.join(d['root'], 'owners.json')
        owners = {}
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                try:
                    owners = json.load(f)
                except ValueError as e:
                    raise SystemExit('talkpage: %s is not JSON (%s); fix or remove it' % (path, e))
            if not isinstance(owners, dict):
                raise SystemExit('talkpage: %s is not a JSON object' % path)
        owners[theme] = {'name': name, 'id': sid}
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
                lang = page_lang(head(os.path.join(d['root'], *x['page'].split('/'))))
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
    s.add_argument('root')
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
    s = sub.add_parser('show', help='all items of a page')
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
