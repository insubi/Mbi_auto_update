#!/usr/bin/env python3
from pathlib import Path
import base64, hashlib, json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
retry_path = app / "dungeon" / "ScenarioEngine.AbyssRetry.cs"
timeout_path = app / "dungeon" / "ScenarioEngine.AbyssTimeout.cs"
targets_path = app / "abyss" / "config" / "targets.json"
project_path = app / "FishingAutomation.csproj"
update_path = app / "UpdateManager.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def method_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"method not found: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"method brace not found: {signature}")
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit(f"method end not found: {signature}")

def replace_method(text: str, signature: str, replacement: str) -> str:
    start, end = method_bounds(text, signature)
    return text[:start] + replacement + text[end:]

def inject_after_first_in_method(text: str, signature: str, needle: str, insertion: str) -> str:
    start, end = method_bounds(text, signature)
    block = text[start:end]
    if needle not in block:
        raise SystemExit(f"inject anchor missing in {signature}: {needle}")
    block = block.replace(needle, needle + insertion, 1)
    return text[:start] + block + text[end:]

tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
           {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat", ".jpg", ".png"}]
before = {p.relative_to(root).as_posix(): digest(p) for p in tracked}

# ---------------------------------------------------------------------------
# 1) User-provided tracked-loot icon templates.
#    Small 40x40 JPEGs are derived from the exact screenshots supplied by the user.
#    They are matched multi-scale against the confirmed Abyss result screen.
# ---------------------------------------------------------------------------
loot_templates = {
"abyssstone.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGwAAAgIDAQAAAAAAAAAAAAAAAAUEBgECBwP/xAAzEAACAQMEAQIDAw0AAAAAAAABAgMABBEFBhIhMRNhIoGhFBVRJTIzQUJVcXOCkbHR8P/EABkBAQEAAwEAAAAAAAAAAAAAAAQFAQMGAv/EACcRAAEDAgUDBQEAAAAAAAAAAAEAAgMEERITITGxodHwBSIyYYHx/9oADAMBAAIRAxEAPwDgwGaaQaJM0SyzyRWyt2vqtgn5Vrolus+qRBxlFy5B9hmpc85LNdTguWbxnB/gP9VVp4GluN+qDNMQ7C1YGiRfvC3+tavokeOtQts+5IqwbX2zf7n1CWO2eCK2gUM8zk8fiGUHsTnFK7+0msdRuLedD6Ua8hIAesZBBHsQaVggI25R8UwO/CS3umz2JUyqCjfmupyrfOim9unr2tzat2jxmRAf2WHefaihzUtiCwaFJinuLP3UXbw/KB/lP/ine3dLbU9x2UEXBiY5OayIWXhjs9A4NKNqW017raW8MbOzowPEE8RjyfarLpy6vt22kvYoJoMsYnkkjdOKdYJ66B+hFbM1op8O5/iPmRCrDJHgeHnZdJgtbTZm3LjT2SGVp0hljnTA5xgHAdfxBHv4qg6xt6O60VdavpkAnZxEnqH1OC+SVAwAc/8AYqXpm8k1AvNr9vyaBAfWtvi9QDPTA+D2PrUC/wB7FrOeCCwWG0PdsjsrMc9fF5zgZ68ZOa9S1IMWS1v3+ron0tIBmtk1IVX0VQsXEFyBFKBz84wcUV7WkgM08pURqsLsQPCjGAKKUHtDG308C5pzbyOw6hLdt6uND3Ba3zczHGSJAnkqQQcf3z8qtWobusdU0CPS453txG4Id4eIZR4BwxycnJooqNHo4EhbKn0+GeQTPHuFul7clJQbMjvUoj/Q1at9hzn7xiH4kRtmiiqZqDb4jr3WBAL7np2UO91GBLRrWy5FZP0krjBb2A/UKKKKnSyukNynRxhgsF//2Q==",
"binding10.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGgAAAwADAQAAAAAAAAAAAAAAAAUGAQMEB//EADMQAAIBAwEGAggGAwAAAAAAAAECAwAEBREGEhMhMUEiYRQWUVJxcoGhIyQzQpGxkqLR/8QAFwEAAwEAAAAAAAAAAAAAAAAAAwQFAv/EACgRAAEEAQMCBQUAAAAAAAAAAAEAAgMRBBIhMUFRBRQiYeGRobHB8P/aAAwDAQACEQMRAD8A8FA1pha4W+ukDx2zlD0Y8gf5rdgbWOS5knmTfjt0MhX3j2FOUWe9k35nZie2vIeQFDlm0JCfILDTUq9W8hp+h/uv/a1ybO5FVJFqzfKQT9jVzjNj7vJWvpCcOKHxBWkJ1kKjUhQAST9qWZvGPhIGDqwuEXindbQFCRpoe/7vZzFBbO47rLXZGgSEU09a+VCyRPE5V1KsOoI0IoqiySDIYl7hhrPbMAX7sh9vwNFNMfqCYjl1jfkLGBX8lffIv91V7NW8UmUtlliEyM4BQnTWpTZwGaC+jTTe4QbmdOQOpNMIbvIxS2klqxttSJUk8J3xrp38wQRpy71OyozJbbpTZ8Z+Q57Wmq59tvg/RelJksf6bcWsZthaW0m42ruEBDhgN9eQ8Q5jQ9POo7bnJw36vJFKGR1dA5BHFdn6qDzCgdPjVT64WdjsocfbWUbXsxPi3QAznqx8u9QWSVY7eSSSTjXUxClz8egHYUlDKT6dO2w35NIkHiE0sTMdzabsL6kDv7fw6lcjw8LE3yd+Guv+VFZuJN7G5Fu24o+u9RVaG6RMeyCT3/QWjYrMW+Nub6G6lihS5tiqPIoIDggga6HTUaj2dKqc/krPLW9jHh+AyQ7zyKjLqpPIDXv3P90UVuYCrSOZiRtyPMi9X24r8JS1veuB+EVZehDDlXPPZ3jyGSQqgPvSBVH0oopJoAPCGzJeBpHCU5W+gis/QraUTFm35ZB0JHQDyoooqmxoAVyJga1f/9k=",
"binding10plus.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGwAAAgIDAQAAAAAAAAAAAAAAAAYEBQIDBwH/xAAwEAABAwQABAMFCQAAAAAAAAABAgMEAAURIQYSMUEUUXFSYXKRsSMkJTRikqGy0f/EABkBAAIDAQAAAAAAAAAAAAAAAAQFAQIDAP/EACoRAAIBAwIEBAcAAAAAAAAAAAECAwAEESExBRIiQRNRYfBCcaGxwdHh/9oADAMBAAIRAxEAPwDgyUlRAAJJ7CrVqwSOQKfWzGyMgOLwflXthaCXnpRSFGO2VJB9roKnssKdWVrJUo7JPenFtahwGYZzS24uCpIGmKiixDH56L+4/wCVgqwLVpuXFWr2QvH1FMMWzuynG220ZLiwgepOBVreLTbrHbZkXmEyUXlNBxLaSg/ZgghRyQASTkYJ9K3uIoYGWNl6m2GtYwSTTK0inpXc9hnaubSob0N4tPtlCh2PeiruWgybK6lw8y4qgpBPXlOiKKXzweG2mxo6GXnXXesLIPuU74E/WmfhqAxMnsolSFxWFKCC6hHMRnWqXOGY7kxqe02lWmecqCSoAA57d6erFIgWqxxnXLSuVdSpTqAoOICgDgoOCMkDm15E+dFtc+Fbjk32+poArHJcGOQ+8U5RTbYTknh6M0t0gY8SUAneME42ACfkM9KSuI7bETF8XAcAjJWWi2VDmKxoq5euD2J3TjxLf7xHbj3WHEbityIyW3VONJXyKVk7VpRSkaA6YzXMLlcfFPuvHCQtRIAGAB21U8MczTNNNqcd9cH08v561PEIRAght2wpOSBkA+p88edVroAt1w+BP9qK1uOfhU9ZOilCR681FdeMMr8vya0tgcH32FaeFL+iySZaX1vJYlMFolvZSrIKTjI949DTJfOKot/bhJjS0xPDZUUqBQCrQGN9AB/NFFAQAc4yM1S44fC0wuviH6x9qjzbvJuMdtqVe23kISEhKnNa6ZGNn3mqt0R8ZcuUcJ/TlRoopwzBE6VAqgUu3UTVZc7i05HTEiBQYSrmUpXVxXnRRRSWWRpGyaaRoEGBX//Z",
"boots.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGgAAAgMBAQAAAAAAAAAAAAAAAAUDBAYBB//EADAQAAIBAwMBBQYHAQAAAAAAAAECAwAEBRESITETFUFhgQYUIlGhwRYyNGNxkZKx/8QAGgEAAQUBAAAAAAAAAAAAAAAAAgEDBAUGAP/EACURAAEDBAAFBQAAAAAAAAAAAAEAAgMEESExBRITQYEicbHB8P/aAAwDAQACEQMRAD8A8HVNxpla4W9uk3xWk0i/MIdKuez1nEWnvJ4xIlsoYIejMToNabzT3jwPcSGabbzsj1AH9dBV7TUTSzqSHG/CNrL7Sb8N5HT9DP8A4qCfAZCJCzWU4UeOw0x76kTmSA7AD+SUltfXii0zNy14m2OSHceD2mv08aK1C+wa7Jx+wi5As1JEUOhGlFajPwLfWC5ERhJ0fspto0DccNRUGopjE/lGk25tirOGjTuS72HXV49ad2iXCW7e5zdhO6lFfaG68cg1n8FIO5LzyeM+lXJc+tkhSIazqAQzabVPn861EM0EdKTMbAtI+cKQy1ksx8cpy3aSIGlhDTFJBwWHgR9Ka3ctxlvaY+9463sZIQ8zxxLp8R0PPPPUUox96FyU000sm9YHZmPB10Gn2pw+f73z7XARYIxAQiA7m04BBPpWdoY4zJTkjJLr+NJRZQX8YGDvR+7H96K5fSa4K9bw7WMf9oqzri3qD2+ymn7SXA5GG2llguSRb3C7GYdVPg3pWnGLtXxyOtsLu638TKVZCnh560UV3C3GRpa7sljN1HeY25vLcp7s0TcfGqrrx4fxVK2wF3aytJsYsw0LuQqqKKKtZKaN7xKR6h3ThF1Rzl9BHaR4+3lE21jJLIvRm6aDyFFFFZOplc+QkqK45X//2Q==",
"coat.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGwAAAgIDAQAAAAAAAAAAAAAAAAUGBwEDBAL/xAAwEAACAQMDAgMGBgMAAAAAAAABAgMABBEFITEGEhNBURUiYXGBkRQjMjRCc5LB0f/EABoBAAMAAwEAAAAAAAAAAAAAAAIEBQABAwb/xAAkEQACAQMCBgMAAAAAAAAAAAABAgADBBESExQhMWFxoUGRwf/aAAwDAQACEQMRAD8Ao2CB5pFRFLMxwABkmpDa9Mun72aCAkbIz+99ccUdOxeDb3d6o/MiUJGfQseftTCO38KBp3DOfIDcsxOAPmSa9LZWSFdx/PYCdEX5M4j04gO1/af5H/lan6aZ8iG8tJH8lDkE/cVatzptl0/01JNcaPDcNDChnUsC5dtjhiMgAny9KrmHwtRszNGACCVZeSpoqAtrpjTReY9zF0vnAkVvbKaznaGeMxuvINFSPVYjdaEJJD3S2sgQMeSjcD70VNubXbfA6QGXBnvQwPYl3/ZHT3qPquxvemtP6fttJhtJLRu+a6U5ediNhxtufXyHFR3Q5QdGvlHKsjn5ZxTC+vBcaSolWN2iwI2KDuA9O7Gcc7ZqpWQ1bIBDjAyfAzkRhOmBLA60ktbzoGIRXcMrI0LgrIGLYHaeDvzVZWF7DaSurZZZQFJAxg55NceFMkZ7FBQHswMduecU30i8itYZx+FtJJjxJNCJCqn0zsN/PBqLYM/ELtYDDmM+x9ZmqK6VJExfqBol7/ZH/uitN7KB0/dMTs0yKvxIyTRVq+ddweP0wGPOING1M6fd9xUPE47JEP8AJTT8jTLpcQ6kIkO/ZKpBH14oopG0rErtsAR3goxEyLCw2PtWDb41tnj0WG3iK6kRMM+KR74YeWBjb60UU8wpUxrWmMjtOmoqCBEOs6tHdJHbWqMlrDkqG/UxPLGiiiodaq1R9TRckmf/2Q==",
"devouring.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGgAAAgMBAQAAAAAAAAAAAAAAAAYCBAcFA//EADEQAAEDAwEGAwYHAAAAAAAAAAECAwQABRESBhMhMUFhFCJRByM0kZPhJDJCUoHR8P/EABkBAAMBAQEAAAAAAAAAAAAAAAQFBgIDAf/EACcRAAEEAQEGBwAAAAAAAAAAAAEAAgMRIQQSIkGxwfATFCMxUXGh/9oADAMBAAIRAxEAPwDJm7XCie7f3kl/9SW1aUpPpnrVpMOAR8E59X7V5FuRugY4St5SgTq9M8Tjr96eth/Zu3tK1LkeOmBtoZWUnSVuHgkD0AGSR14CqZvhRnZLR+dUicXuaZC7CSHIcDrBd/h37VzZ9qaTGVKhrUptJwtCx5kf2K6lxtszZt2XbfEofkNuKKSkZJ7HPD/c6hbg480sPhIW6wsOBPAA4zWHCKfcAz9VS6AyQ7xOOaVzwoqbgwaKQkUU2BtO1gtib5tPbresFLS9SlKGMkDmB3x061rsi/I2RiM2vZuCr8Q0hxxspIBcOQSCeQ4D51m8ixrtNkTeG5LKVpdC2Du1jIJ8oGeXLIJ6c6pwdsL5Bu5uQUl+RnV7xAKQe2COHbFUEckcjjJRPD24hTkOoZqI/TOASPjKaLlZIV22aVNUzi4St4tx5Sg2GiE5CUj9oAJOaz+0NKZZSheNW6WTjuDVyRtPd7jKmrnq1om5L2E6SRnOkHmEk4yBVNl0tMSZSsBDbZSn01HgAK2zYEhkAruyUU+ywMvvgll7nRUVnJoqecbKcNFBMS9sJcqN4aVHjLYK95obSUeb5n1PCvNN6i4+AT9VVFFFQ6iSMU3kEH5OFuGilFd6jcxb0E93VGufOuj81KUK0ttI/K2gYSKKK8l1MjxRPRdY4GNNgKjRRRQiJX//2Q==",
"engrave10.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGgAAAwEBAQEAAAAAAAAAAAAAAAUGAwQHAf/EADIQAAEDAwIDBQYHAQAAAAAAAAECAwQABRESIQYxQRMUUXGBFSIyYXKxFiMlM0JSobL/xAAZAQADAAMAAAAAAAAAAAAAAAADBAUAAQL/xAAmEQABBAECBAcAAAAAAAAAAAABAAIDEQQSMSEiQdFxgZGhseHw/9oADAMBAAIRAxEAPwDwdttTrgQhJUpRwAOZp01w8UAd7lMx1EZ0bqUPMCjh5rQuRKwCpholGeijsD96aw4ZcOpWSTuSetBmm0qbkZBaSAapcn4dY7PX39Onx7JVYOWKOdkXFnUeQWkpB9aq2Lep3Q0P5qCR6nFfLtFjW5UiFEfbmAqILySQkp043T5k9egO1Jx5Rcd0LHM8zHyg8rdzw4XsvP51vfgPaH0YyMpIOQoeINFPpbPa2OQ0vcxlJcQT0BOCKKosk1BOwy628dws7AB3Od9CfvVVw4xGlXRmM+pYb+Jwt41JR1O9TfCUN+e1cG2mnFJSzqUpCNWMbgeZqwi3A2CyQD7CbcnuOFxMmQz7owc6D/Y7ZHTHrSc0eom1MeYn5Bie4A/Xa0+kWke2ZsG3xnChgBae1/dCSgYUBtkZ1HPlUzPhIiEpA5jIJ5kVX8W8QX+HFgXQKVDbWxocaQpKvzlb7JUN/l0GPWoKVPccYR2zmtYSASetJzR0QGil3nxiMiKE8t3Ww6evilskD2fcPoT/ANUVjId/Sbg4TsQhA885oqjC06UfGaaP7oEu4aviLJKkl5tbjElhTKwgjI3BB325iqO78WQ+IkRkrdVEMcH4m9lE432Jxyooo8jAVqbAhklGQRzDr5V8LkVLiulKnLsHCkYTqSs6R8s8qwekW/GV3EqHghsk/wC0UUuIwSsEALrJPt2Se6XRElpEaM2W47Z1e8cqWfE0UUU21oAoJ5jAwUF//9k=",
"engrave10plus.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGwAAAgIDAQAAAAAAAAAAAAAAAAYEBQIDBwH/xAAwEAABAwQABAMFCQAAAAAAAAABAgMEAAURIQYSMUEUUXFSYXKRsSMkJTRikqGy0f/EABkBAAIDAQAAAAAAAAAAAAAAAAQFAQIDAP/EACoRAAIBAwIEBAcAAAAAAAAAAAECAwAEESExBRIiQRNRYfBCcaGxwdHh/9oADAMBAAIRAxEAPwDgyUlRAAJJ7CrVqwSOQKfWzGyMgOLwflXthaCXnpRSFGO2VJB9roKnssKdWVrJUo7JPenFtahwGYZzS24uCpIGmKiixDH56L+4/wCVgqwLVpuXFWr2QvH1FMMWzuynG220ZLiwgepOBVreLTbrHbZkXmEyUXlNBxLaSg/ZgghRyQASTkYJ9K3uIoYGWNl6m2GtYwSTTK0inpXc9hnaubSob0N4tPtlCh2PeiruWgybK6lw8y4qgpBPXlOiKKXzweG2mxo6GXnXXesLIPuU74E/WmfhqAxMnsolSFxWFKCC6hHMRnWqXOGY7kxqe02lWmecqCSoAA57d6erFIgWqxxnXLSuVdSpTqAoOICgDgoOCMkDm15E+dFtc+Fbjk32+poArHJcGOQ+8U5RTbYTknh6M0t0gY8SUAneME42ACfkM9KSuI7bETF8XAcAjJWWi2VDmKxoq5euD2J3TjxLf7xHbj3WHEbityIyW3VONJXyKVk7VpRSkaA6YzXMLlcfFPuvHCQtRIAGAB21U8MczTNNNqcd9cH08v561PEIRAght2wpOSBkA+p88edVroAt1w+BP9qK1uOfhU9ZOilCR681FdeMMr8vya0tgcH32FaeFL+iySZaX1vJYlMFolvZSrIKTjI949DTJfOKot/bhJjS0xPDZUUqBQCrQGN9AB/NFFAQAc4yM1S44fC0wuviH6x9qjzbvJuMdtqVe23kISEhKnNa6ZGNn3mqt0R8ZcuUcJ/TlRoopwzBE6VAqgUu3UTVZc7i05HTEiBQYSrmUpXVxXnRRRSWWRpGyaaRoEGBX//Z",
"gloves.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGgAAAgMBAQAAAAAAAAAAAAAAAAUDBAYCB//EADMQAAEDAwICCAILAAAAAAAAAAECAwQABRESMRMhBhQiQVFhgZFCkwcVFjIzQ1NjcaLB/8QAGQEAAwEBAQAAAAAAAAAAAAAAAwQFAgEG/8QAJxEAAgIBAgUDBQAAAAAAAAAAAQIAAxEEIQUTMUHwEiJRMmFxkcH/2gAMAwEAAhEDEQA/APCW2i4oAAknkAKeMdGZymwtxDbAOwdcCT7VZ6Owyww/cSgKU0kBrPconGfSrjzEhiIm4PNcZlbvCK1L7WrBVtjwFXqdLVXWLbzgefmEVPmUvsxIx+LF+cKic6LTSDw+A6ofCh0E04jvxJEV9xLa0rYRrUhQHpg1Vaj3CbbZNzYtoMKIRxnUvDKM+XInfupu+vRVorFvq6eYmygEysmM5HdU26hSFpOClQwRRWnvLRm2ZMlztPxnA0pfepJ2z60VK1Gl5T4HSAZcGS2LJscsZ/MRT+RHjP8AQ1bUl6S2gP8AGywhLmMJ09oFQOOe/cazdidH1LNAPNKm1emcVGtsXO7lAVo7OkE88aRv71S1JNmjSlN2YgD9mMLuI7hHiwHJspSUiQjKwEhICQkJH9QPWnjNqixfo4uEbiXEoecQ6eLw2Rk7Ado5HIZG55YFI1W112zMwy+GygDWRzCqzcpHVpD8ZClaEr2B+8RtnxNc4vpjQlACYVcD7kncjzuTNsNo4noAsk0fut/7RXdzmMOdFFpSwG3EupCl55rO+3lRRdey8wY+P6YF8ZmZst0ECQrio4jDqdDqPEeI8xWhjNRS4XIk+MoK/UOhf8GiiluH3NkIe0yh7S+A5jHW4vzaoy4jBdDkiZCQR8WrUfYb0UVbvsJT3bwx6RLeroy6y3Dh6urtEqK1DBcUe+iiivJX3NY/qMWJzP/Z",
"hallucination.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGwAAAwACAwAAAAAAAAAAAAAAAAMFBgcBAgT/xAAwEAABAwMCBQEGBwEAAAAAAAABAgMFAAQREjEGIUFRYRMHIjJxodE0RFJicoGisf/EABkBAAIDAQAAAAAAAAAAAAAAAAQGAgMFAf/EACoRAAEEAQEGBQUAAAAAAAAAAAIAAQMEESESEzFBcdEFIrHB4VGBkfDx/9oADAMBAAIRAxEAPwDRdvbuXT6Gmk6lrOAKsIirFg6H7lx1wbhlIwD8zXSCRoRePjktDOEnsScU8NPAttW7OtbgICicBPk1sQxAEe9Ns9lnSyER7sHTG42NWcAXXPymlPRsYCUly6bP6iAofSs3gfZbKzfDFzfsypQUgoZT6WVOL3Vk9EgbY55NYXfIei2GmboF+4DhacCeZHY+fPWox36kxbsW16dl06lmJtt306qTIRq7LQsLS6y58Didj9jRVV1vVDXjStmylxPg5waKqsQsBNs8HVkErmOvJLhPwV9/BP8A2sl4SjRd8RsPLKw2nAUAsDWAcnT+7qPlUThCwVINyScthDbGtWpwIPjfpnc/erl1Z3/DUdbvehbpfuABrUseohQOcp8Ywe4NRtE8tVoYn830+7/1DQXK0F7YmfX4z6Lb9pIOwcUqBswLlplbiUOpGCUHB97Hbqa1vxxACCsbG/8ATduQttReUEBtBWSSEpPccyTvzFcxvtTlIiLUh6walLwkkPugjflhQ647jfrUC64suZgIdlUKuChR0NE4Sgdue39UpV6XiUdhyIcN69vhN9m7RlhYRdv3jlSCv1Im9XjGppBwenvCiluuaYe9dUMBwpbSM9c5+lFO9o8uPT3dKVccM/X2ZToSaehLp11ttLqXmlMrQokAg4O45gggGrchxgmdSwJFl1JYBCS2vJOdyc9eVFFARG4ExMrJacMkm+IfM3NeYSEZj83/AJpbkjGAZ9K6dPZSgkfSiijitnjg34UWrBnmpkhJLvShOhLTLfwNp2H3NFFFZ5mRltE+qMEWFsMv/9k=",
"tricorne.jpg": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAcFBQYFBAcGBgYIBwcICxILCwoKCxYPEA0SGhYbGhkWGRgcICgiHB4mHhgZIzAkJiorLS4tGyIyNTEsNSgsLSz/2wBDAQcICAsJCxULCxUsHRkdLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCz/wAARCAAoACgDASIAAhEBAxEB/8QAGgAAAwADAQAAAAAAAAAAAAAAAAUGAwQHAf/EADIQAAICAQIFAQYDCQAAAAAAAAECAwQABREGEhMhQTEiMlFSYXEUFaElNEJDVJKTsfD/xAAZAQADAQEBAAAAAAAAAAAAAAADBAUCAAb/xAAnEQABBAECAwkAAAAAAAAAAAACAAEDEQQSMQUTIRRBQlFxgbHB0f/aAAwDAQACEQMRAD8A4Oqljm3Bp8843jhkcfFVJxlw7RhkmltWV54ay85T5iTsBlJJJdaFLBm6FdvdEZ5Qv07f8cuYuEJixG9XstiFqR/J7X9NN/jOYp9MsRLzNXlVR5KEDOgSULsdh6ov9WzGoaSCOfmkTcb919fT4b4qe7ZimZY7jsynYgtzA/TvjfY8Yx1Ad+lfq3y1CuhXDKXXacVikmowxLE/P05kUezzbbhh8N8MkT4zxHpQXGnWzoafsO729XTHc9ihpdqK7ZtdKKvJHHKqxbsTGVZCB/EDu438c3nbEuhPtolz6SRnLa9xXb17QNO0q3HA0FEbIQgBI27b5aLALOhjACqt/e0yDWyhPx9TV9S1C+torPel6rcu6vWiEgPY+rOQANl7fE5kj1BdSpJqJJjtK/TmX06w9VcHbYnbs31APnHbaPQM3VFSJZPmVdjjbi/hSvw9whotyvdglbUJQehH/LHL5/QYrLwY8J9ZSU/hpn6v8IgA7dXUpbCvw9cZfdMkZH64Z7cIXQLgHoJIx/vDGMytbX5fbpc90n0C9DE81Wy/JFZULz/IwO4P2ygihu1m2MLOvh09pSPvhhhOGSEQb7Lo9luCa1y/u8v9pzCWuSWoGanJMsbhgjg8p28YYZakkM20k6LbpPxLqEKxNUh6Yd5TNKIzuqHwg+2GGGePzJSKZ77ksb26/9k="
}

template_dir = app / "abyss" / "templates" / "loot"
template_dir.mkdir(parents=True, exist_ok=True)
for name, data in loot_templates.items():
    (template_dir / name).write_bytes(base64.b64decode(data))

# ---------------------------------------------------------------------------
# 2) Register image targets for all 11 tracked loot entries plus network OCR.
# ---------------------------------------------------------------------------
targets = json.loads(read(targets_path))
existing_ids = {t.get("Id") for t in targets}

loot_target_defs = [
    ("abyss_loot_hallucination_stone", "hallucination.jpg"),
    ("abyss_loot_devouring_stone", "devouring.jpg"),
    ("abyss_loot_abyss_stone", "abyssstone.jpg"),
    ("abyss_loot_rune_engraving_10", "engrave10.jpg"),
    ("abyss_loot_rune_engraving_10_plus", "engrave10plus.jpg"),
    ("abyss_loot_rune_binding_10", "binding10.jpg"),
    ("abyss_loot_rune_binding_10_plus", "binding10plus.jpg"),
    ("abyss_loot_mor_coat", "coat.jpg"),
    ("abyss_loot_mor_gloves", "gloves.jpg"),
    ("abyss_loot_mor_boots", "boots.jpg"),
    ("abyss_loot_mor_tricorne", "tricorne.jpg"),
]

for target_id, file_name in loot_target_defs:
    if target_id not in existing_ids:
        targets.append({
            "Id": target_id,
            "Kind": "template",
            "Roi": {"X": 0, "Y": 40, "Width": 800, "Height": 900},
            "TemplatePath": f"templates/loot/{file_name}",
            "Threshold": 0.78,
            "TemplateScaleMin": 1.15,
            "TemplateScaleMax": 1.85,
            "TemplateScaleStep": 0.05,
        })
        existing_ids.add(target_id)

if "abyss_network_unstable_title" not in existing_ids:
    targets.append({
        "Id": "abyss_network_unstable_title",
        "Kind": "ocr",
        "Roi": {"X": 120, "Y": 520, "Width": 560, "Height": 300},
        "Text": "네트워크 상태가 불안정합니다",
        "MaxEditDistance": 4,
        "OcrRetryAt2x": True,
    })
    existing_ids.add("abyss_network_unstable_title")

if "abyss_network_retry_text" not in existing_ids:
    targets.append({
        "Id": "abyss_network_retry_text",
        "Kind": "ocr",
        "Roi": {"X": 340, "Y": 820, "Width": 320, "Height": 160},
        "Text": "다시 시도하기",
        "MaxEditDistance": 2,
        "OcrRetryAt2x": True,
    })
    existing_ids.add("abyss_network_retry_text")

write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2))

