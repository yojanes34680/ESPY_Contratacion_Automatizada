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
) {
    /** Nombre del archivo sin extensión (muchas grabaciones de músicos no tienen etiquetas). */
    val fileNameWithoutExtension: String
        get() = displayName.substringBeforeLast('.', displayName)

    val extension: String
        get() = displayName.substringAfterLast('.', "").uppercase()
}
