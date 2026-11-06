package com.yojanes.vozplayer

data class LyricLine(val timeMs: Long, val text: String)

/** Lector de letras sincronizadas en formato LRC ("[01:23.45] texto"). */
object LrcParser {

    private val TIME_TAG = Regex("\\[(\\d{1,3}):(\\d{1,2})(?:[.:](\\d{1,3}))?]")
    private val OFFSET_TAG = Regex("\\[offset:\\s*([+-]?\\d+)\\s*]", RegexOption.IGNORE_CASE)

    /** Líneas con tiempo, ordenadas. Vacía si el texto no está sincronizado. */
    fun parse(text: String): List<LyricLine> {
        val offset = OFFSET_TAG.find(text)?.groupValues?.get(1)?.toLongOrNull() ?: 0L
        val result = mutableListOf<LyricLine>()
        for (raw in text.lines()) {
            var rest = raw.trim()
            val times = mutableListOf<Long>()
            while (true) {
                val m = TIME_TAG.find(rest) ?: break
                if (m.range.first != 0) break
                val min = m.groupValues[1].toLong()
                val sec = m.groupValues[2].toLong()
                val fracText = m.groupValues[3]
                val frac = when (fracText.length) {
                    0 -> 0L
                    1 -> fracText.toLong() * 100
                    2 -> fracText.toLong() * 10
                    else -> fracText.toLong()
                }
                times += min * 60_000 + sec * 1_000 + frac
                rest = rest.substring(m.range.last + 1).trimStart()
            }
            for (t in times) result += LyricLine((t - offset).coerceAtLeast(0), rest)
        }
        return result.sortedBy { it.timeMs }
    }

    /** Quita las etiquetas de tiempo para mostrar la letra como texto plano. */
    fun toPlain(text: String): String =
        text.lines()
            .filterNot { it.trim().matches(Regex("\\[[a-zA-Z]+:.*]")) }
            .joinToString("\n") { it.replace(TIME_TAG, "").trim() }
            .trim()

    /** Índice de la línea que se está cantando en [positionMs], o -1 si aún no empieza. */
    fun currentIndex(lines: List<LyricLine>, positionMs: Long): Int {
        var lo = 0
        var hi = lines.size - 1
        var ans = -1
        while (lo <= hi) {
            val mid = (lo + hi) ushr 1
            if (lines[mid].timeMs <= positionMs) {
                ans = mid
                lo = mid + 1
            } else {
                hi = mid - 1
            }
        }
        return ans
    }
}
