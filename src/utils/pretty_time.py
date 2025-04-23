import datetime

# pretty print time (either epoch or relative to start time)
def time2str(time, relative_to: int | None = None):
  # for some reason trace compass offsets tracepoints by a certain amount
  fmt = "%m-%d-%Y %H:%M:%S" if relative_to is None else "%H:%M:%S"
  nano = str(time % 1000000000).zfill(9)
  return datetime.datetime.fromtimestamp(time // 1000000000).strftime(fmt) + "." + nano[:3] + " " + nano[3:6] + " " + nano[6:]
