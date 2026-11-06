package com.yojanes.vozplayer

import android.graphics.drawable.GradientDrawable

/** Portadas de colores (degradado + inicial) para pistas sin carátula. */
object Artwork {

    private val PALETTE = listOf(
        0xFFFF3D9A to 0xFFFF8A3D, // rosa → naranja
        0xFF8B5CF6 to 0xFF22D3EE, // violeta → cian
        0xFF22D3EE to 0xFF34D399, // cian → verde
        0xFFFF8A3D to 0xFFFACC15, // naranja → amarillo
        0xFFFF3D9A to 0xFF8B5CF6, // rosa → violeta
        0xFF3B82F6 to 0xFF22D3EE, // azul → cian
        0xFFEC4899 to 0xFFF43F5E, // fucsia → rojo
    )

    fun background(key: String, radiusPx: Float): GradientDrawable {
        val (a, b) = PALETTE[(key.hashCode() and Int.MAX_VALUE) % PALETTE.size]
        return GradientDrawable(GradientDrawable.Orientation.TL_BR, intArrayOf(a.toInt(), b.toInt())).apply {
            cornerRadius = radiusPx
        }
    }

    fun initial(title: String): String =
        title.trim().firstOrNull { it.isLetterOrDigit() }?.uppercaseChar()?.toString() ?: "♪"
}
