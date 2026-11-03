"""Unit tests for scoring + full-pipeline classification. No AWS."""
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.scanner_lib import classify, run_all  # noqa: E402
from common.scanner_lib.checks import Finding  # noqa: E402
from common.scanner_lib.eicar import EICAR_SIGNATURE  # noqa: E402


def test_empty_findings_is_clean():
    v = classify([])
    assert v.verdict == "clean"
    assert v.risk_score == 0
    assert not v.quarantine


def test_suspicious_band():
    v = classify([Finding(30, "x")])
    assert v.verdict == "suspicious"
    assert v.quarantine


def test_malicious_band():
    v = classify([Finding(80, "x")])
    assert v.verdict == "malicious"
    assert v.quarantine


def test_score_caps_at_100():
    v = classify([Finding(70, "a"), Finding(70, "b")])
    assert v.risk_score == 100


def test_reasons_preserved_in_order():
    v = classify([Finding(10, "first"), Finding(25, "second")])
    assert v.reasons == ["first", "second"]


# --- full pipeline against sample-like inputs ------------------------------

def test_clean_pdf_pipeline():
    data = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"
    v = classify(run_all("clean.pdf", data))
    assert v.verdict == "clean"


def test_eicar_pipeline_malicious():
    v = classify(run_all("eicar.txt", EICAR_SIGNATURE))
    assert v.verdict == "malicious"


def test_disguised_exe_pipeline_malicious():
    data = b"MZ" + b"\x90\x00" * 32
    v = classify(run_all("invoice.pdf.exe", data))
    assert v.verdict == "malicious"


def test_macro_doc_pipeline_quarantined():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/vbaProject.bin", b"\x00macro")
    v = classify(run_all("report.docx", buf.getvalue()))
    assert v.quarantine
