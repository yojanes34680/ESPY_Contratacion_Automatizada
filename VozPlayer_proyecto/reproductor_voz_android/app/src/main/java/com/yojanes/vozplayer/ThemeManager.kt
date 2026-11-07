package com.yojanes.vozplayer

import android.app.Activity
import android.content.Context
import android.util.TypedValue
import androidx.annotation.AttrRes
import androidx.annotation.ColorInt

/** Plantillas de diseño que el usuario puede elegir. */
object ThemeManager {

    data class Template(
        val id: String,
        val name: String,
        val description: String,
        val styleRes: Int,
        /** Fondo (arriba, medio, abajo) y acentos, para la vista previa. */
        val background: IntArray,
        val accents: IntArray,
        val card: IntArray,
    )

    val templates = listOf(
        Template(
            "neon", "Neón nocturno", "Rosa, violeta y cian sobre la noche",
            R.style.Theme_VozPlayer,
            intArrayOf(0xFF0B0620.toInt(), 0xFF1B0A3C.toInt(), 0xFF3A0E4F.toInt()),
            intArrayOf(0xFFFF3D9A.toInt(), 0xFF8B5CF6.toInt(), 0xFF22D3EE.toInt(), 0xFFFF8A3D.toInt()),
            intArrayOf(0xFF8B5CF6.toInt(), 0xFFFF3D9A.toInt(), 0xFFFF8A3D.toInt()),
        ),
        Template(
            "ocean", "Océano", "Azules profundos y turquesa",
            R.style.Theme_VozPlayer_Ocean,
            intArrayOf(0xFF03111F.toInt(), 0xFF062A44.toInt(), 0xFF0B4A63.toInt()),
            intArrayOf(0xFF00C2FF.toInt(), 0xFF2563EB.toInt(), 0xFF5EEAD4.toInt(), 0xFF38BDF8.toInt()),
            intArrayOf(0xFF1D4ED8.toInt(), 0xFF0891B2.toInt(), 0xFF14B8A6.toInt()),
        ),
        Template(
            "sunset", "Atardecer", "Naranja, carmesí y dorado",
            R.style.Theme_VozPlayer_Sunset,
            intArrayOf(0xFF170507.toInt(), 0xFF3B0D12.toInt(), 0xFF6B1D1D.toInt()),
            intArrayOf(0xFFFF7A18.toInt(), 0xFFE11D48.toInt(), 0xFFFDE047.toInt(), 0xFFFB923C.toInt()),
            intArrayOf(0xFFBE123C.toInt(), 0xFFF97316.toInt(), 0xFFEAB308.toInt()),
        ),
        Template(
            "aurora", "Aurora boreal", "Verdes y violetas del cielo polar",
            R.style.Theme_VozPlayer_Aurora,
            intArrayOf(0xFF021613.toInt(), 0xFF06302B.toInt(), 0xFF0D3B4F.toInt()),
            intArrayOf(0xFF34D399.toInt(), 0xFF8B5CF6.toInt(), 0xFF67E8F9.toInt(), 0xFFA3E635.toInt()),
            intArrayOf(0xFF0F766E.toInt(), 0xFF10B981.toInt(), 0xFF8B5CF6.toInt()),
        ),
        Template(
            "gold", "Oro y negro", "Elegante, como un escenario de gala",
            R.style.Theme_VozPlayer_Gold,
            intArrayOf(0xFF070707.toInt(), 0xFF151310.toInt(), 0xFF2A2217.toInt()),
            intArrayOf(0xFFF5C542.toInt(), 0xFFB8860B.toInt(), 0xFFFDE68A.toInt(), 0xFFF59E0B.toInt()),
            intArrayOf(0xFF3F2E0C.toInt(), 0xFFB8860B.toInt(), 0xFFF5C542.toInt()),
        ),
        Template(
            "passion", "Rojo pasión", "Rojo intenso para rancheras y boleros",
            R.style.Theme_VozPlayer_Passion,
            intArrayOf(0xFF120208.toInt(), 0xFF2B0614.toInt(), 0xFF4A0A1F.toInt()),
            intArrayOf(0xFFFF1F5A.toInt(), 0xFFBE123C.toInt(), 0xFFFDA4AF.toInt(), 0xFFFF6B6B.toInt()),
            intArrayOf(0xFF9F1239.toInt(), 0xFFFF1F5A.toInt(), 0xFFFF8A3D.toInt()),
        ),
    )

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences("aspecto", Context.MODE_PRIVATE)

    fun current(context: Context): Template {
        val id = prefs(context).getString("plantilla", null)
        return templates.firstOrNull { it.id == id } ?: templates.first()
    }

    fun select(context: Context, template: Template) {
        prefs(context).edit().putString("plantilla", template.id).apply()
    }

    /** Se llama en cada pantalla antes de super.onCreate(). */
    fun apply(activity: Activity) {
        activity.setTheme(current(activity).styleRes)
    }
}

/** Color de la plantilla activa (p. ej. R.attr.vpAccent). */
@ColorInt
fun Context.themeColor(@AttrRes attr: Int): Int {
    val tv = TypedValue()
    theme.resolveAttribute(attr, tv, true)
    return if (tv.resourceId != 0 && tv.type !in TypedValue.TYPE_FIRST_COLOR_INT..TypedValue.TYPE_LAST_COLOR_INT) {
        androidx.core.content.ContextCompat.getColor(this, tv.resourceId)
    } else {
        tv.data
    }
}