# ---------------------------------------------------------------------------
# 3) Loot counting: image-template matching first, 2-frame confirmation.
#    OCR remains only as a fallback when no image target is confirmed.
# ---------------------------------------------------------------------------
retry = read(retry_path)

field_anchor = '''    private bool _abyssLootCountedForCurrentResult;
    private static readonly Rectangle AbyssLootCanonicalRoi = new(20, 80, 760, 800);
'''
field_replace = '''    private bool _abyssLootCountedForCurrentResult;
    private static readonly Rectangle AbyssLootCanonicalRoi = new(20, 80, 760, 800);

    // V0173_ABYSS_LOOT_IMAGE_TEMPLATES
    // User-provided item icons are the primary authority. Each hit must survive
    // a fresh-frame confirmation before it can be counted.
    private static readonly (string Target, string Key)[] AbyssLootTemplateTargets =
    {
        ("abyss_loot_hallucination_stone", FishingAutomation.LootStats.HallucinationStone),
        ("abyss_loot_devouring_stone", FishingAutomation.LootStats.DevouringStone),
        ("abyss_loot_abyss_stone", FishingAutomation.LootStats.AbyssStone),
        ("abyss_loot_rune_engraving_10", FishingAutomation.LootStats.RuneEngraving10),
        ("abyss_loot_rune_engraving_10_plus", FishingAutomation.LootStats.RuneEngraving10Plus),
        ("abyss_loot_rune_binding_10", FishingAutomation.LootStats.RuneBinding10),
        ("abyss_loot_rune_binding_10_plus", FishingAutomation.LootStats.RuneBinding10Plus),
        ("abyss_loot_mor_coat", FishingAutomation.LootStats.MorCorsairCoat),
        ("abyss_loot_mor_gloves", FishingAutomation.LootStats.MorCorsairGloves),
        ("abyss_loot_mor_boots", FishingAutomation.LootStats.MorCorsairBoots),
        ("abyss_loot_mor_tricorne", FishingAutomation.LootStats.MorCorsairTricorne),
    };
'''
if retry.count(field_anchor) != 1:
    raise SystemExit("loot field anchor mismatch")
