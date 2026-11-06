package com.yojanes.vozplayer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LrcParserTest {

    private val lrc = """
        [ti:Prueba]
        [ar:Artista]
        [00:01.50]Primera línea
        [00:05.00][00:20.00]Coro repetido
        [00:10.123]Tercera
    """.trimIndent()

    @Test fun leeTiemposYOrdena() {
        val lines = LrcParser.parse(lrc)
        assertEquals(4, lines.size)
        assertEquals(1_500L, lines[0].timeMs)
        assertEquals("Coro repetido", lines[1].text)
        assertEquals(10_123L, lines[2].timeMs)
        assertEquals(20_000L, lines[3].timeMs)
    }

    @Test fun lineaActual() {
        val lines = LrcParser.parse(lrc)
        assertEquals(-1, LrcParser.currentIndex(lines, 1_000))
        assertEquals(0, LrcParser.currentIndex(lines, 1_500))
        assertEquals(1, LrcParser.currentIndex(lines, 9_999))
        assertEquals(3, LrcParser.currentIndex(lines, 60_000))
    }

    @Test fun textoSinTiemposNoEsSincronizado() {
        assertTrue(LrcParser.parse("Hola\nmundo").isEmpty())
    }

    @Test fun convierteATextoPlano() {
        assertEquals("Primera línea\nCoro repetido\nTercera", LrcParser.toPlain(lrc))
    }

    @Test fun aplicaOffset() {
        val lines = LrcParser.parse("[offset:+500]\n[00:02.00]Hola")
        assertEquals(1_500L, lines[0].timeMs)
    }
}
