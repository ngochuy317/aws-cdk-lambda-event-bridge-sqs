#!/bin/bash

if test -f "main.py"; then
  echo "[INFO] Executing: main.py"
  python3 main.py --mode ${EXECUTION_MODE}

  ret=$?
  if [ $ret -ne 0 ]; then
    echo "[ERROR] Script failed!" && exit 1
  fi
else
  echo "[ERROR] File not found: main.py" && exit 1
fi

echo "[INFO] main.py executed successfully"
