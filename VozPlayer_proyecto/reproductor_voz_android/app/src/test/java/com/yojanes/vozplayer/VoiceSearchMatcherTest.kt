package com.yojanes.vozplayer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceSearchMatcherTest {

    private fun audio(title: String, artist: String = "", file: String = "$title.mp3") =
        MediaEntry("content://audio/$title", title, artist, "", file, 200_000, isVideo = false)

    private fun video(title: String, artist: String = "", file: String = "$title.mp4") =
        MediaEntry("content://video/$title", title, artist, "", file, 200_000, isVideo = true)

    private val library = listOf(
        audio("Bohemian Rhapsody", "Queen"),
        audio("La Bamba", "Ritchie Valens"),
        audio("Despacito", "Luis Fonsi"),
        video("Canción del Mariachi", "Antonio Banderas"),
        audio("Vivir mi vida", "Marc Anthony"),
        audio("", "", file = "Ensayo guitarra acústica 03.m4a"),
        video("Llorarás", "Oscar D'León"),
        audio("Hotel California", "Eagles"),
    )

    private fun top(query: String) = VoiceSearchMatcher.rank(query, library).first().entry

    @Test fun ignoraTildesYMayusculas() {
        assertEquals("Canción del Mariachi", top("cancion del mariachi").title)
    }

    @Test fun ignoraPalabrasDeOrden() {
        assertEquals("Despacito", top("pon la canción despacito por favor").title)
    }

    @Test fun toleraErroresDeDictado() {
        assertEquals("Bohemian Rhapsody", top("bohemian rapsodi").title)
    }

    @Test fun toleraConfusionFonetica() {
        assertEquals("Vivir mi vida", top("bibir mi bida").title)
        assertEquals("Llorarás", top("yoraras").title)
    }

    @Test fun buscaPorArtista() {
        assertEquals("Hotel California", top("eagles").title)
        assertEquals("Despacito", top("reproduce despacito de luis fonsi").title)
    }

    @Test fun buscaPorNombreDeArchivoSinEtiquetas() {
        val e = top("ensayo guitarra")
        assertEquals("Ensayo guitarra acústica 03.m4a", e.displayName)
    }

    @Test fun encuentraVideosYAudiosPorIgual() {
        assertTrue(top("mariachi").isVideo)
        assertTrue(!top("la bamba").isVideo)
    }

    @Test fun eligeLaMejorAlternativaDelReconocedor() {
        val m = VoiceSearchMatcher.bestVoiceMatch(listOf("hotel california", "otel kalifornia"), library)
        assertNotNull(m)
        assertEquals("Hotel California", m!!.best.entry.title)
        assertTrue(m.best.score >= VoiceSearchMatcher.AUTO_PLAY_THRESHOLD)
    }

    @Test fun noReproduceAlgoQueNoExiste() {
        val m = VoiceSearchMatcher.bestVoiceMatch(listOf("stairway to heaven"), library)
        assertTrue(m == null || m.best.score < VoiceSearchMatcher.AUTO_PLAY_THRESHOLD)
    }
}
