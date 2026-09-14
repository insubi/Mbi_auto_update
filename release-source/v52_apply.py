#!/usr/bin/env python3
from pathlib import Path
import sys, io, tarfile, base64
root = Path(sys.argv[1]).resolve()
parts_dir = Path(__file__).resolve().parent / "v52_parts"
payload = "".join(p.read_text(encoding="ascii") for p in sorted(parts_dir.glob("part*.txt")))
data = base64.b85decode(payload.encode("ascii"))
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
    tf.extractall(root)
(root / "CHANGES_v52_AUTUPDATE.txt").write_text(
    "Mabi_Auto v52\n"
    "- UI click crash protection\n"
    "- Abyss current-step text layout fix\n"
    "- Dungeon selection menu shown only in Abyss mode\n"
    "- Left footer slogan removed\n"
    "- Abyss ready state shows selected dungeon name on the next line\n"
    "- Startup automatic update enabled for future releases\n",
    encoding="utf-8",
)
print("v52 files applied successfully")
