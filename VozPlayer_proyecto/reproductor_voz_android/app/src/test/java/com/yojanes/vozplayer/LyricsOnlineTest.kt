package com.yojanes.vozplayer

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

/**
 * Búsqueda real de letras en internet. Solo corre si LETRAS_EN_LINEA=1
 * (paso de diagnóstico en GitHub Actions), para no depender de la red en las pruebas normales.
 */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [34])
class LyricsOnlineTest {

    private fun entryFromFile(name: String, durationMs: Long = 0): MediaEntry {
        val p = TrackNameParser.parse(name)
        return MediaEntry("content://prueba/$name", p.title, p.artist, "", name, durationMs, false)
    }

    private fun check(fileName: String): Boolean {
        val repo = LyricsRepository(ApplicationProvider.getApplicationContext<Application>())
        val e = entryFromFile(fileName)
        val r = repo.searchOnline(e, e.artist, e.title)
        val desc = when (r) {
            is LyricsRepository.OnlineResult.Found ->
                "ENCONTRADA: ${r.lyrics.artist} – ${r.lyrics.title} (sincronizada=${r.lyrics.synced.isNotEmpty()}) " +
                    r.lyrics.plain.lines().firstOrNull { it.isNotBlank() }.orEmpty()
            is LyricsRepository.OnlineResult.NotFound -> "NO ENCONTRADA. Buscó: ${r.searched}"
            is LyricsRepository.OnlineResult.NoConnection -> "SIN CONEXIÓN: ${r.detail}"
        }
        println("LETRA [$fileName] → $desc")
        return r is LyricsRepository.OnlineResult.Found
    }

    @Test
    fun buscaLetrasReales() {
        assumeTrue(System.getenv("LETRAS_EN_LINEA") == "1")
        val files = listOf(
            "Luis Fonsi - Despacito (Pista).mp3",
            "Vivir mi vida - Marc Anthony (Pista).mp3",
            "03 - Hotel California [Karaoke].mp3",
            "Juanes - La Camisa Negra.mp3",
            "Vicente Fernandez - El Rey (Pista).mp3",
            "Como la flor - Selena.mp3",
            "Amor indio.mp3",
            "Amor Indio (Pista).mp3",
        )
        val found = files.count { check(it) }
        println("LETRA total encontradas: $found de ${files.size}")
        assertTrue("Se esperaban al menos 4 letras encontradas", found >= 5)
    }
}
