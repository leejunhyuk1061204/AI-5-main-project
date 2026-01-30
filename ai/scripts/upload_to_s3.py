import boto3
import os
import sys
import argparse
import mimetypes
from dotenv import load_dotenv

# ai/scripts/upload_to_s3.py

def main():
    parser = argparse.ArgumentParser(description="Upload a file to S3 and generate a presigned URL for testing.")
    parser.add_argument("file_path", help="Path to the local file to upload")
    args = parser.parse_args()

    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__)) # ai/scripts
    ai_root_dir = os.path.dirname(script_dir)              # ai
    
    # Load environment variables from ai/.env
    env_path = os.path.join(ai_root_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        # Fallback to root .env
        root_env_path = os.path.dirname(ai_root_dir) # project root
        load_dotenv(os.path.join(root_env_path, ".env"))

    # Try project-specific S3 names first, then fallback to standard AWS names
    aws_access_key = os.getenv("S3_ACCESS_KEY") or os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("S3_SECRET_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("S3_REGION") or os.getenv("AWS_REGION") or "ap-northeast-2"
    bucket_name = os.getenv("S3_BUCKET_NAME")

    if not all([aws_access_key, aws_secret_key, bucket_name]):
        print(f"Error: AWS credentials or S3_BUCKET_NAME not found.")
        print(f"Current values (if any):")
        print(f" - S3_ACCESS_KEY / AWS_ACCESS_KEY_ID: {aws_access_key[:5] if aws_access_key else 'None'}...")
        print(f" - S3_BUCKET_NAME: {bucket_name}")
        print(f"Checked .env at: {env_path}")
        return

    # Initialize S3 Client
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region if aws_region else "ap-northeast-2"
    )

    file_path = args.file_path
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return

    file_name = os.path.basename(file_path)
    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = "application/octet-stream"

    # Upload to a 'test_uploads' folder to keep bucket clean
    object_name = f"test_uploads/{file_name}"

    print(f"Uploading '{file_name}' to s3://{bucket_name}/{object_name}...")

    try:
        s3_client.upload_file(
            file_path, 
            bucket_name, 
            object_name, 
            ExtraArgs={'ContentType': content_type}
        )
        print("✅ Upload Successful.")

        # Generate Presigned URL
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=3600  # 1 hour
        )

        # Determine JSON key based on content type
        json_key = "audioUrl" if content_type and content_type.startswith("audio") else "imageUrl"

        print("\n--- [Insomnia JSON Body] Copy below ---")
        print("{")
        print(f'  "{json_key}": "{url}"')
        print("}")
        print("---------------------------------------\n")

    except Exception as e:
        print(f"❌ Upload Failed: {e}")

if __name__ == "__main__":
    main()
