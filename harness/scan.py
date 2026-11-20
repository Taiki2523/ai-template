"""Scan repository files for supported credential patterns without printing values."""
import os
from pathlib import Path
import re
import subprocess
import sys

patterns = [rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", rb"gh[pousr]_[A-Za-z0-9]{36,}", rb"AKIA[A-Z0-9]{16}"]
names = subprocess.check_output(["git","ls-files","-co","--exclude-standard","-z"])
for raw in filter(None,names.split(b"\0")):
    path = Path(os.fsdecode(raw))
    if path.is_file() and not path.is_symlink():
        data = path.read_bytes()
        if any(re.search(pattern,data) for pattern in patterns):
            sys.exit("Credential pattern detected")
