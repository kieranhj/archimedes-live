"""Mirror the live archi.medes.live build with a patched js/emu_input.js.

Builds a static copy of Archimedes Live that can be hosted anywhere (e.g.
GitHub Pages) without an Emscripten toolchain:

  * the frontend, arculator.wasm/.data and nspark come from archi.medes.live;
  * arculator.js is the live one with its --pre-js copy of js/emu_input.js
    replaced by ours (the live build is arculator-wasm feature/js-input,
    whose emu_input.js appears verbatim in arculator.js);
  * the ROMs come from the public Arculator 2.2 download, as the upstream
    Makefile's build/emu target does (off archi.medes.live the frontend
    loads them from emu/roms/).

    python mirror_patched.py --emu-input ../arculator-wasm/js/emu_input.js \\
        --base-ref 30fd8d3 --out <site>/arclive
"""
import argparse
import io
import os
import re
import subprocess
import tarfile
import urllib.request

LIVE = "https://archi.medes.live/"
ARCULATOR_TGZ = "https://b-em.bbcmicro.com/arculator/Arculator_V2.2_Linux.tar.gz"
FILES = [
    "index.html", "style.css", "zlib.js", "riscosunzip.js", "cmos.js", "machine-config.js",
    "editor.js", "ui.js", "emu-interface.js", "fsutil.js", "software-browser.js", "hostfs.js",
    "arculator.data.js", "arculator.data", "arculator.wasm", "System.Fixed.woff2",
    "clickicon.bbc", "images/arclive.png", "images/logo.svg", "images/archive-icon.png",
    "images/archive-icon-lores.png", "nspark/nspark-helper.js", "nspark/nspark-worker.js",
    "nspark/nspark.js", "nspark/nspark.wasm",
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "arclive-mirror"})
    with urllib.request.urlopen(req) as r:
        return r.read()


def lf(b):
    return b.replace(b"\r\n", b"\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emu-input", required=True, help="patched js/emu_input.js")
    ap.add_argument("--base-ref", default="30fd8d3",
                    help="arculator-wasm commit the live arculator.js was built from")
    ap.add_argument("--wasm-repo", default=os.path.join(os.path.dirname(__file__), "..", "arculator-wasm"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="touch", help="cache-busting tag for the patched arculator.js")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    for f in FILES:
        data = get(LIVE + f)
        if f == "index.html":
            # cache-bust our arculator.js so phones don't keep the live one
            data = re.sub(rb'arculator\.js\?[^"]*"', b'arculator.js?' + a.tag.encode() + b'"', data)
        path = os.path.join(a.out, f)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        print(f"{f}: {len(data)}")

    old = lf(subprocess.run(["git", "-C", a.wasm_repo, "show", f"{a.base_ref}:js/emu_input.js"],
                            check=True, capture_output=True).stdout)
    new = lf(open(a.emu_input, "rb").read())
    js = get(LIVE + "arculator.js")
    assert js.count(old) == 1, "live arculator.js does not contain the base emu_input.js"
    js = js.replace(old, new)
    with open(os.path.join(a.out, "arculator.js"), "wb") as fh:
        fh.write(js)
    print(f"arculator.js: patched ({len(old)} -> {len(new)} bytes of emu_input.js)")

    tgz = tarfile.open(fileobj=io.BytesIO(get(ARCULATOR_TGZ)))
    n = 0
    for m in tgz.getmembers():
        parts = m.name.split("/")
        if m.isfile() and "roms" in parts:
            rel = "/".join(parts[parts.index("roms") + 1:])
            if rel.endswith(".txt"):
                continue
            path = os.path.join(a.out, "emu", "roms", rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(tgz.extractfile(m).read())
            n += 1
    print(f"emu/roms: {n} files")


if __name__ == "__main__":
    main()
