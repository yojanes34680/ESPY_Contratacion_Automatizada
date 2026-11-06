package com.yojanes.vozplayer

/**
 * Archivo multimedia (audio o video) encontrado en el dispositivo.
 * Clase pura de Kotlin (sin dependencias de Android) para poder probar la búsqueda con JUnit.
 */
data class MediaEntry(
    val uri: String,
    val title: String,
    val artist: String,
    val album: String,
    val displayName: String,
    val durationMs: Long,
    val isVideo: Boolean,
    /** Archivo de letra (.lrc o .txt) con el mismo nombre, en la misma carpeta, si existe. */
    val lyricsUri: String? = null,
    /** Fecha de modificación del archivo (para refrescar la caché de metadatos). */
    val modified: Long = 0L,
) {
    /** Nombre del archivo sin extensión (muchas grabaciones de músicos no tienen etiquetas). */
    val fileNameWithoutExtension: String
        get() = displayName.substringBeforeLast('.', displayName)

    val extension: String
        get() = displayName.substringAfterLast('.', "").uppercase()
}
