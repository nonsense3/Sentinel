"""EICAR anti-virus test signature.

The EICAR string is the industry-standard harmless test pattern. We assemble it
from parts at runtime so this source file itself does not contain the literal
signature (which some scanners would flag).
"""

# Assembled from fragments to avoid embedding the literal signature in source.
_PARTS = [
    r"X5O!P%@AP[4\PZX54(P^)7CC)7}",
    r"$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*",
]

EICAR_SIGNATURE = ("".join(_PARTS)).encode("ascii")

# Known SHA-256 of the canonical 68-byte EICAR test file.
EICAR_SHA256 = "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"


def contains_eicar(data: bytes) -> bool:
    """True if the EICAR test signature appears in the payload."""
    return EICAR_SIGNATURE in data
