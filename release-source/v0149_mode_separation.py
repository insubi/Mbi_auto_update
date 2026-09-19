"""Apply the reviewed mode-separation overlay to exactly restored V0.1.48 source."""
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]).resolve()
overlay=Path(__file__).resolve().parent/'v0149-overlay'
manifest=json.loads((overlay/'manifest.json').read_text())
for name,info in manifest.items():
    target=root/name
    actual=hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
    if actual!=info['before_sha256']:
        raise SystemExit('V0.1.48 source mismatch; no files written: '+name)
    if hashlib.sha256((overlay/name).read_bytes()).hexdigest()!=info['after_sha256']:
        raise SystemExit('Overlay checksum mismatch; no files written: '+name)
for name in manifest:
    target=root/name
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes((overlay/name).read_bytes())
print('Applied 9 reviewed files to V0.1.48; project version unchanged; no release published.')
