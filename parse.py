# CLI tool for parsing LTTNG traces generated from experiments

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/src")

from trace_imports import *
from trace_event_parsers import parse_trace_event_message
from task_tracker import TaskTracker

def extract_trace(path) -> TraceIterator:
  return bt2.TraceCollectionMessageIterator(path)

def parse_trace(trace: TraceIterator):
  tracker = TaskTracker()

  for msg in trace:
    if type(msg) is TraceEventMessage:
      parse_trace_event_message(tracker, msg)

  if not tracker.is_complete:
    raise Exception("Last taskset never completed (likely missing tracepoints)")
  
  tracker.output()

def main():
  parse_args()
  trace = extract_trace(Args.path)
  if not os.path.isdir(Args.output_path):
    os.mkdir(Args.output_path)
  parse_trace(trace)

if __name__ == "__main__":
  main()