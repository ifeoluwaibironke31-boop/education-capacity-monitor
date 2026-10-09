import json
from pathlib import Path
from datetime import datetime, timezone
import requests
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "dnemis" / "2024_2025"
RAW_DIR.mkdir(parents=True, exist_ok=True)
DNEMIS_FILES = {
    "dx.parquet": "https://emis.education.gov.ng/portal/data/census/dx/7ee767038ec62a0374c14189ad8d32b3/dx.parquet",
    "ou.parquet": "https://emis.education.gov.ng/portal/data/census/ou/58331b859583c87ea49c3a0dad9499bc/ou.parquet",
    "pe.parquet": "https://emis.education.gov.ng/portal/data/census/pe/9cfd8dc4165763c0334362174a98faa9/pe.parquet",
    "constants.parquet": "https://emis.education.gov.ng/portal/data/census/constants/ece25d79995506f36891ed868e4ed923/constants.parquet",
    "fact_typeown.parquet": "https://emis.education.gov.ng/portal/data/census/fact_typeown/c1822fcb8efc2a56c33b70ca1e013b7d/fact_typeown.parquet",
    "fact.parquet": "https://emis.education.gov.ng/portal/data/census/fact/c7b39c9c32ba5e0dce5e0e9f2a288c79/fact.parquet",
}
def download_parquet(name: str, url: str) -> dict:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    content = response.content
    if content[:4] != b"PAR1":
        raise ValueError(
            f"{name} is not a valid Parquet file. "
            f"Received content type: {response.headers.get('content-type')}"
        )
    output_path = RAW_DIR / name
    output_path.write_bytes(content)
    return {
        "file_name": name,
        "url": url,
        "bytes": len(content),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "path": str(output_path),
    }
def main():
    results = []
    for name, url in DNEMIS_FILES.items():
        print(f"Downloading {name}...")

        metadata = download_parquet(
            name=name,
            url=url,
        )
        results.append(metadata)
        print(
            f"Saved {name} "
            f"({metadata['bytes']:,} bytes)"
        )
    print("\nDownload complete.")
    metadata_path = RAW_DIR / "ingestion_metadata.json"
    metadata_path.write_text(
        json.dumps(
            results,
            indent=2
        ),
        encoding="utf-8",
    )
    print(
        f"Metadata written to: {metadata_path}"
    )
    return results
if __name__ == "__main__":
    main()