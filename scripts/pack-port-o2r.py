#!/usr/bin/env python3
"""pack-port-o2r.py — (re)build oracle/shiphome/lighthouse.o2r, the bundled
ROM-independent port archive, from the pinned vendor tree.

    scripts/pack-port-o2r.py           rebuild it (previous copy kept as .prev)
    scripts/pack-port-o2r.py --check   exit 1 if it does not match vendor/

WHY (D41). Every iOS/visionOS build bundles this archive read-only, and it
carries LUS's shader TEMPLATES (shaders/metal/default.shader.metal), not just
the port's textures. The 1.2.2 bump changed those templates (N64 mipmap LOD:
new DrawUniforms fields, lodFrac, o_mip_lod) while the bundled copy was a host
build from 2026-07-31. A stale template compiles fine for most draws and then
fails on exactly the new combiner input (SHADER_LOD_FRAC -> undeclared
`lodFrac`), so a stale archive is a silent bug, not a build error. The build
scripts run --check so it can never ship stale again.

Contents are exactly upstream's GeneratePortO2R staging (CMakeLists.txt):
`port/` copied whole, then `libultraship/src/fast/shaders` as `shaders/`.
Upstream packs with `torch pack` (a deflated zip of the staging dir); the host
Torch build is broken on this machine (D40: Miniforge/CLT headers vs Xcode
27.1 libc++), so this writes the same zip with Python. Entries are sorted and
timestamps fixed, so the output is reproducible byte for byte.
"""
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor/Lighthouse"
OUT = ROOT / "oracle/shiphome/lighthouse.o2r"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def staging():
    files = {}
    port = VENDOR / "port"
    shaders = VENDOR / "libultraship/src/fast/shaders"
    assert port.is_dir() and shaders.is_dir(), "vendor tree missing — run scripts/bootstrap.sh"
    for base, prefix in ((port, ""), (shaders, "shaders/")):
        for f in sorted(base.rglob("*")):
            if f.is_file() and f.name != ".DS_Store":
                files[prefix + f.relative_to(base).as_posix()] = f.read_bytes()
    assert any(k == "shaders/metal/default.shader.metal" for k in files), "metal shader template missing"
    return files


def check():
    want = staging()
    if not OUT.exists():
        print(f"pack-port-o2r: MISSING {OUT}", file=sys.stderr)
        return 1
    with zipfile.ZipFile(OUT) as z:
        have = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    bad = sorted(k for k in want if have.get(k) != want[k])
    extra = sorted(set(have) - set(want))
    if bad or extra:
        print(f"pack-port-o2r: {OUT.name} is STALE vs vendor/ "
              f"({len(bad)} differ/missing, {len(extra)} extra): {(bad + extra)[:6]}\n"
              f"  rebuild with scripts/pack-port-o2r.py", file=sys.stderr)
        return 1
    print(f"pack-port-o2r: {OUT.name} matches vendor/ ({len(want)} entries)")
    return 0


def build():
    files = staging()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".o2r.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[name])
    if OUT.exists():
        OUT.replace(OUT.with_suffix(".o2r.prev"))
    tmp.replace(OUT)
    print(f"pack-port-o2r: wrote {OUT} ({len(files)} entries, {OUT.stat().st_size} bytes)")
    return check()


if __name__ == "__main__":
    sys.exit(check() if sys.argv[1:] == ["--check"] else build())
