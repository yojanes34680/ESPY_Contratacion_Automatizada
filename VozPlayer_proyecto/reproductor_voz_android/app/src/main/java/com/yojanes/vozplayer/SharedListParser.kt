package com.yojanes.vozplayer

/**
 * Lee una lista compartida como texto (por WhatsApp, notas, etc.) para importarla:
 *
 *   🎤 Serenata
 *   1. Amor Indio — Caballero Gaucho
 *   2. No Quiero Envejecer — Lucho y Rafa
 *   (2 canciones · VozPlayer · Yojanes Producciones)
 *
 * También acepta listas escritas a mano: una canción por línea o separadas por comas.
 */
object SharedListParser {

    data class Song(val title: String, val artist: String) {
        val query: String get() = if (artist.isBlank()) title else "$title $artist"
    }

    data class Parsed(val name: String?, val songs: List<Song>)

    private val NUMBER = Regex("^\\s*\\d{1,3}\\s*[.)\\-:]\\s*")
    private val ARTIST_SEP = Regex("\\s+[—–]\\s+|\\s+-\\s+")
    private val FOOTER = Regex("^\\(.*(canci[oó]n|VozPlayer).*\\)$", RegexOption.IGNORE_CASE)
    private val HEADER = Regex("^(🎤|🎵|🎶|♪)\\s*")

    fun parse(text: String): Parsed {
        val lines = text.lines().map { it.trim() }.filter { it.isNotBlank() }
        var name: String? = null
        val songs = mutableListOf<Song>()
        for (line in lines) {
            when {
                FOOTER.matches(line) -> continue
                HEADER.containsMatchIn(line) && name == null && !NUMBER.containsMatchIn(line) ->
                    name = line.replace(HEADER, "").trim().ifBlank { null }
                NUMBER.containsMatchIn(line) -> songs += toSong(line.replace(NUMBER, ""))
                else -> DictationSplitter.split(line).forEach { songs += toSong(it) }
            }
        }
        return Parsed(name, songs.filter { it.title.isNotBlank() }.distinct())
    }

    private fun toSong(raw: String): Song {
        val parts = raw.trim().split(ARTIST_SEP, limit = 2)
        return if (parts.size == 2) Song(parts[0].trim(), parts[1].trim()) else Song(raw.trim(), "")
    }
}
