package com.yojanes.vozplayer

import android.content.Context
import android.media.MediaMetadataRetriever
import android.net.Uri
import org.json.JSONObject
import java.io.File

/**
 * Completa duración y artista leyendo las etiquetas de cada archivo de la carpeta.
 *
 * Leer etiquetas exige abrir cada archivo, lo cual es lento y compite con el reproductor.
 * Por eso: lo ya leído se guarda y se aplica al instante, y lo nuevo se lee por tandas
 * pequeñas (ver MainActivity), guardando el avance después de cada tanda.
 */
class MetadataEnricher(private val context: Context) {

    private val cacheFile = File(context.filesDir, "metadatos.json")
    private val cache: JSONObject =
        runCatching { JSONObject(cacheFile.readText()) }.getOrElse { JSONObject() }

    fun isCached(e: MediaEntry): Boolean = cache.optJSONObject(e.uri)?.optLong("m") == e.modified

    /** Aplica solo lo que ya está guardado (instantáneo, no abre archivos). */
    fun applyCached(entries: List<MediaEntry>): List<MediaEntry> =
        entries.map { e -> cache.optJSONObject(e.uri)?.takeIf { it.optLong("m") == e.modified }?.let { merge(e, it) } ?: e }

    /**
     * Lee las etiquetas de una tanda de archivos y guarda el avance.
     * Antes de cada archivo consulta [shouldPause]: si el reproductor necesita el
     * almacenamiento, se detiene enseguida (lo leído hasta ahí queda guardado).
     */
    fun readBatch(batch: List<MediaEntry>, shouldPause: () -> Boolean = { false }): Map<String, MediaEntry> {
        val out = HashMap<String, MediaEntry>()
        for (e in batch) {
            if (shouldPause()) break
            val info = read(e.uri, e.modified)
            cache.put(e.uri, info)
            out[e.uri] = merge(e, info)
        }
        if (out.isNotEmpty()) runCatching { cacheFile.writeText(cache.toString()) }
        return out
    }

    private fun merge(e: MediaEntry, info: JSONObject): MediaEntry {
        val tagTitle = info.optString("t")
        val tagArtist = info.optString("a")
        val tagAlbum = info.optString("b")
        return e.copy(
            durationMs = info.optLong("d").takeIf { it > 0 } ?: e.durationMs,
            artist = e.artist.ifBlank { tagArtist },
            album = listOf(
                tagTitle.takeIf { it.isNotBlank() && !it.equals(e.title, ignoreCase = true) },
                tagArtist.takeIf { it.isNotBlank() && !it.equals(e.artist, ignoreCase = true) && e.artist.isNotBlank() },
                tagAlbum.takeIf { it.isNotBlank() },
            ).filterNotNull().joinToString(" · "),
        )
    }

    private fun read(uri: String, modified: Long): JSONObject {
        val o = JSONObject().put("m", modified)
        val r = MediaMetadataRetriever()
        try {
            context.contentResolver.openFileDescriptor(Uri.parse(uri), "r")?.use { pfd ->
                r.setDataSource(pfd.fileDescriptor)
                o.put("d", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L)
                o.put("t", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE).orEmpty().trim())
                o.put("a", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST).orEmpty().trim())
                o.put("b", r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM).orEmpty().trim())
            }
        } catch (_: Exception) {
            // Archivo dañado o formato no soportado: se deja sin etiquetas (y no se vuelve a intentar).
        } finally {
            runCatching { r.release() }
        }
        return o
    }
}
