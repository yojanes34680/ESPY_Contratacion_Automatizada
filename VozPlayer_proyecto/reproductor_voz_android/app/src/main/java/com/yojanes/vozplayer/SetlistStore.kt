package com.yojanes.vozplayer

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

/** Repertorios (listas de canciones en el orden del cantante), guardados en el teléfono. */
object SetlistStore {

    data class Setlist(
        val id: String,
        val name: String,
        val items: List<MediaEntry>,
        val created: Long,
    ) {
        val totalMs: Long get() = items.sumOf { it.durationMs.coerceAtLeast(0) }
    }

    private fun file(context: Context) = File(context.filesDir, "repertorios.json")

    @Synchronized
    fun all(context: Context): List<Setlist> {
        val root = runCatching { JSONObject(file(context).readText()) }.getOrNull() ?: return emptyList()
        val arr = root.optJSONArray("repertorios") ?: return emptyList()
        return (0 until arr.length()).mapNotNull { i -> arr.optJSONObject(i)?.let { fromJson(it) } }
    }

    fun get(context: Context, id: String): Setlist? = all(context).firstOrNull { it.id == id }

    @Synchronized
    fun save(context: Context, setlist: Setlist) {
        val lists = all(context).toMutableList()
        val i = lists.indexOfFirst { it.id == setlist.id }
        if (i >= 0) lists[i] = setlist else lists += setlist
        write(context, lists)
    }

    @Synchronized
    fun delete(context: Context, id: String) {
        write(context, all(context).filterNot { it.id == id })
    }

    fun create(context: Context, name: String): Setlist {
        val s = Setlist(UUID.randomUUID().toString(), name.trim().ifBlank { "Repertorio" }, emptyList(), System.currentTimeMillis())
        save(context, s)
        return s
    }

    /** Agrega al final; devuelve false si la canción ya estaba. */
    fun add(context: Context, id: String, entry: MediaEntry): Boolean {
        val s = get(context, id) ?: return false
        if (s.items.any { it.uri == entry.uri }) return false
        save(context, s.copy(items = s.items + entry))
        return true
    }

    private fun write(context: Context, lists: List<Setlist>) {
        val arr = JSONArray()
        lists.forEach { arr.put(toJson(it)) }
        val tmp = File(context.filesDir, "repertorios.json.tmp")
        tmp.writeText(JSONObject().put("version", 1).put("repertorios", arr).toString())
        tmp.renameTo(file(context))
    }

    private fun toJson(s: Setlist): JSONObject {
        val items = JSONArray()
        s.items.forEach { e ->
            items.put(
                JSONObject()
                    .put("uri", e.uri).put("titulo", e.title).put("artista", e.artist)
                    .put("album", e.album).put("archivo", e.displayName).put("duracion", e.durationMs)
                    .put("video", e.isVideo).put("letra", e.lyricsUri ?: "").put("mod", e.modified),
            )
        }
        return JSONObject().put("id", s.id).put("nombre", s.name).put("creado", s.created).put("canciones", items)
    }

    private fun fromJson(o: JSONObject): Setlist {
        val arr = o.optJSONArray("canciones") ?: JSONArray()
        val items = (0 until arr.length()).mapNotNull { i ->
            arr.optJSONObject(i)?.let { e ->
                MediaEntry(
                    uri = e.optString("uri"),
                    title = e.optString("titulo"),
                    artist = e.optString("artista"),
                    album = e.optString("album"),
                    displayName = e.optString("archivo"),
                    durationMs = e.optLong("duracion"),
                    isVideo = e.optBoolean("video"),
                    lyricsUri = e.optString("letra").ifBlank { null },
                    modified = e.optLong("mod"),
                )
            }
        }.filter { it.uri.isNotBlank() }
        return Setlist(o.optString("id"), o.optString("nombre"), items, o.optLong("creado"))
    }

    /** Texto para compartir por WhatsApp, correo, etc. */
    fun asText(s: Setlist): String = buildString {
        append("🎤 ").append(s.name).append('\n')
        s.items.forEachIndexed { i, e ->
            append(i + 1).append(". ").append(e.title)
            if (e.artist.isNotBlank()) append(" — ").append(e.artist)
            append('\n')
        }
        append("\n(").append(s.items.size).append(" canciones · VozPlayer · Yojanes Producciones)")
    }
}
