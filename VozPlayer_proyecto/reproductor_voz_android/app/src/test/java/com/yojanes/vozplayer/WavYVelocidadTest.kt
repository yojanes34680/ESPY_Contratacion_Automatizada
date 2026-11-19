package com.yojanes.vozplayer

import android.app.Application
import android.net.Uri
import androidx.media3.common.C
import androidx.media3.common.DataReader
import androidx.media3.common.Format
import androidx.media3.common.util.ParsableByteArray
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DataSpec
import androidx.media3.datasource.FileDataSource
import androidx.media3.extractor.DefaultExtractorInput
import androidx.media3.extractor.DefaultExtractorsFactory
import androidx.media3.extractor.Extractor
import androidx.media3.extractor.ExtractorOutput
import androidx.media3.extractor.PositionHolder
import androidx.media3.extractor.SeekMap
import androidx.media3.extractor.TrackOutput
import androidx.media3.extractor.mp3.Mp3Extractor
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import java.io.File
import java.io.RandomAccessFile

/**
 * 1) Qué variantes de WAV abre el motor de la app (el mismo DefaultExtractorsFactory que usa
 *    PlaybackService) y cuáles necesitan la conversión de respaldo.
 * 2) Test de velocidad: lectura de un WAV de 4 minutos, memoria de la biblioteca y búsqueda.
 * Los resultados se imprimen en el registro de GitHub Actions.
 */
@OptIn(UnstableApi::class)
@RunWith(AndroidJUnit4::class)
@Config(sdk = [34])
class WavYVelocidadTest {

    data class Resultado(val ok: Boolean, val formato: String, val bytes: Long, val ms: Double, val error: String = "")

    private class Salida : ExtractorOutput {
        var format: Format? = null
        var bytes = 0L
        override fun track(id: Int, type: Int): TrackOutput = object : TrackOutput {
            override fun format(f: Format) { format = f }
            override fun sampleData(input: DataReader, length: Int, allowEndOfInput: Boolean, sampleDataPart: Int): Int {
                val buf = ByteArray(length)
                val n = input.read(buf, 0, length)
                if (n == C.RESULT_END_OF_INPUT) {
                    if (allowEndOfInput) return C.RESULT_END_OF_INPUT
                    throw java.io.EOFException()
                }
                bytes += n
                return n
            }
            override fun sampleData(data: ParsableByteArray, length: Int, sampleDataPart: Int) {
                data.skipBytes(length)
                bytes += length
            }
            override fun sampleMetadata(timeUs: Long, flags: Int, size: Int, offset: Int, cryptoData: TrackOutput.CryptoData?) {}
        }
        override fun endTracks() {}
        override fun seekMap(seekMap: SeekMap) {}
    }

    private val factory = DefaultExtractorsFactory()
        .setMp3ExtractorFlags(Mp3Extractor.FLAG_DISABLE_ID3_METADATA)
        .setConstantBitrateSeekingEnabled(true)

    private fun input(file: File, position: Long): Pair<FileDataSource, DefaultExtractorInput> {
        val ds = FileDataSource()
        val len = ds.open(DataSpec.Builder().setUri(Uri.fromFile(file)).setPosition(position).build())
        return ds to DefaultExtractorInput(ds, position, if (len == C.LENGTH_UNSET.toLong()) C.LENGTH_UNSET.toLong() else position + len)
    }

    private fun abrir(file: File): Resultado {
        val t0 = System.nanoTime()
        val uri = Uri.fromFile(file)
        var elegido: Extractor? = null
        for (e in factory.createExtractors(uri, emptyMap())) {
            val (ds, inp) = input(file, 0)
            val ok = runCatching { e.sniff(inp) }.getOrDefault(false)
            ds.close()
            if (ok) { elegido = e; break }
        }
        val ext = elegido ?: return Resultado(false, "?", 0, ms(t0), "ningún extractor lo reconoce")
        val out = Salida()
        ext.init(out)
        var (ds, inp) = input(file, 0)
        val pos = PositionHolder()
        return try {
            while (true) {
                val r = ext.read(inp, pos)
                if (r == Extractor.RESULT_END_OF_INPUT) break
                if (r == Extractor.RESULT_SEEK) {
                    ds.close()
                    val p = input(file, pos.position); ds = p.first; inp = p.second
                }
            }
            val f = out.format
            val desc = f?.let { "${it.sampleMimeType} pcm=${it.pcmEncoding} ${it.sampleRate}Hz ${it.channelCount}ch" } ?: "?"
            Resultado(out.bytes > 0, desc, out.bytes, ms(t0), if (out.bytes > 0) "" else "sin audio")
        } catch (e: Exception) {
            Resultado(false, ext.javaClass.simpleName, out.bytes, ms(t0), e.javaClass.simpleName + ": " + e.message)
        } finally {
            ds.close()
        }
    }

