package com.yojanes.vozplayer

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract

/** Carpetas de pistas elegidas por el usuario y cuál está activa. */
class FolderRepository(context: Context) {

    private val app = context.applicationContext
    private val prefs = app.getSharedPreferences("carpetas", Context.MODE_PRIVATE)

    data class Folder(val uri: Uri, val name: String)

    fun folders(): List<Folder> {
        val granted = app.contentResolver.persistedUriPermissions
            .filter { it.isReadPermission }
            .map { it.uri.toString() }
            .toSet()
        return prefs.getString(KEY_FOLDERS, "").orEmpty()
            .lines()
            .filter { it.isNotBlank() && it in granted }
            .map { Folder(Uri.parse(it), nameOf(Uri.parse(it))) }
    }

    fun add(uri: Uri) {
        val list = prefs.getString(KEY_FOLDERS, "").orEmpty().lines().filter { it.isNotBlank() }.toMutableList()
        if (uri.toString() !in list) list += uri.toString()
        prefs.edit().putString(KEY_FOLDERS, list.joinToString("\n")).apply()
    }

    fun remove(uri: Uri) {
        val list = prefs.getString(KEY_FOLDERS, "").orEmpty().lines()
            .filter { it.isNotBlank() && it != uri.toString() }
        prefs.edit().putString(KEY_FOLDERS, list.joinToString("\n")).apply()
        if (active?.uri == uri) active = null
        runCatching {
            app.contentResolver.releasePersistableUriPermission(
                uri, android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION,
            )
        }
    }

    /** Carpeta activa; null = todo el teléfono. */
    var active: Folder?
        get() {
            val saved = prefs.getString(KEY_ACTIVE, null) ?: return null
            return folders().firstOrNull { it.uri.toString() == saved }
        }
        set(value) {
            prefs.edit().putString(KEY_ACTIVE, value?.uri?.toString()).apply()
        }

    companion object {
        private const val KEY_FOLDERS = "carpetas"
        private const val KEY_ACTIVE = "activa"

        /** "primary:Music/Pistas" → "Pistas". */
        fun nameOf(uri: Uri): String {
            val docId = runCatching { DocumentsContract.getTreeDocumentId(uri) }.getOrNull()
                ?: return uri.lastPathSegment.orEmpty()
            val path = docId.substringAfter(':', docId)
            return path.trimEnd('/').substringAfterLast('/').ifBlank { docId.substringBefore(':') }
        }
    }
}
