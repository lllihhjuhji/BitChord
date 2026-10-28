import sys
p = "app/src/main/java/com/music/bitchord/data/SimilarMix.kt"
s = open(p, encoding="utf-8").read()

def rep(old, new):
    global s
    if s.count(old) != 1:
        sys.exit("MISS x%d: %r" % (s.count(old), old[:70]))
    s = s.replace(old, new)

rep('private const val NON_KOREAN_REGION = "JP"',
    '''private const val NON_KOREAN_REGION = "JP"

    /** Tracks this mix handed out recently, so the same song is not suggested build after build. */
    private const val SHOWN_MEMORY = 150
    private val shown = LinkedHashSet<String>()

    private fun rememberShown(songs: List<Song>) = synchronized(shown) {
        songs.forEach { shown.remove(it.videoId); shown.add(it.videoId) }
        while (shown.size > SHOWN_MEMORY) shown.remove(shown.first())
    }

    private fun shownSnapshot(): Set<String> = synchronized(shown) { HashSet(shown) }''')

rep('val played = history.mapTo(HashSet()) { it.videoId }.apply { addAll(excludeSongIds) }',
    '''val recentPlayed = history.take(30).mapTo(HashSet()) { it.videoId }
        val everPlayed = history.mapTo(HashSet()) { it.videoId }''')

rep('s.videoId !in played &&',
    's.videoId !in excludeSongIds && s.videoId !in seedIds &&')

rep('val ranked = pool',
    '''val shownNow = shownSnapshot()
        // Played songs are no longer excluded, only ranked lower: the last 30 plays
        // and anything suggested recently drop furthest, older plays barely.
        fun penalty(id: String): Float =
            (if (id in shownNow) 3f else 0f) +
                (if (id in recentPlayed) 2f else if (id in everPlayed) 0.5f else 0f)

        val ranked = pool''')

rep('.map { it to (it.score + ArtistAffinity.score(it.song.artist) * 0.3f + Random.nextFloat() * 0.5f) }',
    '.map { it to (it.score + ArtistAffinity.score(it.song.artist) * 0.3f + Random.nextFloat() * 0.5f - penalty(it.song.videoId)) }')

rep('return if (seedSong != null) listOf(seedSong)',
    'rememberShown(out)\n        return if (seedSong != null) listOf(seedSong)')

open(p, "w", encoding="utf-8").write(s)
print("OK")
