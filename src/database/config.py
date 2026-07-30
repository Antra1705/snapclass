import os
from pathlib import Path

from supabase import create_client, Client


def _load_credentials():
    """Read Supabase credentials from env vars, falling back to the existing
    .streamlit/secrets.toml so both the API and the legacy Streamlit app work."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if url and key:
        return url, key

    secrets_path = Path(__file__).resolve().parents[2] / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        import tomllib

        with open(secrets_path, "rb") as f:
            secrets = tomllib.load(f)
        url = url or secrets.get("SUPABASE_URL")
        key = key or secrets.get("SUPABASE_KEY")

    return url, key


_url, _key = _load_credentials()

if not _url or not _key:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY must be set as environment variables "
        "or in .streamlit/secrets.toml"
    )

supabase: Client = create_client(_url, _key)
