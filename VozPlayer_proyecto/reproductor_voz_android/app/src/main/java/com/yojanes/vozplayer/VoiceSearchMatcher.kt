package com.yojanes.vozplayer

import java.text.Normalizer

/**
 * Motor de búsqueda difusa pensado para lo que devuelve el reconocimiento de voz:
 *  - ignora mayúsculas, tildes y signos ("Canción" == "cancion");
 *  - descarta palabras de orden ("pon", "reproduce", "la canción de"...);
 *  - tolera errores de dictado (distancia de Levenshtein) y confusiones fonéticas
 *    típicas del español (b/v, s/z/c, ll/y, h muda, qu/k...);
 *  - busca en título, artista, álbum y nombre del archivo.
 */
object VoiceSearchMatcher {

    /** Puntaje mínimo para que un archivo aparezca en la lista filtrada. */
    const val LIST_THRESHOLD = 0.55

    /** Puntaje mínimo para reproducir automáticamente tras una búsqueda por voz. */
    const val AUTO_PLAY_THRESHOLD = 0.72

    data class Scored(val entry: MediaEntry, val score: Double)

    data class VoiceMatch(val spokenText: String, val best: Scored)

    private val STOPWORDS = setOf(
        "pon", "ponme", "poner", "pone", "reproduce", "reproducir", "reproduceme", "reproducime",
        "toca", "tocar", "tocame", "busca", "buscar", "buscame", "abre", "abrir", "abreme",
        "quiero", "escuchar", "oir", "ver", "mira", "mirar", "dame",
        "la", "el", "los", "las", "lo", "de", "del", "un", "una", "y", "a", "al", "mi", "me",
        "cancion", "canciones", "tema", "video", "videos", "musica", "audio", "archivo",
        "por", "favor", "porfa", "play",
    )

    private val MARKS = Regex("\\p{Mn}+")
    private val NON_ALNUM = Regex("[^a-z0-9ñ]+")
    private val SPACES = Regex("\\s+")
    private val REPEATED = Regex("(.)\\1+")

    fun normalize(text: String): String {
        val noAccents = MARKS.replace(Normalizer.normalize(text, Normalizer.Form.NFD), "")
        return SPACES.replace(NON_ALNUM.replace(noAccents.lowercase(), " ").trim(), " ")
    }

    /** Aproximación fonética del español para tolerar errores del dictado. */
    fun phonetic(normalized: String): String {
        var s = normalized
        s = s.replace("ph", "f").replace("qu", "k").replace("ch", "x")
            .replace("ce", "se").replace("ci", "si")
            .replace("ge", "je").replace("gi", "ji")
            .replace("ll", "y").replace("c", "k").replace("z", "s")
            .replace("v", "b").replace("w", "u").replace("h", "")
            .replace("ñ", "n")
        // Colapsa letras repetidas ("rr" -> "r", "ss" -> "s").
        return REPEATED.replace(s, "$1")
    }