retry = retry.replace(field_anchor, field_replace, 1)

new_detect_loot = r'''    private async Task<HashSet<string>> DetectAbyssLootAsync(Bitmap frame, CancellationToken ct)
    {
        var firstFrame = new List<(string Target, string Key, double Score)>();
        foreach (var item in AbyssLootTemplateTargets)
        {
            var hit = await _detector.DetectAsync(item.Target, frame, ct);
            if (hit.Found)
                firstFrame.Add((item.Target, item.Key, hit.Score));
        }

        var confirmed = new Dictionary<string, double>(StringComparer.Ordinal);
        if (firstFrame.Count > 0)
        {
            await Task.Delay(180, ct);
            using var confirmFrame = await CaptureGameWindowAsync(ct);

            foreach (var item in firstFrame)
            {
                var hit2 = await _detector.DetectAsync(item.Target, confirmFrame, ct);
                if (!hit2.Found)
                    continue;

                double score = Math.Min(item.Score, hit2.Score);
                if (!confirmed.TryGetValue(item.Key, out double oldScore) || score > oldScore)
                    confirmed[item.Key] = score;
            }
        }

        // The normal/+ rune pairs are visually related. If both accidentally cross-match,
        // keep only the stronger 2-frame score inside that pair.
        static void KeepBestPair(Dictionary<string, double> scores, string a, string b)
        {
            if (!scores.TryGetValue(a, out double sa) || !scores.TryGetValue(b, out double sb))
                return;
            if (sa >= sb) scores.Remove(b); else scores.Remove(a);
        }

        KeepBestPair(
            confirmed,
            FishingAutomation.LootStats.RuneEngraving10,
            FishingAutomation.LootStats.RuneEngraving10Plus);
        KeepBestPair(
            confirmed,
            FishingAutomation.LootStats.RuneBinding10,
            FishingAutomation.LootStats.RuneBinding10Plus);

        if (confirmed.Count > 0)
        {
            foreach (var pair in confirmed.OrderByDescending(p => p.Value))
            {
                Log?.Invoke(
                    $"[어비스 전리품] 이미지 2/2 확인: " +
                    $"{FishingAutomation.LootStats.GetDisplayName(pair.Key)} score={pair.Value:0.000}");
            }
            return confirmed.Keys.ToHashSet(StringComparer.Ordinal);
        }

        // OCR is retained only as a fallback so an unexpected scale/theme change does
        // not silently remove all counting. Image matching is always attempted first.
        _abyssLootOcr ??= new OcrRecognizer();
        var roi = ScaleAbyssResultRoi(AbyssLootCanonicalRoi, frame.Size);
        var found = new HashSet<string>(StringComparer.Ordinal);

        foreach (int scale in new[] { 1, 2 })
        {
            var lines = await _abyssLootOcr.ReadLinesAsync(frame, roi, scale, ct);
            foreach (var line in lines)
                ClassifyAbyssLootLine(frame, line, found);
        }

        if (found.Count > 0)
            Log?.Invoke("[어비스 전리품] 이미지 미검출 -> 기존 OCR fallback으로 확인");

        return found;
    }
'''
retry = replace_method(
    retry,
    "    private async Task<HashSet<string>> DetectAbyssLootAsync",
    new_detect_loot)

