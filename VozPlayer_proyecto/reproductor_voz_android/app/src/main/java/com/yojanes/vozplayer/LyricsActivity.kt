package com.yojanes.vozplayer

import android.content.ComponentName
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.WindowManager
import android.widget.EditText
import android.widget.LinearLayout
import androidx.annotation.OptIn
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.common.util.concurrent.ListenableFuture
import com.yojanes.vozplayer.databinding.ActivityLyricsBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Panel de letras: grande, con avance automático si la letra está sincronizada. */
@OptIn(UnstableApi::class)
class LyricsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLyricsBinding
    private lateinit var repo: LyricsRepository
    private val adapter = LyricsAdapter { line -> controller?.seekTo(line.timeMs) }
    private val layoutManager by lazy { LinearLayoutManager(this) }

    private var controllerFuture: ListenableFuture<MediaController>? = null
    private val controller: MediaController?
        get() = controllerFuture?.takeIf { it.isDone }?.let { runCatching { it.get() }.getOrNull() }

    private var currentEntry: MediaEntry? = null
    private var synced: List<LyricLine> = emptyList()
    private var loadJob: Job? = null
    private val handler = Handler(Looper.getMainLooper())

    private val ticker = object : Runnable {
        override fun run() {
            val c = controller
            if (c != null && synced.isNotEmpty()) {
                val idx = LrcParser.currentIndex(synced, c.currentPosition)
                if (idx >= 0) {
                    adapter.setCurrent(idx)
                    val offset = binding.lyricsList.height / 3
                    if (layoutManager.findFirstVisibleItemPosition() != idx || offset > 0) {
                        layoutManager.scrollToPositionWithOffset(idx, offset)
                    }
                }
            }
            handler.postDelayed(this, 250)
        }
    }

    private val playerListener = object : Player.Listener {
        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) = loadForCurrent()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLyricsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        repo = LyricsRepository(this)

        val prefs = getSharedPreferences("letras_vista", MODE_PRIVATE)
        adapter.textSizeSp = prefs.getFloat("tamano", 26f)
        binding.lyricsList.layoutManager = layoutManager
        binding.lyricsList.adapter = adapter

        binding.smallerButton.setOnClickListener {
            adapter.textSizeSp = (adapter.textSizeSp - 2f).coerceAtLeast(14f)
            prefs.edit().putFloat("tamano", adapter.textSizeSp).apply()
        }
        binding.biggerButton.setOnClickListener {
            adapter.textSizeSp = (adapter.textSizeSp + 2f).coerceAtMost(48f)
            prefs.edit().putFloat("tamano", adapter.textSizeSp).apply()
        }
        binding.searchButton.setOnClickListener { showSearchDialog() }
        binding.closeButton.setOnClickListener { finish() }
        showMessage(getString(R.string.lyrics_waiting))
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
            loadForCurrent()
        }, ContextCompat.getMainExecutor(this))
        handler.post(ticker)
    }

    override fun onStop() {
        handler.removeCallbacks(ticker)
        controller?.removeListener(playerListener)
        binding.nowPlaying.player = null
        controllerFuture?.let { MediaController.releaseFuture(it) }
        controllerFuture = null
        super.onStop()
    }

    private fun entryForCurrent(): MediaEntry? {
        val c = controller ?: return null
        val item = c.currentMediaItem ?: return null
        return Library.find(item.mediaId) ?: MediaEntry(
            uri = item.mediaId,
            title = item.mediaMetadata.title?.toString().orEmpty(),
            artist = item.mediaMetadata.artist?.toString().orEmpty(),
            album = "",
            displayName = item.mediaMetadata.title?.toString().orEmpty(),
            durationMs = c.duration.coerceAtLeast(0),
            isVideo = false,
        )
    }

    private fun loadForCurrent() {
        val entry = entryForCurrent()
        currentEntry = entry
        if (entry == null) {
            binding.songTitle.text = getString(R.string.lyrics_title)
            binding.songInfo.text = ""
            showMessage(getString(R.string.lyrics_nothing_playing))
            return
        }
        binding.songTitle.text = entry.title
        binding.songInfo.text = entry.artist
        loadJob?.cancel()
        loadJob = lifecycleScope.launch {
            showMessage(getString(R.string.lyrics_loading))
            val local = withContext(Dispatchers.IO) { repo.loadLocal(entry) }
            if (local != null) return@launch show(local)
            if (!repo.hasInternet()) return@launch showMessage(getString(R.string.lyrics_none_offline))
            showMessage(getString(R.string.lyrics_searching))
            showOnline(withContext(Dispatchers.IO) { search(entry, entry.artist, entry.title) })
        }
    }

    private fun search(entry: MediaEntry, artist: String, title: String): LyricsRepository.OnlineResult =
        try {
            repo.searchOnline(entry, artist, title)
        } catch (e: Exception) {
            LyricsRepository.OnlineResult.NoConnection(e.javaClass.simpleName + ": " + e.message.orEmpty())
        }

    private fun showOnline(result: LyricsRepository.OnlineResult) {
        when (result) {
            is LyricsRepository.OnlineResult.Found -> show(result.lyrics)
            is LyricsRepository.OnlineResult.NotFound -> showMessage(
                getString(R.string.lyrics_not_found_detail, result.searched.joinToString("\n")),
            )
            is LyricsRepository.OnlineResult.NoConnection -> showMessage(
                getString(R.string.lyrics_connection_error, result.detail),
            )
        }
    }

    private fun show(lyrics: LyricsRepository.Lyrics) {
        val sourceText = when (lyrics.source) {
            LyricsRepository.Source.FILE -> getString(R.string.lyrics_source_file)
            LyricsRepository.Source.SAVED -> getString(R.string.lyrics_source_saved)
            LyricsRepository.Source.INTERNET -> getString(R.string.lyrics_source_internet)
        }
        val who = listOf(lyrics.artist, lyrics.title).filter { it.isNotBlank() }.joinToString(" – ")
        val warning = lyrics.otherVersionOf?.let { getString(R.string.lyrics_other_version, it, lyrics.artist) }
        binding.songInfo.text = listOfNotNull(
            warning,
            listOf(who, sourceText).filter { it.isNotBlank() }.joinToString("  ·  "),
        ).joinToString("\n")
        synced = lyrics.synced
        if (synced.isNotEmpty()) {
            adapter.submit(synced, isSynced = true)
        } else {
            adapter.submit(lyrics.plain.lines().map { LyricLine(0, it) }, isSynced = false)
            layoutManager.scrollToPosition(0)
        }
        binding.messageText.visibility = View.GONE
        binding.lyricsList.visibility = View.VISIBLE
    }

    private fun showMessage(text: String) {
        synced = emptyList()
        adapter.submit(emptyList(), false)
        binding.lyricsList.visibility = View.GONE
        binding.messageText.visibility = View.VISIBLE
        binding.messageText.text = text
    }

    /** Permite corregir artista y título cuando la búsqueda automática no acierta. */
    private fun showSearchDialog() {
        val entry = currentEntry ?: return
        val pad = (20 * resources.displayMetrics.density).toInt()
        val artistInput = EditText(this).apply {
            hint = getString(R.string.lyrics_artist_hint)
            setText(TrackNameParser.cleanForLyrics(entry.artist))
        }
        val titleInput = EditText(this).apply {
            hint = getString(R.string.lyrics_song_hint)
            setText(TrackNameParser.cleanForLyrics(entry.title))
        }
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad / 2, pad, 0)
            addView(titleInput)
            addView(artistInput)
        }
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.lyrics_search_title)
            .setMessage(R.string.lyrics_search_message)
            .setView(box)
            .setPositiveButton(R.string.lyrics_search_go) { _, _ ->
                if (!repo.hasInternet()) {
                    showMessage(getString(R.string.lyrics_no_internet))
                    return@setPositiveButton
                }
                loadJob?.cancel()
                loadJob = lifecycleScope.launch {
                    showMessage(getString(R.string.lyrics_searching))
                    showOnline(
                        withContext(Dispatchers.IO) {
                            search(entry, artistInput.text.toString(), titleInput.text.toString())
                        },
                    )
                }
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }
}
