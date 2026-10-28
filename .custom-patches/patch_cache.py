import sys

def rep(s, old, new, label):
    if s.count(old) != 1:
        sys.exit("MISS %s x%d" % (label, s.count(old)))
    return s.replace(old, new)

R  = "shared/src/jvmSharedMain/kotlin/com/music/bitchord/data/YtMusicRepository.kt"
V  = "app/src/main/java/com/music/bitchord/ui/MainViewModel.kt"
AS = "app/src/main/java/com/music/bitchord/data/settings/AppSettings.kt"
r = open(R, encoding="utf-8").read()
v = open(V, encoding="utf-8").read()
a = open(AS, encoding="utf-8").read()

# ---------------- AppSettings: storage ----------------
a = rep(a, 'private const val KEY_HOME_RECENTS_VIEW_TYPE = "home_recents_view_type"',
        'private const val KEY_HOME_RECENTS_VIEW_TYPE = "home_recents_view_type"\n    private const val KEY_HOME_FEED_CACHE = "home_feed_cache"', "as-key")
a = rep(a, "fun setHomeRecentsViewType(value: LibraryViewType) {",
        '''fun homeFeedCache(): String? = prefs.getString(KEY_HOME_FEED_CACHE, null)

    fun setHomeFeedCache(json: String) {
        prefs.edit().putString(KEY_HOME_FEED_CACHE, json).apply()
    }

    fun setHomeRecentsViewType(value: LibraryViewType) {''', "as-funcs")

# ---------------- YtMusicRepository: browse cache ----------------
r = rep(r, 'suspend fun home(): Result<HomeFeed> = call("home") {',
        'suspend fun home(fresh: Boolean = false): Result<HomeFeed> = call("home") {', "r-home-sig")
r = rep(r, 'val home = Innertube.browse("FEmusic_home")',
        'val home = cachedBrowse("FEmusic_home", HOME_TTL_MS, fresh)', "r-home-body")
r = rep(r, 'runCatching { Innertube.browse("FEmusic_home") }.getOrNull()',
        'runCatching { cachedBrowse("FEmusic_home", HOME_TTL_MS) }.getOrNull()', "r-quick")
r = rep(r, "InnertubeParser.parseHome(Innertube.browse(browseId))",
        'InnertubeParser.parseHome(cachedBrowse(browseId, if (browseId == "FEmusic_home") HOME_TTL_MS else SUPPLEMENT_TTL_MS))', "r-shelves")
r = rep(r, "/** The server-defined mood and genre categories used by Explore. */",
        r'''// ---- Short-lived browse cache ------------------------------------------

    private const val HOME_TTL_MS = 20_000L
    private const val SUPPLEMENT_TTL_MS = 300_000L

    private class BrowseEntry(
        val at: Long,
        val value: kotlinx.coroutines.Deferred<kotlinx.serialization.json.JsonObject>,
    )

    private val browseScope = kotlinx.coroutines.CoroutineScope(
        kotlinx.coroutines.SupervisorJob() + kotlinx.coroutines.Dispatchers.IO,
    )
    private val browseCache = HashMap<String, BrowseEntry>()

    /** Dropped on sign-in, sign-out and profile switches so nobody sees another listener feed. */
    fun invalidateBrowseCache() = synchronized(browseCache) { browseCache.clear() }

    /**
     * One browse per [browseId] at a time, reused for [ttlMs]. A request already in
     * flight is shared instead of repeated, and a failed one is never kept.
     */
    private suspend fun cachedBrowse(
        browseId: String,
        ttlMs: Long,
        fresh: Boolean = false,
    ): kotlinx.serialization.json.JsonObject {
        val key = "$browseId|${Innertube.cookie?.hashCode() ?: 0}|${Innertube.currentLocaleTag}"
        val entry = synchronized(browseCache) {
            if (fresh) browseCache.remove(key)
            val now = System.currentTimeMillis()
            browseCache[key]?.takeIf { now - it.at < ttlMs }
                ?: BrowseEntry(now, browseScope.async { Innertube.browse(browseId) })
                    .also { browseCache[key] = it }
        }
        return try {
            entry.value.await()
        } catch (e: Throwable) {
            // The caller giving up must not throw away a request others are waiting on.
            if (e is CancellationException && entry.value.isActive) throw e
            synchronized(browseCache) { if (browseCache[key] === entry) browseCache.remove(key) }
            throw e
        }
    }

    /** The server-defined mood and genre categories used by Explore. */''', "r-helper")

