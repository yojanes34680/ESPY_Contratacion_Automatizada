package com.yojanes.vozplayer

import android.content.Intent
import androidx.annotation.OptIn
import androidx.media3.common.util.UnstableApi
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.extractor.DefaultExtractorsFactory
import androidx.media3.extractor.mp3.Mp3Extractor
import androidx.media3.exoplayer.analytics.AnalyticsListener
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService

/**
 * Servicio de reproducción: mantiene la música sonando con la pantalla apagada,
 * muestra la notificación con controles y responde a audífonos Bluetooth.
 */
@OptIn(UnstableApi::class)
class PlaybackService : MediaSessionService() {

    private var session: MediaSession? = null

    override fun onCreate() {
        super.onCreate()
        val audioAttributes = AudioAttributes.Builder()
            .setUsage(C.USAGE_MEDIA)
            .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
            .build()
        // Pistas MP3: no se leen las etiquetas ID3 internas (título, carátula...). La app ya
        // tiene título y artista, y muchas pistas traen carátulas de varios MB que había que
        // leer completas antes de empezar a sonar, en cada canción.
        val extractors = DefaultExtractorsFactory()
            .setMp3ExtractorFlags(Mp3Extractor.FLAG_DISABLE_ID3_METADATA)
            .setConstantBitrateSeekingEnabled(true)
        // Archivos locales: basta con un búfer corto para empezar a sonar enseguida.
        val loadControl = DefaultLoadControl.Builder()
            .setBufferDurationsMs(
                /* minBufferMs = */ 15_000,
                /* maxBufferMs = */ 50_000,
                /* bufferForPlaybackMs = */ 500,
                /* bufferForPlaybackAfterRebufferMs = */ 1_000,
            )
            .build()
        val player = ExoPlayer.Builder(this, DefaultMediaSourceFactory(this, extractors))
            .setLoadControl(loadControl)
            .setAudioAttributes(audioAttributes, /* handleAudioFocus = */ true)
            .setHandleAudioBecomingNoisy(true) // pausa si se desconectan los audífonos
            .setWakeMode(C.WAKE_MODE_LOCAL)
            .build()
        AudioFx.init(this)
        player.volume = AudioFx.masterVolume
        AudioFx.attach(player.audioSessionId)
        player.addAnalyticsListener(object : AnalyticsListener {
            override fun onAudioSessionIdChanged(eventTime: AnalyticsListener.EventTime, audioSessionId: Int) {
                AudioFx.attach(audioSessionId)
            }
        })
        // El tono se recuerda por canción: se aplica cada vez que cambia la pista.
        player.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                PlayGate.buffering = playbackState == Player.STATE_BUFFERING
            }

            override fun onIsPlayingChanged(isPlaying: Boolean) {
                PlayGate.playing = isPlaying
                if (isPlaying && PlayGate.awaitingStart) {
                    PlayGate.awaitingStart = false
                    val ms = android.os.SystemClock.elapsedRealtime() - PlayGate.lastPlayRequestAt
                    PerfLog.add("▶ tocar → sonando: $ms ms")
                }
            }

            override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
                PlayGate.awaitingStart = false
                val item = player.currentMediaItem
                val name = item?.mediaMetadata?.title ?: "?"
                PerfLog.add("⚠ error al reproducir «$name»: ${error.errorCodeName}")
                if (item != null && error.errorCode in FORMAT_ERRORS) convertAndRetry(player, item)
            }

            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                player.playbackParameters = AudioFx.playbackParametersFor(mediaItem?.mediaId)
            }
        })
        session = MediaSession.Builder(this, player).build()
    }

    private val converter = java.util.concurrent.Executors.newSingleThreadExecutor()
    private val main = android.os.Handler(android.os.Looper.getMainLooper())

    /**
     * La pista usa una variante que el reproductor no entiende (p. ej. WAV con MP3 o ADPCM por
     * dentro): se convierte con los decodificadores del teléfono y se vuelve a reproducir.
     */
    private fun convertAndRetry(player: ExoPlayer, item: MediaItem) {
        val source = item.localConfiguration?.uri ?: return
        if (AudioConverter.isConverted(source)) {
            toast(getString(R.string.format_unsupported, item.mediaMetadata.title ?: ""))
            return
        }
        toast(getString(R.string.format_converting, item.mediaMetadata.title ?: ""))
        converter.execute {
            val t0 = android.os.SystemClock.elapsedRealtime()
            val file = AudioConverter.convert(this, source, item.mediaId)
            val ms = android.os.SystemClock.elapsedRealtime() - t0
            main.post {
                if (file == null) {
                    PerfLog.add("⚠ formato no compatible ni convertible: ${item.mediaMetadata.title}")
                    toast(getString(R.string.format_unsupported, item.mediaMetadata.title ?: ""))
                    return@post
                }
                PerfLog.add("🔄 convertida «${item.mediaMetadata.title}»: $ms ms")
                val index = (0 until player.mediaItemCount).firstOrNull { player.getMediaItemAt(it).mediaId == item.mediaId }
                    ?: return@post
                player.replaceMediaItem(index, item.buildUpon().setUri(android.net.Uri.fromFile(file)).build())
                player.seekTo(index, 0)
                PlayGate.markPlayRequested()
                player.prepare()
                player.play()
            }
        }
    }

    private fun toast(msg: String) {
        main.post { android.widget.Toast.makeText(applicationContext, msg, android.widget.Toast.LENGTH_LONG).show() }
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = session

    override fun onTaskRemoved(rootIntent: Intent?) {
        val player = session?.player
        if (player == null || !player.playWhenReady || player.mediaItemCount == 0) {
            stopSelf()
        }
    }

    companion object {
        /** Errores que indican formato no compatible (se intenta convertir la pista). */
        private val FORMAT_ERRORS = setOf(
            androidx.media3.common.PlaybackException.ERROR_CODE_PARSING_CONTAINER_UNSUPPORTED,
            androidx.media3.common.PlaybackException.ERROR_CODE_PARSING_CONTAINER_MALFORMED,
            androidx.media3.common.PlaybackException.ERROR_CODE_DECODING_FORMAT_UNSUPPORTED,
            androidx.media3.common.PlaybackException.ERROR_CODE_DECODING_FORMAT_EXCEEDS_CAPABILITIES,
            androidx.media3.common.PlaybackException.ERROR_CODE_DECODER_INIT_FAILED,
            androidx.media3.common.PlaybackException.ERROR_CODE_DECODER_QUERY_FAILED,
            androidx.media3.common.PlaybackException.ERROR_CODE_DECODING_FAILED,
            androidx.media3.common.PlaybackException.ERROR_CODE_AUDIO_TRACK_INIT_FAILED,
        )
    }

    override fun onDestroy() {
        converter.shutdownNow()
        AudioFx.releaseEffects()
        session?.run {
            player.release()
            release()
        }
        session = null
        super.onDestroy()
    }
}
