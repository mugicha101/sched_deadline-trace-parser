import bt2
from bt2 import event as bt2_event, field as bt2_field, trace_collection_message_iterator
from pretty_time import *
from args import *

from typing import Callable, Any

TraceIterator = trace_collection_message_iterator.TraceCollectionMessageIterator
TraceEventMessage = bt2._EventMessageConst
TraceEvent = bt2_event._EventConst
TraceFields = bt2_field._StructureFieldConst
