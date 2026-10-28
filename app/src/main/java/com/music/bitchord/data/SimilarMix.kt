package com.music.bitchord.data

import com.music.bitchord.data.model.SearchFilter
import com.music.bitchord.data.model.SearchResult
import com.music.bitchord.data.model.Song
import com.music.bitchord.data.scrobbling.LastFM
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlin.random.Random

/**
 * "비슷한 곡" mix: seeds from the latest plays of one language, voted on by YouTube
 * radio + Last.fm similar tracks, language-filtered, then ordered so neighbours are alike.
 */
object SimilarMix {
    private class Cand(val song: Song) {
        var score = 0f
        val sources = HashSet<String>()
    }

    /** 0 = latin/other, 1 = hangul, 2 = kana/kanji. */
    private fun script(s: Song): Int {
        var ko = 0
        var ja = 0
        for (c in s.title + s.artist) {
            val x = c.code
            if (x in 0xAC00..0xD7A3 || x in 0x1100..0x11FF || x in 0x3130..0x318F) {
                ko++
            } else if (x in 0x3040..0x30FF || x in 0x4E00..0x9FFF) {
                ja++
            }
        }
        return when {
            ko == 0 && ja == 0 -> 0
            ko >= ja -> 1
            else -> 2
        }
    }

    suspend fun build(size: Int = 40, excludeSongIds: Set<String> = emptySet()): List<Song> {
        val history = YtMusicRepository.history().getOrNull().orEmpty()
        if (history.isEmpty()) return emptyList()
        val primary = script(history[0])
        val seeds = history.take(10).filter { script(it) == primary }.take(4)
        val played = history.mapTo(HashSet()) { it.videoId }.apply { addAll(excludeSongIds) }

        val cands = HashMap<String, Cand>()
        val lock = Any()
        fun add(song: Song, pts: Float, src: String) {
            synchronized(lock) {
                val c = cands.getOrPut(song.videoId) { Cand(song) }
                c.score += pts
                c.sources.add(src)
            }
        }

        val gate = Semaphore(6)
        coroutineScope {
            seeds.map { seed ->
                async {
                    val radio = runCatching { YtMusicRepository.radio(seed.videoId).getOrNull().orEmpty() }
                        .getOrDefault(emptyList())
                    radio.forEachIndexed { i, s ->
                        add(s, 1f + 0.5f * (1f - i / radio.size.toFloat()), "r:${seed.videoId}")
                    }
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
                }
            }.awaitAll()
        }

        val pool = cands.values.filter { c ->
            val s = c.song
            val cs = script(s)
            s.videoId !in played &&
                ArtistAffinity.score(s.artist) > -3f &&
                (cs == primary || c.score >= 4f || ((cs == 0 || primary == 0) && c.score >= 2f))
        }

        val ranked = pool
            .map { it to (it.score + ArtistAffinity.score(it.song.artist) * 0.3f + Random.nextFloat() * 0.5f) }
            .sortedByDescending { it.second }
            .map { it.first }

        val perArtist = HashMap<String, Int>()
        val picked = ArrayList<Cand>()
        for (c in ranked) {
            if (picked.size >= size) break
            val k = c.song.artistId ?: ArtistAffinity.key(c.song.artist)
            val n = perArtist[k] ?: 0
            if (n >= 2) continue
            perArtist[k] = n + 1
            picked.add(c)
        }
        if (picked.isEmpty()) return emptyList()

        val left = picked.toMutableList()
        var cur = left.removeAt(0)
        val out = ArrayList<Song>(picked.size)
        out.add(cur.song)
        while (left.isNotEmpty()) {
            val prev = cur
            val next = left.maxByOrNull { c ->
                val common = c.sources.count { it in prev.sources }.toFloat()
                val sameArtist = if (c.song.artistId != null && c.song.artistId == prev.song.artistId) 0.5f else 0f
                common + sameArtist + c.score * 0.1f
            }!!
            left.remove(next)
            out.add(next.song)
            cur = next
        }
        return out
    }
}
