package com.yojanes.vozplayer

import android.content.ContentResolver
import android.content.ContentUris
import android.net.Uri
import android.os.Build
import android.provider.MediaStore

/** Lee todos los audios y videos indexados por Android (MediaStore). */
class MediaRepository(private val resolver: ContentResolver) {

    fun loadAll(): List<MediaEntry> =
        (loadAudio() + loadVideo()).sortedBy { it.title.lowercase() }

    private fun loadAudio(): List<MediaEntry> {
        val collection = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL)
        } else {
            MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
        }
        // Se excluyen tonos de llamada, alarmas y notificaciones del sistema.
        val selection = "${MediaStore.Audio.Media.IS_NOTIFICATION} = 0 AND " +
            "${MediaStore.Audio.Media.IS_RINGTONE} = 0 AND " +
            "${MediaStore.Audio.Media.IS_ALARM} = 0"
        return query(
            collection = collection,
            selection = selection,
            idCol = MediaStore.Audio.Media._ID,
            titleCol = MediaStore.Audio.Media.TITLE,
            artistCol = MediaStore.Audio.Media.ARTIST,
            albumCol = MediaStore.Audio.Media.ALBUM,
            nameCol = MediaStore.Audio.Media.DISPLAY_NAME,
            durationCol = MediaStore.Audio.Media.DURATION,
            isVideo = false,
        )
    }

    private fun loadVideo(): List<MediaEntry> {
        val collection = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL)
        } else {
            MediaStore.Video.Media.EXTERNAL_CONTENT_URI
        }
        return query(
            collection = collection,
            selection = null,
            idCol = MediaStore.Video.Media._ID,
            titleCol = MediaStore.Video.Media.TITLE,
            artistCol = MediaStore.Video.VideoColumns.ARTIST,
            albumCol = MediaStore.Video.VideoColumns.ALBUM,
            nameCol = MediaStore.Video.Media.DISPLAY_NAME,
            durationCol = MediaStore.Video.Media.DURATION,
            isVideo = true,
        )
    }

    private fun query(
        collection: Uri,
        selection: String?,
        idCol: String,
        titleCol: String,
        artistCol: String,
        albumCol: String,
        nameCol: String,
        durationCol: String,
        isVideo: Boolean,
    ): List<MediaEntry> {
        val result = mutableListOf<MediaEntry>()
        val projection = arrayOf(idCol, titleCol, artistCol, albumCol, nameCol, durationCol)
        try {
            resolver.query(collection, projection, selection, null, null)?.use { c ->
                val iId = c.getColumnIndexOrThrow(idCol)
                val iTitle = c.getColumnIndexOrThrow(titleCol)
                val iArtist = c.getColumnIndexOrThrow(artistCol)
                val iAlbum = c.getColumnIndexOrThrow(albumCol)
                val iName = c.getColumnIndexOrThrow(nameCol)
                val iDuration = c.getColumnIndexOrThrow(durationCol)
                while (c.moveToNext()) {
                    val id = c.getLong(iId)
                    val name = c.getString(iName).orEmpty()
                    val title = c.getString(iTitle).clean()
                        .ifBlank { name.substringBeforeLast('.', name) }
                    result += MediaEntry(
                        uri = ContentUris.withAppendedId(collection, id).toString(),
                        title = title,
                        artist = c.getString(iArtist).clean(),
                        album = c.getString(iAlbum).clean(),
                        displayName = name,
                        durationMs = c.getLong(iDuration),
                        isVideo = isVideo,
                    )
                }
            }
        } catch (_: SecurityException) {
            // Sin permiso para este tipo de medio (p. ej. el usuario sólo autorizó audio).
        }
        return result
    }

    private fun String?.clean(): String =
        this?.takeUnless { it == MediaStore.UNKNOWN_STRING }?.trim().orEmpty()
}
