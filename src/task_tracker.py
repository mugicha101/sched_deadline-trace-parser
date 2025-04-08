# task tracking logic

from task_model import *
from sched_class_funcs import *
from visualizer import render
from pretty_time import time2str
from args import Args

# represents the execution state of a taskset at a specific point in time
class TaskTracker:
  def __init__(self):
    self.time = -1
    self.tasks: list[Task] = []
    self.id_map: dict[int, int] = {} # tid (thread id) -> task id
    self.completed_tasksets: list[CompletedTaskset] = []
    self.is_complete = True
    self.taskset_id = -1
    self.taskset_init_time = -1
    self.thread_cpu: dict[int, int] = {} # tid -> cpu
    self.cpus: dict[int, CPUState] = {} # cpu id -> cpu state
    self.yield_timers: dict[int, Task] = {} # hrtimer -> task
    self.unhandled_releases: dict[int, int] = {} # task id -> release time (based on hrtimer cancel) of releases yet to have associated job_release (used to track release delay)

  def set_time(self, time):
    if time < self.time:
      raise Exception(f"[{self.time}ns] Attempted to go back in time (new time: {time} < curr time: {self.time})")
    
    self.time = time

  def get_time(self) -> int:
    return self.time
  
  def get_thread_cpu_id(self, tid: int) -> int:
    return self.thread_cpu[tid] if tid in self.thread_cpu else -1
  
  def get_cpu(self, cpu_id: int) -> CPUState:
    if cpu_id not in self.cpus:
      self.cpus[cpu_id] = CPUState(cpu_id)
    
    return self.cpus[cpu_id]

  def new_taskset(self):
    if not self.is_complete:
      raise Exception(f"[{time2str(self.time)}] Cannot create new taskset when current one is not complete (current taskset: {self.taskset_id})")
    if len(self.yield_timers) > 0 or len(self.unhandled_releases) > 0:
      raise Exception(f"[{time2str(self.time)}] Cannot create new taskset when yield timers are not all handled (current taskset: {self.taskset_id}, yield_timers={self.yield_timers}, unhandled_releases={self.unhandled_releases})")
    
    self.taskset_id += 1
    self.tasks = []
    self.id_map = {}
    self.is_complete = False
    self.taskset_init_time = self.time

  def complete_taskset(self):
    if self.is_complete:
      raise Exception(f"[{time2str(self.time)}] No active taskset (last taskset: {self.taskset_id})")
    
    self.is_complete = True

    # abort any running tasks
    for task in self.tasks:
      task.abort(self.time, False)

    # filter the exec blocks for those generated for the tasks in the taskset
    # order by start time
    sfunc_blocks: list[SFuncBlock] = []
    cswitch_blocks: list[ExecBlock] = []
    for cpu in self.cpus.values():
      # add sfunc blocks
      for i in range(len(cpu.sfunc_blocks)-1, -1, -1):
        sfunc_block = cpu.sfunc_blocks[i]
        if sfunc_block.entry_time < self.taskset_init_time:
          break

        sfunc_blocks.append(sfunc_block)
      
      # add cswitch blocks
      for i in range(len(cpu.cswitch_blocks)-1, -1, -1):
        cswitch_block = cpu.cswitch_blocks[i]
        if cswitch_block.start_time < self.taskset_init_time:
          break

        cswitch_blocks.append(cswitch_block)

    sfunc_blocks.sort(key=lambda b : b.entry_time )
    cswitch_blocks.sort(key=lambda b : b.start_time )

    sfunc_map: dict[str, list[SFuncBlock]] = {}
    for sf in sfunc_blocks:
      if sf.name not in sfunc_map:
        sfunc_map[sf.name] = []
      sfunc_map[sf.name].append(sf)
    exec_data: dict[str, ExecData] = {}
    for name, blocks in sfunc_map.items():
      data = SFuncData(name, blocks)
      exec_data[data.name] = data
    jobs = [ job for task in self.tasks for job in task.completed_jobs ]
    exec_data["job:release_delay"] = ExecData("job:release_delay", [ job.release_delay for job in jobs if job.release_delay is not None ])
    exec_data["job:migrations"] = ExecData("job:migrations", [ job.migrations for job in jobs ])
    exec_data["job:preemptions"] = ExecData("job:preemptions", [ len(job.exec_blocks) - 1 for job in jobs ])
    ordered_data = list(exec_data.values())
    ordered_data.sort(key = lambda data : (data.name.split(":")[0], -data.count))
    if Args.verbose:
      print("EXEC STATS:")
      print("                   name               count                 min                mean              median                 max")
      for data in ordered_data:
        name = data.name.rjust(30, " ")
        def fmt(v: int | float):
          return "{:.3f}".format(v).rjust(20, " ")
        def ifmt(v: int):
          return str(v).rjust(20, " ")
        print(f" - {name}{ifmt(data.count)}{ifmt(data.min_runtime)}{fmt(data.mean_runtime)}{fmt(data.median_runtime)}{ifmt(data.max_runtime)}")

    taskset = CompletedTaskset(self.tasks, exec_data, cswitch_blocks, self.taskset_init_time, self.time)

    if Args.render:
      render(taskset, f"{Args.output_path}/taskset_{len(self.completed_tasksets)}.svg")

    self.completed_tasksets.append(taskset)

  def get_task(self, tid) -> Task | None:
    if self.is_complete:
      return None
    
    return self.tasks[self.id_map[tid]] if tid in self.id_map else None

  def add_task(self, tid: int, params: TaskParams):
    if self.is_complete:
      raise Exception(f"[{self.time}ns] No active taskset (last taskset: {self.taskset_id})")
    
    if tid in self.id_map:
      raise Exception(f"[{self.time}ns] Multiple tasks mapped to same thread (tid={tid}):\n    existing task: {self.get_task(tid).params}\n    incoming task: {params}")
    
    self.tasks.append(Task(len(self.tasks), params, self.time, self.get_thread_cpu_id(tid)))
    self.id_map[tid] = self.tasks[-1].task_id
    
    if Args.verbose: print(f"tid={tid} mapped to task {self.tasks[-1]}")

  def switch(self, cpu_id: int, prev_tid: int, next_tid: int):
    cpu = self.get_cpu(cpu_id)
    cpu.switch(next_tid, self.time)
    if cpu.prev_tid != prev_tid and cpu.prev_tid != -1:
      raise Exception(f"[{self.time}ns] CPU marked as running tid={cpu.prev_tid} but switch indicates should be running {prev_tid}")
    
    prev_task = self.get_task(prev_tid)
    if prev_task is not None:
      prev_task.preempt(self.time)
    if prev_tid in self.thread_cpu:
      del self.thread_cpu[prev_tid]

    next_task = self.get_task(next_tid)
    if next_task is not None:
      next_task.execute(self.time, cpu_id)
    self.thread_cpu[next_tid] = cpu_id

  def release(self, tid: int):
    task = self.get_task(tid)
    cpu_id = self.get_thread_cpu_id(tid)

    # find previous hrtimer cancel event mapped to this tasks hrtimer start (when it calls sched_yield)
    # ignore first release due to not having an associated release event
    release_time = None
    if task.job_id != -1:
      if task.task_id not in self.unhandled_releases:
        raise Exception(f"[{time2str(self.time)}]: Could not find task's release time (task={task}, job=J{task.job_id+1})")
      release_time = self.unhandled_releases[task.task_id]
      del self.unhandled_releases[task.task_id]

    task.release(release_time, self.time, cpu_id)

  def complete(self, tid):
    task = self.get_task(tid)
    task.complete(self.time)

  def deadline_overrun(self, tid: int):
    task = self.get_task(tid)
    task.abort(self.time, True)

  def sfunc_entry(self, name: str, cpu_id: int):
    cpu = self.get_cpu(cpu_id)
    cpu.sfunc_entry(name, self.time)

  def sfunc_exit(self, name: str, cpu_id: int):
    cpu = self.get_cpu(cpu_id)
    cpu.sfunc_exit(name, self.time)

  def cswitch_start(self, cpu_id: int):
    cpu = self.get_cpu(cpu_id)
    cpu.cswitch_start(self.time)

  def cswitch_end(self, cpu_id: int):
    cpu = self.get_cpu(cpu_id)
    cpu.cswitch_end(self.time)

  def migrate(self, tid: int, src_cpu_id: int, dst_cpu_id: int):
    task = self.get_task(tid)
    if task is None:
      return
    
    task.migrate(self.time, src_cpu_id, dst_cpu_id)

  def hrtimer_cancel(self, hrtimer: int):
    if hrtimer in self.yield_timers:
      task = self.yield_timers[hrtimer]
      del self.yield_timers[hrtimer]
      if task.task_id in self.unhandled_releases:
        raise Exception(f"[{time2str(self.time)}]: Multiple unhandled releases on a single task (hrtimer={hex(hrtimer)}, task={task})")
      self.unhandled_releases[task.task_id] = self.time

  def hrtimer_start(self, cpu_id: int, hrtimer: int):
    cpu = self.get_cpu(cpu_id)
    if len(cpu.sfunc_stack) > 0 and cpu.sfunc_stack[-1].name == "yield_task_dl":
      task = self.get_task(cpu.curr_tid)
      if task is None:
        raise Exception(f"[{time2str(self.time)}]: Could not find task mapped to sched_yield's htimer start (hrtimer={hex(hrtimer)}, tid={cpu.curr_tid})")
      self.yield_timers[hrtimer] = task