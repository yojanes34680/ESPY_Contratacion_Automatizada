package com.yojanes.vozplayer

/**
 * Entiende cuando el cantante pide una canción del repertorio por su número:
 * "la cinco", "número 12", "pon la tres", "canción 7", "8".
 * Solo responde si la frase es básicamente un número (para no confundir títulos con números).
 */
object SetlistVoice {

    private val WORDS = mapOf(
        "uno" to 1, "una" to 1, "primera" to 1, "primero" to 1,
        "dos" to 2, "segunda" to 2, "segundo" to 2,
        "tres" to 3, "tercera" to 3, "tercero" to 3,
        "cuatro" to 4, "cuarta" to 4, "cinco" to 5, "quinta" to 5,
        "seis" to 6, "sexta" to 6, "siete" to 7, "septima" to 7,
        "ocho" to 8, "octava" to 8, "nueve" to 9, "novena" to 9,
        "diez" to 10, "decima" to 10, "once" to 11, "doce" to 12, "trece" to 13,
        "catorce" to 14, "quince" to 15, "dieciseis" to 16, "diecisiete" to 17,
        "dieciocho" to 18, "diecinueve" to 19, "veinte" to 20, "veintiuno" to 21,
        "veintiuna" to 21, "veintidos" to 22, "veintitres" to 23, "veinticuatro" to 24,
        "veinticinco" to 25, "veintiseis" to 26, "veintisiete" to 27, "veintiocho" to 28,
        "veintinueve" to 29, "treinta" to 30,
    )
    private val FILLERS = setOf(
        "la", "el", "numero", "num", "no", "cancion", "tema", "pista", "pon", "ponme", "reproduce",
        "reproducir", "toca", "tocar", "canta", "cantar", "vamos", "con", "a", "por", "favor", "de", "repertorio",
    )

    /** Número de canción pedido (1, 2, 3...) o null si la frase no es un número. */
    fun parseNumber(text: String): Int? {
        val tokens = VoiceSearchMatcher.normalize(text).split(' ').filter { it.isNotBlank() && it !in FILLERS }
        if (tokens.isEmpty() || tokens.size > 3) return null
        // "treinta y dos" → 32
        if (tokens.size == 3 && tokens[0] == "treinta" && tokens[1] == "y") {
            val unit = WORDS[tokens[2]] ?: return null
            return if (unit in 1..9) 30 + unit else null
        }
        if (tokens.size != 1) return null
        val t = tokens[0]
        return t.toIntOrNull()?.takeIf { it in 1..999 } ?: WORDS[t]
    }
}