# Network reconnect must also be visible while waiting on the result/retry screen.
for sig in (
    "    private async Task RetryAbyssResultAsync",
    "    private async Task WaitForAbyssRetryTransitionAsync",
):
    retry = inject_after_first_in_method(
        retry,
        sig,
        "            using var frame = await CaptureGameWindowAsync(ct);",
        "\n            await HandleAbyssNetworkReconnectAsync(frame, ct);")

write(retry_path, retry)

# ---------------------------------------------------------------------------
# 4) Network reconnect handler.
#    Require title + (retry OCR OR fixed green-button evidence), confirm twice,
#    press Space once, prove popup gone, then restart Abyss from step 1.
# ---------------------------------------------------------------------------
engine = read(engine_path)

network_helper_anchor = '''    // V0166_ABYSS_SCENE_SKIP_OUTLINE
'''
network_helper = r'''    // V0173_ABYSS_NETWORK_RECONNECT
    private static double GetAbyssNetworkRetryGreenRatio(Bitmap frame)
    {
        if (frame.Width <= 0 || frame.Height <= 0)
            return 0;

        double sx = frame.Width / 800.0;
        double sy = frame.Height / 1000.0;
        var canonical = new Rectangle(388, 870, 224, 105);
        var roi = Rectangle.Intersect(
            new Rectangle(
                (int)Math.Round(canonical.X * sx),
                (int)Math.Round(canonical.Y * sy),
                Math.Max(1, (int)Math.Round(canonical.Width * sx)),
                Math.Max(1, (int)Math.Round(canonical.Height * sy))),
            new Rectangle(Point.Empty, frame.Size));

        if (roi.Width < 40 || roi.Height < 20)
            return 0;

        int sampled = 0;
        int green = 0;
        for (int y = roi.Top; y < roi.Bottom; y += 2)
        {
            for (int x = roi.Left; x < roi.Right; x += 2)
            {
                sampled++;
                Color p = frame.GetPixel(x, y);
                if (p.G >= 105 && p.G >= p.R + 35 && p.G >= p.B + 12)
                    green++;
            }
        }

        return sampled == 0 ? 0 : (double)green / sampled;
    }

    private async Task HandleAbyssNetworkReconnectAsync(Bitmap frame, CancellationToken ct)
    {
        if (!IsAbyss)
            return;

        var title = await _detector.DetectAsync("abyss_network_unstable_title", frame, ct);
        if (!title.Found)
            return;

        var retryText = await _detector.DetectAsync("abyss_network_retry_text", frame, ct);
        double greenRatio = GetAbyssNetworkRetryGreenRatio(frame);
        if (!retryText.Found && greenRatio < 0.16)
            return;

        Log?.Invoke(
            $"[네트워크 복구] 불안정 팝업 후보 1/2 " +
            $"title={(title.Found ? 1 : 0)} retry={(retryText.Found ? 1 : 0)} green={greenRatio:0.000}");

        await Task.Delay(220, ct);
        using var confirmFrame = await CaptureGameWindowAsync(ct);
        var title2 = await _detector.DetectAsync("abyss_network_unstable_title", confirmFrame, ct);
        var retry2 = await _detector.DetectAsync("abyss_network_retry_text", confirmFrame, ct);
        double green2 = GetAbyssNetworkRetryGreenRatio(confirmFrame);

        if (!title2.Found || (!retry2.Found && green2 < 0.16))
        {
            Log?.Invoke("[네트워크 복구] 2차 확인 실패 -> 입력 취소");
            return;
        }

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke(
            $"[네트워크 복구] 팝업 2/2 확인 -> '다시 시도하기' Space 1회 " +
            $"retry={(retry2.Found ? 1 : 0)} green={green2:0.000}");
        _input.TapScanCode(0x39);

        var wait = Stopwatch.StartNew();
        int goneFrames = 0;
        while (wait.Elapsed < TimeSpan.FromSeconds(20))
        {
            ct.ThrowIfCancellationRequested();
            await Task.Delay(350, ct);
            using var after = await CaptureGameWindowAsync(ct);
            var stillTitle = await _detector.DetectAsync("abyss_network_unstable_title", after, ct);
            var stillRetry = await _detector.DetectAsync("abyss_network_retry_text", after, ct);
            double stillGreen = GetAbyssNetworkRetryGreenRatio(after);

            bool stillOpen =
                stillTitle.Found &&
                (stillRetry.Found || stillGreen >= 0.16);

            if (stillOpen)
            {
                goneFrames = 0;
                continue;
            }

            if (++goneFrames >= 2)
            {
                _abyssCombatStartedAt = null;
                _abyssLootCountedForCurrentResult = false;
                ResetAbyssExitState();
                Log?.Invoke("[네트워크 복구] 팝업 사라짐 2프레임 확인 -> 어비스 처음부터 재시작");
                throw new RestartCycleException();
            }
        }

        throw new TimeoutException(
            "네트워크 오류 팝업에서 다시 시도하기 Space 입력 후 20초 안에 팝업 종료를 확인하지 못했습니다.");
    }

'''
if engine.count(network_helper_anchor) != 1:
    raise SystemExit("network helper insertion anchor mismatch")
