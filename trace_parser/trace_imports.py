import bt2
from bt2 import event as bt2_event, field as bt2_field, trace_collection_message_iterator
import argparse
import datetime

from typing import Callable, Any

TraceIterator = trace_collection_message_iterator.TraceCollectionMessageIterator
TraceEventMessage = bt2._EventMessageConst
TraceEvent = bt2_event._EventConst
TraceFields = bt2_field._StructureFieldConst

# pretty print time (either epoch or relative to start time)
def time2str(time, relative_to: int | None = None):
  fmt = "%m-%d-%Y %H:%M:%S" if relative_to is None else "%H:%M:%S"
  return datetime.datetime.fromtimestamp(time // 1000000000).strftime(fmt) + ":" + str(time % 1000000000).zfill(9)