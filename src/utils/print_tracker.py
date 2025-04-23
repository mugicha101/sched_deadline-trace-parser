import builtins

print_count = {
  "amount": 0
}

if not hasattr(builtins, "_original_print"):
    builtins._original_print = builtins.print

def print(*args, **kwargs):
  builtins._original_print(*args, **kwargs)
  print_count["amount"] += 1

builtins.print = print
