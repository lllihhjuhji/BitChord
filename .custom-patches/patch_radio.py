import sys

def must_replace(s, old, new, path):
    if s.count(old) != 1:
        sys.exit("MISS %s: %r x%d" % (path, old[:60], s.count(old)))
    return s.replace(old, new)

# ---- Innertube.kt ----
p = "shared/src/jvmSharedMain/kotlin/com/music/bitchord/data/innertube/Innertube.kt"
s = open(p, encoding="utf-8").read()
s = must_replace(
    s,
    'suspend fun next(videoId: String): JsonObject = postMusic("next") {',
    'suspend fun next(videoId: String, region: String? = null): JsonObject =\n        postMusic("next", region = region) {',
    p,
)
a = s.index("private suspend fun postMusic(")
b = s.index("private suspend fun postMusicAnonymous(")
body = s[a:b]
body = must_replace(
    body,
    "        query: Map<String, String> = emptyMap(),\n        bodyExtras: JsonObjectBuilder.() -> Unit,",
    "        query: Map<String, String> = emptyMap(),\n        region: String? = null,\n        bodyExtras: JsonObjectBuilder.() -> Unit,",
    p,
)
body = must_replace(body, 'put("gl", currentRegion)', 'put("gl", region ?: currentRegion)', p)
s = s[:a] + body + s[b:]
open(p, "w", encoding="utf-8").write(s)

# ---- YtMusicRepository.kt ----
p = "shared/src/jvmSharedMain/kotlin/com/music/bitchord/data/YtMusicRepository.kt"
s = open(p, encoding="utf-8").read()
s = must_replace(
    s,
    'suspend fun radio(videoId: String): Result<List<Song>> = call("radio:$videoId") {\n        InnertubeParser.parseWatchQueue(Innertube.next(videoId))\n    }',
    'suspend fun radio(videoId: String, region: String? = null): Result<List<Song>> =\n        call("radio:$videoId:${region.orEmpty()}") {\n            InnertubeParser.parseWatchQueue(Innertube.next(videoId, region))\n        }',
    p,
)
open(p, "w", encoding="utf-8").write(s)

# ---- Autoplay.kt ----
p = "app/src/main/java/com/music/bitchord/playback/Autoplay.kt"
s = open(p, encoding="utf-8").read()
s = must_replace(
    s,
    "    val related = YtMusicRepository.radio(seed).getOrElse { return Result.failure(it) }\n",
    r'''    // Korean seed: leave the station alone. Anything else gets a JP-region
    // station with Hangul tracks removed (the app locale is ko, so the plain
    // request drifts to old Korean songs).
    val koreanSeed = hasHangul(seedSong.toString())
    val related = YtMusicRepository.radio(seed, if (koreanSeed) null else RADIO_REGION)
        .getOrElse { return Result.failure(it) }
        .let { list -> if (koreanSeed) list else list.filterNot { hasHangul(it.toString()) } }
''',
    p,
)
s += r'''

private const val RADIO_REGION = "JP"

private val HANGUL = Regex("[\\u1100-\\u11FF\\u3130-\\u318F\\uAC00-\\uD7A3]")

private fun hasHangul(text: String): Boolean = HANGUL.containsMatchIn(text)
'''
open(p, "w", encoding="utf-8").write(s)
print("OK")
