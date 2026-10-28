import sys

AS = "app/src/main/java/com/music/bitchord/data/settings/AppSettings.kt"
SM = "app/src/main/java/com/music/bitchord/data/SimilarMix.kt"
a = open(AS, encoding="utf-8").read()
m = open(SM, encoding="utf-8").read()

def rep(s, old, new, label):
    if s.count(old) != 1:
        sys.exit("MISS %s x%d" % (label, s.count(old)))
    return s.replace(old, new)

if "object AppSettings" not in a:
    sys.exit("AppSettings is not an object; paste: grep -n 'AppSettings' " + AS + " | head")

# ---- AppSettings: storage ----
a = rep(a, 'private const val KEY_HOME_RECENTS_VIEW_TYPE = "home_recents_view_type"',
        'private const val KEY_HOME_RECENTS_VIEW_TYPE = "home_recents_view_type"\n    private const val KEY_SIMILAR_MIX_SHOWN = "similar_mix_shown"', "key")
a = rep(a, "fun setHomeRecentsViewType(value: LibraryViewType) {",
        '''fun similarMixShown(): List<String> =
        prefs.getString(KEY_SIMILAR_MIX_SHOWN, null)?.split(',')?.filter { it.isNotBlank() }.orEmpty()

    fun setSimilarMixShown(ids: Collection<String>) {
        prefs.edit().putString(KEY_SIMILAR_MIX_SHOWN, ids.joinToString(",")).apply()
    }

    fun setHomeRecentsViewType(value: LibraryViewType) {''', "funcs")

# ---- SimilarMix: use it ----
m = rep(m, "import com.music.bitchord.data.scrobbling.LastFM",
        "import com.music.bitchord.data.scrobbling.LastFM\nimport com.music.bitchord.data.settings.AppSettings", "import")
i = m.index("    private val shown = LinkedHashSet<String>()")
endmark = "synchronized(shown) { HashSet(shown) }"
j = m.index(endmark) + len(endmark)
m = m[:i] + '''    private val shown = LinkedHashSet<String>()
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
    }''' + m[j:]

open(AS, "w", encoding="utf-8").write(a)
open(SM, "w", encoding="utf-8").write(m)
print("OK")
