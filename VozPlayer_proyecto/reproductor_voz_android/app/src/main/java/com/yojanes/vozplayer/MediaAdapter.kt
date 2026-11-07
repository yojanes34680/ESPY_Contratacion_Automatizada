package com.yojanes.vozplayer

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.yojanes.vozplayer.databinding.ItemMediaBinding
import java.util.Locale

class MediaAdapter(
    private val onClick: (position: Int) -> Unit,
) : RecyclerView.Adapter<MediaAdapter.Holder>() {

    private var items: List<MediaEntry> = emptyList()
    private var playingUri: String? = null

    fun submit(newItems: List<MediaEntry>) {
        items = newItems
        notifyDataSetChanged()
    }

    fun setPlaying(uri: String?) {
        if (uri == playingUri) return
        val old = playingUri
        playingUri = uri
        // Solo se redibujan las dos filas que cambian, no toda la lista.
        items.indexOfFirst { it.uri == old }.takeIf { it >= 0 }?.let { notifyItemChanged(it) }
        items.indexOfFirst { it.uri == uri }.takeIf { it >= 0 }?.let { notifyItemChanged(it) }
    }

    override fun getItemCount() = items.size

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder =
        Holder(ItemMediaBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: Holder, position: Int) {
        val item = items[position]
        val b = holder.binding
        b.title.text = item.title
        b.subtitle.text = listOf(
            item.artist,
            formatDuration(item.durationMs),
            item.extension,
        ).filter { it.isNotBlank() }.joinToString("  ·  ")
        val playing = item.uri == playingUri
        val density = b.root.resources.displayMetrics.density
        b.artwork.background = Artwork.background(item.uri, 14 * density)
        b.artwork.text = if (playing) "▶" else Artwork.initial(item.title)
        b.icon.setImageResource(if (item.isVideo) R.drawable.ic_video else R.drawable.ic_music)
        b.root.isActivated = playing
        b.root.setOnClickListener {
            val pos = holder.bindingAdapterPosition
            if (pos != RecyclerView.NO_POSITION) onClick(pos)
        }
    }

    class Holder(val binding: ItemMediaBinding) : RecyclerView.ViewHolder(binding.root)

    companion object {
        fun formatDuration(ms: Long): String {
            if (ms <= 0) return ""
            val total = ms / 1000
            val h = total / 3600
            val m = (total % 3600) / 60
            val s = total % 60
            return if (h > 0) String.format(Locale.ROOT, "%d:%02d:%02d", h, m, s)
            else String.format(Locale.ROOT, "%d:%02d", m, s)
        }
    }
}
