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

    fun normalize(text: String): String {
        val noAccents = Normalizer.normalize(text, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
        return noAccents.lowercase()
            .replace(Regex("[^a-z0-9ñ]+"), " ")
            .trim()
            .replace(Regex("\\s+"), " ")
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
        return s.replace(Regex("(.)\\1+"), "$1")
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
        return 1.0 - levenshtein(a, b).toDouble() / max
    }

    private fun bestSimilarity(a: String, b: String): Double =
        maxOf(similarity(a, b), similarity(phonetic(a), phonetic(b)))

    /** Palabras relevantes de la consulta (sin palabras de orden). */
    fun queryTokens(query: String): List<String> {
        val all = normalize(query).split(' ').filter { it.isNotBlank() }
        val useful = all.filter { it !in STOPWORDS }
        return useful.ifEmpty { all }
    }

    /** Puntaje 0..1 de qué tan bien la consulta describe el archivo. */
    fun score(query: String, entry: MediaEntry): Double {
        val tokens = queryTokens(query)
        if (tokens.isEmpty()) return 0.0
        val cleanQuery = tokens.joinToString(" ")

        val fields = listOf(
            entry.title,
            entry.artist,
            entry.album,
            entry.fileNameWithoutExtension,
            "${entry.artist} ${entry.title}",
        ).map { normalize(it) }.filter { it.isNotBlank() }.distinct()

        var best = 0.0
        for (field in fields) {
            val candidate = when {
                field == cleanQuery -> 1.0
                containsAsWords(field, cleanQuery) ->
                    0.9 + 0.1 * cleanQuery.length / field.length
                else -> maxOf(bestSimilarity(cleanQuery, field), tokenScore(tokens, field) * 0.95)
            }
            if (candidate > best) best = candidate
        }
        return best.coerceIn(0.0, 1.0)
    }

    private fun containsAsWords(field: String, query: String): Boolean =
        " $field ".contains(" $query ") || (query.length >= 4 && field.contains(query))

    /** Promedio, por cada palabra dicha, de su mejor parecido con alguna palabra del campo. */
    private fun tokenScore(tokens: List<String>, field: String): Double {
        val fieldTokens = field.split(' ').filter { it.isNotBlank() }
        if (fieldTokens.isEmpty()) return 0.0
        var total = 0.0
        for (t in tokens) {
            var bestToken = 0.0
            for (ft in fieldTokens) {
                val s = if (t.length >= 3 && ft.startsWith(t)) {
                    maxOf(0.88, bestSimilarity(t, ft))
                } else {
                    bestSimilarity(t, ft)
                }
                if (s > bestToken) bestToken = s
            }
            total += bestToken
        }
        return total / tokens.size
    }

    /** Ordena los archivos por relevancia y descarta los que no se parecen. */
    fun rank(
        query: String,
        entries: List<MediaEntry>,
        threshold: Double = LIST_THRESHOLD,
    ): List<Scored> =
        entries.asSequence()
            .map { Scored(it, score(query, it)) }
            .filter { it.score >= threshold }
            .sortedWith(compareByDescending<Scored> { it.score }.thenBy { it.entry.title.lowercase() })
            .toList()

    /**
     * El reconocedor de voz devuelve varias transcripciones posibles; se elige
     * la que produzca la mejor coincidencia en la biblioteca.
     */
    fun bestVoiceMatch(alternatives: List<String>, entries: List<MediaEntry>): VoiceMatch? {
        var result: VoiceMatch? = null
        for (spoken in alternatives) {
            if (spoken.isBlank()) continue
            val top = rank(spoken, entries, threshold = 0.0).firstOrNull() ?: continue
            if (result == null || top.score > result.best.score) {
                result = VoiceMatch(spoken, top)
            }
        }
        return result
    }
}
