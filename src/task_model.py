# classes representing the task model

from enum import Enum
from args import Args
from pretty_time import time2str

import statistics

# implicit unit of time: nanoseconds

class TaskParams:
  def __init__(self, period, deadline, wcet):
    self.period = period
    self.deadline = deadline
    self.wcet = wcet

  def __str__(self):
    return f"(P={round(self.period, 2)}, C={round(self.wcet, 2)})" if self.deadline == self.period else f"(P={round(self.period, 2)}, C={round(self.wcet, 2)}), D={round(self.deadline, 2)})"

  def __repr__(self):
    return str(self)
  
# represents a block of execution time
class ExecBlock:
  def __init__(self, cpu_id: int, start_time: int, end_time: int):
    self.cpu_id = cpu_id
    self.start_time = start_time
    self.end_time = end_time

  def __str__(self):
    return f"cpu{self.cpu_id}:[{self.start_time}:{self.end_time}]"
  
  def __repr__(self):
    return str(self)

# represents a block of task execution time
class TaskExecBlock(ExecBlock):
  def __init__(self, task_id: int, job_id: int, cpu_id: int, start_time: int, end_time: int):
    super().__init__(cpu_id, start_time, end_time)

    self.task_id = task_id
    self.job_id = job_id
    self.cpu_id = cpu_id

# represents a single migration
class Migration:
  def __init__(self, time: int, src_cpu_id: int, dst_cpu_id: int):
    self.time = time
    self.src_cpu_id = src_cpu_id
    self.dst_cpu_id = dst_cpu_id

# represents a scheduler function invocation
# note: tied to a particular cpu (cannot migrate)
class SFuncBlock:
  def __init__(self, name: str, cpu_id: int, parent: "SFuncBlock", nesting: int, entry_time: int, exit_time: int):
    self.name = name
    self.cpu_id = cpu_id
    self.parent = parent
    self.nesting = nesting
    self.entry_time = entry_time
    self.exit_time = exit_time

# represents a completed (or aborted) job
class CompletedJob:
  class ExitStatus(Enum):
    SUCCESS = 0 # executed to completion
    ABORTED = 1 # killed by process due to experiment completion
    DEADLINE_OVERRUN = 2 # scheduler says it missed its deadline

  def __init__(self, task_id: int, job_id: int, release_time: int | None, userspace_release_time: int, absolute_deadline: int, completion_time: int, exit_status: ExitStatus, exec_blocks: list[TaskExecBlock] | None, migrations: int):
    self.task_id = task_id
    self.job_id = job_id
    self.release_time = release_time
    self.userspace_release_time = userspace_release_time
    self.absolute_deadline = absolute_deadline
    self.completion_time = completion_time
    self.exec_blocks = exec_blocks
    self.exit_status = exit_status
    self.migrations = migrations

    self.release_delay = None if release_time is None else userspace_release_time - release_time

