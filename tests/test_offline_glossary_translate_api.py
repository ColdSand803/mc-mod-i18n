from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen
from zipfile import ZipFile

from http.server import ThreadingHTTPServer

from mc_mod_i18n.web import make_handler, write_user_glossary


def write_lang_jar(path: Path) -> None:
    with ZipFile(path, "w") as zf:
        zf.writestr("assets/example/lang/en_us.json", '{"item.example.copper": "Copper Ingot"}')


def multipart_body(fields: dict[str, str], files: dict[str, tuple[str, bytes]]) -> tuple[bytes, str]:
    boundary = "----mc-mod-i18n-test-boundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    for name, (filename, data) in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"),
                b"Content-Type: application/java-archive\r\n\r\n",
                data,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class OfflineGlossaryTranslateApiTest(unittest.TestCase):
    def test_saved_offline_glossary_translate_job_reaches_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            jar_path = workdir / "example.jar"
            write_lang_jar(jar_path)
            write_user_glossary(workdir, {"Copper": "铜", "Ingot": "锭"})

            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                body, content_type = multipart_body(
                    {
                        "provider": "glossary",
                        "source_locale": "en_us",
                        "target_locale": "zh_cn",
                        "pack_format": "15",
                    },
                    {"jars": ("example.jar", jar_path.read_bytes())},
                )
                request = Request(
                    f"{base_url}/api/translate",
                    data=body,
                    headers={"Content-Type": content_type, "Content-Length": str(len(body))},
                    method="POST",
                )
                with urlopen(request) as response:
                    create_payload = json.loads(response.read().decode("utf-8"))

                progress_payload: dict[str, object] = {}
                for _ in range(80):
                    with urlopen(f"{base_url}/api/progress/{create_payload['job_id']}") as response:
                        progress_payload = json.loads(response.read().decode("utf-8"))
                    if progress_payload.get("status") in {"done", "error"}:
                        break
                    time.sleep(0.05)

                self.assertEqual("done", progress_payload.get("status"), progress_payload.get("error"))
                result = progress_payload["result"]
                self.assertEqual(1, result["processed_jars"])
                self.assertEqual(1, result["generated_files"])
                self.assertEqual({"translated": 1}, result["summary"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
