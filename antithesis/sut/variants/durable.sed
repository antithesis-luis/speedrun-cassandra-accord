s|^commitlog_sync: periodic|commitlog_sync: batch|
s|^commitlog_sync_period:|# commitlog_sync_period:|
s|^    # flush_mode left at the production default (PERIODIC), see tuning.md|    flush_mode: BATCH|
