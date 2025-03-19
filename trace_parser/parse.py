# CLI tool for parsing LTTNG traces generated from experiments

import os
from trace_imports import *
from trace_event_parsers import parse_trace_event_message
from task_tracker import TaskTracker

def dir_path(string) -> str:

  if os.path.isdir(string):
    return string
  else:
    raise NotADirectoryError(string)

def extract_trace(path) -> TraceIterator:
  return bt2.TraceCollectionMessageIterator(path)

def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Extract data from experiments lttng trace data")
  parser.add_argument("path", help="Path to LTTNG trace data", type=dir_path)
  parser.add_argument("-r", "--render", help="Render visualization of job executions", action=argparse.BooleanOptionalAction)
  return parser.parse_args()

def parse_trace(trace: TraceIterator, do_render: bool):
  tracker = TaskTracker(do_render=do_render)

  for msg in trace:
    if type(msg) is TraceEventMessage:
      parse_trace_event_message(tracker, msg)

  if not tracker.is_complete:
    raise Exception("Last taskset never completed (likely missing tracepoints)")

def main():
  args = parse_args()
  trace = extract_trace(args.path)
  parse_trace(trace, args.render)

if __name__ == "__main__":
  main()