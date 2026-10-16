"""Sign leaf binaries, then embedded bundles, then the app."""
from pathlib import Path
import subprocess
import sys

app = Path(sys.argv[1]).resolve()
identity = sys.argv[2]
magic = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
         b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf"}


def sign(path):
    command = ["codesign", "--force", "--sign", identity]
    if identity != "-":
        command += ["--timestamp", "--options", "runtime", "--entitlements", "resources/entitlements.plist"]
    subprocess.run([*command, str(path)], check=True, stdout=subprocess.DEVNULL)


for path in sorted(app.rglob("*"), key=lambda p: len(p.parts), reverse=True):
    if path.is_symlink():
        continue
    if path.is_file():
        with path.open("rb") as stream:
            if stream.read(4) in magic:
                sign(path)
    elif path.suffix in (".framework", ".app", ".bundle"):
        sign(path)
sign(app)
