package com.yojanes.vozplayer

import org.junit.Assert.assertEquals
import org.junit.Test

class TrackNameParserTest {

    @Test fun artistaYTitulo() {
        val p = TrackNameParser.parse("Marc Anthony - Vivir mi vida.mp3")
        assertEquals("Marc Anthony", p.artist)
        assertEquals("Vivir mi vida", p.title)
    }

    @Test fun quitaNumeroDePista() {
        val p = TrackNameParser.parse("03 - Luis Fonsi - Despacito (Pista).mp3")
        assertEquals("Luis Fonsi", p.artist)
        assertEquals("Despacito (Pista)", p.title)
    }

    @Test fun soloTitulo() {
        val p = TrackNameParser.parse("Ensayo_guitarra_03.m4a")
        assertEquals("", p.artist)
        assertEquals("Ensayo guitarra 03", p.title)
    }

    @Test fun noConfundeTitulosConNumeros() {
        assertEquals("7 Rings", TrackNameParser.parse("7 Rings.mp3").title)
    }

    @Test fun limpiaMarcasDePista() {
        assertEquals("Despacito", TrackNameParser.cleanForLyrics("Despacito (Pista)"))
        assertEquals("Hotel California", TrackNameParser.cleanForLyrics("Hotel California [Karaoke HD]"))
        assertEquals("La Bamba", TrackNameParser.cleanForLyrics("La Bamba - Instrumental"))
    }
}
