package com.yojanes.vozplayer

import org.junit.Assert.assertEquals
import org.junit.Test

class SharedListParserTest {

    @Test fun leeListaCompartidaPorLaApp() {
        val texto = """
            🎤 Serenata
            1. Amor Indio — Caballero Gaucho
            2. No Quiero Envejecer — Lucho y Rafa
            3. Despacito

            (3 canciones · VozPlayer · Yojanes Producciones)
        """.trimIndent()
        val p = SharedListParser.parse(texto)
        assertEquals("Serenata", p.name)
        assertEquals(
            listOf(
                SharedListParser.Song("Amor Indio", "Caballero Gaucho"),
                SharedListParser.Song("No Quiero Envejecer", "Lucho y Rafa"),
                SharedListParser.Song("Despacito", ""),
            ),
            p.songs,
        )
    }

    @Test fun leeListaEscritaAMano() {
        val p = SharedListParser.parse("amor indio, la camisa negra\nEl Rey - Vicente Fernández")
        assertEquals(null, p.name)
        assertEquals(listOf("amor indio", "la camisa negra", "El Rey"), p.songs.map { it.title })
        assertEquals("Vicente Fernández", p.songs[2].artist)
    }
}
