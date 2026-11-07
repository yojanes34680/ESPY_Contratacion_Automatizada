package com.yojanes.vozplayer

/**
 * Separa un dictado con varias canciones: "amor indio, luego no quiero envejecer
 * y después la camisa negra" → ["amor indio", "no quiero envejecer", "la camisa negra"].
 * No separa por una "y" sola, porque muchos títulos y artistas la llevan ("Lucho y Rafa").
 */
object DictationSplitter {

    private const val CONNECTORS =
        "luego|despu[eé]s|enseguida|a continuaci[oó]n|siguiente|la siguiente|la otra|otra|tambi[eé]n"

    private val SEPARATORS = Regex(
        "\\s*[,;]\\s*|\\s+(?:y\\s+)?(?:$CONNECTORS)\\s+",
        RegexOption.IGNORE_CASE,
    )

    /** Conectores y órdenes al inicio de cada parte ("luego", "también", "agrega"...). */
    private val LEADING = Regex(
        "^(?:(?:y\\s+)?(?:$CONNECTORS)|agrega(?:r)?|agr[eé]game|a[nñ]ade|a[nñ]adir|pon(?:me)?|mete|incluye)\\s+",
        RegexOption.IGNORE_CASE,
    )

    fun split(text: String): List<String> =
        text.split(SEPARATORS)
            .map { part ->
                var p = part.trim()
                while (true) {
                    val next = p.replaceFirst(LEADING, "").trim()
                    if (next == p) break
                    p = next
                }
                p.trim(' ', '.', ',')
            }
            .filter { it.isNotBlank() }
}
