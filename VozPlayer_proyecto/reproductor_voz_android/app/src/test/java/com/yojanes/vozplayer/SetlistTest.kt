package com.yojanes.vozplayer

import android.app.Application
import android.content.ComponentName
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(sdk = [34])
class SetlistTest {

    private val app get() = ApplicationProvider.getApplicationContext<Application>()

    private fun song(n: Int, artist: String = "Artista $n") =
        MediaEntry("content://pista/$n", "Canción $n", artist, "", "Canción $n.mp3", 180_000L + n, n % 5 == 0)

    @Before
    fun preparar() {
        shadowOf(app).declareComponentUnbindable(ComponentName(app, PlaybackService::class.java))
        SetlistStore.all(app).forEach { SetlistStore.delete(app, it.id) }
    }

    @Test
    fun guardaYLeeEnOrden() {
        val s = SetlistStore.create(app, "Serenata")
        assertTrue(SetlistStore.add(app, s.id, song(1)))
        assertTrue(SetlistStore.add(app, s.id, song(2)))
        assertTrue(SetlistStore.add(app, s.id, song(3)))
        val leido = SetlistStore.get(app, s.id)!!
        assertEquals("Serenata", leido.name)
        assertEquals(listOf("Canción 1", "Canción 2", "Canción 3"), leido.items.map { it.title })
        assertEquals(song(2), leido.items[1])
    }

    @Test
    fun noDuplicaCanciones() {
        val s = SetlistStore.create(app, "Boda")
        assertTrue(SetlistStore.add(app, s.id, song(7)))
        assertFalse(SetlistStore.add(app, s.id, song(7)))
        assertEquals(1, SetlistStore.get(app, s.id)!!.items.size)
    }

    @Test
    fun reordenaRenombraYElimina() {
        val s = SetlistStore.create(app, "Rancheras")
        (1..4).forEach { SetlistStore.add(app, s.id, song(it)) }
        val actual = SetlistStore.get(app, s.id)!!
        val nuevoOrden = listOf(actual.items[3], actual.items[0], actual.items[2], actual.items[1])
        SetlistStore.save(app, actual.copy(name = "Rancheras viernes", items = nuevoOrden))
        val leido = SetlistStore.get(app, s.id)!!
        assertEquals("Rancheras viernes", leido.name)
        assertEquals(listOf(4, 1, 3, 2), leido.items.map { it.title.removePrefix("Canción ").toInt() })
        SetlistStore.delete(app, s.id)
        assertNull(SetlistStore.get(app, s.id))
    }

    @Test
    fun copiaDeSeguridadSeRestauraCompleta() {
        val s = SetlistStore.create(app, "Serenata")
        (1..3).forEach { SetlistStore.add(app, s.id, song(it)) }
        val copia = SetlistStore.exportJson(app)
        // Simula reinstalar: se borra todo y se restaura el archivo.
        SetlistStore.delete(app, s.id)
        assertNull(SetlistStore.get(app, s.id))
        assertEquals(1, SetlistStore.importJson(app, copia))
        val r = SetlistStore.get(app, s.id)!!
        assertEquals("Serenata", r.name)
        assertEquals(listOf("Canción 1", "Canción 2", "Canción 3"), r.items.map { it.title })
    }

    @Test
    fun listaCompartidaSeVuelveAImportar() {
        val s = SetlistStore.create(app, "Boda")
        (1..2).forEach { SetlistStore.add(app, s.id, song(it, "Caballero Gaucho")) }
        val texto = SetlistStore.asText(SetlistStore.get(app, s.id)!!)
        val p = SharedListParser.parse(texto)
        assertEquals("Boda", p.name)
        assertEquals(listOf("Canción 1", "Canción 2"), p.songs.map { it.title })
        assertEquals("Caballero Gaucho", p.songs[0].artist)
    }

    @Test
    fun textoParaCompartir() {
        val s = SetlistStore.create(app, "Serenata")
        SetlistStore.add(app, s.id, song(1, "Caballero Gaucho"))
        val texto = SetlistStore.asText(SetlistStore.get(app, s.id)!!)
        assertTrue(texto.contains("1. Canción 1 — Caballero Gaucho"))
    }

    @Test
    fun laPapeleraQuitaLaCancion() {
        val s = SetlistStore.create(app, "Con error")
        (1..3).forEach { SetlistStore.add(app, s.id, song(it)) }
        ActivityScenario.launch<SetlistActivity>(SetlistActivity.intent(app, s.id)).use { sc ->
            sc.onActivity { a ->
                val rv = a.findViewById<androidx.recyclerview.widget.RecyclerView>(R.id.songsList)
                rv.measure(
                    android.view.View.MeasureSpec.makeMeasureSpec(1080, android.view.View.MeasureSpec.EXACTLY),
                    android.view.View.MeasureSpec.makeMeasureSpec(1800, android.view.View.MeasureSpec.EXACTLY),
                )
                rv.layout(0, 0, 1080, 1800)
                val holder = rv.findViewHolderForAdapterPosition(1)!!
                holder.itemView.findViewById<android.view.View>(R.id.removeButton).performClick()
            }
        }
        assertEquals(listOf("Canción 1", "Canción 3"), SetlistStore.get(app, s.id)!!.items.map { it.title })
    }

    @Test
    fun cambiaEntreModoAgregarYReproducir() {
        val s = SetlistStore.create(app, "Modos")
        (1..3).forEach { SetlistStore.add(app, s.id, song(it)) }
        ActivityScenario.launch<SetlistActivity>(SetlistActivity.intent(app, s.id)).use { sc ->
            sc.onActivity { a ->
                val hint = a.findViewById<android.widget.TextView>(R.id.modeHint)
                a.findViewById<android.view.View>(R.id.modeAdd).performClick()
                assertTrue(hint.text.contains("AGREGAR"))
                a.findViewById<android.view.View>(R.id.modePlay).performClick()
                assertTrue(hint.text.contains("SUENE"))
            }
        }
    }

    @Test
    fun pantallasDeRepertorioAbren() {
        val s = SetlistStore.create(app, "Prueba")
        (1..3).forEach { SetlistStore.add(app, s.id, song(it)) }
        Library.entries = (1..10).map { song(it) }
        ActivityScenario.launch(SetlistsActivity::class.java).use { sc ->
            sc.onActivity { a -> a.findViewById<android.view.View>(R.id.importButton).performClick() }
            sc.onActivity { assertFalse(it.isFinishing) }
        }
        ActivityScenario.launch<SetlistActivity>(SetlistActivity.intent(app, s.id)).use { sc ->
            sc.onActivity { assertFalse(it.isFinishing) }
        }
    }
}
