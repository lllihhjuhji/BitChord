import sys

def rep(s, old, new, label):
    if s.count(old) != 1:
        sys.exit("MISS %s x%d" % (label, s.count(old)))
    return s.replace(old, new)

HP = "sharedUi/src/jvmSharedMain/kotlin/com/music/bitchord/ui/screens/HomeScreen.kt"
MP = "app/src/main/java/com/music/bitchord/MainActivity.kt"
h = open(HP, encoding="utf-8").read()
m = open(MP, encoding="utf-8").read()

# ---------- HomeScreen.kt ----------
h = rep(h, "onShuffleKeyword: ((String) -> Unit)? = null,",
        "onShuffleKeyword: ((String) -> Unit)? = null,\n    onShuffleOpen: ((Int) -> Unit)? = null,", "param")
h = rep(h, "onMode = { onShuffleMode?.invoke(it) },",
        "onMode = { onShuffleMode?.invoke(it) },\n                                    onOpen = { onShuffleOpen?.invoke(it) },", "callsite")

a = h.index("internal fun androidx.compose.foundation.lazy.LazyListScope.shuffleSection(")
b = h.index("private fun PickLabel(")
c = h.rindex("@Composable", a, b)

NEW_SECTION = r'''internal fun androidx.compose.foundation.lazy.LazyListScope.shuffleSection(
    songs: List<Song>,
    loading: Boolean,
    mode: Int,
    onMode: (Int) -> Unit,
    recentSongs: List<Song>,
    onPickSong: (Song) -> Unit,
    onPickKeyword: (String) -> Unit,
    currentSong: Song?,
    isPlaying: Boolean,
    onPlay: (Int) -> Unit,
    onRefresh: () -> Unit,
    onOpen: (Int) -> Unit = {},
) {
    item(key = "shuffle_cards") {
        val covers = songs.map { it.thumbnailUrl }
        Column(Modifier.padding(bottom = 26.dp)) {
            SectionHeader("셔플", "")
            ShelfRow(
                contentPadding = PaddingValues(horizontal = PAGE_GUTTER),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                item(key = "shuffle_random") {
                    ShuffleCard(
                        title = "무작위 셔플",
                        subtitle = "처음 듣는 곡 위주",
                        covers = if (mode == 0) covers else emptyList(),
                        onClick = { onOpen(0) },
                    )
                }
                item(key = "shuffle_genre") {
                    ShuffleCard(
                        title = "장르별 셔플",
                        subtitle = "비슷한 곡끼리 이어서",
                        covers = if (mode == 1) covers else emptyList(),
                        onClick = { onOpen(1) },
                    )
                }
            }
        }
    }
}

'''
h = h[:a] + NEW_SECTION + h[c:]

h += r'''

@Composable
private fun ShuffleCard(
    title: String,
    subtitle: String,
    covers: List<String?>,
    onClick: () -> Unit,
) {
    Column(Modifier.width(SHELF_CARD_WIDTH).clickable(onClick = onClick)) {
        ShuffleCover(
            covers = covers,
            modifier = Modifier.fillMaxWidth().aspectRatio(1f).clip(RoundedCornerShape(12.dp)),
        )
        Spacer(Modifier.height(10.dp))
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onBackground,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            text = subtitle,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/** 2x2 collage when there are four covers, a single cover for fewer, an icon for none. */
@Composable
private fun ShuffleCover(covers: List<String?>, modifier: Modifier = Modifier) {
    val urls = covers.filterNotNull().distinct()
    Box(
        modifier = modifier.background(MaterialTheme.colorScheme.surfaceVariant),
        contentAlignment = Alignment.Center,
    ) {
        when {
            urls.size >= 4 -> Column(Modifier.fillMaxSize()) {
                for (row in 0..1) {
                    Row(Modifier.weight(1f).fillMaxWidth()) {
                        for (col in 0..1) {
                            AsyncImage(
                                model = urls[row * 2 + col].artworkAt(CARD_ART_PX),
                                contentDescription = null,
                                contentScale = ContentScale.Crop,
                                modifier = Modifier.weight(1f).fillMaxSize(),
                            )
                        }
                    }
                }
            }
            urls.isNotEmpty() -> AsyncImage(
                model = urls[0].artworkAt(CARD_ART_PX),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
            else -> Icon(
                imageVector = Icons.Rounded.LibraryMusic,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(34.dp),
            )
        }
    }
}

/** The page a shuffle card opens: cover, play / refresh buttons, then the track list. */
@Composable
fun ShuffleDetailScreen(
    mode: Int,
    songs: List<Song>,
    loading: Boolean,
    recentSongs: List<Song>,
    onPickSong: (Song) -> Unit,
    onPickKeyword: (String) -> Unit,
    onPlay: (Int) -> Unit,
    onRefresh: () -> Unit,
    onBack: () -> Unit,
    contentPadding: PaddingValues,
    modifier: Modifier = Modifier,
    currentSong: Song? = null,
    isPlaying: Boolean = false,
) {
    val title = if (mode == 0) "무작위 셔플" else "장르별 셔플"
    val subtitle = if (mode == 0) "처음 듣는 곡 위주" else "비슷한 곡끼리 이어서"
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = contentPadding,
    ) {
        item(key = "shuffle_back") {
            Text(
                text = "←",
                style = MaterialTheme.typography.headlineSmall,
                color = MaterialTheme.colorScheme.onBackground,
                modifier = Modifier
                    .padding(horizontal = PAGE_GUTTER - 8.dp, vertical = 4.dp)
                    .clip(CircleShape)
                    .clickable(onClick = onBack)
                    .padding(horizontal = 14.dp, vertical = 8.dp),
            )
        }
        item(key = "shuffle_head") {
            Column(
                modifier = Modifier.fillMaxWidth().padding(horizontal = PAGE_GUTTER),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                ShuffleCover(
                    covers = songs.map { it.thumbnailUrl },
                    modifier = Modifier.fillMaxWidth(0.78f).aspectRatio(1f).clip(RoundedCornerShape(16.dp)),
                )
                Spacer(Modifier.height(18.dp))
                Text(
                    text = title,
                    style = MaterialTheme.typography.headlineSmall,
                    color = MaterialTheme.colorScheme.onBackground,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                )
                Text(
                    text = if (songs.isNotEmpty()) "$subtitle · ${songs.size}곡" else subtitle,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                )
                Spacer(Modifier.height(18.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .size(52.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.surfaceVariant)
                            .clickable { if (!loading) onRefresh() },
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.Cached,
                            contentDescription = "새로고침",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(24.dp),
                        )
                    }
                    Row(
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp)
                            .clip(RoundedCornerShape(50))
                            .background(MaterialTheme.colorScheme.primary)
                            .clickable { if (songs.isNotEmpty()) onPlay(0) },
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center,
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.PlayArrow,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onPrimary,
                            modifier = Modifier.size(24.dp),
                        )
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = "재생",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                    }
                }
                Spacer(Modifier.height(16.dp))
            }
        }
        if (mode == 1 && songs.isEmpty() && !loading) {
            item(key = "shuffle_picker") { ShufflePicker(recentSongs, onPickSong, onPickKeyword) }
        } else if (songs.isEmpty()) {
            item(key = "shuffle_empty") {
                Text(
                    text = if (loading) "만드는 중…" else "곡을 찾지 못했어",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = PAGE_GUTTER, vertical = 12.dp),
                )
            }
        } else {
            items(songs.size, key = { "shuffle_row_$it" }) { i ->
                val s = songs[i]
                Box(Modifier.padding(horizontal = PAGE_GUTTER)) {
                    CompactTrackRow(
                        title = s.title,
                        subtitle = s.artist,
                        thumbnailUrl = s.thumbnailUrl,
                        onClick = { onPlay(i) },
                        onLongPress = null,
                        isCurrent = currentSong?.videoId == s.videoId,
                        isPlaying = isPlaying && currentSong?.videoId == s.videoId,
                    )
                }
            }
        }
    }
}
'''

