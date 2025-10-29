from flask import Flask, render_template, request, jsonify
import requests
from requests.exceptions import RequestException, SSLError, Timeout, TooManyRedirects
from curl_parser import parse_curl

app = Flask(__name__)

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/run")
def run():
    payload = request.get_json(force=True, silent=True) or {}
    curl_cmd = payload.get("curl", "")
    # Альтернативный режим: прямыми полями (если пригодится)
    direct = payload.get("direct")

    try:
        if curl_cmd:
            spec = parse_curl(curl_cmd)
        elif isinstance(direct, dict):
            spec = {
                "method": direct.get("method", "GET").upper(),
                "url": direct["url"],
                "headers": direct.get("headers") or {},
                "data": direct.get("data"),
                "json": direct.get("json"),
                "auth": tuple(direct["auth"]) if direct.get("auth") else None,
                "verify": bool(direct.get("verify", True)),
                "timeout": float(direct.get("timeout", 30)),
            }
        else:
            return jsonify({"error": "Нужно передать поле 'curl' или 'direct'"}), 400

        resp = requests.request(
            method=spec["method"],
            url=spec["url"],
            headers=spec["headers"],
            data=spec["data"],
            json=spec["json"],
            auth=spec["auth"],
            verify=spec["verify"],
            timeout=spec["timeout"],
            allow_redirects=True,
        )

        # Пытаемся определить, текст ли это
        content_type = resp.headers.get("Content-Type", "")
        is_textual = any(ct in content_type for ct in ["text/", "json", "xml", "javascript", "yaml"])

        body_text = None
        body_base64 = None
        size_bytes = len(resp.content)

        if is_textual:
            # уважим кодировку, если известна
            resp.encoding = resp.encoding or "utf-8"
            body_text = resp.text
        else:
            # бинарь в base64 не возвращаем, чтоб не раздуть ответ — покажем заметку
            body_text = f"[binary content: {size_bytes} bytes, Content-Type: {content_type}]"

        return jsonify({
            "request": {
                "method": spec["method"],
                "url": resp.request.url,
                "headers": dict(resp.request.headers),
                "has_body": bool(spec["data"] or spec["json"]),
            },
            "response": {
                "status": resp.status_code,
                "reason": resp.reason,
                "url": resp.url,
                "elapsed_ms": int(resp.elapsed.total_seconds() * 1000),
                "headers": dict(resp.headers),
                "cookies": resp.cookies.get_dict(),
                "size_bytes": size_bytes,
                "body": body_text,
            }
        }), 200

    except (ValueError,) as e:
        return jsonify({"error": str(e)}), 400
    except SSLError as e:
        return jsonify({"error": f"SSL error: {e}"}), 502
    except Timeout:
        return jsonify({"error": "Timeout"}), 504
    except TooManyRedirects:
        return jsonify({"error": "Too many redirects"}), 508
    except RequestException as e:
        return jsonify({"error": f"Request error: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Internal error: {e}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7700, debug=True)
