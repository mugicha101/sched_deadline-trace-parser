# Visualizes two timelines composed of tracks of execution blocks:
#   Task Timeline: each track mapped to a task
#   Core Timeline: each track mapped to a core
# export as an svg image

from task_model import *

import xml.etree.ElementTree as ET

TIME_SCALE = 1 / 1000000
TRACK_HEIGHT = 100
TIMELINE_SEPARATION = 200
MARGIN_PADDING = 500
BLOCK_HEIGHT = 50
BLOCK_BORDER_THICKNESS = 1
ARROW_HEIGHT = 80
ARROW_LINE_THICKNESS = 3
ARROW_HEAD_WIDTH = 10
ARROW_HEAD_HEIGHT = 10
COMPLETION_HEIGHT = 90
COMPLETION_WIDTH = 10
COMPLETION_LINE_THICKNESS = 5
TRACK_LINE_HEIGHT = 3
INIT_EVENT_WIDTH = 30
INIT_EVENT_HEIGHT = 60
TASKSET_COMPLETION_WIDTH = 20
MARKER_FONT_SIZE = 5

def rgb(r: float, g: float, b: float) -> str:
  return f"rgb({round(r * 255)}, {round(g * 255)}, {round(b * 255)})"

def rgba(r: float, g: float, b: float, a: float) -> str:
  return f"rgba({round(r * 255)}, {round(g * 255)}, {round(b * 255)}, {a})"

BG_COLOR = rgb(1, 1, 1)
CORE_COLORS = [ rgb(1, 0.8, 0.8), rgb(1, 0.9, 0.8), rgb(1, 1, 0.8), rgb(0.9, 1, 0.8), rgb(0.8, 1, 0.8)]
BLOCK_BORDER_COLOR = rgb(0, 0, 0)
RELEASE_COLOR = rgb(0, 0.5, 0)
DEADLINE_COLOR = rgb(0, 0, 0.5)
INIT_EVENT_COLOR = rgb(0, 0, 0)
TASKSET_COMPLETION_COLOR = rgb(0, 0, 0)
SCHED_BLOCK_COLOR = rgb(0.5, 0.5, 0.5)

