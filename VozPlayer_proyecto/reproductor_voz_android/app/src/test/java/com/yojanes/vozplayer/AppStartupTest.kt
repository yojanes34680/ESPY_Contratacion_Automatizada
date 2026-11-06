package com.yojanes.vozplayer

import android.Manifest
import android.app.Application
import android.widget.FrameLayout
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import android.content.ComponentName
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

/**
 * Pruebas de humo: abren la app en un Android simulado para detectar cierres
 * inesperados al arrancar (lo que el usuario vería como "VozPlayer se detuvo").
 */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [34])
class AppStartupTest {

    /**
     * Robolectric no sabe conectar un MediaController con un MediaSessionService real
     * (entrega un ComponentName nulo). Se declara el servicio como no enlazable para
     * que la conexión falle de forma limpia, como ocurre si el servicio no responde.
     */
    @Before
    fun servicioNoEnlazable() {
        val app = ApplicationProvider.getApplicationContext<Application>()
        shadowOf(app).declareComponentUnbindable(ComponentName(app, PlaybackService::class.java))
    }

    @Test
    fun abreSinPermisos() {
        ActivityScenario.launch(MainActivity::class.java).use { s ->
            s.onActivity { assertEquals(false, it.isFinishing) }
        }
    }

    @Test
    fun abreConPermisos() {
        val app = ApplicationProvider.getApplicationContext<Application>()
        shadowOf(app).grantPermissions(
            Manifest.permission.READ_MEDIA_AUDIO,
            Manifest.permission.READ_MEDIA_VIDEO,
            Manifest.permission.READ_EXTERNAL_STORAGE,
        )
        ActivityScenario.launch(MainActivity::class.java).use { s ->
            s.onActivity { assertEquals(false, it.isFinishing) }
        }
    }

    @Test
    fun dibujaFilasDeLaLista() {
        ActivityScenario.launch(MainActivity::class.java).use { s ->
            s.onActivity { activity ->
                val adapter = MediaAdapter { }
                adapter.submit(
                    listOf(
                        MediaEntry("content://a/1", "Despacito", "Luis Fonsi", "", "despacito.mp3", 228_000, false),
                        MediaEntry("content://v/2", "Concierto", "", "", "concierto.mp4", 3_600_000, true),
                    ),
                )
                adapter.setPlaying("content://a/1")
                val parent = FrameLayout(activity)
                for (i in 0 until adapter.itemCount) {
                    val holder = adapter.onCreateViewHolder(parent, 0)
                    adapter.onBindViewHolder(holder, i)
                }
            }
        }
    }

    @Test
    fun abrePanelMaster() {
        ActivityScenario.launch(MixerActivity::class.java).use { s ->
            s.onActivity { assertEquals(false, it.isFinishing) }
        }
    }

    @Test
    fun abrePanelDeLetras() {
        ActivityScenario.launch(LyricsActivity::class.java).use { s ->
            s.onActivity { assertEquals(false, it.isFinishing) }
        }
    }

    @Test
    fun faderDelEcualizador() {
        ActivityScenario.launch(MainActivity::class.java).use { s ->
            s.onActivity { activity ->
                val fader = VerticalFader(activity).apply { min = -1500; max = 1500; value = 2000 }
                assertEquals(1500, fader.value)
            }
        }
    }

    @Test
    fun iniciaServicioDeReproduccion() {
        val controller = Robolectric.buildService(PlaybackService::class.java).create()
        controller.destroy()
    }
}
