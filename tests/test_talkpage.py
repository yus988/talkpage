"""Tests of talkpage: the store, the HTTP routes and the wait / reply commands. python -m unittest discover tests"""
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')
sys.path.insert(0, SRC)     # run from a clone without installing
import talkpage as tp  # noqa: E402

ENV = dict(os.environ, PYTHONPATH=os.pathsep.join([SRC, os.environ.get('PYTHONPATH', '')]))
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.s = tp.Store(os.path.join(self.dir, 'p.talk.json'), 'p.html')

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_status_comment_reply(self):
        it = self.s.user('C2', 'C2 title', status='NG')
        self.assertTrue(tp.waiting(it))
        self.assertEqual(self.s.waiting_items()[0]['new'][0]['status'], 'NG')
        it = self.s.user('C2', comment='  still on  ')
        self.assertEqual(it['thread'][-1]['text'], 'still on')
        self.assertEqual(len(self.s.waiting_items()[0]['new']), 2)
        it = self.s.agent('C2', reply='looking')
        self.assertFalse(tp.waiting(it))
        self.assertEqual(self.s.waiting_items(), [])
        again = tp.Store(self.s.path, 'p.html')                     # saved beside the page
        self.assertEqual(again.data['items']['C2']['thread'][-1]['text'], 'looking')

    def test_quiet_status_and_ack(self):
        it = self.s.user('B1', status='OK', notify=False)
        self.assertFalse(tp.waiting(it))
        self.s.user('B2', status='OK')
        self.s.user('B3', status='OK')
        self.assertEqual(self.s.ack(['B2']), ['B2'])
        self.assertEqual(self.s.ack(), ['B3'])
        self.assertEqual(self.s.ack(), [])

    def test_seen_and_fields(self):
        self.s.agent('A1', reply='result', status='OK', fields={'note': 'x'})
        it = self.s.data['items']['A1']
        self.assertEqual((it['status'], it['note'], it['seen_rev']), ('OK', 'x', 0))
        self.assertEqual(self.s.seen('A1')['seen_rev'], it['thread'][-1]['rev'])
        with self.assertRaises(ValueError):
            self.s.agent('A1', fields={'thread': []})
        with self.assertRaises(ValueError):
            self.s.user('bad\nid', status='OK')
        with self.assertRaises(ValueError):
            self.s.user('', status='OK')
        self.assertEqual(self.s.user('net:/Power In/Net-(U6-EN)', status='OK')['status'], 'OK')

    def test_anchor(self):
        self.s.user('C1', 'quote', comment='c', anchor={'heads': ['2. A', ' ', 3], 'id': 'H1', 'pos': 0.4567, 'x': 1})
        it = self.s.data['items']['C1']
        self.assertEqual(it['anchor'], {'heads': ['2. A'], 'id': 'H1', 'pos': 0.457})
        rev, user_rev = self.s.data['rev'], it['user_rev']
        self.s.user('C1', 'quote', anchor={'pos': 0.5}, notify=False)       # an anchor alone: kept, nobody is woken
        self.assertEqual((it['anchor'], self.s.data['rev'], it['user_rev']), ({'pos': 0.5}, rev + 1, user_rev))
        self.s.user('C1', 'quote', anchor={'pos': 2, 'id': 'bad\nid', 'heads': 'x'})     # nothing valid: unchanged
        self.assertEqual((it['anchor'], self.s.data['rev']), ({'pos': 0.5}, rev + 1))
        self.assertEqual(tp.Store(self.s.path, 'p.html').data['items']['C1']['anchor'], {'pos': 0.5})
        with self.assertRaises(ValueError):
            self.s.user('C1', anchor='top')

    def test_edit_page_text(self):
        page = os.path.join(self.dir, 'p.html')
        src = ('﻿<!doctype html>\r\n<html><head><title>same</title></head><body>\r\n<p>same</p>\r\n'
               '<div data-talk="A"><p>same</p></div>\r\n<template><p>same</p></template>\r\n'
               '<ul><li>a &amp; <b>b</b></li><li>same<ul><li>in</li></ul></li></ul>\r\n<p>same</p>\r\n</body></html>\r\n')
        with open(page, 'w', encoding='utf-8', newline='') as f:
            f.write(src)
        talk = tp.Talk(self.dir)

        def edit(**kw):
            with talk.cond:
                return talk.edit(dict({'page': 'p.html'}, **kw))
        # the 2nd <p> with this text outside data-talk and template, of 2; the file keeps its BOM and CRLF
        edit(tag='p', text=' same ', nth=1, count=2, html='fixed\n<a href="x">link</a> one=1', after='fixed link one=1')
        edit(tag='li', text='a & b', nth=0, html='a &amp; <b>c</b>')
        with open(page, encoding='utf-8', newline='') as f:
            out = f.read()
        self.assertEqual(out, src.replace('<p>same</p>\r\n</body>', '<p>fixed\r\n<a href="x">link</a> one=1</p>\r\n</body>')
                         .replace('<b>b</b>', '<b>c</b>'))
        edits = talk.store('p.html').data['edits']
        self.assertEqual([(e['tag'], e['before'], e['after']) for e in edits],
                         [('p', 'same', 'fixed link one=1'), ('li', 'a & b', 'a & c')])
        for bad in (dict(nth=1),                                           # only one left
                    dict(nth=0, count=2),                                  # the page saw another number of them
                    dict(nth=0, html='<img src=x onerror=alert(1)>'),
                    dict(nth=0, html='<a href=" java\tscript:alert(1)">x</a>'),
                    dict(nth=0, html='<script>x</script>'),
                    dict(nth=0, tag='div'),
                    dict(nth=0, page='../p.html')):
            with self.assertRaises(ValueError, msg=bad):
                edit(**dict({'tag': 'p', 'text': 'same', 'html': 'x'}, **bad))
        with open(page, 'w', encoding='utf-8') as f:                       # an <li> without </li>: no guess
            f.write('<body><ul><li>one<li>two</li></ul><p>three</p></body>')
        with self.assertRaises(ValueError):
            edit(tag='li', text='two', nth=0, html='2')
        edit(tag='p', text='three', nth=0, html='3')                        # other tags are fine

    def test_deleted_file_starts_over(self):
        self.s.user('C1', status='NG')
        rev = self.s.data['rev']
        os.remove(self.s.path)
        self.s.fresh()
        self.assertEqual((self.s.data['items'], self.s.data['rev']), ({}, rev + 1))
        self.s.user('C2', status='OK')
        self.assertEqual(list(tp.Store(self.s.path, 'p.html').data['items']), ['C2'])

    def test_upgrade_old_file(self):
        with open(self.s.path, 'w', encoding='utf-8') as f:
            json.dump({'items': {'field:C21': {'status': '質問', 'thread': [
                {'who': 'user', 'text': 'why?', 'time': 't'}]}, 'comp:U6': {'status': 'OK', 'thread': [
                    {'who': 'user', 'text': 'q', 'time': 't'}, {'who': 'agent', 'text': 'a', 'time': 't'}]}},
                       'groups': [1]}, f)
        s = tp.Store(self.s.path, 'old')
        self.assertEqual([x['id'] for x in s.waiting_items()], ['field:C21'])
        self.assertEqual(s.waiting_items()[0]['new'][0]['text'], 'why?')
        s.agent('field:C21', reply='because')
        self.assertEqual(s.waiting_items(), [])
        self.assertEqual(s.data['groups'], [1])                        # the owner's keys are kept


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(cls.root, 'notes', 'r1'))
        with open(os.path.join(cls.root, 'notes', 'r1', 'index.html'), 'w', encoding='utf-8') as f:
            f.write('<!doctype html><title>t</title><div data-talk="A1">a</div>')
        os.makedirs(os.path.join(cls.root, 'notes', 'other'))
        with open(os.path.join(cls.root, 'notes', 'other', 'index.html'), 'w', encoding='utf-8') as f:
            f.write('<!doctype html><title>o</title>')
        with open(os.path.join(cls.root, 'secret.txt'), 'w') as f:
            f.write('no')
        cls.talk = tp.Talk(cls.root, 0)
        tp.Handler.talk = cls.talk
        cls.srv = tp.Server(('127.0.0.1', 0), tp.Handler)
        cls.port = cls.talk.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        shutil.rmtree(cls.root)

    def req(self, path, body=None, headers=None, timeout=10, info=False):
        """(code, body) of a request sent like the page does (our Origin); headers: None removes one."""
        h = {'Origin': 'http://127.0.0.1:%d' % self.port}
        if body is not None:
            h['Content-Type'] = 'application/json'
        h.update(headers or {})
        r = urllib.request.Request('http://127.0.0.1:%d%s' % (self.port, path),
                                   json.dumps(body).encode() if body is not None else None,
                                   {k: v for k, v in h.items() if v is not None})
        try:
            with OPENER.open(r, timeout=timeout) as resp:
                data = resp.read()
                out = resp.status, json.loads(data) if 'json' in resp.headers['Content-Type'] else data
                return out + (resp.headers,) if info else out
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}')

    def cli(self, *args, **kw):
        return subprocess.run([sys.executable, '-m', 'talkpage', '--port', str(self.port)] + list(args), env=ENV,
                              capture_output=True, text=True, encoding='utf-8', timeout=30, **kw)

    def test_1_static_and_client(self):
        code, body = self.req('/notes/r1/')
        self.assertEqual(code, 200)
        self.assertIn(b'data-talk', body)
        self.assertNotIn(b'data-talk-report', body)                 # nothing is added without --reports
        self.assertEqual(self.req('/_talk/api/reports')[0], 404)
        self.assertEqual(self.req('/_talk/talkpage.js')[0], 200)
        self.assertEqual(self.req('/secret.txt')[0], 200)
        self.assertEqual(self.req('/notes/r1/../../secret.txt')[0], 404)
        self.assertEqual(self.req('/%2e%2e/x.html')[0], 404)
        self.assertEqual(self.req('/.git/config')[0], 404)
        self.assertEqual(self.req('/_talk/__init__.py')[0], 404)
        code, body = self.req('/_talk/')
        self.assertIn(b'<html lang="en">', body)                    # the index page in the server's language
        self.assertIn(b'Only pages with a state are listed', body)
        self.assertEqual(self.req('/_talk/api/info')[1]['lang'], 'en')

    def test_2_guards(self):
        self.assertEqual(self.req('/_talk/api/info', headers={'Host': 'evil.example:%d' % self.port})[0], 403)
        self.assertEqual(self.req('/_talk/api/user', {'page': 'notes/r1/index.html', 'id': 'A1', 'status': 'OK'},
                                  headers={'Origin': 'https://evil.example'})[0], 403)
        r = urllib.request.Request('http://127.0.0.1:%d/_talk/api/user' % self.port, b'{}', {
            'Content-Type': 'text/plain', 'Origin': 'http://127.0.0.1:%d' % self.port})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            OPENER.open(r, timeout=5)
        self.assertEqual(cm.exception.code, 415)
        self.assertEqual(self.req('/_talk/api/user', {'page': '../x.html', 'id': 'A1', 'status': 'OK'})[0], 400)
        self.assertEqual(self.req('/_talk/api/user', {'page': 'notes/r1/none.html', 'id': 'A1', 'status': 'OK'})[0], 400)

    def test_2a_origins(self):
        port = self.port
        no_origin = {'Origin': None}
        user = {'page': 'notes/r1/index.html', 'id': 'A1', 'status': 'OK'}
        # writes: our Origin (either name) only; none (curl), "null" and another site's are refused
        self.assertEqual(self.req('/_talk/api/user', user, no_origin)[0], 403)
        self.assertEqual(self.req('/_talk/api/user', user, {'Origin': 'null'})[0], 403)
        self.assertEqual(self.req('/_talk/api/ack', {'page': 'other'}, {'Origin': 'http://localhost:%d' % port})[0], 200)
        self.assertEqual(self.req('/_talk/api/ack', {'page': 'other'}, {'Origin': 'http://127.0.0.1:1'})[0], 403)
        # the agent's wait takes items: not by another site's <img>, also without Sec-Fetch-Site and Referer
        cross = {'Origin': None, 'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'no-cors', 'Sec-Fetch-Dest': 'image'}
        self.assertEqual(self.req('/_talk/api/pending?take=1&listen=1', headers=cross)[0], 403)
        self.assertEqual(self.req('/_talk/api/pending?take=1', headers=no_origin)[0], 403)
        self.assertEqual(self.req('/_talk/api/pending?take=1', headers={'Origin': None,
                                                                        'Sec-Fetch-Site': 'same-origin'})[0], 200)
        self.assertEqual(self.req('/_talk/api/pending?take=1', headers={
            'Origin': None, 'Referer': 'http://127.0.0.1:%d/notes/r1/' % port})[0], 200)
        # reads: a client without a browser may read; another site's page may not, nor load our files
        self.assertEqual(self.req('/_talk/api/info', headers=no_origin)[0], 200)
        self.assertEqual(self.req('/_talk/api/info', headers={'Origin': None, 'Referer': 'https://evil.example/'})[0], 403)
        self.assertEqual(self.req('/_talk/api/info', headers=dict(cross, **{'Sec-Fetch-Mode': 'cors'}))[0], 403)
        self.assertEqual(self.req('/secret.txt', headers=dict(cross, **{'Sec-Fetch-Dest': 'script'}))[0], 403)
        # another site may open a page by a link (top level), not frame it
        nav = dict(cross, **{'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document'})
        code, _, head = self.req('/notes/r1/', headers=nav, info=True)
        self.assertEqual((code, head['X-Frame-Options']), (200, 'SAMEORIGIN'))
        self.assertEqual(self.req('/notes/r1/', headers=dict(nav, **{'Sec-Fetch-Dest': 'iframe'}))[0], 403)
        self.assertEqual(self.req('/_talk/api/pending?take=1', headers=nav)[0], 403)

    def test_2b_agent_writes_first(self):
        r = self.cli('reply', '--page', 'other', '--id', 'X1', '--status', 'OK')     # a page with no state yet
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('notes/other/index.html  X1  [OK]', r.stdout)
        self.assertIn("page 'zzz' matches no page", self.cli('reply', '--page', 'zzz', '--id', 'X1').stderr)

    def test_3_flow_with_wait(self):
        page = 'notes/r1/index.html'
        waiter = subprocess.Popen([sys.executable, '-m', 'talkpage', '--port', str(self.port), 'wait',
                                   '--settle', '0.5'], env=ENV, stdout=subprocess.PIPE, text=True, encoding='utf-8')
        for _ in range(50):        # the waiter starts a new python: up to 5 s on a loaded machine
            if self.req('/_talk/api/state?page=' + page)[1]['presence'] == 'listening':
                break
            time.sleep(0.1)
        self.assertEqual(self.req('/_talk/api/state?page=' + page)[1]['presence'], 'listening')
        code, it = self.req('/_talk/api/user', {'page': page, 'id': 'A1', 'title': 'A1 a', 'status': 'NG',
                                                'comment': '鳴らない\n2 行目'}, headers={'Origin': 'http://127.0.0.1:%d' % self.port})
        self.assertEqual(code, 200)
        out = waiter.communicate(timeout=15)[0]
        self.assertEqual(waiter.returncode, 0)
        self.assertIn('- A1  [NG]  A1 a', out)
        self.assertIn('comment: 鳴らない', out)
        self.assertIn('      2 行目', out)
        self.assertIn('status: NG', out)
        self.assertEqual(self.req('/_talk/api/info')[1]['presence'], 'working')
        self.assertTrue(os.path.isfile(os.path.join(self.root, 'notes', 'r1', 'index.talk.json')))

        # a state request with the current rev waits until something changes (the agent's reply)
        rev = self.req('/_talk/api/state?page=' + page)[1]['rev']
        got = {}
        t = threading.Thread(target=lambda: got.update(r=self.req('/_talk/api/state?page=%s&rev=%d&wait=10' % (page, rev))))
        t.start()
        time.sleep(0.3)
        r = self.cli('reply', '--page', 'r1', '--id', 'A1', '--text', '-', input='見ます。`probe.cmd` で確認')
        self.assertEqual(r.returncode, 0, r.stderr)
        t.join(5)
        it = got['r'][1]['items']['A1']
        self.assertEqual(it['thread'][-1], dict(it['thread'][-1], who='agent', text='見ます。`probe.cmd` で確認'))
        self.assertFalse(tp.waiting(it))

        # what was handed to a wait is not handed again; a new comment is
        self.req('/_talk/api/user', {'page': page, 'id': 'A2', 'status': 'OK'})
        w1 = self.cli('wait', '--settle', '0.2')
        self.assertIn('- A2  [OK]', w1.stdout)
        self.req('/_talk/api/user', {'page': page, 'id': 'A1', 'comment': 'again'})
        w2 = self.cli('wait', '--settle', '0.2')
        self.assertIn('comment: again', w2.stdout)
        self.assertIn('also waiting (printed before, not answered): notes/r1/index.html A2', w2.stdout)
        a = self.cli('ack', '--page', 'r1')
        self.assertIn('A1, A2', a.stdout)
        self.assertEqual(self.req('/_talk/api/pending')[1]['items'], [])
        self.assertIn('[NG]', self.cli('show', '--page', 'r1').stdout)

    def test_4_anchor(self):
        page = 'notes/r1/index.html'
        anchor = {'heads': ['2. Background', '2.1 Before'], 'id': 'background', 'pos': 0.25}
        code, it = self.req('/_talk/api/user', {'page': page, 'id': 'C1', 'title': 'some text', 'comment': 'why?',
                                                'anchor': anchor})
        self.assertEqual((code, it['anchor']), (200, anchor))
        # the page notes where an older comment is, quietly: kept, the agent is not woken
        code, it = self.req('/_talk/api/user', {'page': page, 'id': 'C2', 'title': 'other', 'anchor': {'pos': 0.5},
                                                'notify': False})
        self.assertEqual((code, it['anchor'], tp.waiting(it)), (200, {'pos': 0.5}, False))
        self.assertEqual(self.req('/_talk/api/user', {'page': page, 'id': 'C1', 'anchor': 'top'})[0], 400)
        with open(os.path.join(self.root, 'notes', 'r1', 'index.talk.json'), encoding='utf-8') as f:
            items = json.load(f)['items']
        self.assertEqual((items['C1']['anchor'], items['C2']['anchor']), (anchor, {'pos': 0.5}))
        self.assertIn('C1', self.cli('ack', '--page', 'r1').stdout)

    def test_5_edit(self):
        write(self.root, 'notes/fix.html', '<!doctype html><title>f</title><body><p>Old  text</p></body>')
        body = {'page': 'notes/fix.html', 'tag': 'p', 'text': 'Old text', 'nth': 0, 'count': 1, 'html': 'New text'}
        self.assertEqual(self.req('/_talk/api/edit', body, {'Origin': None})[0], 403)       # a write: our Origin only
        self.assertEqual(self.req('/_talk/api/edit', body, {'Origin': 'https://evil.example'})[0], 403)
        code, d = self.req('/_talk/api/edit', body)
        self.assertEqual((code, d['page']), (200, 'notes/fix.html'))
        self.assertIn(b'<p>New text</p>', self.req('/notes/fix.html')[1])
        code, d = self.req('/_talk/api/edit', body)                                    # the old text is gone
        self.assertEqual(code, 400)
        self.assertIn('the file has 0 <p> with this text', d['error'])
        self.assertEqual(self.req('/_talk/api/state?page=notes/fix.html')[1]['edits'][0]['after'], 'New text')
        self.assertEqual(self.req('/_talk/api/pending?page=fix')[1]['items'], [])      # the agent is not woken
        self.assertIn('<p>  Old text  ->  New text', self.cli('show', '--page', 'fix').stdout)


def write(root, path, text):
    full = os.path.join(root, *path.split('/'))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    return full


class ReportsTest(unittest.TestCase):
    """serve --reports --name x.localhost: the list of reports, the client added to the pages, the commands."""
    R3 = 'motor/20261031-1500-r3/index.html'
    FIT = 'cad/widget/case-fit/20261025-0042-r1/index.html'

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        w = lambda p, t: write(cls.root, p, t)      # noqa: E731
        w('motor/index.html', '<title>rounds of motor</title>')
        w('motor/20261030-1000-r2/index.html', '<html lang="ja"><title>r2</title>')
        w(cls.R3, '<html lang="ja"><head><title>モーター &amp;\n  比較 r3</title></head><body>本文</body></html>')
        w('motor/20261031-1500-r3/extra.html', '<title>extra</title>')
        w(cls.FIT, '<html lang="en"><title>case fit</title><body>text</body>')
        cls.single = w('review/index.html', '<html lang="ja"><title>&lt;b&gt;review</title><BODY>x</BODY></html>')
        w('survey-20261016.html', '<title>survey</title>no body')
        w('fusion/bobbin.html', '<title>bobbin</title>')
        w('own/index.html', '<body><script src="/_talk/talkpage.js"></script></body>')
        w('_private/x.html', '<title>private</title>')
        w('.hidden/y.html', '<title>hidden</title>')
        w('style.css', 'body{}')
        w('data.json', '{"a": "</body>"}')
        w('owners.json', json.dumps({'motor': {'name': 'モーター変更検討', 'id': 's1'}}, ensure_ascii=False))
        for i, p in enumerate(('review/index.html', 'survey-20261016.html', 'fusion/bobbin.html', 'own/index.html')):
            t = time.mktime((2026, 10, 28, 11, i, 0, 0, 0, -1))
            os.utime(os.path.join(cls.root, *p.split('/')), (t, t))
        cls.talk = tp.Talk(cls.root, 0, 'ja', name='x.localhost', reports=True)

        class H(tp.Handler):
            talk = cls.talk
        cls.srv = tp.Server(('127.0.0.1', 0), H)
        cls.port = cls.talk.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        shutil.rmtree(cls.root)

    req = HttpTest.req
    cli = HttpTest.cli

    def rows(self):
        return {x['page']: x for x in self.req('/_talk/api/reports')[1]['rows']}

    def test_names(self):
        self.assertEqual(tp.own_origins(80, 'x.localhost'), ('http://127.0.0.1', 'http://localhost', 'http://x.localhost'))
        self.assertEqual(tp.own_origins(8190)[1], 'http://localhost:8190')
        self.assertEqual(tp.check_name('Notes.Localhost'), 'notes.localhost')
        for bad in ('notes.example', 'localhost', 'a..localhost', 'x.localhost:80'):
            with self.assertRaises(SystemExit):
                tp.check_name(bad)
        named = 'x.localhost:%d' % self.port
        user = {'page': 'review/index.html', 'id': 'N1', 'status': 'OK', 'notify': False}
        self.assertEqual(self.req('/_talk/api/user', user, {'Host': named, 'Origin': 'http://' + named})[0], 200)
        self.assertEqual(self.req('/review/', headers={'Host': named, 'Origin': None})[0], 200)
        self.assertEqual(self.req('/_talk/api/info', headers={'Host': 'y.localhost:%d' % self.port})[0], 403)
        # another name's or another port's Origin (a GET: a refused POST body can reset the connection on Windows)
        self.assertEqual(self.req('/_talk/api/info', headers={'Origin': 'http://y.localhost:%d' % self.port})[0], 403)
        self.assertEqual(self.req('/_talk/api/info', headers={'Origin': 'http://x.localhost'})[0], 403)
        info = self.req('/_talk/api/info')[1]
        self.assertEqual((info['name'], info['url']), ('x.localhost', 'http://%s/' % named))
        self.assertEqual(tp.Talk(None, 8190).url, 'http://127.0.0.1:8190/')

    def test_inject(self):
        code, body, head = self.req('/review/', info=True)
        self.assertEqual(body, b'<html lang="ja">' + tp.VIEWPORT + b'<title>&lt;b&gt;review</title><BODY>x' + tp.INJECT +
                         b'</BODY></html>')
        self.assertEqual(int(head['Content-Length']), len(body))
        self.assertTrue(self.req('/survey-20261016.html')[1].endswith(b'no body' + tp.INJECT))
        self.assertEqual(self.req('/own/')[1], tp.VIEWPORT + b'<body><script src="/_talk/talkpage.js"></script></body>')
        self.assertEqual(self.req('/style.css')[1], b'body{}')
        self.assertEqual(self.req('/data.json')[1], {'a': '</body>'})
        with open(self.single, encoding='utf-8') as f:
            self.assertNotIn('talkpage', f.read())                  # the file stays as it is
        self.assertEqual(tp.inject(b'a</body>b</body>'), tp.VIEWPORT + b'a</body>b' + tp.INJECT + b'</body>')
        doc = b'<!DOCTYPE html><HEAD lang=x><meta name=viewport content="width=500"></head>'
        self.assertEqual(tp.inject(doc), doc + tp.INJECT)                        # its own viewport stays
        self.assertEqual(tp.inject(b'<!doctype html><p>'), b'<!doctype html>' + tp.VIEWPORT + b'<p>' + tp.INJECT)

    def test_list(self):
        rows = self.rows()
        self.assertEqual(sorted(rows), sorted([self.R3, self.FIT, 'review/index.html', 'survey-20261016.html',
                                               'fusion/bobbin.html', 'own/index.html']))
        r3 = rows[self.R3]
        self.assertEqual((r3['theme'], r3['round'], r3['title'], r3['owner'], r3['tracked'], r3['time']),
                         ('motor', '20261031-1500-r3', 'モーター & 比較 r3', 'モーター変更検討', True, '2026-10-31 15:00'))
        self.assertEqual(rows[self.FIT]['theme'], 'cad/widget/case-fit')
        self.assertEqual((rows['review/index.html']['theme'], rows['review/index.html']['status']), ('review', '-'))
        self.assertEqual(rows['fusion/bobbin.html']['theme'], 'fusion/bobbin.html')
        self.assertEqual(rows['own/index.html']['title'], 'own')                  # no <title>: the theme
        self.assertEqual([x['time'] for x in self.req('/_talk/api/reports')[1]['rows']][:2],
                         ['2026-10-31 15:00', '2026-10-28 11:03'])                # newest first
        # unread comments only (a status alone is not one)
        self.req('/_talk/api/user', {'page': self.R3, 'id': 'C2', 'title': '本文', 'comment': 'なぜ?'})
        self.req('/_talk/api/user', {'page': self.R3, 'id': 'C1', 'status': 'NG'})
        self.assertEqual(self.rows()[self.R3]['comments'], ['C2'])
        self.req('/_talk/api/ack', {'page': self.R3})
        self.assertEqual(self.rows()[self.R3]['comments'], [])
        code, body = self.req('/')
        self.assertIn(b'"\\u003cb>review"', body)                              # nothing in the JSON ends the <script>
        self.assertNotIn(b'<b>review', body)
        self.assertIn(tp.INJECT, body)
        self.assertIn('レポートの一覧'.encode(), body)

    def test_open_and_summary(self):
        self.req('/_talk/api/state?page=' + self.FIT + '&open=1')
        self.assertIn(self.FIT, self.req('/_talk/api/info')[1]['open'])
        r = self.cli('reply', '--page', self.FIT, '--id', 'C1', '--text', 'ok', '--summary', '  2 行の要約  ',
                     '--fields', '{"note": "n"}')
        self.assertEqual(r.returncode, 0, r.stderr)
        it = self.req('/_talk/api/state?page=' + self.FIT)[1]['items']['C1']
        self.assertEqual((it['summary'], it['note']), ('2 行の要約', 'n'))

    def test_reports_commands(self):
        r = self.cli('reports', 'owner', 'cad/widget/case-fit', 'ケース', 'sid-2')
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.root, 'owners.json'), encoding='utf-8') as f:
            self.assertEqual(json.load(f), {'cad/widget/case-fit': {'name': 'ケース', 'id': 'sid-2'},
                                            'motor': {'name': 'モーター変更検討', 'id': 's1'}})
        self.assertIn('no such theme', self.cli('reports', 'owner', 'nothing', 'a', 'b').stderr)
        r = self.cli('reports', 'read', 'motor', 'cad/widget/case-fit')
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.rows()
        self.assertEqual((rows[self.R3]['status'], rows[self.R3]['read']), ('読んだ', True))
        self.assertEqual((rows[self.FIT]['status'], rows[self.FIT]['read']), ('Read', True))
        self.assertIn('not a theme with rounds: review', self.cli('reports', 'read', 'review').stderr)
        self.cli('reports', 'unread', 'motor')
        self.assertEqual(self.rows()[self.R3]['read'], False)
        out = self.cli('reports').stdout
        self.assertIn('== unread: 1\nmotor\t20261031-1500-r3\tモーター変更検討\tモーター & 比較 r3', out)
        self.assertIn('== read: 1\ncad/widget/case-fit\t20261025-0042-r1\tケース\tcase fit', out)
        self.assertIn('== pages: 4', out)
        self.assertIn('review\t-\t-\t<b>review', out)
        # one name per session: naming one of its themes renames the others
        self.cli('reports', 'owner', 'review', 'ケース', 'sid-2')
        self.cli('reports', 'owner', 'review', 'ケース改', 'sid-2')
        with open(os.path.join(self.root, 'owners.json'), encoding='utf-8') as f:
            self.assertEqual(json.load(f)['cad/widget/case-fit'], {'name': 'ケース改', 'id': 'sid-2'})

    def test_owner_names(self):
        owners = {'a': {'name': 'old', 'id': 's'}, 'b': {'name': 'new', 'id': 's'}, 'c': {'name': 'new', 'id': 's'},
                  'd': {'name': 'x'}, 'e': {'name': 'y', 'id': ''}, 'f': {'id': 't'}}
        self.assertEqual(tp.owner_names(owners), {'a': 'new', 'b': 'new', 'c': 'new', 'd': 'x', 'e': 'y', 'f': ''})

    def test_submissions(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        for p in ('grinder/20261028-1000-r1/index.html', 'grinder/20261029-1500-r2/index.html',
                  'kettle/20261029-1200-r1/index.html', 'cad/case/20261025-0042-r1/index.html', 'notes.html'):
            write(root, p, '<title>%s</title>' % p)
        meta = '<head><title>plan</title><META content="%s" Name=report-basis></head>'
        plan = write(root, 'plan/index.html', meta % 'grinder/20261028-1000-r1 kettle cad/case/20261025-0042-r1 nothing')
        talk = tp.Talk(root, 0, reports=True)
        rows = {x['page']: x for x in talk.reports()['rows']}
        sub = rows['plan/index.html']
        self.assertEqual((sub['submission'], sub['basis'], sub['basis_rounds'], sub['basis_missing']),
                         (True, ['grinder', 'kettle', 'cad/case'], {'grinder': '20261028-1000-r1', 'cad/case': '20261025-0042-r1'},
                          ['nothing']))
        self.assertEqual(rows['grinder/20261029-1500-r2/index.html']['in'], ['plan'])     # the theme's last round
        self.assertEqual((rows['notes.html']['submission'], 'basis' in rows['notes.html'], 'in' in rows['notes.html']),
                         (False, False, False))
        self.assertEqual(tp.report_line(sub, set()), 'plan\t-\t-\tplan [submission; basis: grinder, kettle, cad/case]')
        # a changed meta shows on the next request (not after the walk's few seconds)
        with open(plan, 'w', encoding='utf-8') as f:
            f.write(meta % 'kettle')
        t = time.time() + 5
        os.utime(plan, (t, t))
        sub = {x['page']: x for x in talk.reports()['rows']}['plan/index.html']
        self.assertEqual((sub['basis'], sub['basis_rounds'], sub['basis_missing']), (['kettle'], {}, []))
        self.assertEqual(tp.page_basis(b'<meta name="report-basis" content="">'), [])
        self.assertIsNone(tp.page_basis(b'<meta name="description" content="report-basis">'))
        # several places: a theme of the submission's own place first, another place's by its id
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other)
        write(other, 'grinder/20261030-0900-r1/index.html', '<title>b</title>')
        write(other, 'sum.html', meta % 'grinder a/kettle')
        talk = tp.Talk(places=[('', 'a', root), ('', 'b', other)], reports=True)
        sub = {x['page']: x for x in talk.reports()['rows']}['b/sum.html']
        self.assertEqual((sub['theme'], sub['basis']), ('b/sum.html', ['b/grinder', 'a/kettle']))

    def test_wait_json_and_pending_owner(self):
        page = 'review/index.html'
        self.cli('reports', 'owner', 'review', 'レビュー', 'sid-3')
        self.req('/_talk/api/user', {'page': page, 'id': 'C1', 'title': 'x', 'comment': '1 行目\n2 行目'})
        r = self.cli('wait', '--page', 'review', '--settle', '0.2', '--json')
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d['url'], 'http://x.localhost:%d/' % self.port)
        it = d['items'][0]
        self.assertEqual((it['page'], it['id'], it['theme'], it['owner']),
                         (page, 'C1', 'review', {'name': 'レビュー', 'id': 'sid-3'}))
        self.assertEqual(it['new'][0]['text'], '1 行目\n2 行目')
        self.assertEqual(d['also_waiting'], [])
        self.req('/_talk/api/ack', {'page': page})
        self.assertEqual(tp.report_key(self.FIT), 'cad/widget/case-fit')
        self.assertEqual(tp.report_key('motor/20261031-1500-r3/extra.html'), 'motor')
        self.assertEqual(tp.report_key('fusion/bobbin.html'), 'fusion/bobbin.html')
        self.assertEqual(tp.report_key('case/20261028-1316-r27-marks/index.html'), 'case')    # a note after rN
        # without --reports: neither theme nor owner, no list, nothing added to the pages
        plain = tp.Talk(self.root, 0)
        plain.store(page).user('C9', comment='x')
        self.assertNotIn('theme', json.loads(plain.pending(None, 0, False, False))['items'][0])
        self.assertEqual(plain.get('/_talk/api/reports', {})[0], 404)
        plain.store(page).ack()


