package com.yojanes.vozplayer

import org.junit.Assert.assertEquals
import org.junit.Test

class DictationSplitterTest {

    @Test fun unaSolaCancion() {
        assertEquals(listOf("amor indio"), DictationSplitter.split("amor indio"))
    }

    @Test fun variasConComasYConectores() {
        assertEquals(
            listOf("amor indio", "no quiero envejecer", "la camisa negra", "el rey"),
            DictationSplitter.split("amor indio, luego no quiero envejecer y después la camisa negra, el rey"),
        )
    }

    @Test fun noSeparaPorYSola() {
        assertEquals(listOf("Lucho y Rafa no quiero envejecer"), DictationSplitter.split("Lucho y Rafa no quiero envejecer"))
    }

    @Test fun quitaPalabrasDeOrden() {
        assertEquals(listOf("vivir mi vida", "despacito"), DictationSplitter.split("agrega vivir mi vida, también despacito"))
    }
}
