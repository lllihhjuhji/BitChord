import sys
p = "sharedUi/src/jvmSharedMain/kotlin/com/music/bitchord/ui/screens/HomeScreen.kt"
s = open(p, encoding="utf-8").read()
old = """    if (shelves.size < 2) afterFirst(this)
    shelves.forEachIndexed { index, shelf ->
        if (index == 1) afterFirst(this)
"""
new = """    // Shuffle leads the page; the shelves (Recents first) follow it.
    afterFirst(this)
    shelves.forEachIndexed { index, shelf ->
"""
if s.count(old) != 1:
    sys.exit("MISS x%d" % s.count(old))
open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("OK")
