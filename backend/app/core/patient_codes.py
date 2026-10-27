"""Patient codes: short, random, unique, and safe to copy by hand onto a patient's card.

Format ``PHC-XXXXXC``: five random characters plus one check character. The alphabet leaves out
characters that are easy to confuse when written or read aloud (0/O, 1/I/L, U/V), so a code copied
from a paper card is less likely to be mistyped. The check character uses the Luhn mod N algorithm,
which catches every single wrong character and most swaps of two neighbouring characters, so a
mistyped code is rejected instead of silently matching a different patient. Luhn mod N needs an
even alphabet size (doubling must map the symbols one-to-one), hence exactly 30 symbols.

The same algorithm runs in the browser (``frontend/src/lib/patientCode.ts``) so a device can give a
patient a code while offline; the server still enforces uniqueness when the record syncs.
"""
import re
import secrets

ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"  # 30 symbols; 0, 1, I, L, O and U are left out
PREFIX = "PHC-"
BODY_LENGTH = 5
PATTERN = re.compile(rf"^{PREFIX}[{ALPHABET}]{{{BODY_LENGTH + 1}}}$")
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}
_N = len(ALPHABET)


def _luhn_sum(chars: str, double_first: bool) -> int:
    """Luhn mod N sum, walking from the rightmost character and doubling every second one."""
    total, double = 0, double_first
    for ch in reversed(chars):
        addend = _INDEX[ch] * (2 if double else 1)
        total += addend // _N + addend % _N
        double = not double
    return total


def check_character(body: str) -> str:
    """The character that makes ``body + check`` pass :func:`is_valid`."""
    return ALPHABET[(_N - _luhn_sum(body, double_first=True) % _N) % _N]


def is_valid(code: str) -> bool:
    """True for a well-formed code whose check character matches."""
    code = code.strip().upper()
    if not PATTERN.match(code):
        return False
    return _luhn_sum(code[len(PREFIX):], double_first=False) % _N == 0


def generate() -> str:
    """A new random code. Uniqueness is checked by the caller against the database."""
    body = "".join(secrets.choice(ALPHABET) for _ in range(BODY_LENGTH))
    return f"{PREFIX}{body}{check_character(body)}"
