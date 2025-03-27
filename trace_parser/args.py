import argparse
import os

class Args:
  do_render = False
  verbose = False

def dir_path(string) -> str:
  if os.path.isdir(string):
    return string
  else:
    raise NotADirectoryError(string)

def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Extract data from experiments lttng trace data")
  parser.add_argument("path", help="Path to LTTNG trace data", type=dir_path)
  parser.add_argument("-r", "--render", help="Render visualization of job executions", action=argparse.BooleanOptionalAction)
  parser.add_argument("-v", "--verbose", help="Output debug logs", action=argparse.BooleanOptionalAction)
  args = parser.parse_args()
  Args.do_render = args.render
  Args.verbose = args.verbose
  Args.path = args.path