# CLI (manual) testing =====================================

#! Reinstall 
uv sync --refresh && uv pip install -e .

# {plotsrv} launchers
#* Launch plotsrv server
#* PASSIVE
plotsrv run --host 127.0.0.1 --port 8000
plotsrv run src --host 127.0.0.1 --port 8000
plotsrv run resource-monitor --host 127.0.0.1 --port 8000
plotsrv run resource-monitor.main_infer_decorators --host 127.0.0.1 --port 8000
plotsrv run resource-monitor.main_infer_decorators:plot_mem_percent --host 127.0.0.1 --port 8000 # << expect fail at present due to argparse clash !

#* CALLABLE
plotsrv run src --mode callable --host 127.0.0.1 --port 8000
plotsrv run resource-monitor --host 127.0.0.1 --port 8000
plotsrv run resource-monitor.main_infer_decorators --mode callable --host 127.0.0.1 --port 8000
plotsrv run smoke-tests.python_objs --mode callable --call-every 60 --host 127.0.0.1 --port 8000
plotsrv run resource-monitor.main_infer_decorators:plot_mem_percent --host 127.0.0.1 --port 8000

#* Non-decorators
plotsrv run resource-monitor.main_infer_non-decorators --host 127.0.0.1 --port 8000

#* Python obj only
plotsrv run smoke-tests.python_objs --host 127.0.0.1 --port 8000

# name: smoke
plotsrv run smoke-tests.python_objs --config plotsrv.yml  \
  --watch src/smoke-tests/long_text.txt --watch-label text-head --watch-section static-files --watch-head --truncate 60000 \
  --watch src/smoke-tests/long_text.txt --watch-label text-tail --watch-section static-files --watch-tail \
  --watch README.md --watch-label md --watch-section static-files \
  --watch mock-files/jpeg-small-1.jpeg --watch-label jpeg --watch-section static-files \
  --watch old_plotsrv.ini --watch-label ini --watch-section static-files \
  --watch pyproject.toml --watch-label toml --watch-section static-files \
  --watch plotsrv.yml --watch-label yml --watch-section static-files \
  --watch mock-files/yaml1.yaml --watch-label yaml --watch-section static-files \
  --watch mock-files/json-1.json --watch-label json --watch-section static-files \
  --watch mock-files/html-simple-1.html --watch-label html-simple --watch-section static-files \
  --watch mock-files/html-complex-1.html --watch-label html-complex --watch-section static-files --no-truncate \
  --watch mock-files/ --watch-label csv-very-large --watch-section static-files \
  --watch mock-files/ --watch-label csv-large-head --watch-section static-files --watch-head \
  --watch mock-files/ --watch-label csv-large-tail --watch-section static-files --watch-tail \
  --watch mock-files/ --watch-label csv-small --watch-section static-files

# name: limited smoke
plotsrv run smoke-tests.python_objs --name smoke2 --host 127.0.0.1 --port 8000 \
  --watch src/smoke-tests/long_text.txt --watch-label text-head --watch-section static-files --watch-head --no-truncate

#* Exceptions
plotsrv run smoke-tests.tracebacks --host 127.0.0.1 --port 8000

#* Watch only
plotsrv watch pyproject.toml --every 10 --kind auto --host 127.0.0.1 --port 8000
plotsrv watch src/smoke-tests/long_text.txt --every 10 --kind auto --host 127.0.0.1 --port 8000

# * With [2 watch] commands for text files
plotsrv run src --host 127.0.0.1 --port 8000 \
  --watch pyproject.toml --watch-label toml --watch-section static-files \
  --watch plotsrv.ini --watch-label ini  --watch-section static-files \
  --watch-every 10 \
  --watch-kind auto

#* Store commands
plotsrv store stats
plotsrv store list
plotsrv store list --view seaborn:CPU%
plotsrv store clear --all

# Artifact supplying modules ----------------------------------

# Tables and plots
#* Use @plotsrv decorators or publish_artifact fns
python -m resource-monitor.main_infer_decorators
python -m resource-monitor.main_infer_non-decorators

#* Use @plot and @table decorators or plot_launch() and publish_view() fns
python -m resource-monitor.main_explicit_decorators
python -m resource-monitor.main_explicit_non-decorators

# Python objs
python -m smoke-tests.python_objs

# Exceptions
python -m smoke-tests.tracebacks
