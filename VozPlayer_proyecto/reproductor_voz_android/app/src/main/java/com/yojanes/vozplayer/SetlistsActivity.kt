package com.yojanes.vozplayer

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.FrameLayout
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.yojanes.vozplayer.databinding.ActivitySetlistsBinding
import com.yojanes.vozplayer.databinding.ItemSetlistBinding

/** Lista de repertorios del cantante. */
class SetlistsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySetlistsBinding
    private val adapter = Adapter(
        onOpen = { s -> startActivity(SetlistActivity.intent(this, s.id)) },
        onMore = { s -> showOptions(s) },
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        ThemeManager.apply(this)
        super.onCreate(savedInstanceState)
        binding = ActivitySetlistsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.closeButton.setOnClickListener { finish() }
        binding.setlistsList.layoutManager = LinearLayoutManager(this)
        binding.setlistsList.adapter = adapter
        binding.newSetlistButton.setOnClickListener {
            askName(this, getString(R.string.setlist_new), "") { name ->
                val s = SetlistStore.create(this, name)
                startActivity(SetlistActivity.intent(this, s.id))
            }
        }
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun refresh() {
        val lists = SetlistStore.all(this).sortedByDescending { it.created }
        adapter.submit(lists)
        binding.emptyText.visibility = if (lists.isEmpty()) View.VISIBLE else View.GONE
    }

    private fun showOptions(s: SetlistStore.Setlist) {
        MaterialAlertDialogBuilder(this)
            .setTitle(s.name)
            .setItems(
                arrayOf(getString(R.string.setlist_rename), getString(R.string.setlist_share), getString(R.string.setlist_delete)),
            ) { _, which ->
                when (which) {
                    0 -> askName(this, getString(R.string.setlist_rename), s.name) { name ->
                        SetlistStore.save(this, s.copy(name = name))
                        refresh()
                    }
                    1 -> share(this, s)
                    else -> confirmDelete(this, s) { refresh() }
                }
            }
            .show()
    }

    private class Adapter(
        val onOpen: (SetlistStore.Setlist) -> Unit,
        val onMore: (SetlistStore.Setlist) -> Unit,
    ) : RecyclerView.Adapter<Adapter.Holder>() {
        private var items: List<SetlistStore.Setlist> = emptyList()

        fun submit(list: List<SetlistStore.Setlist>) {
            items = list
            notifyDataSetChanged()
        }

        override fun getItemCount() = items.size

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
            Holder(ItemSetlistBinding.inflate(LayoutInflater.from(parent.context), parent, false))

        override fun onBindViewHolder(holder: Holder, position: Int) {
            val s = items[position]
            val b = holder.b
            val ctx = b.root.context
            b.setlistName.text = s.name
            b.setlistInfo.text = describe(ctx, s)
            b.setlistPreview.text = s.items.take(4).joinToString(" · ") { it.title }
            b.setlistIcon.background = Artwork.background(s.id, 16 * ctx.resources.displayMetrics.density)
            b.root.setOnClickListener { onOpen(s) }
            b.root.setOnLongClickListener { onMore(s); true }
        }

        class Holder(val b: ItemSetlistBinding) : RecyclerView.ViewHolder(b.root)
    }

    companion object {
        fun describe(ctx: Context, s: SetlistStore.Setlist): String {
            val n = ctx.resources.getQuantityString(R.plurals.songs_count, s.items.size, s.items.size)
            val total = s.totalMs
            return if (total > 0) n + "  ·  " + MediaAdapter.formatDuration(total) else n
        }

        fun askName(ctx: Context, title: String, current: String, onOk: (String) -> Unit) {
            val pad = (20 * ctx.resources.displayMetrics.density).toInt()
            val input = EditText(ctx).apply {
                hint = ctx.getString(R.string.setlist_name_hint)
                setText(current)
                setSelection(current.length)
                setSingleLine()
            }
            val box = FrameLayout(ctx).apply {
                setPadding(pad, pad / 2, pad, 0)
                addView(input)
            }
            MaterialAlertDialogBuilder(ctx)
                .setTitle(title)
                .setView(box)
                .setPositiveButton(android.R.string.ok) { _, _ ->
                    val name = input.text.toString().trim()
                    if (name.isNotBlank()) onOk(name)
                }
                .setNegativeButton(android.R.string.cancel, null)
                .show()
        }

        fun share(ctx: Context, s: SetlistStore.Setlist) {
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_SUBJECT, s.name)
                putExtra(Intent.EXTRA_TEXT, SetlistStore.asText(s))
            }
            ctx.startActivity(Intent.createChooser(send, ctx.getString(R.string.setlist_share)))
        }

        fun confirmDelete(ctx: Context, s: SetlistStore.Setlist, onDone: () -> Unit) {
            MaterialAlertDialogBuilder(ctx)
                .setTitle(R.string.setlist_delete)
                .setMessage(ctx.getString(R.string.setlist_delete_confirm, s.name))
                .setPositiveButton(R.string.setlist_delete) { _, _ ->
                    SetlistStore.delete(ctx, s.id)
                    onDone()
                }
                .setNegativeButton(android.R.string.cancel, null)
                .show()
        }
    }
}
