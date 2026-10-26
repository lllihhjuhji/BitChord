#!/usr/bin/env python3
import time, os, re, sys, json, hashlib, pathlib, urllib.request
import xml.etree.ElementTree as ET

MODELS = ["gemini-2.5-flash", "gemini-flash-latest"]
CHUNK = 50
ROOT = pathlib.Path(".")
STATE = ROOT / "tools" / ".i18n_state.json"
STR = re.compile(r'<string\s+name="([^"]+)"([^>]*)>(.*?)</string>', re.S)
PH = re.compile(r'%(?:\d+\$)?[sdfxXc]|%%|\{[^}]+\}|\\n|\\\'|&\w+;')
SKIP = ("/build/", "/node_modules/", "/.git/")
state = json.loads(STATE.read_text()) if STATE.exists() else {}

def parse(path):
    return {m[1]: m[3] for m in STR.finditer(path.read_text("utf-8"))
            if 'translatable="false"' not in m[2]}

def h(s): return hashlib.md5(s.encode()).hexdigest()

def fix(v):
    v = v.strip()
    v = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+);)', '&amp;', v)
    if not v.startswith('"'):
        v = re.sub(r"(?<!\\)'", r"\\'", v)
    return v

def call(system, user):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({"model": "claude-sonnet-5-5", "max_tokens": 8000, "system": system,
                         "messages": [{"role": "user", "content": user}]}).encode(),
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))["content"][0]["text"]

def translate_chunk(todo, ref):
    sys_p = ("Android 음악 앱 UI 문자열을 자연스러운 한국어로 번역. "
             "%s %d %1$s {x} \\n \\' &amp; 등 플레이스홀더/이스케이프는 원문 그대로 유지. "
             "문체는 친근한 해요체(~해요, ~돼요, ~하세요)로 통일하고 간결하게. "
             "Queue, Wi-Fi, Dolby Atmos, YouTube Music, Spotify, Discord, Last.fm, BitChord 같은 고유명사/기술용어는 번역하지 말고 영어 그대로. "
             "아래 existing의 용어와 말투를 그대로 따를 것. 반드시 {키: 번역} JSON만 출력.")
    for attempt in range(6):
        if attempt: time.sleep(min(15 * 2 ** (attempt - 1), 120))
        try:
            text = call(sys_p, json.dumps({"existing": ref, "translate": todo}, ensure_ascii=False))
            out = json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip()).strip())
            out = {k: fix(out[k]) for k in todo}
            if all(sorted(PH.findall(todo[k])) == sorted(PH.findall(out[k])) for k in todo):
                return out
            print("플레이스홀더 불일치, 재시도")
        except Exception as e:
            print("재시도:", type(e).__name__, e if not isinstance(e, KeyError) else "")
    sys.exit("번역 검증 실패: " + ", ".join(todo))

found = False
for ko_path in ROOT.rglob("values-ko/strings.xml"):
    if any(s in "/" + ko_path.as_posix() for s in SKIP): continue
    en_path = ko_path.parent.parent / "values" / "strings.xml"
    if not en_path.exists(): continue
    found = True
    en, ko_txt = parse(en_path), ko_path.read_text("utf-8")
    ko = parse(ko_path)
    sk = str(en_path)
    todo = {k: v for k, v in en.items()
            if k not in ko or state.get(sk, {}).get(k, h(v)) != h(v)}
    if todo:
        ref = dict(list(ko.items())[::4][:200])
        items, out = list(todo.items()), {}
        for i in range(0, len(items), CHUNK):
            out.update(translate_chunk(dict(items[i:i + CHUNK]), ref))
        for k, v in out.items():
            pat = re.compile(rf'(<string\s+name="{re.escape(k)}"[^>]*>).*?(</string>)', re.S)
            if pat.search(ko_txt):
                ko_txt = pat.sub(lambda m: m[1] + v + m[2], ko_txt, 1)
            else:
                ko_txt = ko_txt.replace("</resources>", f'    <string name="{k}">{v}</string>\n</resources>')
        try:
            ET.fromstring(ko_txt.encode("utf-8"))
        except ET.ParseError as e:
            sys.exit(f"XML 깨짐, 저장 안 함: {ko_path} {e}")
        ko_path.write_text(ko_txt, "utf-8")
        print(f"{ko_path}: {len(todo)}개 번역")
    state[sk] = {k: h(v) for k, v in en.items()}

if not found: print("values-ko/strings.xml 못 찾음")
STATE.write_text(json.dumps(state, indent=1))
