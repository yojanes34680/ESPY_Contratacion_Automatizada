package com.yojanes.vozplayer

import android.content.ComponentName
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import androidx.annotation.OptIn
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.google.android.material.chip.Chip
import com.google.common.util.concurrent.ListenableFuture
import com.yojanes.vozplayer.databinding.ActivityMixerBinding
import java.util.Locale

/** Panel master: volumen, ganancia, ecualizador con barras, graves, tono y velocidad. */
@OptIn(UnstableApi::class)
class MixerActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMixerBinding
    private val faders = mutableListOf<Pair<VerticalFader, TextView>>()

    private var controllerFuture: ListenableFuture<MediaController>? = null
    private val controller: MediaController?
        get() = controllerFuture?.takeIf { it.isDone }?.let { runCatching { it.get() }.getOrNull() }

    private val playerListener = object : Player.Listener {
        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) = refreshPitch()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMixerBinding.inflate(layoutInflater)
        setContentView(binding.root)
        AudioFx.init(this)
        binding.closeButton.setOnClickListener { finish() }

        // Volumen y ganancia
        binding.volumeSlider.value = (AudioFx.masterVolume * 100).toInt().toFloat().coerceIn(0f, 100f)
        binding.volumeSlider.addOnChangeListener { _, v, fromUser ->
            if (!fromUser) return@addOnChangeListener
            AudioFx.masterVolume = v / 100f
            controller?.volume = v / 100f
        }
        binding.gainSlider.value = (AudioFx.gainMb / 100).toFloat().coerceIn(0f, 12f)
        binding.gainSlider.setLabelFormatter { "+${it.toInt()} dB" }
        binding.gainSlider.addOnChangeListener { _, v, fromUser ->
            if (fromUser) AudioFx.gainMb = (v * 100).toInt()
        }

        // Ecualizador
        binding.eqSwitch.isChecked = AudioFx.equalizerEnabled
        binding.eqSwitch.setOnCheckedChangeListener { _, on ->
            AudioFx.equalizerEnabled = on
            setFadersEnabled(on)
        }
        binding.bassSlider.value = (AudioFx.bassStrength / 10).toFloat().coerceIn(0f, 100f)
        binding.bassSlider.setLabelFormatter { "${it.toInt()} %" }
        binding.bassSlider.addOnChangeListener { _, v, fromUser ->
            if (fromUser) AudioFx.bassStrength = (v * 10).toInt()
        }
        buildEqualizer()

        // Tono y velocidad
        binding.pitchDown.setOnClickListener { changePitch(-1) }
        binding.pitchUp.setOnClickListener { changePitch(+1) }
        binding.pitchReset.setOnClickListener { changePitch(0, absolute = true) }
        binding.speedSlider.value = (AudioFx.speed * 100).toInt().toFloat().coerceIn(50f, 150f)
        binding.speedSlider.setLabelFormatter { "${it.toInt()} %" }
        binding.speedSlider.addOnChangeListener { _, v, fromUser ->
            if (!fromUser) return@addOnChangeListener
            AudioFx.speed = v / 100f
            applyPlaybackParameters()
        }

        binding.resetAllButton.setOnClickListener {
            AudioFx.resetAll()
            controller?.volume = 1f
            recreate()
        }

        AudioFx.onEffectsChanged = { runOnUiThread { buildEqualizer() } }
        refreshPitch()
    }

    override fun onDestroy() {
        AudioFx.onEffectsChanged = null
        super.onDestroy()
    }

    override fun onStart() {
        super.onStart()
        val token = SessionToken(this, ComponentName(this, PlaybackService::class.java))
        val future = MediaController.Builder(this, token).buildAsync()
        controllerFuture = future
        future.addListener({
            val c = controller ?: return@addListener
            c.addListener(playerListener)
            refreshPitch()
            buildEqualizer()
        }, ContextCompat.getMainExecutor(this))
    }

    override fun onStop() {
        controller?.removeListener(playerListener)
        controllerFuture?.let { MediaController.releaseFuture(it) }
        controllerFuture = null
        super.onStop()
    }

    private fun buildEqualizer() {
        val box = binding.bandsContainer
        box.removeAllViews()
        faders.clear()
        binding.presetChips.removeAllViews()
        if (!AudioFx.equalizerAvailable || AudioFx.bandCount == 0) {
            binding.eqUnavailable.visibility = View.VISIBLE
            return
        }
        binding.eqUnavailable.visibility = View.GONE
        val range = AudioFx.bandRange
        for (band in 0 until AudioFx.bandCount) {
            val column = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER_HORIZONTAL
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }
            val db = TextView(this).apply {
                gravity = Gravity.CENTER
                textSize = 12f
                setTextColor(ContextCompat.getColor(this@MixerActivity, R.color.neon_cyan))
                setTypeface(typeface, android.graphics.Typeface.BOLD)
            }
            val fader = VerticalFader(this).apply {
                min = range.first
                max = range.last
                value = AudioFx.bandLevel(band)
                contentDescription = AudioFx.bandFrequencyLabel(band)
                onValueChange = { v ->
                    AudioFx.setBandLevel(band, v)
                    db.text = formatDb(v)
                }
            }
            db.text = formatDb(fader.value)
            val freq = TextView(this).apply {
                gravity = Gravity.CENTER
                textSize = 11f
                setTextColor(ContextCompat.getColor(this@MixerActivity, R.color.text_secondary))
                text = AudioFx.bandFrequencyLabel(band)
            }
            column.addView(db)
            column.addView(fader, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(220)))
            column.addView(freq)
            box.addView(column)
            faders += fader to db
        }
        AudioFx.presetNames().forEachIndexed { index, name ->
            binding.presetChips.addView(
                Chip(this, null, R.attr.neonChipStyle).apply {
                    text = name
                    isCheckable = false
                    setOnClickListener {
                        AudioFx.usePreset(index)
                        faders.forEachIndexed { band, (f, t) ->
                            f.value = AudioFx.bandLevel(band)
                            t.text = formatDb(f.value)
                        }
                    }
                },
            )
        }
        setFadersEnabled(AudioFx.equalizerEnabled)
    }

    private fun setFadersEnabled(on: Boolean) {
        faders.forEach { (f, _) ->
            f.isEnabled = on
            f.alpha = if (on) 1f else 0.4f
        }
    }

    private fun currentMediaId(): String? = controller?.currentMediaItem?.mediaId

    private fun changePitch(delta: Int, absolute: Boolean = false) {
        val id = currentMediaId()
        if (id == null) {
            binding.pitchHint.text = getString(R.string.mixer_pitch_need_song)
            return
        }
        val next = if (absolute) delta else (AudioFx.semitonesFor(id) + delta).coerceIn(-12, 12)
        AudioFx.setSemitones(id, next)
        applyPlaybackParameters()
        refreshPitch()
    }

    private fun applyPlaybackParameters() {
        controller?.playbackParameters = AudioFx.playbackParametersFor(currentMediaId())
    }

    private fun refreshPitch() {
        val id = currentMediaId()
        val semis = AudioFx.semitonesFor(id)
        binding.pitchValue.text = if (semis > 0) "+$semis" else semis.toString()
        val title = controller?.currentMediaItem?.mediaMetadata?.title
        binding.pitchHint.text = if (title != null) {
            getString(R.string.mixer_pitch_for, title)
        } else {
            getString(R.string.mixer_pitch_need_song)
        }
    }

    private fun formatDb(mb: Int): String {
        val db = mb / 100f
        return String.format(Locale.ROOT, if (db > 0) "+%.0f" else "%.0f", db)
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}
