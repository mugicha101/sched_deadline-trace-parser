# task tracking logic

from task_model import *
from visualizer import render

# represents the execution state of a taskset at a specific point in time
class TaskTracker:
  def __init__(self, do_render = False):
    self.do_render = do_render
    self.time = -1
    self.tasks: list[Task] = []
    self.id_map: dict[tuple[int,int], int] = {} # (vpid, vtid) -> task id
    self.completed_tasksets: list[CompletedTaskset] = []
    self.is_complete = True
    self.taskset_id = -1
    self.taskset_init_time = -1

  def set_time(self, time):
    if time < self.time:
      raise Exception(f"[{self.time}ns] Attempted to go back in time (new time: {time} < curr time: {self.time})")
    
    self.time = time

  def get_time(self) -> int:
    return self.time

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

    if self.do_render:
      render(taskset)

  def get_task(self, vpid, vtid) -> Task | None:
    if self.is_complete:
      raise Exception(f"[{self.time}ns] No active taskset (last taskset: {self.taskset_id})")
    
    key = (vpid, vtid)
    return self.tasks[self.id_map[key]] if key in self.id_map else None

  def add_task(self, vpid: int, vtid: int, params: TaskParams):
    if self.is_complete:
      raise Exception(f"[{self.time}ns] No active taskset (last taskset: {self.taskset_id})")
    
    key = (vpid, vtid)
    if key in self.id_map:
      raise Exception(f"[{self.time}ns] Multiple tasks mapped to same thread (vpid={vpid}, vtid={vtid}):\n    existing task: {self.get_task(vpid, vtid).params}\n    incoming task: {params}")
    self.tasks.append(Task(len(self.tasks), params, self.time, do_render=self.do_render))
    self.id_map[key] = self.tasks[-1].task_id
