import sys
p = "app/src/main/java/com/music/bitchord/data/SimilarMix.kt"
s = open(p, encoding="utf-8").read()

def span(s, start, end):
    a = s.index(start)
    b = s.index(end, a)
    return a, b

# 1) candidate gathering: two hops
a, b = span(s, "        val gate = Semaphore(6)\n", "        val pool = cands.values.filter { c ->")
GATHER = r'''        val gate = Semaphore(6)
        val seedIds = seeds.mapTo(HashSet()) { it.videoId }

        suspend fun addRadio(id: String, weight: Float): List<Song> {
            val radio = runCatching { YtMusicRepository.radio(id, region).getOrNull().orEmpty() }
                .getOrDefault(emptyList())
            radio.forEachIndexed { i, s ->
                add(s, weight * (1f + 0.5f * (1f - i / radio.size.toFloat())), "r:$id")
            }
            return radio
        }

        coroutineScope {
            val firstHop = seeds.map { seed ->
                async {
                    val radio = addRadio(seed.videoId, 1f)
                    if (LastFM.isInitialized()) {
                        val sim = runCatching { LastFM.getSimilar(seed.title, seed.artist, 8) }
                            .getOrDefault(emptyList())
                        sim.map { (t, a) ->
                            async {
                                gate.withPermit {
                                    val hit = runCatching {
                                        YtMusicRepository.search("$a $t", SearchFilter.SONGS).getOrNull()
                                    }.getOrNull()?.firstNotNullOfOrNull { (it as? SearchResult.Track)?.song }
                                    if (hit != null &&
                                        (hit.artist.contains(a, true) || a.contains(hit.artist, true))
                                    ) {
                                        add(hit, 3f, "l:${seed.videoId}")
                                    }
                                }
                            }
                        }.awaitAll()
                    }
                    radio
                }
            }.awaitAll()
            // Second hop: a station for a few of the first stations' tracks, so one
            // seed is no longer capped at a single page of ~25 tracks.
            firstHop.flatten()
                .filter { it.videoId !in seedIds && (allowKorean || script(it) != 1) }
                .distinctBy { it.videoId }
                .shuffled()
                .take(6)
                .map { t -> async { gate.withPermit { addRadio(t.videoId, 0.6f) } } }
                .awaitAll()
        }

'''
s = s[:a] + GATHER + s[b:]

# 2) pool filter: drop the strict script rule, keep "no Hangul unless allowed"
a, b = span(s, "        val pool = cands.values.filter { c ->", "        val ranked = pool")
POOL = r'''        val pool = cands.values.filter { c ->
            val s = c.song
            s.videoId !in played &&
                ArtistAffinity.score(s.artist) > -3f &&
                (allowKorean || script(s) != 1)
        }

'''
s = s[:a] + POOL + s[b:]

# 3) per-artist cap: 2 first, relaxed to 5 to reach the target size
a, b = span(s, "        val perArtist = HashMap<String, Int>()", "        if (picked.isEmpty()) return emptyList()")
PICK = r'''        val perArtist = HashMap<String, Int>()
        val picked = ArrayList<Cand>()
        val pickedIds = HashSet<String>()
        for (cap in intArrayOf(2, 5)) {
            for (c in ranked) {
                if (picked.size >= size) break
                if (c.song.videoId in pickedIds) continue
                val k = c.song.artistId ?: ArtistAffinity.key(c.song.artist)
                val n = perArtist[k] ?: 0
                if (n >= cap) continue
                perArtist[k] = n + 1
                pickedIds.add(c.song.videoId)
                picked.add(c)
            }
        }
'''
s = s[:a] + PICK + s[b:]
open(p, "w", encoding="utf-8").write(s)
print("OK")
