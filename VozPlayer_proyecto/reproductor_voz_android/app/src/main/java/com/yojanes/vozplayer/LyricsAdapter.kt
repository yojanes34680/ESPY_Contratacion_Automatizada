package com.yojanes.vozplayer

import android.graphics.Typeface
import android.util.TypedValue
import android.view.Gravity
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

/** Líneas de la letra; la que se está cantando se resalta. */
class LyricsAdapter(
    private val onLineClick: (LyricLine) -> Unit,
) : RecyclerView.Adapter<LyricsAdapter.Holder>() {

    private var lines: List<LyricLine> = emptyList()
    private var synced = false
    private var current = -1
    var textSizeSp = 26f
        set(v) { field = v; notifyDataSetChanged() }

    fun submit(newLines: List<LyricLine>, isSynced: Boolean) {
        lines = newLines
        synced = isSynced
        current = -1
        notifyDataSetChanged()
    }

    fun setCurrent(index: Int) {
        if (index == current) return
        val old = current
        current = index
        if (old in lines.indices) notifyItemChanged(old)
        if (index in lines.indices) notifyItemChanged(index)
    }

    override fun getItemCount() = lines.size

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val tv = TextView(parent.context).apply {
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            gravity = Gravity.CENTER_HORIZONTAL
            val pad = (8 * resources.displayMetrics.density).toInt()
            setPadding(pad * 2, pad, pad * 2, pad)
        }
        return Holder(tv)
    }

    override fun onBindViewHolder(holder: Holder, position: Int) {
        val line = lines[position]
        val tv = holder.text
        tv.text = line.text.ifBlank { "♪" }
        val isCurrent = synced && position == current
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, if (isCurrent) textSizeSp * 1.15f else textSizeSp)
        tv.setTypeface(null, if (isCurrent) Typeface.BOLD else Typeface.NORMAL)
        tv.alpha = when {
            !synced -> 1f
            isCurrent -> 1f
            position < current -> 0.35f
            else -> 0.6f
        }
        tv.setOnClickListener { if (synced) onLineClick(line) }
    }

    class Holder(val text: TextView) : RecyclerView.ViewHolder(text)
}
