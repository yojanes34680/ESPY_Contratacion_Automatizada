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

    /** Resultado de una búsqueda en internet, con el detalle de lo que pasó. */
    sealed class OnlineResult {
        data class Found(val lyrics: Lyrics) : OnlineResult()
        data class NotFound(val searched: List<String>) : OnlineResult()
        data class NoConnection(val detail: String) : OnlineResult()
    }

    private class NetworkFailure(message: String) : Exception(message)

    /**
     * Busca en internet y, si encuentra, guarda la letra para usarla sin conexión.
     * Prueba el nombre en los dos órdenes ("Cantante - Canción" y "Canción - Cantante"),
     * identifica al cantante si no se conoce y usa una segunda fuente si la primera no tiene la letra.
     */
    fun searchOnline(entry: MediaEntry, artistHint: String, titleHint: String): OnlineResult {
        val title = TrackNameParser.cleanForLyrics(titleHint)
        val artist = TrackNameParser.cleanForLyrics(artistHint)
        if (title.isBlank() && artist.isBlank()) return OnlineResult.NotFound(emptyList())
        val durationSec = (entry.durationMs / 1000).toInt()

        // Combinaciones (cantante, canción) a probar, de la más probable a la menos.
        val pairs = linkedSetOf<Pair<String, String>>()
        if (title.isNotBlank()) pairs += artist to title
        if (artist.isNotBlank() && title.isNotBlank()) pairs += title to artist
        if (artist.isNotBlank() && title.isBlank()) pairs += "" to artist
        val fileName = TrackNameParser.cleanForLyrics(
            entry.fileNameWithoutExtension.replace('_', ' ').replace(Regex("^\\s*\\d{1,3}\\s*[-._)]\\s*"), ""),
        )
        val searched = pairs.map { (a, t) -> if (a.isBlank()) "«$t»" else "«$t» de «$a»" }.toMutableList()

        try {
            val candidates = mutableListOf<JSONObject>()
            for ((a, t) in pairs) {
                if (a.isNotBlank()) {
                    (getJson(
                        "https://lrclib.net/api/get?" + q("artist_name", a) + "&" + q("track_name", t) +
                            (if (durationSec > 0) "&duration=$durationSec" else ""),
                    ) as? JSONObject)?.let { candidates += it }
                    candidates += array(getJson("https://lrclib.net/api/search?" + q("track_name", t) + "&" + q("artist_name", a)))
                    if (usable(candidates).isEmpty()) {
                        candidates += array(getJson("https://lrclib.net/api/search?" + q("q", "$a $t")))
                    }
                } else {
                    candidates += array(getJson("https://lrclib.net/api/search?" + q("track_name", t)))
                    if (usable(candidates).isEmpty()) candidates += array(getJson("https://lrclib.net/api/search?" + q("q", t)))
                }
                if (usable(candidates).isNotEmpty()) break
            }
            if (usable(candidates).isEmpty() && fileName.isNotBlank()) {
                searched += "«$fileName»"
                candidates += array(getJson("https://lrclib.net/api/search?" + q("q", fileName)))
            }

            val best = usable(candidates).maxByOrNull { o ->
                maxOf(score(o, artist, title, durationSec), score(o, title, artist, durationSec))
            }
            if (best != null) {
                val lrc = best.optString("syncedLyrics").takeUnless { it == "null" }.orEmpty()
                val plain = best.optString("plainLyrics").takeUnless { it == "null" }.orEmpty()
                    .ifBlank { LrcParser.toPlain(lrc) }
                return OnlineResult.Found(
                    save(entry, best.optString("artistName").ifBlank { artist }, best.optString("trackName").ifBlank { title }, lrc, plain),
                )
            }

            // Segunda fuente (letra sin sincronizar): necesita cantante y canción.
            for ((a, t) in pairs) {
                if (a.isBlank() || t.isBlank()) continue
                val o = getJson(
                    "https://api.lyrics.ovh/v1/" + URLEncoder.encode(a, "UTF-8").replace("+", "%20") +
                        "/" + URLEncoder.encode(t, "UTF-8").replace("+", "%20"),
                ) as? JSONObject
                val text = o?.optString("lyrics").orEmpty().replace("\r\n", "\n").trim()
                if (text.isNotBlank()) return OnlineResult.Found(save(entry, a, t, "", text))
            }
        } catch (e: NetworkFailure) {
            return OnlineResult.NoConnection(e.message.orEmpty())
        }
        return OnlineResult.NotFound(searched)
    }

    private fun usable(list: List<JSONObject>) = list.filter {
        !it.optBoolean("instrumental") &&
            (it.optString("syncedLyrics").let { s -> s.isNotBlank() && s != "null" } ||
                it.optString("plainLyrics").let { s -> s.isNotBlank() && s != "null" })
    }

    private fun save(entry: MediaEntry, artist: String, title: String, lrc: String, plain: String): Lyrics {
        val result = Lyrics(artist, title, LrcParser.parse(lrc), plain, Source.INTERNET)
        runCatching {
            cacheFile(entry.uri).writeText(
                JSONObject()
                    .put("artista", artist)
                    .put("titulo", title)
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

    /** null si no hay resultado (404, respuesta vacía); NetworkFailure si no se pudo conectar. */
    private fun getJson(url: String): Any? {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 10000
            readTimeout = 15000
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("Accept", "application/json")
        }
        try {
            val code = try {
                conn.responseCode
            } catch (e: java.io.IOException) {
                throw NetworkFailure(e.javaClass.simpleName + ": " + e.message.orEmpty())
            }
            if (code != 200) return null
            val body = conn.inputStream.use { it.readBytes().toString(Charsets.UTF_8) }.trim()
            return when {
                body.startsWith("[") -> JSONArray(body)
                body.startsWith("{") -> JSONObject(body)
                else -> null
            }
        } catch (e: NetworkFailure) {
            throw e
        } catch (_: Exception) {
            return null
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
