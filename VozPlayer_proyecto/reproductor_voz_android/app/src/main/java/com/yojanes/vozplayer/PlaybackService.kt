package com.yojanes.vozplayer

import android.content.Intent
import androidx.annotation.OptIn
import androidx.media3.common.util.UnstableApi
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
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
        val player = ExoPlayer.Builder(this)
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

            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                player.playbackParameters = AudioFx.playbackParametersFor(mediaItem?.mediaId)
            }
        })
        session = MediaSession.Builder(this, player).build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = session

    override fun onTaskRemoved(rootIntent: Intent?) {
        val player = session?.player
        if (player == null || !player.playWhenReady || player.mediaItemCount == 0) {
            stopSelf()
        }
    }

    override fun onDestroy() {
        AudioFx.releaseEffects()
        session?.run {
            player.release()
            release()
        }
        session = null
        super.onDestroy()
    }
}
