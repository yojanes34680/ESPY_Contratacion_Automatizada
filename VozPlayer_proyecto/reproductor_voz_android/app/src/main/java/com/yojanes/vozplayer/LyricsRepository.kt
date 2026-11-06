package com.yojanes.vozplayer

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.security.MessageDigest

/**
 * Letras de canciones, en este orden:
 *  1. Archivo .lrc o .txt con el mismo nombre de la pista, en la misma carpeta.
 *  2. Letra guardada en el teléfono de una búsqueda anterior (funciona sin internet).
 *  3. Búsqueda en internet (LRCLIB, gratuito), identificando también al cantante.
 */
class LyricsRepository(private val context: Context) {

    enum class Source { FILE, SAVED, INTERNET }

    data class Lyrics(
        val artist: String,
        val title: String,
        val synced: List<LyricLine>,
        val plain: String,
        val source: Source,
    )

    private val dir = File(context.filesDir, "letras").apply { mkdirs() }

    fun loadLocal(entry: MediaEntry): Lyrics? {
        entry.lyricsUri?.let { uri ->
            val text = runCatching {
                context.contentResolver.openInputStream(Uri.parse(uri))?.use { it.readBytes().toString(Charsets.UTF_8) }
            }.getOrNull()
            if (!text.isNullOrBlank()) {
                return Lyrics(entry.artist, entry.title, LrcParser.parse(text), LrcParser.toPlain(text), Source.FILE)
            }
        }
        val saved = cacheFile(entry.uri)
        if (saved.exists()) {
            runCatching {
                val o = JSONObject(saved.readText())
                val lrc = o.optString("lrc")
                return Lyrics(
                    o.optString("artista"), o.optString("titulo"),
                    LrcParser.parse(lrc), o.optString("texto").ifBlank { LrcParser.toPlain(lrc) },
                    Source.SAVED,
                )
            }
        }
        return null
    }

    fun hasInternet(): Boolean {
        val cm = context.getSystemService(ConnectivityManager::class.java) ?: return false
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    /** Busca en internet y, si encuentra, guarda la letra para usarla sin conexión. */
    fun searchOnline(entry: MediaEntry, artistHint: String, titleHint: String): Lyrics? {
        val title = TrackNameParser.cleanForLyrics(titleHint)
        val artist = TrackNameParser.cleanForLyrics(artistHint)
        if (title.isBlank()) return null
        val durationSec = (entry.durationMs / 1000).toInt()

        var best: JSONObject? = null
        if (artist.isNotBlank()) {
            best = getJson(
                "https://lrclib.net/api/get?" + q("artist_name", artist) + "&" + q("track_name", title) +
                    (if (durationSec > 0) "&duration=$durationSec" else ""),
            ) as? JSONObject
            if (best != null && best.optBoolean("instrumental")) best = null
        }
        if (best == null) {
            val candidates = mutableListOf<JSONObject>()
            if (artist.isNotBlank()) {
                candidates += array(getJson("https://lrclib.net/api/search?" + q("track_name", title) + "&" + q("artist_name", artist)))
                if (candidates.isEmpty()) candidates += array(getJson("https://lrclib.net/api/search?" + q("q", "$artist $title")))
            }
            if (candidates.isEmpty()) candidates += array(getJson("https://lrclib.net/api/search?" + q("track_name", title)))
            if (candidates.isEmpty()) candidates += array(getJson("https://lrclib.net/api/search?" + q("q", title)))
            best = candidates
                .filter { !it.optBoolean("instrumental") && (it.optString("syncedLyrics").isNotBlank() || it.optString("plainLyrics").isNotBlank()) }
                .maxByOrNull { score(it, artist, title, durationSec) }
        }
        val found = best ?: return null
        val lrc = found.optString("syncedLyrics").takeUnless { it == "null" }.orEmpty()
        val plain = found.optString("plainLyrics").takeUnless { it == "null" }.orEmpty().ifBlank { LrcParser.toPlain(lrc) }
        if (lrc.isBlank() && plain.isBlank()) return null
        val result = Lyrics(
            found.optString("artistName").ifBlank { artist },
            found.optString("trackName").ifBlank { title },
            LrcParser.parse(lrc), plain, Source.INTERNET,
        )
        runCatching {
            cacheFile(entry.uri).writeText(
                JSONObject()
                    .put("artista", result.artist)
                    .put("titulo", result.title)
                    .put("lrc", lrc)
                    .put("texto", plain)
                    .toString(),
            )
        }
        return result
    }

    fun forget(entry: MediaEntry) {
        cacheFile(entry.uri).delete()
    }

    private fun score(o: JSONObject, artist: String, title: String, durationSec: Int): Double {
        var s = 0.0
        if (o.optString("syncedLyrics").let { it.isNotBlank() && it != "null" }) s += 1.0
        s += 2 * VoiceSearchMatcher.similarity(
            VoiceSearchMatcher.normalize(title), VoiceSearchMatcher.normalize(o.optString("trackName")),
        )
        if (artist.isNotBlank()) {
            s += 2 * VoiceSearchMatcher.similarity(
                VoiceSearchMatcher.normalize(artist), VoiceSearchMatcher.normalize(o.optString("artistName")),
            )
        }
        val d = o.optDouble("duration", 0.0)
        if (durationSec > 0 && d > 0 && kotlin.math.abs(d - durationSec) <= 4) s += 1.0
        return s
    }

    private fun array(any: Any?): List<JSONObject> {
        val arr = any as? JSONArray ?: return emptyList()
        return (0 until minOf(arr.length(), 20)).mapNotNull { arr.optJSONObject(it) }
    }

    private fun q(name: String, value: String) = name + "=" + URLEncoder.encode(value, "UTF-8")

    private fun getJson(url: String): Any? {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8000
            readTimeout = 10000
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("Accept", "application/json")
        }
        return try {
            if (conn.responseCode != 200) return null
            val body = conn.inputStream.use { it.readBytes().toString(Charsets.UTF_8) }.trim()
            if (body.startsWith("[")) JSONArray(body) else JSONObject(body)
        } catch (_: Exception) {
            null
        } finally {
            conn.disconnect()
        }
    }

    private fun cacheFile(uri: String): File {
        val hash = MessageDigest.getInstance("SHA-1").digest(uri.toByteArray())
            .joinToString("") { "%02x".format(it) }
        return File(dir, "$hash.json")
    }

    companion object {
        private const val USER_AGENT =
            "VozPlayer/1.1 (https://github.com/yojanes34680/ESPY_Contratacion_Automatizada)"
    }
}
