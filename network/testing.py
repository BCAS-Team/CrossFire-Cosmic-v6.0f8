import re
import time
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional

from core.config import OS_NAME
from core.logger import cprint
from core.progress import ProgressBar

chunksize = str("100MB")


class SpeedTest:
    @staticmethod
    def _download_range(url: str, start: int, end: int) -> int:
        """Download a byte range from the server and return bytes downloaded."""
        req = urllib.request.Request(url)
        req.add_header("Range", f"bytes={start}-{end}")
        downloaded = 0
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                while True:
                    chunk = response.read(10 * 1024 * 1024)  # 10MB chunks
                    if not chunk:
                        break
                    downloaded += len(chunk)
        except:
            pass
        return downloaded

    @staticmethod
    def test_download_speed(url: Optional[str] = None, duration: int = 10, workers: int = 12) -> Dict[str, Any]:
        cprint("Testing internet speed...", "INFO")

        if not url:
                test_urls = [
                    "http://speedtest.tele2.net/500MB.zip",
                    "https://proof.ovh.net/files/1Gb.dat"
                ]
        url = test_urls[1]

        cprint(f"Testing download speed from: {url} with {workers} workers", "INFO")

        # Get total size
        try:
            with urllib.request.urlopen(url) as r:
                total_size = int(r.info().get("Content-Length", 10*1024*1024))
        except:
            total_size = 10*1024*1024

        tracker = ProgressBar(total_size, "Speed Test", "B")
        start_time = time.time()
        total_downloaded = 0

        # Split the file into ranges for each worker
        chunk_size = max(total_size // workers, 1024 * 1024)  # At least 1MB per worker
        futures = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for i in range(workers):
                start_byte = i * chunk_size
                end_byte = min(start_byte + chunk_size - 1, total_size - 1)
                futures.append(executor.submit(SpeedTest._download_range, url, start_byte, end_byte))

            for future in as_completed(futures):
                downloaded = future.result()
                total_downloaded += downloaded
                tracker.update(downloaded)

        elapsed = time.time() - start_time
        download_mbps = (total_downloaded * 8) / elapsed / 1_000_000 if elapsed > 0 else 0

        result = {
            "ok": True,
            "download_mbps": round(download_mbps, 2),
            "downloaded_mb": round(total_downloaded / 1024 / 1024, 2),
            "elapsed_seconds": round(elapsed, 2),
        }
        cprint(f"Speed test complete: {result['download_mbps']} Mbps ({result['downloaded_mb']} MB downloaded)", "SUCCESS")
        print("ChunkSize =",chunksize)
        tracker.finish()
        return result
