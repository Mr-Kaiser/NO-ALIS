"""Launch ALIS on loopback only; no debugger and no public listener."""
import argparse
from pathlib import Path
import threading
import webbrowser
import sys


def main():
    parser = argparse.ArgumentParser(description='ALIS v0.4 local station editor')
    parser.add_argument('root', nargs='?', type=Path, help='Path to preset-loadout')
    parser.add_argument('--port',type=int,default=5000)
    parser.add_argument('--no-browser',action='store_true')
    args = parser.parse_args()
    if not 1<=args.port<=65535:
        parser.error('--port must be between 1 and 65535.')
    root = args.root
    if root is None:
        try:
            entered = input('Path to your preset-loadout folder: ').strip().strip('"')
        except (EOFError,KeyboardInterrupt):
            return 1
        if not entered:
            parser.error('A preset-loadout path is required.')
        root = Path(entered)
    try:
        from alis.web import create_app
        from werkzeug.serving import make_server
    except ModuleNotFoundError as exc:
        print(f'Missing dependency: {exc.name}. Run: python -m pip install -r requirements.txt',file=sys.stderr)
        return 1
    try:
        app = create_app(root)
        server = make_server('127.0.0.1',args.port,app,threaded=True)
    except (ValueError,OSError) as exc:
        print(f'Could not start ALIS: {exc}',file=sys.stderr)
        return 1
    url = f'http://127.0.0.1:{server.server_port}'
    print('ALIS // AUTONOMIC LOADOUT INTEGRATION SYSTEM',flush=True)
    print(f'Data: {root.expanduser().resolve()}',flush=True)
    print(f'Open: {url}',flush=True)
    print('Keep this terminal open. Press Ctrl+C to stop ALIS.',flush=True)
    if not args.no_browser:
        timer = threading.Timer(0.3,lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nALIS stopped.')
    finally:
        server.server_close()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
