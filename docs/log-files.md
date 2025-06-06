# Log Files Generated by `Jupyter-LC_wrapper`

The `lc_wrapper` acts as a kernel between the Python or Bash kernel and the Notebook server. It logs the results of cell executions. This document outlines the directory structure, types of files, and the formats and contents of log files generated under the `.log` directory.

---

## Directory Structure

Log files are stored in the following structure:

```
<notebook_path>/.log/
├── YYYYMMDD/
│   ├── YYYYMMDD-HHMMSS-mmmm.log          ← Execution log file
│   ├── YYYYMMDD-HHMMSS-mmmm-0.pkl        ← Output result (display/result/etc.)
│   ├── ...-1.pkl                         ← Additional results as needed
│
└── <cell-uuid>/
    ├── <cell-uuid>.json                  ← Cell execution history
    ├── YYYYMMDD-HHMMSS-mmmm.log          ← Symlink to the log file
```

* `<notebook_path>` is the directory where the notebook is located.
* The `.log` output destination defaults to either the notebook’s directory or `~/.log`, depending on which is writable.
* `<cell-uuid>` is the cell MEME generated by Jupyter-LC_nblineage.

---

## File Types and Contents

### 1. Execution Log (`YYYYMMDD-HHMMSS-mmm.log`)

* **Filename format**: Date (YYYYMMDD) + Time (HHMMSS-milliseconds)
* **Contents**:

  * The executed cell code
  * Metadata (e.g., notebook path, UID/GID, execution timestamps)
  * Text output (stdout/stderr)
  * Highlighted lines matching specified keywords
  * Execution status (`ok`, `error`, etc.)

#### Example:

```
path: /path/to/.log/20250520/20250520-142300-0123.log
notebook_path: /path/to/notebook
uid: 1000
gid: 1000
start time: 2025-05-20 14:23:00(JST)
----
print("Hello")
----
Hello
----
end time: 2025-05-20 14:23:01(JST)
output size: 123 bytes
0 chunks with matched keywords or errors
```

---

### 2. Output Result Files (`*.pkl`)

* **Contents**: Serialized Python objects using `pickle`, representing:

  * `display_data`
  * `execute_result`
  * `error`

* **Usage**: Stored for replaying output objects or error information

---

### 3. Cell Execution History (`<cell-uuid>.json`)

* **Location**: `.log/<cell-uuid>/<cell-uuid>.json`
* **Format**: JSON array containing records of past executions of the same cell

```json
[
  {
    "code": "print(\"Hello\")",
    "path": "/path/to/.log/20250520/20250520-142300-123.log",
    "start": "2025-05-20 14:23:00(JST)",
    "end": "2025-05-20 14:23:01(JST)",
    "size": 123,
    "server_signature": "...",
    "uid": 1000,
    "gid": 1000,
    "notebook_path": "/path/to/notebook",
    "lc_notebook_meme": "...",
    "execute_reply_status": "ok"
  }
]
```

* Multiple entries will be stored if the same cell is executed repeatedly.

---

### 4. Symlink

* A symbolic link to the corresponding `.log` file is created under the cell's UUID directory.
* Allows easy navigation between cell and log data.

---

## Keyword Highlighting

* Keywords for highlighting error or warning lines are defined in `.lc_wrapper_regex.txt`.
* These extract and emphasize critical lines in the output (e.g., error messages).

---

## Summary Table

| File Type     | Description                           | Example Path                  |
| ------------- | ------------------------------------- | ----------------------------- |
| `.log`        | Execution logs (code + output)        | `.log/YYYYMMDD/*.log`         |
| `.pkl`        | Output objects (`display_data`, etc.) | `.log/YYYYMMDD/*.pkl`         |
| `<uuid>.json` | Execution history of individual cells | `.log/<uuid>/<uuid>.json`     |
| Symlink       | Link to associated `.log` file        | `.log/<uuid>/YYYYMMDD-...log` |

This design allows you to trace and analyze notebook execution history and output per cell.
