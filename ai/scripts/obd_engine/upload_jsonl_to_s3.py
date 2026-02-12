import argparse
import mimetypes
import os
from datetime import datetime

import boto3
from dotenv import load_dotenv


def _load_env() -> None:
    # Try project root .env first
    root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../..", ".env"))
    if os.path.exists(root_env):
        load_dotenv(root_env)
        return

    # Fallback: ai/.env
    ai_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..", ".env"))
    if os.path.exists(ai_env):
        load_dotenv(ai_env)


def _get_s3_client():
    aws_access_key = os.getenv("S3_ACCESS_KEY") or os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("S3_SECRET_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("S3_REGION") or os.getenv("AWS_REGION") or "ap-northeast-2"
    bucket_name = os.getenv("S3_BUCKET_NAME")

    if not all([aws_access_key, aws_secret_key, bucket_name]):
        raise RuntimeError("Missing S3 credentials or S3_BUCKET_NAME in .env")

    return (
        boto3.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region,
        ),
        bucket_name,
    )


def _build_key(prefix: str, dataset_id: str, filename: str) -> str:
    date_tag = datetime.utcnow().strftime("%Y%m%d")
    safe_prefix = prefix.strip("/").replace("\\", "/")
    safe_dataset = dataset_id.strip().replace("\\", "/")
    return f"{safe_prefix}/{safe_dataset}/{date_tag}/{filename}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload JSONL to S3 (OBD real data).")
    parser.add_argument("--file", required=True, help="Path to JSONL file to upload")
    parser.add_argument("--dataset_id", required=True, help="Dataset ID (e.g., real_obd, kaggle_efd)")
    parser.add_argument("--prefix", default="obd/jsonl", help="S3 prefix (default: obd/jsonl)")
    args = parser.parse_args()

    _load_env()
    s3_client, bucket_name = _get_s3_client()

    file_path = args.file
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    filename = os.path.basename(file_path)
    if not filename.lower().endswith(".jsonl"):
        raise ValueError("Only .jsonl files are allowed for upload.")

    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = "application/json"

    key = _build_key(args.prefix, args.dataset_id, filename)
    print(f"Uploading {file_path} -> s3://{bucket_name}/{key}")

    s3_client.upload_file(
        file_path,
        bucket_name,
        key,
        ExtraArgs={"ContentType": content_type},
    )

    print("Upload complete.")


if __name__ == "__main__":
    main()
