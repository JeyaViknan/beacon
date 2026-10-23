"""Deterministic zip: sorted entries, fixed timestamps and permissions.

Same inputs -> byte-identical zip -> same ``source_code_hash`` -> Terraform does not redeploy
functions whose code did not change.
"""

import os
import sys
import zipfile
from pathlib import Path

FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def zip_dir(src: Path, dest: Path) -> None:
    files = sorted(p for p in src.rglob("*") if p.is_file())
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(src).as_posix(), date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            zf.writestr(info, path.read_bytes())
    os.replace(tmp, dest)


if __name__ == "__main__":
    zip_dir(Path(sys.argv[1]), Path(sys.argv[2]))
    size_mb = Path(sys.argv[2]).stat().st_size / 1_048_576
    print(f"   {sys.argv[2]} ({size_mb:.1f} MB)")
