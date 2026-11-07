package com.yojanes.vozplayer

import android.net.Uri
import android.os.SystemClock
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata

/** Convierte una pista de la biblioteca en un elemento del reproductor. */
fun MediaEntry.toMediaItem(): MediaItem =
    MediaItem.Builder()
        .setMediaId(uri)
        .setUri(Uri.parse(uri))
        .setMediaMetadata(
            MediaMetadata.Builder()
                .setTitle(title)
                .setArtist(artist.ifBlank { null })
                .setAlbumTitle(album.ifBlank { null })
                .build(),
        )
        .build()

/**
 * Señal compartida de "el reproductor está arrancando una canción", para que el
 * trabajo de fondo (lectura de etiquetas) le ceda el paso desde cualquier pantalla.
 */
object PlayGate {
    @Volatile var lastPlayRequestAt = 0L
    @Volatile var buffering = false

    fun markPlayRequested() {
        lastPlayRequestAt = SystemClock.elapsedRealtime()
    }

    fun busy(): Boolean = buffering || SystemClock.elapsedRealtime() - lastPlayRequestAt < 15_000
}
