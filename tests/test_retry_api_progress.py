from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen

from http.server import ThreadingHTTPServer

from mc_mod_i18n.web import make_handler


class RetryApiProgressTest(unittest.TestCase):
    def test_retry_endpoint_creates_pollable_retry_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            original_job_id = "abc123"
            failed_entry = {
                "jar": "example.jar",
                "file": "assets/example/lang/zh_cn.json",
                "key": "item.example.copper",
                "source": "Copper",
                "target": "Copper",
                "status": "api_failed",
                "message": "provider timeout",
                "mod_id": "example",
            }
            initial_jobs = {
                original_job_id: {
                    "status": "done",
                    "kind": "jar",
                    "args": {
                        "provider": "copy",
                        "source_locale": "en_us",
                        "target_locale": "zh_cn",
                        "glossary": None,
                        "api_batch_size": 40,
                        "api_concurrency": 1,
                        "api_timeout": 10,
                        "api_retries": 1,
                    },
                    "result": {
                        "job_id": original_job_id,
                        "kind": "jar",
                        "provider": "copy",
                        "entries": [failed_entry],
                        "summary": {"api_failed": 1, "translated": 0},
                        "api_failure_count": 1,
                        "api_failed_entries": [failed_entry],
                    },
                }
            }
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir, initial_jobs=initial_jobs))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                request = Request(f"{base_url}/api/retry/{original_job_id}", method="POST")
                with urlopen(request) as response:
                    retry_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(retry_payload["ok"])
                retry_job_id = retry_payload["retry_job_id"]
                self.assertNotEqual(original_job_id, retry_job_id)

                progress_payload: dict[str, object] = {}
                for _ in range(50):
                    with urlopen(f"{base_url}/api/progress/{retry_job_id}") as response:
                        progress_payload = json.loads(response.read().decode("utf-8"))
                    if progress_payload.get("status") == "done":
                        break
                    time.sleep(0.05)

                self.assertEqual("done", progress_payload.get("status"))
                self.assertEqual("retry", progress_payload.get("mode"))
                self.assertEqual(1, progress_payload.get("files_total"))
                self.assertEqual(1, progress_payload.get("files_completed"))
                self.assertEqual(1, progress_payload.get("retried"))
                result = progress_payload["result"]
                self.assertEqual(0, result["api_failure_count"])
                self.assertEqual("translated", result["entries"][0]["status"])
                self.assertEqual("Copper", result["entries"][0]["target"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
