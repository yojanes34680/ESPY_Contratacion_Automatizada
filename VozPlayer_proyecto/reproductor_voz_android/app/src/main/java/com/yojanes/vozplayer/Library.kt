package com.yojanes.vozplayer

/** Biblioteca cargada actualmente (compartida entre pantallas del mismo proceso). */
object Library {
    @Volatile
    var entries: List<MediaEntry> = emptyList()

    fun find(uri: String?): MediaEntry? = uri?.let { u -> entries.firstOrNull { it.uri == u } }
}
