#!/usr/bin/env python3
import os, re, sys, json, hashlib, pathlib
import anthropic

MODEL = "claude-sonnet-5-5"
ROOT = pathlib.Path(".")
STATE = ROOT / "tools" / ".i18n_state.json"
STR = re.compile(r'<string\s+name="([^"]+)"([^>]*)>(.*?)</string>', re.S)
PH = re.compile(r'%(?:\d+\$)?[sdfxXc]|%%|\{[^}]+\}|\\n|\\\'|&\w+;')

client = anthropic.Anthropic()
state = json.loads(STATE.read_text()) if STATE.exists() else {}

def parse(path):
    return {m[1]: m[3] for m in STR.finditer(path.read_text("utf-8"))
            if 'translatable="false"' not in m[2]}

def h(s): return hashlib.md5(s.encode()).hexdigest()

def translate(todo, ref):
    sys_p = ("Android 음악 앱 UI 문자열을 자연스러운 한국어로 번역. "
             "%s %d %1$s {x} \\n \\' &amp; 등 플레이스홀더/이스케이프는 원문 그대로 유지. "
             "아래 existing의 용어를 따를 것. 반드시 {키: 번역} JSON만 출력.")
    for _ in range(3):
        msg = client.messages.create(
            model=MODEL, max_tokens=8000, system=sys_p,
            messages=[{"role": "user", "content": json.dumps(
                {"existing": ref, "translate": todo}, ensure_ascii=False)}])
        try:
            out = json.loads(re.sub(r"^```(?:json)?|```$", "", msg.content[0].text.strip()).strip())
            if all(k in out and sorted(PH.findall(todo[k])) == sorted(PH.findall(out[k])) for k in todo):
                return out
        except Exception:
            pass
    sys.exit("번역 검증 실패: " + ", ".join(todo))

for ko_path in ROOT.rglob("values-ko/strings.xml"):
    en_path = ko_path.parent.parent / "values" / "strings.xml"
    if not en_path.exists(): continue
    en, ko_txt = parse(en_path), ko_path.read_text("utf-8")
    ko = parse(ko_path)
    sk = str(en_path)
    todo = {k: v for k, v in en.items()
            if k not in ko or state.get(sk, {}).get(k, h(v)) != h(v)}
    if todo:
        ref = dict(list(ko.items())[:80])
        out = translate(todo, ref)
        for k, v in out.items():
            pat = re.compile(rf'(<string\s+name="{re.escape(k)}"[^>]*>).*?(</string>)', re.S)
            if pat.search(ko_txt):
                ko_txt = pat.sub(lambda m: m[1] + v + m[2], ko_txt, 1)
            else:
                ko_txt = ko_txt.replace("</resources>", f'    <string name="{k}">{v}</string>\n</resources>')
        ko_path.write_text(ko_txt, "utf-8")
        print(f"{ko_path}: {len(todo)}개 번역")
    state[sk] = {k: h(v) for k, v in en.items()}

STATE.write_text(json.dumps(state, indent=1))
