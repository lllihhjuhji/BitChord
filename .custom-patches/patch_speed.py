import sys
p = "app/src/main/java/com/music/bitchord/data/SimilarMix.kt"
s = open(p, encoding="utf-8").read()
old = "LastFM.getSimilar(seed.title, seed.artist, 8)"
if s.count(old) != 1:
    sys.exit("MISS x%d" % s.count(old))
s = s.replace(old, "LastFM.getSimilar(seed.title, seed.artist, 4)")
old = "val gate = Semaphore(6)"
if s.count(old) != 1:
    sys.exit("MISS gate x%d" % s.count(old))
s = s.replace(old, "val gate = Semaphore(8)")
open(p, "w", encoding="utf-8").write(s)
print("OK")
