import os, re, sys, json, hashlib, pathlib, urllib.request

MODEL = "claude-sonnet-5-5"
ROOT = pathlib.Path(".")
STATE = ROOT / "tools" / ".i18n_state.json"
STR = re.compile(r'<string\s+name="([^"]+)"([^>]*)>(.*?)</string>', re.S)
PH = re.compile(r'%(?:\d+\$)?[sdfxXc]|%%|\{[^}]+\}|\\n|\\\'|&\w+;')
state = json.loads(STATE.read_text()) if STATE.exists() else {}

def parse(path):
    return {m[1]: m[3] for m in STR.finditer(path.read_text("utf-8"))
            if 'translatable="false"' not in m[2]}

def h(s): return hashlib.md5(s.encode()).hexdigest()

def call(system, user):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + os.environ["GEMINI_API_KEY"]
    req = urllib.request.Request(url,
        data=json.dumps({"systemInstruction": {"parts": [{"text": system}]},
                         "contents": [{"parts": [{"text": user}]}]}).encode(),
        headers={"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))["candidates"][0]["content"]["parts"][0]["text"]

def translate(todo, ref):
    sys_p = ("Android 음악 앱 UI 문자열을 자연스러운 한국어로 번역. "
             "%s %d %1$s {x} \\n \\' &amp; 등 플레이스홀더/이스케이프는 원문 그대로 유지. "
             "아래 existing의 용어를 따를 것. 반드시 {키: 번역} JSON만 출력.")
    for _ in range(3):
        try:
            text = call(sys_p, json.dumps({"existing": ref, "translate": todo}, ensure_ascii=False))
            out = json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip()).strip())
            if all(k in out and sorted(PH.findall(todo[k])) == sorted(PH.findall(out[k])) for k in todo):
                return out
        except Exception as e:
            print("재시도:", e)
    sys.exit("번역 검증 실패: " + ", ".join(todo))

found = False
for ko_path in ROOT.rglob("values-ko/strings.xml"):
    en_path = ko_path.parent.parent / "values" / "strings.xml"
    if not en_path.exists(): continue
    found = True
    en, ko_txt = parse(en_path), ko_path.read_text("utf-8")
    ko = parse(ko_path)
    sk = str(en_path)
    todo = {k: v for k, v in en.items()
            if k not in ko or state.get(sk, {}).get(k, h(v)) != h(v)}
    if todo:
        out = translate(todo, dict(list(ko.items())[:80]))
        for k, v in out.items():
            pat = re.compile(rf'(<string\s+name="{re.escape(k)}"[^>]*>).*?(</string>)', re.S)
            if pat.search(ko_txt):
                ko_txt = pat.sub(lambda m: m[1] + v + m[2], ko_txt, 1)
            else:
                ko_txt = ko_txt.replace("</resources>", f'    <string name="{k}">{v}</string>\n</resources>')
        ko_path.write_text(ko_txt, "utf-8")
        print(f"{ko_path}: {len(todo)}개 번역")
    state[sk] = {k: h(v) for k, v in en.items()}

if not found: print("values-ko/strings.xml 못 찾음")
STATE.write_text(json.dumps(state, indent=1))
