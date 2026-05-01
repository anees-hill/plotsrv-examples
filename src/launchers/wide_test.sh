plotsrv run smoke-tests.python_objs --config plotsrv.yml --host 0.0.0.0 --port 8101 \
  --watch src/smoke-tests/long_text.txt --watch-label text-head --watch-section static-files --watch-head --truncate 60000 \
  --watch src/smoke-tests/long_text.txt --watch-label text-tail --watch-section static-files --watch-tail \
  --watch README.md --watch-label md --watch-section static-files \
  --watch mock-files/small_image.jpg --watch-label jpg --watch-section static-files \
  --watch old_plotsrv.ini --watch-label ini --watch-section static-files \
  --watch pyproject.toml --watch-label toml --watch-section static-files \
  --watch plotsrv.yml --watch-label yml --watch-section static-files \
  --watch mock-files/yaml-1.yaml --watch-label yaml --watch-section static-files \
  --watch mock-files/json-1.json --watch-label json --watch-section static-files \
  --watch mock-files/html-simple-1.html --watch-label html-simple --watch-section static-files \
  --watch mock-files/html-complex-1.html --watch-label html-complex --watch-section static-files --no-truncate \
  --watch mock-files/6000_20.csv --watch-label csv-very-large --watch-section static-files \
  --watch mock-files/1000_20.csv --watch-label csv-large-head --watch-section static-files --watch-head \
  --watch mock-files/1000_20.csv --watch-label csv-large-tail --watch-section static-files --watch-tail \
  --watch mock-files/100_20.csv --watch-label csv-small --watch-section static-files