    private fun ms(t0: Long) = (System.nanoTime() - t0) / 1e6

    private fun wavDir(): File = File(javaClass.classLoader!!.getResource("wav")!!.toURI())

    @Test
    fun variantesDeWav() {
        val archivos = wavDir().listFiles()!!.filter { it.extension == "wav" }.sortedBy { it.name }
        abrir(archivos.first()) // calentamiento
        val res = archivos.associateWith { abrir(it) }
        println("WAV ┌────────────────────────┬──────────┬──────────────────────────────────────┬────────┐")
        res.forEach { (f, r) ->
            println(
                "WAV │ %-22s │ %-8s │ %-36s │ %6.1f ms │ %s".format(
                    f.nameWithoutExtension, if (r.ok) "OK" else "CONVERTIR", r.formato.take(36), r.ms, r.error.take(70),
                ),
            )
        }
        // Las variantes PCM y G.711 deben abrirse directamente.
        listOf("pcm16", "pcm24", "pcm32", "float32", "pcm8", "mono", "con_etiquetas_48k", "alaw", "mulaw", "adpcm_ima")
            .forEach { n -> assertTrue("$n debería abrirse", res.entries.first { it.key.nameWithoutExtension == n }.value.ok) }
    }

    @Test
    fun velocidadLecturaWavLargo() {
        // WAV de 4 minutos, estéreo 44,1 kHz 16 bits (~42 MB), como una pista real.
        val f = File.createTempFile("pista4min", ".wav")
        val seconds = 240
        val dataBytes = 44_100 * 2 * 2 * seconds
        RandomAccessFile(f, "rw").use { raf ->
            val h = java.nio.ByteBuffer.allocate(44).order(java.nio.ByteOrder.LITTLE_ENDIAN)
            h.put("RIFF".toByteArray()).putInt(36 + dataBytes).put("WAVE".toByteArray())
            h.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(2).putInt(44_100).putInt(44_100 * 4).putShort(4).putShort(16)
            h.put("data".toByteArray()).putInt(dataBytes)
            raf.write(h.array())
            raf.setLength(44L + dataBytes)
        }
        abrir(f)
        val r = abrir(f)
        f.delete()
        println("VELOCIDAD WAV 4 min (%.1f MB): abrir y leer todo el audio = %.0f ms (%.0f MB/s)".format(
            dataBytes / 1e6, r.ms, dataBytes / 1e6 / (r.ms / 1000)))
        assertTrue(r.ok)
    }

    @Test
    fun velocidadBibliotecaYBusqueda() {
        val app = ApplicationProvider.getApplicationContext<Application>()
        val palabras = listOf("amor", "indio", "caballero", "gaucho", "vida", "noche", "corazón", "luna", "rancho", "flor", "camino", "rey")
        val rnd = java.util.Random(7)
        val lib = (0 until 1000).map { i ->
            val t = (1..3).joinToString(" ") { palabras[rnd.nextInt(palabras.size)] }
            MediaEntry("content://pista/$i", t, "Artista $i", "", "$t ($i).wav", 200_000, false, null, i.toLong())
        }
        val carpeta = Uri.parse("content://prueba/velocidad")
        LibraryCache.save(app, carpeta, lib)
        LibraryCache.load(app, carpeta)
        var t0 = System.nanoTime(); val leidas = LibraryCache.load(app, carpeta)!!; val tCarga = ms(t0)
        t0 = System.nanoTime(); val idx = VoiceSearchMatcher.prepare(lib); val tIndice = ms(t0)
        VoiceSearchMatcher.rankPrepared("amor indio", idx)
        t0 = System.nanoTime(); repeat(10) { VoiceSearchMatcher.rankPrepared("amor indio caballero", idx) }; val tBusqueda = ms(t0) / 10
        t0 = System.nanoTime(); lib.map { it.toMediaItem() }.subList(0, 70); val tCola = ms(t0)
        println("VELOCIDAD lista guardada (1000 pistas): cargar al abrir = %.1f ms".format(tCarga))
        println("VELOCIDAD índice de búsqueda (1000 pistas) = %.1f ms · cada búsqueda = %.1f ms".format(tIndice, tBusqueda))
        println("VELOCIDAD preparar cola de reproducción = %.1f ms".format(tCola))
        assertTrue(leidas.size == 1000)
    }
}
