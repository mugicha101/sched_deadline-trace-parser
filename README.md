# sched_deadline-trace-parser

## Description

This repository contains code for parsing trace data generated from sched_deadline-emit-traces. This guide provides instructions to compile and run the code from the `main` branch.

## Usage

### Prerequisites

Before you begin, ensure you have the following installed on your system:
- Babeltrace2 built from source with Python bindings (installation guide: https://babeltrace.org/docs/v2.0/python/bt2/installation.html)
- Python3

### Cloning the Repository

```
git clone https://github.com/mugicha101/sched_deadline-trace-parser.git
cd sched_deadline-trace-parser
```

### Running parse.py

Run `./parse.py` [flags] <trace_src>
Flags:
`-h --help`: Help
`-o --output`: Write output to specified directory (default `./output`)
`-r --render`: Enable rendering
`-v --verbose`: Verbose logs
Note: make sure your trace folder is not owned by root (or run with `sudo`)

### Output Format

The output directory will contain the following:
- For each taskset, `taskset_i_stats.txt` containing the execution times of certain scheduler functions
- `combined_taskset_stats.txt` which is a culmination of the individual taskset stats
- If rendering is enabled, for each taskset, `taskset_i.svg` showing a visualization of the traced taskset's execution

## Development

### Structure
`src/` contains the logic of the tool. The core components (split into files) are the following:
- `task_model.py`: represents the state of real-time tasks, jobs, and certain CPU attributes at a certain point in time.
- `task_tracker.py`: represents tasksets at a certain point in time.
- `trace_event_parsers.py`: maps trace events to their handlers.
- `visualizer.py`: renders the taskset execution timeline as an svg.

`parse.py` is the CLI tool.