    fun levenshtein(a: String, b: String): Int {
        if (a == b) return 0
        if (a.isEmpty()) return b.length
        if (b.isEmpty()) return a.length
        var prev = IntArray(b.length + 1) { it }
        var curr = IntArray(b.length + 1)
        for (i in 1..a.length) {
            curr[0] = i
            for (j in 1..b.length) {
                val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                curr[j] = minOf(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
            }
            val tmp = prev; prev = curr; curr = tmp
        }
        return prev[b.length]
    }

    fun similarity(a: String, b: String): Double {
        val max = maxOf(a.length, b.length)
        if (max == 0) return 1.0
        // Si las longitudes son muy distintas, el parecido no puede ser alto: se evita el cálculo.
        if (kotlin.math.abs(a.length - b.length).toDouble() / max > 0.6) {
            return 1.0 - kotlin.math.abs(a.length - b.length).toDouble() / max
        }
        return 1.0 - levenshtein(a, b).toDouble() / max
    }

    /** Palabras relevantes de la consulta (sin palabras de orden). */
    fun queryTokens(query: String): List<String> {
        val all = normalize(query).split(' ').filter { it.isNotBlank() }
        val useful = all.filter { it !in STOPWORDS }
        return useful.ifEmpty { all }
    }

    // ------------------------------------------------------------ Índice preparado

    /** Campo de búsqueda ya normalizado, con su versión fonética y sus palabras. */
    private class Field(val text: String) {
        val phon = phonetic(text)
        val tokens = text.split(' ').filter { it.isNotBlank() }
        val phonTokens = tokens.map { phonetic(it) }
    }

    /** Archivo listo para buscar: se prepara una sola vez, no en cada letra escrita. */
    class Prepared internal constructor(val entry: MediaEntry) {
        internal val fields: List<Any> = listOf(
            entry.title,
            entry.artist,
            entry.album,
            entry.fileNameWithoutExtension,
            "${entry.artist} ${entry.title}",
        ).map { normalize(it) }.filter { it.isNotBlank() }.distinct().map { Field(it) }
    }

    fun prepare(entries: List<MediaEntry>): List<Prepared> = entries.map { Prepared(it) }

    private class Query(raw: String) {
        val tokens = queryTokens(raw)
        val phonTokens = tokens.map { phonetic(it) }
        val clean = tokens.joinToString(" ")
        val phon = phonetic(clean)
    }

    private fun score(q: Query, p: Prepared): Double {
        if (q.tokens.isEmpty()) return 0.0
        var best = 0.0
        for (any in p.fields) {
            val f = any as Field
            val candidate = when {
                f.text == q.clean -> 1.0
                " ${f.text} ".contains(" ${q.clean} ") || (q.clean.length >= 4 && f.text.contains(q.clean)) ->
                    0.9 + 0.1 * q.clean.length / f.text.length
                else -> maxOf(
                    similarity(q.clean, f.text),
                    similarity(q.phon, f.phon),
                    tokenScore(q, f) * 0.95,
                )
            }
            if (candidate > best) best = candidate
            if (best >= 1.0) break
        }
        return best.coerceIn(0.0, 1.0)
    }

    private fun tokenScore(q: Query, f: Field): Double {
        if (f.tokens.isEmpty()) return 0.0
        var total = 0.0
        for (i in q.tokens.indices) {
            val t = q.tokens[i]
            val tp = q.phonTokens[i]
            var bestToken = 0.0
            for (j in f.tokens.indices) {
                val ft = f.tokens[j]
                var s = maxOf(similarity(t, ft), similarity(tp, f.phonTokens[j]))
                if (t.length >= 3 && ft.startsWith(t)) s = maxOf(s, 0.88)
                if (s > bestToken) bestToken = s
                if (bestToken >= 1.0) break
            }
            total += bestToken
        }
        return total / q.tokens.size
    }

    /** Puntaje 0..1 de qué tan bien la consulta describe el archivo. */
    fun score(query: String, entry: MediaEntry): Double = score(Query(query), Prepared(entry))

    /** Ordena los archivos por relevancia y descarta los que no se parecen. */
    fun rank(
        query: String,
        entries: List<MediaEntry>,
        threshold: Double = LIST_THRESHOLD,
    ): List<Scored> = rankPrepared(query, prepare(entries), threshold)

    fun rankPrepared(
        query: String,
        prepared: List<Prepared>,
        threshold: Double = LIST_THRESHOLD,
    ): List<Scored> {
        val q = Query(query)
        return prepared.asSequence()
            .map { Scored(it.entry, score(q, it)) }
            .filter { it.score >= threshold }
            .sortedWith(compareByDescending<Scored> { it.score }.thenBy { it.entry.title.lowercase() })
            .toList()
    }

    /**
     * El reconocedor de voz devuelve varias transcripciones posibles; se elige
     * la que produzca la mejor coincidencia en la biblioteca.
     */
    fun bestVoiceMatch(alternatives: List<String>, entries: List<MediaEntry>): VoiceMatch? =
        bestVoiceMatchPrepared(alternatives, prepare(entries))

    fun bestVoiceMatchPrepared(alternatives: List<String>, prepared: List<Prepared>): VoiceMatch? {
        var result: VoiceMatch? = null
        for (spoken in alternatives.distinct()) {
            if (spoken.isBlank()) continue
            val q = Query(spoken)
            var top: Scored? = null
            for (p in prepared) {
                val sc = score(q, p)
                if (top == null || sc > top.score) top = Scored(p.entry, sc)
            }
            if (top != null && (result == null || top.score > result.best.score)) {
                result = VoiceMatch(spoken, top)
            }
        }
        return result
    }
}
