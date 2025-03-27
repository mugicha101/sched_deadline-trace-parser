# task tracking logic

from task_model import *
from visualizer import render
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

  def set_time(self, time):
    if time < self.time:
      raise Exception(f"[{self.time}ns] Attempted to go back in time (new time: {time} < curr time: {self.time})")
    
    self.time = time

  def get_time(self) -> int:
    return self.time
  
  def get_cpu(self, tid: int) -> int:
    return self.thread_cpu[tid] if tid in self.thread_cpu else -1

  def new_taskset(self):
    if not self.is_complete:
      raise Exception(f"[{self.time}ns] Cannot create new taskset when current one is not complete (current taskset: {self.taskset_id})")
    
    self.taskset_id += 1
    self.tasks = []
    self.id_map = {}
    self.is_complete = False
    self.taskset_init_time = self.time

  def complete_taskset(self):
    if self.is_complete:
      raise Exception(f"[{self.time}ns] No active taskset (last taskset: {self.taskset_id})")
    
    self.is_complete = True
    for task in self.tasks:
      task.abort(self.time, False)

    taskset = CompletedTaskset(self.tasks, self.taskset_init_time, self.time)
    self.completed_tasksets.append(taskset)

    if Args.do_render:
      render(taskset)

  def get_task(self, tid) -> Task | None:
    if self.is_complete:
      return None
    
    return self.tasks[self.id_map[tid]] if tid in self.id_map else None

  def add_task(self, tid: int, params: TaskParams):
    if self.is_complete:
      raise Exception(f"[{self.time}ns] No active taskset (last taskset: {self.taskset_id})")
    
    if tid in self.id_map:
      raise Exception(f"[{self.time}ns] Multiple tasks mapped to same thread (tid={tid}):\n    existing task: {self.get_task(tid).params}\n    incoming task: {params}")
    
    self.tasks.append(Task(len(self.tasks), params, self.time, self.get_cpu(tid)))
    self.id_map[tid] = self.tasks[-1].task_id
    
    if Args.verbose: print(f"tid={tid} mapped to task {self.tasks[-1]}")

  def execute(self, tid: int, cpu_id: int):
    self.thread_cpu[tid] = cpu_id
    task = self.get_task(tid)
    if task is None:
      return
    
    task.execute(self.time, cpu_id)

  def preempt(self, tid: int):
    if tid not in self.thread_cpu:
      return
    
    del self.thread_cpu[tid]
    task = self.get_task(tid)
    if task is None:
      return
    
    task.preempt(self.time)

  def release(self, tid: int):
    task = self.get_task(tid)
    task.release(self.time, self.get_cpu(tid))

  def complete(self, tid):
    task = self.get_task(tid)
    task.complete(self.time)

  def deadline_overrun(self, tid):
    task = self.get_task(tid)
    task.abort(self.time, True)