engine = engine.replace(network_helper_anchor, network_helper + network_helper_anchor, 1)

# Main/specialized loops that can remain active without CheckMonitorsAsync.
for sig in (
    "    private async Task ExecuteStepAsync",
    "    private async Task<bool> TryAbyssInternalRecoveryAsync",
    "    private async Task<DetectionResult> WaitForAbyssTouchPromptAsync",
    "    private async Task WaitForAbyssClearScreenGoneAsync",
    "    private async Task WaitForAbyssHomeAfterNormalExitAsync",
    "    private async Task ClickTargetWithTimeoutAsync",
    "    private async Task VerifyChallengeBeforeEntryAsync",
):
    engine = inject_after_first_in_method(
        engine,
        sig,
        "            using var frame = await CaptureGameWindowAsync(ct);",
        "\n            await HandleAbyssNetworkReconnectAsync(frame, ct);")

# CheckMonitors may also be reached from other helper loops; network recovery must
# precede the existing result-screen guard.
check_sig = "    private async Task<bool> CheckMonitorsAsync"
start, end = method_bounds(engine, check_sig)
block = engine[start:end]
check_anchor = '''    {
        if (IsAbyss && (await DetectAbyssResultRetryAsync(frame, ct)).Found)
'''
check_replace = '''    {
        await HandleAbyssNetworkReconnectAsync(frame, ct);
        if (IsAbyss && (await DetectAbyssResultRetryAsync(frame, ct)).Found)
'''
if check_anchor not in block:
    raise SystemExit("CheckMonitors network anchor mismatch")