class PlacesTest(unittest.TestCase):
    """serve --place: the reports of several folders on one server, each at /<id>/; stars and tags from the list."""
    R5 = 'expo/flyer/20261031-1942-r5/index.html'
    R3 = 'notes/motor/20261031-1500-r3/index.html'

    @classmethod
    def setUpClass(cls):
        cls.top = tempfile.mkdtemp()
        cls.a, cls.b, cls.c = (os.path.join(cls.top, x) for x in ('a', 'b', 'c'))
        write(cls.a, 'motor/20261031-1500-r3/index.html', '<html lang="ja"><title>モーター r3</title><body>x</body>')
        write(cls.a, 'owners.json', json.dumps({'motor': {'name': 'モーター', 'id': 's1'}}, ensure_ascii=False))
        write(cls.b, 'plan.html', '<title>plan</title>')
        write(cls.b, '20261026-1506-r2/index.html', '<title>own rounds r2</title>')     # rounds of the place itself
        write(cls.b, 'index.html', '<title>rounds of props</title>')
        write(cls.c, 'flyer/20261031-1942-r5/index.html', '<html lang="ja"><title>チラシ r5</title><body>y</body>')
        write(cls.top, 'secret.html', '<title>outside</title>')
        cls.marks = os.path.join(cls.top, 'marks.json')
        cls.talk = tp.Talk(None, 0, 'ja', reports=True, marks=cls.marks, fallback='notes',
                           places=[('workspace', 'notes', cls.a), ('workspace', 'props', cls.b), ('', 'expo', cls.c)])

        class H(tp.Handler):
            talk = cls.talk
        cls.srv = tp.Server(('127.0.0.1', 0), H)
        cls.port = cls.talk.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        shutil.rmtree(cls.top)

    req = HttpTest.req
    cli = HttpTest.cli

    def raw(self, path):
        """(code, Location) without following a redirect."""
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request('GET', path, headers={'Origin': 'http://127.0.0.1:%d' % self.port})
        r = c.getresponse()
        r.read()
        c.close()
        return r.status, r.getheader('Location')

    def rows(self):
        self.talk._found = (0.0, None)
        return {x['page']: x for x in self.req('/_talk/api/reports')[1]['rows']}

    def test_list_and_pages(self):
        rows = self.rows()
        self.assertEqual(sorted(rows), sorted([self.R5, self.R3, 'props/plan.html', 'props/20261026-1506-r2/index.html']))
        self.assertEqual(rows['props/20261026-1506-r2/index.html']['theme'], 'props')
        r3 = rows[self.R3]
        self.assertEqual((r3['theme'], r3['place'], r3['group'], r3['owner'], r3['lang']),
                         ('notes/motor', 'notes', 'workspace', 'モーター', 'ja'))
        self.assertEqual((rows[self.R5]['group'], rows['props/plan.html']['theme']), ('expo', 'props/plan.html'))
        code, body = self.req('/' + self.R3)
        self.assertEqual(code, 200)
        self.assertIn(tp.INJECT, body)
        self.assertIn(b'"multi": true', self.req('/')[1])
        self.assertEqual(self.req('/_talk/api/info')[1]['places'][2]['id'], 'expo')

    def test_paths(self):
        self.assertEqual(self.raw('/notes/'), (302, '/#notes'))                       # its group in the list
        self.assertEqual(self.raw('/motor/20261031-1500-r3/'), (301, '/notes/motor/20261031-1500-r3/'))  # --fallback
        self.assertEqual(self.raw('//evil.example/x'), (301, '/notes/evil.example/x'))  # never //host
        self.assertEqual(self.raw('/notes/motor'), (301, '/notes/motor/'))
        for bad in ('/notes/../secret.html', '/notes/%2e%2e/secret.html', '/notes/..%5csecret.html',
                    '/notes/C:%5cWindows%5cwin.ini', '/expo/flyer/20261031-1942-r5/index.html:x', '/_x/a.html'):
            self.assertIn(self.raw(bad)[0], (301, 404), bad)
            self.assertNotEqual(self.req(bad)[0], 200, bad)
        with self.assertRaises(ValueError):
            self.talk.page_file('notes/../secret.html')
        with self.assertRaises(ValueError):
            self.talk.page_file('other/plan.html')
        self.assertEqual(tp.quoted(['evil.example'], '//evil.example/'), '/evil.example/')
        with self.assertRaises(ValueError):
            tp.Talk(None, 0, places=[('', 'x', self.a), ('', 'x', self.b)])
        for bad in ('x', 'A=b', '_t=c', '20261031-1500-r3=c', 'g:=c'):
            with self.assertRaises(SystemExit):
                tp.parse_place(bad)
        self.assertEqual(tp.parse_place('g:h:id-1=C:/x=y'), ('g:h', 'id-1', 'C:/x=y'))

    def test_marks_and_read(self):
        r = self.req('/_talk/api/mark', {'page': self.R5, 'star': True, 'tags': [' 展示 ', '展示', 'later']})
        self.assertEqual(r, (200, {'page': self.R5, 'star': True, 'tags': ['展示', 'later'], 'hidden': False}))
        self.assertEqual((self.rows()[self.R5]['star'], self.rows()[self.R5]['tags']), (True, ['展示', 'later']))
        r = self.req('/_talk/api/mark', {'page': self.R5, 'hidden': True})             # hidden; the star and tags kept
        self.assertEqual(r[1], {'page': self.R5, 'star': True, 'tags': ['展示', 'later'], 'hidden': True})
        self.assertTrue(self.rows()[self.R5]['hidden'])
        self.assertFalse(self.rows()[self.R3]['hidden'])
        self.req('/_talk/api/mark', {'page': self.R5, 'star': False, 'tags': [], 'hidden': False})
        with open(self.marks, encoding='utf-8') as f:
            self.assertEqual(json.load(f), {'pages': {}})                 # nothing left: the entry goes
        for bad in ({'page': self.R5, 'tags': ['a,b']}, {'page': self.R5, 'star': 'yes'}, {'page': self.R5, 'hidden': 1},
                    {'page': 'secret.html', 'star': True}, {'page': self.R5, 'tags': [str(i) for i in range(9)]}):
            self.assertEqual(self.req('/_talk/api/mark', bad)[0], 400, bad)
        self.req('/_talk/api/user', {'page': self.R3, 'id': 'read', 'status': '読んだ', 'notify': False})
        self.assertTrue(self.rows()[self.R3]['read'])
        self.assertEqual(json.loads(self.talk.pending(None, 0, False, False))['items'], [])   # not for the agent

    def test_owner_command(self):
        r = self.cli('reports', 'owner', 'expo/flyer', 'チラシ', 'sid-9')
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.c, 'owners.json'), encoding='utf-8') as f:
            self.assertEqual(json.load(f), {'flyer': {'name': 'チラシ', 'id': 'sid-9'}})
        self.assertEqual((self.rows()[self.R5]['owner'], self.rows()[self.R5]['owner_id']), ('チラシ', 'sid-9'))
        r = self.cli('reports', 'read', 'expo/flyer')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rows()[self.R5]['status'], '読んだ')


