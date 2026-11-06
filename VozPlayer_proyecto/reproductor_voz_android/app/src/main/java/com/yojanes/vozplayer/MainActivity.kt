package com.yojanes.vozplayer

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.speech.RecognizerIntent
import android.view.View
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.annotation.OptIn
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.widget.doAfterTextChanged
import androidx.lifecycle.lifecycleScope
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.common.util.concurrent.ListenableFuture
import com.yojanes.vozplayer.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

@OptIn(UnstableApi::class)
class MainActivity : AppCompatActivity() {

    private enum class TypeFilter { ALL, AUDIO, VIDEO }

    private lateinit var binding: ActivityMainBinding
    private val adapter = MediaAdapter { position -> playFromVisible(position) }

    private var allEntries: List<MediaEntry> = emptyList()
    private var visibleEntries: List<MediaEntry> = emptyList()
    private var typeFilter = TypeFilter.ALL

    private var controllerFuture: ListenableFuture<MediaController>? = null
    private val controller: MediaController?
        get() = controllerFuture?.takeIf { it.isDone }?.let { runCatching { it.get() }.getOrNull() }

    private lateinit var folders: FolderRepository
    private var loadJob: kotlinx.coroutines.Job? = null

    /** Selector de carpeta de pistas (Storage Access Framework). */
    private val folderPicker =
        registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
            if (uri == null) return@registerForActivityResult
            try {
                contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            } catch (_: SecurityException) {
                toast(getString(R.string.folder_not_allowed))
                return@registerForActivityResult
            }
            folders.add(uri)
            folders.active = FolderRepository.Folder(uri, FolderRepository.nameOf(uri))
            loadLibrary()
        }

    /** Archivo recibido con "Abrir con..." mientras el reproductor se conecta. */
    private var pendingExternalUri: Uri? = null

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
            if (hasMediaPermission()) loadLibrary() else showEmpty(getString(R.string.permission_needed))
        }

    private val speechLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == RESULT_OK) {
                val alternatives = result.data
                    ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                    .orEmpty()
                handleVoiceResults(alternatives)
            }
        }

    private val playerListener = object : Player.Listener {
        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
            adapter.setPlaying(mediaItem?.mediaId)
            updatePlayerMode()
        }

        override fun onTracksChanged(tracks: Tracks) = updatePlayerMode()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (showPreviousCrashIfAny()) return
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        folders = FolderRepository(this)
        binding.folderButton.setOnClickListener { showFolderDialog() }
        binding.lyricsButton.setOnClickListener { startActivity(Intent(this, LyricsActivity::class.java)) }
        binding.mixerButton.setOnClickListener { startActivity(Intent(this, MixerActivity::class.java)) }

        binding.list.layoutManager = LinearLayoutManager(this)
        binding.list.adapter = adapter

        binding.searchInput.doAfterTextChanged { applyFilter() }
        binding.micButton.setOnClickListener { startVoiceSearch() }
        binding.swipeRefresh.setOnRefreshListener {
            if (folders.active != null || hasMediaPermission()) loadLibrary() else requestMediaPermissions()
        }
        binding.typeChips.setOnCheckedStateChangeListener { _, checkedIds ->
            typeFilter = when (checkedIds.firstOrNull()) {
                R.id.chipAudio -> TypeFilter.AUDIO
                R.id.chipVideo -> TypeFilter.VIDEO
                else -> TypeFilter.ALL
            }
            applyFilter()
        }

        handleExternalIntent(intent)

        if (folders.active != null || hasMediaPermission()) loadLibrary() else requestMediaPermissions()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (showingCrash) return
        handleExternalIntent(intent)
    }

    /** true si se mostró el error del cierre anterior (en ese caso no se carga la pantalla normal). */
    private var showingCrash = false

    private fun showPreviousCrashIfAny(): Boolean {
        val file = VozPlayerApp.crashFile(application)
        if (!file.exists()) return false
        val report = runCatching { file.readText() }.getOrDefault("")
        file.delete()
        showingCrash = true
        val pad = (16 * resources.displayMetrics.density).toInt()
        val text = TextView(this).apply {
            setTextIsSelectable(true)
            setPadding(pad, pad, pad, pad)
            textSize = 12f
            this.text = getString(R.string.crash_report_header) + "\n\n" + report
        }
        setContentView(ScrollView(this).apply { addView(text) })
        return true
    }

    override fun onStart() {
        super.onStart()
        if (showingCrash) return
        val token = SessionToken(this, ComponentName(this, PlaybackService::class.java))
        val future = MediaController.Builder(this, token).buildAsync()
        controllerFuture = future
        future.addListener({
            val c = controller ?: return@addListener
            binding.playerView.player = c
            c.addListener(playerListener)
            adapter.setPlaying(c.currentMediaItem?.mediaId)
            updatePlayerMode()
            playExternalIfReady()
        }, ContextCompat.getMainExecutor(this))
    }

    override fun onStop() {
        if (showingCrash) return super.onStop()
        controller?.removeListener(playerListener)
        binding.playerView.player = null
        controllerFuture?.let { MediaController.releaseFuture(it) }
        controllerFuture = null
        super.onStop()
    }

    // ---------------------------------------------------------------- Permisos

    private fun mediaPermissions(): Array<String> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            arrayOf(
                Manifest.permission.READ_MEDIA_AUDIO,
                Manifest.permission.READ_MEDIA_VIDEO,
                Manifest.permission.POST_NOTIFICATIONS,
            )
        } else {
            arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE)
        }

    private fun isGranted(permission: String) =
        ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED

    private fun hasMediaPermission(): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            isGranted(Manifest.permission.READ_MEDIA_AUDIO) || isGranted(Manifest.permission.READ_MEDIA_VIDEO)
        } else {
            isGranted(Manifest.permission.READ_EXTERNAL_STORAGE)
        }

    private fun requestMediaPermissions() {
        binding.swipeRefresh.isRefreshing = false
        permissionLauncher.launch(mediaPermissions())
    }

    // ---------------------------------------------------------------- Biblioteca

    private fun loadLibrary() {
        val folder = folders.active
        binding.folderButton.text = folder?.name ?: getString(R.string.folder_whole_phone)
        binding.swipeRefresh.isRefreshing = true
        loadJob?.cancel()
        loadJob = lifecycleScope.launch {
            allEntries = withContext(Dispatchers.IO) {
                if (folder != null) {
                    runCatching { FolderScanner(contentResolver).scan(folder.uri) }.getOrDefault(emptyList())
                } else {
                    MediaRepository(contentResolver).loadAll()
                }
            }
            Library.entries = allEntries
            binding.swipeRefresh.isRefreshing = false
            applyFilter()
            if (folder != null && allEntries.isNotEmpty()) {
                // Completa duración y artista leyendo las etiquetas, sin bloquear la pantalla.
                val enriched = withContext(Dispatchers.IO) {
                    runCatching { MetadataEnricher(this@MainActivity).enrich(allEntries) }.getOrNull()
                }
                if (enriched != null && enriched != allEntries) {
                    allEntries = enriched
                    Library.entries = enriched
                    applyFilter()
                }
            }
        }
    }

    // ---------------------------------------------------------------- Carpetas

    private fun showFolderDialog() {
        val saved = folders.folders()
        val active = folders.active
        val labels = mutableListOf<String>()
        labels += (if (active == null) "✔ " else "") + getString(R.string.folder_whole_phone)
        saved.forEach { labels += (if (it.uri == active?.uri) "✔ " else "") + "📁 " + it.name }
        labels += getString(R.string.folder_add)
        labels += getString(R.string.folder_drive_help)
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.folder_dialog_title)
            .setItems(labels.toTypedArray()) { _, which ->
                when {
                    which == 0 -> {
                        folders.active = null
                        if (hasMediaPermission()) loadLibrary() else requestMediaPermissions()
                    }
                    which <= saved.size -> {
                        folders.active = saved[which - 1]
                        loadLibrary()
                    }
                    which == saved.size + 1 -> openFolderPicker()
                    else -> showDriveHelp()
                }
            }
            .apply {
                if (saved.isNotEmpty()) setNeutralButton(R.string.folder_remove) { _, _ -> showRemoveFolderDialog() }
            }
            .show()
    }

    private fun openFolderPicker() {
        try {
            folderPicker.launch(null)
        } catch (_: ActivityNotFoundException) {
            toast(getString(R.string.folder_picker_missing))
        }
    }

    private fun showRemoveFolderDialog() {
        val saved = folders.folders()
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.folder_remove)
            .setItems(saved.map { "📁 " + it.name }.toTypedArray()) { _, which ->
                folders.remove(saved[which].uri)
                if (folders.active == null && !hasMediaPermission()) requestMediaPermissions() else loadLibrary()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun showDriveHelp() {
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.drive_help_title)
            .setMessage(R.string.drive_help_message)
            .setPositiveButton(R.string.folder_add) { _, _ -> openFolderPicker() }
            .setNegativeButton(android.R.string.ok, null)
            .show()
    }

    private fun applyFilter() {
        val query = binding.searchInput.text?.toString().orEmpty()
        val base = when (typeFilter) {
            TypeFilter.ALL -> allEntries
            TypeFilter.AUDIO -> allEntries.filter { !it.isVideo }
            TypeFilter.VIDEO -> allEntries.filter { it.isVideo }
        }
        visibleEntries = if (query.isBlank()) base
        else VoiceSearchMatcher.rank(query, base).map { it.entry }

        adapter.submit(visibleEntries)
        binding.countText.text = resources.getQuantityString(
            R.plurals.files_count, visibleEntries.size, visibleEntries.size,
        )
        when {
            allEntries.isEmpty() && folders.active != null -> showEmpty(getString(R.string.no_media_in_folder))
            allEntries.isEmpty() && hasMediaPermission() -> showEmpty(getString(R.string.no_media))
            allEntries.isEmpty() -> showEmpty(getString(R.string.permission_needed))
            visibleEntries.isEmpty() -> showEmpty(getString(R.string.no_results, query))
            else -> binding.emptyText.visibility = View.GONE
        }
    }

    private fun showEmpty(message: String) {
        binding.emptyText.text = message
        binding.emptyText.visibility = View.VISIBLE
    }

    // ---------------------------------------------------------------- Voz

    private fun startVoiceSearch() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5)
            putExtra(RecognizerIntent.EXTRA_PROMPT, getString(R.string.voice_prompt))
        }
        try {
            speechLauncher.launch(intent)
        } catch (_: ActivityNotFoundException) {
            toast(getString(R.string.no_voice_engine))
        }
    }

    private fun handleVoiceResults(alternatives: List<String>) {
        if (alternatives.isEmpty()) return
        val candidates = visibleTypeEntries()
        val match = VoiceSearchMatcher.bestVoiceMatch(alternatives, candidates)
        val spoken = match?.spokenText ?: alternatives.first()

        // Muestra en la lista todo lo que se parece a lo que se dijo.
        binding.searchInput.setText(spoken)
        binding.searchInput.setSelection(spoken.length)

        if (match != null && match.best.score >= VoiceSearchMatcher.AUTO_PLAY_THRESHOLD) {
            val index = visibleEntries.indexOfFirst { it.uri == match.best.entry.uri }
            if (index >= 0) {
                playFromVisible(index)
                toast(getString(R.string.now_playing, match.best.entry.title))
            }
        } else if (visibleEntries.isNotEmpty()) {
            toast(getString(R.string.choose_result, visibleEntries.size))
        } else {
            toast(getString(R.string.no_results, spoken))
        }
    }

    private fun visibleTypeEntries(): List<MediaEntry> = when (typeFilter) {
        TypeFilter.ALL -> allEntries
        TypeFilter.AUDIO -> allEntries.filter { !it.isVideo }
        TypeFilter.VIDEO -> allEntries.filter { it.isVideo }
    }

    // ---------------------------------------------------------------- Reproducción

    private fun MediaEntry.toMediaItem(): MediaItem =
        MediaItem.Builder()
            .setMediaId(uri)
            .setUri(Uri.parse(uri))
            .setMediaMetadata(
                MediaMetadata.Builder()
                    .setTitle(title)
                    .setArtist(artist.ifBlank { null })
                    .setAlbumTitle(album.ifBlank { null })
                    .build(),
            )
            .build()

    /** Reproduce el elemento elegido y deja como cola el resto de la lista visible. */
    private fun playFromVisible(position: Int) {
        val c = controller ?: return toast(getString(R.string.player_connecting))
        c.setMediaItems(visibleEntries.map { it.toMediaItem() }, position, 0L)
        c.prepare()
        c.play()
        updatePlayerMode()
    }

    private fun handleExternalIntent(intent: Intent?) {
        if (intent?.action == Intent.ACTION_VIEW && intent.data != null) {
            pendingExternalUri = intent.data
            playExternalIfReady()
        }
    }

    private fun playExternalIfReady() {
        val c = controller ?: return
        val uri = pendingExternalUri ?: return
        pendingExternalUri = null
        c.setMediaItem(MediaItem.Builder().setMediaId(uri.toString()).setUri(uri).build())
        c.prepare()
        c.play()
        updatePlayerMode()
    }

    /** Pantalla grande para video; barra compacta de controles para audio. */
    private fun updatePlayerMode() {
        val c = controller
        val pv = binding.playerView
        if (c == null || c.mediaItemCount == 0) {
            pv.visibility = View.GONE
            return
        }
        pv.visibility = View.VISIBLE
        val isVideo = c.currentTracks.isTypeSupported(C.TRACK_TYPE_VIDEO)
        val heightDp = if (isVideo) 240 else 150
        val heightPx = (heightDp * resources.displayMetrics.density).toInt()
        if (pv.layoutParams.height != heightPx) {
            pv.layoutParams = pv.layoutParams.also { it.height = heightPx }
        }
        if (isVideo) {
            pv.setControllerShowTimeoutMs(3000)
            pv.setControllerHideOnTouch(true)
        } else {
            pv.setControllerShowTimeoutMs(0)
            pv.setControllerHideOnTouch(false)
            pv.showController()
        }
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }
}