block = block.replace(check_anchor, check_replace, 1)
engine = engine[:start] + block + engine[end:]

write(engine_path, engine)

timeout = read(timeout_path)
for sig in (
    "    private async Task StartAbyssCombatClockAsync",
    "    private async Task ExitAbyssAfterCombatTimeoutAsync",
):
    timeout = inject_after_first_in_method(
        timeout,
        sig,
        "            using var frame = await CaptureGameWindowAsync(ct);",
        "\n            await HandleAbyssNetworkReconnectAsync(frame, ct);")
write(timeout_path, timeout)

# ---------------------------------------------------------------------------
# 5) Version metadata.
# ---------------------------------------------------------------------------
project = read(project_path)
for old, new in (
    ("<Version>0.1.72</Version>", "<Version>0.1.73</Version>"),
    ("<AssemblyVersion>0.1.72.0</AssemblyVersion>", "<AssemblyVersion>0.1.73.0</AssemblyVersion>"),
    ("<FileVersion>0.1.72.0</FileVersion>", "<FileVersion>0.1.73.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.72"' not in update:
    raise SystemExit("UpdateManager V0.1.72 marker missing")
update = update.replace('CurrentVersion = "V0.1.72"', 'CurrentVersion = "V0.1.73"', 1)
write(update_path, update)

# ---------------------------------------------------------------------------
# 6) Verification.
# ---------------------------------------------------------------------------
after_tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
                 {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat", ".jpg", ".png"}]
after = {p.relative_to(root).as_posix(): digest(p) for p in after_tracked}
changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}

allowed = {
    engine_path.relative_to(root).as_posix(),
    retry_path.relative_to(root).as_posix(),
    timeout_path.relative_to(root).as_posix(),
    targets_path.relative_to(root).as_posix(),
    project_path.relative_to(root).as_posix(),
    update_path.relative_to(root).as_posix(),
}
allowed.update(
    (template_dir / name).relative_to(root).as_posix()
    for name in loot_templates
)
unexpected = sorted(changed - allowed)
if unexpected:
    raise SystemExit("unexpected V0.1.73 changes: " + ", ".join(unexpected))

engine_check = read(engine_path)
retry_check = read(retry_path)
timeout_check = read(timeout_path)
targets_check = read(targets_path)

for marker in (
    "V0173_ABYSS_LOOT_IMAGE_TEMPLATES",
    "AbyssLootTemplateTargets",
    "[어비스 전리품] 이미지 2/2 확인:",
    "이미지 미검출 -> 기존 OCR fallback으로 확인",
):
    if marker not in retry_check:
        raise SystemExit(f"loot marker missing: {marker}")

for marker in (
    "V0173_ABYSS_NETWORK_RECONNECT",
    "abyss_network_unstable_title",
    "abyss_network_retry_text",
    "팝업 2/2 확인 -> '다시 시도하기' Space 1회",
    "팝업 사라짐 2프레임 확인 -> 어비스 처음부터 재시작",
):
    if marker not in engine_check:
        raise SystemExit(f"network marker missing: {marker}")

for target_id, _ in loot_target_defs:
    if target_id not in targets_check:
        raise SystemExit(f"loot target missing: {target_id}")

for name in loot_templates:
    p = template_dir / name
    if not p.exists() or p.stat().st_size < 500:
        raise SystemExit(f"loot template missing/too small: {name}")

# Existing requested behavior remains intact.
all_runtime = "\n".join(read(p) for p in (app / "dungeon").glob("ScenarioEngine*.cs"))
for marker in (
    "V0172_ABYSS_CLEAR_TITLE_FALLBACK",
    "if (clearTitle.Found && touch.Found)",
    "LootStats.RecordRound",
    "실제 결과 화면 2/2 확인",
):
    if marker not in all_runtime:
        raise SystemExit(f"existing behavior marker missing: {marker}")

for p in app.rglob("*"):
    if p.suffix.lower() in (".cs", ".json"):
        text = read(p)
        if re.search(r"abyss_death|AbyssDeath|DeathTimeout|사망", text):
            raise SystemExit(f"death logic returned: {p}")

scenario = json.loads(read(app / "abyss" / "config" / "scenario.json"))
combat = next(s for s in scenario["Steps"] if s["Target"] == "abyss_touch_screen")
if combat["TimeoutSeconds"] != 600:
    raise SystemExit("Abyss combat timeout is not 600 seconds")

print("PASS V0.1.73: loot image templates + network Space reconnect; V0.1.72 clear fallback preserved")
