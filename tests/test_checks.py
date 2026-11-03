"""Unit tests for the detection checks. No AWS, no Docker."""
import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.scanner_lib import checks  # noqa: E402
from common.scanner_lib.eicar import EICAR_SIGNATURE, contains_eicar  # noqa: E402


# --- magic bytes vs extension ---------------------------------------------

def test_exe_disguised_as_pdf_scores_high():
    data = b"MZ" + b"\x00" * 64
    findings = checks.check_magic_bytes("invoice.pdf", data)
    assert any(f.points == 70 for f in findings)


def test_png_mislabeled_as_pdf_scores_medium():
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    findings = checks.check_magic_bytes("image.pdf", data)
    assert any(f.points == 25 for f in findings)


def test_real_pdf_with_pdf_extension_is_clean():
    assert checks.check_magic_bytes("doc.pdf", b"%PDF-1.4\n") == []


# --- filename tricks -------------------------------------------------------

def test_double_extension_flagged():
    findings = checks.check_filename("resume.pdf.exe")
    assert any("double extension" in f.reason for f in findings)


def test_dangerous_extension_flagged():
    findings = checks.check_filename("tool.exe")
    assert any(f.points == 20 for f in findings)


def test_rtl_override_flagged():
    findings = checks.check_filename("photo\u202egpj.exe")
    assert any("right-to-left" in f.reason for f in findings)


def test_plain_filename_clean():
    assert checks.check_filename("report.pdf") == []


# --- content patterns ------------------------------------------------------

def test_eicar_detected():
    assert contains_eicar(EICAR_SIGNATURE)
    findings = checks.check_content_patterns(EICAR_SIGNATURE)
    assert any(f.points == 100 for f in findings)


def test_pdf_javascript_flagged():
    data = b"%PDF-1.4\n/OpenAction<</S/JavaScript/JS(x)>>"
    findings = checks.check_content_patterns(data)
    reasons = " ".join(f.reason for f in findings)
    assert "JavaScript" in reasons
    assert "OpenAction" in reasons


def test_encoded_powershell_flagged():
    data = b"powershell.exe -enc ZQBjAGgAbwA="
    findings = checks.check_content_patterns(data)
    assert any("encoded PowerShell" in f.reason for f in findings)


def test_plain_text_no_pattern_hits():
    assert checks.check_content_patterns(b"just some harmless text") == []


# --- entropy ---------------------------------------------------------------

def test_low_entropy_text_not_flagged():
    assert checks.check_entropy(b"a" * 1024) == []


def test_high_entropy_flagged():
    # Pseudo-random bytes -> entropy near 8.
    state = 0x1234
    blob = bytearray()
    for _ in range(2048):
        state = (1103515245 * state + 12345) & 0xFFFFFFFF
        blob += state.to_bytes(4, "little")
    findings = checks.check_entropy(bytes(blob))
    assert any("high entropy" in f.reason for f in findings)


def test_entropy_skips_tiny_files():
    assert checks.check_entropy(b"\x00\xff" * 10) == []


# --- zip inspection --------------------------------------------------------

def _zip_with(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_macro_archive_flagged():
    data = _zip_with({"word/vbaProject.bin": b"\x00macro"})
    findings = checks.check_zip(data)
    assert any("VBA macro" in f.reason for f in findings)


def test_embedded_exe_in_zip_flagged():
    data = _zip_with({"setup.exe": b"MZstuff"})
    findings = checks.check_zip(data)
    assert any("embedded executable" in f.reason for f in findings)


def test_zip_bomb_flagged():
    data = _zip_with({"big.txt": b"0" * (20 * 1024 * 1024)})
    findings = checks.check_zip(data)
    assert any("zip bomb" in f.reason for f in findings)


def test_non_zip_ignored():
    assert checks.check_zip(b"%PDF-1.4") == []
