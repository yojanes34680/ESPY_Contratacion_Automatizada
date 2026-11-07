package com.yojanes.vozplayer

import android.app.Activity
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import com.google.android.material.dialog.MaterialAlertDialogBuilder

/** Selector de plantillas con vista previa de cada una. */
object ThemePicker {

    fun show(activity: Activity) {
        val d = activity.resources.displayMetrics.density
        fun dp(v: Int) = (v * d).toInt()
        val current = ThemeManager.current(activity)
        var dialog: AlertDialog? = null

        val list = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(4), dp(16), dp(8))
        }
        ThemeManager.templates.forEach { t ->
            list.addView(card(activity, t, t.id == current.id, ::dp) {
                ThemeManager.select(activity, t)
                dialog?.dismiss()
                activity.recreate()
            })
        }
        dialog = MaterialAlertDialogBuilder(activity)
            .setTitle(R.string.theme_title)
            .setMessage(R.string.theme_message)
            .setView(ScrollView(activity).apply { addView(list) })
            .setNegativeButton(R.string.close, null)
            .show()
    }

    private fun card(
        activity: Activity,
        t: ThemeManager.Template,
        selected: Boolean,
        dp: (Int) -> Int,
        onPick: () -> Unit,
    ): View {
        val root = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), dp(12), dp(14), dp(12))
            background = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, t.background).apply {
                cornerRadius = dp(20).toFloat()
                setStroke(if (selected) dp(3) else dp(1), if (selected) t.accents[0] else 0x33FFFFFF)
            }
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = dp(10) }
            isClickable = true
            isFocusable = true
            setOnClickListener { onPick() }
            contentDescription = t.name
        }
        // Mini panel "Sonando ahora" con los colores de la plantilla.
        val mini = TextView(activity).apply {
            text = "▶"
            gravity = Gravity.CENTER
            textSize = 18f
            setTextColor(0xFFFFFFFF.toInt())
            background = GradientDrawable(GradientDrawable.Orientation.TL_BR, t.card).apply {
                cornerRadius = dp(14).toFloat()
            }
        }
        root.addView(mini, LinearLayout.LayoutParams(dp(54), dp(54)))

        val texts = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), 0, dp(8), 0)
        }
        texts.addView(TextView(activity).apply {
            text = if (selected) "✔  ${t.name}" else t.name
            textSize = 17f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(0xFFFFFFFF.toInt())
        })
        texts.addView(TextView(activity).apply {
            text = t.description
            textSize = 12f
            setTextColor(0xB3FFFFFF.toInt())
        })
        // Barra de progreso de ejemplo con el acento.
        texts.addView(View(activity).apply {
            background = GradientDrawable(
                GradientDrawable.Orientation.LEFT_RIGHT, intArrayOf(t.accents[0], t.accents[1]),
            ).apply { cornerRadius = dp(3).toFloat() }
        }, LinearLayout.LayoutParams(dp(110), dp(5)).apply { topMargin = dp(8) })
        root.addView(texts, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))

        val dots = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }
        t.accents.forEach { c ->
            dots.addView(View(activity).apply {
                background = GradientDrawable().apply {
                    shape = GradientDrawable.OVAL
                    setColor(c)
                }
            }, LinearLayout.LayoutParams(dp(12), dp(12)).apply { topMargin = dp(3) })
        }
        root.addView(dots)
        return root
    }
}
