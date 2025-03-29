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
    self.cpus: dict[int, CPUState] = {} # cpu id -> cpu state

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

    # abort any running tasks
    for task in self.tasks:
      task.abort(self.time, False)

    # filter the sched blocks for those generated for the tasks in the taskset
    # order by start time
    sched_blocks: list[SchedBlock] = []
    for cpu in self.cpus.values():
      for i in range(len(cpu.sched_blocks)-1, -1, -1):
        sched_block = cpu.sched_blocks[i]
        if sched_block.start_time < self.taskset_init_time:
          break

        prev_task = self.get_task(sched_block.prev_tid)
        next_task = self.get_task(sched_block.next_tid)

        # TODO: pretty sure this never happens due to context swithces to stuff like rcu_preempt and ktimers/n
        # figure out a more robust way to map the scheduling event to a task
        if prev_task is not None:
          sched_block.prev_task_id = prev_task.task_id
        if next_task is not None:
          sched_block.next_task_id = next_task.task_id
        
        sched_blocks.append(sched_block)
    sched_blocks.sort(key=lambda sb : sb.start_time )

    taskset = CompletedTaskset(self.tasks, sched_blocks, self.taskset_init_time, self.time)

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
    task.release(self.time, self.get_thread_cpu_id(tid))

  def complete(self, tid):
    task = self.get_task(tid)
    task.complete(self.time)

  def deadline_overrun(self, tid):
    task = self.get_task(tid)
    task.abort(self.time, True)

  def resched_enter(self, cpu_id):
    cpu = self.get_cpu(cpu_id)
    cpu.resched_enter(self.time)

  def resched_exit(self, cpu_id):
    cpu = self.get_cpu(cpu_id)
    cpu.resched_exit(self.time)