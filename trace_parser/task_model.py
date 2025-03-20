# classes representing the task model

from enum import Enum

# implicit unit of time: nanoseconds

class TaskParams:
  def __init__(self, period, deadline, wcet):
    self.period = period
    self.deadline = deadline
    self.wcet = wcet

  def __str__(self):
    return f"(P={self.period}, D={self.deadline}, C={self.wcet})"

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
  def __init__(self, task_id: int, params: TaskParams, init_time: int, do_render = False):
    self.init_time = init_time
    self.task_id = task_id
    self.params = params
    self.job_id = -1 # current job id (-1 if none released yet)
    self.last_cpu_id = -1 # last cpu of current job (-1 if hasn't started executing yet)
    self.is_executing = False # currently executing on cpu?
    self.is_completed = True # current job completed or no job released?
    self.migrations = 0
    self.release_time = 0
    self.exec_blocks: list[ExecBlock] | None = [] if do_render else None
    self.completed_jobs: list[CompletedJob] = []

  def release(self, time: int) -> None:
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

  def execute(self, time: int, cpu_id: int) -> None:
    if self.job_id == -1:
      raise Exception(f"[{time}ns]: Task {self.task_id} has not released any jobs")
    if self.is_executing:
      raise Exception(f"[{time}ns]: Task {self.task_id} is already running (job id: {self.job_id})")
    if self.is_completed:
      raise Exception(f"[{time}ns]: Task {self.task_id} is already completed (job id: {self.job_id})")
    
    if self.last_cpu_id not in [-1, cpu_id]:
      self.migrations += 1

    self.last_cpu_id = cpu_id
    self.is_executing = True
    self.exec_start_time = time

  def preempt(self, time: int) -> None:
    if self.job_id == -1:
      raise Exception(f"[{time}ns]: Task {self.task_id} has not released any jobs")
    if not self.is_executing:
      raise Exception(f"[{time}ns]: Task {self.task_id} is already preempted (job id: {self.job_id})")
    
    self.is_executing = False
    if self.exec_blocks is not None: self.exec_blocks.append(ExecBlock(self.task_id, self.job_id, self.last_cpu_id, self.exec_start_time, time))

  def complete(self, time: int) -> None:
    if self.job_id == -1:
      raise Exception(f"[{time}ns]: Task {self.task_id} has not released any jobs")
    if self.is_completed:
      raise Exception(f"[{time}ns]: Task {self.task_id} is already finished (job id: {self.job_id})")
    if self.last_cpu_id == -1:
      raise Exception(f"[{time}ns]: Task {self.task_id} cannot complete without executing (job id: {self.job_id})")
    
    if self.is_executing:
      self.preempt(time)
    
    self.is_completed = True
    self.completed_jobs.append(CompletedJob(
      self.task_id, self.job_id,
      self.release_time, self.release_time + self.params.deadline, time,
      CompletedJob.ExitStatus.SUCCESS,
      self.exec_blocks
    ))

  def abort(self, time: int, is_deadline_overrun: bool) -> None:
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
  
# represents a completed taskset
class CompletedTaskset:
  def __init__(self, tasks: list[Task], init_time: int, completion_time: int):
    self.tasks = tasks
    self.jobs: list[CompletedJob] = [ job for task in tasks for job in task.completed_jobs ]
    self.jobs.sort(key = lambda job : job.release_time)
    self.init_time = init_time
    self.completion_time = completion_time
    self.cpu_ids = list(set([ exec_block.cpu_id for task in tasks for job in task.completed_jobs if job.exec_blocks is not None for exec_block in job.exec_blocks ]))
