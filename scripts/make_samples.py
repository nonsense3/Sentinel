"""Generate harmless sample files that exercise each detection path.

All samples are synthetic and safe. The EICAR file uses the industry-standard
anti-virus TEST string (not malware); some AV products still quarantine it, which
is expected and noted in the README.

Writes to the samples/ directory at the repo root.
"""
import io
import os
import struct
import zipfile

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")

# EICAR assembled from fragments (see src/common/scanner_lib/eicar.py).
EICAR = (
    r"X5O!P%@AP[4\PZX54(P^)7CC)7}"
    r"$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
).encode("ascii")


def _write(name, data: bytes):
    path = os.path.join(SAMPLES_DIR, name)
    with open(path, "wb") as fh:
        fh.write(data)
    print(f"  wrote {name} ({len(data)} bytes)")
    return path


def clean_pdf() -> bytes:
    # Minimal, valid-enough PDF with no active content.
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )


def malicious_pdf() -> bytes:
    # PDF that declares JavaScript and an OpenAction.
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/OpenAction 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Action/S/JavaScript/JS(app.alert('x');)>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )


def disguised_exe() -> bytes:
    # Windows PE header ("MZ") but named like an invoice PDF.
    return b"MZ" + b"\x90\x00" * 32 + b"This program cannot be run in DOS mode."


def macro_doc() -> bytes:
    # A ZIP (Office container shape) carrying a vbaProject.bin entry.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/vbaProject.bin", b"\x00\x01\x02macro-bytes")
    return buf.getvalue()


def zip_bomb() -> bytes:
    # Highly compressible payload: large but trivially small on disk.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("big.txt", b"0" * (20 * 1024 * 1024))  # 20 MB of zeros
    return buf.getvalue()


def high_entropy() -> bytes:
    # Deterministic pseudo-random bytes -> high Shannon entropy. Represents a
    # packed/encrypted payload. Paired with an executable extension below so it
    # reads as a realistic packed dropper (entropy alone is a weak signal).
    state = 0x12345678
    out = bytearray()
    for _ in range(4096):
        state = (1103515245 * state + 12345) & 0xFFFFFFFF
        out += struct.pack("<I", state)
    return bytes(out)


def crash_me() -> bytes:
    # The scanner raises on filenames starting with "crash-me" to demo DLQ.
    return b"this file makes the scanner raise on purpose"


# (filename, builder, expected_verdict) -- expected drives the demo PASS/FAIL table.
SAMPLES = [
    ("clean.pdf", clean_pdf, "clean"),
    ("eicar.txt", lambda: EICAR, "malicious"),
    ("invoice.pdf.exe", disguised_exe, "malicious"),
    ("report.docx", macro_doc, "suspicious"),
    ("resume.pdf.exe", lambda: b"not really an exe body", "suspicious"),
    ("evil.pdf", malicious_pdf, "malicious"),
    ("archive.zip", zip_bomb, "suspicious"),
    ("packed.scr", high_entropy, "suspicious"),
    ("crash-me.txt", crash_me, "DLQ"),
]


def main():
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    print(f"Generating samples in {os.path.abspath(SAMPLES_DIR)}")
    for name, builder, _expected in SAMPLES:
        _write(name, builder())
    print("Done.")


if __name__ == "__main__":
    main()
