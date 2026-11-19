package com.yojanes.vozplayer

import java.io.BufferedInputStream
import java.io.EOFException
import java.io.File
import java.io.InputStream
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Arregla las variantes de WAV que ni el reproductor ni Android saben abrir, sin depender
 * de los decodificadores del teléfono (Kotlin puro, probado con archivos reales):
 *  - MP3 dentro de un WAV (formato 0x0055/0x0050): se quita la envoltura → archivo .mp3.
 *  - ADPCM de Microsoft (formato 0x0002): se decodifica → WAV PCM 16 bits.
 */
object WavRepair {

    const val TAG_PCM = 0x0001
    const val TAG_MS_ADPCM = 0x0002
    const val TAG_FLOAT = 0x0003
    const val TAG_ALAW = 0x0006
    const val TAG_MULAW = 0x0007
    const val TAG_IMA_ADPCM = 0x0011
    const val TAG_MPEG = 0x0050
    const val TAG_MP3 = 0x0055
    const val TAG_EXTENSIBLE = 0xFFFE

    data class Fmt(
        val tag: Int,
        val channels: Int,
        val sampleRate: Int,
        val blockAlign: Int,
        val bits: Int,
        val extra: ByteArray,
    )

    fun describe(tag: Int): String = when (tag) {
        TAG_PCM -> "PCM"
        TAG_MS_ADPCM -> "ADPCM de Microsoft"
        TAG_FLOAT -> "PCM flotante"
        TAG_ALAW -> "A-law"
        TAG_MULAW -> "μ-law"
        TAG_IMA_ADPCM -> "ADPCM IMA"
        TAG_MPEG, TAG_MP3 -> "MP3 dentro de WAV"
        0x0031 -> "GSM"
        0x0161, 0x0162, 0x0163 -> "WMA dentro de WAV"
        else -> "formato 0x%04X".format(tag)
    }

    /** Resultado: archivo creado (o null si no es WAV o no es una variante que se sepa arreglar). */
    data class Result(val file: File?, val fmt: Fmt?)

    /**
     * Lee el WAV de [input] y, si es una variante conocida que hay que arreglar, escribe el
     * resultado en [outDir] con nombre [baseName] (+ .mp3 o .wav).
     */
    fun repair(input: InputStream, outDir: File, baseName: String): Result {
        val inp = BufferedInputStream(input, 64 * 1024)
        val riff = readBytes(inp, 12) ?: return Result(null, null)
        if (String(riff, 0, 4, Charsets.US_ASCII) != "RIFF" || String(riff, 8, 4, Charsets.US_ASCII) != "WAVE") {
            return Result(null, null)
        }
        var fmt: Fmt? = null
        while (true) {
            val hdr = readBytes(inp, 8) ?: return Result(null, fmt)
            val id = String(hdr, 0, 4, Charsets.US_ASCII)
            val size = le32(hdr, 4).toLong() and 0xFFFFFFFFL
            when (id) {
                "fmt " -> {
                    val body = readBytes(inp, size.toInt()) ?: return Result(null, fmt)
                    if (size % 2 == 1L) inp.skip(1)
                    fmt = parseFmt(body)
                }
                "data" -> {
                    val f = fmt ?: return Result(null, null)
                    val dataSize = if (size == 0L || size == 0xFFFFFFFFL) Long.MAX_VALUE else size
                    return when (f.tag) {
                        TAG_MP3, TAG_MPEG -> Result(copyMp3(inp, dataSize, File(outDir, "$baseName.mp3")), f)
                        TAG_MS_ADPCM -> Result(decodeMsAdpcm(inp, dataSize, f, File(outDir, "$baseName.wav")), f)
                        else -> Result(null, f)
                    }
                }
                else -> skipFully(inp, size + (size and 1))
            }
        }
    }

    private fun parseFmt(b: ByteArray): Fmt {
        var tag = le16(b, 0)
        // Extensión del formato: empieza en cbSize (byte 16) → samplesPerBlock, numCoef, coeficientes.
        val extra = if (b.size > 16) b.copyOfRange(16, b.size) else ByteArray(0)
        if (tag == TAG_EXTENSIBLE && b.size >= 26) tag = le16(b, 24) // subformato GUID
        return Fmt(tag, le16(b, 2), le32(b, 4), le16(b, 12), if (b.size >= 16) le16(b, 14) else 0, extra)
    }

    private fun copyMp3(inp: InputStream, size: Long, out: File): File? {
        val tmp = File(out.parentFile, out.name + ".tmp")
        var left = size
        var total = 0L
        tmp.outputStream().buffered().use { o ->
            val buf = ByteArray(64 * 1024)
            while (left > 0) {
                val n = inp.read(buf, 0, minOf(buf.size.toLong(), left).toInt())
                if (n < 0) break
                o.write(buf, 0, n)
                left -= n
                total += n
            }
        }
        if (total == 0L || !tmp.renameTo(out)) {
            tmp.delete()
            return null
        }
        return out
    }

    private val ADAPT = intArrayOf(230, 230, 230, 230, 307, 409, 512, 614, 768, 614, 512, 409, 307, 230, 230, 230)
    private val DEFAULT_COEFS = arrayOf(
        intArrayOf(256, 0), intArrayOf(512, -256), intArrayOf(0, 0), intArrayOf(192, 64),
        intArrayOf(240, 0), intArrayOf(460, -208), intArrayOf(392, -232),
    )

