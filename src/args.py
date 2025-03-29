import argparse
import os

# global way to access args
class Args:
  pass

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
  parser.add_argument("-o", "--output-path", help="Path to output to", default="./output")
  args = parser.parse_args()
  for field in vars(args):
    setattr(Args, field, getattr(args, field))