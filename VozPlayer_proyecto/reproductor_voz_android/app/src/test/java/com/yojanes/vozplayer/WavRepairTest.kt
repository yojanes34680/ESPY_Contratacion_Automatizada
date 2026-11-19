package com.yojanes.vozplayer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** Reparación de variantes de WAV que ni el reproductor ni Android saben abrir. */
class WavRepairTest {

    private fun res(name: String) = File(javaClass.classLoader!!.getResource("wav/$name")!!.toURI())
    private val out: File = Files.createTempDirectory("wavrepair").toFile()

    private fun pcm(bytes: ByteArray, start: Int) =
        ShortArray((bytes.size - start) / 2) { i ->
            ((bytes[start + i * 2].toInt() and 0xFF) or (bytes[start + i * 2 + 1].toInt() shl 8)).toShort()
        }

    @Test
    fun adpcmMicrosoftIgualQueFfmpeg() {
        val r = res("adpcm_ms.wav").inputStream().use { WavRepair.repair(it, out, "adpcm") }
        assertEquals(WavRepair.TAG_MS_ADPCM, r.fmt!!.tag)
        val mine = pcm(r.file!!.readBytes(), 44)
        val ref = pcm(res("adpcm_ms.ffmpeg.raw").readBytes(), 0)
        assertEquals(ref.size, mine.size)
        assertEquals("muestras distintas a ffmpeg", 0, mine.indices.count { mine[it] != ref[it] })
    }

    @Test
    fun mp3DentroDeWavSeExtrae() {
        val r = res("mp3_en_wav.wav").inputStream().use { WavRepair.repair(it, out, "mp3") }
        assertEquals(WavRepair.TAG_MP3, r.fmt!!.tag)
        val b = r.file!!.readBytes()
        assertEquals("mp3", r.file!!.extension)
        // Empieza con una cabecera de trama MP3 (sincronía 0xFFE).
        assertEquals(0xFF, b[0].toInt() and 0xFF)
        assertEquals(0xE0, b[1].toInt() and 0xE0)
    }

    @Test
    fun wavNormalNoSeToca() {
        val r = res("pcm16.wav").inputStream().use { WavRepair.repair(it, out, "pcm") }
        assertNull(r.file)
        assertEquals(WavRepair.TAG_PCM, r.fmt!!.tag)
    }
}