    private fun decodeMsAdpcm(inp: InputStream, size: Long, f: Fmt, out: File): File? {
        val ch = f.channels
        if (ch !in 1..2 || f.blockAlign < 7 * ch) return null
        // Coeficientes: vienen en la extensión de "fmt " (cbSize, samplesPerBlock, numCoef, pares).
        val coefs: Array<IntArray> = if (f.extra.size >= 6) {
            val n = le16(f.extra, 4)
            if (n in 1..256 && f.extra.size >= 6 + n * 4) {
                Array(n) { i -> intArrayOf(sle16(f.extra, 6 + i * 4), sle16(f.extra, 8 + i * 4)) }
            } else {
                DEFAULT_COEFS
            }
        } else {
            DEFAULT_COEFS
        }
        val samplesPerBlockHdr = if (f.extra.size >= 4) le16(f.extra, 2) else 0
        val tmp = File(out.parentFile, out.name + ".tmp")
        var pcmBytes = 0L
        RandomAccessFile(tmp, "rw").use { raf ->
            raf.setLength(0)
            raf.write(ByteArray(44))
            val block = ByteArray(f.blockAlign)
            var left = size
            val outBuf = ByteBuffer.allocate(f.blockAlign * 4 + 64).order(ByteOrder.LITTLE_ENDIAN)
            while (left > 0) {
                val want = minOf(f.blockAlign.toLong(), left).toInt()
                val n = readUpTo(inp, block, want)
                if (n < 7 * ch) break
                left -= n
                outBuf.clear()
                decodeBlock(block, n, ch, coefs, samplesPerBlockHdr, outBuf)
                raf.write(outBuf.array(), 0, outBuf.position())
                pcmBytes += outBuf.position()
            }
            if (pcmBytes == 0L) return null
            raf.seek(0)
            raf.write(wavHeader(f.sampleRate, ch, pcmBytes))
        }
        if (!tmp.renameTo(out)) {
            tmp.delete()
            return null
        }
        return out
    }

    private fun decodeBlock(b: ByteArray, len: Int, ch: Int, coefs: Array<IntArray>, spbHdr: Int, out: ByteBuffer) {
        val pred = IntArray(ch) { (b[it].toInt() and 0xFF).coerceAtMost(coefs.size - 1) }
        var p = ch
        val delta = IntArray(ch) { sle16(b, p + it * 2) }
        p += ch * 2
        val s1 = IntArray(ch) { sle16(b, p + it * 2) }
        p += ch * 2
        val s2 = IntArray(ch) { sle16(b, p + it * 2) }
        p += ch * 2
        for (c in 0 until ch) out.putShort(s2[c].toShort())
        for (c in 0 until ch) out.putShort(s1[c].toShort())
        val nibblesAvail = (len - p) * 2
        var nibbles = nibblesAvail
        if (spbHdr > 2) nibbles = minOf(nibbles, (spbHdr - 2) * ch)
        var c = 0
        for (k in 0 until nibbles) {
            val byte = b[p + k / 2].toInt() and 0xFF
            val nib = if (k % 2 == 0) byte shr 4 else byte and 0x0F
            val signed = if (nib >= 8) nib - 16 else nib
            val coef = coefs[pred[c]]
            var sample = ((s1[c] * coef[0] + s2[c] * coef[1]) shr 8) + signed * delta[c]
            sample = sample.coerceIn(-32768, 32767)
            s2[c] = s1[c]
            s1[c] = sample
            delta[c] = (ADAPT[nib] * delta[c]) shr 8
            if (delta[c] < 16) delta[c] = 16
            out.putShort(sample.toShort())
            c = (c + 1) % ch
        }
    }

    fun wavHeader(sampleRate: Int, channels: Int, dataBytes: Long): ByteArray {
        val h = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        h.put("RIFF".toByteArray()).putInt((36 + dataBytes).toInt()).put("WAVE".toByteArray())
        h.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(channels.toShort())
        h.putInt(sampleRate).putInt(sampleRate * channels * 2).putShort((channels * 2).toShort()).putShort(16)
        h.put("data".toByteArray()).putInt(dataBytes.toInt())
        return h.array()
    }

    // ---------------------------------------------------------------- lectura

    private fun readBytes(inp: InputStream, n: Int): ByteArray? {
        val b = ByteArray(n)
        return if (readUpTo(inp, b, n) == n) b else null
    }

    private fun readUpTo(inp: InputStream, b: ByteArray, n: Int): Int {
        var off = 0
        while (off < n) {
            val r = inp.read(b, off, n - off)
            if (r < 0) break
            off += r
        }
        return off
    }

    private fun skipFully(inp: InputStream, n: Long) {
        var left = n
        while (left > 0) {
            val s = inp.skip(left)
            if (s <= 0) {
                if (inp.read() < 0) throw EOFException()
                left--
            } else {
                left -= s
            }
        }
    }

    private fun le16(b: ByteArray, o: Int) = (b[o].toInt() and 0xFF) or ((b[o + 1].toInt() and 0xFF) shl 8)
    private fun sle16(b: ByteArray, o: Int) = le16(b, o).toShort().toInt()
    private fun le32(b: ByteArray, o: Int) =
        (b[o].toInt() and 0xFF) or ((b[o + 1].toInt() and 0xFF) shl 8) or
            ((b[o + 2].toInt() and 0xFF) shl 16) or ((b[o + 3].toInt() and 0xFF) shl 24)
}
