package com.yojanes.vozplayer

import android.app.Application
import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(sdk = [34])
class LibraryCacheTest {

    private val app get() = ApplicationProvider.getApplicationContext<Application>()
    private val folder = Uri.parse("content://com.android.externalstorage.documents/tree/primary%3AMusic%2FPistas")

    private fun song(n: Int, mod: Long = 1000L + n) =
        MediaEntry("content://pista/$n", "Canción $n", "Artista $n", "", "Canción $n.mp3", 180_000L, false, null, mod)

    @Test
    fun guardaYLeeLaListaDeLaCarpeta() {
        val lista = (1..50).map { song(it) }
        LibraryCache.save(app, folder, lista)
        assertEquals(lista, LibraryCache.load(app, folder))
    }

    @Test
    fun sinListaGuardadaDevuelveNulo() {
        assertNull(LibraryCache.load(app, Uri.parse("content://otra/carpeta")))
    }

    @Test
    fun detectaCambiosEnLosArchivos() {
        val a = (1..5).map { song(it) }
        assertTrue(LibraryCache.sameFiles(a, a.reversed()))
        assertTrue(LibraryCache.sameFiles(a, a.map { it.copy(artist = "Etiqueta leída") })) // datos leídos no cuentan
        assertFalse(LibraryCache.sameFiles(a, a + song(6)))               // pista nueva
        assertFalse(LibraryCache.sameFiles(a, a.drop(1)))                 // pista borrada
        assertFalse(LibraryCache.sameFiles(a, a.map { if (it.uri.endsWith("/3")) it.copy(modified = 9) else it })) // modificada
    }
}
