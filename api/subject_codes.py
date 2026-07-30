"""Random subject join-code generation (shared by the API and migrations)."""

import secrets

# Crockford base32 (no I, L, O, U): 32 chars -> 5 bits each.
CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LENGTH = 8  # 32^8 = 2^40 ≈ 1.1e12 possible codes


def generate_subject_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
