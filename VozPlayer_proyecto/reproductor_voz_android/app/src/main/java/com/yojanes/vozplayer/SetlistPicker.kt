package com.yojanes.vozplayer

import android.app.Activity
import android.widget.Toast
import com.google.android.material.dialog.MaterialAlertDialogBuilder

/** Diálogo "Agregar a repertorio" desde la lista principal (mantener presionada una canción). */
object SetlistPicker {

    fun show(activity: Activity, entry: MediaEntry) {
        val lists = SetlistStore.all(activity).sortedByDescending { it.created }
        val labels = lists.map { "🎤  " + it.name + "  (" + it.items.size + ")" } + activity.getString(R.string.setlist_new_with_plus)
        MaterialAlertDialogBuilder(activity)
            .setTitle(activity.getString(R.string.setlist_add_to, entry.title))
            .setItems(labels.toTypedArray()) { _, which ->
                if (which < lists.size) {
                    addAndTell(activity, lists[which], entry)
                } else {
                    SetlistsActivity.askName(activity, activity.getString(R.string.setlist_new), "") { name ->
                        addAndTell(activity, SetlistStore.create(activity, name), entry)
                    }
                }
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun addAndTell(activity: Activity, s: SetlistStore.Setlist, entry: MediaEntry) {
        val msg = if (SetlistStore.add(activity, s.id, entry)) {
            activity.getString(R.string.setlist_added_to, entry.title, s.name)
        } else {
            activity.getString(R.string.setlist_already, entry.title)
        }
        Toast.makeText(activity, msg, Toast.LENGTH_SHORT).show()
    }
}
