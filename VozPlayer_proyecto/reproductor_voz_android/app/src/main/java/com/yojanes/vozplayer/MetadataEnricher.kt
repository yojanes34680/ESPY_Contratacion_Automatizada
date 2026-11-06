package com.yojanes.vozplayer

import android.content.Context
import android.media.MediaMetadataRetriever
import android.net.Uri
import org.json.JSONObject
import java.io.File

/**
 * Completa duración y artista leyendo las etiquetas de cada archivo de la carpeta.
 * Guarda el resultado para que la próxima apertura sea instantánea.
 */
class MetadataEnricher(private val context: Context) {

    private val cacheFile = File(context.filesDir, "metadatos.json")

    fun enrich(entries: List<MediaEntry>): List<MediaEntry> {
        val cache = runCatching { JSONObject(cacheFile.readText()) }.getOrElse { JSONObject() }
        var changed = false
        val result = entries.map { e ->
            var info = cache.optJSONObject(e.uri)
            if (info == null || info.optLong("m") != e.modified) {
                info = read(e.uri, e.modified)
                cache.put(e.uri, info)
                changed = true
            }
            val tagTitle = info.optString("t")
            val tagArtist = info.optString("a")
            val tagAlbum = info.optString("b")
            e.copy(
                durationMs = info.optLong("d").takeIf { it > 0 } ?: e.durationMs,
                artist = e.artist.ifBlank { tagArtist },
                album = listOf(
                    tagTitle.takeIf { it.isNotBlank() && !it.equals(e.title, ignoreCase = true) },
                    tagArtist.takeIf { it.isNotBlank() && !it.equals(e.artist, ignoreCase = true) && e.artist.isNotBlank() },
                    tagAlbum.takeIf { it.isNotBlank() },
                ).filterNotNull().joinToString(" · "),
            )
        }
        if (changed) runCatching { cacheFile.writeText(cache.toString()) }
        return result
    }

    private fun read(uri: String, modified: Long): JSONObject {
        val o = JSONObject().put("m", modified)
        val r = MediaMetadataRetriever()
        try {
            r.setDataSource(context, Uri.parse(uri))
            o.put("d", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L)
            o.put("t", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE).orEmpty().trim())
            o.put("a", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST).orEmpty().trim())
            o.put("b", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM).orEmpty().trim())
        } catch (_: Exception) {
            // Archivo dañado o formato no soportado: se deja sin etiquetas.
        } finally {
            runCatching { r.release() }
        }
        return o
    }
}
