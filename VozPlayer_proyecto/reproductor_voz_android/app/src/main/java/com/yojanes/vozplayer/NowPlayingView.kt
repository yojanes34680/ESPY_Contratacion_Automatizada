package com.yojanes.vozplayer

import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.os.Handler
import android.os.Looper
import android.util.AttributeSet
import android.view.LayoutInflater
import android.view.View
import android.widget.FrameLayout
import android.widget.SeekBar
import android.transition.TransitionManager
import android.view.ViewGroup
import androidx.media3.common.C
import androidx.media3.common.Player
import com.yojanes.vozplayer.databinding.ViewNowPlayingBinding

/** Panel "Sonando ahora": portada, título, progreso y controles grandes. */
class NowPlayingView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : FrameLayout(context, attrs) {

    private val b = ViewNowPlayingBinding.inflate(LayoutInflater.from(context), this, true)
    private val handler = Handler(Looper.getMainLooper())
    private var userSeeking = false
    private var lastArtKey: String? = null
    private val density = resources.displayMetrics.density

    private val listener = object : Player.Listener {
        override fun onEvents(player: Player, events: Player.Events) = refresh()
    }

    private val prefs = context.getSharedPreferences("vista", Context.MODE_PRIVATE)

    /** Panel desplegado (controles completos, Letra y Master) o barra compacta. Se recuerda. */
    private var expanded = prefs.getBoolean("panel_expandido", false)

    /** Oculta el botón "Letra" (por ejemplo, dentro de la propia pantalla de letra). */
    var showLyricsButton: Boolean = true
        set(value) {
            field = value
            b.npLyrics.visibility = if (value) View.VISIBLE else View.GONE
            applyMode()
        }

    var player: Player? = null
        set(value) {
            field?.removeListener(listener)
            field = value
            value?.addListener(listener)
            refresh()
        }

    private val ticker = object : Runnable {
        override fun run() {
            updateProgress()
            handler.postDelayed(this, 500)
        }
    }

