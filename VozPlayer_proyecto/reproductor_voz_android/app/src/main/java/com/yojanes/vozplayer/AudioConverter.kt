package com.yojanes.vozplayer

import android.content.Context
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/**
 * Respaldo para pistas que el reproductor no entiende (por ejemplo WAV con MP3 o ADPCM por
 * dentro, o WMA en teléfonos Samsung): se decodifican con los decodificadores del propio
 * teléfono a un WAV PCM estándar, que se guarda para reproducirlo al instante la próxima vez.
 */
object AudioConverter {

    private const val MAX_CACHE_BYTES = 800L * 1024 * 1024

    @Volatile private var dir: File? = null
    private val ready = java.util.concurrent.ConcurrentHashMap<String, File>()

    fun init(context: Context) {
        val d = File(context.cacheDir, "convertidas").apply { mkdirs() }
        dir = d
        d.listFiles()?.filter { it.extension == "wav" }?.forEach { ready[it.nameWithoutExtension] = it }
    }

    private fun key(uri: String): String =
        MessageDigest.getInstance("SHA-1").digest(uri.toByteArray()).joinToString("") { "%02x".format(it) }

    /** Versión ya convertida de esta pista, si existe. */
    fun convertedFor(uri: String): File? = ready[key(uri)]?.takeIf { it.exists() }

    fun isConverted(uri: Uri): Boolean = uri.scheme == "file" && uri.path?.contains("/convertidas/") == true

    /** Convierte a WAV PCM 16 bits. Devuelve null si el teléfono tampoco puede decodificarla. */
    fun convert(context: Context, source: Uri, originalUri: String): File? {
        convertedFor(originalUri)?.let { return it }
        val d = dir ?: File(context.cacheDir, "convertidas").apply { mkdirs() }
        val out = File(d, key(originalUri) + ".wav")
        val tmp = File(d, key(originalUri) + ".tmp")
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        try {
            extractor.setDataSource(context, source, null)
            val track = (0 until extractor.trackCount).firstOrNull {
                extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true
            } ?: return null
            extractor.selectTrack(track)
            val inFormat = extractor.getTrackFormat(track)
            val mime = inFormat.getString(MediaFormat.KEY_MIME)!!
            var sampleRate = inFormat.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            var channels = inFormat.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            var encoding = AudioFormat.ENCODING_PCM_16BIT

            RandomAccessFile(tmp, "rw").use { raf ->
                raf.setLength(0)
                raf.write(ByteArray(44)) // cabecera provisional
                var dataBytes = 0L
                if (mime == MediaFormat.MIMETYPE_AUDIO_RAW) {
                    // PCM sin decodificador: se copia tal cual (16 bits).
                    val buf = ByteBuffer.allocate(256 * 1024)
                    while (true) {
                        buf.clear()
                        val n = extractor.readSampleData(buf, 0)
                        if (n < 0) break
                        raf.write(buf.array(), 0, n)
                        dataBytes += n
                        extractor.advance()
                    }
                } else {
                    val c = MediaCodec.createDecoderByType(mime)
                    codec = c
                    c.configure(inFormat, null, null, 0)
                    c.start()
                    val info = MediaCodec.BufferInfo()
                    var inputDone = false
                    var outputDone = false
                    var chunk = ByteArray(0)
                    while (!outputDone) {
                        if (!inputDone) {
                            val i = c.dequeueInputBuffer(10_000)
                            if (i >= 0) {
                                val n = extractor.readSampleData(c.getInputBuffer(i)!!, 0)
                                if (n < 0) {
                                    c.queueInputBuffer(i, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                                    inputDone = true
                                } else {
                                    c.queueInputBuffer(i, 0, n, extractor.sampleTime, 0)
                                    extractor.advance()
                                }
                            }
                        }
                        val o = c.dequeueOutputBuffer(info, 10_000)
                        when {
                            o == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                                val f = c.outputFormat
                                sampleRate = f.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                                channels = f.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                                if (f.containsKey(MediaFormat.KEY_PCM_ENCODING)) encoding = f.getInteger(MediaFormat.KEY_PCM_ENCODING)
                            }
                            o >= 0 -> {
                                val b = c.getOutputBuffer(o)!!
                                if (info.size > 0) {
                                    b.position(info.offset).limit(info.offset + info.size)
                                    val pcm16 = toPcm16(b, encoding)
                                    if (chunk.size < pcm16.remaining()) chunk = ByteArray(pcm16.remaining())
                                    val n = pcm16.remaining()
                                    pcm16.get(chunk, 0, n)
                                    raf.write(chunk, 0, n)
                                    dataBytes += n
                                }
                                c.releaseOutputBuffer(o, false)
                                if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) outputDone = true
                            }
                        }
                    }
                }
                if (dataBytes == 0L) return null
                raf.seek(0)
                raf.write(header(sampleRate, channels, dataBytes))
            }
            if (!tmp.renameTo(out)) return null
            ready[out.nameWithoutExtension] = out
            trimCache(out)
            return out
        } catch (e: Exception) {
            PerfLog.add("⚠ no se pudo convertir: ${e.javaClass.simpleName} ${e.message.orEmpty().take(60)}")
            return null
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            runCatching { extractor.release() }
            tmp.delete()
        }
    }

    /** Pasa el audio decodificado a PCM 16 bits (algunos decodificadores entregan flotante). */
    private fun toPcm16(src: ByteBuffer, encoding: Int): ByteBuffer {
        val inBuf = src.slice().order(ByteOrder.nativeOrder())
        if (encoding != AudioFormat.ENCODING_PCM_FLOAT) return inBuf
        val floats = inBuf.asFloatBuffer()
        val out = ByteBuffer.allocate(floats.remaining() * 2).order(ByteOrder.LITTLE_ENDIAN)
        while (floats.hasRemaining()) {
            val v = (floats.get().coerceIn(-1f, 1f) * 32767f).toInt()
            out.putShort(v.toShort())
        }
        out.flip()
        return out
    }

    private fun header(sampleRate: Int, channels: Int, dataBytes: Long): ByteArray {
        val h = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        h.put("RIFF".toByteArray()).putInt((36 + dataBytes).toInt()).put("WAVE".toByteArray())
        h.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(channels.toShort())
        h.putInt(sampleRate).putInt(sampleRate * channels * 2).putShort((channels * 2).toShort()).putShort(16)
        h.put("data".toByteArray()).putInt(dataBytes.toInt())
        return h.array()
    }

    /** Mantiene las conversiones por debajo de ~800 MB borrando las más antiguas. */
    private fun trimCache(keep: File) {
        val files = dir?.listFiles()?.filter { it.extension == "wav" }?.sortedBy { it.lastModified() } ?: return
        var total = files.sumOf { it.length() }
        for (f in files) {
            if (total <= MAX_CACHE_BYTES) break
            if (f == keep) continue
            total -= f.length()
            ready.remove(f.nameWithoutExtension)
            f.delete()
        }
    }
}