# represents the execution state of a task at a specific point in time
# also records completed jobs
class Task:
  def __init__(self, task_id: int, params: TaskParams, init_time: int, cpu_id: int):
    self.init_time = init_time
    self.task_id = task_id
    self.params = params
    self.job_id = -1 # current job id (-1 if none released yet)
    self.cpu_id = cpu_id # cpu of current job (-1 if hasn't started executing yet)
    self.is_executing = False # currently executing on cpu?
    self.is_completed = True # current job completed or no job released?
    self.migrations: list[Migration] = [] # migrations across all jobs
    self.job_migrations = 0 # migrations associated to current job
    self.release_time = 0
    self.exec_start_time = 0
    self.exec_blocks: list[TaskExecBlock] | None = [] if Args.render else None
    self.completed_jobs: list[CompletedJob] = []
    self.absolute_deadline = 0
    if cpu_id != -1:
      self.execute(init_time, cpu_id)
    if Args.verbose: print(f"{self}: init")

  def __str__(self):
    return f"T{self.task_id}{self.params}"
  
  def __repr__(self):
    return str(self)

  # release time: hrtimer_cancel time
  # userspace_release_time: when task_proc's job_release tracepoint is emitted
  def release(self, release_time: int | None, userspace_release_time: int, cpu_id: int) -> None:
    if Args.verbose: print(f"{self}: release({release_time}, {userspace_release_time}, {cpu_id})")
    if not self.is_completed:
      raise Exception(f"[{userspace_release_time}ns]: Task {self.task_id} released new job before old job completed (old job id: {self.job_id})")
    
    self.job_id += 1
    self.is_executing = False
    self.cpu_id = -1
    self.is_completed = False
    self.release_time = release_time
    self.userspace_release_time = userspace_release_time
    self.absolute_deadline = (userspace_release_time if release_time is None else release_time) + self.params.deadline
    self.exec_start_time = 0
    self.job_migrations = 0
    if self.exec_blocks is not None:
      self.exec_blocks = []
    if cpu_id != -1:
      self.execute(userspace_release_time, cpu_id)

  def migrate(self, time: int, src_cpu_id: int, dst_cpu_id: int):
    if Args.verbose: print(f"{self}: migrate({time}, {src_cpu_id}, {dst_cpu_id})")
    if self.is_executing:
      raise Exception(f"[{time2str(time)}]: Task {self.task_id} cannot migrate while running (job id: {self.job_id})")
    if self.cpu_id not in [-1, src_cpu_id]:
      raise Exception(f"[{time2str(time)}]: Task {self.task_id} is not on the cpu it's migrating from (job id: {self.job_id})")
    
    self.migrations.append(Migration(time, src_cpu_id, dst_cpu_id))
    self.job_migrations += 1
    self.cpu_id = dst_cpu_id

  def execute(self, time: int, cpu_id: int) -> None:
    if Args.verbose: print(f"{self}: execute({time}, {cpu_id})")
    if self.is_executing:
      raise Exception(f"[{time2str(time)}]: Task {self.task_id} is already running (job id: {self.job_id})")
    if self.cpu_id not in [-1, cpu_id]:
      raise Exception(f"[{time2str(time)}]: Task {self.task_id} on cpu{self.cpu_id} cannot execute on cpu{cpu_id} (job id: {self.job_id})")

    self.last_cpu_id = cpu_id
    self.is_executing = True
    self.exec_start_time = time

  def preempt(self, time: int) -> None:
    if Args.verbose: print(f"{self}: preempt({time})")
    if not self.is_executing:
      raise Exception(f"[{time2str(time)}]: Task {self.task_id} is already preempted (job id: {self.job_id})")
    
    self.is_executing = False
    if self.exec_blocks is not None: self.exec_blocks.append(TaskExecBlock(self.task_id, self.job_id, self.last_cpu_id, self.exec_start_time, time))

  def complete(self, time: int) -> None:
    if Args.verbose: print(f"{self}: complete({time})")
    if self.job_id == -1:
      raise Exception(f"[{time2str(time)}]: Task {self.task_id} has not released any jobs")
    if self.is_completed:
      raise Exception(f"[{time2str(time)}]: Task {self.task_id} is already finished (job id: {self.job_id})")
    if self.last_cpu_id == -1:
      raise Exception(f"[{time2str(time)}]: Task {self.task_id} cannot complete without executing (job id: {self.job_id})")

    self.is_completed = True
    self.completed_jobs.append(CompletedJob(
      self.task_id, self.job_id,
      self.release_time, self.userspace_release_time, self.absolute_deadline, time,
      CompletedJob.ExitStatus.SUCCESS,
      self.exec_blocks,
      self.job_migrations
    ))

  def abort(self, time: int, is_deadline_overrun: bool) -> None:
    if Args.verbose: print(f"{self}: abort({time}, {is_deadline_overrun})")
    if self.is_completed:
      return
    
    if self.is_executing:
      self.preempt(time)
    
    self.completed_jobs.append(CompletedJob(
      self.task_id, self.job_id,
      self.release_time, self.userspace_release_time, self.absolute_deadline, time,
      CompletedJob.ExitStatus.DEADLINE_OVERRUN if is_deadline_overrun else CompletedJob.ExitStatus.ABORTED,
      self.exec_blocks,
      self.job_migrations
    ))
    self.is_executing = False
    self.is_completed = True

