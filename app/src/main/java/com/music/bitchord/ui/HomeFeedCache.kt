package com.music.bitchord.ui

import com.music.bitchord.data.model.HomeShelf
import com.music.bitchord.data.model.ShelfItem
import com.music.bitchord.data.settings.AppSettings
import org.json.JSONArray
import org.json.JSONObject

/** The last Home feed per listener, so the page can paint before the network answers. */
object HomeFeedCache {
    private const val VERSION = 1
    private const val MAX_SHELVES = 14
    private const val MAX_ITEMS = 14

    private fun JSONObject.str(key: String): String? = if (isNull(key)) null else optString(key)

    fun save(identity: String?, shelves: List<HomeShelf>) {
        if (shelves.isEmpty()) return
        try {
            val arr = JSONArray()
            for (shelf in shelves.take(MAX_SHELVES)) {
                val items = JSONArray()
                for (item in shelf.items.take(MAX_ITEMS)) {
                    items.put(JSONObject().apply {
                        put("t", item.title)
                        put("s", item.subtitle)
                        put("u", item.thumbnailUrl)
                        put("v", item.videoId)
                        put("b", item.browseId)
                    })
                }
                arr.put(JSONObject().apply {
                    put("t", shelf.title)
                    put("s", shelf.subtitle)
                    put("mb", shelf.moreBrowseId)
                    put("mp", shelf.moreParams)
                    put("i", items)
                })
            }
            val root = JSONObject()
            root.put("v", VERSION)
            root.put("id", identity.orEmpty())
            root.put("shelves", arr)
            AppSettings.setHomeFeedCache(root.toString())
        } catch (e: Throwable) {
            // A cache that cannot be written is just a cache miss next time.
        }
    }

    fun load(identity: String?): List<HomeShelf>? {
        return try {
            val raw = AppSettings.homeFeedCache() ?: return null
            val root = JSONObject(raw)
            if (root.optInt("v") != VERSION || root.optString("id") != identity.orEmpty()) return null
            val arr = root.getJSONArray("shelves")
            val out = ArrayList<HomeShelf>(arr.length())
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                val itemsJson = o.getJSONArray("i")
                val items = ArrayList<ShelfItem>(itemsJson.length())
                for (j in 0 until itemsJson.length()) {
                    val ji = itemsJson.getJSONObject(j)
                    items.add(
                        ShelfItem(
                            title = ji.optString("t"),
                            subtitle = ji.optString("s"),
                            thumbnailUrl = ji.str("u"),
                            videoId = ji.str("v"),
                            browseId = ji.str("b"),
                        ),
                    )
                }
                out.add(
                    HomeShelf(
                        title = o.optString("t"),
                        items = items,
                        subtitle = o.optString("s"),
                        moreBrowseId = o.str("mb"),
                        moreParams = o.str("mp"),
                    ),
                )
            }
            out.takeIf { it.isNotEmpty() }
        } catch (e: Throwable) {
            null
        }
    }
}
