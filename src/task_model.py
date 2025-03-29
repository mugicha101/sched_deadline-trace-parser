# classes representing the task model

from enum import Enum
from args import Args

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
  def __init__(self, task_id: int, job_id: int, cpu_id: int, start_time: int, end_time: int):
    self.task_id = task_id
    self.job_id = job_id
    self.cpu_id = cpu_id
    self.start_time = start_time
    self.end_time = end_time

  def __str__(self):
    return f"([<{self.task_id}:{self.job_id}> cpu{self.cpu_id}:[{self.start_time}:{self.end_time}])"
  def __repr__(self):
    return str(self)

# represents a completed (or aborted) job
class CompletedJob:
  class ExitStatus(Enum):
    SUCCESS = 0 # executed to completion
    ABORTED = 1 # killed by process due to experiment completion
    DEADLINE_OVERRUN = 2 # scheduler says it missed its deadline

  def __init__(self, task_id: int, job_id: int, release_time: int, absolute_deadline: int, completion_time: int, exit_status: ExitStatus, exec_blocks: list[ExecBlock] | None):
    self.task_id = task_id
    self.job_id = job_id
    self.release_time = release_time
    self.absolute_deadline = absolute_deadline
    self.completion_time = completion_time
    self.exec_blocks = exec_blocks
    self.exit_status = exit_status

# represents the execution state of a task at a specific point in time
# also records completed jobs
class Task:
  def __init__(self, task_id: int, params: TaskParams, init_time: int, cpu_id: int):
    self.init_time = init_time
    self.task_id = task_id
    self.params = params
    self.job_id = -1 # current job id (-1 if none released yet)
    self.last_cpu_id = -1 # last cpu of current job (-1 if hasn't started executing yet)
    self.is_executing = False # currently executing on cpu?
    self.is_completed = True # current job completed or no job released?
    self.migrations = 0
    self.release_time = 0
    self.exec_start_time = 0
    self.exec_blocks: list[ExecBlock] | None = [] if Args.render else None
    self.completed_jobs: list[CompletedJob] = []
    if cpu_id != -1:
      self.execute(init_time, cpu_id)
    if Args.verbose: print(f"{self}: init")

  def __str__(self):
    return f"T{self.task_id}{self.params}"
  
  def __repr__(self):
    return str(self)

  def release(self, time: int, cpu_id: int) -> None:
    if Args.verbose: print(f"{self}: release({time})")
    if not self.is_completed:
      raise Exception(f"[{time}ns]: Task {self.task_id} released new job before old job completed (old job id: {self.job_id})")
    
    self.job_id += 1
    self.is_executing = False
    self.last_cpu_id = -1
    self.is_completed = False
    self.release_time = time
    self.exec_start_time = 0
    if self.exec_blocks is not None:
      self.exec_blocks = []
    if cpu_id != -1:
      self.execute(time, cpu_id)

  def execute(self, time: int, cpu_id: int) -> None:
    if Args.verbose: print(f"{self}: execute({time}, {cpu_id})")
    if self.is_executing:
      raise Exception(f"[{time}ns]: Task {self.task_id} is already running (job id: {self.job_id})")
    
    if self.last_cpu_id not in [-1, cpu_id]:
      self.migrations += 1

    self.last_cpu_id = cpu_id
    self.is_executing = True
    self.exec_start_time = time

  def preempt(self, time: int) -> None:
    if Args.verbose: print(f"{self}: preempt({time})")
    if not self.is_executing:
      raise Exception(f"[{time}ns]: Task {self.task_id} is already preempted (job id: {self.job_id})")
    
    self.is_executing = False
    if self.exec_blocks is not None: self.exec_blocks.append(ExecBlock(self.task_id, self.job_id, self.last_cpu_id, self.exec_start_time, time))

  def complete(self, time: int) -> None:
    if Args.verbose: print(f"{self}: complete({time})")
    if self.job_id == -1:
      raise Exception(f"[{time}ns]: Task {self.task_id} has not released any jobs")
    if self.is_completed:
      raise Exception(f"[{time}ns]: Task {self.task_id} is already finished (job id: {self.job_id})")
    if self.last_cpu_id == -1:
      raise Exception(f"[{time}ns]: Task {self.task_id} cannot complete without executing (job id: {self.job_id})")

    self.is_completed = True
    self.completed_jobs.append(CompletedJob(
      self.task_id, self.job_id,
      self.release_time, self.release_time + self.params.deadline, time,
      CompletedJob.ExitStatus.SUCCESS,
      self.exec_blocks
    ))

  def abort(self, time: int, is_deadline_overrun: bool) -> None:
    if Args.verbose: print(f"{self}: abort({time}, {is_deadline_overrun})")
    if self.is_completed:
      return
    
    if self.is_executing:
      self.preempt(time)
    
    self.completed_jobs.append(CompletedJob(
      self.task_id, self.job_id,
      self.release_time, self.release_time + self.params.deadline, time,
      CompletedJob.ExitStatus.DEADLINE_OVERRUN if is_deadline_overrun else CompletedJob.ExitStatus.ABORTED,
      self.exec_blocks
    ))
    self.is_executing = False
    self.is_completed = True

