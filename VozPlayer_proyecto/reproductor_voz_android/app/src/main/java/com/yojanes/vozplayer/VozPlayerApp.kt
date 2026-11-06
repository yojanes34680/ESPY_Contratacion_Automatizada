package com.yojanes.vozplayer

import android.app.Application
import android.os.Build
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter

/**
 * Si la app se cierra por un error, guarda el detalle para mostrarlo en pantalla
 * la próxima vez que se abra (así el usuario puede enviar una captura).
 */
class VozPlayerApp : Application() {

    override fun onCreate() {
        super.onCreate()
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            runCatching {
                val sw = StringWriter()
                error.printStackTrace(PrintWriter(sw))
                crashFile(this).writeText(
                    "VozPlayer ${BuildConfig.VERSION_NAME} · Android ${Build.VERSION.RELEASE} " +
                        "(API ${Build.VERSION.SDK_INT}) · ${Build.MANUFACTURER} ${Build.MODEL}\n\n$sw",
                )
            }
            previous?.uncaughtException(thread, error)
        }
    }

    companion object {
        fun crashFile(app: Application): File = File(app.filesDir, "ultimo_error.txt")
    }
}
