package com.yojanes.vozplayer

import android.content.ContentResolver
import android.net.Uri
import android.provider.DocumentsContract
import android.provider.DocumentsContract.Document

/** Recorre una carpeta elegida (y sus subcarpetas) buscando pistas y archivos de letra. */
class FolderScanner(private val resolver: ContentResolver) {

    private data class Found(
        val docId: String,
        val dirId: String,
        val name: String,
        val modified: Long,
        val isVideo: Boolean,
    )

    fun scan(treeUri: Uri): List<MediaEntry> {
        val rootId = DocumentsContract.getTreeDocumentId(treeUri)
        val media = mutableListOf<Found>()
        val lyrics = HashMap<String, String>()
        val pending = ArrayDeque<String>().apply { add(rootId) }
        var visitedDirs = 0
        val projection = arrayOf(
            Document.COLUMN_DOCUMENT_ID,
            Document.COLUMN_DISPLAY_NAME,
            Document.COLUMN_MIME_TYPE,
            Document.COLUMN_LAST_MODIFIED,
        )
        while (pending.isNotEmpty() && visitedDirs < MAX_DIRS) {
            val dirId = pending.removeFirst()
            visitedDirs++
            val children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, dirId)
            try {
                resolver.query(children, projection, null, null, null)?.use { c ->
                    while (c.moveToNext()) {
                        val id = c.getString(0) ?: continue
                        val name = c.getString(1).orEmpty()
                        val mime = c.getString(2).orEmpty()
                        val modified = if (c.isNull(3)) 0L else c.getLong(3)
                        if (name.startsWith(".")) continue
                        if (mime == Document.MIME_TYPE_DIR) {
                            pending.add(id)
                            continue
                        }
                        val ext = name.substringAfterLast('.', "").lowercase()
                        val base = name.substringBeforeLast('.', name).lowercase()
                        when {
                            ext == "lrc" -> lyrics["$dirId|$base"] = docUri(treeUri, id)
                            ext == "txt" -> lyrics.putIfAbsent("$dirId|$base", docUri(treeUri, id))
                            mime.startsWith("video/") || (!mime.startsWith("audio/") && ext in VIDEO_EXT) ->
                                media += Found(id, dirId, name, modified, isVideo = true)
                            mime.startsWith("audio/") || ext in AUDIO_EXT ->
                                media += Found(id, dirId, name, modified, isVideo = false)
                        }
                    }
                }
            } catch (_: Exception) {
                // Subcarpeta ilegible: se omite.
            }
        }
        return media.map { f ->
            val parsed = TrackNameParser.parse(f.name)
            val base = f.name.substringBeforeLast('.', f.name).lowercase()
            MediaEntry(
                uri = docUri(treeUri, f.docId),
                title = parsed.title.ifBlank { f.name },
                artist = parsed.artist,
                album = "",
                displayName = f.name,
                durationMs = 0L,
                isVideo = f.isVideo,
                lyricsUri = lyrics["${f.dirId}|$base"],
                modified = f.modified,
            )
        }.sortedBy { it.title.lowercase() }
    }

    private fun docUri(tree: Uri, id: String) =
        DocumentsContract.buildDocumentUriUsingTree(tree, id).toString()

    companion object {
        private const val MAX_DIRS = 2000
        val AUDIO_EXT = setOf("mp3", "m4a", "aac", "wav", "flac", "ogg", "oga", "opus", "amr", "wma", "aif", "aiff", "mka")
        val VIDEO_EXT = setOf("mp4", "m4v", "mkv", "webm", "3gp", "mov", "avi", "ts")
    }
}