# represents a scheduler invocation
class SchedBlock:
  def __init__(self, cpu_id: int, prev_tid: int, next_tid: int, start_time: int, end_time: int):
    self.cpu_id = cpu_id
    self.prev_tid = prev_tid
    self.next_tid = next_tid
    self.start_time = start_time
    self.end_time = end_time

    # variables set later when considering taskset data
    self.prev_task_id = -1
    self.next_task_id = -1

# represents the state of a CPU core
# note: enforces that the current task will not switch while the scheduler is running
class CPUState:
  def __init__(self, cpu_id: int):
    # note: tid=0 is the swapper task (idle), tid=-1 means no idea (before tracing started)
    self.cpu_id = cpu_id
    self.curr_tid = -1 # current running task
    self.prev_tid = -1 # last running task
    self.active_sched_block: SchedBlock | None = None # keeps track of current scheduler invocation (None if none active)
    self.sched_blocks: list[SchedBlock] = [] # completed sched blocks
  
  def switch(self, tid: int, time: int):
    if self.active_sched_block is not None:
      raise Exception("CPU cannot switch tasks while scheduler is running")

    self.prev_tid, self.curr_tid = self.curr_tid, tid
    self.last_switch_time = time

    # update last sched block with the next task
    if len(self.sched_blocks) > 0:
      sched_block = self.sched_blocks[-1]
      if sched_block.next_tid == -1:
        sched_block.next_tid = tid

  def resched_enter(self, time: int):
    if self.active_sched_block is not None:
      raise Exception("CPU already in scheduler")
    
    # update last sched block with the current task if no switch had occured
    if len(self.sched_blocks) > 0:
      sched_block = self.sched_blocks[-1]
      if sched_block.next_tid == -1:
        sched_block.next_tid = self.curr_tid
    
    self.active_sched_block = SchedBlock(self.cpu_id, self.curr_tid, -1, time, -1)

  def resched_exit(self, time: int):
    sched_block = self.active_sched_block
    self.active_sched_block = None
    sched_block.end_time = time
    self.sched_blocks.append(sched_block)

# represents a completed taskset
class CompletedTaskset:
  def __init__(self, tasks: list[Task], sched_blocks: list[SchedBlock], init_time: int, completion_time: int):
    self.tasks = tasks
    self.sched_blocks = sched_blocks
    self.jobs: list[CompletedJob] = [ job for task in tasks for job in task.completed_jobs ]
    self.jobs.sort(key = lambda job : job.release_time)
    self.init_time = init_time
    self.completion_time = completion_time
    self.cpu_ids = list(set([ sched_block.cpu_id for sched_block in sched_blocks ] + [ exec_block.cpu_id for task in tasks for job in task.completed_jobs if job.exec_blocks is not None for exec_block in job.exec_blocks ]))
  