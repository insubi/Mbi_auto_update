#!/usr/bin/env python3
from pathlib import Path
import base64, gzip, hashlib, struct, sys

# V0.1.2 verified split payload loader.
base = Path(__file__).resolve().parent

def rebuild_b64(target_name: str, prefix: str, count: int):
    chunks = []
    for i in range(count):
        p = base / f"{prefix}_{i:02d}.part"
        if not p.is_file():
            raise RuntimeError(f"V0.1.2 side-car chunk missing: {p.name}")
        chunks.append(p.read_text(encoding="ascii").strip())
    encoded = "".join(chunks)
    data = base64.b64decode(encoded, validate=True)
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(f"V0.1.2 side-car is not PNG: {target_name}")
    (base / target_name).write_text(encoded, encoding="ascii")
    print(f"V75 REBUILT {target_name}: bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()}")

rebuild_b64("v75_outside_home.b64", "v75_homefix", 3)
rebuild_b64("v75_outside_end.b64", "v75_endfix", 3)
rebuild_b64("v75_outside_k.b64", "v75_kfix", 8)

for name in ("v75_outside_home.b64", "v75_outside_end.b64", "v75_outside_k.b64", "v75_outside_i.b64"):
    p = base / name
    if p.is_file():
        data = base64.b64decode(p.read_text(encoding="ascii").strip(), validate=True)
        extra = ""
        if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 26:
            w, h = struct.unpack(">II", data[16:24])
            extra = f" png={w}x{h} color_type={data[25]}"
        print(f"V75 SIDE-CAR {name}: bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()}{extra}")

parts = []
for i in range(10):
    p = base / f"v75_impl_{i:02d}.b64part"
    if not p.is_file():
        raise RuntimeError(f"V0.1.2 payload part missing: {p.name}")
    parts.append(p.read_text(encoding="ascii").strip())

encoded = "".join(parts)
compressed = base64.b64decode(encoded, validate=True)
compressed_sha = hashlib.sha256(compressed).hexdigest()
if compressed_sha != "f8523c8359731bcdbce63ab739714a888378b873df3ab7742ee093acf55a9157":
    raise RuntimeError(f"V0.1.2 compressed payload SHA mismatch: {compressed_sha}")

source = gzip.decompress(compressed)
source_sha = hashlib.sha256(source).hexdigest()
if source_sha != "ea07d47cc81756d258152fe889419e3719702dd64e575638870e5dc5774cdc36":
    raise RuntimeError(f"V0.1.2 implementation SHA mismatch: {source_sha}")

exec(compile(source.decode("utf-8"), __file__, "exec"))

# The generated C# interpolation needs two backslashes in source so TimeSpan's
# escaped colon survives C# string parsing: hh\\:mm. The implementation payload
# emitted only one, which produces CS1009. Apply the minimal source fix here.
if len(sys.argv) > 1:
    main_form = Path(sys.argv[1]) / "FishingAutomation" / "MainForm.cs"
    if main_form.is_file():
        text = main_form.read_text(encoding="utf-8")
        bad = r"{_autoStopTime:hh\:mm}"
        good = r"{_autoStopTime:hh\\:mm}"
        if bad in text:
            text = text.replace(bad, good, 1)
            main_form.write_text(text, encoding="utf-8")
            print("V75 FIXED MainForm auto-stop TimeSpan format escape")
        elif good not in text:
            raise RuntimeError("V0.1.2 auto-stop TimeSpan format marker not found")
