"""Compare BOM / line endings of working files with HEAD and optionally restore HEAD's convention.
usage: eol_check.py [--fix] <file> ..."""
import subprocess, sys
fix = "--fix" in sys.argv
for f in [a for a in sys.argv[1:] if a != "--fix"]:
    head = subprocess.run(["git", "show", f"HEAD:{f}"], capture_output=True).stdout
    now = open(f, "rb").read()
    hb, nb = head.startswith(b"\xef\xbb\xbf"), now.startswith(b"\xef\xbb\xbf")
    hcr = head.count(b"\r\n"); hlf = head.count(b"\n"); ncr = now.count(b"\r\n"); nlf = now.count(b"\n")
    print(f"{f}: BOM head {hb} now {nb}; CRLF head {hcr}/{hlf} now {ncr}/{nlf}")
    if fix:
        body = now[3:] if nb else now
        body = body.replace(b"\r\n", b"\n")
        if hcr and hcr == hlf: body = body.replace(b"\n", b"\r\n")
        if hb: body = b"\xef\xbb\xbf" + body
        open(f, "wb").write(body)
        print("   restored")
