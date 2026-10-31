package com.music.bitchord.data

import java.util.concurrent.ConcurrentHashMap
import kotlin.math.abs

/**
 * How the listener has treated each artist: finished tracks push the score up,
 * skipped ones push it down. Only the discovery mix reads it.
 */
object ArtistAffinity {
    private const val LIMIT = 6f
    private const val MAX_ENTRIES = 500

    private val scores = ConcurrentHashMap<String, Float>()

    @Volatile
    private var persist: ((String) -> Unit)? = null

    /** Load [saved] and start handing every change to [persist]. */
    fun attach(saved: String, persist: (String) -> Unit) {
        scores.clear()
        saved.lineSequence().forEach { line ->
            val i = line.indexOf('|')
            if (i <= 0) return@forEach
            val value = line.substring(0, i).toFloatOrNull() ?: return@forEach
            val key = line.substring(i + 1)
            if (key.isNotBlank()) scores[key] = value
        }
        this.persist = persist
    }

    fun key(artist: String): String =
        artist.trim().lowercase().replace('\n', ' ').replace('|', ' ')

    fun score(artist: String): Float = scores[key(artist)] ?: 0f

    fun record(artist: String, delta: Float) {
        val k = key(artist)
        if (k.isEmpty()) return
        scores.compute(k) { _, old -> ((old ?: 0f) + delta).coerceIn(-LIMIT, LIMIT) }
        if (scores.size > MAX_ENTRIES) {
            scores.entries
                .sortedBy { abs(it.value) }
                .take(scores.size - MAX_ENTRIES)
                .forEach { scores.remove(it.key) }
        }
        persist?.invoke(scores.entries.joinToString("\n") { "${it.value}|${it.key}" })
    }

    /** Call once per track when it stops being the current one. */
    fun onTrackEnded(artist: String, playedSeconds: Long, durationSeconds: Long, finished: Boolean) {
        val ratio = if (durationSeconds > 0) playedSeconds.toFloat() / durationSeconds else -1f
        when {
            finished || ratio >= 0.8f -> record(artist, 1f)
            playedSeconds < 30 || ratio in 0f..0.3f -> record(artist, -1f)
        }
    }
}
