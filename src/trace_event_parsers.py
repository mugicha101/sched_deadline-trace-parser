# definitions of handlers for each event message type

from trace_imports import *
from task_tracker import *
from sched_class_funcs import *

import sys

# trace event name --> parser bookkeeping

parser_map: dict[str, Callable[[TaskTracker, TraceEventMessage], Any]] = {}

display_data = {
  "next_update": datetime.datetime(year=1960, month=1, day=1),
  "update_period": datetime.timedelta(seconds=0.1),
  "parsed_msgs": 0
}

def parse_trace_event_message(tracker: TaskTracker, msg: TraceEventMessage) -> Any:
  old_print_count = print_count["amount"]
  name = msg.event.name
  tracker.set_time(msg.default_clock_snapshot.ns_from_origin)
  ret = parser_map[name](tracker, msg.event) if name in parser_map else None
  display_data["parsed_msgs"] += 1
  now = datetime.datetime.now()

  # display progress bar
  if print_count["amount"] != old_print_count or now >= display_data["next_update"]:
    display_data["next_update"] = now + display_data["update_period"]
    parsed_msgs = display_data["parsed_msgs"]
    print(f"{parsed_msgs} [{time2str(tracker.time)}]", end="\r")
  return ret

def trace_event_parser(name):
  def decorator(func):
    parser_map[name] = func
    return func
  return decorator

# trace event parsers

@trace_event_parser("task_proc:taskset_init")
def taskset_init(tracker: TaskTracker, event: TraceEvent):
  tracker.new_taskset()

@trace_event_parser("task_proc:task_init")
def task_init(tracker: TaskTracker, event: TraceEvent):
  tracker.add_task(event["vtid"], TaskParams(event["period"], event["deadline"], event["wcet"]))

@trace_event_parser("task_proc:job_release")
def job_release(tracker: TaskTracker, event: TraceEvent):
  tracker.release(event["vtid"])

@trace_event_parser("task_proc:job_completion")
def job_completion(tracker: TaskTracker, event: TraceEvent):
  tracker.complete(event["vtid"])

@trace_event_parser("task_proc:kill_threads")
def job_completion(tracker: TaskTracker, event: TraceEvent):
  tracker.complete_taskset()

@trace_event_parser("task_proc:deadline_overrun")
def deadline_overrun(tracker: TaskTracker, event: TraceEvent):
  tracker.deadline_overrun(event["vtid"])

@trace_event_parser("sched_switch")
def sched_switch(tracker: TaskTracker, event: TraceEvent):
  tracker.switch(event["cpu_id"], event["prev_tid"], event["next_tid"])

# NOTE: NOT ACTUALLY THE SCHEDULER
# @trace_event_parser("x86_irq_vectors_reschedule_entry")
# def sched_entry(tracker: TaskTracker, event: TraceEvent):
#   tracker.resched_enter(event["cpu_id"])

# @trace_event_parser("x86_irq_vectors_reschedule_exit")
# def sched_entry(tracker: TaskTracker, event: TraceEvent):
#   tracker.resched_exit(event["cpu_id"])

@trace_event_parser("rcu_utilization")
def rcu_util(tracker: TaskTracker, event: TraceEvent):
  cpu_id = event["cpu_id"]
  match event["s"]:
    case "Start context switch":
      tracker.cswitch_start(cpu_id)
    case "End context switch":
      tracker.cswitch_end(cpu_id)

@trace_event_parser("sched_migrate_task")
def migrate(tracker: TaskTracker, event: TraceEvent):
  tracker.migrate(event["tid"], event["orig_cpu"], event["dest_cpu"])

# add trace handlers for scheduler functions
SCHED_CLASSES = [
  SCHED_DL_CLASS_FUNCS,
  # SCHED_EXT_CLASS_FUNCS
]

def gen_sfunc_handlers(name):
  @trace_event_parser(f"{name}_entry")
  def sfunc_entry(tracker: TaskTracker, event: TraceEvent):
    tracker.sfunc_entry(name, event["cpu_id"])
  @trace_event_parser(f"{name}_exit")
  def sfunc_exit(tracker: TaskTracker, event: TraceEvent):
    tracker.sfunc_exit(name, event["cpu_id"])
  return sfunc_entry, sfunc_exit

for sfunc in SFUNCS:
  gen_sfunc_handlers(sfunc)

# to figure out when a task is truly released,
# identify which hrtimer was called during its sched_yield
# the same hrtimer calling hrtimer_cancel should signify the release
# - may be cancelled from a different core
# from there it will be enqueued onto the dl_rq and possibly migrated
# release delay as defined in bjorn's diss is interval between the event triggering the release of a job and the first instruction executed by the job
# this is modeled by taking the time between timer_hrtimer_cancel and task_proc:job_release

@trace_event_parser("timer_hrtimer_cancel")
def hrtimer_cancel(tracker: TaskTracker, event: TraceEvent):
  tracker.hrtimer_cancel(event["hrtimer"])

@trace_event_parser("timer_hrtimer_start")
def hrtimer_start(tracker: TaskTracker, event: TraceEvent):
  tracker.hrtimer_start(event["cpu_id"], event["hrtimer"], event["mode"])

gen_sfunc_handlers("timer_hrtimer_expire")
gen_sfunc_handlers("replenish_dl_entity")
gen_sfunc_handlers("dl_task_timer")
