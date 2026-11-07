package com.yojanes.vozplayer

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
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

    /** Guardar copia de seguridad en un archivo elegido por el usuario. */
    private val exportLauncher =
        registerForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
            if (uri == null) return@registerForActivityResult
            val ok = runCatching {
                contentResolver.openOutputStream(uri, "wt")!!.use { it.write(SetlistStore.exportJson(this).toByteArray()) }
            }.isSuccess
            toast(getString(if (ok) R.string.backup_saved else R.string.backup_error))
        }

    /** Restaurar una copia de seguridad. */
    private val importLauncher =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri == null) return@registerForActivityResult
            val n = runCatching {
                val text = contentResolver.openInputStream(uri)!!.use { it.readBytes().toString(Charsets.UTF_8) }
                SetlistStore.importJson(this, text)
            }.getOrNull()
            if (n == null) {
                toast(getString(R.string.backup_error))
            } else {
                toast(resources.getQuantityString(R.plurals.backup_restored, n, n))
                refresh()
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        ThemeManager.apply(this)
        super.onCreate(savedInstanceState)
        binding = ActivitySetlistsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.closeButton.setOnClickListener { finish() }
        binding.setlistsList.layoutManager = LinearLayoutManager(this)
        binding.setlistsList.adapter = adapter
        binding.importButton.setOnClickListener { showImportFromText() }
        binding.backupButton.setOnClickListener { showBackupOptions() }
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

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_LONG).show()

    private fun showBackupOptions() {
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.backup_title)
            .setMessage(R.string.backup_message)
            .setPositiveButton(R.string.backup_save) { _, _ ->
                val date = SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(Date())
                exportLauncher.launch("VozPlayer_repertorios_$date.json")
            }
            .setNeutralButton(R.string.backup_restore) { _, _ ->
                importLauncher.launch(arrayOf("application/json", "text/plain", "application/octet-stream", "*/*"))
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    /** Pegar una lista compartida (o escrita a mano) y reconstruirla con las canciones de la carpeta. */
    private fun showImportFromText() {
        if (Library.entries.isEmpty()) {
            toast(getString(R.string.setlist_library_loading))
            return
        }
        val pad = (20 * resources.displayMetrics.density).toInt()
        val input = EditText(this).apply {
            hint = getString(R.string.setlist_import_hint)
            minLines = 6
            maxLines = 12
            gravity = android.view.Gravity.TOP or android.view.Gravity.START
        }
        val clip = (getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager).primaryClip
        clip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)?.toString()
            ?.takeIf { SharedListParser.parse(it).songs.isNotEmpty() }
            ?.let { input.setText(it) }
        val box = FrameLayout(this).apply {
            setPadding(pad, pad / 2, pad, 0)
            addView(input)
        }
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.setlist_import)
            .setMessage(R.string.setlist_import_message)
            .setView(box)
            .setPositiveButton(R.string.setlist_import_go) { _, _ -> importText(input.text.toString()) }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun importText(text: String) {
        val parsed = SharedListParser.parse(text)
        if (parsed.songs.isEmpty()) {
            toast(getString(R.string.setlist_import_nothing))
            return
        }
        lifecycleScope.launch {
            val (found, missing) = withContext(Dispatchers.Default) {
                val index = VoiceSearchMatcher.prepare(Library.entries)
                val found = mutableListOf<MediaEntry>()
                val missing = mutableListOf<String>()
                for (song in parsed.songs) {
                    val best = VoiceSearchMatcher.rankPrepared(song.query, index, threshold = 0.6).firstOrNull()
                    if (best != null && found.none { it.uri == best.entry.uri }) found += best.entry
                    else if (best == null) missing += song.title + (if (song.artist.isNotBlank()) " — " + song.artist else "")
                }
                found to missing
            }
            val s = SetlistStore.create(this@SetlistsActivity, parsed.name ?: getString(R.string.setlist_imported_name))
            SetlistStore.save(this@SetlistsActivity, s.copy(items = found))
            refresh()
            val msg = buildString {
                append(getString(R.string.setlist_import_result, found.size, parsed.songs.size))
                if (missing.isNotEmpty()) {
                    append("\n\n").append(getString(R.string.setlist_import_missing)).append("\n")
                    missing.forEach { append("• ").append(it).append("\n") }
                }
            }
            MaterialAlertDialogBuilder(this@SetlistsActivity)
                .setTitle(s.name)
                .setMessage(msg)
                .setPositiveButton(R.string.setlist_open) { _, _ ->
                    startActivity(SetlistActivity.intent(this@SetlistsActivity, s.id))
                }
                .setNegativeButton(R.string.close, null)
                .show()
        }
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
