# One worker on purpose: running jobs and the per-service lock live in this process's memory, so a second worker (or a
# second App Service instance) would not see them. Threads give concurrency inside the single worker. Do not set WMTS_LOCAL here.
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "8000")
workers = 1
threads = 8
timeout = 120          # requests are short: adds run in background threads and are polled
accesslog = "-"
errorlog = "-"
