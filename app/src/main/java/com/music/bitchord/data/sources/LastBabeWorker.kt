package com.music.bitchord.data.sources

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/** Runs LastBabeRefresher in the background so the addon URL stays fresh while the app is closed. */
class LastBabeWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {

    override suspend fun doWork(): Result =
        runCatching { LastBabeRefresher.refreshIfDue() }
            .fold(onSuccess = { Result.success() }, onFailure = { Result.retry() })

    companion object {
        private const val NAME = "lastbabe-refresh"

        fun schedule(context: Context) {
            val req = PeriodicWorkRequestBuilder<LastBabeWorker>(4, TimeUnit.HOURS)
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build(),
                )
                .build()
            WorkManager.getInstance(context)
                .enqueueUniquePeriodicWork(NAME, ExistingPeriodicWorkPolicy.KEEP, req)
        }
    }
}
