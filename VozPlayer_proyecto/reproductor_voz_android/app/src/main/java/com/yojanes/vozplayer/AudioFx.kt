package com.yojanes.vozplayer

import android.content.Context
import android.content.SharedPreferences
import android.media.audiofx.BassBoost
import android.media.audiofx.Equalizer
import android.media.audiofx.LoudnessEnhancer
import androidx.media3.common.C
import androidx.media3.common.PlaybackParameters
import kotlin.math.pow

/**
 * Panel master: ecualizador, refuerzo de graves, ganancia, volumen, tono y velocidad.
 * Los ajustes se guardan y se vuelven a aplicar en cada sesión de audio.
 * El tono se recuerda por canción (cada pista puede ir en una tonalidad distinta).
 */
object AudioFx {

    private var prefs: SharedPreferences? = null
    private var equalizer: Equalizer? = null
    private var bassBoost: BassBoost? = null
    private var loudness: LoudnessEnhancer? = null

    /** Se notifica cuando cambia la disponibilidad de los efectos (p. ej. al iniciar la reproducción). */
    var onEffectsChanged: (() -> Unit)? = null

    fun init(context: Context) {
        if (prefs == null) prefs = context.applicationContext.getSharedPreferences("master", Context.MODE_PRIVATE)
    }

    private val p: SharedPreferences get() = checkNotNull(prefs) { "AudioFx.init no fue llamado" }

    // ------------------------------------------------------------ Sesión de audio

    fun attach(audioSessionId: Int) {
        releaseEffects()
        if (audioSessionId == C.AUDIO_SESSION_ID_UNSET || audioSessionId == 0) return
        equalizer = runCatching { Equalizer(0, audioSessionId) }.getOrNull()
        bassBoost = runCatching { BassBoost(0, audioSessionId) }.getOrNull()
        loudness = runCatching { LoudnessEnhancer(audioSessionId) }.getOrNull()
        applySaved()
        onEffectsChanged?.invoke()
    }

    fun releaseEffects() {
        runCatching { equalizer?.release() }
        runCatching { bassBoost?.release() }
        runCatching { loudness?.release() }
        equalizer = null
        bassBoost = null
        loudness = null
    }

    private fun applySaved() {
        equalizer?.let { eq ->
            runCatching {
                for (i in 0 until eq.numberOfBands) eq.setBandLevel(i.toShort(), bandLevel(i).toShort())
                eq.enabled = equalizerEnabled
            }
        }
        bassBoost?.let { bb ->
            runCatching {
                if (bb.strengthSupported) bb.setStrength(bassStrength.toShort())
                bb.enabled = equalizerEnabled && bassStrength > 0
            }
        }
        loudness?.let { le ->
            runCatching {
                le.setTargetGain(gainMb)
                le.enabled = gainMb > 0
            }
        }
    }

    // ------------------------------------------------------------ Ecualizador

    val equalizerAvailable: Boolean get() = equalizer != null

    val bandCount: Int get() = runCatching { equalizer?.numberOfBands?.toInt() }.getOrNull() ?: 0

    /** Rango de cada banda en milibelios (p. ej. -1500..1500 = ±15 dB). */
    val bandRange: IntRange
        get() = runCatching {
            val r = equalizer!!.bandLevelRange
            r[0].toInt()..r[1].toInt()
        }.getOrDefault(-1500..1500)

    fun bandFrequencyLabel(band: Int): String {
        val hz = runCatching { equalizer!!.getCenterFreq(band.toShort()) / 1000 }.getOrDefault(0)
        return if (hz >= 1000) {
            String.format(java.util.Locale.ROOT, "%.1f", hz / 1000f).removeSuffix(".0") + " kHz"
        } else {
            "$hz Hz"
        }
    }

    fun bandLevel(band: Int): Int = p.getInt("banda_$band", 0)

    fun setBandLevel(band: Int, levelMb: Int) {
        p.edit().putInt("banda_$band", levelMb).apply()
        runCatching { equalizer?.setBandLevel(band.toShort(), levelMb.toShort()) }
    }

    var equalizerEnabled: Boolean
        get() = p.getBoolean("eq_activo", true)
        set(value) {
            p.edit().putBoolean("eq_activo", value).apply()
            runCatching { equalizer?.enabled = value }
            runCatching { bassBoost?.enabled = value && bassStrength > 0 }
        }

    fun presetNames(): List<String> = runCatching {
        val eq = equalizer!!
        (0 until eq.numberOfPresets).map { eq.getPresetName(it.toShort()) }
    }.getOrDefault(emptyList())

    fun usePreset(index: Int) {
        val eq = equalizer ?: return
        runCatching {
            eq.usePreset(index.toShort())
            for (i in 0 until eq.numberOfBands) {
                p.edit().putInt("banda_$i", eq.getBandLevel(i.toShort()).toInt()).apply()
            }
        }
    }

    /** Refuerzo de graves 0..1000. */
    var bassStrength: Int
        get() = p.getInt("graves", 0)
        set(value) {
            p.edit().putInt("graves", value).apply()
            runCatching {
                bassBoost?.setStrength(value.toShort())
                bassBoost?.enabled = equalizerEnabled && value > 0
            }
        }

    /** Ganancia extra en milibelios (0..1200 = hasta +12 dB). */
    var gainMb: Int
        get() = p.getInt("ganancia", 0)
        set(value) {
            p.edit().putInt("ganancia", value).apply()
            runCatching {
                loudness?.setTargetGain(value)
                loudness?.enabled = value > 0
            }
        }

    /** Volumen master del reproductor 0..1. */
    var masterVolume: Float
        get() = p.getFloat("volumen", 1f)
        set(value) = p.edit().putFloat("volumen", value).apply()

    // ------------------------------------------------------------ Tono y velocidad

    var speed: Float
        get() = p.getFloat("velocidad", 1f)
        set(value) = p.edit().putFloat("velocidad", value).apply()

    fun semitonesFor(mediaId: String?): Int =
        if (mediaId == null) 0 else p.getInt("tono_" + mediaId.hashCode(), 0)

    fun setSemitones(mediaId: String?, semitones: Int) {
        if (mediaId == null) return
        p.edit().putInt("tono_" + mediaId.hashCode(), semitones).apply()
    }

    fun playbackParametersFor(mediaId: String?): PlaybackParameters =
        PlaybackParameters(speed, 2.0.pow(semitonesFor(mediaId) / 12.0).toFloat())

    /** Vuelve todo a cero, pero conserva el tono guardado de cada canción. */
    fun resetAll() {
        val editor = p.edit()
        p.all.keys.filterNot { it.startsWith("tono_") }.forEach { editor.remove(it) }
        editor.apply()
        applySaved()
    }
}
