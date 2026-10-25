package com.music.bitchord.data.sources

import android.net.Uri
import com.music.bitchord.data.TrackLog
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Keeps a lastbabe.velixir.run addon alive: when its URL is within
 * [REFRESH_WINDOW_SEC] of expiring, solves the site's proof-of-work, mints a
 * fresh URL and swaps it into the stored source.
 */
object LastBabeRefresher {

    private const val TAG = "LastBabe"
    private const val HOST = "lastbabe.velixir.run"
    private const val BASE = "https://$HOST"
    private const val REFRESH_WINDOW_SEC = 12 * 3600L
    private const val CHECK_EVERY_MS = 30 * 60 * 1000L
    private const val MAX_NONCE = 50_000_000L

    private val started = AtomicBoolean(false)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val expiryRegex = Regex("""/e/(\d+)/""")
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    fun start() {
        if (!started.compareAndSet(false, true)) return
        scope.launch {
            while (true) {
                runCatching { refreshIfDue() }
                    .onFailure { TrackLog.w(TAG, "refresh failed: ${it.message}") }
                delay(CHECK_EVERY_MS)
            }
        }
    }

    private fun SourceConfig.isLastBabe(): Boolean =
        kind == SourceKind.ADDON &&
            runCatching { Uri.parse(baseUrl).host }.getOrNull().equals(HOST, ignoreCase = true)

    /** Seconds until this addon's URL dies, or null if the URL carries no expiry. */
    private fun secondsLeft(config: SourceConfig, nowSec: Long): Long? =
        expiryRegex.find(config.baseUrl)?.groupValues?.get(1)?.toLongOrNull()?.minus(nowSec)

    suspend fun refreshIfDue() {
        val nowSec = System.currentTimeMillis() / 1000
        val due = SourceRegistry.configs.value.any { cfg ->
            cfg.isLastBabe() && (secondsLeft(cfg, nowSec) ?: Long.MAX_VALUE) < REFRESH_WINDOW_SEC
        }
        if (!due) return

        val fresh = mint()
        TrackLog.d(TAG, "minted a fresh addon url")
        // Registry state is mutated from the UI thread everywhere else; stay consistent.
        withContext(Dispatchers.Main) {
            SourceRegistry.configs.value
                .filter { it.isLastBabe() }
                .forEach { SourceRegistry.update(it.copy(baseUrl = fresh)) }
        }
    }

    private fun mint(): String {
        val c = getJson("$BASE/challenge")
        val challenge = c["challenge"]?.jsonPrimitive?.contentOrNull ?: error("no challenge")
        val difficulty = c["difficulty"]?.jsonPrimitive?.intOrNull ?: 4
        val nonce = solve(challenge, difficulty)

        val body = buildJsonObject {
            put("challenge", challenge)
            put("nonce", nonce)
        }.toString()
        val m = postJson("$BASE/mint", body)
        return m["manifestUrl"]?.jsonPrimitive?.contentOrNull
            ?: m["addonUrl"]?.jsonPrimitive?.contentOrNull
            ?: error("mint failed: ${m["error"]?.jsonPrimitive?.contentOrNull}")
    }

    private fun solve(challenge: String, difficulty: Int): String {
        val md = MessageDigest.getInstance("SHA-256")
        var n = 0L
        while (n < MAX_NONCE) {
            n++
            val digest = md.digest((challenge + n).toByteArray())
            if (leadingZeroNibbles(digest) >= difficulty) return n.toString()
        }
        error("proof-of-work gave up")
    }

    private fun leadingZeroNibbles(d: ByteArray): Int {
        var count = 0
        for (b in d) {
            val v = b.toInt() and 0xFF
            if (v == 0) { count += 2; continue }
            if (v < 16) count += 1
            break
        }
        return count
    }

    private fun getJson(url: String): JsonObject =
        client.newCall(Request.Builder().url(url).build()).execute().use { parse(it) }

    private fun postJson(url: String, body: String): JsonObject =
        client.newCall(
            Request.Builder().url(url)
                .post(body.toRequestBody("application/json".toMediaType()))
                .build(),
        ).execute().use { parse(it) }

    private fun parse(r: okhttp3.Response): JsonObject {
        val text = r.body?.string().orEmpty()
        return runCatching { Json.parseToJsonElement(text).jsonObject }
            .getOrElse { error("HTTP ${r.code}: unreadable response") }
    }
}
