"""Direct test of MinerU API without S3.

Tests MinerU API with a public PDF URL to inspect actual output structure.

Usage:
    MINERU_API_KEY=your-key python -m tests.test_mineru_direct
"""

import asyncio
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

import httpx


async def test_mineru_direct():
    """Test MinerU API with a public PDF URL."""
    api_key = os.getenv("MINERU_API_KEY")

    if not api_key:
        print("❌ MINERU_API_KEY not set")
        print("Usage: MINERU_API_KEY=your-key python -m tests.test_mineru_direct")
        return

    # MinerU API configuration
    api_url = "https://mineru.net/api/v4/extract/task"
    pdf_url = "https://arxiv.org/pdf/1706.03762"  # Attention is All You Need paper

    print("=" * 80)
    print("MinerU API Direct Test")
    print("=" * 80)
    print(f"PDF: {pdf_url}")
    print(f"API: {api_url}")
    print("=" * 80)

    try:
        # Step 1: Submit task
        print("\n[STEP 1] Submitting PDF to MinerU API...")
        print("-" * 80)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "url": pdf_url,
            "is_ocr": True,
            "enable_formula": True,
            "enable_table": True,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)

            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")

            if response.status_code != 200:
                print(f"❌ API returned status {response.status_code}")
                return

            data = response.json()
            print("\nFull response:")
            print(json.dumps(data, indent=2))

            if data.get("code") != 0:
                print(f"❌ API error: {data.get('msg', 'Unknown error')}")
                return

            task_id = data["data"]["task_id"]
            print("\n✅ Task submitted successfully!")
            print(f"Task ID: {task_id}")

        # Step 2: Poll for completion
        print("\n[STEP 2] Polling for task completion...")
        print("-" * 80)

        query_url = f"{api_url}/{task_id}"
        poll_interval = 5  # seconds
        max_wait = 600  # 10 minutes
        retry_count = 0
        max_retries = max_wait // poll_interval

        async with httpx.AsyncClient(timeout=30.0) as client:
            while retry_count < max_retries:
                response = await client.get(query_url, headers=headers)

                if response.status_code != 200:
                    print(f"❌ Status check failed: {response.status_code}")
                    return

                data = response.json()

                if data.get("code") != 0:
                    print(f"❌ API error: {data.get('msg', 'Unknown error')}")
                    return

                state = data["data"]["state"]
                print(f"Poll #{retry_count + 1}: state = {state}")

                if state == "done":
                    print("\n✅ Task completed!")
                    print("Full response:")
                    print(json.dumps(data, indent=2))

                    zip_url = data["data"]["full_zip_url"]
                    print(f"\nZIP URL: {zip_url}")
                    break

                elif state == "failed":
                    err_msg = data["data"].get("err_msg", "Unknown error")
                    print(f"❌ Task failed: {err_msg}")
                    return

                elif state in ["pending", "running", "converting"]:
                    # Show progress if available
                    if "extract_progress" in data["data"]:
                        progress = data["data"]["extract_progress"]
                        extracted = progress.get("extracted_pages", "?")
                        total = progress.get("total_pages", "?")
                        start_time = progress.get("start_time", "?")
                        print(f"  Progress: {extracted}/{total} pages (started: {start_time})")

                    await asyncio.sleep(poll_interval)
                    retry_count += 1

                else:
                    print(f"❌ Unknown state: {state}")
                    return

            if retry_count >= max_retries:
                print(f"❌ Timeout waiting for task completion ({max_wait}s)")
                return

        # Step 3: Download ZIP
        print("\n[STEP 3] Downloading result ZIP...")
        print("-" * 80)

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(zip_url)

            if response.status_code != 200:
                print(f"❌ Failed to download ZIP: {response.status_code}")
                return

            zip_bytes = response.content
            print(
                f"✅ Downloaded ZIP: {len(zip_bytes):,} bytes "
                f"({len(zip_bytes) / 1024 / 1024:.2f} MB)"
            )

        # Step 4: Inspect ZIP contents
        print("\n[STEP 4] Inspecting ZIP contents...")
        print("-" * 80)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract ZIP
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                print(f"\nZIP contains {len(zf.namelist())} files:\n")

                for name in sorted(zf.namelist()):
                    info = zf.getinfo(name)
                    print(f"  {name:60} {info.file_size:>12,} bytes")

                zf.extractall(temp_dir)

            # Show directory tree
            print("\n\nDirectory structure:")
            print("-" * 80)
            for root, dirs, files in os.walk(temp_dir):
                level = root.replace(temp_dir, "").count(os.sep)
                indent = "  " * level
                folder_name = os.path.basename(root) or "."
                print(f"{indent}{folder_name}/")

                subindent = "  " * (level + 1)
                for file in sorted(files):
                    file_path = os.path.join(root, file)
                    size = os.path.getsize(file_path)
                    print(f"{subindent}{file} ({size:,} bytes)")

            # Read markdown files
            print("\n\n[MARKDOWN FILES]")
            print("=" * 80)
            md_files = list(Path(temp_dir).rglob("*.md"))
            print(f"Found {len(md_files)} markdown file(s)\n")

            for md_file in md_files:
                rel_path = md_file.relative_to(temp_dir)
                print(f"\nFile: {rel_path}")
                print("-" * 80)

                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                print(f"Size: {len(content):,} characters")
                print(f"Lines: {content.count(chr(10)) + 1:,}")
                print("\nFirst 1000 characters:")
                print("~" * 80)
                print(content[:1000])
                if len(content) > 1000:
                    print("\n... (truncated) ...")
                print("~" * 80)

                # Show last 500 characters
                if len(content) > 1500:
                    print("\nLast 500 characters:")
                    print("~" * 80)
                    print(content[-500:])
                    print("~" * 80)

            # Read JSON files
            print("\n\n[JSON FILES]")
            print("=" * 80)
            json_files = list(Path(temp_dir).rglob("*.json"))
            print(f"Found {len(json_files)} JSON file(s)\n")

            for json_file in sorted(json_files):
                rel_path = json_file.relative_to(temp_dir)
                print(f"\nFile: {rel_path}")
                print("-" * 80)

                with open(json_file, "r", encoding="utf-8") as f:
                    content = f.read()

                print(f"Size: {len(content):,} characters")

                try:
                    json_data = json.loads(content)
                    print(f"Structure: {type(json_data)}")

                    if isinstance(json_data, dict):
                        print(f"Keys: {list(json_data.keys())}")
                        print("\nSample (pretty-printed, max 1500 chars):")
                        print("~" * 80)
                        pretty = json.dumps(json_data, indent=2, ensure_ascii=False)
                        print(pretty[:1500])
                        if len(pretty) > 1500:
                            print("\n... (truncated) ...")
                        print("~" * 80)

                    elif isinstance(json_data, list):
                        print(f"Array length: {len(json_data)}")
                        if json_data:
                            print(f"First element type: {type(json_data[0])}")
                            print("\nFirst element (pretty-printed, max 1000 chars):")
                            print("~" * 80)
                            pretty = json.dumps(json_data[0], indent=2, ensure_ascii=False)
                            print(pretty[:1000])
                            if len(pretty) > 1000:
                                print("\n... (truncated) ...")
                            print("~" * 80)

                except json.JSONDecodeError as e:
                    print(f"⚠️ Invalid JSON: {e}")
                    print("Raw content preview:")
                    print(content[:500])

        print("\n" + "=" * 80)
        print("✅ Test completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_mineru_direct())