def render(taskset: CompletedTaskset):
  task_y: dict[int, int] = dict([ task.task_id, 0 ] for task in taskset.tasks)
  for track_idx, task_id in enumerate(task_y.keys()):
    task_y[task_id] = track_idx * TRACK_HEIGHT + MARGIN_PADDING
  core_y: dict[int, int] = dict([ cpu_id, 0 ] for cpu_id in taskset.cpu_ids)
  for track_idx, cpu_id in enumerate(core_y.keys()):
    core_y[cpu_id] = (len(task_y) + track_idx) * TRACK_HEIGHT + TIMELINE_SEPARATION + MARGIN_PADDING
  core_color: dict[int, str] = dict([ item[0], CORE_COLORS[track_idx % len(CORE_COLORS)] ] for track_idx, item in enumerate(core_y.items()))

  duration = taskset.completion_time - taskset.init_time

  img_width = duration * TIME_SCALE + MARGIN_PADDING * 2
  img_height = (len(task_y) + len(core_y)) * TRACK_HEIGHT + TIMELINE_SEPARATION + MARGIN_PADDING * 2
  svg = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width=f"{img_width}", height=f"{img_height}")
  geo_group = ET.SubElement(svg, "g")
  ui_bg_group = ET.SubElement(svg, "g")
  ui_group = ET.SubElement(svg, "g")

  def rect_font_size(width, height, text):
    return min(height, width * 2 / max(len(text), 1))

  def draw_box(x=0, y=0, width=0, height=0, fill="white", stroke="black", stroke_width=0, text="", font_size=15, text_color="black", group=geo_group):
      ET.SubElement(group, "rect", x=str(x), y=str(y), width=str(width), height=str(height), stroke=stroke, fill=fill, attrib={"stroke-width": str(stroke_width)})
      if len(text) > 0:
        ET.SubElement(ui_group, "text", x=str(x + width * 0.5), y=str(y + height * 0.5), fill=text_color, attrib={ "font-size": str(font_size), "dominant-baseline": "middle", "text-anchor": "middle" }).text = text
  
  draw_box(0, 0, img_width, img_height, BG_COLOR)

  def draw_time(time, x, y, label = ""):
    ms = time // 1000000
    text_ms = f"{ms}ms"
    text_ns = f"+{time % 1000000}ns"
    draw_box(x-MARKER_FONT_SIZE * 2, y - MARKER_FONT_SIZE * 0.25, MARKER_FONT_SIZE * 4, MARKER_FONT_SIZE * (2 if len(label) == 0 else 2.5), rgba(1, 1, 1, 0.8), group=ui_bg_group)
    ET.SubElement(ui_group, "text", x=str(x), y=str(y), fill="black", attrib={ "font-size": str(MARKER_FONT_SIZE), "dominant-baseline": "hanging", "text-anchor": "middle" }).text = f"{text_ms}"
    ET.SubElement(ui_group, "text", x=str(x), y=str(y+MARKER_FONT_SIZE), fill="black", attrib={ "font-size": str(MARKER_FONT_SIZE * 0.5), "dominant-baseline": "hanging", "text-anchor": "middle" }).text = f"{text_ns}"
    if len(label) > 0:
      ET.SubElement(ui_group, "text", x=str(x), y=str(y+MARKER_FONT_SIZE * 1.5), fill="black", attrib={ "font-size": str(MARKER_FONT_SIZE * 0.5), "dominant-baseline": "hanging", "text-anchor": "middle" }).text = label

  # draw a small marker at a certain point in time
  marker_pos: list[tuple[float,float]] = []
  def draw_marker(time, track_y, name=""):
    x = time * TIME_SCALE + MARGIN_PADDING
    y = track_y + TRACK_HEIGHT + TRACK_LINE_HEIGHT + MARKER_FONT_SIZE * 0.25
    valid = False
    while not valid:
      valid = True
      for ox, oy in marker_pos:
        if oy == y and abs(ox - x) <= MARKER_FONT_SIZE * 4:
          valid = False
          y += MARKER_FONT_SIZE * 2.5
    marker_pos.append((x, y))
    draw_time(time, x, y, name)

  def draw_block(start_time: int, end_time: int, y: int, text: str, color: str):
    width = (end_time - start_time) * TIME_SCALE
    rx = start_time * TIME_SCALE + MARGIN_PADDING
    ry = y + TRACK_HEIGHT - BLOCK_HEIGHT

    # border
    draw_box(
      rx, ry,
      width, BLOCK_HEIGHT,
      text = text,
      font_size = rect_font_size(width, BLOCK_HEIGHT, text),
      fill = BLOCK_BORDER_COLOR
    )
    if width > BLOCK_BORDER_THICKNESS * 2:
      # body
      draw_box(
        rx + BLOCK_BORDER_THICKNESS, ry + BLOCK_BORDER_THICKNESS,
        width - BLOCK_BORDER_THICKNESS * 2, BLOCK_HEIGHT - BLOCK_BORDER_THICKNESS,
        font_size = rect_font_size(width, BLOCK_HEIGHT, text),
        fill = color
      )

    # duration
    draw_time(end_time - start_time, rx + width * 0.5, ry - MARKER_FONT_SIZE * 2)

    # markers
    draw_marker(start_time, y, f"cpu {cpu_id}")
    draw_marker(end_time, y, f"cpu -1")

  def draw_exec_block(exec_block: ExecBlock):
    text = f"{exec_block.task_id},{exec_block.job_id}"
    color = core_color[exec_block.cpu_id]
    for y in [ task_y[exec_block.task_id], core_y[exec_block.cpu_id] ]:
      draw_block(exec_block.start_time - taskset.init_time, exec_block.end_time - taskset.init_time, y, text, color)

  def draw_sched_block(sched_block: SchedBlock):
    ys = [ core_y[sched_block.cpu_id] ]

    for task_id in [ sched_block.prev_task_id, sched_block.next_task_id ]:
      if task_id != -1:
        ys.append(task_y[task_id])

    for y in ys:
      draw_block(sched_block.start_time - taskset.init_time, sched_block.end_time - taskset.init_time, y, "", SCHED_BLOCK_COLOR)

  def draw_arrow(time: int, y: int, up: bool, color: str, job_id: int):
    x = time * TIME_SCALE + MARGIN_PADDING
    y1 = y + TRACK_HEIGHT - (0 if up else ARROW_HEAD_HEIGHT)
    y2 = y + TRACK_HEIGHT - ARROW_HEIGHT + (ARROW_HEAD_HEIGHT if up else 0)
    ET.SubElement(
      geo_group,
      "line",
      x1=str(x),
      y1=str(y1),
      x2=str(x),
      y2=str(y2-1),
      stroke=color,
      attrib={
        "stroke-width": str(ARROW_LINE_THICKNESS)
      }
    )
    ay1 = y2 if up else y1
    ay2 = ay1 + (-ARROW_HEAD_HEIGHT if up else ARROW_HEAD_HEIGHT)
    arrowhead_points = f"{x - (ARROW_HEAD_WIDTH * 0.5)},{ay1} {x + (ARROW_HEAD_WIDTH * 0.5)},{ay1} {x},{ay2}"
    ET.SubElement(geo_group, 'polygon', points=arrowhead_points, fill=color)
    draw_marker(time, y, f"J{job_id} release" if up else f"J{job_id} deadline")

  def draw_completion(time: int, y: int, job_id: int, exit_status: CompletedJob.ExitStatus):
    x = time * TIME_SCALE + MARGIN_PADDING
    match exit_status:
      case CompletedJob.ExitStatus.SUCCESS:
        color = "black"
      case CompletedJob.ExitStatus.ABORTED:
        color = "blue"
      case CompletedJob.ExitStatus.DEADLINE_OVERRUN:
        color = "red"
    ET.SubElement(
      geo_group,
      "line",
      x1=str(x),
      y1=str(y + TRACK_HEIGHT),
      x2=str(x),
      y2=str(y + TRACK_HEIGHT - COMPLETION_HEIGHT),
      stroke=color,
      attrib={
        "stroke-width": str(COMPLETION_LINE_THICKNESS)
      }
    )
    ET.SubElement(
      geo_group,
      "line",
      x1=str(x - COMPLETION_WIDTH),
      y1=str(y + TRACK_HEIGHT - COMPLETION_HEIGHT),
      x2=str(x + COMPLETION_WIDTH),
      y2=str(y + TRACK_HEIGHT - COMPLETION_HEIGHT),
      stroke=color,
      attrib={
        "stroke-width": str(COMPLETION_LINE_THICKNESS)
      }
    )
    exit_status_str = str(exit_status).split(".")[1].lower().replace("_", " ")
    draw_marker(time, y, f"J{job_id} {exit_status_str}")
  
  # draw exec blocks
  for job in taskset.jobs:
    if job.exec_blocks is None:
      continue

    for exec_block in job.exec_blocks:
      draw_exec_block(exec_block)

  # draw sched blocks
  for sched_block in taskset.sched_blocks:
    # draw_sched_block(sched_block)
    pass # disabled for now until theres a better way to display small blocks

  # draw realtime events
  for job in taskset.jobs:
    y = task_y[job.task_id]
    params = taskset.tasks[job.task_id].params

    # release
    draw_arrow(job.release_time - taskset.init_time, y, True, RELEASE_COLOR, job.job_id)

    # completion
    draw_completion(job.completion_time - taskset.init_time, y, job.job_id, job.exit_status)

    # deadline
    if params.period != params.deadline: draw_arrow(job.absolute_deadline - taskset.init_time, y, False, DEADLINE_COLOR, job.job_id)

  # draw task inits
  for task in taskset.tasks:
    y = task_y[task.task_id]
    x = (task.init_time - taskset.init_time) * TIME_SCALE
    text = str(task)
    draw_box(
      x, y + TRACK_HEIGHT - BLOCK_HEIGHT,
      MARGIN_PADDING , BLOCK_HEIGHT - BLOCK_BORDER_THICKNESS,
      text = text,
      font_size = rect_font_size(MARGIN_PADDING, BLOCK_HEIGHT, text),
      fill = "none"
    )
    triangle_pts = f"{x + MARGIN_PADDING - (INIT_EVENT_WIDTH * 0.5)},{y + TRACK_HEIGHT} {x + MARGIN_PADDING + (INIT_EVENT_WIDTH * 0.5)},{y + TRACK_HEIGHT} {x + MARGIN_PADDING},{y + TRACK_HEIGHT - INIT_EVENT_HEIGHT}"
    ET.SubElement(geo_group, 'polygon', points=triangle_pts, fill=INIT_EVENT_COLOR)
    draw_marker(task.init_time - taskset.init_time, y, f"T{task.task_id} init")
  
  # draw taskset completion
  tcx = duration * TIME_SCALE + MARGIN_PADDING
  draw_box(
    tcx, MARGIN_PADDING,
    TASKSET_COMPLETION_WIDTH, img_height - MARGIN_PADDING * 2,
    fill = TASKSET_COMPLETION_COLOR
  )

  # draw track lines
  for y in [ *task_y.values(), *core_y.values() ]:
    draw_box(0, y + TRACK_HEIGHT, img_width, TRACK_LINE_HEIGHT, "black")

  tree = ET.ElementTree(svg)
  tree.write("test.svg")
  