package com.yojanes.vozplayer

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import com.google.android.material.color.MaterialColors

/** Barra deslizante vertical, como el fader de una consola de sonido. */
class VerticalFader @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {

    var min = -1500
        set(v) { field = v; invalidate() }
    var max = 1500
        set(v) { field = v; invalidate() }
    var value = 0
        set(v) { field = v.coerceIn(min, max); invalidate() }

    /** (valor, cambiadoPorElUsuario) */
    var onValueChange: ((Int) -> Unit)? = null

    private val density = resources.displayMetrics.density
    private val primary = MaterialColors.getColor(this, androidx.appcompat.R.attr.colorPrimary)
    private val onSurface = MaterialColors.getColor(this, com.google.android.material.R.attr.colorOnSurface)

    private val trackPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = onSurface; alpha = 50 }
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = primary }
    private val zeroPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = onSurface; alpha = 120; strokeWidth = 1.5f * density }
    private val thumbPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = primary }
    private val thumbLine = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFFFFF.toInt(); strokeWidth = 2 * density }

    private val pad = 14 * density
    private val rect = RectF()

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val w = resolveSize((48 * density).toInt(), widthMeasureSpec)
        val h = resolveSize((200 * density).toInt(), heightMeasureSpec)
        setMeasuredDimension(w, h)
    }

    private fun yFor(v: Int): Float {
        val frac = (v - min).toFloat() / (max - min).coerceAtLeast(1)
        return height - pad - frac * (height - 2 * pad)
    }

    override fun onDraw(canvas: Canvas) {
        val cx = width / 2f
        val trackW = 6 * density
        rect.set(cx - trackW / 2, pad, cx + trackW / 2, height - pad)
        canvas.drawRoundRect(rect, trackW, trackW, trackPaint)

        val zero = (if (min < 0 && max > 0) 0 else min)
        val yZero = yFor(zero)
        val yVal = yFor(value)
        rect.set(cx - trackW / 2, minOf(yZero, yVal), cx + trackW / 2, maxOf(yZero, yVal))
        canvas.drawRect(rect, fillPaint)
        canvas.drawLine(cx - 12 * density, yZero, cx + 12 * density, yZero, zeroPaint)

        val tw = 18 * density
        val th = 10 * density
        rect.set(cx - tw, yVal - th, cx + tw, yVal + th)
        canvas.drawRoundRect(rect, 4 * density, 4 * density, thumbPaint)
        canvas.drawLine(cx - tw + 6 * density, yVal, cx + tw - 6 * density, yVal, thumbLine)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (!isEnabled) return false
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> {
                parent?.requestDisallowInterceptTouchEvent(true)
                val frac = ((height - pad - event.y) / (height - 2 * pad)).coerceIn(0f, 1f)
                var v = (min + frac * (max - min)).toInt()
                if (min < 0 && max > 0 && kotlin.math.abs(v) < (max - min) / 40) v = 0 // imán al 0
                if (v != value) {
                    value = v
                    onValueChange?.invoke(v)
                }
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                parent?.requestDisallowInterceptTouchEvent(false)
                performClick()
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    override fun performClick(): Boolean = super.performClick()
}
