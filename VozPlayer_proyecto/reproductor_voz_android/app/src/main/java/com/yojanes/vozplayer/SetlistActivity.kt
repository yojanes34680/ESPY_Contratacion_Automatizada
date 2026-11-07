package com.yojanes.vozplayer

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognizerIntent
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.OptIn
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import androidx.recyclerview.widget.ItemTouchHelper
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.snackbar.Snackbar
import com.google.common.util.concurrent.ListenableFuture
import com.yojanes.vozplayer.databinding.ActivitySetlistBinding
import com.yojanes.vozplayer.databinding.ItemSetlistSongBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

/**
 * Un repertorio: canciones en el orden del cantante.
 * Se agregan dictando (con dictado continuo y varias canciones a la vez) o buscando;
 * se ordenan arrastrando el asa ≡ y se quitan deslizando hacia un lado.
 */
@OptIn(UnstableApi::class)
class SetlistActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySetlistBinding
    private lateinit var setlistId: String
    private var setlist: SetlistStore.Setlist? = null
    private val items = mutableListOf<MediaEntry>()

    private var controllerFuture: ListenableFuture<MediaController>? = null
    private val controller: MediaController?
        get() = controllerFuture?.takeIf { it.isDone }?.let { runCatching { it.get() }.getOrNull() }

    private var index: List<VoiceSearchMatcher.Prepared>? = null
    private var indexSource: List<MediaEntry>? = null

    /** Modo del micrófono: agregar canciones (de la carpeta) o reproducir canciones (del repertorio). */
    private enum class VoiceMode { ADD, PLAY }
    private var voiceMode = VoiceMode.ADD
    private var listeningFor = VoiceMode.ADD

    /** Dictado continuo: tras agregar, el micrófono se vuelve a abrir solo. */
    private var continuous = false
    private val pendingParts = ArrayDeque<String>()

    private lateinit var touchHelper: ItemTouchHelper
    private val adapter = SongAdapter(
        onClick = { pos -> playFrom(pos) },
        onRemove = { pos -> removeAt(pos) },
        onMenu = { pos -> showSongMenu(pos) },
        onStartDrag = { holder -> touchHelper.startDrag(holder) },
    )

    private val speechLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            val alternatives = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS).orEmpty()
            if (result.resultCode == RESULT_OK && alternatives.isNotEmpty()) {
                if (listeningFor == VoiceMode.PLAY) handlePlayRequest(alternatives) else handleDictation(alternatives)
            } else {
                continuous = false
            }
        }

    private val playerListener = object : Player.Listener {
        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
            adapter.setPlaying(mediaItem?.mediaId)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        ThemeManager.apply(this)
        super.onCreate(savedInstanceState)
        binding = ActivitySetlistBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setlistId = intent.getStringExtra(EXTRA_ID).orEmpty()
        val s = SetlistStore.get(this, setlistId)
        if (s == null) {
            finish()
            return
        }
        setlist = s
        items += relink(s.items)
        if (items != s.items) SetlistStore.save(this, s.copy(items = items.toList()))

        binding.songsList.layoutManager = LinearLayoutManager(this)
        binding.songsList.adapter = adapter
        touchHelper = ItemTouchHelper(TouchCallback())
        touchHelper.attachToRecyclerView(binding.songsList)

        binding.closeButton.setOnClickListener { finish() }
        binding.setlistName.setOnClickListener { rename() }
        binding.playAllButton.setOnClickListener { playFrom(0) }
        val prefs = getSharedPreferences("vista", MODE_PRIVATE)
        voiceMode = when {
            items.isEmpty() -> VoiceMode.ADD
            prefs.getString("modo_voz", "reproducir") == "agregar" -> VoiceMode.ADD
            else -> VoiceMode.PLAY
        }
        binding.voiceMode.check(if (voiceMode == VoiceMode.ADD) R.id.modeAdd else R.id.modePlay)
        binding.voiceMode.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (!isChecked) return@addOnButtonCheckedListener
            voiceMode = if (checkedId == R.id.modePlay) VoiceMode.PLAY else VoiceMode.ADD
            prefs.edit().putString("modo_voz", if (voiceMode == VoiceMode.PLAY) "reproducir" else "agregar").apply()
            updateModeHint()
        }
        updateModeHint()
        binding.dictateButton.setOnClickListener {
            if (voiceMode == VoiceMode.PLAY) {
                startPlayDictation()
            } else {
                continuous = true
                startDictation()
            }
        }
        binding.searchAddButton.setOnClickListener { searchByText() }
        binding.shareButton.setOnClickListener { setlist?.let { SetlistsActivity.share(this, current()) } }
        binding.moreButton.setOnClickListener { showOptions() }
        refreshUi()
    }

    override fun onStart() {
        super.onStart()
        val token = SessionToken(this, ComponentName(this, PlaybackService::class.java))
        val future = MediaController.Builder(this, token).buildAsync()
        controllerFuture = future
        future.addListener({
            val c = controller ?: return@addListener
            binding.nowPlaying.player = c
            c.addListener(playerListener)
            adapter.setPlaying(c.currentMediaItem?.mediaId)
        }, ContextCompat.getMainExecutor(this))
    }

    override fun onStop() {
        controller?.removeListener(playerListener)
        binding.nowPlaying.player = null
        controllerFuture?.let { MediaController.releaseFuture(it) }
        controllerFuture = null
        super.onStop()
    }

    // ---------------------------------------------------------------- Datos

    private fun current(): SetlistStore.Setlist = setlist!!.copy(items = items.toList())

    private fun persist() {
        val s = current()
        setlist = s
        SetlistStore.save(this, s)
        refreshUi()
    }

    private fun refreshUi() {
        val s = current()
        binding.setlistName.text = s.name
        binding.setlistInfo.text = SetlistsActivity.describe(this, s)
        adapter.submit(items)
        binding.emptyText.visibility = if (items.isEmpty()) View.VISIBLE else View.GONE
        binding.playAllButton.isEnabled = items.isNotEmpty()
    }

    /**
     * Si una canción del repertorio ya no está en la biblioteca con la misma dirección
     * (por ejemplo, tras reinstalar o volver a elegir la carpeta), se busca por nombre de archivo.
     */
    private fun relink(list: List<MediaEntry>): List<MediaEntry> {
        val lib = Library.entries
        if (lib.isEmpty()) return list
        val byUri = lib.associateBy { it.uri }
        val byName = lib.groupBy { it.displayName.lowercase() }
        return list.map { e ->
            if (byUri.containsKey(e.uri)) e
            else byName[e.displayName.lowercase()]?.firstOrNull() ?: e
        }
    }

    private fun addEntry(e: MediaEntry): Boolean {
        if (items.any { it.uri == e.uri }) {
            toast(getString(R.string.setlist_already, e.title))
            return false
        }
        items += e
        persist()
        binding.songsList.scrollToPosition(items.size - 1)
        Snackbar.make(binding.root, getString(R.string.setlist_added, items.size, e.title), Snackbar.LENGTH_SHORT)
            .setAnchorView(binding.nowPlaying)
            .show()
        return true
    }

    private suspend fun preparedIndex(): List<VoiceSearchMatcher.Prepared> {
        val entries = Library.entries
        if (indexSource === entries) index?.let { return it }
        val prepared = withContext(Dispatchers.Default) { VoiceSearchMatcher.prepare(entries) }
        index = prepared
        indexSource = entries
        return prepared
    }

    // ---------------------------------------------------------------- Dictado

    private fun updateModeHint() {
        binding.modeHint.text = getString(
            if (voiceMode == VoiceMode.PLAY) R.string.voice_mode_play_hint else R.string.voice_mode_add_hint,
        )
        binding.dictateButton.contentDescription = getString(
            if (voiceMode == VoiceMode.PLAY) R.string.voice_mode_play else R.string.voice_mode_add,
        )
    }

    private fun launchRecognizer(mode: VoiceMode, prompt: String): Boolean {
        listeningFor = mode
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5)
            putExtra(RecognizerIntent.EXTRA_PROMPT, prompt)
        }
        return try {
            speechLauncher.launch(intent)
            true
        } catch (_: ActivityNotFoundException) {
            toast(getString(R.string.no_voice_engine))
            false
        }
    }

    // ---------------------------------------------------------------- Reproducir por voz

    private fun startPlayDictation() {
        if (items.isEmpty()) {
            toast(getString(R.string.setlist_empty_play))
            return
        }
        launchRecognizer(VoiceMode.PLAY, getString(R.string.voice_play_prompt))
    }

    /** Busca lo dicho SOLO dentro del repertorio y lo reproduce (por nombre o por número). */
    private fun handlePlayRequest(alternatives: List<String>) {
        val number = alternatives.firstNotNullOfOrNull { SetlistVoice.parseNumber(it) }
        if (number != null) {
            if (number in 1..items.size) {
                playFrom(number - 1)
                toast(getString(R.string.voice_play_now, number, items[number - 1].title))
            } else {
                toast(getString(R.string.voice_play_number_missing, number, items.size))
            }
            return
        }
        lifecycleScope.launch {
            val snapshot = items.toList()
            val (spoken, ranked) = withContext(Dispatchers.Default) {
                val idx = VoiceSearchMatcher.prepare(snapshot)
                val best = VoiceSearchMatcher.bestVoiceMatchPrepared(alternatives, idx)
                val said = best?.spokenText ?: alternatives.first()
                said to VoiceSearchMatcher.rankPrepared(said, idx, threshold = 0.5)
            }
            if (ranked.isEmpty()) {
                toast(getString(R.string.voice_play_not_found, spoken))
                return@launch
            }
            val top = ranked[0]
            val clear = top.score >= 0.75 && (ranked.size == 1 || ranked[1].score < top.score - 0.08)
            if (clear) {
                playEntry(top.entry)
            } else {
                val options = ranked.take(6).map { it.entry }
                val labels = options.map { e ->
                    val n = items.indexOfFirst { it.uri == e.uri } + 1
                    "#$n   " + e.title + (if (e.artist.isNotBlank()) "  —  " + e.artist else "")
                }
                MaterialAlertDialogBuilder(this@SetlistActivity)
                    .setTitle(getString(R.string.voice_play_choose, spoken))
                    .setItems(labels.toTypedArray()) { _, which -> playEntry(options[which]) }
                    .setNegativeButton(android.R.string.cancel, null)
                    .show()
            }
        }
    }

    private fun playEntry(e: MediaEntry) {
        val pos = items.indexOfFirst { it.uri == e.uri }
        if (pos < 0) return
        playFrom(pos)
        binding.songsList.smoothScrollToPosition(pos)
        toast(getString(R.string.voice_play_now, pos + 1, e.title))
    }

    // ---------------------------------------------------------------- Agregar por voz

    private fun startDictation() {
        if (Library.entries.isEmpty()) {
            toast(getString(R.string.setlist_library_loading))
            continuous = false
            return
        }
        if (!launchRecognizer(VoiceMode.ADD, getString(R.string.setlist_dictate_prompt, items.size + 1))) {
            continuous = false
        }
    }

    private fun handleDictation(alternatives: List<String>) {
        lifecycleScope.launch {
            val idx = preparedIndex()
            val parts = DictationSplitter.split(alternatives.first())
            pendingParts.clear()
            if (parts.size > 1) {
                pendingParts.addAll(parts)
            } else {
                val best = withContext(Dispatchers.Default) { VoiceSearchMatcher.bestVoiceMatchPrepared(alternatives, idx) }
                pendingParts.add(best?.spokenText ?: alternatives.first())
            }
            processNextPart()
        }
    }

    /** Procesa las canciones dictadas una por una; al terminar, si es continuo, vuelve a escuchar. */
    private fun processNextPart() {
        val part = pendingParts.removeFirstOrNull()
        if (part == null) {
            if (continuous) startDictation()
            return
        }
        lifecycleScope.launch {
            val idx = preparedIndex()
            val results = withContext(Dispatchers.Default) { VoiceSearchMatcher.rankPrepared(part, idx).take(6) }
            when {
                results.isEmpty() -> {
                    toast(getString(R.string.no_results, part))
                    processNextPart()
                }
                // Coincidencia clarísima y única: se agrega sin preguntar.
                results[0].score >= 0.97 && (results.size == 1 || results[1].score < 0.8) -> {
                    addEntry(results[0].entry)
                    processNextPart()
                }
                else -> chooseFor(part, results.map { it.entry })
            }
        }
    }

    private fun chooseFor(part: String, options: List<MediaEntry>) {
        val labels = options.map { e ->
            (if (e.isVideo) "🎬  " else "🎵  ") + e.title + (if (e.artist.isNotBlank()) "  —  " + e.artist else "")
        }
        MaterialAlertDialogBuilder(this)
            .setTitle(getString(R.string.setlist_choose_for, part))
            .setItems(labels.toTypedArray()) { _, which ->
                addEntry(options[which])
                processNextPart()
            }
            .setNeutralButton(R.string.setlist_skip) { _, _ -> processNextPart() }
            .setNegativeButton(R.string.setlist_stop) { _, _ ->
                continuous = false
                pendingParts.clear()
            }
            .setCancelable(false)
            .show()
    }

    private fun searchByText() {
        if (Library.entries.isEmpty()) {
            toast(getString(R.string.setlist_library_loading))
            return
        }
        val pad = (20 * resources.displayMetrics.density).toInt()
        val input = EditText(this).apply {
            hint = getString(R.string.search_hint)
            setSingleLine()
        }
        val box = FrameLayout(this).apply {
            setPadding(pad, pad / 2, pad, 0)
            addView(input)
        }
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.setlist_search_add)
            .setMessage(R.string.setlist_search_message)
            .setView(box)
            .setPositiveButton(R.string.lyrics_search_go) { _, _ ->
                val text = input.text.toString().trim()
                if (text.isBlank()) return@setPositiveButton
                continuous = false
                pendingParts.clear()
                pendingParts.addAll(DictationSplitter.split(text))
                processNextPart()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    // ---------------------------------------------------------------- Reproducción

    private fun playFrom(position: Int) {
        val c = controller ?: return toast(getString(R.string.player_connecting))
        if (position !in items.indices) return
        PlayGate.markPlayRequested()
        c.setMediaItems(items.map { it.toMediaItem() }, position, 0L)
        c.prepare()
        c.play()
    }

    // ---------------------------------------------------------------- Opciones

    private fun rename() {
        SetlistsActivity.askName(this, getString(R.string.setlist_rename), current().name) { name ->
            setlist = current().copy(name = name)
            persist()
        }
    }

    private fun showOptions() {
        MaterialAlertDialogBuilder(this)
            .setItems(
                arrayOf(
                    getString(R.string.setlist_rename),
                    getString(R.string.setlist_share),
                    getString(R.string.setlist_clear),
                    getString(R.string.setlist_delete),
                ),
            ) { _, which ->
                when (which) {
                    0 -> rename()
                    1 -> SetlistsActivity.share(this, current())
                    2 -> MaterialAlertDialogBuilder(this)
                        .setMessage(R.string.setlist_clear_confirm)
                        .setPositiveButton(R.string.setlist_clear) { _, _ ->
                            items.clear()
                            persist()
                        }
                        .setNegativeButton(android.R.string.cancel, null)
                        .show()
                    else -> SetlistsActivity.confirmDelete(this, current()) { finish() }
                }
            }
            .show()
    }

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()

    /** Quita una canción del repertorio (no la borra del teléfono), con opción de deshacer. */
    private fun removeAt(pos: Int) {
        if (pos !in items.indices) return
        val removed = items.removeAt(pos)
        persist()
        Snackbar.make(binding.root, getString(R.string.setlist_removed, removed.title), Snackbar.LENGTH_LONG)
            .setAnchorView(binding.nowPlaying)
            .setAction(R.string.setlist_undo) {
                items.add(pos.coerceAtMost(items.size), removed)
                persist()
            }
            .show()
    }

    private fun move(pos: Int, delta: Int) {
        val target = pos + delta
        if (pos !in items.indices || target !in items.indices) return
        val e = items.removeAt(pos)
        items.add(target, e)
        persist()
    }

    private fun showSongMenu(pos: Int) {
        val e = items.getOrNull(pos) ?: return
        MaterialAlertDialogBuilder(this)
            .setTitle("${pos + 1}. ${e.title}")
            .setItems(
                arrayOf(
                    getString(R.string.setlist_play_from_here),
                    getString(R.string.setlist_move_up),
                    getString(R.string.setlist_move_down),
                    getString(R.string.setlist_view_lyrics),
                    getString(R.string.setlist_remove),
                ),
            ) { _, which ->
                when (which) {
                    0 -> playFrom(pos)
                    1 -> move(pos, -1)
                    2 -> move(pos, +1)
                    3 -> {
                        playFrom(pos)
                        startActivity(Intent(this, LyricsActivity::class.java))
                    }
                    else -> removeAt(pos)
                }
            }
            .show()
    }

    // ---------------------------------------------------------------- Ordenar / quitar

    private inner class TouchCallback : ItemTouchHelper.SimpleCallback(
        ItemTouchHelper.UP or ItemTouchHelper.DOWN,
        ItemTouchHelper.LEFT or ItemTouchHelper.RIGHT,
    ) {
        // Arrastrar solo desde el asa ≡; mantener presionado abre el menú de la canción.
        override fun isLongPressDragEnabled() = false

        override fun onMove(rv: RecyclerView, from: RecyclerView.ViewHolder, to: RecyclerView.ViewHolder): Boolean {
            val a = from.bindingAdapterPosition
            val b = to.bindingAdapterPosition
            if (a < 0 || b < 0) return false
            val moved = items.removeAt(a)
            items.add(b, moved)
            adapter.notifyItemMoved(a, b)
            return true
        }

        override fun clearView(rv: RecyclerView, holder: RecyclerView.ViewHolder) {
            super.clearView(rv, holder)
            rv.post { persist() } // guarda el nuevo orden y renumera
        }

        override fun onSwiped(holder: RecyclerView.ViewHolder, direction: Int) {
            removeAt(holder.bindingAdapterPosition)
        }
    }

    private class SongAdapter(
        val onClick: (Int) -> Unit,
        val onRemove: (Int) -> Unit,
        val onMenu: (Int) -> Unit,
        val onStartDrag: (RecyclerView.ViewHolder) -> Unit,
    ) : RecyclerView.Adapter<SongAdapter.Holder>() {
        private var items: List<MediaEntry> = emptyList()
        private var playingUri: String? = null

        fun submit(list: List<MediaEntry>) {
            items = list
            notifyDataSetChanged()
        }

        fun setPlaying(uri: String?) {
            playingUri = uri
            notifyDataSetChanged()
        }

        override fun getItemCount() = items.size

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
            Holder(ItemSetlistSongBinding.inflate(LayoutInflater.from(parent.context), parent, false))

        @SuppressLint("ClickableViewAccessibility")
        override fun onBindViewHolder(holder: Holder, position: Int) {
            val e = items[position]
            val b = holder.b
            val playing = e.uri == playingUri
            b.number.text = (position + 1).toString()
            b.title.text = e.title
            b.subtitle.text = listOf(e.artist, MediaAdapter.formatDuration(e.durationMs), if (e.isVideo) "🎬" else "")
                .filter { it.isNotBlank() }.joinToString("  ·  ")
            b.artwork.background = Artwork.background(e.uri, 12 * b.root.resources.displayMetrics.density)
            b.artwork.text = if (playing) "▶" else Artwork.initial(e.title)
            b.root.isActivated = playing
            b.root.setOnClickListener {
                val pos = holder.bindingAdapterPosition
                if (pos != RecyclerView.NO_POSITION) onClick(pos)
            }
            b.root.setOnLongClickListener {
                val pos = holder.bindingAdapterPosition
                if (pos != RecyclerView.NO_POSITION) onMenu(pos)
                true
            }
            b.removeButton.setOnClickListener {
                val pos = holder.bindingAdapterPosition
                if (pos != RecyclerView.NO_POSITION) onRemove(pos)
            }
            b.dragHandle.setOnTouchListener { _, ev ->
                if (ev.actionMasked == MotionEvent.ACTION_DOWN) onStartDrag(holder)
                false
            }
        }

        class Holder(val b: ItemSetlistSongBinding) : RecyclerView.ViewHolder(b.root)
    }

    companion object {
        private const val EXTRA_ID = "repertorio"

        fun intent(context: Context, id: String) =
            Intent(context, SetlistActivity::class.java).putExtra(EXTRA_ID, id)
    }
}
