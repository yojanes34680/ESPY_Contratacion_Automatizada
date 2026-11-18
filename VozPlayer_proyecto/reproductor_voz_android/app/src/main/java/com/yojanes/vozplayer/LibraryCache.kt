package com.yojanes.vozplayer

import android.content.Context
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/**
 * Guarda la última lista de pistas de cada carpeta para mostrarla AL INSTANTE al abrir
 * la app. Recorrer una carpeta con el selector de Android es lento (pregunta archivo por
 * archivo); ese recorrido ahora se hace después, en segundo plano, solo para detectar cambios.
 */
object LibraryCache {

    private fun file(context: Context, folder: Uri): File {
        val hash = MessageDigest.getInstance("SHA-1").digest(folder.toString().toByteArray())
            .joinToString("") { "%02x".format(it) }
        return File(File(context.filesDir, "biblioteca").apply { mkdirs() }, "$hash.json")
    }

    fun load(context: Context, folder: Uri): List<MediaEntry>? = runCatching {
        val arr = JSONArray(file(context, folder).readText())
        (0 until arr.length()).mapNotNull { arr.optJSONObject(it)?.let { o -> EntryJson.from(o) } }
    }.getOrNull()

    fun save(context: Context, folder: Uri, entries: List<MediaEntry>) {
        runCatching {
            val arr = JSONArray()
            entries.forEach { arr.put(EntryJson.to(it)) }
            val f = file(context, folder)
            val tmp = File(f.parentFile, f.name + ".tmp")
            tmp.writeText(arr.toString())
            tmp.renameTo(f)
        }
    }

    /** ¿Son los mismos archivos (mismas direcciones y fechas de modificación)? */
    fun sameFiles(a: List<MediaEntry>, b: List<MediaEntry>): Boolean =
        a.size == b.size && a.map { it.uri to it.modified }.toSet() == b.map { it.uri to it.modified }.toSet()
}

/** Formato JSON de una pista (compartido por la biblioteca guardada y los repertorios). */
object EntryJson {
    fun to(e: MediaEntry): JSONObject = JSONObject()
        .put("uri", e.uri).put("titulo", e.title).put("artista", e.artist)
        .put("album", e.album).put("archivo", e.displayName).put("duracion", e.durationMs)
        .put("video", e.isVideo).put("letra", e.lyricsUri ?: "").put("mod", e.modified)

    fun from(o: JSONObject): MediaEntry? {
        val uri = o.optString("uri")
        if (uri.isBlank()) return null
        return MediaEntry(
            uri = uri,
            title = o.optString("titulo"),
            artist = o.optString("artista"),
            album = o.optString("album"),
            displayName = o.optString("archivo"),
            durationMs = o.optLong("duracion"),
            isVideo = o.optBoolean("video"),
            lyricsUri = o.optString("letra").ifBlank { null },
            modified = o.optLong("mod"),
        )
    }
}

/** Registro de tiempos para el diagnóstico de velocidad (mantener presionado el logo). */
object PerfLog {
    private val lines = ArrayDeque<String>()
    private val fmt = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.ROOT)

    @Synchronized
    fun add(msg: String) {
        lines.addLast(fmt.format(java.util.Date()) + "  " + msg)
        while (lines.size > 40) lines.removeFirst()
    }

    @Synchronized
    fun dump(): String = if (lines.isEmpty()) "" else lines.joinToString("\n")
}
