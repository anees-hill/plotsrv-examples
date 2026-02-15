# CLI (manual) testing =====================================

# {plotsrv} launchers
#* Launch plotsrv server
plotsrv run src --host 127.0.0.1 --port 8000
plotsrv run resource-monitor --host 127.0.0.1 --port 8000
plotsrv run resource-monitor.main --host 127.0.0.1 --port 8000
plotsrv run resource-monitor.main:plot_mem_percent --host 127.0.0.1 --port 8000 # << expect fail at present due to argparse clash !

# * With [2 watch] commands for text files
plotsrv run src --host 127.0.0.1 --port 8000 \
  --watch pyproject.toml \
  --watch plotsrv.ini \
  --watch-every 10 \
  --watch-kind auto

# Artifact supplying modules
python -m resource-monitor.dev_validate3