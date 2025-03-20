# definitions of handlers for each event message type

from trace_imports import *
from task_tracker import *

# trace event name --> parser bookkeeping

parser_map: dict[str, Callable[[TaskTracker, TraceEventMessage], Any]] = {}

def parse_trace_event_message(tracker: TaskTracker, msg: TraceEventMessage) -> Any:
  name = msg.event.name
  tracker.set_time(msg.default_clock_snapshot.ns_from_origin)
  return parser_map[name](tracker, msg.event) if name in parser_map else None

def trace_event_parser(namespace: str, name: str):
  def decorator(func):
    parser_map[f"{namespace}:{name}"] = func
    return func
  return decorator

# trace event parsers

@trace_event_parser("task_proc", "taskset_init")
def taskset_init(tracker: TaskTracker, event: TraceEvent):
  tracker.new_taskset()

@trace_event_parser("task_proc", "task_init")
def task_init(tracker: TaskTracker, event: TraceEvent):
  tracker.add_task(event["vpid"], event["vtid"], TaskParams(event["period"], event["deadline"], event["wcet"]))

@trace_event_parser("task_proc", "job_release")
def job_release(tracker: TaskTracker, event: TraceEvent):
  task = tracker.get_task(event["vpid"], event["vtid"])
  task.release(tracker.get_time())

@trace_event_parser("ros2", "callback_start")
def debug(tracker: TaskTracker, event: TraceEvent):
  print(time2str(tracker.get_time()), flush=False)