class TailnetTest(unittest.TestCase):
    """serve --tailscale: requests that Tailscale serve proxies by the tailnet name, for this PC's own user only."""
    ORIGIN = 'https://pc.tail1234.ts.net'

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        write(cls.root, 'r/index.html', '<title>r</title><body>x</body>')
        cls.talk = tp.Talk(cls.root, 0, name='x.localhost', reports=True, remote=(cls.ORIGIN, 'Alice'))

        class H(tp.Handler):
            talk = cls.talk
        cls.srv = tp.Server(('127.0.0.1', 0), H)
        cls.port = cls.talk.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        shutil.rmtree(cls.root)

    req = HttpTest.req

    def test_own_user_only(self):
        via = {'Host': 'pc.tail1234.ts.net', 'Origin': self.ORIGIN, 'Tailscale-User-Login': 'alice'}
        user = {'page': 'r/index.html', 'id': 'C1', 'title': 'x', 'comment': 'from the phone', 'notify': False}
        self.assertEqual(self.req('/_talk/api/user', user, via)[0], 200)
        self.assertEqual(self.req('/r/', headers=dict(via, Origin=None))[0], 200)
        self.assertEqual(self.req('/r/', headers=dict(via, Origin=None, **{
            'Tailscale-User-Login': '=?utf-8?q?Alice?='}))[0], 200)                  # serve's encoded form
        for bad in ({'Tailscale-User-Login': None}, {'Tailscale-User-Login': 'bob'},
                    {'Tailscale-Funnel-Request': '?1'}, {'Host': 'other.tail1234.ts.net'},
                    {'Origin': 'https://evil.example'}, {'Origin': 'http://pc.tail1234.ts.net'}):
            self.assertEqual(self.req('/_talk/api/info', headers=dict(via, **bad))[0], 403, bad)
        info = self.req('/_talk/api/info')[1]                       # this PC as before
        self.assertEqual((info['url'], info['local_url']),
                         (self.ORIGIN + '/', 'http://x.localhost:%d/' % self.port))
        self.assertEqual(self.req('/_talk/api/reports')[1]['url'], self.ORIGIN + '/')
        self.req('/_talk/api/ack', {'page': 'r/index.html'})

    def test_serve_origin(self):
        p = self.port
        serve = {'TCP': {'443': {'HTTPS': True}, '8443': {'HTTPS': True}, '80': {'HTTP': True}},
                 'Web': {'pc.tail1234.ts.net:8443': {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:1'}}},
                         'pc.tail1234.ts.net:443': {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:%d' % p}}}}}
        self.assertEqual(tp.serve_origin(serve, p), self.ORIGIN)
        self.assertEqual(tp.serve_origin(serve, 1), self.ORIGIN + ':8443')
        self.assertIsNone(tp.serve_origin(serve, 2))
        self.assertIsNone(tp.serve_origin(None, p))
        moved = {'TCP': {'443': {'HTTPS': True}},
                 'Web': {'pc.tail1234.ts.net:443': {'Handlers': {'/notes': {'Proxy': 'http://127.0.0.1:%d' % p}}}}}
        self.assertIsNone(tp.serve_origin(moved, p))                # not at /: the pages' absolute paths break
        plain = {'TCP': {'80': {'HTTP': True}},
                 'Web': {'pc.tail1234.ts.net:80': {'Handlers': {'/': {'Proxy': 'http://localhost:%d/' % p}}}}}
        self.assertEqual(tp.serve_origin(plain, p), 'http://pc.tail1234.ts.net')


if __name__ == '__main__':
    unittest.main()