# ---------- MainActivity.kt ----------
m = rep(m, "var shuffleMode by remember { mutableStateOf(0) }",
        "var shuffleMode by remember { mutableStateOf(0) }\n    var shuffleDetail by remember { mutableStateOf<Int?>(null) }", "state")
# the mix is now built when its card is opened, not on every app start
m = rep(m, "LaunchedEffect(Unit) { loadShuffle() }",
        "// shuffle is built lazily when its card is opened (keeps startup requests free for Home)", "lazy")
m = rep(m, "BackHandler(enabled = canGoBack, onBack = goBack)",
        "BackHandler(enabled = canGoBack, onBack = goBack)\n        BackHandler(enabled = shuffleDetail != null) { shuffleDetail = null }", "back")
m = rep(m, "onShufflePickSong = { loadSimilar(it, null) },",
        """onShufflePickSong = { loadSimilar(it, null) },
                                onShuffleOpen = { target ->
                                    if (shuffleMode != target) {
                                        shuffleMode = target
                                        shuffleSongs = emptyList()
                                        if (target == 0) loadShuffle() else loadRecent()
                                    } else if (target == 0 && shuffleSongs.isEmpty() && !shuffleLoading) {
                                        loadShuffle()
                                    }
                                    shuffleDetail = target
                                },""", "open")
m = rep(m, "TAB_HOME -> HomeScreen(",
        """TAB_HOME -> if (shuffleDetail != null) {
                            com.music.bitchord.ui.screens.ShuffleDetailScreen(
                                mode = shuffleDetail ?: 0,
                                songs = shuffleSongs,
                                loading = shuffleLoading,
                                recentSongs = shuffleRecent,
                                onPickSong = { loadSimilar(it, null) },
                                onPickKeyword = { loadSimilar(null, it) },
                                onPlay = { index ->
                                    scope.launch {
                                        val c = controller
                                        if (shuffleSongs.isNotEmpty() && c != null && !refusedByHost()) {
                                            playRequestGeneration++
                                            c.playSongs(
                                                shuffleSongs.map {
                                                    it.copy(
                                                        playbackSource = if (shuffleMode == 0) "무작위 셔플" else "비슷한 곡",
                                                        playbackSourceType = PlaybackSourceType.HOME,
                                                    )
                                                },
                                                index,
                                            )
                                        }
                                    }
                                },
                                onRefresh = { if (shuffleMode == 0) loadShuffle() else shuffleSongs = emptyList() },
                                onBack = { shuffleDetail = null },
                                contentPadding = listPadding,
                                currentSong = player.song,
                            )
                        } else HomeScreen(""", "tab")

open(HP, "w", encoding="utf-8").write(h)
open(MP, "w", encoding="utf-8").write(m)
print("OK")
