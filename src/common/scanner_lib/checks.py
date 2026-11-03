"""Detection checks.

Each check is a pure function: it takes the file bytes and/or filename and
returns a list of Finding(points, reason). No AWS, no I/O. This keeps every
check trivially unit-testable.

Point values match the README's "What the scanner checks" table.
"""
from __future__ import annotations

import io
import math
import re
import zipfile
from dataclasses import dataclass
from typing import List

from .eicar import contains_eicar


@dataclass(frozen=True)
class Finding:
    points: int
    reason: str


# --- Magic bytes -----------------------------------------------------------

# Leading signatures mapped to a short type label.
_MAGIC = [
    (b"MZ", "windows-executable"),
    (b"\x7fELF", "elf-executable"),
    (b"%PDF", "pdf"),
    (b"PK\x03\x04", "zip"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF8", "gif"),
    (b"\x1f\x8b", "gzip"),
    (b"ID3", "mp3"),
    (b"%!PS", "postscript"),
]

# Extensions that should line up with a detected type.
_EXT_EXPECTED = {
    "pdf": {"pdf"},
    "png": {"png"},
    "jpg": {"jpeg"},
    "jpeg": {"jpeg"},
    "gif": {"gif"},
    "zip": {"zip"},
    "docx": {"zip"},
    "xlsx": {"zip"},
    "pptx": {"zip"},
    "gz": {"gzip"},
    "mp3": {"mp3"},
}

_EXECUTABLE_TYPES = {"windows-executable", "elf-executable"}

_DANGEROUS_EXTS = {
    "exe", "scr", "bat", "cmd", "com", "pif", "msi", "js", "jse",
    "vbs", "vbe", "wsf", "wsh", "ps1", "jar", "hta", "cpl", "dll",
}

_RTL_OVERRIDE = "\u202e"


def detect_type(data: bytes) -> str | None:
    for sig, label in _MAGIC:
        if data.startswith(sig):
            return label
    return None


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def check_magic_bytes(filename: str, data: bytes) -> List[Finding]:
    """Flag content whose real type contradicts its extension."""
    findings: List[Finding] = []
    detected = detect_type(data)
    ext = _ext(filename)
    if detected is None:
        return findings

    name_lower = filename.lower()
    doc_like = {"pdf", "doc", "docx", "txt", "jpg", "jpeg", "png", "xls", "xlsx"}

    if detected in _EXECUTABLE_TYPES:
        # Real executable whose name carries a disguising document extension
        # anywhere (e.g. invoice.pdf.exe). This is the strongest signal.
        parts = name_lower.split(".")
        disguised = any(p in doc_like for p in parts[:-1])
        if disguised:
            findings.append(
                Finding(70, f"content is {detected} disguised by filename '{filename}'")
            )
            return findings
        # Executable wearing a non-executable extension (e.g. invoice.pdf).
        if ext not in {"exe", "dll", "scr", "com", ""}:
            findings.append(
                Finding(70, f"content is {detected} but extension is '.{ext}'")
            )
            return findings

    expected = _EXT_EXPECTED.get(ext)
    if expected is not None and detected not in expected:
        findings.append(
            Finding(25, f"content is {detected} but extension '.{ext}' expects {sorted(expected)}")
        )
    return findings


def check_filename(filename: str) -> List[Finding]:
    """Flag deceptive filenames: double extensions, dangerous types, RTL tricks."""
    findings: List[Finding] = []
    name = filename
    parts = name.lower().split(".")

    # RTL override character hides the real extension in some UIs.
    if _RTL_OVERRIDE in name:
        findings.append(Finding(40, "filename contains right-to-left override character"))

    ext = parts[-1] if len(parts) > 1 else ""

    # Double extension where an inner part looks like a document and the final
    # part is executable, e.g. resume.pdf.exe
    if len(parts) >= 3:
        inner = parts[-2]
        doc_like = {"pdf", "doc", "docx", "txt", "jpg", "jpeg", "png", "xls", "xlsx"}
        if inner in doc_like and ext in _DANGEROUS_EXTS:
            findings.append(
                Finding(40, f"double extension '.{inner}.{ext}' disguises an executable")
            )

    # A dangerous final extension on its own.
    if ext in _DANGEROUS_EXTS:
        # Avoid double-counting when the double-extension rule already fired hard.
        already = any("double extension" in f.reason for f in findings)
        if not already:
            findings.append(Finding(20, f"dangerous file extension '.{ext}'"))

    return findings


# --- Content patterns ------------------------------------------------------

_PDF_PATTERNS = [
    (re.compile(rb"/JavaScript", re.IGNORECASE), 50, "PDF contains JavaScript"),
    (re.compile(rb"/JS\b", re.IGNORECASE), 40, "PDF contains /JS action"),
    (re.compile(rb"/OpenAction", re.IGNORECASE), 40, "PDF runs an action on open (/OpenAction)"),
    (re.compile(rb"/Launch", re.IGNORECASE), 50, "PDF can launch an external program (/Launch)"),
]

# Base64-encoded PowerShell is a common loader pattern.
_PS_ENCODED = re.compile(rb"powershell(\.exe)?\s+.*-enc(odedcommand)?", re.IGNORECASE)
_PS_DOWNLOAD = re.compile(rb"(DownloadString|Invoke-Expression|IEX)\b", re.IGNORECASE)


def check_content_patterns(data: bytes) -> List[Finding]:
    findings: List[Finding] = []

    if contains_eicar(data):
        findings.append(Finding(100, "EICAR anti-virus test signature detected"))

    head = data[:5]
    if head.startswith(b"%PDF"):
        for pattern, pts, reason in _PDF_PATTERNS:
            if pattern.search(data):
                findings.append(Finding(pts, reason))

    if _PS_ENCODED.search(data):
        findings.append(Finding(60, "encoded PowerShell command detected"))
    if _PS_DOWNLOAD.search(data):
        findings.append(Finding(40, "PowerShell download/exec pattern detected"))

    return findings


# --- Entropy ---------------------------------------------------------------

def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    length = len(data)
    entropy = 0.0
    for c in counts:
        if c:
            p = c / length
            entropy -= p * math.log2(p)
    return entropy


def check_entropy(data: bytes) -> List[Finding]:
    """High entropy suggests packing or encryption. Skip tiny files (noisy)."""
    if len(data) < 256:
        return []
    ent = shannon_entropy(data)
    if ent >= 7.5:
        return [Finding(20, f"high entropy ({ent:.2f}/8.0) suggests packed/encrypted content")]
    return []


# --- ZIP metadata inspection (never extracts) ------------------------------

_ZIP_BOMB_RATIO = 100  # uncompressed:compressed ratio threshold


def check_zip(data: bytes) -> List[Finding]:
    """Inspect archive metadata only. Never extracts content."""
    if not data.startswith(b"PK\x03\x04"):
        return []

    findings: List[Finding] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return [Finding(15, "declared ZIP is malformed")]

    total_compressed = 0
    total_uncompressed = 0
    has_macro = False
    has_nested_archive = False
    has_embedded_exe = False
    has_encrypted = False

    for info in zf.infolist():
        total_compressed += info.compress_size
        total_uncompressed += info.file_size
        lname = info.filename.lower()

        # Office VBA macro project.
        if lname.endswith("vbaproject.bin") or "/vba" in lname:
            has_macro = True
        if lname.endswith((".zip", ".gz", ".7z", ".rar")):
            has_nested_archive = True
        if lname.endswith((".exe", ".dll", ".scr", ".bat", ".cmd", ".js", ".vbs")):
            has_embedded_exe = True
        # bit 0 of the general purpose flag indicates encryption
        if info.flag_bits & 0x1:
            has_encrypted = True

    if total_compressed > 0:
        ratio = total_uncompressed / total_compressed
        if ratio >= _ZIP_BOMB_RATIO and total_uncompressed > 10 * 1024 * 1024:
            findings.append(
                Finding(60, f"possible zip bomb (expands {ratio:.0f}x to {total_uncompressed} bytes)")
            )

    if has_macro:
        findings.append(Finding(50, "archive contains a VBA macro project"))
    if has_embedded_exe:
        findings.append(Finding(50, "archive contains an embedded executable"))
    if has_encrypted:
        findings.append(Finding(25, "archive contains encrypted entries"))
    if has_nested_archive:
        findings.append(Finding(15, "archive contains a nested archive"))

    return findings


# --- Orchestration ---------------------------------------------------------

def run_all(filename: str, data: bytes) -> List[Finding]:
    """Run every check and return the combined findings."""
    findings: List[Finding] = []
    findings += check_magic_bytes(filename, data)
    findings += check_filename(filename)
    findings += check_content_patterns(data)
    findings += check_entropy(data)
    findings += check_zip(data)
    return findings
