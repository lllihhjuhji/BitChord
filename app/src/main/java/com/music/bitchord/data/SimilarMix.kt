package com.music.bitchord.data

import com.music.bitchord.data.model.SearchFilter
import com.music.bitchord.data.model.SearchResult
import com.music.bitchord.data.model.Song
import com.music.bitchord.data.scrobbling.LastFM
import com.music.bitchord.data.settings.AppSettings
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

    /** Region for YouTube radio when the mix is not meant to be Korean. */
    private const val NON_KOREAN_REGION = "JP"

    /** Tracks this mix handed out recently, so the same song is not suggested build after build. */
    private const val SHOWN_MEMORY = 150
    private val shown = LinkedHashSet<String>()
    private var shownLoaded = false

    /** Survives restarts: kept in AppSettings as a comma-separated id list. */
    private fun loadShown() {
        if (shownLoaded) return
        shownLoaded = true
        runCatching { shown.addAll(AppSettings.similarMixShown()) }
    }

    private fun rememberShown(songs: List<Song>) = synchronized(shown) {
        loadShown()
        songs.forEach { shown.remove(it.videoId); shown.add(it.videoId) }
        while (shown.size > SHOWN_MEMORY) shown.remove(shown.first())
        runCatching { AppSettings.setSimilarMixShown(shown) }
        Unit
    }

    private fun shownSnapshot(): Set<String> = synchronized(shown) {
        loadShown()
        HashSet(shown)
    }

    /** Korean picker labels searched as English, so the app's ko locale doesn't pull Korean songs in. */
    private val KEYWORD_EN = mapOf(
        "신나는" to "upbeat",
        "잔잔한" to "calm",
        "감성" to "emotional",
        "운동" to "workout",
        "집중" to "focus",
        "새벽" to "late night",
        "발라드" to "ballad",
        "힙합" to "hip hop",
        "트로트" to "trot",
        "팝송" to "pop",
    )

    private fun searchQuery(keyword: String): String =
        keyword.split(' ').filter { it.isNotBlank() }.joinToString(" ") { KEYWORD_EN[it] ?: it }

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

    suspend fun build(
        size: Int = 40,
        excludeSongIds: Set<String> = emptySet(),
        seedSong: Song? = null,
        keyword: String? = null,
    ): List<Song> {
        val history = YtMusicRepository.history().getOrNull().orEmpty()
        val kw = keyword?.takeIf { it.isNotBlank() }
        // J-pop / 팝송 explicitly ask for non-Korean results; null = decided by the seed below.
        val kwAllowsKorean: Boolean? = kw?.let { !(it.contains("j-pop", true) || it.contains("팝송")) }

        val seeds: List<Song> = when {
            seedSong != null -> listOf(seedSong)
            kw != null -> runCatching {
                YtMusicRepository.search(searchQuery(kw), SearchFilter.SONGS).getOrNull().orEmpty()
            }.getOrDefault(emptyList()).mapNotNull {
                (it as? SearchResult.Track)?.song ?: (it as? SearchResult.TopTrack)?.song
            }.filter { kwAllowsKorean != false || script(it) != 1 }.take(4)
            else -> {
                if (history.isEmpty()) return emptyList()
                val p = script(history[0])
                history.take(10).filter { script(it) == p }.take(4)
            }
        }
        if (seeds.isEmpty()) return emptyList()
        val primary = script(seeds[0])
        val allowKorean = kwAllowsKorean ?: (primary == 1)
        val region = if (allowKorean) null else NON_KOREAN_REGION
        val recentPlayed = history.take(30).mapTo(HashSet()) { it.videoId }
        val everPlayed = history.mapTo(HashSet()) { it.videoId }

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

        val pool = cands.values.filter { c ->
            val s = c.song
            s.videoId !in excludeSongIds && s.videoId !in seedIds &&
                ArtistAffinity.score(s.artist) > -3f &&
                (allowKorean || script(s) != 1)
        }

        val shownNow = shownSnapshot()
        // Played songs are no longer excluded, only ranked lower: the last 30 plays
        // and anything suggested recently drop furthest, older plays barely.
        fun penalty(id: String): Float =
            (if (id in shownNow) 3f else 0f) +
                (if (id in recentPlayed) 2f else if (id in everPlayed) 0.5f else 0f)

        val ranked = pool
            .map { it to (it.score + ArtistAffinity.score(it.song.artist) * 0.3f + Random.nextFloat() * 0.5f - penalty(it.song.videoId)) }
            .sortedByDescending { it.second }
            .map { it.first }

        val perArtist = HashMap<String, Int>()
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
        rememberShown(out)
        return if (seedSong != null) listOf(seedSong) + out.filter { it.videoId != seedSong.videoId } else out
    }
}
