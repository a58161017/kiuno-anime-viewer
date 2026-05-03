"""CLI dispatcher for the anime database pipeline + viewer."""
from __future__ import annotations
import argparse
import sys

# When invoked under PowerShell with redirected stdout (e.g. Bash run_in_background),
# Python buffers stdout in 4KB blocks → progress prints are invisible until done.
# Force line buffering so background runs show real-time progress.
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass


def cmd_parse(args):
    from pipeline.parse import run as parse_run
    parse_run(input_path=args.input, append=args.append)


def cmd_match(args):
    from pipeline.match import run as match_run
    match_run(retry_unresolved=args.retry_unresolved, only_new=args.only_new)


def cmd_enrich(args):
    from pipeline.enrich import run as enrich_run
    enrich_run(source=args.source, force=args.force, only_new=args.only_new)


def cmd_download(args):
    from pipeline.download import run as download_run
    download_run(retry_failed=args.retry_failed)


def cmd_graph(args):
    from pipeline.graph import run as graph_run
    graph_run()


def cmd_serve(args):
    import http.server
    import socketserver
    import os
    import json
    from config import ROOT, SERVE_PORT, USER_LISTS

    # 從 ROOT 的「父目錄」起服務，URL 結構與 GitHub Pages 一致：
    # /kiuno-anime-viewer/viewer/index.html
    os.chdir(ROOT.parent)
    project_dir = ROOT.name  # "kiuno-anime-viewer"
    api_paths = ("/api/user_lists", f"/{project_dir}/api/user_lists")

    class Handler(http.server.SimpleHTTPRequestHandler):
        # Persist viewer's recommend list into data/user_lists.json. Accepts both
        # bare and project-prefixed paths so the viewer can call either.
        def do_POST(self):
            if self.path.rstrip("/") in api_paths:
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length) if length > 0 else b""
                try:
                    data = json.loads(body or b"{}")
                    if not isinstance(data, dict):
                        raise ValueError("expected object")
                    # 我的最愛是本機資料，不寫進可分享的 user_lists.json
                    payload = {
                        "version": 1,
                        "recommend": list(data.get("recommend") or []),
                    }
                    USER_LISTS.parent.mkdir(parents=True, exist_ok=True)
                    USER_LISTS.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    self._send_json(200, {"ok": True, "saved": str(USER_LISTS)})
                except Exception as e:
                    self._send_json(400, {"ok": False, "error": str(e)})
                return
            self.send_error(404, "Unknown POST endpoint")

        def _send_json(self, status, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with socketserver.TCPServer(("127.0.0.1", SERVE_PORT), Handler) as httpd:
        base = f"http://127.0.0.1:{SERVE_PORT}/{project_dir}"
        print(f"Serving at {base}/")
        print(f"Graph view: {base}/graph.html")
        print(f"User lists file: {USER_LISTS}  (POST {base}/api/user_lists)")
        print("Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def cmd_add(args):
    from pipeline.add import run as add_run
    add_run(raw_line=args.raw_line)


def cmd_stats(args):
    import json
    from config import ANIME_JSON, ENTRIES_RAW, UNRESOLVED
    raw = _load_json(ENTRIES_RAW, default={"entries": {}})
    anime = _load_json(ANIME_JSON, default={"anime": {}})
    unresolved = _load_json(UNRESOLVED, default={})

    total_raw = len(raw.get("entries", {}))
    total_anime = len(anime.get("anime", {}))
    total_unresolved = len(unresolved) if isinstance(unresolved, dict) else 0

    enriched_anilist = sum(1 for a in anime.get("anime", {}).values() if a.get("enrichment", {}).get("anilist_at"))
    enriched_mal = sum(1 for a in anime.get("anime", {}).values() if a.get("enrichment", {}).get("mal_at"))
    enriched_bangumi = sum(1 for a in anime.get("anime", {}).values() if a.get("enrichment", {}).get("bangumi_at"))
    has_cover = sum(1 for a in anime.get("anime", {}).values() if a.get("cover", {}).get("local"))

    print("=== kiuno-anime-viewer stats ===")
    print(f"raw entries (parsed):     {total_raw}")
    print(f"anime records:            {total_anime}")
    print(f"  enriched (AniList):     {enriched_anilist}")
    print(f"  enriched (MAL):         {enriched_mal}")
    print(f"  enriched (Bangumi):     {enriched_bangumi}")
    print(f"  cover downloaded:       {has_cover}")
    print(f"unresolved:               {total_unresolved}")


def _load_json(path, default):
    import json
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def main(argv=None):
    p = argparse.ArgumentParser(prog="run.py", description="Anime database pipeline + viewer")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("parse", help="Doc raw text -> entries.raw.json")
    sp.add_argument("--input", default=None, help="path to raw anime list (default: raw/anime_list.txt)")
    sp.add_argument("--append", action="store_true", help="append to existing entries.raw.json (SHA-deduped)")
    sp.set_defaults(func=cmd_parse)

    sm = sub.add_parser("match", help="title -> AniList/MAL/Bangumi ids")
    sm.add_argument("--retry-unresolved", action="store_true")
    sm.add_argument("--only-new", action="store_true")
    sm.set_defaults(func=cmd_match)

    se = sub.add_parser("enrich", help="ids -> metadata into anime.json")
    se.add_argument("--source", choices=["all", "anilist", "mal", "bangumi"], default="all")
    se.add_argument("--force", action="store_true", help="ignore TTL and refetch")
    se.add_argument("--only-new", action="store_true")
    se.set_defaults(func=cmd_enrich)

    sd = sub.add_parser("download", help="download cover images")
    sd.add_argument("--retry-failed", action="store_true")
    sd.set_defaults(func=cmd_download)

    sg = sub.add_parser("graph", help="anime.json -> graph.json")
    sg.set_defaults(func=cmd_graph)

    sv = sub.add_parser("serve", help="run local http.server for the viewer")
    sv.set_defaults(func=cmd_serve)

    sa = sub.add_parser("add", help="interactive single-entry add")
    sa.add_argument("raw_line", help='raw line, e.g. "(4.8星)BOCCHI THE ROCK!(12)"')
    sa.set_defaults(func=cmd_add)

    ss = sub.add_parser("stats", help="show pipeline progress")
    ss.set_defaults(func=cmd_stats)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