    init {
        b.npArtImage.clipToOutline = true
        b.npLyrics.setOnClickListener {
            context.startActivity(Intent(context, LyricsActivity::class.java))
        }
        b.npMixer.setOnClickListener {
            context.startActivity(Intent(context, MixerActivity::class.java))
        }
        b.npPlay.setOnClickListener {
            val p = player ?: return@setOnClickListener
            if (p.isPlaying) {
                p.pause()
            } else {
                if (p.playbackState == Player.STATE_ENDED) p.seekToDefaultPosition()
                p.play()
            }
        }
        b.npMiniPlay.setOnClickListener { b.npPlay.performClick() }
        b.npToggle.setOnClickListener { toggle() }
        b.npTitle.setOnClickListener { if (!expanded) toggle() }
        b.npArtFrame.setOnClickListener { if (!expanded) toggle() }
        b.npPrev.setOnClickListener { player?.seekToPrevious() }
        b.npNext.setOnClickListener { player?.seekToNext() }
        b.npShuffle.setOnClickListener { player?.let { it.shuffleModeEnabled = !it.shuffleModeEnabled } }
        b.npRepeat.setOnClickListener {
            player?.let {
                it.repeatMode = when (it.repeatMode) {
                    Player.REPEAT_MODE_OFF -> Player.REPEAT_MODE_ALL
                    Player.REPEAT_MODE_ALL -> Player.REPEAT_MODE_ONE
                    else -> Player.REPEAT_MODE_OFF
                }
            }
        }
        b.npSeek.max = 1000
        b.npSeek.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(bar: SeekBar, progress: Int, fromUser: Boolean) {
                if (fromUser) b.npPosition.text = format(durationMs() * progress / 1000)
            }

            override fun onStartTrackingTouch(bar: SeekBar) {
                userSeeking = true
            }

            override fun onStopTrackingTouch(bar: SeekBar) {
                player?.seekTo(durationMs() * bar.progress / 1000)
                userSeeking = false
            }
        })
        applyMode()
        refresh()
    }

    private fun toggle() {
        expanded = !expanded
        prefs.edit().putBoolean("panel_expandido", expanded).apply()
        (parent as? ViewGroup)?.let { TransitionManager.beginDelayedTransition(it) }
        applyMode()
    }

    private fun applyMode() {
        b.npFull.visibility = if (expanded) View.VISIBLE else View.GONE
        b.npChips.visibility = if (expanded) View.VISIBLE else View.GONE
        b.npMiniPlay.visibility = if (expanded) View.GONE else View.VISIBLE
        b.npToggle.setImageResource(if (expanded) R.drawable.ic_expand_more else R.drawable.ic_expand_less)
        b.npToggle.contentDescription = context.getString(if (expanded) R.string.np_collapse else R.string.np_expand)
        val art = ((if (expanded) 52 else 40) * density).toInt()
        b.npArtFrame.layoutParams = b.npArtFrame.layoutParams.also { it.width = art; it.height = art }
        val v = ((if (expanded) 12 else 8) * density).toInt()
        b.root.setPadding(b.root.paddingLeft, v, b.root.paddingRight, if (expanded) (10 * density).toInt() else v)
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        handler.post(ticker)
    }

    override fun onDetachedFromWindow() {
        handler.removeCallbacks(ticker)
        super.onDetachedFromWindow()
    }

    private fun durationMs(): Long = player?.duration?.takeIf { it != C.TIME_UNSET && it > 0 } ?: 0L

    private fun refresh() {
        val p = player
        val item = p?.currentMediaItem
        val controls = listOf(b.npPlay, b.npPrev, b.npNext, b.npShuffle, b.npRepeat, b.npSeek)
        if (p == null || item == null) {
            b.npTitle.text = context.getString(R.string.np_idle_title)
            b.npArtist.text = context.getString(R.string.np_idle_subtitle)
            setArtwork("YJ", null, "vozplayer")
            b.npPlay.setImageResource(R.drawable.ic_play)
            b.npMiniPlay.setImageResource(R.drawable.ic_play)
            b.npMiniPlay.isEnabled = false
            controls.forEach { it.isEnabled = p != null && item != null }
            b.npPosition.text = format(0)
            b.npDuration.text = format(0)
            b.npSeek.progress = 0
            return
        }
        controls.forEach { it.isEnabled = true }
        b.npMiniPlay.isEnabled = true
        val md = p.mediaMetadata
        val title = (md.title ?: item.mediaMetadata.title)?.toString().orEmpty()
            .ifBlank { Library.find(item.mediaId)?.title.orEmpty() }
        val artist = (md.artist ?: item.mediaMetadata.artist)?.toString().orEmpty()
            .ifBlank { Library.find(item.mediaId)?.artist.orEmpty() }
        if (b.npTitle.text.toString() != title) {
            b.npTitle.text = title
            b.npTitle.isSelected = true // desplazamiento del título largo
        }
        b.npArtist.text = artist.ifBlank { context.getString(R.string.np_unknown_artist) }
        setArtwork(Artwork.initial(title), md.artworkData, item.mediaId)
        b.npPlay.setImageResource(if (p.isPlaying) R.drawable.ic_pause else R.drawable.ic_play)
        b.npMiniPlay.setImageResource(if (p.isPlaying) R.drawable.ic_pause else R.drawable.ic_play)
        b.npShuffle.alpha = if (p.shuffleModeEnabled) 1f else 0.45f
        b.npRepeat.alpha = if (p.repeatMode == Player.REPEAT_MODE_OFF) 0.45f else 1f
        b.npRepeat.setImageResource(
            if (p.repeatMode == Player.REPEAT_MODE_ONE) R.drawable.ic_repeat_one else R.drawable.ic_repeat,
        )
        updateProgress()
    }

    private fun setArtwork(initial: String, artwork: ByteArray?, key: String) {
        val artKey = key + "|" + (artwork?.size ?: 0)
        if (artKey == lastArtKey) return
        lastArtKey = artKey
        b.npArtwork.background = Artwork.background(key, 16 * density)
        b.npArtwork.text = initial
        val bmp = artwork?.let { runCatching { BitmapFactory.decodeByteArray(it, 0, it.size) }.getOrNull() }
        if (bmp != null) {
            b.npArtImage.setImageBitmap(bmp)
            b.npArtImage.visibility = View.VISIBLE
        } else {
            b.npArtImage.setImageDrawable(null)
            b.npArtImage.visibility = View.GONE
        }
    }

    private fun updateProgress() {
        val p = player ?: return
        val dur = durationMs()
        val pos = p.currentPosition.coerceAtLeast(0)
        b.npDuration.text = format(dur)
        if (!userSeeking) {
            b.npPosition.text = format(pos)
            b.npSeek.progress = if (dur > 0) (pos * 1000 / dur).toInt() else 0
        }
    }

    private fun format(ms: Long): String = MediaAdapter.formatDuration(ms).ifBlank { "0:00" }
}
