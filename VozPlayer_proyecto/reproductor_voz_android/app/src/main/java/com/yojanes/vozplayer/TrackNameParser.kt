package com.yojanes.vozplayer

/**
 * Deduce artista y título a partir del nombre del archivo, p. ej.
 * "03 - Marc Anthony - Vivir mi vida (Pista).mp3" → artista "Marc Anthony", título "Vivir mi vida (Pista)".
 */
object TrackNameParser {

    data class Parsed(val artist: String, val title: String)

    private val LEADING_NUMBER = Regex("^\\s*\\d{1,3}\\s*[-._)]\\s*")
    private val SEPARATOR = Regex("\\s+[-–—]\\s+")

    fun parse(fileName: String): Parsed {
        var base = fileName.substringBeforeLast('.', fileName).replace('_', ' ').trim()
        base = base.replace(LEADING_NUMBER, "").replace(Regex("\\s+"), " ").trim()
        val parts = base.split(SEPARATOR).map { it.trim() }.filter { it.isNotEmpty() }
        return if (parts.size >= 2) {
            Parsed(parts[0], parts.drop(1).joinToString(" - "))
        } else {
            Parsed("", base)
        }
    }

    private val NOISE_BRACKETS = Regex(
        "(?i)[(\\[][^)\\]]*(pista|karaoke|instrumental|cover|versi[oó]n|letra|lyrics?|official|oficial|" +
            "video|audio|remaster\\w*|\\bhd\\b|\\bhq\\b|\\d{3,4}p|en vivo|live)[^)\\]]*[)\\]]",
    )
    private val NOISE_WORDS = Regex(
        "(?i)\\b(pista|karaoke|instrumental|con letra|video oficial|audio oficial|official video|lyrics|hd)\\b",
    )

    /** Quita marcas típicas de pistas ("(Pista)", "[Karaoke]", "HD"...) para buscar la letra. */
    fun cleanForLyrics(text: String): String =
        text.replace(NOISE_BRACKETS, " ")
            .replace(NOISE_WORDS, " ")
            .replace(Regex("\\s+"), " ")
            .trim(' ', '-', '–', '—', '_', '.')
}
