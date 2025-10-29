import shlex
import json
from urllib.parse import urlparse

def parse_curl(curl_cmd: str):
    """
    Разбирает популярные опции curl (без запуска shell).
    Поддержка:
      -X / --request METHOD
      -H / --header "Name: value"
      -d / --data / --data-raw / --data-binary / --data-urlencode
      --json '{...}'
      --form / -F name=value или name=@file (файлы не поддерживаем намеренно)
      -u / --user user:pass (Basic)
      -k / --insecure (verify=False)
      --compressed (игнорируем — requests сам справляется)
      --url URL  (редко, но бывает)
      --max-time SEC (timeout)
      -I / --head  -> METHOD=HEAD (если не задано -X)
    """
    if curl_cmd.strip().startswith("curl"):
        tokens = shlex.split(curl_cmd, posix=True)
        tokens = tokens[1:]  # drop 'curl'
    else:
        tokens = shlex.split(curl_cmd, posix=True)

    method = None
    url = None
    headers = {}
    data = None
    json_payload = None
    files = None
    auth = None
    verify = True
    timeout = 30
    use_head = False

    it = iter(range(len(tokens)))
    i = 0
    while i < len(tokens):
        t = tokens[i]

        def take_next():
            nonlocal i
            i += 1
            if i >= len(tokens):
                raise ValueError(f"Ожидался аргумент после {t}")
            return tokens[i]

        if t in ("-X", "--request"):
            method = take_next().upper()
        elif t in ("-H", "--header"):
            h = take_next()
            if ":" not in h:
                raise ValueError(f"Некорректный заголовок: {h}")
            name, val = h.split(":", 1)
            headers[name.strip()] = val.strip()
        elif t in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode"):
            d = take_next()
            data = d if data is None else (str(data) + "&" + d)
            if method is None:
                method = "POST"
        elif t == "--json":
            js = take_next()
            json_payload = json.loads(js)
            if method is None:
                method = "POST"
            headers.setdefault("Content-Type", "application/json")
        elif t in ("-F", "--form"):
            f = take_next()
            # безопасно: файлы через @ не разрешаем
            if "@" in f or "@".encode() in f.encode():
                raise ValueError("Загрузка файлов через -F не поддерживается в этой версии.")
            # простой multipart симулируем как form-encoded
            data = f if data is None else (str(data) + "&" + f)
            if method is None:
                method = "POST"
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif t in ("-u", "--user"):
            up = take_next()
            if ":" in up:
                user, pwd = up.split(":", 1)
            else:
                user, pwd = up, ""
            auth = (user, pwd)
        elif t in ("-k", "--insecure"):
            verify = False
        elif t == "--compressed":
            pass
        elif t == "--url":
            url = take_next()
        elif t in ("-I", "--head"):
            use_head = True
            if method is None:
                method = "HEAD"
        elif t == "--max-time":
            timeout = float(take_next())
        elif t.startswith("-"):
            # игнор нерелевантных ключей, чтоб не падать
            # можно расширять по мере нужды
            # если у ключа параметр (например --proto-default http), аккуратно съедим его
            if i + 1 < len(tokens) and not tokens[i+1].startswith("-"):
                _ = tokens[i+1]
                i += 1
        else:
            # предполагаем это URL, если похоже
            if url is None and (t.startswith("http://") or t.startswith("https://") or urlparse(t).scheme):
                url = t
            else:
                # если сюда попали — вероятно хвостовые аргументы
                pass

        i += 1

    if url is None:
        raise ValueError("Не найден URL в команде curl")

    if use_head and method is None:
        method = "HEAD"

    if method is None:
        method = "GET"

    # Нельзя выставлять эти служебные — requests сам выставит корректно
    for h in ["Host", "Content-Length", "Transfer-Encoding"]:
        headers.pop(h, None)

    return {
        "method": method,
        "url": url,
        "headers": headers,
        "data": data,
        "json": json_payload,
        "auth": auth,
        "verify": verify,
        "timeout": timeout,
    }
