# -*- coding: utf-8 -*-
r"""Run the talkpage server like a desktop app: no console window, an icon in the notification area.

  pythonw talkpage_tray.pyw [<root>] [--port 8190] [--name NAME.localhost] [--icon FILE.ico]
                            [--log FILE] [--no-open] [other `talkpage serve` options...]
  pythonw talkpage_tray.pyw <root> ... --install "<shortcut name>"

- Starts `talkpage.py serve <root> ...` (the talkpage.py next to this file) in the background and
  opens the entrance page in the default browser. If the port already answers, it only opens the page.
- Tray icon: left click opens the page; right click > Stop stops the server and quits.
  If the server exits by itself, the icon goes away too.
- --no-open: start without opening the browser (for a logon shortcut).
- --log: where the server output goes (default: discarded).
- --install NAME (Windows): write a Desktop shortcut NAME (opens the page) and a Startup shortcut
  NAME (--no-open, starts at logon) with the same options, then exit.
Needs pystray and Pillow (pip install pystray pillow).
"""
import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
TALKPAGE = os.path.join(HERE, "talkpage.py")


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def ja():
    """Japanese menu: $TALKPAGE_LANG, else the OS language (as talkpage.py does)."""
    lang = os.environ.get("TALKPAGE_LANG", "")
    if lang:
        return lang.startswith("ja")
    try:
        import ctypes
        return ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x11
    except Exception:
        import locale
        return (locale.getlocale()[0] or "").lower().startswith(("ja", "japanese"))


def default_icon():
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 6, 60, 46), radius=10, fill=(40, 110, 200, 255))
    d.polygon([(16, 44), (30, 44), (14, 58)], fill=(40, 110, 200, 255))
    for x in (20, 32, 44):
        d.ellipse((x - 4, 22, x + 4, 30), fill=(255, 255, 255, 255))
    return im


def pythonw():
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return w if os.path.exists(w) else exe


def install(name, argv):
    """Desktop and Startup shortcuts that run this file with the same options."""
    args = [a for a in argv]
    i = args.index("--install")
    del args[i:i + 2]
    args = [a for a in args if a != "--no-open"]
    quote = lambda a: '"%s"' % a if (" " in a or not a) else a
    base = "-I %s %s" % (quote(os.path.abspath(__file__)), " ".join(quote(a) for a in args))
    ps = ("$sh=New-Object -ComObject WScript.Shell;"
          "foreach($p in @(@([Environment]::GetFolderPath('Desktop'),''),"
          "@([Environment]::GetFolderPath('Startup'),' --no-open'))){"
          "$l=$sh.CreateShortcut((Join-Path $p[0] $env:TP_NAME)+'.lnk');"
          "$l.TargetPath=$env:TP_EXE;$l.Arguments=$env:TP_ARGS+$p[1];"
          "$l.WorkingDirectory=$env:TP_DIR;"
          "if($env:TP_ICON){$l.IconLocation=$env:TP_ICON+',0'};$l.Save();"
          "Write-Output ($l.FullName+' -> '+$l.Arguments)}")
    ico = ""
    if "--icon" in args:
        ico = os.path.abspath(args[args.index("--icon") + 1])
    env = dict(os.environ, TP_NAME=name, TP_EXE=pythonw(), TP_ARGS=base, TP_DIR=HERE, TP_ICON=ico)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, check=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog="talkpage_tray")
    ap.add_argument("root", nargs="?", help="folder to serve (omit with --place ...)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("TALKPAGE_PORT", 8190)))
    ap.add_argument("--name", default=os.environ.get("TALKPAGE_NAME", ""))
    ap.add_argument("--icon")
    ap.add_argument("--log")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--install", metavar="NAME")
    a, rest = ap.parse_known_args(argv)
    if a.install:
        install(a.install, argv)
        return
    url = "http://%s/" % a.name if a.name else "http://127.0.0.1:%d/" % a.port

    if listening(a.port):
        if not a.no_open:
            webbrowser.open(url)
        return

    import pystray
    from PIL import Image

    if a.log:
        os.makedirs(os.path.dirname(os.path.abspath(a.log)), exist_ok=True)
        out = open(a.log, "a", encoding="utf-8")
        out.write("\n=== start %s ===\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        out.flush()
    else:
        out = subprocess.DEVNULL
    cmd = [sys.executable, "-I", TALKPAGE, "serve"] + ([a.root] if a.root else []) + ["--port", str(a.port)]
    if a.name:
        cmd += ["--name", a.name]
    proc = subprocess.Popen(cmd + rest, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(100):
        if listening(a.port) or proc.poll() is not None:
            break
        time.sleep(0.1)
    if proc.poll() is not None:
        return
    if not a.no_open:
        webbrowser.open(url)

    def stop(icon, _item=None):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        icon.stop()

    image = Image.open(a.icon) if a.icon else default_icon()
    icon = pystray.Icon("talkpage", image, "talkpage  %s" % url, menu=pystray.Menu(
        pystray.MenuItem("入口を開く" if ja() else "Open", lambda i, it: webbrowser.open(url), default=True),
        pystray.MenuItem("停止" if ja() else "Stop", stop)))

    def watch():
        proc.wait()
        icon.stop()

    threading.Thread(target=watch, daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
