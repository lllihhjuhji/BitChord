import sys
p = "sharedUi/src/jvmSharedMain/kotlin/com/music/bitchord/ui/screens/HomeScreen.kt"
s = open(p, encoding="utf-8").read()

def rep(old, new):
    global s
    if s.count(old) != 1:
        sys.exit("MISS x%d: %r" % (s.count(old), old[:70]))
    s = s.replace(old, new)

rep("onOpen: (Int) -> Unit = {},",
    "onOpen: (Int) -> Unit = {},\n    coverPool: List<String> = emptyList(),")

rep("val covers = songs.map { it.thumbnailUrl }",
    '''// Cards always show four random covers from the feed, whatever the mix holds.
        val picks = remember(coverPool.isNotEmpty()) { coverPool.shuffled() }
        val firstCovers = picks.take(4)
        val secondCovers = if (picks.size >= 8) picks.subList(4, 8) else picks.asReversed().take(4)''')

rep("covers = if (mode == 0) covers else emptyList(),", "covers = firstCovers,")
rep("covers = if (mode == 1) covers else emptyList(),", "covers = secondCovers,")

rep("onOpen = { onShuffleOpen?.invoke(it) },",
    '''onOpen = { onShuffleOpen?.invoke(it) },
                                    coverPool = state.data.flatMap { it.items }.mapNotNull { it.thumbnailUrl }.distinct(),''')

open(p, "w", encoding="utf-8").write(s)
print("OK")
