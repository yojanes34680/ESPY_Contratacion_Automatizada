package com.yojanes.vozplayer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SetlistVoiceTest {

    @Test fun numerosDichos() {
        assertEquals(5, SetlistVoice.parseNumber("la cinco"))
        assertEquals(12, SetlistVoice.parseNumber("número 12"))
        assertEquals(3, SetlistVoice.parseNumber("pon la tres"))
        assertEquals(7, SetlistVoice.parseNumber("canción 7"))
        assertEquals(1, SetlistVoice.parseNumber("la primera"))
        assertEquals(32, SetlistVoice.parseNumber("treinta y dos"))
        assertEquals(8, SetlistVoice.parseNumber("8"))
    }

    @Test fun titulosNoSeConfundenConNumeros() {
        assertNull(SetlistVoice.parseNumber("amor indio"))
        assertNull(SetlistVoice.parseNumber("7 rings de ariana grande"))
        assertNull(SetlistVoice.parseNumber("las mañanitas"))
    }
}