# represents the state of a CPU core
# note: enforces that the current task will not switch while the scheduler is running
class CPUState:
  def __init__(self, cpu_id: int):
    # note: tid=0 is the swapper task (idle), tid=-1 means no idea (before tracing started)
    self.cpu_id = cpu_id
    self.curr_tid = -1 # current running task
    self.prev_tid = -1 # last running task
    self.active_cswitch_block = None
    self.cswitch_blocks: list[ExecBlock] = [] # completed cswitch blocks
    self.sfunc_stack: list[SFuncBlock] = [] # scheduler function stack
    self.sfunc_blocks: list[SFuncBlock] = [] # completed function blocks
  
  def switch(self, tid: int, time: int):
    self.prev_tid, self.curr_tid = self.curr_tid, tid
    self.last_switch_time = time

  def cswitch_start(self, time: int):
    # if Args.verbose: print(f"{self}: cswitch_start({time})")
    if self.active_cswitch_block is not None:
      raise Exception("CPU already context switching")
    
    self.active_cswitch_block = ExecBlock(self.cpu_id, time, -1)
  
  def cswitch_end(self, time: int):
    # if Args.verbose: print(f"{self}: cswitch_end({time})")
    cswitch_block = self.active_cswitch_block
    if cswitch_block is None:
      return # switch_start happened before tracing started
    
    self.active_cswitch_block = None
    cswitch_block.end_time = time
    self.cswitch_blocks.append(cswitch_block)

  def sfunc_entry(self, name: str, time: int):
    # if Args.verbose: print(f"{self}: sfunc_entry({name}, {time})")
    parent = None if len(self.sfunc_stack) == 0 else self.sfunc_stack[-1]
    self.sfunc_stack.append(SFuncBlock(name, self.cpu_id, parent, len(self.sfunc_stack), time, -1))
  
  def sfunc_exit(self, name: str, time: int):
    # if Args.verbose: print(f"{self}: sfunc_exit({name}, {time})")
    if len(self.sfunc_stack) == 0 or self.sfunc_stack[-1].name != name:
      stack_dump = ", ".join(sfunc.name for sfunc in self.sfunc_stack)
      raise Exception(f"CPU sched func stack mismatch: stack is [{stack_dump}] but {name} exited")
    
    sfunc_block = self.sfunc_stack.pop()
    sfunc_block.exit_time = time
    self.sfunc_blocks.append(sfunc_block)

  def __str__(self):
    return f"CPU{self.cpu_id}"
  
# represents the execution time info of a certain type of execution
class ExecData:
  def __init__(self, name: str, durations: list[int]):
    self.name = name
    self.durations = durations
    self.count = len(durations)
    self.mean_runtime = statistics.mean(durations) if len(durations) > 0 else -1
    self.median_runtime = statistics.median(durations) if len(durations) > 0 else -1
    self.max_runtime = max(durations) if len(durations) > 0 else -1
    self.min_runtime = min(durations) if len(durations) > 0 else -1
  
# represents the info of a certain sfunc
class SFuncData(ExecData):
  def __init__(self, name: str, blocks: list[SFuncBlock]):
    self.blocks = blocks
    durations = [ b.exit_time - b.entry_time for b in blocks ]
    super().__init__(f"sfunc:{name}", durations)

# represents a completed taskset
class CompletedTaskset:
  def __init__(self, tasks: list[Task], exec_data: dict[str, ExecData], cswitch_blocks: list[ExecBlock], init_time: int, completion_time: int):
    self.tasks = tasks
    self.sfunc_blocks = [ sfunc_block for data in exec_data.values() if isinstance(data, SFuncData) for sfunc_block in data.blocks ]
    self.sfunc_blocks.sort(key = lambda sfunc_block : sfunc_block.entry_time)
    self.cswitch_blocks = cswitch_blocks
    self.jobs: list[CompletedJob] = [ job for task in tasks for job in task.completed_jobs ]
    self.jobs.sort(key = lambda job : job.userspace_release_time)
    self.init_time = init_time
    self.completion_time = completion_time
    self.cpu_ids = list(set([ sfunc_block.cpu_id for sfunc_block in self.sfunc_blocks ] + [ exec_block.cpu_id for task in tasks for job in task.completed_jobs if job.exec_blocks is not None for exec_block in job.exec_blocks ]))
  