# ---------------- MainViewModel: cache-first Home ----------------
v = rep(v, "publishHomeShelves(feed.shelves)", "publishHomeShelves(feed.shelves, core = true)", "v-core")
v = rep(v, "YtMusicRepository.home().onSuccess { feed ->",
        "YtMusicRepository.home(fresh = true).onSuccess { feed ->", "v-refresh-fresh")
v = rep(v, "if (shelves.isNotEmpty()) _home.value = UiState.Success(shelves)",
        "if (shelves.isNotEmpty()) {\n                homeCached = false\n                _home.value = UiState.Success(shelves)\n                scheduleHomeCacheSave()\n            }", "v-refresh-save")
v = rep(v, "private fun clearListenerState(restoreCached: Boolean = false) {",
        "private fun clearListenerState(restoreCached: Boolean = false) {\n        YtMusicRepository.invalidateBrowseCache()", "v-clear")
v = rep(v, "private val homeSeenTitles = mutableSetOf<String>()",
        '''private val homeSeenTitles = mutableSetOf<String>()

    /** True while Home is showing the saved feed and waiting for the core feed to replace it. */
    private var homeCached = false
    private val homeHeld = mutableListOf<Pair<List<HomeShelf>, Boolean>>()
    private var homeSaveJob: kotlinx.coroutines.Job? = null

    private fun scheduleHomeCacheSave() {
        val identity = listenerKey()
        val data = (_home.value as? UiState.Success)?.data ?: return
        homeSaveJob?.cancel()
        homeSaveJob = viewModelScope.launch(kotlinx.coroutines.Dispatchers.Default) {
            kotlinx.coroutines.delay(1500)
            HomeFeedCache.save(identity, data)
        }
    }''', "v-fields")

i = v.index("    fun loadHome() {")
j = v.index("_homePendingShelves.value = 1 + YtMusicRepository.HOME_SUPPLEMENT_BROWSE_IDS.size", i)
v = v[:i] + '''    fun loadHome() {
        val identity = listenerKey()
        val generation = homeLoadGeneration.incrementAndGet()
        // Paint the last feed for this listener at once; the core feed replaces it
        // when it lands (see publishHomeShelves).
        val cached = HomeFeedCache.load(identity)
        homeCached = cached != null
        homeHeld.clear()
        _home.value = if (cached != null) UiState.Success(cached) else UiState.Loading
        homeContinuation = null
        homeSeenTitles.clear()
        _homeLoadingMore.value = false
        _homeRecentlyPlayedLoading.value = _signedIn.value && cached == null
        // The core feed plus one browse per supplement. Recently played is left
        // out: it has its own skeleton at the head of the page rather than the
        // one at the tail.
        ''' + v[j:]

v = rep(v, "private fun publishHomeShelves(shelves: List<HomeShelf>, prepend: Boolean = false) {",
        '''private fun publishHomeShelves(shelves: List<HomeShelf>, prepend: Boolean = false, core: Boolean = false) {
        if (homeCached) {
            // Saved feed on screen: hold everything except the core feed, then swap
            // the whole page at once so it never collapses to a single shelf.
            if (!core) {
                homeHeld += shelves to prepend
                return
            }
            homeCached = false
            homeSeenTitles.clear()
            _home.value = UiState.Success(emptyList())
            applyHomeShelves(shelves, prepend)
            val held = homeHeld.toList()
            homeHeld.clear()
            held.forEach { (list, pre) -> applyHomeShelves(list, pre) }
        } else {
            applyHomeShelves(shelves, prepend)
        }
        scheduleHomeCacheSave()
    }

    private fun applyHomeShelves(shelves: List<HomeShelf>, prepend: Boolean = false) {''', "v-wrapper")

open(R, "w", encoding="utf-8").write(r)
open(V, "w", encoding="utf-8").write(v)
open(AS, "w", encoding="utf-8").write(a)
print("OK")
