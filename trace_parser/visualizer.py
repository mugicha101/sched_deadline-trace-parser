# Visualizes two timelines composed of tracks of execution blocks:
#   Task Timeline: each track mapped to a task
#   Core Timeline: each track mapped to a core
# export as an svg image

from task_model import *

import xml.etree.ElementTree as ET

TIME_SCALE = 1 / 1000000
TRACK_HEIGHT = 100
TIMELINE_SEPARATION = 200
MARGIN_PADDING = 50
BLOCK_HEIGHT = 50
BLOCK_BORDER_THICKNESS = 2
ARROW_HEIGHT = 80
ARROW_LINE_THICKNESS = 3
ARROW_HEAD_WIDTH = 10
ARROW_HEAD_HEIGHT = 10
COMPLETION_HEIGHT = 90
COMPLETION_WIDTH = 10
COMPLETION_LINE_THICKNESS = 5
TRACK_LINE_HEIGHT = 3

def rgb(r: float, g: float, b: float) -> str:
  return f"rgb({round(r * 255)}, {round(g * 255)}, {round(b * 255)})"

BG_COLOR = rgb(1, 1, 0.8)
CORE_COLORS = [ rgb(1, 0.8, 0.8), rgb(1, 0.9, 0.8), rgb(1, 1, 0.8), rgb(0.9, 1, 0.8), rgb(0.8, 1, 0.8)]
BLOCK_BORDER_COLOR = rgb(0, 0, 0)
RELEASE_COLOR = rgb(0, 0.5, 0)
DEADLINE_COLOR = rgb(0, 0, 0.5)

def render(taskset: CompletedTaskset):
  print([ f"{job.task_id}.{job.job_id}" for job in taskset.jobs ])

  task_y: dict[int, int] = dict([ task.task_id, 0 ] for task in taskset.tasks)
  for track_idx, task_id in enumerate(task_y.keys()):
    task_y[task_id] = track_idx * TRACK_HEIGHT + MARGIN_PADDING
  core_y: dict[int, int] = dict([ cpu_id, 0 ] for cpu_id in taskset.cpu_ids)
  for track_idx, cpu_id in enumerate(core_y.keys()):
    core_y[cpu_id] = (len(task_y) + track_idx) * TRACK_HEIGHT + TIMELINE_SEPARATION + MARGIN_PADDING
  core_color: dict[int, str] = dict([ item[0], CORE_COLORS[track_idx % len(CORE_COLORS)] ] for track_idx, item in enumerate(core_y.items()))

  duration = taskset.completion_time - taskset.init_time

  width = duration * TIME_SCALE + MARGIN_PADDING * 2
  height = (len(task_y) + len(core_y)) * TRACK_HEIGHT + TIMELINE_SEPARATION + MARGIN_PADDING * 2
  svg = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width=f"{width}", height=f"{height}")
  print(width, height)

  def draw_box(x=0, y=0, width=0, height=0, fill="white", stroke="black", stroke_width=0, text="", font_size=15, text_color="black"):
      ET.SubElement(svg, "rect", x=str(x), y=str(y), width=str(width), height=str(height), stroke=stroke, fill=fill, attrib={"stroke-width": str(stroke_width)})
      if len(text) > 0:
        ET.SubElement(svg, "text", x=str(x + width * 0.5), y=str(y + height * 0.5), fill=text_color, attrib={ "font-size": str(font_size), "dominant-baseline": "middle", "text-anchor": "middle" }).text = text
  
  draw_box(0, 0, width, height, BG_COLOR)

  def draw_exec_block(exec_block: ExecBlock, y: int):
    width = (exec_block.end_time - exec_block.start_time) * TIME_SCALE
    text = f"{exec_block.task_id},{exec_block.job_id}"
    color = core_color[exec_block.cpu_id]
    rx = (exec_block.start_time - taskset.init_time) * TIME_SCALE + MARGIN_PADDING
    ry = y + TRACK_HEIGHT - BLOCK_HEIGHT
    draw_box(
      rx, ry,
      width, BLOCK_HEIGHT,
      text = text,
      font_size = min(BLOCK_HEIGHT, width * 2 / len(text)),
      fill = BLOCK_BORDER_COLOR
    )
    draw_box(
      rx + BLOCK_BORDER_THICKNESS, ry + BLOCK_BORDER_THICKNESS,
      width - BLOCK_BORDER_THICKNESS * 2, BLOCK_HEIGHT - BLOCK_BORDER_THICKNESS,
      text = text,
      font_size = min(BLOCK_HEIGHT, width * 2 / len(text)),
      fill = color
    )

  def draw_arrow(time: int, y: int, up: bool, color: str):
    x = time * TIME_SCALE + MARGIN_PADDING
    y1 = y + TRACK_HEIGHT - (0 if up else ARROW_HEAD_HEIGHT)
    y2 = y + TRACK_HEIGHT - ARROW_HEIGHT + (ARROW_HEAD_HEIGHT if up else 0)
    ET.SubElement(
      svg,
      "line",
      x1=str(x),
      y1=str(y1),
      x2=str(x),
      y2=str(y2),
      stroke=color,
      attrib={
        "stroke-width": str(ARROW_LINE_THICKNESS)
      }
    )
    ay1 = y2 if up else y1
    ay2 = ay1 + (-ARROW_HEAD_HEIGHT if up else ARROW_HEAD_HEIGHT)
    arrowhead_points = f"{x - (ARROW_HEAD_WIDTH * 0.5)},{ay1} {x + (ARROW_HEAD_WIDTH * 0.5)},{ay1} {x},{ay2}"
    ET.SubElement(svg, 'polygon', points=arrowhead_points, fill=color)

  def draw_completion(time: int, y: int, exit_status: CompletedJob.ExitStatus):
    x = time * TIME_SCALE + MARGIN_PADDING
    match exit_status:
      case CompletedJob.ExitStatus.SUCCESS:
        color = "black"
      case CompletedJob.ExitStatus.ABORTED:
        color = "blue"
      case CompletedJob.ExitStatus.DEADLINE_OVERRUN:
        color = "red"
    ET.SubElement(
      svg,
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
      svg,
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
  
  # draw exec blocks
  for job in taskset.jobs:
    if job.exec_blocks is None:
      continue

    for exec_block in job.exec_blocks:
      # fill task track
      draw_exec_block(exec_block, task_y[exec_block.task_id])

      # fill core track
      draw_exec_block(exec_block, core_y[exec_block.cpu_id])

  # draw realtime events
  for job in taskset.jobs:
    y = task_y[job.task_id]

    # release
    draw_arrow(job.release_time - taskset.init_time, y, True, RELEASE_COLOR)

    # completion
    draw_completion(job.completion_time - taskset.init_time, y, job.exit_status)

    # deadline
    draw_arrow(job.absolute_deadline - taskset.init_time, y, False, DEADLINE_COLOR)

  # draw track lines
  for y in [ *task_y.values(), *core_y.values() ]:
    draw_box(0, y + TRACK_HEIGHT, width, TRACK_LINE_HEIGHT, "black")

  tree = ET.ElementTree(svg)
  tree.write("test.svg")
  